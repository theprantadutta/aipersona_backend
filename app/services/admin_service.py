"""Admin dashboard service"""
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from typing import List, Dict, Any, Optional, Tuple
from datetime import timedelta
from decimal import Decimal
import logging

from app.utils.time_utils import utc_now

from app.models.user import User, UsageTracking
from app.models.persona import Persona
from app.models.chat import ChatSession, ChatMessage
from app.models.marketplace import MarketplacePersona, MarketplaceReview
from app.models.subscription import SubscriptionEvent

logger = logging.getLogger(__name__)


class AdminService:
    """Service for admin dashboard operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_users(
        self,
        status: Optional[str] = None,
        subscription_tier: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[User], int]:
        """
        Get users with filters

        Args:
            status: Filter by status (active, inactive)
            subscription_tier: Filter by subscription tier
            search: Search in email and display_name
            skip: Records to skip
            limit: Max records to return

        Returns:
            Tuple of (users list, total count)
        """
        query = self.db.query(User)

        # Apply filters
        if status == "active":
            query = query.filter(User.is_active == True)
        elif status == "inactive":
            query = query.filter(User.is_active == False)

        if subscription_tier:
            query = query.filter(User.subscription_tier == subscription_tier)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    User.email.ilike(search_pattern),
                    User.display_name.ilike(search_pattern)
                )
            )

        # Get total count
        total = query.count()

        # Apply sorting and pagination
        users = query.order_by(desc(User.created_at)).offset(skip).limit(limit).all()

        return users, total

    def update_user_status(
        self,
        user_id: str,
        action: str,
        reason: Optional[str] = None
    ) -> User:
        """
        Update user status (activate, suspend, ban)

        Args:
            user_id: User ID
            action: Action to perform (activate, suspend, ban)
            reason: Optional reason for the action

        Returns:
            Updated user

        Raises:
            ValueError: If user not found or invalid action
        """
        user = self.db.query(User).filter(User.id == user_id).first()

        if not user:
            raise ValueError("User not found")

        if action == "activate":
            user.is_active = True
        elif action in ["suspend", "ban"]:
            user.is_active = False
        else:
            raise ValueError(f"Invalid action: {action}")

        self.db.commit()
        self.db.refresh(user)

        logger.info(f"User {user_id} status updated: {action}" + (f" - Reason: {reason}" if reason else ""))

        return user

    def get_business_analytics(self) -> Dict[str, Any]:
        """
        Get comprehensive business analytics

        Returns:
            Dictionary with analytics data
        """
        now = utc_now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        today_start = datetime(now.year, now.month, now.day)

        # User metrics
        total_users = self.db.query(func.count(User.id)).scalar()

        active_users_today = self.db.query(func.count(User.id)).filter(
            User.last_login >= today_start
        ).scalar()

        new_users_this_week = self.db.query(func.count(User.id)).filter(
            User.created_at >= week_ago
        ).scalar()

        new_users_this_month = self.db.query(func.count(User.id)).filter(
            User.created_at >= month_ago
        ).scalar()

        # Subscription metrics
        free_tier_users = self.db.query(func.count(User.id)).filter(
            User.subscription_tier == "free"
        ).scalar()

        premium_users = self.db.query(func.count(User.id)).filter(
            User.subscription_tier != "free"
        ).scalar()

        daily_subscribers = self.db.query(func.count(User.id)).filter(
            User.subscription_tier == "premium_daily"
        ).scalar()

        monthly_subscribers = self.db.query(func.count(User.id)).filter(
            User.subscription_tier == "premium_monthly"
        ).scalar()

        yearly_subscribers = self.db.query(func.count(User.id)).filter(
            User.subscription_tier == "premium_yearly"
        ).scalar()

        lifetime_subscribers = self.db.query(func.count(User.id)).filter(
            User.subscription_tier == "lifetime"
        ).scalar()

        # Revenue metrics (estimated)
        monthly_recurring_revenue = Decimal(
            (daily_subscribers * 0.99 * 30) +
            (monthly_subscribers * 9.99) +
            (yearly_subscribers * 59.99 / 12)
        )

        total_lifetime_revenue = Decimal(
            (lifetime_subscribers * 149.99) +
            (monthly_recurring_revenue * 12)  # Estimated annual from recurring
        )

        # Usage metrics
        total_messages_today = self.db.query(
            func.sum(UsageTracking.messages_today)
        ).scalar() or 0

        total_messages_this_week = self.db.query(
            func.count(ChatMessage.id)
        ).filter(ChatMessage.created_at >= week_ago).scalar() or 0

        total_messages_this_month = self.db.query(
            func.count(ChatMessage.id)
        ).filter(ChatMessage.created_at >= month_ago).scalar() or 0

        avg_messages_per_user = (
            total_messages_this_month / total_users
        ) if total_users > 0 else 0.0

        # Content metrics
        total_personas = self.db.query(func.count(Persona.id)).scalar()

        public_personas = self.db.query(func.count(Persona.id)).filter(
            Persona.is_public == True
        ).scalar()

        marketplace_listings = self.db.query(func.count(MarketplacePersona.id)).filter(
            MarketplacePersona.status == "approved"
        ).scalar()

        # Engagement metrics
        active_chat_sessions = self.db.query(func.count(ChatSession.id)).filter(
            ChatSession.status == "active"
        ).scalar()

        total_chat_sessions = self.db.query(func.count(ChatSession.id)).scalar()

        # Calculate average session length
        sessions_with_messages = self.db.query(
            ChatSession.id,
            func.min(ChatMessage.created_at).label('first_message'),
            func.max(ChatMessage.created_at).label('last_message')
        ).join(ChatMessage).group_by(ChatSession.id).all()

        if sessions_with_messages:
            total_minutes = sum(
                (session.last_message - session.first_message).total_seconds() / 60
                for session in sessions_with_messages
            )
            avg_session_length_minutes = total_minutes / len(sessions_with_messages)
        else:
            avg_session_length_minutes = 0.0

        return {
            "total_users": total_users,
            "active_users_today": active_users_today,
            "new_users_this_week": new_users_this_week,
            "new_users_this_month": new_users_this_month,
            "free_tier_users": free_tier_users,
            "premium_users": premium_users,
            "daily_subscribers": daily_subscribers,
            "monthly_subscribers": monthly_subscribers,
            "yearly_subscribers": yearly_subscribers,
            "lifetime_subscribers": lifetime_subscribers,
            "monthly_recurring_revenue": monthly_recurring_revenue,
            "total_lifetime_revenue": total_lifetime_revenue,
            "total_messages_today": total_messages_today,
            "total_messages_this_week": total_messages_this_week,
            "total_messages_this_month": total_messages_this_month,
            "avg_messages_per_user": round(avg_messages_per_user, 2),
            "total_personas": total_personas,
            "public_personas": public_personas,
            "marketplace_listings": marketplace_listings,
            "active_chat_sessions": active_chat_sessions,
            "total_chat_sessions": total_chat_sessions,
            "avg_session_length_minutes": round(avg_session_length_minutes, 2)
        }

    def get_moderation_queue(
        self,
        content_type: Optional[str] = None,
        status: str = "pending",
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get content moderation queue

        Args:
            content_type: Filter by type (persona, marketplace_listing, review)
            status: Filter by status (pending, approved, rejected)
            skip: Records to skip
            limit: Max records to return

        Returns:
            Tuple of (queue items, total count)
        """
        items = []

        # For now, we'll return marketplace listings that need moderation
        # In a real implementation, you'd have a content_moderation table

        if not content_type or content_type == "marketplace_listing":
            query = self.db.query(MarketplacePersona).filter(
                MarketplacePersona.status == status
            )

            total = query.count()
            listings = query.order_by(desc(MarketplacePersona.created_at)).offset(skip).limit(limit).all()

            for listing in listings:
                items.append({
                    "id": str(listing.id),
                    "type": "marketplace_listing",
                    "content_id": str(listing.id),
                    "user_id": str(listing.seller_id),
                    "user_email": listing.seller.email if listing.seller else "Unknown",
                    "title": listing.title,
                    "description": listing.description,
                    "status": listing.status,
                    "created_at": listing.created_at,
                    "flagged_count": 0
                })

        if not content_type or content_type == "review":
            # Get reviews for moderation (could be flagged reviews)
            reviews = self.db.query(MarketplaceReview).filter(
                MarketplaceReview.rating <= 2  # Low-rated reviews for review
            ).order_by(desc(MarketplaceReview.created_at)).offset(skip).limit(limit).all()

            for review in reviews:
                items.append({
                    "id": str(review.id),
                    "type": "review",
                    "content_id": str(review.id),
                    "user_id": str(review.reviewer_id),
                    "user_email": review.reviewer.email if review.reviewer else "Unknown",
                    "title": f"Review for {review.marketplace_persona.title}" if review.marketplace_persona else "Review",
                    "description": review.review_text,
                    "status": "pending",
                    "created_at": review.created_at,
                    "flagged_count": 0
                })

        return items, len(items)

    def moderate_content(
        self,
        content_type: str,
        content_id: str,
        action: str,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Moderate content (approve, reject, delete)

        Args:
            content_type: Type of content (marketplace_listing, review, etc.)
            content_id: Content ID
            action: Action to perform (approve, reject, delete)
            reason: Optional reason for the action

        Returns:
            Moderation result

        Raises:
            ValueError: If content not found or invalid action
        """
        if action not in ["approve", "reject", "delete"]:
            raise ValueError(f"Invalid action: {action}")

        if content_type == "marketplace_listing":
            listing = self.db.query(MarketplacePersona).filter(
                MarketplacePersona.id == content_id
            ).first()

            if not listing:
                raise ValueError("Marketplace listing not found")

            if action == "approve":
                listing.status = "approved"
                listing.approved_at = utc_now()
            elif action == "reject":
                listing.status = "rejected"
            elif action == "delete":
                self.db.delete(listing)

            self.db.commit()

            logger.info(f"Moderated marketplace listing {content_id}: {action}" + (f" - Reason: {reason}" if reason else ""))

            return {
                "content_id": content_id,
                "content_type": content_type,
                "action": action,
                "message": f"Content {action}d successfully"
            }

        elif content_type == "review":
            review = self.db.query(MarketplaceReview).filter(
                MarketplaceReview.id == content_id
            ).first()

            if not review:
                raise ValueError("Review not found")

            if action == "delete":
                self.db.delete(review)
                self.db.commit()

            logger.info(f"Moderated review {content_id}: {action}" + (f" - Reason: {reason}" if reason else ""))

            return {
                "content_id": content_id,
                "content_type": content_type,
                "action": action,
                "message": f"Review {action}d successfully"
            }

        else:
            raise ValueError(f"Unknown content type: {content_type}")

    def get_system_health(self) -> Dict[str, Any]:
        """
        Get system health metrics

        Returns:
            System health data
        """
        try:
            # Test database connection
            self.db.execute("SELECT 1")
            database_connected = True
        except Exception:
            database_connected = False

        # Calculate uptime (simplified - in production, track actual uptime)
        uptime_hours = 24.0  # Placeholder

        return {
            "database_connected": database_connected,
            "redis_connected": False,  # Not implemented yet
            "gemini_api_available": True,  # Would check API in production
            "total_requests_today": 0,  # Would track in middleware
            "avg_response_time_ms": 0.0,  # Would track in middleware
            "error_rate_percent": 0.0,  # Would track in middleware
            "uptime_hours": uptime_hours
        }
