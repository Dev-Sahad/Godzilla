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
    subscription_expires_at = Column(DateTime, nullable=True)   # When premium ends
    subscription_plan = Column(String(50), nullable=True)       # e.g. "monthly"
    auto_renew = Column(Boolean, default=False)
    downloads_today = Column(Integer, default=0)
    total_downloads = Column(Integer, default=0)
    last_reset = Column(DateTime, default=datetime.utcnow)
    joined_at = Column(DateTime, default=datetime.utcnow)
    referred_by = Column(BigInteger, nullable=True)
    referral_count = Column(Integer, default=0)
    referral_reward_claimed = Column(Boolean, default=False)   # Got 7-day bonus?
    custom_limit = Column(Integer, nullable=True)              # Admin-set daily limit override

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
    seed_defaults()


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
