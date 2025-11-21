"""Admin user setup utility"""
from sqlalchemy.orm import Session
import logging

from app.models.user import User, UsageTracking
from app.core.security import get_password_hash
from app.config import settings

logger = logging.getLogger(__name__)


def ensure_admin_user(db: Session) -> None:
    """
    Ensure admin user exists in the database.
    Creates admin user if it doesn't exist, updates if it does.
    """
    try:
        # Check if admin user exists
        admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()

        if admin:
            # Update existing user to admin
            if not admin.is_admin:
                admin.is_admin = True
                logger.info(f"Updated user {settings.ADMIN_EMAIL} to admin")

            # Update password if changed
            admin.password_hash = get_password_hash(settings.ADMIN_PASSWORD)
            admin.is_active = True

            db.commit()
            logger.info(f"Admin user {settings.ADMIN_EMAIL} verified")
        else:
            # Create new admin user
            admin = User(
                email=settings.ADMIN_EMAIL,
                password_hash=get_password_hash(settings.ADMIN_PASSWORD),
                display_name="Admin",
                auth_provider="email",
                email_verified=True,
                is_active=True,
                is_admin=True,
                subscription_tier="lifetime"  # Give admin lifetime premium
            )

            db.add(admin)
            db.flush()  # Get the user ID

            # Create usage tracking for admin
            usage = UsageTracking(user_id=admin.id)
            db.add(usage)

            db.commit()
            logger.info(f"Created admin user: {settings.ADMIN_EMAIL}")

    except Exception as e:
        logger.error(f"Failed to ensure admin user: {str(e)}")
        db.rollback()
        raise
