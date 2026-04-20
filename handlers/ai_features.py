"""
AI Features - v3.5
Commands: /ai, /script, /askai, /aisearch
Uses Google Gemini API.
"""
import logging
import os
from telegram import Update
from telegram.ext import ContextTypes

from config import GEMINI_API_KEY
from database import get_or_create_user

logger = logging.getLogger(__name__)


def is_gemini_configured():
    return bool(GEMINI_API_KEY)


async def call_gemini(prompt, max_tokens=800):
    """Call Gemini API and return response text."""
    if not is_gemini_configured():
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-pro")

        response = model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": max_tokens,
                "temperature": 0.8,
            }
        )
        return response.text
    except ImportError:
        return "ERROR: google-generativeai library not installed"
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return f"ERROR: {e}"


async def askai_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Chat with AI. Usage: /askai <question>"""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    if not is_gemini_configured():
        await update.message.reply_text(
            "⚠️ *AI not configured*\n\nAdmin needs to set `GEMINI_API_KEY` in environment.",
            parse_mode="Markdown",
        )
        return

    if not context.args:
        await update.message.reply_text(
            "*Usage:* `/askai <your question>`\n\n"
            "*Examples:*\n"
            "• `/askai Who invented Python?`\n"
            "• `/askai Best YouTube thumbnail design tips`\n"
            "• `/askai Explain quantum computing simply`",
            parse_mode="Markdown",
        )
        return

    question = " ".join(context.args)
    msg = await update.message.reply_text("🤖 _Thinking..._", parse_mode="Markdown")

    response = await call_gemini(question, max_tokens=600)

    if not response:
        await msg.edit_text("❌ AI unavailable right now. Try again later.")
        return

    if response.startswith("ERROR:"):
        await msg.edit_text(f"❌ {response}")
        return

    # Truncate if too long
    if len(response) > 3800:
        response = response[:3800] + "..."

    await msg.edit_text(
        f"🤖 *AI Response:*\n\n{response}\n\n_Powered by Gemini_",
        parse_mode="Markdown",
    )


async def script_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate video script. Usage: /script <topic>"""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    if not is_gemini_configured():
        await update.message.reply_text(
            "⚠️ *AI Script Generator not configured*\n\n"
            "Admin needs to set `GEMINI_API_KEY`.",
            parse_mode="Markdown",
        )
        return

    if not context.args:
        await update.message.reply_text(
            "*🎬 Video Script Generator*\n\n"
            "*Usage:* `/script <topic>`\n\n"
            "*Examples:*\n"
            "• `/script How to cook biryani`\n"
            "• `/script GTA V roleplay tips`\n"
            "• `/script iPhone 15 review`\n"
            "• `/script Funny anime moments`\n\n"
            "_Gets you a ready-to-shoot script for Instagram Reels/YouTube Shorts!_",
            parse_mode="Markdown",
        )
        return

    topic = " ".join(context.args)
    msg = await update.message.reply_text("✍️ _Writing your script..._", parse_mode="Markdown")

    prompt = (
        f"Write a short, engaging video script for Instagram Reels or YouTube Shorts on the topic: \"{topic}\".\n\n"
        "Format your response EXACTLY like this:\n\n"
        "**HOOK (0-3 sec):**\n[attention-grabbing opening]\n\n"
        "**MAIN CONTENT (3-45 sec):**\n[3-5 key points in short sentences]\n\n"
        "**CLIMAX (45-55 sec):**\n[surprising fact or reveal]\n\n"
        "**CTA (55-60 sec):**\n[call to action - like/follow/comment]\n\n"
        "**CAPTION:**\n[Instagram caption with hashtags]\n\n"
        "Keep it punchy, casual, and under 60 seconds total. Use emojis naturally."
    )

    response = await call_gemini(prompt, max_tokens=800)

    if not response or response.startswith("ERROR:"):
        await msg.edit_text(f"❌ Script generation failed: {response or 'Unknown error'}")
        return

    if len(response) > 3800:
        response = response[:3800] + "..."

    await msg.edit_text(
        f"🎬 *Your Video Script*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"*Topic:* {topic}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"{response}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"_🎥 Ready to film! Powered by Gemini AI_",
        parse_mode="Markdown",
    )


async def aisearch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI-powered smart search. Usage: /aisearch <description>"""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    if not is_gemini_configured():
        await update.message.reply_text(
            "⚠️ *AI Search not configured*\n\nAdmin needs to set `GEMINI_API_KEY`.",
            parse_mode="Markdown",
        )
        return

    if not context.args:
        await update.message.reply_text(
            "*🧠 Smart AI Search*\n\n"
            "*Usage:* `/aisearch <description>`\n\n"
            "*Examples:*\n"
            "• `/aisearch funny cat videos`\n"
            "• `/aisearch Naruto best fight scenes`\n"
            "• `/aisearch latest Malayalam songs`\n"
            "• `/aisearch iPhone unboxing`\n\n"
            "_AI finds the best YouTube matches for you!_",
            parse_mode="Markdown",
        )
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text("🔍 _Searching with AI..._", parse_mode="Markdown")

    prompt = (
        f"I want to find YouTube videos matching this description: \"{query}\"\n\n"
        "Suggest exactly 5 specific video titles that would be popular YouTube search results for this query. "
        "Format your response as a numbered list (1-5). Each line should contain ONLY the video title (no extra commentary).\n\n"
        "Also include a good YouTube search query at the end.\n\n"
        "Example format:\n"
        "1. Video Title One\n"
        "2. Video Title Two\n"
        "...\n"
        "**Search query:** best keyword search terms"
    )

    response = await call_gemini(prompt, max_tokens=500)

    if not response or response.startswith("ERROR:"):
        await msg.edit_text(f"❌ AI search failed: {response or 'Unknown error'}")
        return

    search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"

    await msg.edit_text(
        f"🧠 *AI Search Results*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"*Query:* {query}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"{response}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔗 [Search on YouTube]({search_url})\n\n"
        f"_Tip: Copy a title above and send it to me — I'll download it!_",
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )
