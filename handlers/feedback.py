"""
Feedback / Bug Report / Suggestion Handler — v3.6
Commands: /feedback, /bug, /suggest, /myreports

Flow:
1. User types /feedback → chooses type (bug/suggestion/praise)
2. Bot asks for subject
3. Bot asks for detailed message
4. Report saved → admin notified via Telegram + Discord
5. Admin can reply via web panel
6. User gets notification when admin replies
"""
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.models import get_session, User, Feedback, UserState
from database import get_or_create_user
from database.helpers import get_all_admin_ids

logger = logging.getLogger(__name__)


# ========== STATE HELPERS ==========

def set_feedback_state(telegram_id, state, data=None):
    """Set user's feedback conversation state."""
    import json
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


def get_feedback_state(telegram_id):
    """Get user's feedback state."""
    import json
    session = get_session()
    try:
        us = session.query(UserState).filter_by(telegram_id=telegram_id).first()
        if not us or not us.state:
            return None, {}
        data = json.loads(us.state_data) if us.state_data else {}
        return us.state, data
    finally:
        session.close()


def clear_feedback_state(telegram_id):
    """Clear state."""
    session = get_session()
    try:
        us = session.query(UserState).filter_by(telegram_id=telegram_id).first()
        if us and us.state and us.state.startswith("fb_"):
            us.state = None
            us.state_data = None
            session.commit()
    finally:
        session.close()


# ========== COMMANDS ==========

