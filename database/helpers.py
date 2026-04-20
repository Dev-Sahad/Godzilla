"""Database helper functions."""
from datetime import datetime, timedelta
from database.models import User, Download, Favorite, Log, get_session
from config import DAILY_DOWNLOAD_LIMIT_FREE, DAILY_DOWNLOAD_LIMIT_PREMIUM


def get_or_create_user(telegram_id, username=None, first_name=None, referred_by=None):
    """Get user or create new one."""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                referred_by=referred_by,
            )
            session.add(user)
            session.commit()

            # Give referrer credit
            if referred_by:
                referrer = session.query(User).filter_by(telegram_id=referred_by).first()
                if referrer:
                    referrer.referral_count += 1
                    # Give 5 bonus downloads for each referral
                    session.commit()
        else:
            # Update info if changed
            updated = False
            if username and user.username != username:
                user.username = username
                updated = True
            if first_name and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if updated:
                session.commit()

        session.refresh(user)
        # Detach for safe use outside session
        session.expunge(user)
        return user
    finally:
        session.close()


def check_download_limit(telegram_id):
    """Check if user can download. Returns (can_download, used, limit)."""
    from config import REFERRAL_BONUS
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return True, 0, DAILY_DOWNLOAD_LIMIT_FREE

        # Auto-expire premium if past expiry date
        if user.is_premium and user.subscription_expires_at:
            if datetime.utcnow() > user.subscription_expires_at:
                user.is_premium = False
                session.commit()

        # Reset daily counter if it's a new day
        if user.last_reset.date() < datetime.utcnow().date():
            user.downloads_today = 0
            user.last_reset = datetime.utcnow()
            session.commit()

        limit = DAILY_DOWNLOAD_LIMIT_PREMIUM if user.is_premium else DAILY_DOWNLOAD_LIMIT_FREE
        # Bonus for referrals (applies to free users only; premium has enough already)
        if not user.is_premium:
            limit += user.referral_count * REFERRAL_BONUS

        # Admin-set custom limit overrides everything
        if getattr(user, "custom_limit", None) is not None:
            limit = user.custom_limit

        return user.downloads_today < limit, user.downloads_today, limit
    finally:
        session.close()


def record_download(telegram_id, url, title, platform, media_type, quality, file_size, status, error=None):
    """Record a download in the database."""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return

        download = Download(
            user_id=user.id,
            url=url,
            title=title[:500] if title else "Unknown",
            platform=platform,
            media_type=media_type,
            quality=quality,
            file_size=file_size,
            status=status,
            error_msg=error[:1000] if error else None,
        )
        session.add(download)

        if status == "success":
            user.downloads_today += 1
            user.total_downloads += 1

        session.commit()
    finally:
        session.close()


def is_banned(telegram_id):
    """Check if user is banned."""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        return user and user.is_banned
    finally:
        session.close()


def ban_user(telegram_id):
    """Ban a user."""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            user.is_banned = True
            session.commit()
            return True
        return False
    finally:
        session.close()


def unban_user(telegram_id):
    """Unban a user."""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            user.is_banned = False
            session.commit()
            return True
        return False
    finally:
        session.close()


def get_user_history(telegram_id, limit=10):
    """Get user's recent downloads."""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return []
        downloads = (
            session.query(Download)
            .filter_by(user_id=user.id, status="success")
            .order_by(Download.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "title": d.title,
                "url": d.url,
                "platform": d.platform,
                "media_type": d.media_type,
                "created_at": d.created_at,
            }
            for d in downloads
        ]
    finally:
        session.close()


def add_favorite(telegram_id, url, title):
    """Add a favorite."""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return False

        # Check duplicate
        existing = session.query(Favorite).filter_by(user_id=user.id, url=url).first()
        if existing:
            return False

        fav = Favorite(user_id=user.id, url=url, title=title[:500])
        session.add(fav)
        session.commit()
        return True
    finally:
        session.close()


def get_favorites(telegram_id):
    """Get user's favorites."""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return []
        favs = session.query(Favorite).filter_by(user_id=user.id).order_by(Favorite.created_at.desc()).all()
        return [{"id": f.id, "title": f.title, "url": f.url} for f in favs]
    finally:
        session.close()


def remove_favorite(telegram_id, fav_id):
    """Remove a favorite."""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            return False
        fav = session.query(Favorite).filter_by(id=fav_id, user_id=user.id).first()
        if fav:
            session.delete(fav)
            session.commit()
            return True
        return False
    finally:
        session.close()


