"""File storage models"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base


class UploadedFile(Base):
    """Backend file storage model"""

    __tablename__ = "uploaded_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # File information
    file_path = Column(String(500), nullable=False)  # Relative path in uploads/ directory
    original_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # Bytes
    mime_type = Column(String(100), nullable=False)

    # Category
    category = Column(String(50), nullable=False)  # avatar, persona_image, chat_attachment, knowledge_base

    # Reference to what it's attached to
    reference_type = Column(String(50), nullable=True)  # persona, message, user_avatar, knowledge_base
    reference_id = Column(UUID(as_uuid=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="uploaded_files")

    def __repr__(self):
        return f"<UploadedFile(id={self.id}, name={self.original_name}, category={self.category})>"
