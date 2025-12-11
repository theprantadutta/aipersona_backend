"""Social service for business logic"""
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from sqlalchemy.exc import IntegrityError
from app.models.social import PersonaLike, PersonaFavorite, UserFollow, PersonaView, UserBlock, ContentReport, UserActivity
from app.models.persona import Persona
from app.models.user import User
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime
import uuid
import logging
import json

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

    def get_user_favorites(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get favorited personas for a user with details
        Returns list of favorited personas with creator info
        Supports pagination with limit and offset
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
        ).limit(limit).offset(offset).all()

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

    def get_user_followers(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get list of users following this user
        Supports pagination with limit and offset
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
        ).limit(limit).offset(offset).all()

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

    def get_user_following(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get list of users this user is following
        Supports pagination with limit and offset
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
        ).limit(limit).offset(offset).all()

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
            "bio": user.bio,  # User bio/description
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

    # =========================================================================
    # USER BLOCKING
    # =========================================================================

    def toggle_user_block(
        self,
        blocker_id: str,
        blocked_id: str,
        reason: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Toggle block on a user
        Returns (is_blocked: bool, message: str)
        """
        try:
            blocker_uuid = uuid.UUID(blocker_id) if isinstance(blocker_id, str) else blocker_id
            blocked_uuid = uuid.UUID(blocked_id) if isinstance(blocked_id, str) else blocked_id

            # Prevent self-block
            if blocker_uuid == blocked_uuid:
                raise ValueError("Cannot block yourself")

            # Verify user to block exists
            user_to_block = self.db.query(User).filter(User.id == blocked_uuid).first()
            if not user_to_block:
                raise ValueError("User not found")

            # Check if block exists
            existing_block = self.db.query(UserBlock).filter(
                UserBlock.blocker_id == blocker_uuid,
                UserBlock.blocked_id == blocked_uuid
            ).first()

            if existing_block:
                # Unblock
                self.db.delete(existing_block)
                self.db.commit()
                return False, "User unblocked"
            else:
                # Block
                new_block = UserBlock(
                    blocker_id=blocker_uuid,
                    blocked_id=blocked_uuid,
                    reason=reason
                )
                self.db.add(new_block)
                self.db.commit()
                return True, "User blocked"

        except IntegrityError as e:
            self.db.rollback()
            logger.error(f"Integrity error toggling block: {str(e)}")
            current_block = self.db.query(UserBlock).filter(
                UserBlock.blocker_id == blocker_uuid,
                UserBlock.blocked_id == blocked_uuid
            ).first()
            return current_block is not None, "Block status updated"
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error toggling user block: {str(e)}")
            raise

    def check_user_blocked(self, blocker_id: str, blocked_id: str) -> bool:
        """Check if blocker has blocked the blocked user"""
        blocker_uuid = uuid.UUID(blocker_id) if isinstance(blocker_id, str) else blocker_id
        blocked_uuid = uuid.UUID(blocked_id) if isinstance(blocked_id, str) else blocked_id

        block = self.db.query(UserBlock).filter(
            UserBlock.blocker_id == blocker_uuid,
            UserBlock.blocked_id == blocked_uuid
        ).first()

        return block is not None

    def get_blocked_users(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get list of users blocked by this user"""
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        blocked = self.db.query(
            UserBlock,
            User
        ).join(
            User, UserBlock.blocked_id == User.id
        ).filter(
            UserBlock.blocker_id == user_uuid
        ).order_by(
            desc(UserBlock.created_at)
        ).limit(limit).offset(offset).all()

        result = []
        for block, user in blocked:
            result.append({
                "user_id": str(user.id),
                "username": user.display_name,
                "email": user.email,
                "avatar_url": user.photo_url,
                "blocked_at": block.created_at,
                "reason": block.reason
            })

        return result

    # =========================================================================
    # CONTENT REPORTING
    # =========================================================================

    def create_report(
        self,
        reporter_id: str,
        content_id: str,
        content_type: str,
        reason: str,
        additional_info: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new content report"""
        try:
            reporter_uuid = uuid.UUID(reporter_id) if isinstance(reporter_id, str) else reporter_id

            # Verify reporter exists
            reporter = self.db.query(User).filter(User.id == reporter_uuid).first()
            if not reporter:
                raise ValueError("Reporter not found")

            # Create report
            report = ContentReport(
                reporter_id=reporter_uuid,
                content_id=content_id,
                content_type=content_type,
                reason=reason,
                additional_info=additional_info,
                status="pending"
            )

            self.db.add(report)
            self.db.commit()
            self.db.refresh(report)

            logger.info(f"Report created: {report.id} for {content_type}:{content_id}")

            return {
                "report_id": str(report.id),
                "message": "Report submitted successfully"
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating report: {str(e)}")
            raise

    def get_user_reports(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get reports submitted by a user"""
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        reports = self.db.query(ContentReport).filter(
            ContentReport.reporter_id == user_uuid
        ).order_by(
            desc(ContentReport.created_at)
        ).limit(limit).offset(offset).all()

        result = []
        for report in reports:
            result.append({
                "id": str(report.id),
                "content_id": report.content_id,
                "content_type": report.content_type,
                "reason": report.reason,
                "additional_info": report.additional_info,
                "status": report.status,
                "created_at": report.created_at,
                "reviewed_at": report.reviewed_at,
                "resolution": report.resolution
            })

        return result

    def get_all_reports(
        self,
        status: Optional[str] = None,
        content_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get all reports (admin only) with optional filters"""
        query = self.db.query(
            ContentReport,
            User
        ).join(
            User, ContentReport.reporter_id == User.id
        )

        if status:
            query = query.filter(ContentReport.status == status)
        if content_type:
            query = query.filter(ContentReport.content_type == content_type)

        # Get total count
        total = query.count()

        # Get paginated results
        reports = query.order_by(
            desc(ContentReport.created_at)
        ).limit(limit).offset(offset).all()

        result = []
        for report, reporter in reports:
            # Get reviewer info if exists
            reviewer_name = None
            if report.reviewed_by:
                reviewer = self.db.query(User).filter(User.id == report.reviewed_by).first()
                if reviewer:
                    reviewer_name = reviewer.display_name or reviewer.email

            result.append({
                "id": str(report.id),
                "reporter_id": str(report.reporter_id),
                "reporter_email": reporter.email,
                "reporter_name": reporter.display_name,
                "content_id": report.content_id,
                "content_type": report.content_type,
                "reason": report.reason,
                "additional_info": report.additional_info,
                "status": report.status,
                "created_at": report.created_at,
                "reviewed_at": report.reviewed_at,
                "reviewed_by": str(report.reviewed_by) if report.reviewed_by else None,
                "reviewer_name": reviewer_name,
                "resolution": report.resolution
            })

        return result, total

    def update_report_status(
        self,
        report_id: str,
        reviewer_id: str,
        status: str,
        resolution: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update report status (admin only)"""
        try:
            report_uuid = uuid.UUID(report_id) if isinstance(report_id, str) else report_id
            reviewer_uuid = uuid.UUID(reviewer_id) if isinstance(reviewer_id, str) else reviewer_id

            report = self.db.query(ContentReport).filter(ContentReport.id == report_uuid).first()
            if not report:
                raise ValueError("Report not found")

            # Validate status
            valid_statuses = ["pending", "under_review", "resolved", "dismissed"]
            if status not in valid_statuses:
                raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")

            report.status = status
            report.reviewed_by = reviewer_uuid
            report.reviewed_at = datetime.utcnow()
            if resolution:
                report.resolution = resolution

            self.db.commit()
            self.db.refresh(report)

            return {
                "id": str(report.id),
                "status": report.status,
                "message": f"Report status updated to {status}"
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating report status: {str(e)}")
            raise

    # =========================================================================
    # ACTIVITY FEED
    # =========================================================================

    def record_activity(
        self,
        user_id: str,
        activity_type: str,
        target_id: Optional[str] = None,
        target_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Record a user activity"""
        try:
            user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

            activity = UserActivity(
                user_id=user_uuid,
                activity_type=activity_type,
                target_id=target_id,
                target_type=target_type,
                metadata=json.dumps(metadata) if metadata else None
            )

            self.db.add(activity)
            self.db.commit()

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error recording activity: {str(e)}")
            return False

    def get_user_activity_feed(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get activity feed for a user"""
        user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

        # Get total count
        total = self.db.query(UserActivity).filter(
            UserActivity.user_id == user_uuid
        ).count()

        # Get activities
        activities = self.db.query(UserActivity).filter(
            UserActivity.user_id == user_uuid
        ).order_by(
            desc(UserActivity.created_at)
        ).limit(limit).offset(offset).all()

        result = []
        for activity in activities:
            # Get target info based on target_type
            target_name = None
            target_avatar = None

            if activity.target_id and activity.target_type:
                if activity.target_type == "persona":
                    try:
                        persona = self.db.query(Persona).filter(
                            Persona.id == uuid.UUID(activity.target_id)
                        ).first()
                        if persona:
                            target_name = persona.name
                            target_avatar = persona.image_path
                    except:
                        pass
                elif activity.target_type == "user":
                    try:
                        user = self.db.query(User).filter(
                            User.id == uuid.UUID(activity.target_id)
                        ).first()
                        if user:
                            target_name = user.display_name or user.email
                            target_avatar = user.photo_url
                    except:
                        pass

            result.append({
                "id": str(activity.id),
                "activity_type": activity.activity_type,
                "target_id": activity.target_id,
                "target_type": activity.target_type,
                "target_name": target_name,
                "target_avatar": target_avatar,
                "created_at": activity.created_at,
                "metadata": json.loads(activity.metadata) if activity.metadata else None
            })

        return result, total
