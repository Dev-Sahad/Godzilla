"""
GODZILLA v3.0.0 - Database Models
Uses SQLAlchemy for PostgreSQL on Railway (falls back to SQLite locally)
"""
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, BigInteger, String, Boolean,
    DateTime, Text, ForeignKey, Float
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from config import DATABASE_URL

# Railway provides postgres:// but SQLAlchemy needs postgresql://
db_url = DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

engine = create_engine(db_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    is_banned = Column(Boolean, default=False)
    is_premium = Column(Boolean, default=False)
    subscription_expires_at = Column(DateTime, nullable=True)
    subscription_plan = Column(String(50), nullable=True)
    auto_renew = Column(Boolean, default=False)
    downloads_today = Column(Integer, default=0)
    total_downloads = Column(Integer, default=0)
    last_reset = Column(DateTime, default=datetime.utcnow)
    joined_at = Column(DateTime, default=datetime.utcnow)
    referred_by = Column(BigInteger, nullable=True)
    referral_count = Column(Integer, default=0)
    referral_reward_claimed = Column(Boolean, default=False)
    custom_limit = Column(Integer, nullable=True)

    # === PROFILE FIELDS (NEW in v3.3) ===
    bio = Column(Text, default="")                          # User's bio/about
    avatar_emoji = Column(String(10), default="🦖")         # Profile emoji
    display_name = Column(String(100), nullable=True)       # Custom display name
    badges = Column(Text, default="")                       # JSON list of earned badges
    reputation = Column(Integer, default=0)                 # Points earned
    title = Column(String(50), default="")                  # e.g. "Beta Tester", "OG"

    downloads = relationship("Download", back_populates="user", cascade="all, delete")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete")
    payments = relationship("Payment", back_populates="user", cascade="all, delete")


class Download(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    url = Column(Text, nullable=False)
    title = Column(String(500))
    platform = Column(String(50))
    media_type = Column(String(20))  # video / audio
    quality = Column(String(20))
    file_size = Column(Float)  # in MB
    status = Column(String(20))  # success / failed
    error_msg = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="downloads")


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    url = Column(Text, nullable=False)
    title = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="favorites")


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True)
    level = Column(String(10))  # INFO / WARNING / ERROR
    action = Column(String(100))
    user_id = Column(BigInteger, nullable=True)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class BroadcastHistory(Base):
    __tablename__ = "broadcasts"

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger)
    message = Column(Text)
    sent_to = Column(Integer, default=0)
    failed = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    telegram_id = Column(BigInteger, index=True)
    razorpay_order_id = Column(String(100), unique=True, index=True)
    razorpay_payment_id = Column(String(100), nullable=True)
    plan = Column(String(50))               # e.g. "monthly"
    amount = Column(Integer)                # In paise (₹49 = 4900)
    currency = Column(String(10), default="INR")
    status = Column(String(20), default="created")  # created / paid / failed
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="payments")


class SubscriptionPlan(Base):
    """Subscription plans — editable from admin web panel."""
    __tablename__ = "subscription_plans"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, index=True, nullable=False)  # e.g. "monthly"
    name = Column(String(100), nullable=False)                          # e.g. "💎 Monthly Premium"
    category = Column(String(50), default="premium", index=True)       # premium/pro/basic/lifetime/custom
    amount = Column(Integer, nullable=False)                            # In rupees (whole)
    duration_days = Column(Integer, nullable=False)                     # 30, 90, 365
    daily_limit = Column(Integer, default=100)
    description = Column(Text, default="")
    badge = Column(String(50), default="")                              # e.g. "POPULAR", "BEST VALUE"
    is_active = Column(Boolean, default=True)                           # Show in /subscribe?
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AdminUser(Base):
    """Admin web panel users."""
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    telegram_id = Column(BigInteger, nullable=True)
    is_superadmin = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)


class BotAdmin(Base):
    """Sub-admins promoted by super-admins (Telegram side admins)."""
    __tablename__ = "bot_admins"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    promoted_by = Column(BigInteger, nullable=False)
    role = Column(String(50), default="admin")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


# ===== v3.5: FRIENDS SYSTEM =====

class Friendship(Base):
    """User-to-user friendship."""
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, index=True, nullable=False)          # requester
    friend_id = Column(BigInteger, index=True, nullable=False)        # target
    status = Column(String(20), default="pending")                    # pending, accepted, blocked
    created_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)


# ===== v3.5: MYSTERY BOX / DAILY REWARDS =====

