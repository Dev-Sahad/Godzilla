"""
Manual UPI Payment Handler with UTR Verification.

Flow:
1. User runs /subscribe → picks plan
2. Bot shows UPI ID + QR + amount
3. User pays via UPI app
4. User sends UTR to bot
5. Bot notifies admin with approve/reject buttons
6. Admin taps approve → premium activates
"""
import os
import re
import json
import logging
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto, InputFile,
)
from telegram.ext import ContextTypes

from config import (
    UPI_ID, UPI_NAME, UPI_QR_FILENAME, MAX_PENDING_PER_USER,
)
from database.models import (
    get_session, User, PaymentRequest, UserState, SubscriptionPlan,
)
from database import get_or_create_user
from utils.payments import get_plans, get_plan, activate_premium
from utils import notify_admin_action
from database.helpers import is_bot_admin, get_all_admin_ids

logger = logging.getLogger(__name__)

# UTR format: exactly 12 digits (standard Indian UPI reference number)
UTR_REGEX = re.compile(r"^\d{12}$")


# ========== USER STATE HELPERS ==========

def set_state(telegram_id, state, data=None):
    """Set user's conversation state."""
    session = get_session()
    try:
        us = session.query(UserState).filter_by(telegram_id=telegram_id).first()
        data_json = json.dumps(data) if data else None
        if us:
            us.state = state
            us.state_data = data_json
        else:
            us = UserState(telegram_id=telegram_id, state=state, state_data=data_json)
            session.add(us)
        session.commit()
    finally:
        session.close()


def get_state(telegram_id):
    """Get user's state. Returns (state, data_dict) or (None, {})."""
    session = get_session()
    try:
        us = session.query(UserState).filter_by(telegram_id=telegram_id).first()
        if not us or not us.state:
            return None, {}
        data = json.loads(us.state_data) if us.state_data else {}
        return us.state, data
    finally:
        session.close()


def clear_state(telegram_id):
    """Clear user's state."""
    session = get_session()
    try:
        us = session.query(UserState).filter_by(telegram_id=telegram_id).first()
        if us:
            us.state = None
            us.state_data = None
            session.commit()
    finally:
        session.close()


async def send_myplan_info(context, telegram_id):
    """Send /myplan info to user (used after approval)."""
    try:
        session = get_session()
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                return

            is_premium = user.is_premium
            plan_key = user.subscription_plan or ""
            plan_info = get_plan(plan_key) if plan_key else {}
            plan_name = (plan_info or {}).get("name") or plan_key or "Free"
            expiry = user.subscription_expires_at
            daily_limit = getattr(user, "custom_limit", None) or (100 if is_premium else 3)

            if is_premium and expiry:
                days_left = max(0, (expiry - datetime.utcnow()).days)
                expiry_str = expiry.strftime("%d %B %Y")
                status = "💎 *PREMIUM ACTIVE*"
            else:
                days_left = 0
                expiry_str = "N/A"
                status = "🆓 *FREE TIER*"

            text = (
                f"{status}\n\n"
                "━━━━━━━━━━━━━━━\n"
                f"👤 *Your Plan:* {plan_name}\n"
                f"📥 *Daily Limit:* {daily_limit} downloads\n"
                f"📅 *Valid Until:* {expiry_str}\n"
                f"⏰ *Days Left:* {days_left}\n"
                "━━━━━━━━━━━━━━━\n\n"
                "_Download away! 🦖_"
            )
        finally:
            session.close()

        await context.bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"send_myplan_info error: {e}")


# ========== SUBSCRIBE FLOW ==========

def is_upi_configured():
    """Check if UPI payment is set up."""
    return bool(UPI_ID)


