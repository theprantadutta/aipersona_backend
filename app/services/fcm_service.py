"""Firebase Cloud Messaging service"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import os

from app.models.user import User
from app.models.notification import FCMToken
from app.schemas.notification import RegisterFCMTokenRequest
from app.config import settings

logger = logging.getLogger(__name__)


class FCMService:
    """Service for managing Firebase Cloud Messaging"""

    def __init__(self, db: Session):
        self.db = db
        self._firebase_app = None

    def _get_firebase_app(self):
        """Initialize Firebase Admin SDK (lazy loading)"""
        if self._firebase_app is None:
            try:
                import firebase_admin
                from firebase_admin import credentials

                if not firebase_admin._apps:
                    # Check if credentials file exists
                    if os.path.exists(settings.FCM_CREDENTIALS_PATH):
                        cred = credentials.Certificate(settings.FCM_CREDENTIALS_PATH)
                        self._firebase_app = firebase_admin.initialize_app(cred)
                        logger.info("Firebase Admin SDK initialized successfully")
                    else:
                        logger.warning(f"FCM credentials file not found at {settings.FCM_CREDENTIALS_PATH}")
                        logger.info("Running in development mode - notifications will be logged only")
                else:
                    self._firebase_app = firebase_admin.get_app()

            except ImportError:
                logger.error("firebase-admin package not installed. Run: pip install firebase-admin")
                logger.info("Running in development mode - notifications will be logged only")
            except Exception as e:
                logger.error(f"Failed to initialize Firebase Admin SDK: {str(e)}")

        return self._firebase_app

    def register_token(
        self,
        user_id: str,
        token_data: RegisterFCMTokenRequest
    ) -> FCMToken:
        """
        Register or update FCM token for a user

        Args:
            user_id: User ID
            token_data: FCM token data

        Returns:
            FCM token record
        """
        # Check if token already exists
        existing_token = self.db.query(FCMToken).filter(
            FCMToken.fcm_token == token_data.fcm_token
        ).first()

        if existing_token:
            # Update existing token
            existing_token.user_id = user_id
            existing_token.device_id = token_data.device_id
            existing_token.platform = token_data.platform
            existing_token.is_active = True
            existing_token.last_used_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing_token)

            logger.info(f"Updated FCM token for user {user_id}, device {token_data.device_id}")
            return existing_token

        # Check if device already has a token
        device_token = self.db.query(FCMToken).filter(
            FCMToken.user_id == user_id,
            FCMToken.device_id == token_data.device_id
        ).first()

        if device_token:
            # Update device token
            device_token.fcm_token = token_data.fcm_token
            device_token.platform = token_data.platform
            device_token.is_active = True
            device_token.last_used_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(device_token)

            logger.info(f"Updated FCM token for user {user_id}, device {token_data.device_id}")
            return device_token

        # Create new token
        new_token = FCMToken(
            user_id=user_id,
            fcm_token=token_data.fcm_token,
            device_id=token_data.device_id,
            platform=token_data.platform
        )

        self.db.add(new_token)
        self.db.commit()
        self.db.refresh(new_token)

        logger.info(f"Registered new FCM token for user {user_id}, device {token_data.device_id}")
        return new_token

    def remove_token(self, user_id: str, device_id: str) -> bool:
        """
        Remove FCM token for a device

        Args:
            user_id: User ID
            device_id: Device ID

        Returns:
            True if removed successfully

        Raises:
            ValueError: If token not found
        """
        token = self.db.query(FCMToken).filter(
            FCMToken.user_id == user_id,
            FCMToken.device_id == device_id
        ).first()

        if not token:
            raise ValueError("FCM token not found for this device")

        self.db.delete(token)
        self.db.commit()

        logger.info(f"Removed FCM token for user {user_id}, device {device_id}")
        return True

    def get_user_tokens(self, user_id: str) -> List[FCMToken]:
        """
        Get all FCM tokens for a user

        Args:
            user_id: User ID

        Returns:
            List of FCM tokens
        """
        tokens = self.db.query(FCMToken).filter(
            FCMToken.user_id == user_id,
            FCMToken.is_active == True
        ).all()

        return tokens

    def send_notification(
        self,
        user_id: Optional[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send push notification to user(s)

        Args:
            user_id: User ID (None for broadcast to all users)
            title: Notification title
            body: Notification body
            data: Additional data payload
            image_url: Optional image URL

        Returns:
            Dictionary with send results
        """
        try:
            # Get Firebase app
            app = self._get_firebase_app()

            # Get target tokens
            if user_id:
                tokens = self.db.query(FCMToken).filter(
                    FCMToken.user_id == user_id,
                    FCMToken.is_active == True
                ).all()
            else:
                # Broadcast to all active tokens (limit to prevent abuse)
                tokens = self.db.query(FCMToken).filter(
                    FCMToken.is_active == True
                ).limit(1000).all()

            if not tokens:
                return {
                    "success": False,
                    "message": "No active FCM tokens found",
                    "sent_count": 0,
                    "failed_count": 0
                }

            token_strings = [token.fcm_token for token in tokens]

            # If Firebase is not initialized, just log
            if app is None:
                logger.info(f"[DEV MODE] Would send notification to {len(token_strings)} devices:")
                logger.info(f"  Title: {title}")
                logger.info(f"  Body: {body}")
                logger.info(f"  Data: {data}")

                return {
                    "success": True,
                    "message": f"Development mode - notification logged for {len(token_strings)} devices",
                    "sent_count": len(token_strings),
                    "failed_count": 0
                }

            # Send notification via FCM
            try:
                from firebase_admin import messaging

                # Build notification
                notification = messaging.Notification(
                    title=title,
                    body=body,
                    image=image_url
                )

                # Build message
                message = messaging.MulticastMessage(
                    notification=notification,
                    data=data or {},
                    tokens=token_strings
                )

                # Send
                response = messaging.send_multicast(message)

                # Update token last_used_at
                for token in tokens:
                    token.last_used_at = datetime.utcnow()
                self.db.commit()

                logger.info(f"Sent notification to {response.success_count}/{len(token_strings)} devices")

                return {
                    "success": True,
                    "message": f"Notification sent successfully",
                    "sent_count": response.success_count,
                    "failed_count": response.failure_count
                }

            except Exception as e:
                logger.error(f"Failed to send FCM notification: {str(e)}")
                raise ValueError(f"Failed to send notification: {str(e)}")

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error in send_notification: {str(e)}")
            raise ValueError(f"Notification service error: {str(e)}")

    def cleanup_inactive_tokens(self, days: int = 90) -> int:
        """
        Remove FCM tokens that haven't been used in X days

        Args:
            days: Number of days of inactivity before removal

        Returns:
            Number of tokens removed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        inactive_tokens = self.db.query(FCMToken).filter(
            FCMToken.last_used_at < cutoff_date
        ).all()

        count = len(inactive_tokens)

        for token in inactive_tokens:
            self.db.delete(token)

        self.db.commit()

        logger.info(f"Cleaned up {count} inactive FCM tokens")
        return count