def get_all_users():
    """Get all user telegram IDs (for broadcast)."""
    session = get_session()
    try:
        users = session.query(User).filter_by(is_banned=False).all()
        return [u.telegram_id for u in users]
    finally:
        session.close()


def get_stats():
    """Get bot statistics."""
    session = get_session()
    try:
        total_users = session.query(User).count()
        banned_users = session.query(User).filter_by(is_banned=True).count()
        premium_users = session.query(User).filter_by(is_premium=True).count()
        total_downloads = session.query(Download).filter_by(status="success").count()

        today = datetime.utcnow().date()
        downloads_today = (
            session.query(Download)
            .filter(Download.created_at >= today, Download.status == "success")
            .count()
        )

        # Active users (downloaded in last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_users = (
            session.query(Download.user_id)
            .filter(Download.created_at >= week_ago)
            .distinct()
            .count()
        )

        return {
            "total_users": total_users,
            "banned_users": banned_users,
            "premium_users": premium_users,
            "active_users_7d": active_users,
            "total_downloads": total_downloads,
            "downloads_today": downloads_today,
        }
    finally:
        session.close()


def add_log(level, action, user_id, message):
    """Add a log entry."""
    session = get_session()
    try:
        log = Log(level=level, action=action, user_id=user_id, message=message[:5000])
        session.add(log)
        session.commit()
    finally:
        session.close()


def get_recent_logs(limit=50):
    """Get recent logs."""
    session = get_session()
    try:
        logs = session.query(Log).order_by(Log.created_at.desc()).limit(limit).all()
        return [
            {
                "level": log.level,
                "action": log.action,
                "user_id": log.user_id,
                "message": log.message,
                "created_at": log.created_at,
            }
            for log in logs
        ]
    finally:
        session.close()


def set_premium(telegram_id, status=True):
    """Set premium status."""
    session = get_session()
    try:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            user.is_premium = status
            session.commit()
            return True
        return False
    finally:
        session.close()


# ===== ADMIN MANAGEMENT (v3.4) =====

def is_super_admin(telegram_id):
    """Check if user is a super admin (from env ADMIN_IDS)."""
    from config import SUPER_ADMIN_IDS
    return int(telegram_id) in SUPER_ADMIN_IDS


def is_bot_admin(telegram_id):
    """Check if user is any kind of admin (super OR sub-admin)."""
    from config import SUPER_ADMIN_IDS
    from database.models import BotAdmin

    if int(telegram_id) in SUPER_ADMIN_IDS:
        return True

    session = get_session()
    try:
        return session.query(BotAdmin).filter_by(telegram_id=telegram_id).first() is not None
    finally:
        session.close()


def get_all_admin_ids():
    """Get list of ALL admin telegram IDs (super + sub)."""
    from config import SUPER_ADMIN_IDS
    from database.models import BotAdmin

    admins = set(SUPER_ADMIN_IDS)
    session = get_session()
    try:
        subs = session.query(BotAdmin).all()
        for s in subs:
            admins.add(int(s.telegram_id))
    except Exception:
        pass
    finally:
        session.close()
    return list(admins)


def add_sub_admin(telegram_id, username, first_name, promoted_by, notes=""):
    """Add a sub-admin. Returns (success, message)."""
    from database.models import BotAdmin
    from config import SUPER_ADMIN_IDS

    if int(telegram_id) in SUPER_ADMIN_IDS:
        return False, "User is already a super admin."

    session = get_session()
    try:
        existing = session.query(BotAdmin).filter_by(telegram_id=telegram_id).first()
        if existing:
            return False, "User is already a sub-admin."

        admin = BotAdmin(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            promoted_by=promoted_by,
            notes=notes,
        )
        session.add(admin)
        session.commit()
        return True, "Sub-admin added successfully."
    except Exception as e:
        session.rollback()
        return False, f"Error: {e}"
    finally:
        session.close()


def remove_sub_admin(telegram_id):
    """Remove a sub-admin. Returns (success, message)."""
    from database.models import BotAdmin

    session = get_session()
    try:
        admin = session.query(BotAdmin).filter_by(telegram_id=telegram_id).first()
        if not admin:
            return False, "User is not a sub-admin."
        session.delete(admin)
        session.commit()
        return True, "Sub-admin removed."
    except Exception as e:
        session.rollback()
        return False, f"Error: {e}"
    finally:
        session.close()


def list_sub_admins():
    """Get list of all sub-admins."""
    from database.models import BotAdmin

    session = get_session()
    try:
        return session.query(BotAdmin).order_by(BotAdmin.created_at.desc()).all()
    finally:
        session.close()
