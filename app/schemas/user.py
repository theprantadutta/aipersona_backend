"""User schemas"""
from pydantic import BaseModel, EmailStr, UUID4, field_serializer
from datetime import datetime
from typing import Optional

from app.utils.time_utils import to_utc_isoformat


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr


class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str


class UserLogin(UserBase):
    """Schema for user login"""
    password: str


class UserResponse(UserBase):
    """Schema for user response (no password)"""
    id: UUID4
    created_at: datetime
    subscription_tier: str
    is_active: bool
    is_premium: bool

    # Firebase/Google authentication fields (like pinpoint)
    firebase_uid: Optional[str] = None
    auth_provider: str
    google_id: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    email_verified: bool

    @field_serializer('created_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_isoformat(value)

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user"""
    email: Optional[EmailStr] = None
    password: Optional[str] = None


# Firebase Auth schemas (like pinpoint)
class FirebaseAuthRequest(BaseModel):
    """Schema for Firebase token authentication"""
    firebase_token: str


class GoogleAuthRequest(BaseModel):
    """Schema for Google Sign-In authentication"""
    firebase_token: str


class LinkAccountRequest(BaseModel):
    """Schema for linking Google account to existing account"""
    firebase_token: str
    password: str


class AuthProvidersResponse(BaseModel):
    """Schema for auth providers response"""
    providers: list[str]  # ['email', 'google']
    has_password: bool
    has_google: bool
