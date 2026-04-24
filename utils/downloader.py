"""
Download engine using yt-dlp with robust timeout + retry handling.

Key improvements:
- 120s timeout per download (prevents infinite hangs)
- Automatic retry on network errors (3 attempts)
- Better headers (bypass Instagram/TikTok rate limits)
- Smaller file size limit (40MB) to finish faster
- Progress logging for debugging
"""
import os
import asyncio
import logging
import yt_dlp
from urllib.parse import urlparse
from config import DOWNLOAD_DIR, QUALITY_OPTIONS

logger = logging.getLogger(__name__)

# ============ TIMEOUT CONFIGURATION ============
DOWNLOAD_TIMEOUT = 120           # 2 min total per download attempt
SOCKET_TIMEOUT = 30              # 30s per HTTP request
MAX_RETRIES = 3                  # retry 3x on network errors
MAX_FILESIZE_MB = 40             # keep files small for faster upload to Telegram

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


def _get_base_opts(user_id, is_audio=False):
    """Base yt-dlp options with robust network handling."""
    output_path = f"{DOWNLOAD_DIR}/{user_id}_%(id)s.%(ext)s"

    opts = {
        "outtmpl": output_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # ============ TIMEOUT & RETRY ============
        "socket_timeout": SOCKET_TIMEOUT,
        "retries": MAX_RETRIES,
        "fragment_retries": MAX_RETRIES,
        "file_access_retries": 2,
        "extractor_retries": 2,
        # ============ NETWORK HEADERS ============
        # Instagram/TikTok block default yt-dlp user agent
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
        # ============ PLATFORM-SPECIFIC ============
        # Skip dash/hls manifests that often hang
        "prefer_ffmpeg": True,
        "keepvideo": False,
        # Don't include subtitles (speeds up downloads significantly)
        "writesubtitles": False,
        "writeautomaticsub": False,
        # Skip embeds that hang
        "embed_subs": False,
        "embed_thumbnail": False,
    }

    if is_audio:
        opts["format"] = f"bestaudio[filesize<{MAX_FILESIZE_MB}M]/bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

    return opts


def _download_sync(ydl_opts, url, is_audio=False):
    """Synchronous download — runs in executor."""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Starting download: {url}")
            info = ydl.extract_info(url, download=True)

            # Handle playlists
            if "entries" in info:
                if not info["entries"]:
                    raise Exception("No content found in URL")
                info = info["entries"][0]

            title = info.get("title", "Unknown")[:100]
            filename = ydl.prepare_filename(info)

            if is_audio:
                filename = os.path.splitext(filename)[0] + ".mp3"

            if not os.path.exists(filename):
                raise FileNotFoundError(f"Downloaded file missing: {filename}")

            size_mb = os.path.getsize(filename) / (1024 * 1024)
            logger.info(f"✅ Downloaded: {title} ({size_mb:.1f}MB)")

            return filename, title
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if "private" in msg:
            raise Exception("This content is private. Bot can only download public posts.")
        if "unavailable" in msg or "removed" in msg:
            raise Exception("Content has been removed or is unavailable.")
        if "login" in msg or "sign in" in msg:
            raise Exception("This platform requires login for this content. Try a public post.")
        if "429" in msg or "rate" in msg:
            raise Exception("Platform rate-limited us. Try again in 1-2 minutes.")
        raise Exception(f"Download error: {str(e)[:100]}")
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        raise


async def _run_with_timeout(coro_fn, url_for_log="unknown"):
    """Run sync function with timeout guard."""
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, coro_fn),
            timeout=DOWNLOAD_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning(f"⏱ Download timeout after {DOWNLOAD_TIMEOUT}s for: {url_for_log}")
        raise Exception(
            f"Download took too long (>{DOWNLOAD_TIMEOUT}s). "
            "The video might be too large or the source is slow. "
            "Try: (1) a shorter video, (2) audio-only, or (3) wait and retry."
        )


async def download_video(url, user_id, quality="720p"):
    """Download video with quality selection."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    format_str = QUALITY_OPTIONS.get(quality, QUALITY_OPTIONS.get("720p", "best[height<=720]"))

    ydl_opts = _get_base_opts(user_id, is_audio=False)
    ydl_opts["format"] = (
        f"{format_str}[filesize<{MAX_FILESIZE_MB}M]/"
        f"{format_str}/"
        f"best[filesize<{MAX_FILESIZE_MB}M]/best"
    )
    ydl_opts["merge_output_format"] = "mp4"

    return await _run_with_timeout(
        lambda: _download_sync(ydl_opts, url, is_audio=False),
        url_for_log=url,
    )


async def download_audio(url, user_id):
    """Download audio as MP3."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    ydl_opts = _get_base_opts(user_id, is_audio=True)

    return await _run_with_timeout(
        lambda: _download_sync(ydl_opts, url, is_audio=True),
        url_for_log=url,
    )


async def download_thumbnail(url, user_id):
    """Download video thumbnail only (fast, no video data)."""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    output_path = f"{DOWNLOAD_DIR}/{user_id}_thumb_%(id)s.%(ext)s"

    ydl_opts = {
        "skip_download": True,
        "writethumbnail": True,
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "retries": 2,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
    }

    def _sync():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if "entries" in info:
                info = info["entries"][0]
            title = info.get("title", "Unknown")
            thumbnails = info.get("thumbnails", [])
            if thumbnails:
                # yt-dlp saves the thumbnail; find it
                import glob
                matches = glob.glob(f"{DOWNLOAD_DIR}/{user_id}_thumb_*")
                if matches:
                    return matches[0], title
            raise Exception("No thumbnail available")

    return await _run_with_timeout(_sync, url_for_log=url)


async def get_info(url):
    """Get video metadata without downloading (fast)."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 15,
        "retries": 1,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        },
    }

    def _sync():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return {
                "title": info.get("title", "Unknown"),
                "duration": info.get("duration", 0),
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader", "Unknown"),
                "view_count": info.get("view_count", 0),
            }

    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, _sync),
            timeout=30,
        )
    except asyncio.TimeoutError:
        raise Exception("Metadata fetch timed out. Try again.")


def cleanup_file(filepath):
    """Delete a file after sending."""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        logger.warning(f"Cleanup failed for {filepath}: {e}")
