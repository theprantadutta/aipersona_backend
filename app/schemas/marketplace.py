"""Marketplace schemas"""
from pydantic import BaseModel, Field, validator, field_serializer
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from app.utils.time_utils import to_utc_isoformat


class MarketplacePersonaBase(BaseModel):
    """Base marketplace persona schema"""
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10)
    category: str = Field(..., min_length=3, max_length=100)
    pricing_type: str = Field(..., pattern="^(free|one_time)$")
    price: Decimal = Field(default=Decimal("0.00"), ge=0)

    @validator("price")
    def validate_price(cls, v, values):
        if values.get("pricing_type") == "free" and v != 0:
            raise ValueError("Free listings must have price 0.00")
        if values.get("pricing_type") == "one_time" and v <= 0:
            raise ValueError("One-time purchase listings must have a positive price")
        return v


class MarketplacePersonaPublish(MarketplacePersonaBase):
    """Schema for publishing a persona to marketplace"""
    persona_id: str


class MarketplacePersonaResponse(MarketplacePersonaBase):
    """Marketplace persona response"""
    id: str
    persona_id: str
    seller_id: str
    status: str
    views: int
    purchases: int
    created_at: datetime
    approved_at: Optional[datetime]
    average_rating: Optional[float] = None
    review_count: int = 0

    @field_serializer('created_at', 'approved_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_isoformat(value)

    class Config:
        from_attributes = True


class MarketplacePersonaListResponse(BaseModel):
    """List of marketplace personas"""
    personas: List[MarketplacePersonaResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PurchasePersonaRequest(BaseModel):
    """Purchase a marketplace persona"""
    marketplace_persona_id: str


class PurchaseResponse(BaseModel):
    """Purchase confirmation"""
    id: str
    marketplace_persona_id: str
    persona_id: str
    amount: Decimal
    purchased_at: datetime
    message: str

    @field_serializer('purchased_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_isoformat(value)

    class Config:
        from_attributes = True


class UserPurchasesResponse(BaseModel):
    """User's marketplace purchases"""
    purchases: List[PurchaseResponse]
    total: int


class ReviewCreate(BaseModel):
    """Create a review"""
    marketplace_persona_id: str
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = Field(None, max_length=1000)


class ReviewResponse(BaseModel):
    """Review response"""
    id: str
    marketplace_persona_id: str
    reviewer_id: str
    rating: int
    review_text: Optional[str]
    created_at: datetime
    updated_at: datetime

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_isoformat(value)

    class Config:
        from_attributes = True


class ReviewListResponse(BaseModel):
    """List of reviews"""
    reviews: List[ReviewResponse]
    total: int
    average_rating: float