async def feedback_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main feedback menu — shows type picker."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    keyboard = [
        [
            InlineKeyboardButton("🐛 Report a Bug", callback_data="fb_type_bug"),
            InlineKeyboardButton("💡 Suggest Feature", callback_data="fb_type_suggestion"),
        ],
        [
            InlineKeyboardButton("❤️ Praise / Thanks", callback_data="fb_type_praise"),
            InlineKeyboardButton("💬 Other", callback_data="fb_type_other"),
        ],
        [
            InlineKeyboardButton("📋 My Reports", callback_data="fb_my_reports"),
            InlineKeyboardButton("❌ Cancel", callback_data="fb_cancel"),
        ],
    ]

    text = (
        "📬 *Feedback Center*\n"
        "━━━━━━━━━━━━━━━\n\n"
        "Your voice matters! Help shape GODZILLA.\n\n"
        "*What would you like to share?*\n\n"
        "🐛 *Bug Report* — something broken?\n"
        "💡 *Feature Request* — new idea?\n"
        "❤️ *Praise* — what you love\n"
        "💬 *Other* — anything else\n\n"
        "_All reports reach @sahad_____sha directly._"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def bug_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shortcut for bug reports."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)
    await _start_feedback_flow(update.message, user.id, "bug")


async def suggest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shortcut for suggestions."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)
    await _start_feedback_flow(update.message, user.id, "suggestion")


async def _start_feedback_flow(msg_or_query, user_id, fb_type):
    """Start the feedback input flow."""
    set_feedback_state(user_id, "fb_subject", {"type": fb_type})

    type_labels = {
        "bug": ("🐛 BUG REPORT", "Describe the bug clearly. What went wrong?"),
        "suggestion": ("💡 FEATURE SUGGESTION", "What new feature would you like?"),
        "praise": ("❤️ PRAISE", "Share what you love!"),
        "other": ("💬 FEEDBACK", "What's on your mind?"),
    }
    label, hint = type_labels.get(fb_type, type_labels["other"])

    text = (
        f"*{label}*\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"*Step 1 of 2: Subject*\n\n"
        f"{hint}\n\n"
        "Type a *short subject* (max 100 chars):\n"
        "_Example: \"Instagram download fails\" or \"Add dark theme\"_\n\n"
        "Send /cancel to abort."
    )

    if hasattr(msg_or_query, "reply_text"):
        await msg_or_query.reply_text(text, parse_mode="Markdown")
    else:
        await msg_or_query.edit_message_text(text, parse_mode="Markdown")


async def maybe_handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check if user is in feedback flow. Returns True if handled."""
    user = update.effective_user
    state, data = get_feedback_state(user.id)

    if not state or not state.startswith("fb_"):
        return False

    text = update.message.text.strip() if update.message.text else ""

    if text == "/cancel":
        clear_feedback_state(user.id)
        await update.message.reply_text("❌ Feedback cancelled.", parse_mode="Markdown")
        return True

    # Step 1: Got subject, ask for message
    if state == "fb_subject":
        if len(text) < 3:
            await update.message.reply_text("⚠️ Too short. Give a meaningful subject (at least 3 chars).")
            return True
        if len(text) > 100:
            await update.message.reply_text("⚠️ Too long! Max 100 chars for subject.")
            return True

        data["subject"] = text
        set_feedback_state(user.id, "fb_message", data)

        await update.message.reply_text(
            "*Step 2 of 2: Details*\n\n"
            "Now send the *full details*:\n\n"
            "• For bugs: What you did, what happened, screenshots help\n"
            "• For suggestions: Why it would be useful\n"
            "• For other: Any context\n\n"
            "Max 2000 chars.\nSend /cancel to abort.",
            parse_mode="Markdown",
        )
        return True

    # Step 2: Got full message, save to database
    if state == "fb_message":
        if len(text) < 10:
            await update.message.reply_text("⚠️ Please give more details (at least 10 chars).")
            return True
        if len(text) > 2000:
            await update.message.reply_text("⚠️ Too long! Max 2000 chars. Please shorten your message.")
            return True

        subject = data.get("subject", "")
        fb_type = data.get("type", "other")

        # Save to database
        session = get_session()
        try:
            fb = Feedback(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                feedback_type=fb_type,
                subject=subject,
                message=text,
                status="new",
                priority="high" if fb_type == "bug" else "normal",
            )
            session.add(fb)
            session.commit()
            fb_id = fb.id
        finally:
            session.close()

        clear_feedback_state(user.id)

        type_emoji = {"bug": "🐛", "suggestion": "💡", "praise": "❤️", "other": "💬"}
        emoji = type_emoji.get(fb_type, "💬")

        # Confirm to user
        await update.message.reply_text(
            f"✅ *Feedback Submitted!*\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"{emoji} *Type:* {fb_type.upper()}\n"
            f"📌 *Subject:* {subject}\n"
            f"🎫 *Ticket ID:* `#FB-{fb_id}`\n\n"
            "━━━━━━━━━━━━━━━\n"
            "Your feedback is now with the dev team.\n"
            "You'll be notified if admin replies.\n\n"
            "_Thank you for helping improve GODZILLA! 🦖_",
            parse_mode="Markdown",
        )

        # Notify admins
        await _notify_admins_new_feedback(context, fb_id, user, fb_type, subject, text)
        return True

    return False


async def _notify_admins_new_feedback(context, fb_id, user, fb_type, subject, message):
    """Send notification to all admins."""
    type_emoji = {"bug": "🐛", "suggestion": "💡", "praise": "❤️", "other": "💬"}
    emoji = type_emoji.get(fb_type, "💬")

    preview = message[:300] + "..." if len(message) > 300 else message

    text = (
        f"{emoji} *NEW {fb_type.upper()} REPORT*\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"*Ticket:* `#FB-{fb_id}`\n"
        f"*From:* {user.first_name or 'User'}"
        + (f" (@{user.username})" if user.username else "")
        + f"\n*User ID:* `{user.id}`\n"
        f"*Subject:* {subject}\n\n"
        "━━━━━━━━━━━━━━━\n"
        f"*Message:*\n_{preview}_\n\n"
        "━━━━━━━━━━━━━━━\n"
        "💻 Reply via Admin Panel → Feedback"
    )

    keyboard = [[
        InlineKeyboardButton("✅ Mark Reviewing", callback_data=f"fb_status_{fb_id}_reviewing"),
        InlineKeyboardButton("✔️ Resolved", callback_data=f"fb_status_{fb_id}_resolved"),
    ]]

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

    # Discord webhook if configured
    try:
        from utils.discord_webhook import notify_admin_action
        await notify_admin_action(
            user.id, f"New {fb_type}", f"#{fb_id} · {subject}"
        )
    except Exception:
        pass


async def feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle feedback button callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id

    if data == "fb_cancel":
        clear_feedback_state(user_id)
        await query.edit_message_text("❌ Cancelled.")
        return

    if data == "fb_my_reports":
        await _show_my_reports(query, user_id)
        return

    if data.startswith("fb_type_"):
        fb_type = data.replace("fb_type_", "")
        await _start_feedback_flow(query, user_id, fb_type)
        return

    if data.startswith("fb_status_"):
        # Admin action: mark reviewing/resolved
        from database.helpers import is_bot_admin
        if not is_bot_admin(user_id):
            await query.answer("🚫 Admin only!", show_alert=True)
            return

        parts = data.split("_")
        if len(parts) < 4:
            return

        try:
            fb_id = int(parts[2])
            new_status = parts[3]
        except (ValueError, IndexError):
            return

        session = get_session()
        try:
            fb = session.query(Feedback).get(fb_id)
            if fb:
                fb.status = new_status
                fb.admin_id = user_id
                if new_status == "resolved":
                    fb.resolved_at = datetime.utcnow()
                session.commit()

                # Notify user
                try:
                    status_emoji = {"reviewing": "👀", "resolved": "✅", "rejected": "❌"}
                    emoji = status_emoji.get(new_status, "📋")
                    await context.bot.send_message(
                        chat_id=fb.telegram_id,
                        text=(
                            f"{emoji} *Feedback Status Update*\n\n"
                            f"Your ticket `#FB-{fb_id}` is now:\n"
                            f"*{new_status.upper()}*\n\n"
                            f"_Subject:_ {fb.subject}"
                        ),
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass

                await query.edit_message_text(
                    f"✅ Ticket `#FB-{fb_id}` marked as *{new_status.upper()}*.",
                    parse_mode="Markdown",
                )
        finally:
            session.close()


async def _show_my_reports(query, user_id):
    """Show user's submitted reports."""
    session = get_session()
    try:
        reports = (
            session.query(Feedback)
            .filter_by(telegram_id=user_id)
            .order_by(Feedback.created_at.desc())
            .limit(10)
            .all()
        )

        if not reports:
            await query.edit_message_text(
                "📭 *No reports yet*\n\nUse /feedback to submit your first report!",
                parse_mode="Markdown",
            )
            return

        text = "📋 *Your Reports*\n━━━━━━━━━━━━━━━\n\n"
        type_emoji = {"bug": "🐛", "suggestion": "💡", "praise": "❤️", "other": "💬"}
        status_emoji = {"new": "🆕", "reviewing": "👀", "resolved": "✅", "rejected": "❌"}

        for r in reports:
            te = type_emoji.get(r.feedback_type, "💬")
            se = status_emoji.get(r.status, "📋")
            text += (
                f"{te} *#FB-{r.id}* {se} _{r.status}_\n"
                f"_{r.subject}_\n"
                f"📅 {r.created_at.strftime('%d %b %Y')}\n\n"
            )

        text += "━━━━━━━━━━━━━━━\n_Showing last 10 reports_"

        await query.edit_message_text(text, parse_mode="Markdown")
    finally:
        session.close()


async def myreports_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's reports directly."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    session = get_session()
    try:
        reports = (
            session.query(Feedback)
            .filter_by(telegram_id=user.id)
            .order_by(Feedback.created_at.desc())
            .limit(10)
            .all()
        )

        if not reports:
            await update.message.reply_text(
                "📭 *No reports yet*\n\nUse /feedback to submit one!",
                parse_mode="Markdown",
            )
            return

        text = "📋 *Your Reports*\n━━━━━━━━━━━━━━━\n\n"
        type_emoji = {"bug": "🐛", "suggestion": "💡", "praise": "❤️", "other": "💬"}
        status_emoji = {"new": "🆕", "reviewing": "👀", "resolved": "✅", "rejected": "❌"}

        for r in reports:
            te = type_emoji.get(r.feedback_type, "💬")
            se = status_emoji.get(r.status, "📋")
            text += (
                f"{te} *#FB-{r.id}* {se} _{r.status}_\n"
                f"_{r.subject}_\n"
                f"📅 {r.created_at.strftime('%d %b %Y')}\n\n"
            )

        text += "━━━━━━━━━━━━━━━\n_Last 10 reports_"
        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        session.close()
