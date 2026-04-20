"""
Friends System - v3.5
Commands: /addfriend, /friends, /acceptfriend, /declinefriend, /unfriend
"""
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.models import get_session, User, Friendship
from database import get_or_create_user

logger = logging.getLogger(__name__)


async def addfriend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a friend request. Usage: /addfriend <telegram_id or @username>"""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    if not context.args:
        await update.message.reply_text(
            "*Usage:* `/addfriend <telegram_id>`\n\n"
            "*Example:* `/addfriend 123456789`\n\n"
            "_Get friend's ID from their /profile page._",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Use their numeric Telegram ID.")
        return

    if target_id == user.id:
        await update.message.reply_text("😅 You can't add yourself as a friend!")
        return

    session = get_session()
    try:
        # Check if target user exists
        target = session.query(User).filter_by(telegram_id=target_id).first()
        if not target:
            await update.message.reply_text(
                "❌ User not found. They need to use the bot at least once first."
            )
            return

        # Check existing friendship
        existing = session.query(Friendship).filter(
            ((Friendship.user_id == user.id) & (Friendship.friend_id == target_id)) |
            ((Friendship.user_id == target_id) & (Friendship.friend_id == user.id))
        ).first()

        if existing:
            if existing.status == "accepted":
                await update.message.reply_text("✅ You're already friends!")
            elif existing.status == "pending":
                await update.message.reply_text("⏳ Friend request already pending.")
            elif existing.status == "blocked":
                await update.message.reply_text("🚫 Cannot add this user.")
            return

        # Create friendship
        fs = Friendship(user_id=user.id, friend_id=target_id, status="pending")
        session.add(fs)
        session.commit()
        req_id = fs.id

        # Notify target
        try:
            keyboard = [[
                InlineKeyboardButton("✅ Accept", callback_data=f"friend_accept_{req_id}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"friend_decline_{req_id}"),
            ]]
            target_name = target.display_name or target.first_name or "User"
            from_name = user.first_name or "Someone"
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"🤝 *Friend Request*\n\n"
                    f"{target.avatar_emoji or '🦖'} *{from_name}* (`{user.id}`) "
                    f"wants to be your friend!\n\n"
                    "_Accept to see each other's stats and share downloads._"
                ),
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            logger.error(f"Failed to notify friend request: {e}")

        await update.message.reply_text(
            f"✅ *Friend request sent!*\n\nWaiting for `{target_id}` to accept.",
            parse_mode="Markdown",
        )
    finally:
        session.close()


async def friends_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List user's friends and pending requests."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    session = get_session()
    try:
        # Accepted friends (in either direction)
        accepted = session.query(Friendship).filter(
            ((Friendship.user_id == user.id) | (Friendship.friend_id == user.id)) &
            (Friendship.status == "accepted")
        ).all()

        # Pending requests TO me
        incoming = session.query(Friendship).filter_by(
            friend_id=user.id, status="pending"
        ).all()

        # Pending requests FROM me
        outgoing = session.query(Friendship).filter_by(
            user_id=user.id, status="pending"
        ).all()

        text = "🤝 *Your Friends*\n━━━━━━━━━━━━━━━\n\n"

        if accepted:
            text += f"*✅ Friends ({len(accepted)})*\n"
            for f in accepted[:10]:
                other_id = f.friend_id if f.user_id == user.id else f.user_id
                other = session.query(User).filter_by(telegram_id=other_id).first()
                if other:
                    name = other.display_name or other.first_name or "Unknown"
                    emoji = other.avatar_emoji or "🦖"
                    text += f"{emoji} *{name}* — `{other_id}`\n"
                    text += f"   📥 {other.total_downloads} downloads\n"
            text += "\n"

        if incoming:
            text += f"*📬 Incoming Requests ({len(incoming)})*\n"
            for f in incoming[:5]:
                sender = session.query(User).filter_by(telegram_id=f.user_id).first()
                if sender:
                    name = sender.first_name or "Unknown"
                    text += f"• {name} (`{f.user_id}`)\n"
            text += "_Use /friends to check back for requests._\n\n"

        if outgoing:
            text += f"*📤 Sent Requests ({len(outgoing)})*\n"
            for f in outgoing[:5]:
                target = session.query(User).filter_by(telegram_id=f.friend_id).first()
                if target:
                    name = target.first_name or "Unknown"
                    text += f"• {name} (`{f.friend_id}`) _pending_\n"
            text += "\n"

        if not accepted and not incoming and not outgoing:
            text += "_No friends yet! Use `/addfriend <user_id>` to send a request._"

        text += "\n💡 *Commands:*\n"
        text += "`/addfriend <id>` — send request\n"
        text += "`/unfriend <id>` — remove friend"

        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        session.close()


async def unfriend_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a friend."""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "*Usage:* `/unfriend <telegram_id>`",
            parse_mode="Markdown",
        )
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return

    session = get_session()
    try:
        fs = session.query(Friendship).filter(
            ((Friendship.user_id == user.id) & (Friendship.friend_id == target_id)) |
            ((Friendship.user_id == target_id) & (Friendship.friend_id == user.id))
        ).first()

        if not fs:
            await update.message.reply_text("❌ No friendship found.")
            return

        session.delete(fs)
        session.commit()
        await update.message.reply_text("✅ Friendship removed.")
    finally:
        session.close()


async def friend_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle accept/decline friend request buttons."""
    query = update.callback_query
    await query.answer()
    data = query.data  # "friend_accept_5" or "friend_decline_5"

    parts = data.split("_")
    if len(parts) != 3:
        return

    action = parts[1]
    try:
        req_id = int(parts[2])
    except ValueError:
        return

    session = get_session()
    try:
        fs = session.query(Friendship).get(req_id)
        if not fs:
            await query.edit_message_text("❌ Request not found.")
            return

        if fs.friend_id != query.from_user.id:
            await query.answer("🚫 Not for you!", show_alert=True)
            return

        if action == "accept":
            fs.status = "accepted"
            fs.accepted_at = datetime.utcnow()
            session.commit()

            # Notify requester
            try:
                await context.bot.send_message(
                    chat_id=fs.user_id,
                    text=f"🎉 *{query.from_user.first_name}* accepted your friend request!",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

            await query.edit_message_text(
                "✅ *Friend request accepted!*\n\nUse /friends to see your friends list.",
                parse_mode="Markdown",
            )
        elif action == "decline":
            session.delete(fs)
            session.commit()
            await query.edit_message_text("❌ Request declined.")
    finally:
        session.close()
