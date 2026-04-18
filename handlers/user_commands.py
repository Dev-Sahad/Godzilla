"""User-facing command handlers."""
import time
import platform as plt
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import BOT_NAME, BOT_VERSION, BOT_OWNER, BOT_COMMUNITY, BOT_BORN, BOT_PREFIX
from database import (
    get_or_create_user, check_download_limit, get_user_history,
    add_favorite, get_favorites, remove_favorite, is_banned
)
from utils import notify_new_user


def get_uptime(start_time):
    """Format uptime."""
    seconds = int(time.time() - start_time)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{days}d {hours}h {minutes}m {seconds}s"


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message + register user."""
    user = update.effective_user

    # Check for referral code in /start argument
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            if referred_by == user.id:
                referred_by = None
        except (ValueError, IndexError):
            pass

    # Register user
    db_user = get_or_create_user(user.id, user.username, user.first_name, referred_by)

    # Notify admin via Discord on new users
    if db_user.total_downloads == 0 and not db_user.downloads_today:
        await notify_new_user(user.id, user.username, user.first_name)

    welcome = (
        f"🦖 *Welcome to GODZILLA, {user.first_name}!*\n\n"
        "I can download videos & audio from:\n"
        "▫️ YouTube\n"
        "▫️ Instagram (Reels/Posts)\n"
        "▫️ TikTok\n"
        "▫️ Twitter / X\n"
        "▫️ Facebook\n"
        "▫️ Pinterest\n"
        "▫️ Reddit, SoundCloud & more!\n\n"
        "📥 *How to use:* Just send me a link!\n\n"
        "*Quick commands:*\n"
        "/help — Full command list\n"
        "/info — Bot stats\n"
        "/history — Your downloads\n"
        "/favorites — Saved links\n"
        "/referral — Invite friends\n\n"
        "_🦖 GODZILLA — King of Bots_"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Full help menu."""
    help_text = (
        "🦖 *GODZILLA — Command Menu*\n\n"
        "*📥 DOWNLOADING*\n"
        "Just send any video/audio URL\n"
        "/quality — Set default quality\n"
        "/thumb <url> — Get video thumbnail\n"
        "/info\\_url <url> — Get video info\n"
        "/batch — Send up to 5 links at once\n\n"
        "*💎 PREMIUM*\n"
        "/subscribe — Upgrade to Premium\n"
        "/plans — View all plans\n"
        "/myplan — Check your plan\n"
        "/cancel — Cancel auto-renewal\n\n"
        "*👤 YOUR ACCOUNT*\n"
        "/history — Last 10 downloads\n"
        "/favorites — Saved links\n"
        "/fav <url> — Save to favorites\n"
        "/referral — Invite friends for rewards\n"
        "/limit — Check daily limit\n\n"
        "*ℹ️ INFO*\n"
        "/start — Welcome message\n"
        "/help — This menu\n"
        "/info — Bot info & live stats\n"
        "/about — About developer\n"
        "/ping — Check speed\n\n"
        "*🛠 UTILITY*\n"
        "/qr <text> — Generate QR code\n"
        "/short <url> — Short URL\n"
        "/tr <text> — Quick translate\n\n"
        "⚠️ Free limit: 3 downloads/day\n"
        "💎 Premium: 100/day — /subscribe\n"
        "🎁 Referrals: +3/day per friend\n\n"
        "_🦖 Always Online. Always Ready._"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed bot info."""
    start = time.time()
    msg = await update.message.reply_text("⏳ Loading info...")
    ping_ms = int((time.time() - start) * 1000)

    bot_start = context.bot_data.get("start_time", time.time())
    uptime = get_uptime(bot_start)

    now = datetime.now()
    time_str = now.strftime("%I:%M:%S %p")
    date_str = now.strftime("%B %d, %Y")

    info_text = f"""╔═══════════════════════════╗
║   🦖 *GODZILLA BOT v{BOT_VERSION}*  ║
║      _by {BOT_OWNER}_              ║
╚═══════════════════════════╝

━━━━━━ 🪪 *IDENTITY* ━━━━━━━
📛 *Name*        : {BOT_NAME}
🔖 *Version*     : {BOT_VERSION}
👑 *Owner*       : {BOT_OWNER}
🏠 *Community*   : {BOT_COMMUNITY}
📅 *Born*        : {BOT_BORN}
🌍 *Status*      : 🟢 _Online 24/7_

━━━━━━ ⚙️ *SYSTEM* ━━━━━━━━
📌 *Prefix*      : {BOT_PREFIX}
💬 *Commands*    : 25+
🔧 *Engine*      : python-telegram-bot v21
💻 *Runtime*     : Python {plt.python_version()}
🧠 *AI Model*    : Gemini (coming soon)
🌐 *Platform*    : {plt.system()} {plt.release()}
📡 *Database*    : PostgreSQL

━━━━━━ 📊 *LIVE STATS* ━━━━━━
⏱️ *Uptime*      : {uptime}
🕒 *Time*        : {time_str}
📅 *Date*        : {date_str}
⚡ *Ping*        : {ping_ms}ms
🟢 *Mode*        : public

━━━━━━ 🎯 *FEATURES* ━━━━━━━
▫️ Multi-Platform Downloader
▫️ Quality Selector (144p-1080p)
▫️ MP3 Audio Extraction
▫️ Batch Downloads (5 at once)
▫️ Thumbnail Extractor
▫️ Download History
▫️ Favorites System
▫️ Referral Rewards
▫️ Daily Limits
▫️ Admin Panel

━━━━━━ 👨‍💻 *CREDITS* ━━━━━━━
💻 *Developer*   : {BOT_OWNER}
🦖 *Project*     : {BOT_NAME}
🏠 *Built for*   : {BOT_COMMUNITY}
🧠 *AI by*       : Anthropic Claude
📦 *Hosted on*   : Railway.app

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_Type {BOT_PREFIX}help to see all commands_
_🦖 GODZILLA — King of Bots_"""

    await msg.edit_text(info_text, parse_mode="Markdown")


async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """About the developer."""
    about_text = (
        "🦖 *About GODZILLA*\n\n"
        f"*{BOT_NAME} v{BOT_VERSION}* is the most powerful media downloader "
        "bot on Telegram, built with love for SHA COMMUNITY.\n\n"
        "👨‍💻 *Developer:* @Sxhd_Sha\n"
        "🏠 *Community:* SHA COMMUNITY\n"
        "🌐 *GitHub:* github.com/Dev-Sahad\n\n"
        "_🦖 King of Bots. Always Online._"
    )
    await update.message.reply_text(about_text, parse_mode="Markdown")


async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ping command."""
    start = time.time()
    msg = await update.message.reply_text("🏓 Pinging...")
    ping_ms = int((time.time() - start) * 1000)
    bot_start = context.bot_data.get("start_time", time.time())
    await msg.edit_text(
        f"🦖 *GODZILLA Ping*\n\n"
        f"⚡ Response: `{ping_ms}ms`\n"
        f"⏱️ Uptime: `{get_uptime(bot_start)}`\n"
        f"🟢 Status: Online",
        parse_mode="Markdown",
    )


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's download history."""
    user_id = update.effective_user.id
    history = get_user_history(user_id, limit=10)

    if not history:
        await update.message.reply_text(
            "📭 *No downloads yet!*\n\nSend me a video link to get started.",
            parse_mode="Markdown",
        )
        return

    text = "📚 *Your Last 10 Downloads*\n\n"
    for i, h in enumerate(history, 1):
        emoji = "🎵" if h["media_type"] == "audio" else "🎬"
        date = h["created_at"].strftime("%b %d, %H:%M")
        title = h["title"][:60] + ("..." if len(h["title"]) > 60 else "")
        text += f"{emoji} *{i}.* {title}\n   `{h['platform']}` • {date}\n\n"

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def favorites_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's favorites."""
    user_id = update.effective_user.id
    favs = get_favorites(user_id)

    if not favs:
        await update.message.reply_text(
            "⭐ *No favorites saved.*\n\nUse `/fav <url>` to save a link.",
            parse_mode="Markdown",
        )
        return

    text = f"⭐ *Your Favorites ({len(favs)})*\n\n"
    for i, f in enumerate(favs[:20], 1):
        title = f["title"][:60] + ("..." if len(f["title"]) > 60 else "")
        text += f"*{i}.* {title}\n   🆔 `{f['id']}` — [Link]({f['url']})\n\n"

    text += "_Remove with_ `/unfav <id>`"
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def fav_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a favorite."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/fav <url>`\nExample: `/fav https://youtube.com/...`",
            parse_mode="Markdown",
        )
        return

    url = context.args[0]
    user_id = update.effective_user.id

    if add_favorite(user_id, url, url[:100]):
        await update.message.reply_text("⭐ *Added to favorites!*", parse_mode="Markdown")
    else:
        await update.message.reply_text("ℹ️ Already in favorites.")


