"""Social interaction schemas"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


class SocialInteraction(BaseModel):
    """Base social interaction"""
    user_id: str
    persona_id: Optional[str] = None
    target_user_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


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
