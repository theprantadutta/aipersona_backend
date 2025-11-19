"""Usage tracking service for analytics"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.models.user import User, UsageTracking
from app.models.chat import ChatMessage, ChatSession
from app.config import settings
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, date
import logging

logger = logging.getLogger(__name__)


class UsageService:
    """Service for usage tracking and analytics"""

    def __init__(self, db: Session):
        self.db = db

    def get_current_usage(self, user_id: str) -> Dict[str, Any]:
        """Get current usage stats for a user"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        usage = user.usage_tracking
        if not usage:
            # Create usage tracking if it doesn't exist
            usage = UsageTracking(user_id=user_id)
            self.db.add(usage)
            self.db.commit()
            self.db.refresh(usage)

        # Check and reset daily counters if needed
        usage.check_and_reset_daily()
        self.db.commit()

        # Calculate storage in MB
        storage_mb = usage.storage_used_bytes / (1024 * 1024)

        return {
            "messages_today": usage.messages_today,
            "messages_limit": settings.FREE_TIER_MESSAGE_LIMIT if not user.is_premium else None,
            "personas_count": usage.personas_count,
            "personas_limit": settings.FREE_TIER_PERSONA_LIMIT if not user.is_premium else None,
            "storage_used_bytes": usage.storage_used_bytes,
            "storage_used_mb": round(storage_mb, 2),
            "gemini_api_calls_today": usage.gemini_api_calls_today,
            "gemini_tokens_used_total": usage.gemini_tokens_used_total,
            "last_reset_at": usage.messages_count_reset_at,
            "is_premium": user.is_premium,
            "subscription_tier": user.subscription_tier
        }

    def get_usage_history(
        self,
        user_id: str,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        Get historical usage data for a date range

        This queries chat messages to build historical usage
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        # Convert dates to datetime
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        # Get all user's sessions
        session_ids = self.db.query(ChatSession.id).filter(
            ChatSession.user_id == user_id
        ).all()
        session_ids = [sid[0] for sid in session_ids]

        # Query messages grouped by date
        daily_stats = self.db.query(
            func.date(ChatMessage.created_at).label('date'),
            func.count(ChatMessage.id).filter(ChatMessage.sender_type == 'user').label('user_messages'),
            func.count(ChatMessage.id).filter(ChatMessage.sender_type == 'ai').label('ai_messages'),
            func.sum(ChatMessage.tokens_used).label('tokens')
        ).filter(
            and_(
                ChatMessage.session_id.in_(session_ids),
                ChatMessage.created_at >= start_dt,
                ChatMessage.created_at <= end_dt
            )
        ).group_by(
            func.date(ChatMessage.created_at)
        ).all()

        # Build response
        entries = []
        total_messages = 0
        total_api_calls = 0
        total_tokens = 0

        for stat in daily_stats:
            user_msg_count = stat.user_messages or 0
            ai_msg_count = stat.ai_messages or 0
            tokens = stat.tokens or 0

            entries.append({
                "date": stat.date,
                "messages_count": user_msg_count,
                "api_calls": ai_msg_count,
                "tokens_used": tokens
            })

            total_messages += user_msg_count
            total_api_calls += ai_msg_count
            total_tokens += tokens

        return {
            "entries": entries,
            "period_start": start_date,
            "period_end": end_date,
            "total_messages": total_messages,
            "total_api_calls": total_api_calls,
            "total_tokens": total_tokens
        }

    def get_usage_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get advanced usage analytics

        Includes current usage, trends, predictions
        """
        # Get current usage
        current_usage = self.get_current_usage(user_id)

        # Get historical data
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        history = self.get_usage_history(user_id, start_date, end_date)

        # Calculate daily average
        day_count = (end_date - start_date).days + 1
        daily_average = history["total_messages"] / day_count if day_count > 0 else 0

        # Find peak usage day
        peak_day = None
        peak_count = 0
        for entry in history["entries"]:
            if entry["messages_count"] > peak_count:
                peak_count = entry["messages_count"]
                peak_day = entry["date"]

        # Determine trend (simple: compare first half vs second half)
        mid_point = len(history["entries"]) // 2
        if len(history["entries"]) > 4:
            first_half_avg = sum(e["messages_count"] for e in history["entries"][:mid_point]) / max(mid_point, 1)
            second_half_avg = sum(e["messages_count"] for e in history["entries"][mid_point:]) / max(len(history["entries"]) - mid_point, 1)

            if second_half_avg > first_half_avg * 1.2:
                trend = "increasing"
            elif second_half_avg < first_half_avg * 0.8:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        # Calculate usage percentage (for free tier)
        usage_percentage = None
        if current_usage["messages_limit"]:
            usage_percentage = (current_usage["messages_today"] / current_usage["messages_limit"]) * 100

        # Simple predictions
        predictions = {
            "projected_messages_today": current_usage["messages_today"],  # Could be more sophisticated
            "likely_to_hit_limit": usage_percentage and usage_percentage > 80 if usage_percentage else False,
            "recommended_upgrade": trend == "increasing" and not current_usage["is_premium"]
        }

        return {
            "current_usage": current_usage,
            "daily_average": round(daily_average, 2),
            "peak_usage_day": peak_day,
            "peak_usage_count": peak_count,
            "trend": trend,
            "usage_percentage": round(usage_percentage, 2) if usage_percentage else None,
            "predictions": predictions
        }

    def export_usage_data(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
        format: str = "json",
        include_details: bool = True
    ) -> Dict[str, Any]:
        """
        Export usage data

        Args:
            user_id: User ID
            start_date: Start date
            end_date: End date
            format: Export format (json or csv)
            include_details: Include detailed breakdown

        Returns:
            Dict with export data
        """
        history = self.get_usage_history(user_id, start_date, end_date)

        export_data = {
            "user_id": user_id,
            "export_date": datetime.utcnow().isoformat(),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "summary": {
                "total_messages": history["total_messages"],
                "total_api_calls": history["total_api_calls"],
                "total_tokens": history["total_tokens"]
            }
        }

        if include_details:
            export_data["daily_breakdown"] = history["entries"]

        if format == "csv":
            # Convert to CSV format
            csv_lines = ["Date,Messages,API Calls,Tokens Used"]
            for entry in history["entries"]:
                csv_lines.append(
                    f"{entry['date']},{entry['messages_count']},{entry['api_calls']},{entry['tokens_used']}"
                )
            export_data["csv_content"] = "\n".join(csv_lines)

        return export_data

    def reset_daily_counters_for_all_users(self):
        """
        Background task to reset daily counters
        Called by scheduler
        """
        now = datetime.utcnow()

        # Get all usage tracking records
        all_usage = self.db.query(UsageTracking).all()

        reset_count = 0
        for usage in all_usage:
            if usage.check_and_reset_daily():
                reset_count += 1

        self.db.commit()

        logger.info(f"Reset daily counters for {reset_count} users")
        return {"reset_count": reset_count}
