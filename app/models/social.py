"""Social interaction database models"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base
import uuid


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
