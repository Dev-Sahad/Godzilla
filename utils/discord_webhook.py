"""Discord webhook for real-time bot notifications."""
import aiohttp
import logging
from datetime import datetime
from config import DISCORD_WEBHOOK_URL

logger = logging.getLogger(__name__)


async def send_discord_webhook(title, description, color=0x00FF41, fields=None):
    """Send an embed notification to Discord."""
    if not DISCORD_WEBHOOK_URL:
        return

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "🦖 GODZILLA BOT | SHA COMMUNITY"},
    }

    if fields:
        embed["fields"] = fields

    payload = {"embeds": [embed]}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10) as resp:
                if resp.status >= 400:
                    logger.warning(f"Discord webhook failed: {resp.status}")
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")


async def notify_new_user(user_id, username, first_name):
    """Notify when a new user joins."""
    await send_discord_webhook(
        title="👤 New User Joined",
        description=f"**{first_name}** started GODZILLA",
        color=0x00D4FF,
        fields=[
            {"name": "User ID", "value": f"`{user_id}`", "inline": True},
            {"name": "Username", "value": f"@{username}" if username else "None", "inline": True},
        ],
    )


async def notify_download(user_id, username, platform, media_type, title, status):
    """Notify on download."""
    color = 0x00FF41 if status == "success" else 0xFF1744
    emoji = "✅" if status == "success" else "❌"
    await send_discord_webhook(
        title=f"{emoji} Download {status.capitalize()}",
        description=f"**{title[:100]}**",
        color=color,
        fields=[
            {"name": "User", "value": f"@{username}" if username else f"`{user_id}`", "inline": True},
            {"name": "Platform", "value": platform.capitalize(), "inline": True},
            {"name": "Type", "value": media_type.capitalize(), "inline": True},
        ],
    )


async def notify_error(action, user_id, error):
    """Notify on errors."""
    await send_discord_webhook(
        title="⚠️ Error Occurred",
        description=f"```{str(error)[:500]}```",
        color=0xFF1744,
        fields=[
            {"name": "Action", "value": action, "inline": True},
            {"name": "User ID", "value": f"`{user_id}`", "inline": True},
        ],
    )


async def notify_admin_action(admin_id, action, details):
    """Notify on admin actions."""
    await send_discord_webhook(
        title="🛠️ Admin Action",
        description=f"**{action}**\n{details}",
        color=0xFFAA00,
        fields=[{"name": "Admin ID", "value": f"`{admin_id}`", "inline": True}],
    )
