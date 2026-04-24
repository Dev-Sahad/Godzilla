"""Download command handlers with quality selection."""
import os
import re
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import MAX_FILE_SIZE, MAX_BATCH_LINKS
from database import (
    check_download_limit, record_download, is_banned, get_or_create_user
)
from utils import (
    detect_platform, is_valid_url, download_video, download_audio,
    download_thumbnail, get_video_info, cleanup_file, notify_download, notify_error
)

logger = logging.getLogger(__name__)

# Store pending downloads: user_id -> {"url": str, "quality": str}
pending_downloads = {}
# Store user quality preferences: user_id -> quality
user_quality_pref = {}


URL_REGEX = re.compile(r"https?://[^\s]+")


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming URL — show download options."""
    user = update.effective_user
    text = update.message.text.strip()

    # Ban check
    if is_banned(user.id):
        await update.message.reply_text("🚫 *You are banned from using this bot.*", parse_mode="Markdown")
        return

    # Register user if new
    get_or_create_user(user.id, user.username, user.first_name)

    # Detect URLs
    urls = URL_REGEX.findall(text)

    # Batch detection (multiple URLs)
    if len(urls) > 1:
        await handle_batch(update, context, urls)
        return

    # Single URL
    url = urls[0] if urls else text
    if not is_valid_url(url):
        await update.message.reply_text(
            "❌ Please send a valid URL or use /help for commands."
        )
        return

    # Check download limit
    can_dl, used, limit = check_download_limit(user.id)
    if not can_dl:
        await update.message.reply_text(
            f"⚠️ *Daily limit reached!* ({used}/{limit})\n\n"
            "Invite friends with /referral for more downloads!",
            parse_mode="Markdown",
        )
        return

    pending_downloads[user.id] = {"url": url}
    platform = detect_platform(url)

    keyboard = [
        [
            InlineKeyboardButton("🎬 Video", callback_data="dl_video"),
            InlineKeyboardButton("🎵 Audio MP3", callback_data="dl_audio"),
        ],
        [
            InlineKeyboardButton("🖼 Thumbnail", callback_data="dl_thumb"),
            InlineKeyboardButton("ℹ️ Info", callback_data="dl_info"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="dl_cancel")],
    ]

    await update.message.reply_text(
        f"🦖 *Link Detected!*\n\n"
        f"📡 *Platform:* `{platform}`\n"
        f"📊 *Daily usage:* {used}/{limit}\n\n"
        "*Choose an action:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def handle_batch(update: Update, context: ContextTypes.DEFAULT_TYPE, urls):
    """Handle multiple URLs (batch download)."""
    user_id = update.effective_user.id

    if len(urls) > MAX_BATCH_LINKS:
        await update.message.reply_text(
            f"⚠️ *Max {MAX_BATCH_LINKS} links per batch.*\n\n"
            f"You sent {len(urls)}. Only first {MAX_BATCH_LINKS} will process.",
            parse_mode="Markdown",
        )
        urls = urls[:MAX_BATCH_LINKS]

    # Check limit — needs enough quota for all
    can_dl, used, limit = check_download_limit(user_id)
    if used + len(urls) > limit:
        await update.message.reply_text(
            f"⚠️ *Not enough daily downloads left.*\n"
            f"Need: {len(urls)} | Available: {limit - used}",
            parse_mode="Markdown",
        )
        return

    status = await update.message.reply_text(
        f"🔄 *Batch download started*\n📦 {len(urls)} links queued...",
        parse_mode="Markdown",
    )

    success = 0
    failed = 0
    for i, url in enumerate(urls, 1):
        if not is_valid_url(url):
            failed += 1
            continue

        try:
            await status.edit_text(
                f"🔄 *Batch download*\n"
                f"📦 [{i}/{len(urls)}] `{url[:50]}...`\n"
                f"✅ Done: {success} | ❌ Failed: {failed}",
                parse_mode="Markdown",
            )

            file_path, title = await download_video(url, user_id, quality="720p")
            platform = detect_platform(url)

            if os.path.getsize(file_path) > MAX_FILE_SIZE:
                cleanup_file(file_path)
                record_download(user_id, url, title, platform, "video", "720p", 0, "failed", "Too large")
                failed += 1
                continue

            with open(file_path, "rb") as f:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=f,
                    caption=f"🦖 *{title[:80]}*",
                    parse_mode="Markdown",
                )

            file_size_mb = os.path.getsize(file_path) / 1024 / 1024
            cleanup_file(file_path)
            record_download(user_id, url, title, platform, "video", "720p", file_size_mb, "success")
            success += 1
        except Exception as e:
            logger.error(f"Batch error for {url}: {e}")
            failed += 1

    await status.edit_text(
        f"✅ *Batch Complete*\n\n"
        f"✅ Success: `{success}`\n"
        f"❌ Failed: `{failed}`\n"
        f"📦 Total: `{len(urls)}`",
        parse_mode="Markdown",
    )


async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle download button callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    action = query.data

    if action == "dl_cancel":
        pending_downloads.pop(user_id, None)
        await query.edit_message_text("❌ Cancelled.")
        return

    data = pending_downloads.get(user_id)
    if not data:
        await query.edit_message_text("❌ Session expired. Send the link again.")
        return

    url = data["url"]
    platform = detect_platform(url)

    # Video quality selection
    if action == "dl_video":
        keyboard = [
            [
                InlineKeyboardButton("📱 360p", callback_data="q_360p"),
                InlineKeyboardButton("💻 720p", callback_data="q_720p"),
            ],
            [
                InlineKeyboardButton("🖥 1080p", callback_data="q_1080p"),
                InlineKeyboardButton("⚡ Best", callback_data="q_best"),
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="dl_back")],
        ]
        await query.edit_message_text(
            "🎬 *Select Quality:*\n\n"
            "📱 360p — Fastest, low data\n"
            "💻 720p — HD, balanced\n"
            "🖥 1080p — Full HD\n"
            "⚡ Best — Max available\n\n"
            "_⚠️ Higher quality = larger file_",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return

    # Quality selected — start video download
    if action.startswith("q_"):
        quality = action[2:]  # remove "q_"
        await query.edit_message_text(f"⏳ Downloading video ({quality})...")
        await perform_download(query, context, url, "video", quality, platform, user_id)
        return

    # Audio download
    if action == "dl_audio":
        await query.edit_message_text("⏳ Extracting audio...")
        await perform_download(query, context, url, "audio", "mp3", platform, user_id)
        return

    # Thumbnail
    if action == "dl_thumb":
        await query.edit_message_text("⏳ Fetching thumbnail...")
        try:
            thumb_path, title = await download_thumbnail(url, user_id)
            if thumb_path and os.path.exists(thumb_path):
                with open(thumb_path, "rb") as f:
                    await context.bot.send_photo(
                        chat_id=query.message.chat_id,
                        photo=f,
                        caption=f"🖼 *{title[:80]}*\n\n_🦖 GODZILLA_",
                        parse_mode="Markdown",
                    )
                cleanup_file(thumb_path)
                await query.delete_message()
            else:
                await query.edit_message_text("❌ Thumbnail not available.")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)[:200]}")
        return

    # Info
    if action == "dl_info":
        await query.edit_message_text("⏳ Fetching info...")
        try:
            info = await get_video_info(url)
            duration = info["duration"]
            mins, secs = divmod(duration, 60)
            views = f"{info['view_count']:,}" if info["view_count"] else "N/A"

            text = (
                f"ℹ️ *Video Info*\n\n"
                f"📌 *Title:* {info['title'][:100]}\n"
                f"👤 *Uploader:* {info['uploader']}\n"
                f"⏱ *Duration:* {mins}m {secs}s\n"
                f"👁 *Views:* {views}\n"
                f"📡 *Platform:* {platform}"
            )
            await query.edit_message_text(text, parse_mode="Markdown")
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)[:200]}")
        return


async def perform_download(query, context, url, media_type, quality, platform, user_id):
    """Actually download and send the file."""
    file_path = None
    try:
        if media_type == "video":
            file_path, title = await download_video(url, user_id, quality)
        else:
            file_path, title = await download_audio(url, user_id)

        # Size check
        size = os.path.getsize(file_path)
        if size > MAX_FILE_SIZE:
            cleanup_file(file_path)
            await query.edit_message_text(
                f"❌ *File too large!* ({size / 1024 / 1024:.1f} MB)\n\n"
                "Telegram bot limit is 50MB. Try:\n"
                "• Lower quality (360p)\n"
                "• Audio only\n"
                "• Shorter video",
                parse_mode="Markdown",
            )
            record_download(user_id, url, title, platform, media_type, quality, size/1024/1024, "failed", "Too large")
            return

        await query.edit_message_text("📤 Uploading to Telegram...")

        caption = f"🦖 *{title[:80]}*\n_Downloaded by GODZILLA_"
        with open(file_path, "rb") as f:
            if media_type == "video":
                await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=f,
                    caption=caption,
                    parse_mode="Markdown",
                    supports_streaming=True,
                )
            else:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=f,
                    caption=caption,
                    parse_mode="Markdown",
                )

        # Record success
        file_size_mb = size / 1024 / 1024
        record_download(user_id, url, title, platform, media_type, quality, file_size_mb, "success")

        await notify_download(
            user_id, query.from_user.username, platform, media_type, title, "success"
        )
        await query.delete_message()

    except Exception as e:
        logger.error(f"Download error: {e}")
        err = str(e)[:250]

        # Friendly error display
        err_text = (
            f"❌ *Download Failed*\n\n"
            f"_{err}_\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💡 *Tips:*\n"
            f"• Try a shorter video\n"
            f"• Try audio-only (smaller)\n"
            f"• Wait 1-2 min if rate-limited\n"
            f"• Make sure link is public"
        )
        try:
            await query.edit_message_text(err_text, parse_mode="Markdown")
        except Exception:
            pass

        record_download(user_id, url, "Unknown", platform, media_type, quality, 0, "failed", err)
        await notify_error("Download", user_id, err)
    finally:
        cleanup_file(file_path)
        pending_downloads.pop(user_id, None)


async def quality_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set default quality preference."""
    user_id = update.effective_user.id

    keyboard = [
        [
            InlineKeyboardButton("📱 360p", callback_data="pref_360p"),
            InlineKeyboardButton("💻 720p", callback_data="pref_720p"),
        ],
        [
            InlineKeyboardButton("🖥 1080p", callback_data="pref_1080p"),
            InlineKeyboardButton("⚡ Best", callback_data="pref_best"),
        ],
    ]
    current = user_quality_pref.get(user_id, "720p")
    await update.message.reply_text(
        f"🎬 *Set Default Video Quality*\n\n"
        f"Current: `{current}`\n\n"
        "Choose a new default:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def quality_pref_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save quality preference."""
    query = update.callback_query
    await query.answer()

    quality = query.data[5:]  # remove "pref_"
    user_quality_pref[query.from_user.id] = quality
    await query.edit_message_text(
        f"✅ *Default quality set to:* `{quality}`",
        parse_mode="Markdown",
    )


async def thumb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extract thumbnail command."""
    if not context.args:
        await update.message.reply_text("Usage: `/thumb <url>`", parse_mode="Markdown")
        return

    url = context.args[0]
    if not is_valid_url(url):
        await update.message.reply_text("❌ Invalid URL.")
        return

    user_id = update.effective_user.id
    status = await update.message.reply_text("⏳ Fetching thumbnail...")

    try:
        thumb_path, title = await download_thumbnail(url, user_id)
        if thumb_path and os.path.exists(thumb_path):
            with open(thumb_path, "rb") as f:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=f,
                    caption=f"🖼 *{title[:80]}*",
                    parse_mode="Markdown",
                )
            cleanup_file(thumb_path)
            await status.delete()
        else:
            await status.edit_text("❌ Thumbnail not available.")
    except Exception as e:
        await status.edit_text(f"❌ Error: {str(e)[:200]}")
