"""
Mystery Box / Daily Rewards - v3.5
Commands: /daily, /streak, /rewards
"""
import random
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.models import get_session, User, UserStreak, DailyReward
from database import get_or_create_user

logger = logging.getLogger(__name__)

# ========== REWARD POOL ==========
# Format: (type, min, max, weight)  — higher weight = more likely
REWARDS = [
    ("downloads", 2, 5, 50),          # 2-5 extra downloads — common
    ("downloads", 10, 20, 20),        # 10-20 downloads — uncommon
    ("downloads", 50, 50, 5),         # 50 downloads — rare
    ("premium_hours", 1, 3, 15),      # 1-3 hours premium — uncommon
    ("premium_hours", 24, 24, 5),     # 24h premium — rare
    ("points", 10, 50, 25),           # reputation points — common
    ("points", 100, 200, 8),          # big points — rare
    ("nothing", 0, 0, 2),             # tough luck — very rare (2%)
]

# Streak bonuses (multiplier on rewards)
STREAK_BONUSES = {
    3: 1.2,    # 3-day streak: 20% bonus
    7: 1.5,    # 7-day streak: 50% bonus
    14: 2.0,   # 14-day streak: 2x
    30: 3.0,   # 30-day streak: 3x
}


def pick_reward():
    """Weighted random reward from pool."""
    total = sum(r[3] for r in REWARDS)
    roll = random.uniform(0, total)
    cum = 0
    for rtype, rmin, rmax, weight in REWARDS:
        cum += weight
        if roll <= cum:
            if rtype == "nothing":
                return ("nothing", 0)
            value = random.randint(rmin, rmax)
            return (rtype, value)
    return ("downloads", 2)


def apply_streak_bonus(value, streak):
    """Boost reward based on streak days."""
    multiplier = 1.0
    for days, mult in sorted(STREAK_BONUSES.items(), reverse=True):
        if streak >= days:
            multiplier = mult
            break
    return int(value * multiplier)


def can_claim_today(streak_obj):
    """Check if user can claim today's box."""
    if not streak_obj or not streak_obj.last_claim_date:
        return True
    last = streak_obj.last_claim_date.date()
    today = datetime.utcnow().date()
    return last < today


def update_streak(streak_obj):
    """Update streak counter based on last claim."""
    today = datetime.utcnow()
    if not streak_obj.last_claim_date:
        streak_obj.current_streak = 1
    else:
        delta = (today.date() - streak_obj.last_claim_date.date()).days
        if delta == 1:
            streak_obj.current_streak += 1
        elif delta > 1:
            streak_obj.current_streak = 1
    streak_obj.last_claim_date = today
    streak_obj.total_claims += 1
    if streak_obj.current_streak > streak_obj.longest_streak:
        streak_obj.longest_streak = streak_obj.current_streak


