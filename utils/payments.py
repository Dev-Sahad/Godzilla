"""
Razorpay payment integration.
Handles order creation, signature verification, and plan activation.
"""
import hmac
import hashlib
import logging
from datetime import datetime, timedelta
import razorpay
from config import (
    RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET,
)
from database.models import get_session, User, Payment, SubscriptionPlan

logger = logging.getLogger(__name__)

# Initialize Razorpay client (only if keys are set)
client = None
if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    try:
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    except Exception as e:
        logger.error(f"Razorpay init failed: {e}")


def is_configured():
    """Check if Razorpay is set up."""
    return client is not None


def get_plans():
    """Get all active plans from database."""
    session = get_session()
    try:
        plans = (
            session.query(SubscriptionPlan)
            .filter_by(is_active=True)
            .order_by(SubscriptionPlan.sort_order)
            .all()
        )
        return {
            p.key: {
                "name": p.name,
                "category": getattr(p, "category", None) or "premium",
                "badge": getattr(p, "badge", None) or "",
                "amount": p.amount,
                "duration_days": p.duration_days,
                "daily_limit": p.daily_limit,
                "description": p.description,
            }
            for p in plans
        }
    finally:
        session.close()


def get_plan(plan_key):
    """Get one plan by key."""
    plans = get_plans()
    return plans.get(plan_key)


def create_payment_order(telegram_id, plan_key):
    """
    Create a Razorpay order for a subscription plan.
    Returns dict with order_id, amount, currency, payment_link (None if error).
    """
    if not is_configured():
        return None

    plan = get_plan(plan_key)
    if not plan:
        return None

    amount_paise = plan["amount"] * 100  # Razorpay uses paise

    try:
        # Create order
        order = client.order.create({
            "amount": amount_paise,
            "currency": "INR",
            "notes": {
                "telegram_id": str(telegram_id),
                "plan": plan_key,
            },
        })

        # Save order to DB
        session = get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                payment = Payment(
                    user_id=user.id,
                    telegram_id=telegram_id,
                    razorpay_order_id=order["id"],
                    plan=plan_key,
                    amount=amount_paise,
                    currency="INR",
                    status="created",
                )
                session.add(payment)
                session.commit()
        finally:
            session.close()

        # Build payment link (Razorpay hosted checkout)
        # User will be redirected to this URL
        payment_link = create_payment_link(telegram_id, plan_key, order["id"])

        return {
            "order_id": order["id"],
            "amount": plan["amount"],
            "currency": "INR",
            "payment_link": payment_link,
        }
    except Exception as e:
        logger.error(f"Razorpay order error: {e}")
        return None


def create_payment_link(telegram_id, plan_key, order_id):
    """
    Create a Razorpay Payment Link (a shareable URL for payment).
    This is easier than building your own checkout page.
    """
    if not is_configured():
        return None

    plan = get_plan(plan_key)
    if not plan:
        return None

    try:
        expiry = int((datetime.utcnow() + timedelta(hours=1)).timestamp())

        link_data = {
            "amount": plan["amount"] * 100,
            "currency": "INR",
            "accept_partial": False,
            "expire_by": expiry,
            "reference_id": f"godzilla_{telegram_id}_{order_id}",
            "description": f"GODZILLA {plan['name']} Subscription",
            "notes": {
                "telegram_id": str(telegram_id),
                "plan": plan_key,
                "order_id": order_id,
            },
            "notify": {
                "sms": False,
                "email": False,
            },
            "reminder_enable": False,
        }

        link = client.payment_link.create(link_data)
        return link.get("short_url")
    except Exception as e:
        logger.error(f"Payment link error: {e}")
        return None


def verify_webhook_signature(payload_body, signature):
    """
    Verify that a webhook request actually came from Razorpay.
    Prevents fake activation attempts.
    """
    if not RAZORPAY_WEBHOOK_SECRET:
        logger.warning("No webhook secret configured!")
        return False

    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def activate_premium(telegram_id, plan_key):
    """
    Grant premium to a user after successful payment.
    Returns True on success.
    """
    plan = get_plan(plan_key)
    if not plan:
        return False

    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return False

        # If user already has active premium, extend instead of reset
        now = datetime.utcnow()
        base = user.subscription_expires_at if (
            user.subscription_expires_at and user.subscription_expires_at > now
        ) else now

        user.is_premium = True
        user.subscription_plan = plan_key
        user.subscription_expires_at = base + timedelta(days=plan["duration_days"])
        session.commit()
        logger.info(f"✅ Premium activated for {telegram_id} until {user.subscription_expires_at}")
        return True
    except Exception as e:
        logger.error(f"Activate premium error: {e}")
        return False
    finally:
        session.close()


def mark_payment_paid(order_id, payment_id):
    """Mark a payment as paid in DB."""
    session = get_session()
    try:
        payment = session.query(Payment).filter_by(razorpay_order_id=order_id).first()
        if payment:
            payment.status = "paid"
            payment.razorpay_payment_id = payment_id
            payment.paid_at = datetime.utcnow()
            session.commit()
            return payment.telegram_id, payment.plan
        return None, None
    finally:
        session.close()


def check_and_expire_subscriptions():
    """
    Run periodically — downgrades users whose premium has expired.
    Returns list of telegram_ids that were expired (for notifications).
    """
    session = get_session()
    expired = []
    try:
        now = datetime.utcnow()
        users = session.query(User).filter(
            User.is_premium.is_(True),
            User.subscription_expires_at.isnot(None),
            User.subscription_expires_at < now,
        ).all()

        for user in users:
            user.is_premium = False
            expired.append(user.telegram_id)

        if expired:
            session.commit()
            logger.info(f"Expired {len(expired)} subscriptions")
        return expired
    finally:
        session.close()
