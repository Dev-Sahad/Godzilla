"""Admin command handlers."""
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from config import ADMIN_IDS, WEB_PANEL_URL
from database import (
    get_stats, get_all_users, ban_user, unban_user,
    get_recent_logs, set_premium
)
from utils import notify_admin_action


def is_admin(user_id):
    """Check if user is admin."""
    return user_id in ADMIN_IDS


async def admin_only(update: Update):
    """Check admin permissions."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 *Admin only.*", parse_mode="Markdown")
        return False
    return True


async def admin_panel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show web admin panel link (admins only)."""
    if not await admin_only(update):
        return

    if not WEB_PANEL_URL:
        await update.message.reply_text(
            "⚠️ *Web panel URL not set.*\n\n"
            "Set `WEB_PANEL_URL` environment variable to your Railway domain.\n"
            "Example: `https://godzilla-bot-production.up.railway.app`",
            parse_mode="Markdown",
        )
        return

    url = WEB_PANEL_URL.rstrip("/") + "/login"
    keyboard = [[InlineKeyboardButton("🔐 Open Admin Panel", url=url)]]

    await update.message.reply_text(
        "🛠 *GODZILLA Admin Control Panel*\n\n"
        "Access the full web dashboard to manage:\n"
        "▫️ Subscription plans (edit prices live!)\n"
        "▫️ User accounts (ban, premium, search)\n"
        "▫️ Payments & revenue\n"
        "▫️ Broadcasts\n"
        "▫️ Activity logs\n"
        "▫️ Bot settings\n\n"
        "🔐 Login with your admin credentials.\n\n"
        "_🦖 Only admins can see this command._",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot stats (admin only)."""
    if not await admin_only(update):
        return

    stats = get_stats()

    text = (
        "📊 *GODZILLA — Admin Stats*\n\n"
        "*👥 USERS*\n"
        f"• Total: `{stats['total_users']}`\n"
        f"• Active (7d): `{stats['active_users_7d']}`\n"
        f"• Premium: `{stats['premium_users']}`\n"
        f"• Banned: `{stats['banned_users']}`\n\n"
        "*📥 DOWNLOADS*\n"
        f"• Total: `{stats['total_downloads']}`\n"
        f"• Today: `{stats['downloads_today']}`\n\n"
        "_Use /users for user list, /logs for activity_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all users."""
    if not await admin_only(update):
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: `/broadcast <message>`\n\n"
            "Example: `/broadcast 🦖 New feature: AI chat! Try /ai`",
            parse_mode="Markdown",
        )
        return

    message = " ".join(context.args)
    users = get_all_users()

    status_msg = await update.message.reply_text(
        f"📡 *Broadcasting to {len(users)} users...*", parse_mode="Markdown"
    )

    sent = 0
    failed = 0
    for i, user_id in enumerate(users):
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *Announcement*\n\n{message}\n\n_— GODZILLA Team_",
                parse_mode="Markdown",
            )
            sent += 1
        except TelegramError:
            failed += 1

        # Update status every 25 users
        if (i + 1) % 25 == 0:
            try:
                await status_msg.edit_text(
                    f"📡 *Broadcasting...*\n"
                    f"✅ Sent: `{sent}`\n"
                    f"❌ Failed: `{failed}`\n"
                    f"📊 Progress: `{i+1}/{len(users)}`",
                    parse_mode="Markdown",
                )
            except TelegramError:
                pass

        # Rate limit: 30 msgs/sec max
        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ *Broadcast Complete*\n\n"
        f"📤 Sent: `{sent}`\n"
        f"❌ Failed: `{failed}`\n"
        f"📊 Total: `{len(users)}`",
        parse_mode="Markdown",
    )

    await notify_admin_action(
        update.effective_user.id,
        "Broadcast Sent",
        f"Sent: {sent} | Failed: {failed}\nMsg: {message[:100]}",
    )


async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ban a user."""
    if not await admin_only(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: `/ban <user_id>`", parse_mode="Markdown")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    if target_id in ADMIN_IDS:
        await update.message.reply_text("🚫 Cannot ban an admin.")
        return

    if ban_user(target_id):
        await update.message.reply_text(f"🔨 *User `{target_id}` banned.*", parse_mode="Markdown")
        await notify_admin_action(
            update.effective_user.id, "User Banned", f"User ID: {target_id}"
        )
    else:
        await update.message.reply_text("❌ User not found.")


async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unban a user."""
    if not await admin_only(update):
        return

    if not context.args:
        await update.message.reply_text("Usage: `/unban <user_id>`", parse_mode="Markdown")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    if unban_user(target_id):
        await update.message.reply_text(f"♻️ *User `{target_id}` unbanned.*", parse_mode="Markdown")
        await notify_admin_action(
            update.effective_user.id, "User Unbanned", f"User ID: {target_id}"
        )
    else:
        await update.message.reply_text("❌ User not found.")


async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View recent logs."""
    if not await admin_only(update):
        return

    logs = get_recent_logs(limit=20)

    if not logs:
        await update.message.reply_text("📭 No logs yet.")
        return

    text = "📋 *Recent Activity (Last 20)*\n\n"
    for log in logs:
        emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌"}.get(log["level"], "•")
        time_str = log["created_at"].strftime("%m-%d %H:%M")
        msg = log["message"][:80]
        text += f"{emoji} `{time_str}` {log['action']}\n   {msg}\n\n"

    # Telegram has 4096 char limit
    if len(text) > 4000:
        text = text[:4000] + "\n\n_...truncated_"

    await update.message.reply_text(text, parse_mode="Markdown")


async def premium_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Grant premium to a user."""
    if not await admin_only(update):
        return

    if len(context.args) < 1:
        await update.message.reply_text(
            "Usage: `/premium <user_id> [on/off]`\nDefault: on", parse_mode="Markdown"
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    status = True
    if len(context.args) > 1 and context.args[1].lower() in ("off", "false", "0"):
        status = False

    if set_premium(target_id, status):
        action = "granted" if status else "revoked"
        await update.message.reply_text(
            f"⭐ *Premium {action} for `{target_id}`.*", parse_mode="Markdown"
        )
        await notify_admin_action(
            update.effective_user.id, f"Premium {action.capitalize()}", f"User: {target_id}"
        )
    else:
        await update.message.reply_text("❌ User not found.")


async def admin_help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin help menu."""
    if not await admin_only(update):
        return

    text = (
        "🛠 *GODZILLA — Admin Panel*\n\n"
        "*🌐 Web Control Panel*\n"
        "/admin\\_panel — Open full web dashboard\n\n"
        "*📊 Stats & Monitoring*\n"
        "/stats — Bot statistics\n"
        "/logs — Recent activity\n\n"
        "*📡 Broadcasting*\n"
        "/broadcast <msg> — Send to all users\n\n"
        "*👥 User Management*\n"
        "/ban <user\\_id> — Ban user\n"
        "/unban <user\\_id> — Unban user\n"
        "/premium <user\\_id> [on/off] — Grant/revoke premium\n\n"
        "_🔐 Admin access only_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
