"""Subscription API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.subscription_service import SubscriptionService
from app.schemas.subscription import (
    SubscriptionPlansResponse,
    SubscriptionPlan,
    VerifyPurchaseRequest,
    VerifyPurchaseResponse,
    SubscriptionStatusResponse,
    SubscriptionEventResponse,
    CancelSubscriptionResponse
)

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/plans", response_model=SubscriptionPlansResponse)
def get_subscription_plans(db: Session = Depends(get_db)):
    """
    Get all available subscription plans

    Returns all subscription tiers with pricing and features
    No authentication required
    """
    try:
        service = SubscriptionService(db)
        plans = service.get_all_plans()

        return SubscriptionPlansResponse(plans=plans)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching subscription plans: {str(e)}"
        )


@router.post("/verify", response_model=VerifyPurchaseResponse)
async def verify_purchase(
    purchase_data: VerifyPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify a Google Play purchase and activate subscription

    - **purchase_token**: Google Play purchase token
    - **product_id**: Google Play product ID
    - **package_name**: App package name

    This endpoint:
    1. Verifies the purchase with Google Play API
    2. Updates the user's subscription tier
    3. Sets the expiration date
    4. Creates a subscription event record

    Returns the updated subscription status
    """
    try:
        service = SubscriptionService(db)
        result = await service.verify_purchase(
            user_id=str(current_user.id),
            purchase_data=purchase_data
        )

        subscription_status = SubscriptionStatusResponse(
            subscription_tier=result["subscription_tier"],
            is_premium=result["is_premium"],
            is_active=result["is_premium"],
            expires_at=result.get("expires_at"),
            grace_period_ends_at=None,
            status="active_lifetime" if result["subscription_tier"] == "lifetime" else "active",
            auto_renewing=True
        )

        return VerifyPurchaseResponse(
            success=result["success"],
            message=result["message"],
            subscription_status=subscription_status
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying purchase: {str(e)}"
        )


@router.get("/status", response_model=SubscriptionStatusResponse)
def get_subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the current user's subscription status

    Returns:
    - Subscription tier
    - Premium status
    - Expiration date
    - Grace period status
    - Auto-renewal status
    """
    try:
        service = SubscriptionService(db)
        status_data = service.get_subscription_status(str(current_user.id))

        return SubscriptionStatusResponse(**status_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching subscription status: {str(e)}"
        )


@router.post("/cancel", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel the current user's subscription

    User will retain access until the end of their current billing period
    This does not issue a refund - user should request refund through Google Play
    """
    try:
        service = SubscriptionService(db)
        result = await service.cancel_subscription(str(current_user.id))

        return CancelSubscriptionResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling subscription: {str(e)}"
        )


@router.get("/history", response_model=List[SubscriptionEventResponse])
def get_subscription_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get subscription event history for the current user

    Returns all subscription events (purchases, renewals, cancellations, etc.)
    in reverse chronological order
    """
    try:
        service = SubscriptionService(db)
        events = service.get_user_subscription_events(
            user_id=str(current_user.id),
            limit=limit
        )

        return [SubscriptionEventResponse.model_validate(e) for e in events]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching subscription history: {str(e)}"
        )
