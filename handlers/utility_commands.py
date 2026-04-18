"""Utility command handlers — QR, short URL, translate."""
import io
import aiohttp
import qrcode
from telegram import Update
from telegram.ext import ContextTypes


async def qr_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate QR code from text."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/qr <text>`\nExample: `/qr https://google.com`",
            parse_mode="Markdown",
        )
        return

    text = " ".join(context.args)
    if len(text) > 1000:
        await update.message.reply_text("❌ Text too long (max 1000 chars).")
        return

    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        bio = io.BytesIO()
        bio.name = "qr.png"
        img.save(bio, "PNG")
        bio.seek(0)

        await update.message.reply_photo(
            photo=bio,
            caption=f"🔲 *QR Code generated*\n\n`{text[:100]}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def short_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shorten a URL using TinyURL API."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/short <url>`\nExample: `/short https://verylongurl.com/...`",
            parse_mode="Markdown",
        )
        return

    url = context.args[0]
    if not url.startswith(("http://", "https://")):
        await update.message.reply_text("❌ URL must start with http:// or https://")
        return

    try:
        async with aiohttp.ClientSession() as session:
            api = f"https://tinyurl.com/api-create.php?url={url}"
            async with session.get(api, timeout=10) as resp:
                short = await resp.text()

        if short.startswith("http"):
            await update.message.reply_text(
                f"🔗 *URL Shortened!*\n\n"
                f"*Original:* `{url[:80]}...`\n"
                f"*Short:* {short}",
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        else:
            await update.message.reply_text("❌ Failed to shorten URL.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")


async def translate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick translate using Google Translate (free endpoint)."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/tr <text>`\n"
            "Auto-detects source, translates to English.\n\n"
            "For specific target: `/tr es Hello world` (to Spanish)",
            parse_mode="Markdown",
        )
        return

    args = context.args
    # Check if first arg is a lang code (2 letters)
    target = "en"
    if len(args[0]) == 2 and args[0].isalpha():
        target = args[0].lower()
        text = " ".join(args[1:])
    else:
        text = " ".join(args)

    if not text:
        await update.message.reply_text("❌ No text to translate.")
        return

    try:
        async with aiohttp.ClientSession() as session:
            api = (
                "https://translate.googleapis.com/translate_a/single"
                f"?client=gtx&sl=auto&tl={target}&dt=t&q={text}"
            )
            async with session.get(api, timeout=10) as resp:
                data = await resp.json()

        translated = "".join(part[0] for part in data[0] if part[0])
        source_lang = data[2] if len(data) > 2 else "auto"

        await update.message.reply_text(
            f"🌐 *Translation*\n\n"
            f"*From:* `{source_lang}` → *To:* `{target}`\n\n"
            f"{translated}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:200]}")
