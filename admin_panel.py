"""
GODZILLA Admin Web Panel
Full control panel: plans, users, payments, stats, broadcast, logs, settings.
"""
import os
import asyncio
import logging
from datetime import datetime, timedelta
from functools import wraps
from flask import (
    Flask, request, render_template, redirect, url_for,
    session, flash, jsonify
)
import bcrypt

from config import FLASK_SECRET_KEY
from database.models import (
    get_session, User, Download, Payment, SubscriptionPlan,
    AdminUser, Log, BroadcastHistory, Settings
)
from utils.payments import verify_webhook_signature, activate_premium, mark_payment_paid

logger = logging.getLogger(__name__)

# Flask app — single app for webhook + admin panel
app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
app.secret_key = FLASK_SECRET_KEY

# Reference to the bot application (set from bot.py)
_bot_app = None


def set_bot_app(bot_app):
    """Set bot reference for sending messages from web."""
    global _bot_app
    _bot_app = bot_app


# ===== DECORATORS =====

def login_required(f):
    """Require admin login for a route."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


# ===== PUBLIC ROUTES =====

@app.route("/")
def index():
    """Redirect to login or dashboard."""
    if "admin_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "godzilla-admin-panel"})


# ===== AUTH ROUTES =====

@app.route("/login", methods=["GET", "POST"])
def login():
    """Admin login page."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_session()
        try:
            admin = db.query(AdminUser).filter_by(username=username).first()
            if admin and bcrypt.checkpw(password.encode(), admin.password_hash.encode()):
                session["admin_id"] = admin.id
                session["admin_username"] = admin.username
                session["is_superadmin"] = admin.is_superadmin
                admin.last_login = datetime.utcnow()
                db.commit()

                next_url = request.args.get("next") or url_for("dashboard")
                return redirect(next_url)
            else:
                flash("Invalid credentials", "danger")
        finally:
            db.close()

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ===== DASHBOARD =====

@app.route("/admin/dashboard")
@login_required
def dashboard():
    """Main dashboard with stats."""
    db = get_session()
    try:
        today = datetime.utcnow().date()
        week_ago = datetime.utcnow() - timedelta(days=7)

        total_users = db.query(User).count()
        active_today = db.query(Download).filter(Download.created_at >= today).distinct(Download.user_id).count()
        premium_users = db.query(User).filter_by(is_premium=True).count()
        total_downloads = db.query(Download).filter_by(status="success").count()
        downloads_today = db.query(Download).filter(Download.created_at >= today, Download.status == "success").count()

        # Revenue
        paid_payments = db.query(Payment).filter_by(status="paid").all()
        total_revenue = sum(p.amount for p in paid_payments) / 100  # paise → rupees
        revenue_today = sum(
            p.amount for p in paid_payments
            if p.paid_at and p.paid_at.date() == today
        ) / 100

        # Recent activity
        recent_downloads = (
            db.query(Download, User)
            .join(User)
            .order_by(Download.created_at.desc())
            .limit(10)
            .all()
        )

        # Recent users
        recent_users = db.query(User).order_by(User.joined_at.desc()).limit(10).all()

        stats = {
            "total_users": total_users,
            "active_today": active_today,
            "premium_users": premium_users,
            "total_downloads": total_downloads,
            "downloads_today": downloads_today,
            "total_revenue": total_revenue,
            "revenue_today": revenue_today,
            "recent_downloads": recent_downloads,
            "recent_users": recent_users,
        }
        return render_template("dashboard.html", stats=stats)
    finally:
        db.close()


# ===== PLANS MANAGEMENT =====

@app.route("/admin/plans")
@login_required
def plans_list():
    """List all subscription plans."""
    db = get_session()
    try:
        plans = db.query(SubscriptionPlan).order_by(SubscriptionPlan.sort_order).all()
        return render_template("plans.html", plans=plans)
    finally:
        db.close()


@app.route("/admin/plans/new", methods=["GET", "POST"])
@login_required
def plan_new():
    """Create a new plan."""
    if request.method == "POST":
        db = get_session()
        try:
            plan = SubscriptionPlan(
                key=request.form["key"].strip(),
                name=request.form["name"].strip(),
                category=request.form.get("category", "premium").strip(),
                amount=int(request.form["amount"]),
                duration_days=int(request.form["duration_days"]),
                daily_limit=int(request.form["daily_limit"]),
                description=request.form.get("description", ""),
                badge=request.form.get("badge", "").strip(),
                is_active=request.form.get("is_active") == "on",
                sort_order=int(request.form.get("sort_order", 0)),
            )
            db.add(plan)
            db.commit()
            flash(f"Plan '{plan.name}' created!", "success")
            return redirect(url_for("plans_list"))
        except Exception as e:
            flash(f"Error: {e}", "danger")
        finally:
            db.close()

    return render_template("plan_form.html", plan=None)


