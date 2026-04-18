"""Subscription command handlers."""
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import REFERRAL_GOAL_FREE_PREMIUM, REFERRAL_BONUS
from database.models import get_session, User
from utils.payments import (
    create_payment_order, is_configured, activate_premium, get_plans, get_plan
)
from utils import notify_admin_action

logger = logging.getLogger(__name__)


async def subscribe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show subscription plans and start payment."""
    user = update.effective_user

    if not is_configured():
        await update.message.reply_text(
            "⚠️ *Payments not configured yet.*\n\n"
            "Please contact the admin to enable premium subscriptions.",
            parse_mode="Markdown",
        )
        return

    plans = get_plans()
    if not plans:
        await update.message.reply_text(
            "⚠️ *No subscription plans available right now.*\n\n"
            "Check back later!",
            parse_mode="Markdown",
        )
        return

    # Build plan buttons
    keyboard = []
    plan_text = "💎 *GODZILLA Premium Plans*\n\n"

    for key, plan in plans.items():
        plan_text += (
            f"*{plan['name']}*\n"
            f"💰 ₹{plan['amount']} • {plan['duration_days']} days\n"
            f"📥 {plan['daily_limit']} downloads/day\n"
            f"_{plan['description']}_\n\n"
        )
        keyboard.append([
            InlineKeyboardButton(
                f"Buy {plan['name']} — ₹{plan['amount']}",
                callback_data=f"sub_{key}",
            )
        ])

    plan_text += (
        "✨ *Premium Benefits:*\n"
        "• No daily download limits\n"
        "• Priority queue (faster)\n"
        "• HD quality by default\n"
        "• Support development 🦖\n\n"
        "💳 *Payment:* UPI, Cards, Netbanking (via Razorpay)\n"
        "🔒 *Secure:* End-to-end encrypted"
    )

    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="sub_cancel")])

    await update.message.reply_text(
        plan_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def subscribe_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle subscription plan button clicks."""
    query = update.callback_query
    await query.answer()

    action = query.data  # e.g. "sub_monthly" or "sub_cancel"

    if action == "sub_cancel":
        await query.edit_message_text("❌ Subscription cancelled.")
        return

    plan_key = action[4:]  # Remove "sub_" prefix
    plan = get_plan(plan_key)

    if not plan:
        await query.edit_message_text("❌ Invalid plan.")
        return

    user_id = query.from_user.id

    await query.edit_message_text("⏳ Creating payment link...")

    # Create Razorpay order + payment link
    order = create_payment_order(user_id, plan_key)

    if not order or not order.get("payment_link"):
        await query.edit_message_text(
            "❌ *Failed to create payment.*\n\n"
            "Please try again or contact admin.",
            parse_mode="Markdown",
        )
        return

    text = (
        f"💳 *Complete Your Payment*\n\n"
        f"*Plan:* {plan['name']}\n"
        f"*Amount:* ₹{order['amount']}\n"
        f"*Duration:* {plan['duration_days']} days\n\n"
        f"👇 *Click below to pay:*\n\n"
        f"🔒 Secure payment via Razorpay\n"
        f"Supports: UPI, Cards, Netbanking\n\n"
        f"⏱ Link expires in *1 hour*\n"
        f"📧 After payment, premium activates automatically."
    )

    keyboard = [
        [InlineKeyboardButton("💳 Pay Now", url=order["payment_link"])],
        [InlineKeyboardButton("❓ Need Help?", callback_data="sub_help")],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def myplan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's current subscription status."""
    user_id = update.effective_user.id

    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=user_id).first()

        if not user:
            await update.message.reply_text("❌ User not found. Send /start first.")
            return

        if not user.is_premium or not user.subscription_expires_at:
            text = (
                "📋 *Your Current Plan*\n\n"
                "🆓 *Tier:* Free\n"
                "📥 *Daily Limit:* 3 downloads\n"
                f"🎁 *Referral Bonus:* +{user.referral_count * REFERRAL_BONUS}/day\n\n"
                "💎 *Upgrade to Premium:*\n"
                "Use /subscribe for unlimited downloads!\n\n"
                "🎁 Or invite friends with /referral\n"
                f"Invite {REFERRAL_GOAL_FREE_PREMIUM} friends = 7 days free premium!"
            )
        else:
            now = datetime.utcnow()
            remaining = user.subscription_expires_at - now

            if remaining.total_seconds() <= 0:
                text = (
                    "📋 *Your Current Plan*\n\n"
                    "⚠️ *Your premium has expired.*\n\n"
                    "Renew now with /subscribe"
                )
            else:
                days = remaining.days
                hours = remaining.seconds // 3600
                expiry_str = user.subscription_expires_at.strftime("%B %d, %Y")
                plan = get_plan(user.subscription_plan) or {}

                text = (
                    "💎 *Your Current Plan*\n\n"
                    f"✨ *Tier:* Premium\n"
                    f"📦 *Plan:* {plan.get('name', user.subscription_plan)}\n"
                    f"📥 *Daily Limit:* {plan.get('daily_limit', 100)} downloads\n"
                    f"📅 *Expires:* {expiry_str}\n"
                    f"⏳ *Time left:* {days} days, {hours} hours\n"
                    f"🔁 *Auto-renew:* {'ON ✅' if user.auto_renew else 'OFF ❌'}\n\n"
                    f"_Thank you for supporting GODZILLA! 🦖_"
                )

        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        session.close()


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel auto-renewal (premium stays active until expiry)."""
    user_id = update.effective_user.id

    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=user_id).first()

        if not user or not user.is_premium:
            await update.message.reply_text(
                "ℹ️ *You don't have an active subscription.*",
                parse_mode="Markdown",
            )
            return

        if not user.auto_renew:
            await update.message.reply_text(
                "ℹ️ *Auto-renew is already off.*\n\n"
                "Your premium stays active until it expires. No action needed.",
                parse_mode="Markdown",
            )
            return

        user.auto_renew = False
        session.commit()

        expiry_str = user.subscription_expires_at.strftime("%B %d, %Y")
        await update.message.reply_text(
            "✅ *Auto-renew cancelled.*\n\n"
            f"Your premium remains active until *{expiry_str}*.\n"
            f"After that, you'll return to the free tier.\n\n"
            "_Changed your mind? Use /subscribe to reactivate anytime._",
            parse_mode="Markdown",
        )
    finally:
        session.close()


async def plans_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all available plans (same as /subscribe)."""
    await subscribe_cmd(update, context)


