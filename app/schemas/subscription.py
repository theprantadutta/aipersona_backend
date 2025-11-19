"""Schemas for Subscription endpoints"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SubscriptionPlan(BaseModel):
    """Subscription plan details"""
    id: str
    name: str
    description: str
    price: float
    currency: str
    duration: str  # "daily", "monthly", "yearly", "lifetime"
    features: List[str]
    google_play_product_id: str


class SubscriptionPlansResponse(BaseModel):
    """Response with all available plans"""
    plans: List[SubscriptionPlan]


class VerifyPurchaseRequest(BaseModel):
    """Request to verify a Google Play purchase"""
    purchase_token: str = Field(..., description="Google Play purchase token")
    product_id: str = Field(..., description="Google Play product ID")
    package_name: str = Field(..., description="App package name")


class SubscriptionStatusResponse(BaseModel):
    """User's subscription status"""
    subscription_tier: str
    is_premium: bool
    is_active: bool
    expires_at: Optional[datetime] = None
    grace_period_ends_at: Optional[datetime] = None
    status: str  # "free", "active", "active_lifetime", "grace_period", "expired"
    auto_renewing: Optional[bool] = None


class VerifyPurchaseResponse(BaseModel):
    """Response after purchase verification"""
    success: bool
    message: str
    subscription_status: SubscriptionStatusResponse


class SubscriptionEventResponse(BaseModel):
    """Subscription event history"""
    id: str
    user_id: str
    event_type: str  # purchased, renewed, cancelled, expired, refunded
    product_id: str
    purchase_token: str
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CancelSubscriptionResponse(BaseModel):
    """Response after subscription cancellation"""
    success: bool
    message: str
    will_expire_at: Optional[datetime] = None
