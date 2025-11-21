"""Admin dashboard schemas"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal


class UserListItem(BaseModel):
    """User list item for admin dashboard"""
    id: str
    email: str
    display_name: Optional[str]
    auth_provider: str
    subscription_tier: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]
    messages_today: Optional[int] = 0
    personas_count: Optional[int] = 0

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """List of users with pagination"""
    users: List[UserListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class UpdateUserStatusRequest(BaseModel):
    """Update user status (activate, suspend, ban)"""
    action: str = Field(..., pattern="^(activate|suspend|ban)$")
    reason: Optional[str] = Field(None, max_length=500)


class UpdateUserStatusResponse(BaseModel):
    """User status update confirmation"""
    user_id: str
    email: str
    is_active: bool
    action: str
    message: str


class BusinessAnalyticsResponse(BaseModel):
    """Business analytics dashboard data"""
    # User metrics
    total_users: int
    active_users_today: int
    new_users_this_week: int
    new_users_this_month: int

    # Subscription metrics
    free_tier_users: int
    premium_users: int
    daily_subscribers: int
    monthly_subscribers: int
    yearly_subscribers: int
    lifetime_subscribers: int

    # Revenue metrics (estimated based on subscriptions)
    monthly_recurring_revenue: Decimal
    total_lifetime_revenue: Decimal

    # Usage metrics
    total_messages_today: int
    total_messages_this_week: int
    total_messages_this_month: int
    avg_messages_per_user: float

    # Content metrics
    total_personas: int
    public_personas: int
    marketplace_listings: int

    # Engagement metrics
    active_chat_sessions: int
    total_chat_sessions: int
    avg_session_length_minutes: float


class ModerationQueueItem(BaseModel):
    """Content moderation queue item"""
    id: str
    type: str  # "persona", "marketplace_listing", "review", "chat_message"
    content_id: str
    user_id: str
    user_email: str
    title: Optional[str]
    description: Optional[str]
    status: str  # "pending", "approved", "rejected"
    created_at: datetime
    flagged_count: int = 0

    class Config:
        from_attributes = True


class ModerationQueueResponse(BaseModel):
    """Moderation queue with pagination"""
    items: List[ModerationQueueItem]
    total: int
    page: int
    page_size: int


class ModerateContentRequest(BaseModel):
    """Moderate content action"""
    action: str = Field(..., pattern="^(approve|reject|delete)$")
    reason: Optional[str] = Field(None, max_length=500)


class ModerateContentResponse(BaseModel):
    """Content moderation confirmation"""
    content_id: str
    content_type: str
    action: str
    message: str


class SystemHealthResponse(BaseModel):
    """System health metrics"""
    database_connected: bool
    redis_connected: bool
    gemini_api_available: bool
    total_requests_today: int
    avg_response_time_ms: float
    error_rate_percent: float
    uptime_hours: float
