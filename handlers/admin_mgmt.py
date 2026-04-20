"""
Admin Management Helper Module.
Handles sub-admin CRUD and per-user command menu scoping.
"""
import logging
from telegram import BotCommand, BotCommandScopeChat

from config import SUPER_ADMIN_IDS
from database.helpers import (
    is_bot_admin, is_super_admin, add_sub_admin, remove_sub_admin,
    list_sub_admins, get_all_admin_ids,
)

logger = logging.getLogger(__name__)


# ========== USER COMMAND MENU (regular users) ==========

USER_COMMANDS = [
    BotCommand("start", "🦖 Start the bot"),
    BotCommand("help", "📖 Show help menu"),
    BotCommand("info", "🪪 Bot info & stats"),
    BotCommand("about", "👨‍💻 About GODZILLA"),
    BotCommand("ping", "⚡ Check bot speed"),
    BotCommand("profile", "👤 View your profile"),
    BotCommand("setbio", "📝 Set your bio"),
    BotCommand("setname", "✏️ Set display name"),
    BotCommand("setemoji", "😀 Change avatar emoji"),
    BotCommand("badges", "🏆 View all badges"),
    BotCommand("history", "📚 Your download history"),
    BotCommand("favorites", "⭐ Saved favorite links"),
    BotCommand("fav", "⭐ Add link to favorites"),
    BotCommand("unfav", "❌ Remove from favorites"),
    BotCommand("quality", "🎬 Set default video quality"),
    BotCommand("thumb", "🖼️ Get video thumbnail"),
    BotCommand("subscribe", "💎 Get Premium plans"),
    BotCommand("plans", "💰 View subscription plans"),
    BotCommand("myplan", "📋 Check your plan status"),
    BotCommand("cancel", "🚫 Cancel subscription"),
    BotCommand("referral", "🎁 Referral program"),
    BotCommand("limit", "📊 Check daily usage"),
    BotCommand("qr", "🔲 Generate QR code"),
    BotCommand("short", "🔗 Shorten a URL"),
    BotCommand("tr", "🌐 Translate text"),
]


# ========== ADMIN COMMAND MENU (admins see everything) ==========

ADMIN_COMMANDS = USER_COMMANDS + [
    # Admin separator (visual)
    BotCommand("admin", "👑 Admin menu"),
    BotCommand("admin_panel", "🌐 Open web panel"),
    BotCommand("stats", "📊 Bot statistics"),
    BotCommand("logs", "📋 Recent activity logs"),
    BotCommand("broadcast", "📢 Broadcast to all users"),
    BotCommand("ban", "🔨 Ban a user"),
    BotCommand("unban", "✅ Unban a user"),
    BotCommand("premium", "⭐ Grant/revoke premium"),
    BotCommand("setlimit", "🎯 Set user's daily limit"),
    BotCommand("pending", "⏳ Pending payments"),
    BotCommand("approve", "✅ Approve payment"),
    BotCommand("reject", "❌ Reject payment"),
]


# ========== SUPER-ADMIN COMMANDS (includes admin mgmt) ==========

SUPER_ADMIN_COMMANDS = ADMIN_COMMANDS + [
    BotCommand("addadmin", "➕ Promote user to sub-admin"),
    BotCommand("deladmin", "➖ Remove sub-admin"),
    BotCommand("admins", "📋 List all admins"),
]


# ========== HELPER FUNCTIONS ==========

def is_superadmin(telegram_id):
    """Alias for is_super_admin."""
    return is_super_admin(telegram_id)


def add_subadmin(telegram_id, username, added_by):
    """Add a sub-admin. Returns (success, message) tuple."""
    if not is_super_admin(added_by):
        return False, "Only super-admins can promote others."

    success, msg = add_sub_admin(
        telegram_id=telegram_id,
        username=username,
        first_name=None,
        promoted_by=added_by,
        notes="",
    )
    if success:
        return True, f"✅ *User `{telegram_id}` is now a sub-admin!*"
    return False, msg


def remove_subadmin(telegram_id, removed_by):
    """Remove a sub-admin. Returns (success, message) tuple."""
    if not is_super_admin(removed_by):
        return False, "Only super-admins can remove sub-admins."

    if is_super_admin(telegram_id):
        return False, "Cannot remove a super-admin (set in .env ADMIN_IDS)."

    success, msg = remove_sub_admin(telegram_id)
    if success:
        return True, f"✅ *Sub-admin `{telegram_id}` removed.*"
    return False, msg


def list_all_admins():
    """Returns list of dicts with admin info: [{'telegram_id', 'username', 'type'}]."""
    result = []

    # Super admins
    for sid in SUPER_ADMIN_IDS:
        result.append({
            "telegram_id": sid,
            "username": None,
            "first_name": None,
            "type": "super",
        })

    # Sub admins
    try:
        for sa in list_sub_admins():
            result.append({
                "telegram_id": sa.telegram_id,
                "username": sa.username,
                "first_name": sa.first_name,
                "type": "sub",
            })
    except Exception as e:
        logger.error(f"list_sub_admins error: {e}")

    return result


async def set_menu_for_user(bot, telegram_id):
    """Set appropriate command menu for a specific user based on their role."""
    try:
        scope = BotCommandScopeChat(chat_id=telegram_id)

        if is_super_admin(telegram_id):
            await bot.set_my_commands(SUPER_ADMIN_COMMANDS, scope=scope)
            logger.info(f"Set super-admin menu for {telegram_id}")
        elif is_bot_admin(telegram_id):
            await bot.set_my_commands(ADMIN_COMMANDS, scope=scope)
            logger.info(f"Set admin menu for {telegram_id}")
        else:
            # Remove chat-specific commands (falls back to default user menu)
            await bot.delete_my_commands(scope=scope)
            logger.info(f"Cleared admin menu for {telegram_id}")
    except Exception as e:
        logger.error(f"Failed to set menu for {telegram_id}: {e}")


async def refresh_all_admin_menus(bot):
    """Refresh command menus for all admins (called on bot start)."""
    all_admin_ids = get_all_admin_ids()
    success_count = 0

    for tid in all_admin_ids:
        try:
            await set_menu_for_user(bot, tid)
            success_count += 1
        except Exception as e:
            logger.error(f"Menu refresh failed for {tid}: {e}")

    logger.info(f"✅ Refreshed menus for {success_count}/{len(all_admin_ids)} admins")
    return success_count
