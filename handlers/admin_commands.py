"""Admin command handlers."""
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from config import WEB_PANEL_URL
from database import (
    get_stats, get_all_users, ban_user, unban_user,
    get_recent_logs, set_premium
)
from database.helpers import (
    is_bot_admin, is_super_admin, add_sub_admin, remove_sub_admin,
    list_sub_admins, get_all_admin_ids,
)
from utils import notify_admin_action


def is_admin(user_id):
    """Check if user is admin (super or sub)."""
    return is_bot_admin(user_id)


async def admin_only(update: Update):
    """Check admin permissions."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 *Admin only.*", parse_mode="Markdown")
        return False
    return True


async def super_admin_only(update: Update):
    """Check super-admin permissions."""
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text(
            "🚫 *Super-admin only.*\n\nThis command requires super-admin rights.",
            parse_mode="Markdown",
        )
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

    if is_bot_admin(target_id):
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

    user_id = update.effective_user.id
    is_super = is_super_admin(user_id)

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
        "/premium <user\\_id> [on/off] — Grant/revoke premium\n"
        "/setlimit <user\\_id> <limit> — Change daily limit\n\n"
        "*💰 Payments*\n"
        "/pending — List pending payments\n"
        "/approve <id> — Approve payment\n"
        "/reject <id> — Reject payment\n"
    )

    if is_super:
        text += (
            "\n*👑 SUPER ADMIN — Team Management*\n"
            "/admins — List all admins\n"
            "/addadmin <user\\_id> — Promote user to sub-admin\n"
            "/deladmin <user\\_id> — Remove sub-admin\n"
            "\n_🔐 You are a SUPER admin_"
        )
    else:
        text += "\n_🔐 You are a sub-admin_"

    await update.message.reply_text(text, parse_mode="Markdown")


async def setlimit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /setlimit <user_id> <daily_limit>"""
    if not await admin_only(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/setlimit <user_id> <daily_limit>`\n\n"
            "Examples:\n"
            "`/setlimit 123456789 500` — set 500/day\n"
            "`/setlimit 123456789 reset` — remove custom limit (use plan default)",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(context.args[0])
        limit_arg = context.args[1].lower()
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    from database.models import get_session, User
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=target_id).first()
        if not user:
            await update.message.reply_text(f"❌ User `{target_id}` not found.", parse_mode="Markdown")
            return

        if limit_arg == "reset":
            user.custom_limit = None
            session.commit()
            await update.message.reply_text(
                f"✅ Custom limit *removed* for `{target_id}`.\n"
                f"Now uses plan default.",
                parse_mode="Markdown",
            )
        else:
            try:
                new_limit = int(limit_arg)
                if new_limit < 0 or new_limit > 10000:
                    raise ValueError
            except ValueError:
                await update.message.reply_text("❌ Limit must be a number 0-10000, or 'reset'.")
                return

            user.custom_limit = new_limit
            session.commit()
            await update.message.reply_text(
                f"✅ Daily limit set to *{new_limit}* for `{target_id}`.",
                parse_mode="Markdown",
            )

            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"📣 *Admin update:*\n\nYour daily download limit is now *{new_limit}* downloads/day.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

        await notify_admin_action(
            update.effective_user.id,
            "Daily Limit Changed",
            f"User: {target_id} | New limit: {limit_arg}",
        )
    finally:
        session.close()




# ===== SUB-ADMIN MANAGEMENT (Super-admin only) =====

async def addadmin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super admin: /addadmin <telegram_id> [username] — promote user to sub-admin."""
    from handlers.admin_mgmt import add_subadmin, set_menu_for_user

    user_id = update.effective_user.id
    if not await super_admin_only(update):
        return

    if not context.args:
        await update.message.reply_text(
            "*Usage:* `/addadmin <telegram_id> [username]`\n\n"
            "*Example:* `/addadmin 123456789 sahad_admin`\n\n"
            "Sub-admins get:\n"
            "✓ All admin commands in Telegram\n"
            "✓ Admin command menu (scoped)\n"
            "✗ Cannot add/remove other admins\n"
            "✗ Cannot change super-admin settings",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid Telegram ID.")
        return

    username = context.args[1] if len(context.args) > 1 else None

    success, message = add_subadmin(target_id, username, added_by=user_id)

    if success:
        # Update their command menu to admin menu
        try:
            await set_menu_for_user(context.bot, target_id)
        except Exception as e:
            pass

        # Notify the new sub-admin
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    "🎉 *You've been promoted to ADMIN!*\n\n"
                    "You now have access to admin commands.\n"
                    "Restart the bot chat to see the new commands menu.\n\n"
                    "Use /admin to see the full admin panel."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass

        await update.message.reply_text(message, parse_mode="Markdown")
        await notify_admin_action(
            user_id, "Sub-admin Added", f"New admin: {target_id}"
        )
    else:
        await update.message.reply_text(f"❌ {message}", parse_mode="Markdown")


async def deladmin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Super admin: /deladmin <telegram_id> — remove sub-admin."""
    from handlers.admin_mgmt import remove_subadmin, set_menu_for_user

    user_id = update.effective_user.id
    if not await super_admin_only(update):
        return

    if not context.args:
        await update.message.reply_text(
            "*Usage:* `/deladmin <telegram_id>`\n\n"
            "Removes a sub-admin. Super-admins cannot be removed (set in `.env`).",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid Telegram ID.")
        return

    success, message = remove_subadmin(target_id, removed_by=user_id)

    if success:
        # Reset their command menu to user menu
        try:
            await set_menu_for_user(context.bot, target_id)
        except Exception:
            pass

        # Notify the user
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    "ℹ️ *Admin access removed*\n\n"
                    "Your admin privileges have been revoked."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass

        await update.message.reply_text(message, parse_mode="Markdown")
        await notify_admin_action(
            user_id, "Sub-admin Removed", f"Removed: {target_id}"
        )
    else:
        await update.message.reply_text(f"❌ {message}", parse_mode="Markdown")


async def admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all admins (super + sub). Admin-only."""
    from handlers.admin_mgmt import list_all_admins

    if not await admin_only(update):
        return

    admins = list_all_admins()
    text = "👑 *GODZILLA Admin Team*\n━━━━━━━━━━━━━━━\n\n"

    super_admins = [a for a in admins if a["type"] == "super"]
    sub_admins = [a for a in admins if a["type"] == "sub"]

    if super_admins:
        text += f"*👑 SUPER ADMINS ({len(super_admins)})*\n"
        text += "_(Set in .env ADMIN_IDS — immutable)_\n"
        for a in super_admins:
            text += f"• `{a['telegram_id']}`\n"
        text += "\n"

    if sub_admins:
        text += f"*⚡ SUB-ADMINS ({len(sub_admins)})*\n"
        for a in sub_admins:
            name = a["username"] or a["first_name"] or "—"
            text += f"• `{a['telegram_id']}` ({name})\n"
            if is_super_admin(update.effective_user.id):
                text += f"  _Remove:_ `/deladmin {a['telegram_id']}`\n"
        text += "\n"
    else:
        text += "_No sub-admins yet._\n\n"

    if is_super_admin(update.effective_user.id):
        text += "💡 Use `/addadmin <user_id>` to promote a new sub-admin."

    await update.message.reply_text(text, parse_mode="Markdown")