@app.route("/admin/plans/<int:plan_id>/edit", methods=["GET", "POST"])
@login_required
def plan_edit(plan_id):
    """Edit an existing plan."""
    db = get_session()
    try:
        plan = db.query(SubscriptionPlan).get(plan_id)
        if not plan:
            flash("Plan not found", "danger")
            return redirect(url_for("plans_list"))

        if request.method == "POST":
            plan.key = request.form["key"].strip()
            plan.name = request.form["name"].strip()
            plan.category = request.form.get("category", "premium").strip()
            plan.amount = int(request.form["amount"])
            plan.duration_days = int(request.form["duration_days"])
            plan.daily_limit = int(request.form["daily_limit"])
            plan.description = request.form.get("description", "")
            plan.badge = request.form.get("badge", "").strip()
            plan.is_active = request.form.get("is_active") == "on"
            plan.sort_order = int(request.form.get("sort_order", 0))
            db.commit()
            flash(f"Plan '{plan.name}' updated!", "success")
            return redirect(url_for("plans_list"))

        return render_template("plan_form.html", plan=plan)
    finally:
        db.close()


@app.route("/admin/plans/<int:plan_id>/delete", methods=["POST"])
@login_required
def plan_delete(plan_id):
    """Delete a plan."""
    db = get_session()
    try:
        plan = db.query(SubscriptionPlan).get(plan_id)
        if plan:
            db.delete(plan)
            db.commit()
            flash(f"Plan deleted", "success")
    finally:
        db.close()
    return redirect(url_for("plans_list"))


# ===== USERS MANAGEMENT =====

