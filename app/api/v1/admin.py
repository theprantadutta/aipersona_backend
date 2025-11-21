"""Admin dashboard API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.core.dependencies import get_admin_user
from app.models.user import User
from app.services.admin_service import AdminService
from app.schemas.admin import (
    UserListResponse,
    UserListItem,
    UpdateUserStatusRequest,
    UpdateUserStatusResponse,
    BusinessAnalyticsResponse,
    ModerationQueueResponse,
    ModerateContentRequest,
    ModerateContentResponse,
    SystemHealthResponse
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=UserListResponse)
def get_users(
    status: Optional[str] = Query(None, pattern="^(active|inactive)$"),
    subscription_tier: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search in email and display_name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get list of all users with filters (Admin only)

    - **status**: Filter by status (active, inactive)
    - **subscription_tier**: Filter by subscription tier
    - **search**: Search in email and display_name
    - **page**: Page number (1-indexed)
    - **page_size**: Number of users per page (max 100)

    Requires admin authentication
    """
    try:
        skip = (page - 1) * page_size
        service = AdminService(db)
        users, total = service.get_users(
            status=status,
            subscription_tier=subscription_tier,
            search=search,
            skip=skip,
            limit=page_size
        )

        total_pages = (total + page_size - 1) // page_size

        # Build response with usage data
        user_items = []
        for user in users:
            usage = user.usage_tracking
            user_items.append(
                UserListItem(
                    id=str(user.id),
                    email=user.email,
                    display_name=user.display_name,
                    auth_provider=user.auth_provider,
                    subscription_tier=user.subscription_tier,
                    is_active=user.is_active,
                    is_admin=user.is_admin,
                    created_at=user.created_at,
                    last_login=user.last_login,
                    messages_today=usage.messages_today if usage else 0,
                    personas_count=usage.personas_count if usage else 0
                )
            )

        return UserListResponse(
            users=user_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching users: {str(e)}"
        )


@router.put("/users/{user_id}/status", response_model=UpdateUserStatusResponse)
def update_user_status(
    user_id: str,
    request_data: UpdateUserStatusRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update user status (activate, suspend, ban) (Admin only)

    - **user_id**: ID of the user to update
    - **action**: Action to perform (activate, suspend, ban)
    - **reason**: Optional reason for the action

    Actions:
    - **activate**: Activate a suspended/banned user
    - **suspend**: Temporarily suspend user access
    - **ban**: Permanently ban user access

    Requires admin authentication
    """
    try:
        service = AdminService(db)
        user = service.update_user_status(
            user_id=user_id,
            action=request_data.action,
            reason=request_data.reason
        )

        return UpdateUserStatusResponse(
            user_id=str(user.id),
            email=user.email,
            is_active=user.is_active,
            action=request_data.action,
            message=f"User {request_data.action}d successfully"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user status: {str(e)}"
        )


@router.get("/analytics", response_model=BusinessAnalyticsResponse)
def get_business_analytics(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive business analytics (Admin only)

    Returns:
    - User metrics (total, active, new users)
    - Subscription metrics (by tier, premium vs free)
    - Revenue metrics (MRR, lifetime revenue estimates)
    - Usage metrics (messages, personas, sessions)
    - Engagement metrics (session length, activity)

    Requires admin authentication
    """
    try:
        service = AdminService(db)
        analytics = service.get_business_analytics()

        return BusinessAnalyticsResponse(**analytics)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching analytics: {str(e)}"
        )


@router.get("/content/moderation", response_model=ModerationQueueResponse)
def get_moderation_queue(
    content_type: Optional[str] = Query(
        None,
        pattern="^(persona|marketplace_listing|review)$",
        description="Filter by content type"
    ),
    status: str = Query(
        "pending",
        pattern="^(pending|approved|rejected)$",
        description="Filter by status"
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get content moderation queue (Admin only)

    - **content_type**: Filter by type (persona, marketplace_listing, review)
    - **status**: Filter by status (pending, approved, rejected)
    - **page**: Page number (1-indexed)
    - **page_size**: Number of items per page (max 100)

    Returns content that needs moderation approval

    Requires admin authentication
    """
    try:
        skip = (page - 1) * page_size
        service = AdminService(db)
        items, total = service.get_moderation_queue(
            content_type=content_type,
            status=status,
            skip=skip,
            limit=page_size
        )

        return ModerationQueueResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching moderation queue: {str(e)}"
        )


@router.post("/content/{content_type}/{content_id}/action", response_model=ModerateContentResponse)
def moderate_content(
    content_type: str,
    content_id: str,
    action_data: ModerateContentRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Moderate content (approve, reject, delete) (Admin only)

    - **content_type**: Type of content (marketplace_listing, review, etc.)
    - **content_id**: ID of the content to moderate
    - **action**: Action to perform (approve, reject, delete)
    - **reason**: Optional reason for the action

    Actions:
    - **approve**: Approve content for public visibility
    - **reject**: Reject content (keep but hide)
    - **delete**: Permanently delete content

    Requires admin authentication
    """
    try:
        service = AdminService(db)
        result = service.moderate_content(
            content_type=content_type,
            content_id=content_id,
            action=action_data.action,
            reason=action_data.reason
        )

        return ModerateContentResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error moderating content: {str(e)}"
        )


@router.get("/health", response_model=SystemHealthResponse)
def get_system_health(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get system health metrics (Admin only)

    Returns:
    - Database connection status
    - Redis connection status
    - API availability
    - Request metrics
    - System uptime

    Requires admin authentication
    """
    try:
        service = AdminService(db)
        health = service.get_system_health()

        return SystemHealthResponse(**health)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching system health: {str(e)}"
        )
