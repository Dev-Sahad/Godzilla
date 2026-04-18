"""Manual UPI Payment Handler with UTR Verification."""
import os
import re
import json
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (
    UPI_ID, UPI_NAME, UPI_QR_FILENAME, MAX_PENDING_PER_USER, ADMIN_IDS,
)
from database.models import (
    get_session, User, PaymentRequest, UserState, SubscriptionPlan,
)
from database import get_or_create_user
from utils.payments import get_plans, get_plan, activate_premium
from utils import notify_admin_action

logger = logging.getLogger(__name__)
UTR_REGEX = re.compile(r"^\d{12}$")


def set_state(telegram_id, state, data=None):
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
    session = get_session()
    try:
        us = session.query(UserState).filter_by(telegram_id=telegram_id).first()
        if us:
            us.state = None
            us.state_data = None
            session.commit()
    finally:
        session.close()


def is_upi_configured():
    return bool(UPI_ID)


def count_pending(telegram_id):
    session = get_session()
    try:
        return session.query(PaymentRequest).filter_by(
            telegram_id=telegram_id, status="pending"
        ).count()
    finally:
        session.close()


async def subscribe_upi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_upi_configured():
        await update.message.reply_text(
            "⚠️ *Payments not configured yet.*\n\nContact the admin.",
            parse_mode="Markdown",
        )
        return

    get_or_create_user(user.id, user.username, user.first_name)
    plans = get_plans()
    if not plans:
        await update.message.reply_text("⚠️ *No plans available.*", parse_mode="Markdown")
        return

    pending = count_pending(user.id)
    if pending >= MAX_PENDING_PER_USER:
        await update.message.reply_text(
            f"⚠️ *You have {pending} pending payments.* Wait for approval.",
            parse_mode="Markdown",
        )
        return

    keyboard = []
    text = "💎 *GODZILLA Premium Plans*\n\n"
    for key, plan in plans.items():
        text += (
            f"*{plan['name']}*\n"
            f"💰 ₹{plan['amount']} • {plan['duration_days']} days\n"
            f"📥 {plan['daily_limit']} downloads/day\n"
            f"_{plan['description']}_\n\n"
        )
        keyboard.append([InlineKeyboardButton(
            f"Buy — ₹{plan['amount']}", callback_data=f"upi_{key}"
        )])

    text += (
        "✨ *Payment via UPI:*\n"
        "• PhonePe, GPay, Paytm, BHIM\n"
        "• 100% secure direct payment\n\n"
        "⚠️ After payment, send UTR to confirm."
    )
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="upi_cancel")])
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown",
    )


