"""Subscription service for Google Play purchases"""
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.subscription import SubscriptionEvent
from app.schemas.subscription import VerifyPurchaseRequest, SubscriptionPlan
from app.config import settings
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing Google Play subscriptions"""

    # Subscription plans configuration
    PLANS = {
        "premium_daily": {
            "id": "premium_daily",
            "name": "Premium Daily",
            "description": "Unlimited messages and personas for 24 hours",
            "price": 0.99,
            "currency": "USD",
            "duration": "daily",
            "duration_days": 1,
            "google_play_product_id": "com.aipersona.premium.daily",
            "features": [
                "Unlimited messages per day",
                "Unlimited personas",
                "Unlimited chat history",
                "All premium features",
                "Priority support"
            ]
        },
        "premium_monthly": {
            "id": "premium_monthly",
            "name": "Premium Monthly",
            "description": "Unlimited access for 30 days",
            "price": 9.99,
            "currency": "USD",
            "duration": "monthly",
            "duration_days": 30,
            "google_play_product_id": "com.aipersona.premium.monthly",
            "features": [
                "Unlimited messages per day",
                "Unlimited personas",
                "Unlimited chat history",
                "All premium features",
                "Priority support",
                "Export chat history"
            ]
        },
        "premium_yearly": {
            "id": "premium_yearly",
            "name": "Premium Yearly",
            "description": "Best value - save 50%",
            "price": 59.99,
            "currency": "USD",
            "duration": "yearly",
            "duration_days": 365,
            "google_play_product_id": "com.aipersona.premium.yearly",
            "features": [
                "Unlimited messages per day",
                "Unlimited personas",
                "Unlimited chat history",
                "All premium features",
                "Priority support",
                "Export chat history",
                "Early access to new features"
            ]
        },
        "lifetime": {
            "id": "lifetime",
            "name": "Lifetime Premium",
            "description": "One-time payment, lifetime access",
            "price": 149.99,
            "currency": "USD",
            "duration": "lifetime",
            "duration_days": None,
            "google_play_product_id": "com.aipersona.premium.lifetime",
            "features": [
                "Unlimited messages per day",
                "Unlimited personas",
                "Unlimited chat history",
                "All premium features",
                "Priority support",
                "Export chat history",
                "Early access to new features",
                "Lifetime updates"
            ]
        }
    }

    def __init__(self, db: Session):
        self.db = db

    def get_all_plans(self) -> List[SubscriptionPlan]:
        """Get all available subscription plans"""
        plans = []
        for plan_data in self.PLANS.values():
            plans.append(SubscriptionPlan(**plan_data))
        return plans

    def get_plan_by_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get plan details by ID"""
        return self.PLANS.get(plan_id)

    def get_plan_by_product_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get plan by Google Play product ID"""
        for plan in self.PLANS.values():
            if plan["google_play_product_id"] == product_id:
                return plan
        return None

    async def verify_purchase(
        self,
        user_id: str,
        purchase_data: VerifyPurchaseRequest
    ) -> Dict[str, Any]:
        """
        Verify Google Play purchase and update user subscription

        In production, this would call Google Play Developer API
        For now, we'll implement a simplified version
        """
        try:
            # Get user
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            # Get plan by product ID
            plan = self.get_plan_by_product_id(purchase_data.product_id)
            if not plan:
                raise ValueError(f"Unknown product ID: {purchase_data.product_id}")

            # Verify with Google Play API
            logger.info(f"Verifying purchase for user {user_id}, product {purchase_data.product_id}")

            # Check if Google Play service account file exists
            if not os.path.exists(settings.GOOGLE_PLAY_SERVICE_ACCOUNT_PATH):
                logger.warning(f"Google Play service account file not found at {settings.GOOGLE_PLAY_SERVICE_ACCOUNT_PATH}")
                logger.info("Falling back to development mode - accepting all purchases")
                # Development mode: Accept all purchases
                verification_result = {
                    "kind": "androidpublisher#subscriptionPurchase",
                    "startTimeMillis": str(int(datetime.utcnow().timestamp() * 1000)),
                    "expiryTimeMillis": str(int((datetime.utcnow() + timedelta(days=plan["duration_days"])).timestamp() * 1000)),
                    "autoRenewing": True,
                    "priceCurrencyCode": "USD",
                    "paymentState": 1,  # Payment received
                    "orderId": purchase_data.purchase_token[:20]
                }
            else:
                # Production mode: Verify with Google Play API
                try:
                    from google.oauth2 import service_account
                    from googleapiclient.discovery import build

                    credentials = service_account.Credentials.from_service_account_file(
                        settings.GOOGLE_PLAY_SERVICE_ACCOUNT_PATH,
                        scopes=['https://www.googleapis.com/auth/androidpublisher']
                    )
                    service = build('androidpublisher', 'v3', credentials=credentials)

                    # Verify the purchase
                    verification_result = service.purchases().subscriptions().get(
                        packageName=settings.GOOGLE_PLAY_PACKAGE_NAME,
                        subscriptionId=purchase_data.product_id,
                        token=purchase_data.purchase_token
                    ).execute()

                    # Check if purchase is valid
                    if verification_result.get('paymentState') != 1:
                        raise ValueError("Purchase payment not received")

                    # Check if subscription is expired
                    expiry_time = int(verification_result.get('expiryTimeMillis', 0)) / 1000
                    if expiry_time < datetime.utcnow().timestamp():
                        raise ValueError("Subscription has expired")

                    logger.info(f"Successfully verified purchase with Google Play API")

                except ImportError:
                    logger.error("Google API client library not installed. Run: pip install google-api-python-client google-auth")
                    raise ValueError("Google Play verification not available - missing dependencies")
                except Exception as e:
                    logger.error(f"Google Play API verification failed: {str(e)}")
                    raise ValueError(f"Purchase verification failed: {str(e)}")

            # Calculate expiration date
            if plan["duration"] == "lifetime":
                expires_at = None
                subscription_tier = "lifetime"
            else:
                expires_at = datetime.utcnow() + timedelta(days=plan["duration_days"])
                subscription_tier = plan["id"]

            # Update user subscription
            user.subscription_tier = subscription_tier
            user.subscription_expires_at = expires_at
            user.google_play_purchase_token = purchase_data.purchase_token
            user.clear_grace_period()  # Clear any grace period

            # Create subscription event
            event = SubscriptionEvent(
                user_id=user_id,
                event_type="purchased",
                product_id=purchase_data.product_id,
                purchase_token=purchase_data.purchase_token,
                expires_at=expires_at
            )
            self.db.add(event)

            self.db.commit()
            self.db.refresh(user)

            logger.info(f"Purchase verified successfully for user {user_id}")

            return {
                "success": True,
                "message": "Subscription activated successfully",
                "subscription_tier": user.subscription_tier,
                "expires_at": expires_at,
                "is_premium": user.is_premium
            }

        except ValueError as e:
            logger.error(f"Purchase verification failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error verifying purchase: {str(e)}")
            raise

    def get_subscription_status(self, user_id: str) -> Dict[str, Any]:
        """Get user's subscription status"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        return {
            "subscription_tier": user.subscription_tier,
            "is_premium": user.is_premium,
            "is_active": user.is_premium,
            "expires_at": user.subscription_expires_at,
            "grace_period_ends_at": user.grace_period_ends_at,
            "status": user.get_subscription_status(),
            "auto_renewing": None  # Would come from Google Play API in production
        }

    async def cancel_subscription(self, user_id: str) -> Dict[str, Any]:
        """
        Cancel user's subscription

        In production, this would notify Google Play API
        User retains access until expiration date
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        if user.subscription_tier == "free":
            raise ValueError("User does not have an active subscription")

        # Create cancellation event
        event = SubscriptionEvent(
            user_id=user_id,
            event_type="cancelled",
            product_id=self.PLANS.get(user.subscription_tier, {}).get("google_play_product_id", ""),
            purchase_token=user.google_play_purchase_token or "",
            expires_at=user.subscription_expires_at
        )
        self.db.add(event)
        self.db.commit()

        logger.info(f"Subscription cancelled for user {user_id}")

        return {
            "success": True,
            "message": "Subscription cancelled. You will retain access until the end of your billing period.",
            "will_expire_at": user.subscription_expires_at
        }

    def get_user_subscription_events(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[SubscriptionEvent]:
        """Get subscription event history for a user"""
        events = self.db.query(SubscriptionEvent).filter(
            SubscriptionEvent.user_id == user_id
        ).order_by(
            SubscriptionEvent.created_at.desc()
        ).limit(limit).all()

        return events

    def check_and_update_expired_subscriptions(self):
        """
        Background task to check and update expired subscriptions
        Called by scheduler
        """
        now = datetime.utcnow()

        # Find users with expired subscriptions (not in grace period)
        expired_users = self.db.query(User).filter(
            User.subscription_tier != "free",
            User.subscription_tier != "lifetime",
            User.subscription_expires_at < now,
            User.grace_period_ends_at.is_(None)
        ).all()

        for user in expired_users:
            # Start grace period
            user.start_grace_period(days=settings.GRACE_PERIOD_DAYS)

            # Create event
            event = SubscriptionEvent(
                user_id=str(user.id),
                event_type="expired",
                product_id=self.PLANS.get(user.subscription_tier, {}).get("google_play_product_id", ""),
                purchase_token=user.google_play_purchase_token or ""
            )
            self.db.add(event)

            logger.info(f"Started grace period for user {user.id}")

        self.db.commit()

        # Find users whose grace period has ended
        grace_ended_users = self.db.query(User).filter(
            User.grace_period_ends_at < now,
            User.subscription_tier != "free"
        ).all()

        for user in grace_ended_users:
            # Downgrade to free tier
            old_tier = user.subscription_tier
            user.subscription_tier = "free"
            user.subscription_expires_at = None
            user.grace_period_ends_at = None
            user.google_play_purchase_token = None

            logger.info(f"Downgraded user {user.id} from {old_tier} to free tier")

        self.db.commit()

        return {
            "grace_period_started": len(expired_users),
            "downgraded_to_free": len(grace_ended_users)
        }