async def subscribe_upi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show subscription plans for UPI payment."""
    user = update.effective_user

    if not is_upi_configured():
        await update.message.reply_text(
            "⚠️ *Payments not configured yet.*\n\n"
            "Contact the admin to enable premium subscriptions.",
            parse_mode="Markdown",
        )
        return

    get_or_create_user(user.id, user.username, user.first_name)

    plans = get_plans()
    if not plans:
        await update.message.reply_text(
            "⚠️ *No subscription plans available.*\n\nCheck back later!",
            parse_mode="Markdown",
        )
        return

    # Check pending count
    pending = count_pending(user.id)
    if pending >= MAX_PENDING_PER_USER:
        await update.message.reply_text(
            f"⚠️ *You have {pending} pending payments.*\n\n"
            f"Wait for approval before submitting new ones, or contact admin.",
            parse_mode="Markdown",
        )
        return

    keyboard = []
    text = "💎 *GODZILLA Premium Plans*\n\n"

    # Group by category
    categories_order = [
        ("basic", "🆓 *BASIC*"),
        ("premium", "💎 *PREMIUM*"),
        ("pro", "🔥 *PRO*"),
        ("lifetime", "👑 *LIFETIME*"),
        ("custom", "⚡ *CUSTOM*"),
    ]

    grouped = {}
    for key, plan in plans.items():
        cat = plan.get("category", "premium")
        grouped.setdefault(cat, []).append((key, plan))

    for cat_key, cat_label in categories_order:
        if cat_key not in grouped:
            continue
        text += f"{cat_label}\n━━━━━━━━━━━━━━\n"
        for key, plan in grouped[cat_key]:
            badge = f" 🏷 *{plan['badge']}*" if plan.get("badge") else ""
            text += (
                f"*{plan['name']}*{badge}\n"
                f"💰 ₹{plan['amount']} • {plan['duration_days']} days\n"
                f"📥 {plan['daily_limit']} downloads/day\n"
            )
            if plan.get("description"):
                text += f"_{plan['description']}_\n"
            text += "\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"{plan['name']} — ₹{plan['amount']}",
                    callback_data=f"upi_{key}",
                )
            ])

    text += (
        "✨ *Payment via UPI:*\n"
        "• PhonePe, GPay, Paytm, BHIM\n"
        "• 100% secure direct payment\n\n"
        "⚠️ *Manual verification:* After payment, send UTR to confirm."
    )

    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="upi_cancel")])

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def upi_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plan selection — show UPI payment info."""
    query = update.callback_query
    await query.answer()

    action = query.data

    if action == "upi_cancel":
        clear_state(query.from_user.id)
        await query.edit_message_text("❌ Cancelled.")
        return

    if action == "upi_confirm_cancel":
        clear_state(query.from_user.id)
        await query.edit_message_text(
            "❌ *Payment cancelled.*\n\n"
            "You can try again with /subscribe",
            parse_mode="Markdown",
        )
        return

    plan_key = action[4:]  # Remove "upi_" prefix
    plan = get_plan(plan_key)

    if not plan:
        await query.edit_message_text("❌ Invalid plan.")
        return

    user_id = query.from_user.id

    # Save state: awaiting UTR for this plan
    set_state(user_id, "awaiting_utr", {"plan": plan_key, "amount": plan["amount"]})

    text = (
        "💳 *Payment Details*\n\n"
        f"*Plan:* {plan['name']}\n"
        f"*Amount:* ₹{plan['amount']}\n"
        f"*Duration:* {plan['duration_days']} days\n\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "📱 *UPI ID:*\n"
        f"`{UPI_ID}`\n"
        "_(Tap UPI ID to copy)_\n\n"
        f"💰 *Amount:* `₹{plan['amount']}`\n\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "📋 *How to pay:*\n"
        f"1️⃣ Open GPay/PhonePe/Paytm\n"
        f"2️⃣ Send *exactly ₹{plan['amount']}* to above UPI ID\n"
        f"3️⃣ Copy the *12-digit UTR* from your UPI app\n"
        f"4️⃣ Send the UTR here as a message\n\n"
        "⚠️ *Important:*\n"
        "• Pay *exactly ₹" + str(plan["amount"]) + "* (wrong amount = rejection)\n"
        "• UTR = transaction reference number\n"
        "• Approval takes 5-30 minutes\n"
        "• Don't pay twice if approval is slow"
    )

    keyboard = [
        [InlineKeyboardButton("❌ Cancel Payment", callback_data="upi_confirm_cancel")],
    ]

    # Try to send QR image if available
    # Check multiple possible paths (relative, absolute, uploads dir)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    possible_paths = [
        os.path.join(base_dir, "web", "static", UPI_QR_FILENAME),
        os.path.join("web", "static", UPI_QR_FILENAME),
        os.path.join(base_dir, "uploads", UPI_QR_FILENAME),
        UPI_QR_FILENAME,
    ]

    qr_path = None
    for path in possible_paths:
        if os.path.exists(path):
            qr_path = path
            logger.info(f"QR found at: {qr_path}")
            break

    if qr_path:
        try:
            with open(qr_path, "rb") as qr:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=qr,
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            try:
                await query.delete_message()
            except Exception:
                pass
            return
        except Exception as e:
            logger.error(f"QR send error: {e}")
    else:
        logger.warning(f"QR not found. Searched: {possible_paths}")

    # Fallback: text only if no QR file
    await query.edit_message_text(
        text + "\n\n_💡 Tip: Use UPI ID above to pay_",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


# ========== UTR HANDLER ==========

async def maybe_handle_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Check if user is in 'awaiting_utr' state and handle their message.
    Returns True if handled, False otherwise.
    """
    user = update.effective_user
    state, data = get_state(user.id)

    if state != "awaiting_utr":
        return False

    text = update.message.text.strip() if update.message.text else ""

    # Clean UTR (remove spaces, dashes)
    utr = re.sub(r"[\s\-]", "", text)

    # Validate UTR format
    if not UTR_REGEX.match(utr):
        await update.message.reply_text(
            "❌ *Invalid UTR format.*\n\n"
            "UTR must be exactly *12 digits*.\n\n"
            "Where to find UTR:\n"
            "• *GPay:* Transaction → UPI reference ID\n"
            "• *PhonePe:* Transaction → UPI ID\n"
            "• *Paytm:* Transaction → UPI Reference No.\n\n"
            "Please send the 12-digit number only.",
            parse_mode="Markdown",
        )
        return True

    plan_key = data.get("plan")
    amount = data.get("amount")

    if not plan_key:
        clear_state(user.id)
        await update.message.reply_text(
            "❌ Session expired. Please start again with /subscribe"
        )
        return True

    # Check for duplicate UTR (fraud prevention)
    session = get_session()
    try:
        existing = session.query(PaymentRequest).filter_by(utr=utr).first()
        if existing:
            await update.message.reply_text(
                "⚠️ *This UTR is already submitted.*\n\n"
                "Each payment has a unique UTR. Check your UPI app again.",
                parse_mode="Markdown",
            )
            return True

        # Create payment request
        req = PaymentRequest(
            telegram_id=user.id,
            username=user.username,
            plan_key=plan_key,
            amount=amount,
            utr=utr,
            status="pending",
        )
        session.add(req)
        session.commit()
        req_id = req.id
    finally:
        session.close()

    clear_state(user.id)

    # Confirm to user
    await update.message.reply_text(
        "✅ *UTR received!*\n\n"
        f"*Plan:* {get_plan(plan_key).get('name', plan_key)}\n"
        f"*Amount:* ₹{amount}\n"
        f"*UTR:* `{utr}`\n"
        f"*Request ID:* `#{req_id}`\n\n"
        "⏳ *Waiting for admin approval...*\n"
        "You'll get a message once approved.\n"
        "Usually takes 5-30 minutes.\n\n"
        "_Thank you for your patience! 🦖_",
        parse_mode="Markdown",
    )

    # Notify all admins
    await notify_admins_new_payment(context, req_id, user, plan_key, amount, utr)
    return True


async def notify_admins_new_payment(context, req_id, user, plan_key, amount, utr):
    """Send approval notification to all admins."""
    plan = get_plan(plan_key) or {}
    plan_name = plan.get("name", plan_key)

    text = (
        "💰 *NEW PAYMENT REQUEST*\n\n"
        f"*Request ID:* `#{req_id}`\n"
        f"*User:* {user.first_name}"
        + (f" (@{user.username})" if user.username else "")
        + f"\n*Telegram ID:* `{user.id}`\n"
        f"*Plan:* {plan_name}\n"
        f"*Amount:* ₹{amount}\n"
        f"*UTR:* `{utr}`\n\n"
        "🔍 *Verify in your UPI app:*\n"
        "1. Open bank/UPI app\n"
        "2. Find recent ₹" + str(amount) + " credit\n"
        "3. Match UTR above\n"
        "4. Click below to decide:"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"pay_approve_{req_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"pay_reject_{req_id}"),
        ]
    ]

    for admin_id in get_all_admin_ids():
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


# ========== APPROVAL HANDLERS ==========

async def approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approve/reject button clicks by admin."""
    query = update.callback_query
    admin_id = query.from_user.id

    if not is_bot_admin(admin_id):
        await query.answer("🚫 Admin only!", show_alert=True)
        return

    await query.answer()

    data = query.data  # e.g., "pay_approve_5" or "pay_reject_5"
    parts = data.split("_")
    if len(parts) != 3:
        return

    action = parts[1]  # approve or reject
    try:
        req_id = int(parts[2])
    except ValueError:
        return

    await process_decision(context, query, req_id, action, admin_id)


async def process_decision(context, query_or_msg, req_id, action, admin_id):
    """Execute approval or rejection."""
    session = get_session()
    try:
        req = session.query(PaymentRequest).get(req_id)
        if not req:
            if query_or_msg:
                await query_or_msg.edit_message_text("❌ Request not found.")
            return

        if req.status != "pending":
            if query_or_msg:
                await query_or_msg.edit_message_text(
                    f"⚠️ Already processed: *{req.status}*\n\n"
                    f"By admin `{req.admin_id}` at {req.processed_at}",
                    parse_mode="Markdown",
                )
            return

        if action == "approve":
            # Activate premium
            if activate_premium(req.telegram_id, req.plan_key):
                req.status = "approved"
                req.admin_id = admin_id
                req.processed_at = datetime.utcnow()
                session.commit()

                # Notify user — approval confirmation
                plan = get_plan(req.plan_key) or {}
                try:
                    await context.bot.send_message(
                        chat_id=req.telegram_id,
                        text=(
                            "🎉 *Payment Approved!*\n\n"
                            f"✨ *{plan.get('name', 'Premium')}* activated!\n"
                            f"📥 *Daily Limit:* {plan.get('daily_limit', 100)} downloads\n"
                            f"📅 *Duration:* {plan.get('duration_days', 30)} days\n\n"
                            "_Thank you for supporting GODZILLA! 🦖_"
                        ),
                        parse_mode="Markdown",
                    )

                    # Auto-send /myplan status
                    await send_myplan_info(context, req.telegram_id)

                except Exception as e:
                    logger.error(f"Failed to notify user {req.telegram_id}: {e}")

                if query_or_msg:
                    await query_or_msg.edit_message_text(
                        f"✅ *APPROVED #{req_id}*\n\n"
                        f"User `{req.telegram_id}` now has premium.\n"
                        f"Plan: {plan.get('name', req.plan_key)}\n"
                        f"Amount: ₹{req.amount}\n"
                        f"UTR: `{req.utr}`",
                        parse_mode="Markdown",
                    )

                await notify_admin_action(
                    admin_id,
                    f"Payment Approved #{req_id}",
                    f"User: {req.telegram_id} | ₹{req.amount} | UTR: {req.utr}",
                )
            else:
                if query_or_msg:
                    await query_or_msg.edit_message_text(
                        "❌ Failed to activate premium. Check logs."
                    )

        elif action == "reject":
            req.status = "rejected"
            req.admin_id = admin_id
            req.processed_at = datetime.utcnow()
            session.commit()

            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=req.telegram_id,
                    text=(
                        "❌ *Payment Rejected*\n\n"
                        f"*Request:* `#{req_id}`\n"
                        f"*UTR:* `{req.utr}`\n\n"
                        "Possible reasons:\n"
                        "• UTR not found in our account\n"
                        "• Wrong amount paid\n"
                        "• Duplicate submission\n"
                        "• Invalid UTR\n\n"
                        "If you think this is a mistake, contact admin with proof of payment."
                    ),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to notify user {req.telegram_id}: {e}")

            if query_or_msg:
                await query_or_msg.edit_message_text(
                    f"❌ *REJECTED #{req_id}*\n\n"
                    f"User `{req.telegram_id}` notified.",
                    parse_mode="Markdown",
                )

            await notify_admin_action(
                admin_id,
                f"Payment Rejected #{req_id}",
                f"User: {req.telegram_id} | UTR: {req.utr}",
            )
    finally:
        session.close()


# ========== COMMAND HANDLERS ==========

async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /approve <user_id or request_id>."""
    user_id = update.effective_user.id
    if not is_bot_admin(user_id):
        await update.message.reply_text("🚫 *Admin only.*", parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/approve <request_id>` or `/approve <user_id>`\n\n"
            "Use /pending to see all pending requests.",
            parse_mode="Markdown",
        )
        return

    try:
        arg = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return

    # Try as request_id first, then as user_id
    session = get_session()
    try:
        req = session.query(PaymentRequest).get(arg)
        if not req:
            # Try as user_id — get latest pending
            req = (
                session.query(PaymentRequest)
                .filter_by(telegram_id=arg, status="pending")
                .order_by(PaymentRequest.created_at.desc())
                .first()
            )
        if not req:
            await update.message.reply_text("❌ No pending request found.")
            return

        req_id = req.id
    finally:
        session.close()

    await process_decision(context, update.message, req_id, "approve", user_id)


async def reject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /reject <user_id or request_id>."""
    user_id = update.effective_user.id
    if not is_bot_admin(user_id):
        await update.message.reply_text("🚫 *Admin only.*", parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/reject <request_id>` or `/reject <user_id>`",
            parse_mode="Markdown",
        )
        return

    try:
        arg = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return

    session = get_session()
    try:
        req = session.query(PaymentRequest).get(arg)
        if not req:
            req = (
                session.query(PaymentRequest)
                .filter_by(telegram_id=arg, status="pending")
                .order_by(PaymentRequest.created_at.desc())
                .first()
            )
        if not req:
            await update.message.reply_text("❌ No pending request found.")
            return

        req_id = req.id
    finally:
        session.close()

    await process_decision(context, update.message, req_id, "reject", user_id)


async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /pending — list all pending payments."""
    user_id = update.effective_user.id
    if not is_bot_admin(user_id):
        await update.message.reply_text("🚫 *Admin only.*", parse_mode="Markdown")
        return

    session = get_session()
    try:
        pending = (
            session.query(PaymentRequest)
            .filter_by(status="pending")
            .order_by(PaymentRequest.created_at.desc())
            .limit(20)
            .all()
        )

        if not pending:
            await update.message.reply_text("📭 *No pending payments.*", parse_mode="Markdown")
            return

        text = f"⏳ *Pending Payments ({len(pending)})*\n\n"
        for p in pending:
            plan = get_plan(p.plan_key) or {}
            age = datetime.utcnow() - p.created_at
            age_str = f"{int(age.total_seconds()/60)} min ago"
            text += (
                f"*#{p.id}* — @{p.username or p.telegram_id}\n"
                f"💰 ₹{p.amount} • {plan.get('name', p.plan_key)}\n"
                f"🔢 UTR: `{p.utr}`\n"
                f"⏰ {age_str}\n"
                f"✅ /approve {p.id}  ❌ /reject {p.id}\n\n"
            )

        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        session.close()


# ========== HELPER ==========

def count_pending(telegram_id):
    """Count user's pending payment requests."""
    session = get_session()
    try:
        return (
            session.query(PaymentRequest)
            .filter_by(telegram_id=telegram_id, status="pending")
            .count()
        )
    finally:
        session.close()
