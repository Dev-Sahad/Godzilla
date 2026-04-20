"""
User Profile Handler - v3.3
Commands: /profile, /setbio, /setname, /setemoji
Auto-awards badges based on user achievements.
"""
import json
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.models import get_session, User
from database import get_or_create_user

logger = logging.getLogger(__name__)

# ========== BADGES ==========

BADGES = {
    "early_bird":   {"emoji": "🌅", "name": "Early Bird",    "desc": "One of first 100 users"},
    "loyal":        {"emoji": "💎", "name": "Loyal User",    "desc": "30+ days active"},
    "downloader":   {"emoji": "📥", "name": "Downloader",    "desc": "100+ downloads"},
    "power_user":   {"emoji": "⚡", "name": "Power User",    "desc": "500+ downloads"},
    "legend":       {"emoji": "👑", "name": "Legend",        "desc": "1000+ downloads"},
    "referrer":     {"emoji": "🤝", "name": "Referrer",      "desc": "Invited 1+ friends"},
    "ambassador":   {"emoji": "🌟", "name": "Ambassador",    "desc": "Invited 10+ friends"},
    "premium":      {"emoji": "💳", "name": "Supporter",     "desc": "Active premium"},
    "veteran":      {"emoji": "🎖", "name": "Veteran",       "desc": "90+ days account age"},
}

AVATAR_EMOJIS = ["🦖", "🐉", "⚡", "🔥", "💎", "👑", "🎯", "🚀", "🎮", "🦁",
                 "🐺", "🦅", "🐙", "🦊", "🐯", "🎨", "🎭", "🎪", "🌟", "💫"]


def get_user_badges(user):
    """Get list of badge keys the user has earned."""
    try:
        return json.loads(user.badges) if user.badges else []
    except Exception:
        return []


def set_user_badges(user, badges_list):
    """Save badge list to user."""
    user.badges = json.dumps(badges_list)


def compute_badges(user):
    """Compute which badges user deserves based on their activity."""
    earned = set(get_user_badges(user))
    now = datetime.utcnow()

    # Downloads milestones
    if user.total_downloads >= 100:
        earned.add("downloader")
    if user.total_downloads >= 500:
        earned.add("power_user")
    if user.total_downloads >= 1000:
        earned.add("legend")

    # Referrals
    if user.referral_count >= 1:
        earned.add("referrer")
    if user.referral_count >= 10:
        earned.add("ambassador")

    # Premium
    if user.is_premium:
        earned.add("premium")

    # Age-based
    try:
        age_days = (now - user.joined_at).days
        if age_days >= 90:
            earned.add("veteran")
        if age_days >= 30:
            earned.add("loyal")
    except Exception:
        pass

    # Early bird (first 100 users)
    if user.id and user.id <= 100:
        earned.add("early_bird")

    return sorted(earned)


def format_badges(badge_keys):
    """Convert badge keys to display string."""
    if not badge_keys:
        return "_No badges yet_"
    return " ".join(BADGES[k]["emoji"] for k in badge_keys if k in BADGES)


# ========== COMMANDS ==========

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's profile."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    session = get_session()
    try:
        u = session.query(User).filter_by(telegram_id=user.id).first()
        if not u:
            await update.message.reply_text("❌ User not found.")
            return

        # Update badges
        new_badges = compute_badges(u)
        set_user_badges(u, new_badges)
        session.commit()

        display = u.display_name or u.first_name or "Unknown"
        avatar = u.avatar_emoji or "🦖"
        bio = u.bio or "_No bio yet. Set with /setbio_"
        title = f" | 🎖 *{u.title}*" if u.title else ""

        # Stats
        age_days = (datetime.utcnow() - u.joined_at).days if u.joined_at else 0
        plan_status = "💎 Premium" if u.is_premium else "🆓 Free"

        text = (
            f"{avatar} *{display}*{title}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📝 *About:*\n{bio}\n\n"
            f"🏆 *Badges:*\n{format_badges(new_badges)}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📊 *Stats*\n"
            f"📥 Downloads: `{u.total_downloads}`\n"
            f"🤝 Referrals: `{u.referral_count}`\n"
            f"⭐ Reputation: `{u.reputation}`\n"
            f"📅 Member for: `{age_days} days`\n"
            f"💳 Status: {plan_status}\n"
            f"━━━━━━━━━━━━━━━\n\n"
            "_Customize: /setbio /setname /setemoji_"
        )

        keyboard = [[
            InlineKeyboardButton("📝 Edit Bio", callback_data="profile_edit_bio"),
            InlineKeyboardButton("😀 Change Emoji", callback_data="profile_change_emoji"),
        ]]

        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    finally:
        session.close()


