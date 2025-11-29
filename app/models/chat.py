"""Chat models"""
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base


class ChatSession(Base):
    """Chat session model"""

    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    persona_id = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), nullable=True, index=True)

    persona_name = Column(String(255), nullable=False)  # Cached for convenience

    # Deleted persona tracking - populated when persona is deleted
    deleted_persona_name = Column(String(255), nullable=True)  # Cached name when persona deleted
    deleted_persona_image = Column(String(500), nullable=True)  # Cached image path when deleted
    persona_deleted_at = Column(DateTime, nullable=True)  # When the persona was deleted

    # Status
    status = Column(String(50), default="active", nullable=False)  # active, archived, deleted
    is_pinned = Column(Boolean, default=False, nullable=False)

    # Metadata
    message_count = Column(Integer, default=0, nullable=False)
    meta_data = Column(JSON, nullable=True)  # Custom metadata (renamed to avoid SQLAlchemy conflict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    persona = relationship("Persona", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, persona={self.persona_name})>"


class ChatMessage(Base):
    """Chat message model"""

    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    sender_id = Column(UUID(as_uuid=True), nullable=False)  # User ID or Persona ID
    sender_type = Column(String(20), nullable=False)  # "user" or "ai"

    # Message content
    text = Column(Text, nullable=False)
    message_type = Column(String(50), default="text", nullable=False)  # text, image, file, voice

    # AI-specific fields
    sentiment = Column(String(50), nullable=True)  # positive, negative, neutral
    tokens_used = Column(Integer, default=0, nullable=False)  # For AI messages

    # Metadata
    meta_data = Column(JSON, nullable=True)  # Additional data (renamed to avoid SQLAlchemy conflict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ChatMessage(id={self.id}, session_id={self.session_id}, type={self.sender_type})>"


class MessageAttachment(Base):
    """Message attachment model for files, images, voice"""

    __tablename__ = "message_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True)

    # File information
    file_path = Column(String(500), nullable=False)  # Backend storage path
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # Bytes
    mime_type = Column(String(100), nullable=False)

    attachment_type = Column(String(50), nullable=False)  # image, audio, document, voice

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    message = relationship("ChatMessage", back_populates="attachments")

    def __repr__(self):
        return f"<MessageAttachment(id={self.id}, type={self.attachment_type}, file={self.file_name})>"
