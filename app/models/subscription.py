"""Subscription models (Google Play only)"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
import uuid
from app.database import Base
from app.utils.time_utils import utc_now


class SubscriptionEvent(Base):
    """Google Play subscription event tracking"""

    __tablename__ = "subscription_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Google Play purchase information
    purchase_token = Column(String(500), nullable=False, index=True)
    product_id = Column(String(100), nullable=False)  # daily_premium, monthly_premium, yearly_premium
    subscription_tier = Column(String(50), nullable=False)  # premium_daily, premium_monthly, premium_yearly

    # Expiration
    expires_at = Column(DateTime, nullable=False)

    # Event tracking
    event_type = Column(String(50), nullable=False)  # purchased, renewed, cancelled, expired, refunded
    verification_status = Column(String(50), nullable=False)  # verified, pending, failed

    # Raw Google Play response
    raw_response = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utc_now, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="subscription_events")

    def __repr__(self):
        return f"<SubscriptionEvent(id={self.id}, user_id={self.user_id}, type={self.event_type})>"