async def setbio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's bio."""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "Usage: `/setbio Your bio here`\n\n"
            "Example: `/setbio Music lover and content creator 🎵`\n\n"
            "Max 200 characters.",
            parse_mode="Markdown",
        )
        return

    bio = " ".join(context.args)
    if len(bio) > 200:
        await update.message.reply_text("❌ Bio too long. Max 200 chars.")
        return

    session = get_session()
    try:
        u = session.query(User).filter_by(telegram_id=user.id).first()
        if u:
            u.bio = bio
            session.commit()
            await update.message.reply_text(
                f"✅ *Bio updated!*\n\n_{bio}_",
                parse_mode="Markdown",
            )
    finally:
        session.close()


async def setname_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set display name."""
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "Usage: `/setname Your Display Name`\n\nMax 50 chars.",
            parse_mode="Markdown",
        )
        return

    name = " ".join(context.args)[:50]

    session = get_session()
    try:
        u = session.query(User).filter_by(telegram_id=user.id).first()
        if u:
            u.display_name = name
            session.commit()
            await update.message.reply_text(f"✅ Display name set to: *{name}*", parse_mode="Markdown")
    finally:
        session.close()


async def setemoji_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show emoji picker."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    # Create emoji grid (4 per row)
    keyboard = []
    for i in range(0, len(AVATAR_EMOJIS), 4):
        row = [
            InlineKeyboardButton(e, callback_data=f"profile_set_emoji_{e}")
            for e in AVATAR_EMOJIS[i:i+4]
        ]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="profile_cancel")])

    await update.message.reply_text(
        "😀 *Pick your avatar emoji:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle profile-related callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "profile_cancel":
        await query.edit_message_text("❌ Cancelled.")
        return

    if data.startswith("profile_set_emoji_"):
        emoji = data[len("profile_set_emoji_"):]
        session = get_session()
        try:
            u = session.query(User).filter_by(telegram_id=query.from_user.id).first()
            if u:
                u.avatar_emoji = emoji
                session.commit()
                await query.edit_message_text(
                    f"✅ Avatar set to: {emoji}\n\nUse /profile to see your profile!",
                )
        finally:
            session.close()
        return

    if data == "profile_edit_bio":
        await query.answer(
            "Use: /setbio Your bio here",
            show_alert=True,
        )
        return

    if data == "profile_change_emoji":
        await setemoji_cmd_from_callback(query, context)
        return


async def setemoji_cmd_from_callback(query, context):
    """Trigger emoji picker from callback."""
    keyboard = []
    for i in range(0, len(AVATAR_EMOJIS), 4):
        row = [
            InlineKeyboardButton(e, callback_data=f"profile_set_emoji_{e}")
            for e in AVATAR_EMOJIS[i:i+4]
        ]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="profile_cancel")])

    await query.edit_message_text(
        "😀 *Pick your avatar emoji:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def badges_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all available badges."""
    text = "🏆 *GODZILLA Badges*\n━━━━━━━━━━━━━━━\n\n"
    for key, info in BADGES.items():
        text += f"{info['emoji']} *{info['name']}*\n_{info['desc']}_\n\n"
    text += "_Badges are earned automatically based on your activity!_"

    await update.message.reply_text(text, parse_mode="Markdown")
