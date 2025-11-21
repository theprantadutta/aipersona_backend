"""Notification schemas"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class RegisterFCMTokenRequest(BaseModel):
    """Register FCM token for push notifications"""
    fcm_token: str = Field(..., min_length=10, max_length=500)
    device_id: str = Field(..., min_length=1, max_length=255)
    platform: str = Field(..., pattern="^(android|ios|web)$")


class RegisterFCMTokenResponse(BaseModel):
    """FCM token registration response"""
    id: str
    device_id: str
    platform: str
    message: str

    class Config:
        from_attributes = True


class FCMTokenResponse(BaseModel):
    """FCM token details"""
    id: str
    device_id: str
    platform: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime

    class Config:
        from_attributes = True


class UserTokensResponse(BaseModel):
    """List of user's FCM tokens"""
    tokens: List[FCMTokenResponse]
    total: int


class SendNotificationRequest(BaseModel):
    """Send notification request (admin only)"""
    user_id: Optional[str] = Field(None, description="Specific user ID (leave empty for broadcast)")
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=500)
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data payload")
    image_url: Optional[str] = Field(None, description="Notification image URL")


class SendNotificationResponse(BaseModel):
    """Notification send result"""
    success: bool
    message: str
    sent_count: int
    failed_count: int
