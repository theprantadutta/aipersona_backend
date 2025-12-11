"""Social interaction schemas"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from app.utils.time_utils import utc_now


class SocialInteraction(BaseModel):
    """Base social interaction"""
    user_id: str
    persona_id: Optional[str] = None
    target_user_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now)


class LikeToggleResponse(BaseModel):
    """Response for like toggle"""
    is_liked: bool
    like_count: int
    message: str


class FavoriteToggleResponse(BaseModel):
    """Response for favorite toggle"""
    is_favorited: bool
    message: str


class FollowToggleResponse(BaseModel):
    """Response for follow toggle"""
    is_following: bool
    follower_count: int
    message: str


class UserProfileResponse(BaseModel):
    """User social profile"""
    user_id: str
    username: Optional[str] = None
    email: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    follower_count: int = 0
    following_count: int = 0
    persona_count: int = 0
    liked_personas_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class PersonaSocialStatsResponse(BaseModel):
    """Persona social statistics"""
    persona_id: str
    like_count: int = 0
    favorite_count: int = 0
    clone_count: int = 0
    view_count: int = 0
    is_liked: bool = False
    is_favorited: bool = False


class FavoritedPersona(BaseModel):
    """Favorited persona info"""
    persona_id: str
    persona_name: str
    persona_description: Optional[str] = None
    persona_avatar_url: Optional[str] = None
    creator_name: Optional[str] = None
    favorited_at: datetime


class FavoritesListResponse(BaseModel):
    """List of favorited personas"""
    favorites: List[FavoritedPersona]
    total: int


class FollowerInfo(BaseModel):
    """Follower/following user info"""
    user_id: str
    username: Optional[str] = None
    email: str
    avatar_url: Optional[str] = None
    followed_at: datetime


class FollowersListResponse(BaseModel):
    """List of followers"""
    followers: List[FollowerInfo]
    total: int


class FollowingListResponse(BaseModel):
    """List of users being followed"""
    following: List[FollowerInfo]
    total: int


# User Blocking Schemas

class BlockUserRequest(BaseModel):
    """Request to block a user"""
    reason: Optional[str] = Field(None, max_length=500, description="Optional reason for blocking")


class BlockToggleResponse(BaseModel):
    """Response for block toggle"""
    is_blocked: bool
    message: str


class BlockedUserInfo(BaseModel):
    """Blocked user info"""
    user_id: str
    username: Optional[str] = None
    email: str
    avatar_url: Optional[str] = None
    blocked_at: datetime
    reason: Optional[str] = None


class BlockedUsersListResponse(BaseModel):
    """List of blocked users"""
    blocked_users: List[BlockedUserInfo]
    total: int


# Content Reporting Schemas

class ReportContentRequest(BaseModel):
    """Request to report content"""
    content_id: str = Field(..., description="ID of the content being reported")
    content_type: str = Field(..., description="Type of content: persona, user, conversation, message")
    reason: str = Field(..., description="Reason for report")
    additional_info: Optional[str] = Field(None, max_length=2000, description="Additional details about the report")


class ReportResponse(BaseModel):
    """Response for report submission"""
    report_id: str
    message: str


class ReportInfo(BaseModel):
    """Report information"""
    id: str
    content_id: str
    content_type: str
    reason: str
    additional_info: Optional[str] = None
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    resolution: Optional[str] = None


class ReportsListResponse(BaseModel):
    """List of reports"""
    reports: List[ReportInfo]
    total: int


class AdminReportInfo(BaseModel):
    """Report info for admin view"""
    id: str
    reporter_id: str
    reporter_email: Optional[str] = None
    reporter_name: Optional[str] = None
    content_id: str
    content_type: str
    reason: str
    additional_info: Optional[str] = None
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    reviewer_name: Optional[str] = None
    resolution: Optional[str] = None


class AdminReportsListResponse(BaseModel):
    """Admin list of reports"""
    reports: List[AdminReportInfo]
    total: int


class UpdateReportStatusRequest(BaseModel):
    """Request to update report status"""
    status: str = Field(..., description="New status: under_review, resolved, dismissed")
    resolution: Optional[str] = Field(None, max_length=2000, description="Resolution notes")


# Activity Feed Schemas

class ActivityInfo(BaseModel):
    """Activity information"""
    id: str
    activity_type: str
    target_id: Optional[str] = None
    target_type: Optional[str] = None
    target_name: Optional[str] = None  # Name of persona/user for display
    target_avatar: Optional[str] = None  # Avatar URL for display
    created_at: datetime
    metadata: Optional[dict] = None


class ActivityFeedResponse(BaseModel):
    """Activity feed response"""
    activities: List[ActivityInfo]
    total: int
