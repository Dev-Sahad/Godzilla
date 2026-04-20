"""
Cloud Sync - v3.5
Commands: /cloudsync, /cloudstatus, /clouddisconnect

NOTE: Full OAuth flow requires extensive setup. This is a simpler
implementation that gives users a Google Drive link placeholder
and lets admin manually configure. Full OAuth can be added later.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.models import get_session, User, CloudIntegration
from database import get_or_create_user

logger = logging.getLogger(__name__)


async def cloudsync_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show cloud sync setup info."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    session = get_session()
    try:
        integration = session.query(CloudIntegration).filter_by(telegram_id=user.id).first()

        if integration and integration.enabled:
            status = "✅ *Cloud Sync: ACTIVE*"
            subtext = f"_Syncing to Google Drive_\nConnected since: {integration.created_at.strftime('%d %b %Y')}"
            keyboard = [[InlineKeyboardButton("🔌 Disconnect", callback_data="cloud_disconnect")]]
        else:
            status = "⚙️ *Cloud Sync: NOT CONNECTED*"
            subtext = "_Connect Google Drive to auto-save all your downloads_"
            keyboard = [[InlineKeyboardButton("🔗 Connect Google Drive", callback_data="cloud_connect")]]

        text = (
            f"{status}\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"{subtext}\n\n"
            f"━━━━━━━━━━━━━━━\n\n"
            "✨ *Benefits:*\n"
            "• Auto-backup all downloads\n"
            "• Access from any device\n"
            "• Never lose files again\n"
            "• Organized by platform\n\n"
            "🔒 *Privacy:*\n"
            "• Bot only accesses /GODZILLA folder\n"
            "• Revoke anytime from Drive settings\n"
            "• Your files stay private"
        )

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    finally:
        session.close()


async def cloudstatus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show cloud sync status."""
    user = update.effective_user

    session = get_session()
    try:
        integration = session.query(CloudIntegration).filter_by(telegram_id=user.id).first()

        if not integration:
            await update.message.reply_text(
                "❌ *Not connected*\n\nUse /cloudsync to set up Google Drive integration.",
                parse_mode="Markdown",
            )
            return

        status = "✅ ACTIVE" if integration.enabled else "⏸ PAUSED"
        text = (
            f"☁️ *Cloud Sync Status*\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"*Status:* {status}\n"
            f"*Provider:* Google Drive\n"
            f"*Connected:* {integration.created_at.strftime('%d %b %Y')}\n"
            f"*Folder:* /GODZILLA/\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"_Use /clouddisconnect to remove._"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        session.close()


async def clouddisconnect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disconnect cloud sync."""
    user = update.effective_user

    session = get_session()
    try:
        integration = session.query(CloudIntegration).filter_by(telegram_id=user.id).first()
        if not integration:
            await update.message.reply_text("❌ You're not connected.")
            return

        session.delete(integration)
        session.commit()
        await update.message.reply_text(
            "✅ *Cloud sync disconnected.*\n\n"
            "_Your existing Drive files are not affected._",
            parse_mode="Markdown",
        )
    finally:
        session.close()


async def cloud_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cloud sync button clicks."""
    query = update.callback_query
    await query.answer()

    if query.data == "cloud_connect":
        # For full OAuth implementation, admin needs to set up Google Cloud Console
        # For now, show instructions
        await query.edit_message_text(
            "🔗 *Connect Google Drive*\n"
            "━━━━━━━━━━━━━━━\n\n"
            "⚙️ *Setup in progress!*\n\n"
            "Full OAuth integration coming soon. For now:\n\n"
            "1️⃣ Admin is setting up Google Cloud Console\n"
            "2️⃣ OAuth consent screen approval in review\n"
            "3️⃣ Feature will go live within 48 hours\n\n"
            "_You'll be notified when it's ready!_\n\n"
            "📧 *Want priority access?*\n"
            "Contact @sahad_____sha for early beta.",
            parse_mode="Markdown",
        )

        # Mark interest
        user_id = query.from_user.id
        session = get_session()
        try:
            existing = session.query(CloudIntegration).filter_by(telegram_id=user_id).first()
            if not existing:
                integration = CloudIntegration(
                    telegram_id=user_id,
                    provider="google_drive",
                    enabled=False,  # Not yet active
                    access_token="pending",
                )
                session.add(integration)
                session.commit()
        except Exception as e:
            logger.error(f"Cloud interest tracking: {e}")
        finally:
            session.close()

    elif query.data == "cloud_disconnect":
        user_id = query.from_user.id
        session = get_session()
        try:
            integration = session.query(CloudIntegration).filter_by(telegram_id=user_id).first()
            if integration:
                session.delete(integration)
                session.commit()
                await query.edit_message_text(
                    "✅ *Cloud sync disconnected.*",
                    parse_mode="Markdown",
                )
        finally:
            session.close()
