"""
GODZILLA v3.0.0 - Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ===== BOT INFO =====
BOT_NAME = "GODZILLA"
BOT_VERSION = "3.0.0"
BOT_OWNER = "@Sxhd_Sha"
BOT_COMMUNITY = "SHA COMMUNITY"
BOT_BORN = "2025"
BOT_PREFIX = "/"

# ===== CREDENTIALS (from .env) =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///godzilla.db")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# ===== UPI PAYMENT (Direct/Manual) =====
# Your UPI ID users will pay to
UPI_ID = os.getenv("UPI_ID", "")
# Display name for UPI (what users see)
UPI_NAME = os.getenv("UPI_NAME", "GODZILLA")
# QR code image file (place in web/static/)
UPI_QR_FILENAME = os.getenv("UPI_QR_FILENAME", "upi_qr.png")
# Max pending requests per user (anti-spam)
MAX_PENDING_PER_USER = 3

# ===== RAZORPAY (from .env) — optional if using UPI only =====
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# ===== ADMIN WEB PANEL =====
# Web panel URL (set this after Railway generates your domain)
# Example: https://godzilla-bot-production.up.railway.app
WEB_PANEL_URL = os.getenv("WEB_PANEL_URL", "")
# Secret key for Flask sessions (random string)
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-this-to-random-string-in-production")

# ===== LIMITS =====
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB Telegram limit
DAILY_DOWNLOAD_LIMIT_FREE = 3       # Free users get 3 downloads per day
DAILY_DOWNLOAD_LIMIT_PREMIUM = 100  # Premium users get 100 per day
REFERRAL_BONUS = 3                  # Each friend invited = +3 daily downloads
REFERRAL_GOAL_FREE_PREMIUM = 10     # Invite 10 friends = 7 days free premium
MAX_BATCH_LINKS = 5

# ===== DOWNLOAD SETTINGS =====
DOWNLOAD_DIR = "downloads"
QUALITY_OPTIONS = {
    "low": "worst[height>=240]",
    "360p": "best[height<=360]",
    "720p": "best[height<=720]",
    "1080p": "best[height<=1080]",
    "best": "best",
}

# ===== URL FOR SELF-PING (for uptime) =====
SELF_URL = os.getenv("SELF_URL", "")