class DailyReward(Base):
    """Tracks user's daily box claims."""
    __tablename__ = "daily_rewards"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, index=True, nullable=False)
    reward_type = Column(String(50))          # downloads, premium_days, points, badge
    reward_value = Column(String(100))        # amount or badge key
    claimed_at = Column(DateTime, default=datetime.utcnow)
    streak_day = Column(Integer, default=1)   # which day in current streak


class UserStreak(Base):
    """Daily login streaks."""
    __tablename__ = "user_streaks"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    current_streak = Column(Integer, default=0)
    longest_streak = Column(Integer, default=0)
    last_claim_date = Column(DateTime, nullable=True)
    total_claims = Column(Integer, default=0)
    extra_downloads = Column(Integer, default=0)  # accumulated bonus downloads


# ===== v3.5: CLOUD SYNC (Google Drive) =====

class CloudIntegration(Base):
    """User's Google Drive OAuth tokens."""
    __tablename__ = "cloud_integrations"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    provider = Column(String(30), default="google_drive")
    access_token = Column(Text)
    refresh_token = Column(Text)
    expires_at = Column(DateTime, nullable=True)
    folder_id = Column(String(100), nullable=True)  # GODZILLA folder in user's Drive
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Settings(Base):
    """Key-value settings store for bot configuration."""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PaymentRequest(Base):
    """UPI/manual payment requests awaiting admin approval."""
    __tablename__ = "payment_requests"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, index=True, nullable=False)
    username = Column(String(100), nullable=True)
    plan_key = Column(String(50), nullable=False)
    amount = Column(Integer, nullable=False)  # in rupees
    utr = Column(String(50), index=True, nullable=True)  # 12-digit UTR
    screenshot_file_id = Column(String(200), nullable=True)  # Telegram file_id
    status = Column(String(20), default="pending", index=True)  # pending/approved/rejected
    admin_id = Column(BigInteger, nullable=True)  # admin who approved/rejected
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)


class UserState(Base):
    """Track user's current conversation state (e.g., awaiting UTR)."""
    __tablename__ = "user_states"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    state = Column(String(50), nullable=True)  # e.g., "awaiting_utr"
    state_data = Column(Text, nullable=True)  # JSON blob
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db():
    """Create all tables and seed defaults."""
    Base.metadata.create_all(bind=engine)
    run_migrations()
    seed_defaults()


def run_migrations():
    """Safe migrations — add new columns to existing tables if missing."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)

    migrations = [
        # (table, column, sql_type_and_default)
        ("users", "bio", "TEXT DEFAULT ''"),
        ("users", "avatar_emoji", "VARCHAR(10) DEFAULT '🦖'"),
        ("users", "display_name", "VARCHAR(100)"),
        ("users", "badges", "TEXT DEFAULT ''"),
        ("users", "reputation", "INTEGER DEFAULT 0"),
        ("users", "title", "VARCHAR(50) DEFAULT ''"),
        ("users", "custom_limit", "INTEGER"),
        ("subscription_plans", "category", "VARCHAR(50) DEFAULT 'premium'"),
        ("subscription_plans", "badge", "VARCHAR(50) DEFAULT ''"),
    ]

    with engine.begin() as conn:
        for table, column, col_def in migrations:
            try:
                existing_cols = [c["name"] for c in inspector.get_columns(table)]
                if column not in existing_cols:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
                    print(f"✅ Migration: added {table}.{column}")
            except Exception as e:
                # Column might already exist or table missing — safe to skip
                pass


def seed_defaults():
    """Insert default subscription plan and admin if none exist."""
    import os
    import bcrypt

    session = SessionLocal()
    try:
        # Seed default plan if none exists
        if session.query(SubscriptionPlan).count() == 0:
            default_plan = SubscriptionPlan(
                key="monthly",
                name="💎 Monthly Premium",
                amount=49,
                duration_days=30,
                daily_limit=100,
                description="30 days of premium downloads",
                is_active=True,
                sort_order=1,
            )
            session.add(default_plan)
            session.commit()

        # Seed default admin from env vars if none exists
        if session.query(AdminUser).count() == 0:
            admin_user = os.getenv("ADMIN_WEB_USER", "admin")
            admin_pass = os.getenv("ADMIN_WEB_PASS", "godzilla123")
            pw_hash = bcrypt.hashpw(admin_pass.encode(), bcrypt.gensalt()).decode()
            admin = AdminUser(
                username=admin_user,
                password_hash=pw_hash,
                is_superadmin=True,
            )
            session.add(admin)
            session.commit()
    finally:
        session.close()


def get_session():
    """Get a database session."""
    return SessionLocal()
