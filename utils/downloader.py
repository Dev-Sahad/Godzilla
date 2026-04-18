"""Download engine using yt-dlp."""
import os
import asyncio
import yt_dlp
from urllib.parse import urlparse
from config import DOWNLOAD_DIR, QUALITY_OPTIONS

PLATFORM_MAP = {
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "instagram.com": "Instagram",
    "tiktok.com": "TikTok",
    "twitter.com": "Twitter",
    "x.com": "Twitter",
    "facebook.com": "Facebook",
    "fb.watch": "Facebook",
    "pinterest.com": "Pinterest",
    "reddit.com": "Reddit",
    "soundcloud.com": "SoundCloud",
}


def detect_platform(url: str) -> str:
    """Detect platform from URL."""
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        for key, value in PLATFORM_MAP.items():
            if key in domain:
                return value
        return "Unknown"
    except Exception:
        return "Unknown"


def is_valid_url(url: str) -> bool:
    """Check if URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def _download_sync(ydl_opts, url, is_audio=False):
    """Synchronous download."""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        # Handle playlists — take first entry
        if "entries" in info:
            info = info["entries"][0]

        title = info.get("title", "Unknown")
        filename = ydl.prepare_filename(info)
        if is_audio:
            filename = os.path.splitext(filename)[0] + ".mp3"
        return filename, title


async def download_video(url, user_id, quality="720p"):
    """Download video with quality selection."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    output_path = f"{DOWNLOAD_DIR}/{user_id}_%(id)s.%(ext)s"

    format_str = QUALITY_OPTIONS.get(quality, QUALITY_OPTIONS["720p"])

    ydl_opts = {
        "format": f"{format_str}[filesize<50M]/{format_str}/best",
        "outtmpl": output_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _download_sync(ydl_opts, url))


async def download_audio(url, user_id):
    """Download audio as MP3."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    output_path = f"{DOWNLOAD_DIR}/{user_id}_%(id)s.%(ext)s"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _download_sync(ydl_opts, url, is_audio=True))


async def download_thumbnail(url, user_id):
    """Download video thumbnail only."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    output_path = f"{DOWNLOAD_DIR}/{user_id}_thumb_%(id)s.%(ext)s"

    ydl_opts = {
        "skip_download": True,
        "writethumbnail": True,
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
    }

    def _get_thumb():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "Unknown")
            base = ydl.prepare_filename(info)
            # Find the actual thumbnail file
            for ext in [".jpg", ".webp", ".png"]:
                thumb = os.path.splitext(base)[0] + ext
                if os.path.exists(thumb):
                    return thumb, title
            return None, title

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_thumb)


async def get_video_info(url):
    """Get video info without downloading."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return {
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", "Unknown"),
                "view_count": info.get("view_count", 0),
                "thumbnail": info.get("thumbnail"),
            }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract)


def cleanup_file(filepath):
    """Safely remove a file."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except Exception:
        pass