async def check_referral_reward(user_id):
    """
    Check if user hit the referral goal and should get free premium.
    Called after each successful referral.
    """
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if not user or user.referral_reward_claimed:
            return False, 0

        if user.referral_count >= REFERRAL_GOAL_FREE_PREMIUM:
            # Grant 7 days free premium
            now = datetime.utcnow()
            base = user.subscription_expires_at if (
                user.subscription_expires_at and user.subscription_expires_at > now
            ) else now

            user.is_premium = True
            user.subscription_plan = "referral_reward"
            user.subscription_expires_at = base + timedelta(days=7)
            user.referral_reward_claimed = True
            session.commit()
            return True, 7
        return False, 0
    finally:
        session.close()


# ===== SUCCESS HANDLER (called from webhook) =====

async def send_success_message(bot, telegram_id, plan_key):
    """Send confirmation after successful payment."""
    plan = get_plan(plan_key) or {}

    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "🎉 *Payment Successful!*\n\n"
                f"✨ *{plan.get('name', 'Premium')}* activated!\n"
                f"📥 *Daily Limit:* {plan.get('daily_limit', 100)} downloads\n"
                f"📅 *Duration:* {plan.get('duration_days', 30)} days\n\n"
                "Use /myplan to check your plan anytime.\n\n"
                "_Thank you for supporting GODZILLA! 🦖_"
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Success message error: {e}")
