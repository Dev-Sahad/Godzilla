"""
GODZILLA BOT v3.0.0 - ULTRA EDITION
Developer: @Sxhd_Sha
Community: SHA COMMUNITY

Main entry point — registers all handlers and starts the bot.
"""
import os
import time
import asyncio
import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

from config import BOT_TOKEN, BOT_NAME, BOT_VERSION, BOT_OWNER
from database import init_db, add_log

from handlers.user_commands import (
    start_cmd, help_cmd, info_cmd, about_cmd, ping_cmd,
    history_cmd, favorites_cmd, fav_cmd, unfav_cmd,
    referral_cmd, limit_cmd
)
from handlers.admin_commands import (
    stats_cmd, broadcast_cmd, ban_cmd, unban_cmd,
    logs_cmd, premium_cmd, admin_help_cmd, admin_panel_cmd, setlimit_cmd
)
from handlers.download_handler import (
    handle_url, download_callback, quality_cmd,
    quality_pref_callback, thumb_cmd
)
from handlers.utility_commands import qr_cmd, short_cmd, translate_cmd
from handlers.subscription_commands import (
    myplan_cmd, cancel_cmd
)
from handlers.manual_payment import (
    subscribe_upi_cmd, upi_callback, maybe_handle_utr, approval_callback,
    approve_cmd, reject_cmd, pending_cmd,
)
from handlers.profile import (
    profile_cmd, setbio_cmd, setname_cmd, setemoji_cmd, profile_callback,
    badges_cmd,
)
from admin_panel import start_server_in_thread, set_bot_app
from config import WEB_PANEL_URL, ADMIN_IDS


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(app: Application):
    """Set up bot after initialization."""
    # Register command menu in Telegram (user-facing only — no admin)
    commands = [
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
    await app.bot.set_my_commands(commands)
    logger.info(f"✅ Command menu registered with Telegram ({len(commands)} commands)")

    # Store start time in bot_data for uptime tracking
    app.bot_data["start_time"] = time.time()
    # Store event loop for Flask broadcast to use
    app.bot_data["event_loop"] = asyncio.get_event_loop()


async def error_handler(update, context):
    """Global error handler."""
    logger.error(f"Exception: {context.error}", exc_info=context.error)
    add_log("ERROR", "exception", None, str(context.error))


async def activity_tracker(update, context):
    """Track all user activity to Discord webhook (type=1 handler — always runs)."""
    try:
        from utils import notify_command, notify_message
        if not update or not update.effective_user:
            return
        user = update.effective_user

        if update.message:
            text = update.message.text or ""
            if text.startswith("/"):
                parts = text.split(maxsplit=1)
                cmd = parts[0][1:].split("@")[0]  # remove / and @botname
                args = parts[1] if len(parts) > 1 else ""
                await notify_command(user.id, user.username, user.first_name, cmd, args)
            elif text:
                await notify_message(user.id, user.username, user.first_name, text, "text")
            elif update.message.photo:
                await notify_message(user.id, user.username, user.first_name, "[Photo]", "photo")
            elif update.message.document:
                await notify_message(user.id, user.username, user.first_name, "[Document]", "document")
    except Exception as e:
        logger.debug(f"activity_tracker error: {e}")


async def text_router(update, context):
    """
    Route incoming text messages:
    1. Check if user is awaiting UTR → handle payment verification
    2. Otherwise → pass to URL handler
    """
    # First check: is this a UTR response?
    if await maybe_handle_utr(update, context):
        return
    # Otherwise treat as URL
    await handle_url(update, context)


def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not set! Check your .env file.")
        return

    # Initialize database
    try:
        init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database init failed: {e}")
        return

    # Build application
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # ===== ACTIVITY TRACKER (group -1 — runs first, doesn't block other handlers) =====
    app.add_handler(MessageHandler(filters.ALL, activity_tracker), group=-1)

    # ===== USER COMMANDS =====
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("info", info_cmd))
    app.add_handler(CommandHandler("about", about_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("favorites", favorites_cmd))
    app.add_handler(CommandHandler("fav", fav_cmd))
    app.add_handler(CommandHandler("unfav", unfav_cmd))
    app.add_handler(CommandHandler("referral", referral_cmd))
    app.add_handler(CommandHandler("limit", limit_cmd))

    # ===== PROFILE COMMANDS (NEW v3.3) =====
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("setbio", setbio_cmd))
    app.add_handler(CommandHandler("setname", setname_cmd))
    app.add_handler(CommandHandler("setemoji", setemoji_cmd))
    app.add_handler(CommandHandler("badges", badges_cmd))

    # ===== DOWNLOAD COMMANDS =====
    app.add_handler(CommandHandler("quality", quality_cmd))
    app.add_handler(CommandHandler("thumb", thumb_cmd))

    # ===== ADMIN COMMANDS =====
    app.add_handler(CommandHandler("admin", admin_help_cmd))
    app.add_handler(CommandHandler("admin_panel", admin_panel_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(CommandHandler("premium", premium_cmd))
    app.add_handler(CommandHandler("setlimit", setlimit_cmd))

    # ===== UTILITY COMMANDS =====
    app.add_handler(CommandHandler("qr", qr_cmd))
    app.add_handler(CommandHandler("short", short_cmd))
    app.add_handler(CommandHandler("tr", translate_cmd))

    # ===== SUBSCRIPTION COMMANDS (UPI Manual) =====
    app.add_handler(CommandHandler("subscribe", subscribe_upi_cmd))
    app.add_handler(CommandHandler("plans", subscribe_upi_cmd))
    app.add_handler(CommandHandler("myplan", myplan_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))

    # ===== ADMIN PAYMENT APPROVAL =====
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CommandHandler("approve", approve_cmd))
    app.add_handler(CommandHandler("reject", reject_cmd))

    # ===== CALLBACK HANDLERS =====
    app.add_handler(CallbackQueryHandler(download_callback, pattern="^dl_|^q_"))
    app.add_handler(CallbackQueryHandler(quality_pref_callback, pattern="^pref_"))
    app.add_handler(CallbackQueryHandler(upi_callback, pattern="^upi_"))
    app.add_handler(CallbackQueryHandler(approval_callback, pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(profile_callback, pattern="^profile_"))

    # ===== TEXT HANDLER (always last — routes UTR vs URL) =====
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    # Error handler
    app.add_error_handler(error_handler)

    # Start webhook + admin panel server in background
    set_bot_app(app)
    start_server_in_thread()
    logger.info("🌐 Admin panel + Razorpay webhook server started")

    logger.info(f"🦖 {BOT_NAME} v{BOT_VERSION} is online! Developer: {BOT_OWNER}")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