async def unfav_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a favorite."""
    if not context.args:
        await update.message.reply_text("Usage: `/unfav <id>`", parse_mode="Markdown")
        return

    try:
        fav_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Use number from `/favorites`.")
        return

    user_id = update.effective_user.id
    if remove_favorite(user_id, fav_id):
        await update.message.reply_text("🗑️ *Favorite removed.*", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Favorite not found.")


async def referral_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show referral code."""
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    ref_link = f"https://t.me/{bot_username}?start={user.id}"

    from database import get_or_create_user
    from config import REFERRAL_BONUS, REFERRAL_GOAL_FREE_PREMIUM
    db_user = get_or_create_user(user.id, user.username, user.first_name)

    progress_bar_len = 10
    progress = min(db_user.referral_count / REFERRAL_GOAL_FREE_PREMIUM, 1.0)
    filled = int(progress * progress_bar_len)
    bar = "█" * filled + "░" * (progress_bar_len - filled)

    text = (
        "🎁 *Referral Program*\n\n"
        f"Your referral link:\n`{ref_link}`\n\n"
        f"👥 *Friends invited:* {db_user.referral_count}\n"
        f"🎯 *Bonus downloads:* +{db_user.referral_count * REFERRAL_BONUS}/day\n\n"
        "*🏆 Free Premium Challenge*\n"
        f"`{bar}` {db_user.referral_count}/{REFERRAL_GOAL_FREE_PREMIUM}\n"
        f"Invite *{REFERRAL_GOAL_FREE_PREMIUM}* friends = *7 days free premium!*\n\n"
        "*How it works:*\n"
        f"• Each friend who joins = +{REFERRAL_BONUS} daily downloads\n"
        f"• Hit {REFERRAL_GOAL_FREE_PREMIUM} friends = free 7-day premium\n"
        "• Or just use /subscribe to go premium instantly!\n\n"
        "_🦖 Share the beast._"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def limit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check daily download limit."""
    user_id = update.effective_user.id
    can_dl, used, limit = check_download_limit(user_id)

    bar_filled = int((used / limit) * 10) if limit > 0 else 0
    bar = "█" * bar_filled + "░" * (10 - bar_filled)

    text = (
        "📊 *Your Daily Usage*\n\n"
        f"`{bar}`\n"
        f"*Used:* {used} / {limit}\n"
        f"*Remaining:* {limit - used}\n\n"
    )
    if not can_dl:
        text += "⚠️ *Limit reached!* Resets at midnight UTC.\nInvite friends with /referral for more!"
    else:
        text += "✅ *You can keep downloading!*"

    await update.message.reply_text(text, parse_mode="Markdown")