@app.route("/admin/users")
@login_required
def users_list():
    """List all users with search."""
    q = request.args.get("q", "").strip()
    filter_type = request.args.get("filter", "all")
    page = int(request.args.get("page", 1))
    per_page = 50

    db = get_session()
    try:
        query = db.query(User)

        if q:
            query = query.filter(
                (User.username.ilike(f"%{q}%")) |
                (User.first_name.ilike(f"%{q}%")) |
                (User.telegram_id == (int(q) if q.isdigit() else 0))
            )

        if filter_type == "premium":
            query = query.filter_by(is_premium=True)
        elif filter_type == "banned":
            query = query.filter_by(is_banned=True)
        elif filter_type == "free":
            query = query.filter_by(is_premium=False, is_banned=False)

        total = query.count()
        users = (
            query.order_by(User.joined_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return render_template(
            "users.html",
            users=users, q=q, filter_type=filter_type,
            page=page, total=total, per_page=per_page,
        )
    finally:
        db.close()


@app.route("/admin/users/<int:user_id>")
@login_required
def user_detail(user_id):
    """View a user's details."""
    db = get_session()
    try:
        user = db.query(User).get(user_id)
        if not user:
            flash("User not found", "danger")
            return redirect(url_for("users_list"))

        downloads = (
            db.query(Download).filter_by(user_id=user.id)
            .order_by(Download.created_at.desc()).limit(20).all()
        )
        payments = (
            db.query(Payment).filter_by(user_id=user.id)
            .order_by(Payment.created_at.desc()).all()
        )
        return render_template("user_detail.html", user=user, downloads=downloads, payments=payments)
    finally:
        db.close()


@app.route("/admin/users/<int:user_id>/action", methods=["POST"])
@login_required
def user_action(user_id):
    """Ban/unban/premium actions."""
    action = request.form.get("action")
    db = get_session()
    try:
        user = db.query(User).get(user_id)
        if not user:
            flash("User not found", "danger")
            return redirect(url_for("users_list"))

        if action == "ban":
            user.is_banned = True
            flash(f"User banned", "success")
        elif action == "unban":
            user.is_banned = False
            flash(f"User unbanned", "success")
        elif action == "grant_premium":
            days = int(request.form.get("days", 30))
            now = datetime.utcnow()
            base = user.subscription_expires_at if (
                user.subscription_expires_at and user.subscription_expires_at > now
            ) else now
            user.is_premium = True
            user.subscription_expires_at = base + timedelta(days=days)
            user.subscription_plan = "manual"
            flash(f"Granted {days} days premium", "success")
        elif action == "revoke_premium":
            user.is_premium = False
            user.subscription_expires_at = None
            flash("Premium revoked", "success")

        db.commit()
    finally:
        db.close()
    return redirect(url_for("user_detail", user_id=user_id))


# ===== PAYMENTS =====

@app.route("/admin/payments")
@login_required
def payments_list():
    """List all payments."""
    status = request.args.get("status", "all")
    page = int(request.args.get("page", 1))
    per_page = 50

    db = get_session()
    try:
        query = db.query(Payment, User).join(User)
        if status != "all":
            query = query.filter(Payment.status == status)

        total = query.count()
        payments = (
            query.order_by(Payment.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return render_template(
            "payments.html",
            payments=payments, status=status,
            page=page, total=total, per_page=per_page,
        )
    finally:
        db.close()


# ===== BROADCAST =====

@app.route("/admin/broadcast", methods=["GET", "POST"])
@login_required
def broadcast():
    """Send broadcast message to all users via bot."""
    if request.method == "POST":
        message = request.form.get("message", "").strip()
        target = request.form.get("target", "all")

        if not message:
            flash("Message cannot be empty", "danger")
            return redirect(url_for("broadcast"))

        if not _bot_app:
            flash("Bot not available", "danger")
            return redirect(url_for("broadcast"))

        # Get targets
        db = get_session()
        try:
            query = db.query(User).filter_by(is_banned=False)
            if target == "premium":
                query = query.filter_by(is_premium=True)
            elif target == "free":
                query = query.filter_by(is_premium=False)
            user_ids = [u.telegram_id for u in query.all()]
        finally:
            db.close()

        # Send async via bot
        sent, failed = _send_broadcast(message, user_ids)

        # Record
        db = get_session()
        try:
            bh = BroadcastHistory(
                admin_id=session.get("admin_id"),
                message=message,
                sent_to=sent,
                failed=failed,
            )
            db.add(bh)
            db.commit()
        finally:
            db.close()

        flash(f"Broadcast sent to {sent} users ({failed} failed)", "success")
        return redirect(url_for("broadcast"))

    # Recent broadcasts
    db = get_session()
    try:
        recent = db.query(BroadcastHistory).order_by(BroadcastHistory.created_at.desc()).limit(10).all()
        return render_template("broadcast.html", recent=recent)
    finally:
        db.close()


def _send_broadcast(message, user_ids):
    """Send message to multiple users via bot (sync call from Flask)."""
    if not _bot_app:
        return 0, len(user_ids)

    # Get the bot's event loop (stored by bot.py at startup)
    bot_loop = _bot_app.bot_data.get("event_loop") if hasattr(_bot_app, "bot_data") else None

    async def _send():
        s, f = 0, 0
        for uid in user_ids:
            try:
                await _bot_app.bot.send_message(
                    chat_id=uid,
                    text=f"📢 *Announcement*\n\n{message}\n\n_— GODZILLA Team_",
                    parse_mode="Markdown",
                )
                s += 1
                await asyncio.sleep(0.05)  # rate limit
            except Exception as e:
                logger.error(f"Broadcast to {uid} failed: {e}")
                f += 1
        return s, f

    try:
        if bot_loop and bot_loop.is_running():
            # Use the bot's running loop (thread-safe)
            future = asyncio.run_coroutine_threadsafe(_send(), bot_loop)
            return future.result(timeout=300)
        else:
            # Fallback: create new loop
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_send())
            finally:
                loop.close()
    except Exception as e:
        logger.error(f"Broadcast error: {e}")
        return 0, len(user_ids)


# ===== LOGS =====

@app.route("/admin/logs")
@login_required
def logs_list():
    """View recent logs."""
    page = int(request.args.get("page", 1))
    per_page = 100
    level = request.args.get("level", "all")

    db = get_session()
    try:
        query = db.query(Log)
        if level != "all":
            query = query.filter(Log.level == level.upper())

        total = query.count()
        logs = (
            query.order_by(Log.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return render_template(
            "logs.html",
            logs=logs, level=level,
            page=page, total=total, per_page=per_page,
        )
    finally:
        db.close()


# ===== SETTINGS =====

@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    """Bot settings (key-value store)."""
    db = get_session()
    try:
        if request.method == "POST":
            for key, value in request.form.items():
                if key.startswith("setting_"):
                    actual_key = key[8:]
                    existing = db.query(Settings).filter_by(key=actual_key).first()
                    if existing:
                        existing.value = value
                    else:
                        db.add(Settings(key=actual_key, value=value))
            db.commit()
            flash("Settings saved!", "success")
            return redirect(url_for("settings_page"))

        settings_rows = db.query(Settings).all()
        settings_dict = {s.key: s.value for s in settings_rows}
        return render_template("settings.html", settings=settings_dict)
    finally:
        db.close()


@app.route("/admin/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Change admin password."""
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        if new != confirm:
            flash("New passwords don't match", "danger")
            return redirect(url_for("change_password"))

        if len(new) < 6:
            flash("Password must be at least 6 characters", "danger")
            return redirect(url_for("change_password"))

        db = get_session()
        try:
            admin = db.query(AdminUser).get(session["admin_id"])
            if not bcrypt.checkpw(current.encode(), admin.password_hash.encode()):
                flash("Current password is wrong", "danger")
                return redirect(url_for("change_password"))

            admin.password_hash = bcrypt.hashpw(new.encode(), bcrypt.gensalt()).decode()
            db.commit()
            flash("Password changed!", "success")
            return redirect(url_for("dashboard"))
        finally:
            db.close()

    return render_template("change_password.html")


# ===== ANALYTICS =====

@app.route("/admin/analytics")
@login_required
def analytics():
    """Analytics dashboard with charts."""
    db = get_session()
    try:
        from sqlalchemy import func, text

        # Last 7 days downloads
        week_downloads = []
        for i in range(6, -1, -1):
            day = datetime.utcnow().date() - timedelta(days=i)
            count = db.query(Download).filter(
                func.date(Download.created_at) == day
            ).count()
            week_downloads.append({"date": day.strftime("%b %d"), "count": count})

        # Platform breakdown
        platform_stats = {}
        rows = db.query(Download.platform, func.count(Download.id)).group_by(Download.platform).all()
        for platform, count in rows:
            if platform:
                platform_stats[platform] = count

        # User growth (last 30 days)
        growth = []
        for i in range(29, -1, -1):
            day = datetime.utcnow().date() - timedelta(days=i)
            count = db.query(User).filter(func.date(User.created_at) == day).count()
            growth.append({"date": day.strftime("%b %d"), "count": count})

        # Top users by downloads
        top_users_raw = (
            db.query(User, func.count(Download.id).label("dl_count"))
            .join(Download)
            .group_by(User.id)
            .order_by(text("dl_count DESC"))
            .limit(10)
            .all()
        )
        top_users = [{"user": u, "count": c} for u, c in top_users_raw]

        # Revenue (from approved payment requests)
        try:
            from database.models import PaymentRequest
            total_revenue = db.query(func.sum(PaymentRequest.amount)).filter(
                PaymentRequest.status == "approved"
            ).scalar() or 0
        except Exception:
            total_revenue = 0

        # Success rate
        total_dls = db.query(Download).count()
        success_dls = db.query(Download).filter_by(status="success").count()
        success_rate = round((success_dls / total_dls * 100) if total_dls else 0, 1)

        stats = {
            "week_downloads": week_downloads,
            "platform_stats": platform_stats,
            "growth": growth,
            "top_users": top_users,
            "total_revenue": total_revenue,
            "success_rate": success_rate,
            "total_downloads": total_dls,
        }
        return render_template("analytics.html", stats=stats)
    finally:
        db.close()


# ===== REFERRALS =====

@app.route("/admin/referrals")
@login_required
def referrals():
    """Referral program overview."""
    db = get_session()
    try:
        from sqlalchemy import func, desc

        # Top referrers
        top_referrers = (
            db.query(User)
            .filter(User.referral_count > 0)
            .order_by(desc(User.referral_count))
            .limit(50)
            .all()
        )

        # Recent referrals
        recent_refs = (
            db.query(User)
            .filter(User.referred_by.isnot(None))
            .order_by(desc(User.created_at))
            .limit(30)
            .all()
        )

        total_referrals = db.query(User).filter(User.referred_by.isnot(None)).count()
        total_referrers = db.query(User).filter(User.referral_count > 0).count()

        return render_template(
            "referrals.html",
            top_referrers=top_referrers,
            recent_refs=recent_refs,
            total_referrals=total_referrals,
            total_referrers=total_referrers,
        )
    finally:
        db.close()


# ===== ACTIVITY FEED =====

@app.route("/admin/activity")
@login_required
def activity():
    """Real-time activity feed: users, downloads, logins."""
    db = get_session()
    try:
        recent_users = db.query(User).order_by(User.created_at.desc()).limit(20).all()
        recent_downloads = db.query(Download).order_by(Download.created_at.desc()).limit(30).all()
        recent_logs = db.query(Log).order_by(Log.created_at.desc()).limit(20).all()

        return render_template(
            "activity.html",
            recent_users=recent_users,
            recent_downloads=recent_downloads,
            recent_logs=recent_logs,
        )
    finally:
        db.close()


# ===== PAYMENT REQUESTS (UPI) =====

@app.route("/admin/payment-requests")
@login_required
def payment_requests():
    """Manage UPI payment requests from web."""
    try:
        from database.models import PaymentRequest
    except ImportError:
        flash("PaymentRequest model not available", "warning")
        return redirect(url_for("dashboard"))

    status_filter = request.args.get("status", "pending")
    db = get_session()
    try:
        query = db.query(PaymentRequest)
        if status_filter != "all":
            query = query.filter_by(status=status_filter)

        requests_list = query.order_by(PaymentRequest.created_at.desc()).limit(100).all()

        counts = {
            "pending": db.query(PaymentRequest).filter_by(status="pending").count(),
            "approved": db.query(PaymentRequest).filter_by(status="approved").count(),
            "rejected": db.query(PaymentRequest).filter_by(status="rejected").count(),
        }

        return render_template(
            "payment_requests.html",
            requests=requests_list,
            counts=counts,
            status_filter=status_filter,
        )
    finally:
        db.close()


@app.route("/admin/payment-requests/<int:req_id>/<action>", methods=["POST"])
@login_required
def payment_request_action(req_id, action):
    """Approve or reject a payment request from web."""
    from database.models import PaymentRequest
    from utils.payments import activate_premium

    if action not in ("approve", "reject"):
        flash("Invalid action", "danger")
        return redirect(url_for("payment_requests"))

    db = get_session()
    try:
        req = db.query(PaymentRequest).get(req_id)
        if not req:
            flash("Request not found", "danger")
            return redirect(url_for("payment_requests"))

        if req.status != "pending":
            flash(f"Already {req.status}", "warning")
            return redirect(url_for("payment_requests"))

        admin_id = session.get("admin_id")

        if action == "approve":
            if activate_premium(req.telegram_id, req.plan_key):
                req.status = "approved"
                req.admin_id = admin_id
                req.processed_at = datetime.utcnow()
                db.commit()
                flash(f"✅ Approved #{req_id}", "success")

                # Notify user via bot
                if _bot_app:
                    _notify_user_approved(req.telegram_id, req.plan_key)
            else:
                flash("Failed to activate premium", "danger")
        else:
            req.status = "rejected"
            req.admin_id = admin_id
            req.processed_at = datetime.utcnow()
            db.commit()
            flash(f"❌ Rejected #{req_id}", "warning")

            if _bot_app:
                _notify_user_rejected(req.telegram_id, req_id)
    finally:
        db.close()

    return redirect(url_for("payment_requests"))


def _notify_user_approved(telegram_id, plan_key):
    """Notify user their payment was approved (thread-safe)."""
    bot_loop = _bot_app.bot_data.get("event_loop") if hasattr(_bot_app, "bot_data") else None

    async def _send():
        try:
            from utils.payments import get_plan
            plan = get_plan(plan_key) or {}
            await _bot_app.bot.send_message(
                chat_id=telegram_id,
                text=(
                    "🎉 *Payment Approved!*\n\n"
                    f"✨ *{plan.get('name', 'Premium')}* activated!\n"
                    f"📥 Daily Limit: {plan.get('daily_limit', 100)} downloads\n"
                    f"📅 Duration: {plan.get('duration_days', 30)} days\n\n"
                    "Use /myplan to check status.\n\n"
                    "_Thank you for supporting GODZILLA! 🦖_"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Notify approve error: {e}")

    try:
        if bot_loop and bot_loop.is_running():
            asyncio.run_coroutine_threadsafe(_send(), bot_loop)
    except Exception as e:
        logger.error(f"Bot notify error: {e}")


def _notify_user_rejected(telegram_id, req_id):
    """Notify user their payment was rejected."""
    bot_loop = _bot_app.bot_data.get("event_loop") if hasattr(_bot_app, "bot_data") else None

    async def _send():
        try:
            await _bot_app.bot.send_message(
                chat_id=telegram_id,
                text=(
                    f"❌ *Payment Rejected* — Request `#{req_id}`\n\n"
                    "Possible reasons: wrong UTR, amount mismatch, duplicate.\n"
                    "Contact admin if this is a mistake."
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Notify reject error: {e}")

    try:
        if bot_loop and bot_loop.is_running():
            asyncio.run_coroutine_threadsafe(_send(), bot_loop)
    except Exception as e:
        logger.error(f"Bot notify error: {e}")


# ===== SET USER LIMIT (from user detail page) =====

@app.route("/admin/users/<int:user_id>/set-limit", methods=["POST"])
@login_required
def user_set_limit(user_id):
    """Set a user's custom daily download limit."""
    limit_value = request.form.get("custom_limit", "").strip()
    db = get_session()
    try:
        user = db.query(User).get(user_id)
        if not user:
            flash("User not found", "danger")
            return redirect(url_for("users_list"))

        if limit_value.lower() in ("", "reset", "none"):
            user.custom_limit = None
            flash(f"Limit reset for {user.first_name}", "success")
        else:
            try:
                new_limit = int(limit_value)
                if 0 <= new_limit <= 10000:
                    user.custom_limit = new_limit
                    flash(f"Limit set to {new_limit}/day for {user.first_name}", "success")
                else:
                    flash("Limit must be 0-10000", "danger")
            except ValueError:
                flash("Invalid number", "danger")

        db.commit()
    finally:
        db.close()
    return redirect(url_for("user_detail", user_id=user_id))


# ===== RAZORPAY WEBHOOK (unchanged logic) =====

@app.route("/webhook/razorpay", methods=["POST"])
def razorpay_webhook():
    """Receive Razorpay payment events."""
    signature = request.headers.get("X-Razorpay-Signature", "")
    payload = request.get_data()

    if not verify_webhook_signature(payload, signature):
        logger.warning("⚠️ Invalid webhook signature!")
        return jsonify({"error": "invalid signature"}), 400

    try:
        data = request.json
        event = data.get("event", "")
        logger.info(f"📨 Razorpay webhook: {event}")

        if event in ("payment.captured", "payment_link.paid"):
            payload_data = data.get("payload", {})

            if event == "payment.captured":
                payment = payload_data.get("payment", {}).get("entity", {})
                order_id = payment.get("order_id")
                payment_id = payment.get("id")
                notes = payment.get("notes", {})
            else:
                payment_link = payload_data.get("payment_link", {}).get("entity", {})
                payment = payload_data.get("payment", {}).get("entity", {})
                order_id = payment.get("order_id") or payment_link.get("order_id")
                payment_id = payment.get("id")
                notes = payment_link.get("notes", {})

            telegram_id = int(notes.get("telegram_id", 0))
            plan = notes.get("plan", "monthly")

            if not telegram_id:
                return jsonify({"error": "no user"}), 400

            mark_payment_paid(order_id, payment_id)

            if activate_premium(telegram_id, plan):
                logger.info(f"✅ Premium activated for {telegram_id}")
                if _bot_app:
                    from handlers.subscription_commands import send_success_message
                    try:
                        asyncio.run_coroutine_threadsafe(
                            send_success_message(_bot_app.bot, telegram_id, plan),
                            _bot_app.loop if hasattr(_bot_app, "loop") else asyncio.get_event_loop(),
                        )
                    except Exception as e:
                        logger.error(f"Failed to send success msg: {e}")
                return jsonify({"status": "ok"}), 200
            return jsonify({"error": "activation failed"}), 500

        return jsonify({"status": "ignored"}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return jsonify({"error": "server error"}), 500


# ===== RUN SERVER =====

def run_server(port=8080):
    """Run the combined webhook + admin panel server."""
    logger.info(f"🌐 Admin panel + webhook server starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


def start_server_in_thread(port=None):
    """Start server in background thread."""
    import threading
    port = port or int(os.getenv("PORT", "8080"))
    thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    thread.start()
    return thread
