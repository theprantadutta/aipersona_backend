"""Persona models"""
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base


class Persona(Base):
    """AI Persona model"""

    __tablename__ = "personas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    image_path = Column(String(500), nullable=True)  # Backend file path, not Firebase URL
    bio = Column(Text, nullable=True)

    # Personality configuration
    personality_traits = Column(JSON, nullable=True)  # Array of trait strings
    language_style = Column(String(100), nullable=True)  # casual, formal, friendly, etc.
    expertise = Column(JSON, nullable=True)  # Array of expertise areas
    tags = Column(JSON, nullable=True)  # Array of tags for discovery

    # Voice settings
    voice_id = Column(String(100), nullable=True)
    voice_settings = Column(JSON, nullable=True)

    # Status and visibility
    status = Column(String(50), default="active", nullable=False)  # active, draft, archived, suspended
    is_public = Column(Boolean, default=True, nullable=False)
    is_marketplace = Column(Boolean, default=False, nullable=False)

    # Analytics
    conversation_count = Column(Integer, default=0, nullable=False)
    clone_count = Column(Integer, default=0, nullable=False)
    like_count = Column(Integer, default=0, nullable=False)

    # Cloning support
    cloned_from_persona_id = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True)
    original_creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    creator = relationship("User", foreign_keys=[creator_id], back_populates="personas")
    knowledge_bases = relationship("KnowledgeBase", back_populates="persona", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="persona", cascade="all, delete-orphan")
    marketplace_listing = relationship("MarketplacePersona", back_populates="persona", uselist=False)

    def __repr__(self):
        return f"<Persona(id={self.id}, name={self.name}, creator_id={self.creator_id})>"


class KnowledgeBase(Base):
    """Knowledge base for personas"""

    __tablename__ = "knowledge_bases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False, index=True)

    # Source information
    source_type = Column(String(50), nullable=False)  # text, file, url, document
    source_name = Column(String(255), nullable=True)  # Filename or URL
    content = Column(Text, nullable=False)  # The actual knowledge content

    # Processing status
    tokens = Column(Integer, default=0, nullable=False)  # Token count for content
    status = Column(String(50), default="active", nullable=False)  # active, processing, error
    indexed_at = Column(DateTime, nullable=True)

    # Metadata
    metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    persona = relationship("Persona", back_populates="knowledge_bases")

    def __repr__(self):
        return f"<KnowledgeBase(id={self.id}, persona_id={self.persona_id}, type={self.source_type})>"
