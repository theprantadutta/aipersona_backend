"""Social API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.social_service import SocialService
from app.schemas.social import (
    LikeToggleResponse,
    FavoriteToggleResponse,
    FollowToggleResponse,
    PersonaSocialStatsResponse,
    UserProfileResponse,
    FavoritesListResponse,
    FavoritedPersona,
    FollowersListResponse,
    FollowingListResponse,
    FollowerInfo
)

router = APIRouter(prefix="/social", tags=["social"])


@router.post("/personas/{persona_id}/like", response_model=LikeToggleResponse)
def toggle_persona_like(
    persona_id: str = Path(..., description="Persona ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle like on a persona

    - Returns whether persona is now liked and the total like count
    - Liking an already-liked persona will unlike it
    - Updates persona like_count
    """
    try:
        service = SocialService(db)
        is_liked, like_count = service.toggle_persona_like(
            user_id=str(current_user.id),
            persona_id=persona_id
        )

        message = "Persona liked" if is_liked else "Persona unliked"

        return LikeToggleResponse(
            is_liked=is_liked,
            like_count=like_count,
            message=message
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error toggling like: {str(e)}"
        )


@router.get("/personas/{persona_id}/liked", response_model=dict)
def check_persona_liked(
    persona_id: str = Path(..., description="Persona ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if current user has liked a persona

    Returns:
    - is_liked: boolean indicating if user has liked the persona
    """
    try:
        service = SocialService(db)
        is_liked = service.check_persona_liked(
            user_id=str(current_user.id),
            persona_id=persona_id
        )

        return {"is_liked": is_liked}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking like status: {str(e)}"
        )


@router.post("/personas/{persona_id}/favorite", response_model=FavoriteToggleResponse)
def toggle_persona_favorite(
    persona_id: str = Path(..., description="Persona ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle favorite on a persona

    - Returns whether persona is now favorited
    - Favoriting an already-favorited persona will unfavorite it
    - Favorites are private to the user
    """
    try:
        service = SocialService(db)
        is_favorited = service.toggle_persona_favorite(
            user_id=str(current_user.id),
            persona_id=persona_id
        )

        message = "Persona added to favorites" if is_favorited else "Persona removed from favorites"

        return FavoriteToggleResponse(
            is_favorited=is_favorited,
            message=message
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error toggling favorite: {str(e)}"
        )


@router.get("/personas/{persona_id}/favorited", response_model=dict)
def check_persona_favorited(
    persona_id: str = Path(..., description="Persona ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if current user has favorited a persona

    Returns:
    - is_favorited: boolean indicating if user has favorited the persona
    """
    try:
        service = SocialService(db)
        is_favorited = service.check_persona_favorited(
            user_id=str(current_user.id),
            persona_id=persona_id
        )

        return {"is_favorited": is_favorited}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking favorite status: {str(e)}"
        )


@router.get("/favorites", response_model=FavoritesListResponse)
def get_user_favorites(
    limit: int = Query(50, ge=1, le=100, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's favorited personas

    Returns:
    - List of favorited personas with details
    - Ordered by most recently favorited
    - Supports pagination with limit and offset
    """
    try:
        service = SocialService(db)
        favorites_data = service.get_user_favorites(
            user_id=str(current_user.id),
            limit=limit,
            offset=offset
        )

        favorites = [
            FavoritedPersona(
                persona_id=f["persona_id"],
                persona_name=f["persona_name"],
                persona_description=f["persona_description"],
                persona_avatar_url=f["persona_avatar_url"],
                creator_name=f["creator_name"],
                favorited_at=f["favorited_at"]
            )
            for f in favorites_data
        ]

        return FavoritesListResponse(
            favorites=favorites,
            total=len(favorites)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching favorites: {str(e)}"
        )


@router.post("/users/{user_id}/follow", response_model=FollowToggleResponse)
def toggle_user_follow(
    user_id: str = Path(..., description="User ID to follow/unfollow"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle follow on a user

    - Returns whether user is now being followed and follower count
    - Following an already-followed user will unfollow them
    - Cannot follow yourself
    """
    try:
        service = SocialService(db)
        is_following, follower_count = service.toggle_user_follow(
            follower_id=str(current_user.id),
            following_id=user_id
        )

        message = "User followed" if is_following else "User unfollowed"

        return FollowToggleResponse(
            is_following=is_following,
            follower_count=follower_count,
            message=message
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error toggling follow: {str(e)}"
        )


@router.get("/users/{user_id}/following", response_model=dict)
def check_user_following(
    user_id: str = Path(..., description="User ID to check"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if current user is following another user

    Returns:
    - is_following: boolean indicating if current user follows the specified user
    """
    try:
        service = SocialService(db)
        is_following = service.check_user_following(
            follower_id=str(current_user.id),
            following_id=user_id
        )

        return {"is_following": is_following}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking follow status: {str(e)}"
        )


@router.get("/users/{user_id}/followers", response_model=FollowersListResponse)
def get_user_followers(
    user_id: str = Path(..., description="User ID"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of followers for a user

    Returns:
    - List of users who follow the specified user
    - Ordered by most recent follow
    - Supports pagination with limit and offset
    """
    try:
        service = SocialService(db)
        followers_data = service.get_user_followers(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        followers = [
            FollowerInfo(
                user_id=f["user_id"],
                username=f["username"],
                email=f["email"],
                avatar_url=f["avatar_url"],
                followed_at=f["followed_at"]
            )
            for f in followers_data
        ]

        return FollowersListResponse(
            followers=followers,
            total=len(followers)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching followers: {str(e)}"
        )


@router.get("/users/{user_id}/following-list", response_model=FollowingListResponse)
def get_user_following_list(
    user_id: str = Path(..., description="User ID"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of users that a user is following

    Returns:
    - List of users that the specified user follows
    - Ordered by most recent follow
    - Supports pagination with limit and offset
    """
    try:
        service = SocialService(db)
        following_data = service.get_user_following(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        following = [
            FollowerInfo(
                user_id=f["user_id"],
                username=f["username"],
                email=f["email"],
                avatar_url=f["avatar_url"],
                followed_at=f["followed_at"]
            )
            for f in following_data
        ]

        return FollowingListResponse(
            following=following,
            total=len(following)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching following list: {str(e)}"
        )


@router.get("/personas/{persona_id}/stats", response_model=PersonaSocialStatsResponse)
def get_persona_stats(
    persona_id: str = Path(..., description="Persona ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get social statistics for a persona

    Returns:
    - like_count: Total number of likes
    - favorite_count: Total number of favorites
    - clone_count: Total number of times cloned
    - view_count: Total number of views
    - is_liked: Whether current user has liked this persona
    - is_favorited: Whether current user has favorited this persona
    """
    try:
        service = SocialService(db)
        stats = service.get_persona_social_stats(
            persona_id=persona_id,
            user_id=str(current_user.id)
        )

        return PersonaSocialStatsResponse(**stats)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching persona stats: {str(e)}"
        )


@router.get("/users/{user_id}/profile", response_model=UserProfileResponse)
def get_user_profile(
    user_id: str = Path(..., description="User ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user social profile

    Returns:
    - User information
    - follower_count: Number of followers
    - following_count: Number of users being followed
    - persona_count: Number of active personas created
    - liked_personas_count: Number of personas liked
    """
    try:
        service = SocialService(db)
        profile = service.get_user_profile(user_id=user_id)

        return UserProfileResponse(**profile)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user profile: {str(e)}"
        )


@router.post("/personas/{persona_id}/view", response_model=dict)
def record_persona_view(
    persona_id: str = Path(..., description="Persona ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record a view for a persona

    - Increments view count for analytics
    - Tracks which user viewed (for authenticated views)
    - Can be called when user opens persona details
    """
    try:
        service = SocialService(db)
        success = service.record_persona_view(
            persona_id=persona_id,
            user_id=str(current_user.id)
        )

        return {
            "success": success,
            "message": "View recorded successfully"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error recording view: {str(e)}"
        )
