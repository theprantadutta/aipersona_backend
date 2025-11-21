"""Marketplace API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.marketplace_service import MarketplaceService
from app.schemas.marketplace import (
    MarketplacePersonaPublish,
    MarketplacePersonaResponse,
    MarketplacePersonaListResponse,
    PurchasePersonaRequest,
    PurchaseResponse,
    UserPurchasesResponse,
    ReviewCreate,
    ReviewResponse,
    ReviewListResponse
)

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.get("/personas", response_model=MarketplacePersonaListResponse)
def get_marketplace_personas(
    category: Optional[str] = Query(None, description="Filter by category"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    sort_by: str = Query("created_at", pattern="^(created_at|price|views|purchases)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all published marketplace personas with filters

    - **category**: Filter by persona category
    - **min_price**: Minimum price (inclusive)
    - **max_price**: Maximum price (inclusive)
    - **search**: Search term for title and description
    - **sort_by**: Sort field (created_at, price, views, purchases)
    - **page**: Page number (1-indexed)
    - **page_size**: Number of personas per page (max 100)

    Only returns approved personas
    No authentication required
    """
    try:
        skip = (page - 1) * page_size
        service = MarketplaceService(db)
        personas, total = service.get_marketplace_personas(
            category=category,
            min_price=min_price,
            max_price=max_price,
            search=search,
            sort_by=sort_by,
            skip=skip,
            limit=page_size
        )

        total_pages = (total + page_size - 1) // page_size

        return MarketplacePersonaListResponse(
            personas=[MarketplacePersonaResponse.model_validate(p) for p in personas],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching marketplace personas: {str(e)}"
        )


@router.get("/personas/{persona_id}", response_model=MarketplacePersonaResponse)
def get_marketplace_persona(
    persona_id: str,
    increment_views: bool = Query(True, description="Increment view count"),
    db: Session = Depends(get_db)
):
    """
    Get a specific marketplace persona by ID

    - **persona_id**: Marketplace persona ID
    - **increment_views**: Whether to increment view count (default: true)

    No authentication required
    """
    try:
        service = MarketplaceService(db)
        persona = service.get_marketplace_persona(
            persona_id=persona_id,
            increment_views=increment_views
        )

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Marketplace persona not found"
            )

        return MarketplacePersonaResponse.model_validate(persona)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching marketplace persona: {str(e)}"
        )


@router.post("/personas", response_model=MarketplacePersonaResponse, status_code=status.HTTP_201_CREATED)
def publish_persona(
    publish_data: MarketplacePersonaPublish,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Publish a persona to the marketplace

    - **persona_id**: ID of the persona to publish (must be owned by user)
    - **title**: Marketplace listing title
    - **description**: Detailed description of the persona
    - **category**: Category for classification
    - **pricing_type**: "free" or "one_time"
    - **price**: Price in USD (must be 0 for free, >0 for one_time)

    The persona must exist and belong to the current user
    Cannot publish the same persona twice
    """
    try:
        service = MarketplaceService(db)
        listing = service.publish_persona(
            user_id=str(current_user.id),
            publish_data=publish_data
        )

        return MarketplacePersonaResponse.model_validate(listing)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error publishing persona: {str(e)}"
        )


@router.delete("/personas/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
def unpublish_persona(
    persona_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove a persona from the marketplace

    - **persona_id**: Marketplace persona ID

    Only the seller can unpublish their own personas
    """
    try:
        service = MarketplaceService(db)
        service.unpublish_persona(
            persona_id=persona_id,
            user_id=str(current_user.id)
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
            detail=f"Error unpublishing persona: {str(e)}"
        )


@router.post("/purchase", response_model=PurchaseResponse)
def purchase_persona(
    purchase_data: PurchasePersonaRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Purchase a marketplace persona

    - **marketplace_persona_id**: ID of the marketplace persona to purchase

    This will:
    1. Create a purchase record
    2. Clone the persona to the buyer's account
    3. Increment the purchase count

    Cannot purchase:
    - Your own personas
    - Personas you've already purchased
    - Non-existent or non-approved personas
    """
    try:
        service = MarketplaceService(db)
        purchase = service.purchase_persona(
            user_id=str(current_user.id),
            marketplace_persona_id=purchase_data.marketplace_persona_id
        )

        # Get the marketplace persona for response details
        marketplace_persona = service.get_marketplace_persona(
            persona_id=purchase_data.marketplace_persona_id,
            increment_views=False
        )

        return PurchaseResponse(
            id=str(purchase.id),
            marketplace_persona_id=str(purchase.marketplace_persona_id),
            persona_id=str(marketplace_persona.persona_id),
            amount=purchase.amount,
            purchased_at=purchase.purchased_at,
            message="Persona purchased successfully! Check your personas list."
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error purchasing persona: {str(e)}"
        )


@router.get("/purchases", response_model=UserPurchasesResponse)
def get_user_purchases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all marketplace purchases made by the current user

    Returns purchase history in reverse chronological order
    """
    try:
        service = MarketplaceService(db)
        purchases = service.get_user_purchases(user_id=str(current_user.id))

        purchase_responses = []
        for purchase in purchases:
            # Get marketplace persona details
            marketplace_persona = service.get_marketplace_persona(
                persona_id=str(purchase.marketplace_persona_id),
                increment_views=False
            )

            purchase_responses.append(
                PurchaseResponse(
                    id=str(purchase.id),
                    marketplace_persona_id=str(purchase.marketplace_persona_id),
                    persona_id=str(marketplace_persona.persona_id) if marketplace_persona else "",
                    amount=purchase.amount,
                    purchased_at=purchase.purchased_at,
                    message=""
                )
            )

        return UserPurchasesResponse(
            purchases=purchase_responses,
            total=len(purchase_responses)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching purchases: {str(e)}"
        )


@router.post("/review", response_model=ReviewResponse)
def add_review(
    review_data: ReviewCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add or update a review for a marketplace persona

    - **marketplace_persona_id**: ID of the marketplace persona to review
    - **rating**: Rating from 1 to 5 stars
    - **review_text**: Optional review text (max 1000 characters)

    Requirements:
    - Must have purchased the persona before reviewing
    - Can only review once (subsequent calls update the existing review)
    """
    try:
        service = MarketplaceService(db)
        review = service.add_review(
            user_id=str(current_user.id),
            review_data=review_data
        )

        return ReviewResponse.model_validate(review)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding review: {str(e)}"
        )


@router.get("/reviews/{marketplace_persona_id}", response_model=ReviewListResponse)
def get_reviews(
    marketplace_persona_id: str,
    db: Session = Depends(get_db)
):
    """
    Get all reviews for a marketplace persona

    - **marketplace_persona_id**: ID of the marketplace persona

    Returns reviews in reverse chronological order with average rating
    No authentication required
    """
    try:
        service = MarketplaceService(db)
        reviews, avg_rating = service.get_reviews(marketplace_persona_id)

        return ReviewListResponse(
            reviews=[ReviewResponse.model_validate(r) for r in reviews],
            total=len(reviews),
            average_rating=avg_rating
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching reviews: {str(e)}"
        )
