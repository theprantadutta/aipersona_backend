"""Background scheduler for periodic tasks"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import timedelta
from app.config import settings
from app.utils.time_utils import utc_now
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def start_scheduler():
    """Start the background scheduler"""
    try:
        scheduler.start()
        logger.info("✅ Scheduler started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start scheduler: {e}")


def stop_scheduler():
    """Stop the background scheduler"""
    try:
        scheduler.shutdown()
        logger.info("✅ Scheduler stopped successfully")
    except Exception as e:
        logger.error(f"❌ Failed to stop scheduler: {e}")


@scheduler.scheduled_job('cron', hour=0, minute=0)
async def cleanup_free_tier_history():
    """
    Delete chat messages older than FREE_TIER_HISTORY_DAYS for free users
    Runs daily at midnight
    """
    try:
        from app.database import SessionLocal
        from app.models.user import User
        from app.models.chat import ChatMessage, ChatSession

        db = SessionLocal()

        cutoff_date = utc_now() - timedelta(days=settings.FREE_TIER_HISTORY_DAYS)

        logger.info(f"🧹 Starting free tier history cleanup (older than {cutoff_date})")

        # Get all free tier users
        free_users = db.query(User).filter(User.subscription_tier == "free").all()

        total_deleted = 0
        for user in free_users:
            # Get user's session IDs
            session_ids = [s.id for s in db.query(ChatSession.id).filter_by(user_id=user.id).all()]

            if session_ids:
                # Delete old messages
                deleted = db.query(ChatMessage).filter(
                    ChatMessage.session_id.in_(session_ids),
                    ChatMessage.created_at < cutoff_date
                ).delete(synchronize_session=False)

                total_deleted += deleted

        db.commit()
        db.close()

        logger.info(f"✅ Cleanup complete: Deleted {total_deleted} old messages from free tier users")

    except Exception as e:
        logger.error(f"❌ Error during history cleanup: {e}")


@scheduler.scheduled_job('cron', hour=0, minute=0)
async def reset_daily_counters():
    """
    Reset daily usage counters (messages, API calls)
    Runs daily at midnight
    """
    try:
        from app.database import SessionLocal
        from app.models.user import UsageTracking

        db = SessionLocal()

        logger.info("🔄 Resetting daily usage counters")

        # Reset all daily counters
        db.query(UsageTracking).update({
            "messages_today": 0,
            "gemini_api_calls_today": 0,
            "messages_count_reset_at": utc_now()
        })

        db.commit()
        db.close()

        logger.info("✅ Daily counters reset successfully")

    except Exception as e:
        logger.error(f"❌ Error resetting daily counters: {e}")


@scheduler.scheduled_job('cron', hour=0, minute=30)
async def check_subscription_expirations():
    """
    Check for expired subscriptions and handle grace periods
    Runs daily at 12:30 AM
    """
    try:
        from app.database import SessionLocal
        from app.models.user import User

        db = SessionLocal()
        now = utc_now()

        logger.info("🔍 Checking subscription expirations")

        # Find users with expired subscriptions (not in grace period)
        expired_users = db.query(User).filter(
            User.subscription_expires_at < now,
            User.subscription_tier.notin_(["free", "lifetime"])
        ).all()

        for user in expired_users:
            # Check if already in grace period
            if user.grace_period_ends_at and user.grace_period_ends_at > now:
                # Still in grace period, do nothing
                continue
            elif user.grace_period_ends_at and user.grace_period_ends_at < now:
                # Grace period ended, downgrade to free
                user.subscription_tier = "free"
                user.subscription_expires_at = None
                user.grace_period_ends_at = None
                logger.info(f"⬇️ Downgraded user {user.email} to free tier (grace period ended)")
            else:
                # Just expired, start grace period
                user.grace_period_ends_at = now + timedelta(days=settings.GRACE_PERIOD_DAYS)
                logger.info(f"⏰ Started grace period for user {user.email}")

        db.commit()
        db.close()

        logger.info(f"✅ Processed {len(expired_users)} subscription expirations")

    except Exception as e:
        logger.error(f"❌ Error checking subscription expirations: {e}")
