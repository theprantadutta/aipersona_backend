"""Social interaction database models"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, UniqueConstraint, Index, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base
import uuid
import enum


# Enums for Content Reporting
class ReportType(str, enum.Enum):
    persona = "persona"
    user = "user"
    conversation = "conversation"
    message = "message"


class ReportReason(str, enum.Enum):
    inappropriate_content = "inappropriate_content"
    harassment = "harassment"
    spam = "spam"
    hate_speech = "hate_speech"
    violence = "violence"
    sexual_content = "sexual_content"
    misinformation = "misinformation"
    copyright_violation = "copyright_violation"
    other = "other"


class ReportStatus(str, enum.Enum):
    pending = "pending"
    under_review = "under_review"
    resolved = "resolved"
    dismissed = "dismissed"


# Enums for Activity Feed
class ActivityType(str, enum.Enum):
    persona_created = "persona_created"
    persona_liked = "persona_liked"
    persona_favorited = "persona_favorited"
    persona_cloned = "persona_cloned"
    user_followed = "user_followed"
    persona_published = "persona_published"


class PersonaLike(Base):
    """Persona likes table"""
    __tablename__ = "persona_likes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    persona_id = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Unique constraint: one like per user per persona
    __table_args__ = (
        UniqueConstraint('user_id', 'persona_id', name='uq_user_persona_like'),
        Index('idx_persona_likes_user', 'user_id'),
        Index('idx_persona_likes_persona', 'persona_id'),
    )


class PersonaFavorite(Base):
    """Persona favorites table"""
    __tablename__ = "persona_favorites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    persona_id = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Unique constraint: one favorite per user per persona
    __table_args__ = (
        UniqueConstraint('user_id', 'persona_id', name='uq_user_persona_favorite'),
        Index('idx_persona_favorites_user', 'user_id'),
        Index('idx_persona_favorites_persona', 'persona_id'),
    )


class UserFollow(Base):
    """User follows table"""
    __tablename__ = "user_follows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    follower_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # Who is following
    following_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # Who is being followed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Unique constraint: one follow per follower-following pair
    __table_args__ = (
        UniqueConstraint('follower_id', 'following_id', name='uq_follower_following'),
        Index('idx_user_follows_follower', 'follower_id'),
        Index('idx_user_follows_following', 'following_id'),
    )


class PersonaView(Base):
    """Persona views tracking"""
    __tablename__ = "persona_views"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Can be anonymous
    viewed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index('idx_persona_views_persona', 'persona_id'),
        Index('idx_persona_views_user', 'user_id'),
        Index('idx_persona_views_date', 'viewed_at'),
    )


class UserBlock(Base):
    """User blocking table"""
    __tablename__ = "user_blocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blocker_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # Who is blocking
    blocked_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # Who is being blocked
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reason = Column(String(500), nullable=True)  # Optional reason for blocking

    # Unique constraint: one block per blocker-blocked pair
    __table_args__ = (
        UniqueConstraint('blocker_id', 'blocked_id', name='uq_blocker_blocked'),
        Index('idx_user_blocks_blocker', 'blocker_id'),
        Index('idx_user_blocks_blocked', 'blocked_id'),
    )


class ContentReport(Base):
    """Content reports table for moderation"""
    __tablename__ = "content_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(String(255), nullable=False)  # ID of the reported content (persona_id, user_id, etc.)
    content_type = Column(String(50), nullable=False)  # 'persona', 'user', 'conversation', 'message'
    reason = Column(String(50), nullable=False)  # Report reason enum value
    additional_info = Column(Text, nullable=True)  # Optional additional details
    status = Column(String(50), default="pending", nullable=False)  # 'pending', 'under_review', 'resolved', 'dismissed'
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Admin review fields
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution = Column(Text, nullable=True)  # Resolution notes from admin

    __table_args__ = (
        Index('idx_content_reports_reporter', 'reporter_id'),
        Index('idx_content_reports_content', 'content_id'),
        Index('idx_content_reports_status', 'status'),
        Index('idx_content_reports_type', 'content_type'),
        Index('idx_content_reports_created', 'created_at'),
    )


class UserActivity(Base):
    """User activity feed tracking"""
    __tablename__ = "user_activities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)  # User who performed the action
    activity_type = Column(String(50), nullable=False)  # Type of activity (enum value)
    target_id = Column(String(255), nullable=True)  # ID of the target (persona_id, user_id, etc.)
    target_type = Column(String(50), nullable=True)  # Type of target ('persona', 'user')
    activity_data = Column(Text, nullable=True)  # JSON metadata for additional context
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index('idx_user_activities_user', 'user_id'),
        Index('idx_user_activities_type', 'activity_type'),
        Index('idx_user_activities_created', 'created_at'),
        Index('idx_user_activities_target', 'target_id'),
    )