async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claim daily mystery box."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    session = get_session()
    try:
        streak = session.query(UserStreak).filter_by(telegram_id=user.id).first()
        if not streak:
            streak = UserStreak(telegram_id=user.id)
            session.add(streak)
            session.commit()

        if not can_claim_today(streak):
            # Calculate time until next claim
            now = datetime.utcnow()
            tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
            hours_left = int((tomorrow - now).total_seconds() // 3600)
            mins_left = int(((tomorrow - now).total_seconds() % 3600) // 60)

            await update.message.reply_text(
                f"⏰ *Already claimed today!*\n\n"
                f"Current streak: *{streak.current_streak} days* 🔥\n"
                f"Come back in *{hours_left}h {mins_left}m* for another box.\n\n"
                f"_Don't break the streak!_",
                parse_mode="Markdown",
            )
            return

        # Show opening animation
        msg = await update.message.reply_text("🎁 *Opening your daily mystery box...*", parse_mode="Markdown")

        # Update streak first to get current value
        update_streak(streak)
        current_streak = streak.current_streak

        # Roll reward
        reward_type, reward_value = pick_reward()
        boosted_value = apply_streak_bonus(reward_value, current_streak)

        # Apply reward
        result_text = ""
        db_user = session.query(User).filter_by(telegram_id=user.id).first()

        if reward_type == "nothing":
            result_text = "😅 *Empty box!* Better luck tomorrow."
        elif reward_type == "downloads":
            streak.extra_downloads += boosted_value
            result_text = f"📥 *+{boosted_value} Extra Downloads!*"
        elif reward_type == "premium_hours":
            if db_user.is_premium and db_user.subscription_expires_at:
                db_user.subscription_expires_at += timedelta(hours=boosted_value)
            else:
                db_user.is_premium = True
                db_user.subscription_expires_at = datetime.utcnow() + timedelta(hours=boosted_value)
                db_user.subscription_plan = "mystery_box"
            result_text = f"💎 *+{boosted_value} Hours Premium!*"
        elif reward_type == "points":
            db_user.reputation = (db_user.reputation or 0) + boosted_value
            result_text = f"⭐ *+{boosted_value} Reputation Points!*"

        # Save DailyReward
        dr = DailyReward(
            telegram_id=user.id,
            reward_type=reward_type,
            reward_value=str(boosted_value),
            streak_day=current_streak,
        )
        session.add(dr)
        session.commit()

        # Streak milestones
        milestone_text = ""
        if current_streak in STREAK_BONUSES:
            mult = STREAK_BONUSES[current_streak]
            milestone_text = f"\n\n🏆 *{current_streak}-DAY STREAK!*\n_Rewards now {mult}x boosted!_"

        text = (
            f"🎁 *Daily Mystery Box*\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"{result_text}\n\n"
            f"🔥 *Streak:* {current_streak} days\n"
            f"🏆 *Longest:* {streak.longest_streak} days\n"
            f"📊 *Total boxes:* {streak.total_claims}"
            f"{milestone_text}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"_Come back tomorrow for another box!_"
        )

        await msg.edit_text(text, parse_mode="Markdown")
    finally:
        session.close()


async def streak_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current streak info."""
    user = update.effective_user
    get_or_create_user(user.id, user.username, user.first_name)

    session = get_session()
    try:
        streak = session.query(UserStreak).filter_by(telegram_id=user.id).first()
        if not streak or streak.total_claims == 0:
            await update.message.reply_text(
                "🎁 *No streak yet!*\n\nUse /daily to open your first mystery box and start a streak.",
                parse_mode="Markdown",
            )
            return

        # Next milestone
        next_milestone = None
        for days in sorted(STREAK_BONUSES.keys()):
            if streak.current_streak < days:
                next_milestone = days
                break

        text = (
            f"🔥 *Your Streak Dashboard*\n"
            f"━━━━━━━━━━━━━━━\n\n"
            f"*Current Streak:* {streak.current_streak} days 🔥\n"
            f"*Longest Streak:* {streak.longest_streak} days 👑\n"
            f"*Total Boxes Claimed:* {streak.total_claims}\n"
            f"*Bonus Downloads Earned:* {streak.extra_downloads}\n"
        )

        if next_milestone:
            days_left = next_milestone - streak.current_streak
            mult = STREAK_BONUSES[next_milestone]
            text += f"\n🎯 *Next milestone:* {next_milestone} days ({mult}x rewards)\n"
            text += f"_Only {days_left} more days to go!_"

        text += "\n\n━━━━━━━━━━━━━━━\n"
        text += "💡 *Milestones:*\n"
        for days, mult in STREAK_BONUSES.items():
            check = "✅" if streak.current_streak >= days else "⭕"
            text += f"{check} {days} days = {mult}x rewards\n"

        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        session.close()


async def rewards_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recent reward history."""
    user = update.effective_user

    session = get_session()
    try:
        recent = session.query(DailyReward).filter_by(telegram_id=user.id) \
            .order_by(DailyReward.claimed_at.desc()).limit(10).all()

        if not recent:
            await update.message.reply_text(
                "📭 *No rewards yet!*\n\nUse /daily to claim your first box.",
                parse_mode="Markdown",
            )
            return

        text = "🎁 *Your Recent Rewards*\n━━━━━━━━━━━━━━━\n\n"
        for r in recent:
            date = r.claimed_at.strftime("%d %b")
            emoji = {"downloads": "📥", "premium_hours": "💎", "points": "⭐", "nothing": "😅"}.get(r.reward_type, "🎁")
            text += f"{emoji} *{r.reward_type}*: +{r.reward_value} _({date}, day {r.streak_day})_\n"

        await update.message.reply_text(text, parse_mode="Markdown")
    finally:
        session.close()
