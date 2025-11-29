"""Marketplace models"""
from sqlalchemy import Column, String, Numeric, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from app.database import Base
from app.utils.time_utils import utc_now


class MarketplacePersona(Base):
    """Marketplace persona listing"""

    __tablename__ = "marketplace_personas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id = Column(UUID(as_uuid=True), ForeignKey("personas.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Listing information
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(100), nullable=False)  # entertainment, education, business, etc.

    # Pricing
    pricing_type = Column(String(50), nullable=False)  # free, one_time
    price = Column(Numeric(10, 2), default=0.00, nullable=False)

    # Status
    status = Column(String(50), default="pending", nullable=False)  # pending, approved, rejected, suspended

    # Analytics
    views = Column(Integer, default=0, nullable=False)
    purchases = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    approved_at = Column(DateTime, nullable=True)

    # Relationships
    persona = relationship("Persona", back_populates="marketplace_listing")
    purchases = relationship("MarketplacePurchase", back_populates="marketplace_persona", cascade="all, delete-orphan")
    reviews = relationship("MarketplaceReview", back_populates="marketplace_persona", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MarketplacePersona(id={self.id}, title={self.title}, price={self.price})>"


class MarketplacePurchase(Base):
    """Marketplace purchase record"""

    __tablename__ = "marketplace_purchases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    marketplace_persona_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_personas.id", ondelete="CASCADE"), nullable=False, index=True)

    # Purchase details
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(50), default="completed", nullable=False)  # completed, refunded

    # Timestamps
    purchased_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    buyer = relationship("User", back_populates="marketplace_purchases")
    marketplace_persona = relationship("MarketplacePersona", back_populates="purchases")

    def __repr__(self):
        return f"<MarketplacePurchase(id={self.id}, buyer_id={self.buyer_id}, amount={self.amount})>"


class MarketplaceReview(Base):
    """Marketplace persona review"""

    __tablename__ = "marketplace_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    marketplace_persona_id = Column(UUID(as_uuid=True), ForeignKey("marketplace_personas.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Review
    rating = Column(Integer, nullable=False)  # 1-5 stars
    review_text = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    marketplace_persona = relationship("MarketplacePersona", back_populates="reviews")

    def __repr__(self):
        return f"<MarketplaceReview(id={self.id}, rating={self.rating})>"
