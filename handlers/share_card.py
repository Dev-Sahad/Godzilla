"""
Share Cards - v3.5
Commands: /sharecard - generate Instagram-ready profile card
Uses Pillow to create beautiful PNG images.
"""
import os
import io
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from database.models import get_session, User
from database import get_or_create_user

logger = logging.getLogger(__name__)


def generate_share_card(user_obj):
    """Generate a beautiful profile card PNG. Returns BytesIO."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None

    # Card dimensions (Instagram story size 9:16)
    W, H = 1080, 1920

    # Create gradient background (dark green/black)
    img = Image.new("RGB", (W, H), (10, 10, 15))
    draw = ImageDraw.Draw(img)

    # Draw gradient (simulated)
    for y in range(H):
        r = int(10 + (y / H) * 15)
        g = int(20 + (y / H) * 40)
        b = int(15 + (y / H) * 20)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Try to load a font, fallback to default
    try:
        font_xl = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
        font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
        font_md = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 55)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except Exception:
        font_xl = ImageFont.load_default()
        font_lg = font_xl
        font_md = font_xl
        font_sm = font_xl

    # Top area: Bot logo/title
    draw.text((W//2, 180), "🦖 GODZILLA", fill=(0, 255, 65), font=font_xl, anchor="mm")
    draw.text((W//2, 270), "Media Downloader", fill=(150, 150, 150), font=font_sm, anchor="mm")

    # Divider
    draw.line([(100, 340), (W-100, 340)], fill=(0, 255, 65), width=3)

    # User profile section
    avatar = user_obj.avatar_emoji or "🦖"
    name = user_obj.display_name or user_obj.first_name or "User"

    draw.text((W//2, 500), avatar, fill=(255, 255, 255), font=font_xl, anchor="mm")
    draw.text((W//2, 640), name, fill=(255, 255, 255), font=font_lg, anchor="mm")

    if user_obj.title:
        draw.text((W//2, 740), f"🏅 {user_obj.title}", fill=(255, 200, 0), font=font_md, anchor="mm")

    # Stats box
    stats_y = 900
    draw.rectangle([(80, stats_y), (W-80, stats_y + 550)], outline=(0, 255, 65), width=3)
    draw.text((W//2, stats_y + 70), "📊 MY STATS", fill=(0, 255, 65), font=font_md, anchor="mm")

    draw.text((W//2, stats_y + 180), f"📥 {user_obj.total_downloads}", fill=(255, 255, 255), font=font_lg, anchor="mm")
    draw.text((W//2, stats_y + 260), "Downloads", fill=(150, 150, 150), font=font_sm, anchor="mm")

    draw.text((W//2, stats_y + 360), f"🤝 {user_obj.referral_count}", fill=(255, 255, 255), font=font_lg, anchor="mm")
    draw.text((W//2, stats_y + 440), "Friends Invited", fill=(150, 150, 150), font=font_sm, anchor="mm")

    # Premium badge
    if user_obj.is_premium:
        draw.text((W//2, 1530), "💎 PREMIUM MEMBER", fill=(255, 215, 0), font=font_md, anchor="mm")

    # Call to action at bottom
    draw.rectangle([(80, 1650), (W-80, 1820)], fill=(0, 255, 65))
    draw.text((W//2, 1720), "Join GODZILLA", fill=(0, 0, 0), font=font_md, anchor="mm")
    draw.text((W//2, 1780), "@godzilla_media_downloader_bot", fill=(0, 0, 0), font=font_sm, anchor="mm")

    # Creator credit
    draw.text((W//2, 1870), "Made by @sahad_____sha", fill=(100, 100, 100), font=font_sm, anchor="mm")

    # Save to BytesIO
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


async def sharecard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate user's shareable profile card."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    msg = await update.message.reply_text("🎨 *Generating your share card...*", parse_mode="Markdown")

    session = get_session()
    try:
        u = session.query(User).filter_by(telegram_id=user.id).first()
        if not u:
            await msg.edit_text("❌ User not found.")
            return

        card = generate_share_card(u)
        if not card:
            await msg.edit_text(
                "❌ *Image generation unavailable*\n\n"
                "Pillow library is needed. Ask admin to install it.",
                parse_mode="Markdown",
            )
            return

        await context.bot.send_photo(
            chat_id=user.id,
            photo=card,
            caption=(
                "✨ *Your GODZILLA Share Card*\n\n"
                "📱 *Share this on:*\n"
                "• Instagram Story\n"
                "• Twitter/X\n"
                "• WhatsApp Status\n\n"
                "_Earn a badge for each friend who joins!_ 🦖"
            ),
            parse_mode="Markdown",
        )
        await msg.delete()
    except Exception as e:
        logger.error(f"Share card error: {e}")
        await msg.edit_text(f"❌ Error generating card: {e}")
    finally:
        session.close()
