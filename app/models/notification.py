"""Notification models (FCM)"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.database import Base
from app.utils.time_utils import utc_now


class FCMToken(Base):
    """Firebase Cloud Messaging token model"""

    __tablename__ = "fcm_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # FCM token
    fcm_token = Column(String(500), nullable=False, unique=True)

    # Device information
    device_id = Column(String(255), nullable=False, index=True)
    platform = Column(String(50), nullable=False)  # android, ios, web

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=utc_now, nullable=False)
    last_used_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="fcm_tokens")

    def __repr__(self):
        return f"<FCMToken(id={self.id}, user_id={self.user_id}, device={self.device_id})>"
