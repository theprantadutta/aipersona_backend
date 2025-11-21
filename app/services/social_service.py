"""Social service for business logic"""
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from sqlalchemy.exc import IntegrityError
from app.models.social import PersonaLike, PersonaFavorite, UserFollow, PersonaView
from app.models.persona import Persona
from app.models.user import User
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


class SocialService:
    """Service for social interactions"""

    def __init__(self, db: Session):
        self.db = db

    def toggle_persona_like(self, user_id: str, persona_id: str) -> Tuple[bool, int]:
        """
        Toggle like on a persona
        Returns (is_liked: bool, like_count: int)
        """
        try:
            # Convert string IDs to UUID if needed
            user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            persona_uuid = uuid.UUID(persona_id) if isinstance(persona_id, str) else persona_id

            # Check if like exists
            existing_like = self.db.query(PersonaLike).filter(
                PersonaLike.user_id == user_uuid,
                PersonaLike.persona_id == persona_uuid
            ).first()

            # Get persona
            persona = self.db.query(Persona).filter(Persona.id == persona_uuid).first()
            if not persona:
                raise ValueError("Persona not found")

            if existing_like:
                # Unlike - remove the like
                self.db.delete(existing_like)
                persona.like_count = max(0, persona.like_count - 1)
                is_liked = False
            else:
                # Like - add the like
                new_like = PersonaLike(
                    user_id=user_uuid,
                    persona_id=persona_uuid
                )
                self.db.add(new_like)
                persona.like_count += 1
                is_liked = True

            self.db.commit()

            return is_liked, persona.like_count

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error toggling like: {str(e)}")
            # Re-query to get current state in case of race condition
            current_like = self.db.query(PersonaLike).filter(
                PersonaLike.user_id == user_uuid,
                PersonaLike.persona_id == persona_uuid
            ).first()
            persona = self.db.query(Persona).filter(Persona.id == persona_uuid).first()
            return current_like is not None, persona.like_count if persona else 0
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error toggling persona like: {str(e)}")
            raise

    def check_persona_liked(self, user_id: str, persona_id: str) -> bool:
        """
        Check if user has liked a persona
        """
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        persona_uuid = uuid.UUID(persona_id) if isinstance(persona_id, str) else persona_id

        like = self.db.query(PersonaLike).filter(
            PersonaLike.user_id == user_uuid,
            PersonaLike.persona_id == persona_uuid
        ).first()

        return like is not None

    def toggle_persona_favorite(self, user_id: str, persona_id: str) -> bool:
        """
        Toggle favorite on a persona
        Returns is_favorited: bool
        """
        try:
            user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            persona_uuid = uuid.UUID(persona_id) if isinstance(persona_id, str) else persona_id

            # Check if favorite exists
            existing_favorite = self.db.query(PersonaFavorite).filter(
                PersonaFavorite.user_id == user_uuid,
                PersonaFavorite.persona_id == persona_uuid
            ).first()

            # Verify persona exists
            persona = self.db.query(Persona).filter(Persona.id == persona_uuid).first()
            if not persona:
                raise ValueError("Persona not found")

            if existing_favorite:
                # Unfavorite
                self.db.delete(existing_favorite)
                is_favorited = False
            else:
                # Favorite
                new_favorite = PersonaFavorite(
                    user_id=user_uuid,
                    persona_id=persona_uuid
                )
                self.db.add(new_favorite)
                is_favorited = True

            self.db.commit()

            return is_favorited

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error toggling favorite: {str(e)}")
            # Re-query to get current state
            current_favorite = self.db.query(PersonaFavorite).filter(
                PersonaFavorite.user_id == user_uuid,
                PersonaFavorite.persona_id == persona_uuid
            ).first()
            return current_favorite is not None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error toggling persona favorite: {str(e)}")
            raise

    def check_persona_favorited(self, user_id: str, persona_id: str) -> bool:
        """
        Check if user has favorited a persona
        """
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        persona_uuid = uuid.UUID(persona_id) if isinstance(persona_id, str) else persona_id

        favorite = self.db.query(PersonaFavorite).filter(
            PersonaFavorite.user_id == user_uuid,
            PersonaFavorite.persona_id == persona_uuid
        ).first()

        return favorite is not None

    def get_user_favorites(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all favorited personas for a user with details
        Returns list of favorited personas with creator info
        """
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        # Join favorites with personas and users
        favorites = self.db.query(
            PersonaFavorite,
            Persona,
            User
        ).join(
            Persona, PersonaFavorite.persona_id == Persona.id
        ).join(
            User, Persona.creator_id == User.id
        ).filter(
            PersonaFavorite.user_id == user_uuid,
            Persona.status == "active"
        ).order_by(
            desc(PersonaFavorite.created_at)
        ).all()

        result = []
        for favorite, persona, creator in favorites:
            result.append({
                "persona_id": str(persona.id),
                "persona_name": persona.name,
                "persona_description": persona.description,
                "persona_avatar_url": persona.image_path,
                "creator_name": creator.display_name or creator.email.split('@')[0],
                "favorited_at": favorite.created_at
            })

        return result

    def toggle_user_follow(self, follower_id: str, following_id: str) -> Tuple[bool, int]:
        """
        Toggle follow on a user
        Returns (is_following: bool, follower_count: int)
        """
        try:
            follower_uuid = uuid.UUID(follower_id) if isinstance(follower_id, str) else follower_id
            following_uuid = uuid.UUID(following_id) if isinstance(following_id, str) else following_id

            # Prevent self-follow
            if follower_uuid == following_uuid:
                raise ValueError("Cannot follow yourself")

            # Check if follow exists
            existing_follow = self.db.query(UserFollow).filter(
                UserFollow.follower_id == follower_uuid,
                UserFollow.following_id == following_uuid
            ).first()

            # Verify user exists
            user_to_follow = self.db.query(User).filter(User.id == following_uuid).first()
            if not user_to_follow:
                raise ValueError("User not found")

            if existing_follow:
                # Unfollow
                self.db.delete(existing_follow)
                is_following = False
            else:
                # Follow
                new_follow = UserFollow(
                    follower_id=follower_uuid,
                    following_id=following_uuid
                )
                self.db.add(new_follow)
                is_following = True

            self.db.commit()

            # Get follower count for the user being followed
            follower_count = self.db.query(UserFollow).filter(
                UserFollow.following_id == following_uuid
            ).count()

            return is_following, follower_count

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error toggling follow: {str(e)}")
            # Re-query to get current state
            current_follow = self.db.query(UserFollow).filter(
                UserFollow.follower_id == follower_uuid,
                UserFollow.following_id == following_uuid
            ).first()
            follower_count = self.db.query(UserFollow).filter(
                UserFollow.following_id == following_uuid
            ).count()
            return current_follow is not None, follower_count
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error toggling user follow: {str(e)}")
            raise

    def check_user_following(self, follower_id: str, following_id: str) -> bool:
        """
        Check if follower is following user
        """
        follower_uuid = uuid.UUID(follower_id) if isinstance(follower_id, str) else follower_id
        following_uuid = uuid.UUID(following_id) if isinstance(following_id, str) else following_id

        follow = self.db.query(UserFollow).filter(
            UserFollow.follower_id == follower_uuid,
            UserFollow.following_id == following_uuid
        ).first()

        return follow is not None

    def get_user_followers(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get list of users following this user
        """
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        # Join to get follower user details
        followers = self.db.query(
            UserFollow,
            User
        ).join(
            User, UserFollow.follower_id == User.id
        ).filter(
            UserFollow.following_id == user_uuid
        ).order_by(
            desc(UserFollow.created_at)
        ).all()

        result = []
        for follow, user in followers:
            result.append({
                "user_id": str(user.id),
                "username": user.display_name,
                "email": user.email,
                "avatar_url": user.photo_url,
                "followed_at": follow.created_at
            })

        return result

    def get_user_following(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get list of users this user is following
        """
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        # Join to get following user details
        following = self.db.query(
            UserFollow,
            User
        ).join(
            User, UserFollow.following_id == User.id
        ).filter(
            UserFollow.follower_id == user_uuid
        ).order_by(
            desc(UserFollow.created_at)
        ).all()

        result = []
        for follow, user in following:
            result.append({
                "user_id": str(user.id),
                "username": user.display_name,
                "email": user.email,
                "avatar_url": user.photo_url,
                "followed_at": follow.created_at
            })

        return result

    def get_persona_social_stats(
        self,
        persona_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get social statistics for a persona
        Includes user-specific data if user_id provided
        """
        persona_uuid = uuid.UUID(persona_id) if isinstance(persona_id, str) else persona_id

        # Get persona
        persona = self.db.query(Persona).filter(Persona.id == persona_uuid).first()
        if not persona:
            raise ValueError("Persona not found")

        # Get like count (from persona model)
        like_count = persona.like_count

        # Get favorite count
        favorite_count = self.db.query(PersonaFavorite).filter(
            PersonaFavorite.persona_id == persona_uuid
        ).count()

        # Get clone count (from persona model)
        clone_count = persona.clone_count

        # Get view count
        view_count = self.db.query(PersonaView).filter(
            PersonaView.persona_id == persona_uuid
        ).count()

        # Check user-specific data
        is_liked = False
        is_favorited = False

        if user_id:
            user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            is_liked = self.check_persona_liked(str(user_uuid), str(persona_uuid))
            is_favorited = self.check_persona_favorited(str(user_uuid), str(persona_uuid))

        return {
            "persona_id": str(persona_id),
            "like_count": like_count,
            "favorite_count": favorite_count,
            "clone_count": clone_count,
            "view_count": view_count,
            "is_liked": is_liked,
            "is_favorited": is_favorited
        }

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Get user social profile with counts
        """
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        # Get user
        user = self.db.query(User).filter(User.id == user_uuid).first()
        if not user:
            raise ValueError("User not found")

        # Get follower count
        follower_count = self.db.query(UserFollow).filter(
            UserFollow.following_id == user_uuid
        ).count()

        # Get following count
        following_count = self.db.query(UserFollow).filter(
            UserFollow.follower_id == user_uuid
        ).count()

        # Get persona count
        persona_count = self.db.query(Persona).filter(
            Persona.creator_id == user_uuid,
            Persona.status == "active"
        ).count()

        # Get liked personas count
        liked_personas_count = self.db.query(PersonaLike).filter(
            PersonaLike.user_id == user_uuid
        ).count()

        return {
            "user_id": str(user.id),
            "username": user.display_name,
            "email": user.email,
            "avatar_url": user.photo_url,
            "bio": None,  # Add bio field to User model if needed
            "follower_count": follower_count,
            "following_count": following_count,
            "persona_count": persona_count,
            "liked_personas_count": liked_personas_count,
            "created_at": user.created_at
        }

    def record_persona_view(
        self,
        persona_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Record a view for a persona
        Can be anonymous (user_id = None) or authenticated
        """
        try:
            persona_uuid = uuid.UUID(persona_id) if isinstance(persona_id, str) else persona_id
            user_uuid = uuid.UUID(user_id) if user_id and isinstance(user_id, str) else user_id if user_id else None

            # Verify persona exists
            persona = self.db.query(Persona).filter(Persona.id == persona_uuid).first()
            if not persona:
                raise ValueError("Persona not found")

            # Create view record
            view = PersonaView(
                persona_id=persona_uuid,
                user_id=user_uuid  # Can be None for anonymous views
            )

            self.db.add(view)
            self.db.commit()

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error recording persona view: {str(e)}")
            raise
