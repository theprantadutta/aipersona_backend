"""Notifications API endpoints (FCM)"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user, get_admin_user
from app.models.user import User
from app.services.fcm_service import FCMService
from app.schemas.notification import (
    RegisterFCMTokenRequest,
    RegisterFCMTokenResponse,
    FCMTokenResponse,
    UserTokensResponse,
    SendNotificationRequest,
    SendNotificationResponse
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/register", response_model=RegisterFCMTokenResponse, status_code=status.HTTP_201_CREATED)
def register_fcm_token(
    token_data: RegisterFCMTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register FCM token for push notifications

    - **fcm_token**: FCM registration token from the device
    - **device_id**: Unique device identifier
    - **platform**: Device platform (android, ios, web)

    Registers or updates the FCM token for the current user's device.
    If the device already has a token, it will be updated.
    """
    try:
        service = FCMService(db)
        token = service.register_token(
            user_id=str(current_user.id),
            token_data=token_data
        )

        return RegisterFCMTokenResponse(
            id=str(token.id),
            device_id=token.device_id,
            platform=token.platform,
            message="FCM token registered successfully"
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering FCM token: {str(e)}"
        )


@router.delete("/token/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_fcm_token(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove FCM token for a device

    - **device_id**: Device identifier

    Removes the FCM token for the specified device.
    Use this when logging out or uninstalling the app.
    """
    try:
        service = FCMService(db)
        service.remove_token(
            user_id=str(current_user.id),
            device_id=device_id
        )

        return None

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error removing FCM token: {str(e)}"
        )


@router.get("/tokens", response_model=UserTokensResponse)
def get_user_tokens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all FCM tokens for the current user

    Returns all active FCM tokens registered for the current user's devices.
    """
    try:
        service = FCMService(db)
        tokens = service.get_user_tokens(user_id=str(current_user.id))

        return UserTokensResponse(
            tokens=[FCMTokenResponse.model_validate(t) for t in tokens],
            total=len(tokens)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching FCM tokens: {str(e)}"
        )


@router.post("/send", response_model=SendNotificationResponse)
def send_notification(
    notification_data: SendNotificationRequest,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Send push notification (Admin only)

    - **user_id**: Target user ID (leave empty for broadcast to all users)
    - **title**: Notification title
    - **body**: Notification body
    - **data**: Additional data payload (optional)
    - **image_url**: Notification image URL (optional)

    Sends a push notification via Firebase Cloud Messaging.

    **Broadcast**: If user_id is not provided, sends to all users (limited to 1000 devices).

    **Note**: In development mode (without FCM credentials), notifications are logged only.

    Requires admin authentication
    """
    try:
        service = FCMService(db)
        result = service.send_notification(
            user_id=notification_data.user_id,
            title=notification_data.title,
            body=notification_data.body,
            data=notification_data.data,
            image_url=notification_data.image_url
        )

        return SendNotificationResponse(
            success=result["success"],
            message=result["message"],
            sent_count=result["sent_count"],
            failed_count=result["failed_count"]
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending notification: {str(e)}"
        )