async def upi_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            "❌ *Payment cancelled.*\n\nTry again with /subscribe",
            parse_mode="Markdown",
        )
        return

    plan_key = action[4:]
    plan = get_plan(plan_key)
    if not plan:
        await query.edit_message_text("❌ Invalid plan.")
        return

    user_id = query.from_user.id
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
        "1️⃣ Copy UPI ID above\n"
        "2️⃣ Open GPay/PhonePe/Paytm\n"
        f"3️⃣ Paste UPI ID and send *exactly ₹{plan['amount']}*\n"
        "4️⃣ Copy the *12-digit UTR* from your UPI app\n"
        "5️⃣ Send the UTR here as a message\n\n"
        "⚠️ *Important:*\n"
        f"• Pay *exactly ₹{plan['amount']}* (wrong amount = rejection)\n"
        "• Approval takes 5-30 minutes"
    )

    keyboard = [[InlineKeyboardButton("❌ Cancel Payment", callback_data="upi_confirm_cancel")]]

    qr_path = os.path.join("web", "static", UPI_QR_FILENAME)
    if os.path.exists(qr_path):
        try:
            with open(qr_path, "rb") as qr:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=qr,
                    caption=text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            await query.delete_message()
            return
        except Exception as e:
            logger.error(f"QR send error: {e}")

    await query.edit_message_text(
        text + "\n\n_QR image not configured — use UPI ID above_",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def maybe_handle_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    state, data = get_state(user.id)
    if state != "awaiting_utr":
        return False

    text = update.message.text.strip() if update.message.text else ""
    utr = re.sub(r"[\s\-]", "", text)

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
        await update.message.reply_text("❌ Session expired. Use /subscribe again.")
        return True

    session = get_session()
    try:
        existing = session.query(PaymentRequest).filter_by(utr=utr).first()
        if existing:
            await update.message.reply_text(
                "⚠️ *This UTR is already submitted.*\n\n"
                "Each payment has a unique UTR. Check your UPI app.",
                parse_mode="Markdown",
            )
            return True

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

    plan = get_plan(plan_key) or {}
    await update.message.reply_text(
        "✅ *UTR received!*\n\n"
        f"*Plan:* {plan.get('name', plan_key)}\n"
        f"*Amount:* ₹{amount}\n"
        f"*UTR:* `{utr}`\n"
        f"*Request ID:* `#{req_id}`\n\n"
        "⏳ *Waiting for admin approval...*\n"
        "Usually takes 5-30 minutes.\n\n"
        "_Thank you! 🦖_",
        parse_mode="Markdown",
    )

    await notify_admins_new_payment(context, req_id, user, plan_key, amount, utr)
    return True


async def notify_admins_new_payment(context, req_id, user, plan_key, amount, utr):
    plan = get_plan(plan_key) or {}
    plan_name = plan.get("name", plan_key)

    text = (
        "💰 *NEW PAYMENT REQUEST*\n\n"
        f"*Request ID:* `#{req_id}`\n"
        f"*User:* {user.first_name}"
    )
    if user.username:
        text += f" (@{user.username})"
    text += (
        f"\n*Telegram ID:* `{user.id}`\n"
        f"*Plan:* {plan_name}\n"
        f"*Amount:* ₹{amount}\n"
        f"*UTR:* `{utr}`\n\n"
        "🔍 *Verify in your UPI app* then click below:"
    )

    keyboard = [[
        InlineKeyboardButton("✅ Approve", callback_data=f"pay_approve_{req_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"pay_reject_{req_id}"),
    ]]

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.error(f"Failed to notify admin {admin_id}: {e}")


async def approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    admin_id = query.from_user.id

    if admin_id not in ADMIN_IDS:
        await query.answer("🚫 Admin only!", show_alert=True)
        return
    await query.answer()

    data = query.data
    parts = data.split("_")
    if len(parts) != 3:
        return

    action = parts[1]
    try:
        req_id = int(parts[2])
    except ValueError:
        return

    await process_decision(context, query, req_id, action, admin_id)


async def process_decision(context, query_or_msg, req_id, action, admin_id):
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
                    f"⚠️ Already processed: *{req.status}*",
                    parse_mode="Markdown",
                )
            return

        if action == "approve":
            if activate_premium(req.telegram_id, req.plan_key):
                req.status = "approved"
                req.admin_id = admin_id
                req.processed_at = datetime.utcnow()
                session.commit()

                plan = get_plan(req.plan_key) or {}
                try:
                    await context.bot.send_message(
                        chat_id=req.telegram_id,
                        text=(
                            "🎉 *Payment Approved!*\n\n"
                            f"✨ *{plan.get('name', 'Premium')}* activated!\n"
                            f"📥 *Daily Limit:* {plan.get('daily_limit', 100)} downloads\n"
                            f"📅 *Duration:* {plan.get('duration_days', 30)} days\n\n"
                            "Use /myplan to check status.\n\n"
                            "_Thank you for supporting GODZILLA! 🦖_"
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.error(f"Notify error: {e}")

                if query_or_msg:
                    await query_or_msg.edit_message_text(
                        f"✅ *APPROVED #{req_id}*\n\n"
                        f"User: `{req.telegram_id}`\n"
                        f"Amount: ₹{req.amount}\n"
                        f"UTR: `{req.utr}`",
                        parse_mode="Markdown",
                    )

                await notify_admin_action(
                    admin_id, f"Payment Approved #{req_id}",
                    f"User: {req.telegram_id} | ₹{req.amount}",
                )
            else:
                if query_or_msg:
                    await query_or_msg.edit_message_text("❌ Failed to activate premium.")

        elif action == "reject":
            req.status = "rejected"
            req.admin_id = admin_id
            req.processed_at = datetime.utcnow()
            session.commit()

            try:
                await context.bot.send_message(
                    chat_id=req.telegram_id,
                    text=(
                        "❌ *Payment Rejected*\n\n"
                        f"*Request:* `#{req_id}`\n"
                        f"*UTR:* `{req.utr}`\n\n"
                        "Contact admin if this is a mistake."
                    ),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Notify error: {e}")

            if query_or_msg:
                await query_or_msg.edit_message_text(
                    f"❌ *REJECTED #{req_id}*", parse_mode="Markdown"
                )

            await notify_admin_action(
                admin_id, f"Payment Rejected #{req_id}",
                f"User: {req.telegram_id}",
            )
    finally:
        session.close()


async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🚫 *Admin only.*", parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/approve <request_id>` or `/approve <user_id>`",
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
            req = session.query(PaymentRequest).filter_by(
                telegram_id=arg, status="pending"
            ).order_by(PaymentRequest.created_at.desc()).first()
        if not req:
            await update.message.reply_text("❌ No pending request found.")
            return
        req_id = req.id
    finally:
        session.close()

    await process_decision(context, update.message, req_id, "approve", user_id)


async def reject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
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
            req = session.query(PaymentRequest).filter_by(
                telegram_id=arg, status="pending"
            ).order_by(PaymentRequest.created_at.desc()).first()
        if not req:
            await update.message.reply_text("❌ No pending request found.")
            return
        req_id = req.id
    finally:
        session.close()

    await process_decision(context, update.message, req_id, "reject", user_id)


async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🚫 *Admin only.*", parse_mode="Markdown")
        return

    session = get_session()
    try:
        pending = session.query(PaymentRequest).filter_by(
            status="pending"
        ).order_by(PaymentRequest.created_at.desc()).limit(20).all()

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
