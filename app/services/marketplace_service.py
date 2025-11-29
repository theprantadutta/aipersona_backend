"""Marketplace Service"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
from typing import List, Dict, Any, Optional, Tuple
import logging

from app.utils.time_utils import utc_now

from app.models.marketplace import MarketplacePersona, MarketplacePurchase, MarketplaceReview
from app.models.persona import Persona
from app.models.user import User
from app.schemas.marketplace import MarketplacePersonaPublish, ReviewCreate

logger = logging.getLogger(__name__)


class MarketplaceService:
    """Service for managing marketplace operations"""

    def __init__(self, db: Session):
        self.db = db

    def publish_persona(
        self,
        user_id: str,
        publish_data: MarketplacePersonaPublish
    ) -> MarketplacePersona:
        """
        Publish a persona to the marketplace

        Args:
            user_id: ID of the user publishing
            publish_data: Publishing data

        Returns:
            Created marketplace listing
        """
        # Check if persona exists and belongs to user
        persona = self.db.query(Persona).filter(
            Persona.id == publish_data.persona_id,
            Persona.user_id == user_id
        ).first()

        if not persona:
            raise ValueError("Persona not found or access denied")

        # Check if already published
        existing = self.db.query(MarketplacePersona).filter(
            MarketplacePersona.persona_id == publish_data.persona_id
        ).first()

        if existing:
            raise ValueError("Persona is already published to marketplace")

        # Create marketplace listing
        listing = MarketplacePersona(
            persona_id=publish_data.persona_id,
            seller_id=user_id,
            title=publish_data.title,
            description=publish_data.description,
            category=publish_data.category,
            pricing_type=publish_data.pricing_type,
            price=publish_data.price,
            status="approved"  # Auto-approve for now
        )

        if listing.status == "approved":
            listing.approved_at = utc_now()

        self.db.add(listing)
        self.db.commit()
        self.db.refresh(listing)

        logger.info(f"Persona {publish_data.persona_id} published to marketplace")

        return listing

    def get_marketplace_personas(
        self,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[MarketplacePersona], int]:
        """
        Get marketplace personas with filters

        Args:
            category: Filter by category
            min_price: Minimum price
            max_price: Maximum price
            search: Search in title/description
            sort_by: Sort field (created_at, price, views, purchases)
            skip: Records to skip
            limit: Max records to return

        Returns:
            Tuple of (personas list, total count)
        """
        query = self.db.query(MarketplacePersona).filter(
            MarketplacePersona.status == "approved"
        )

        # Apply filters
        if category:
            query = query.filter(MarketplacePersona.category == category)

        if min_price is not None:
            query = query.filter(MarketplacePersona.price >= min_price)

        if max_price is not None:
            query = query.filter(MarketplacePersona.price <= max_price)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    MarketplacePersona.title.ilike(search_pattern),
                    MarketplacePersona.description.ilike(search_pattern)
                )
            )

        # Get total count
        total = query.count()

        # Apply sorting
        if sort_by == "price":
            query = query.order_by(MarketplacePersona.price.asc())
        elif sort_by == "views":
            query = query.order_by(desc(MarketplacePersona.views))
        elif sort_by == "purchases":
            query = query.order_by(desc(MarketplacePersona.purchases))
        else:  # created_at
            query = query.order_by(desc(MarketplacePersona.created_at))

        # Apply pagination
        personas = query.offset(skip).limit(limit).all()

        return personas, total

    def get_marketplace_persona(
        self,
        persona_id: str,
        increment_views: bool = True
    ) -> Optional[MarketplacePersona]:
        """
        Get a single marketplace persona

        Args:
            persona_id: Marketplace persona ID
            increment_views: Whether to increment view count

        Returns:
            Marketplace persona or None
        """
        listing = self.db.query(MarketplacePersona).filter(
            MarketplacePersona.id == persona_id,
            MarketplacePersona.status == "approved"
        ).first()

        if listing and increment_views:
            listing.views += 1
            self.db.commit()

        return listing

    def unpublish_persona(
        self,
        persona_id: str,
        user_id: str
    ) -> bool:
        """
        Remove a persona from marketplace

        Args:
            persona_id: Marketplace persona ID
            user_id: ID of user (must be seller)

        Returns:
            True if unpublished successfully
        """
        listing = self.db.query(MarketplacePersona).filter(
            MarketplacePersona.id == persona_id,
            MarketplacePersona.seller_id == user_id
        ).first()

        if not listing:
            raise ValueError("Listing not found or access denied")

        self.db.delete(listing)
        self.db.commit()

        logger.info(f"Marketplace listing {persona_id} unpublished")

        return True

    def purchase_persona(
        self,
        user_id: str,
        marketplace_persona_id: str
    ) -> MarketplacePurchase:
        """
        Purchase a marketplace persona

        Args:
            user_id: Buyer user ID
            marketplace_persona_id: Marketplace persona ID

        Returns:
            Purchase record
        """
        # Get marketplace listing
        listing = self.db.query(MarketplacePersona).filter(
            MarketplacePersona.id == marketplace_persona_id,
            MarketplacePersona.status == "approved"
        ).first()

        if not listing:
            raise ValueError("Marketplace persona not found")

        # Check if user already purchased
        existing_purchase = self.db.query(MarketplacePurchase).filter(
            MarketplacePurchase.buyer_id == user_id,
            MarketplacePurchase.marketplace_persona_id == marketplace_persona_id
        ).first()

        if existing_purchase:
            raise ValueError("You have already purchased this persona")

        # Check if user is the seller
        if str(listing.seller_id) == user_id:
            raise ValueError("You cannot purchase your own persona")

        # Create purchase record
        purchase = MarketplacePurchase(
            buyer_id=user_id,
            marketplace_persona_id=marketplace_persona_id,
            amount=listing.price,
            status="completed"
        )

        self.db.add(purchase)

        # Increment purchase count
        listing.purchases += 1

        # Clone the persona for the buyer
        original_persona = listing.persona
        cloned_persona = Persona(
            user_id=user_id,
            name=f"{original_persona.name} (Clone)",
            bio=original_persona.bio,
            description=original_persona.description,
            avatar_url=original_persona.avatar_url,
            personality_traits=original_persona.personality_traits,
            language_style=original_persona.language_style,
            expertise=original_persona.expertise,
            status="active",
            is_public=False
        )

        self.db.add(cloned_persona)
        self.db.commit()
        self.db.refresh(purchase)

        logger.info(f"User {user_id} purchased marketplace persona {marketplace_persona_id}")

        return purchase

    def get_user_purchases(
        self,
        user_id: str
    ) -> List[MarketplacePurchase]:
        """
        Get all purchases by a user

        Args:
            user_id: User ID

        Returns:
            List of purchases
        """
        purchases = self.db.query(MarketplacePurchase).filter(
            MarketplacePurchase.buyer_id == user_id
        ).order_by(desc(MarketplacePurchase.purchased_at)).all()

        return purchases

    def add_review(
        self,
        user_id: str,
        review_data: ReviewCreate
    ) -> MarketplaceReview:
        """
        Add a review for a marketplace persona

        Args:
            user_id: Reviewer user ID
            review_data: Review data

        Returns:
            Created review
        """
        # Check if marketplace persona exists
        listing = self.db.query(MarketplacePersona).filter(
            MarketplacePersona.id == review_data.marketplace_persona_id
        ).first()

        if not listing:
            raise ValueError("Marketplace persona not found")

        # Check if user has purchased this persona
        purchase = self.db.query(MarketplacePurchase).filter(
            MarketplacePurchase.buyer_id == user_id,
            MarketplacePurchase.marketplace_persona_id == review_data.marketplace_persona_id
        ).first()

        if not purchase:
            raise ValueError("You must purchase this persona before reviewing it")

        # Check if user already reviewed
        existing_review = self.db.query(MarketplaceReview).filter(
            MarketplaceReview.marketplace_persona_id == review_data.marketplace_persona_id,
            MarketplaceReview.reviewer_id == user_id
        ).first()

        if existing_review:
            # Update existing review
            existing_review.rating = review_data.rating
            existing_review.review_text = review_data.review_text
            existing_review.updated_at = utc_now()
            self.db.commit()
            self.db.refresh(existing_review)
            return existing_review

        # Create new review
        review = MarketplaceReview(
            marketplace_persona_id=review_data.marketplace_persona_id,
            reviewer_id=user_id,
            rating=review_data.rating,
            review_text=review_data.review_text
        )

        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)

        logger.info(f"User {user_id} reviewed marketplace persona {review_data.marketplace_persona_id}")

        return review

    def get_reviews(
        self,
        marketplace_persona_id: str
    ) -> Tuple[List[MarketplaceReview], float]:
        """
        Get reviews for a marketplace persona

        Args:
            marketplace_persona_id: Marketplace persona ID

        Returns:
            Tuple of (reviews list, average rating)
        """
        reviews = self.db.query(MarketplaceReview).filter(
            MarketplaceReview.marketplace_persona_id == marketplace_persona_id
        ).order_by(desc(MarketplaceReview.created_at)).all()

        # Calculate average rating
        if reviews:
            avg_rating = sum(r.rating for r in reviews) / len(reviews)
        else:
            avg_rating = 0.0

        return reviews, avg_rating
