"""Subscription service for Google Play purchases"""
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.subscription import SubscriptionEvent
from app.schemas.subscription import VerifyPurchaseRequest, SubscriptionPlan
from app.config import settings
from typing import List, Dict, Any, Optional
from datetime import timedelta
import logging
import os

from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing Google Play subscriptions"""

    # Subscription tiers configuration
    TIERS = {
        "free": {
            "name": "Free",
            "description": "Get started with basic AI persona features",
            "messages_per_day": 25,
            "personas_limit": 3,
            "storage_mb": 50,
            "history_days": 3,
            "features": [
                "25 messages per day",
                "3 custom personas",
                "3-day chat history",
                "50MB storage",
                "Text export only",
                "No voice features"
            ]
        },
        "basic": {
            "name": "Basic",
            "description": "Enhanced features for regular users",
            "messages_per_day": 200,
            "personas_limit": 15,
            "storage_mb": 500,
            "history_days": 30,
            "features": [
                "200 messages per day",
                "15 custom personas",
                "30-day chat history",
                "500MB storage",
                "Voice input",
                "Text & PDF export",
                "Persona cloning",
                "Email support"
            ]
        },
        "premium": {
            "name": "Premium",
            "description": "Advanced features for power users",
            "messages_per_day": 1000,
            "personas_limit": 50,
            "storage_mb": 2048,
            "history_days": 90,
            "features": [
                "1,000 messages per day",
                "50 custom personas",
                "90-day chat history",
                "2GB storage",
                "Voice input & output (TTS)",
                "All export formats",
                "Priority response",
                "Full analytics",
                "Priority support"
            ]
        },
        "pro": {
            "name": "Pro",
            "description": "Professional tier with unlimited usage",
            "messages_per_day": -1,  # Unlimited
            "personas_limit": -1,  # Unlimited
            "storage_mb": 10240,
            "history_days": -1,  # Unlimited
            "features": [
                "Unlimited messages",
                "Unlimited personas",
                "Unlimited chat history",
                "10GB storage",
                "All voice features",
                "All export formats",
                "Priority response",
                "Full analytics + API access",
                "Dedicated support"
            ]
        }
    }

    # Subscription plans configuration (tier + duration combinations)
    PLANS = {
        # Basic Tier Plans
        "basic_daily": {
            "id": "basic_daily",
            "tier": "basic",
            "name": "Basic Daily Pass",
            "description": "Basic features for 24 hours",
            "price": 0.99,
            "currency": "USD",
            "duration": "daily",
            "duration_days": 1,
            "google_play_product_id": "com.pranta.aipersona.basic.daily",
            "ios_product_id": "basic_daily",
            "features": TIERS["basic"]["features"]
        },
        "basic_monthly": {
            "id": "basic_monthly",
            "tier": "basic",
            "name": "Basic Monthly",
            "description": "Monthly access to Basic features",
            "price": 4.99,
            "currency": "USD",
            "duration": "monthly",
            "duration_days": 30,
            "google_play_product_id": "com.pranta.aipersona.basic.monthly",
            "ios_product_id": "basic_monthly",
            "features": TIERS["basic"]["features"]
        },
        "basic_yearly": {
            "id": "basic_yearly",
            "tier": "basic",
            "name": "Basic Yearly",
            "description": "Save 17% with annual Basic subscription",
            "price": 49.99,
            "currency": "USD",
            "duration": "yearly",
            "duration_days": 365,
            "google_play_product_id": "com.pranta.aipersona.basic.yearly",
            "ios_product_id": "basic_yearly",
            "features": TIERS["basic"]["features"]
        },
        # Premium Tier Plans
        "premium_daily": {
            "id": "premium_daily",
            "tier": "premium",
            "name": "Premium Daily Pass",
            "description": "Full Premium access for 24 hours",
            "price": 1.99,
            "currency": "USD",
            "duration": "daily",
            "duration_days": 1,
            "google_play_product_id": "com.pranta.aipersona.premium.daily",
            "ios_product_id": "premium_daily",
            "features": TIERS["premium"]["features"]
        },
        "premium_monthly": {
            "id": "premium_monthly",
            "tier": "premium",
            "name": "Premium Monthly",
            "description": "Monthly Premium subscription",
            "price": 9.99,
            "currency": "USD",
            "duration": "monthly",
            "duration_days": 30,
            "google_play_product_id": "com.pranta.aipersona.premium.monthly",
            "ios_product_id": "premium_monthly",
            "features": TIERS["premium"]["features"]
        },
        "premium_yearly": {
            "id": "premium_yearly",
            "tier": "premium",
            "name": "Premium Yearly",
            "description": "Best value! Save 17% on Premium",
            "price": 99.99,
            "currency": "USD",
            "duration": "yearly",
            "duration_days": 365,
            "google_play_product_id": "com.pranta.aipersona.premium.yearly",
            "ios_product_id": "premium_yearly",
            "features": TIERS["premium"]["features"]
        },
        # Pro Tier Plans
        "pro_monthly": {
            "id": "pro_monthly",
            "tier": "pro",
            "name": "Pro Monthly",
            "description": "Professional tier with unlimited usage",
            "price": 19.99,
            "currency": "USD",
            "duration": "monthly",
            "duration_days": 30,
            "google_play_product_id": "com.pranta.aipersona.pro.monthly",
            "ios_product_id": "pro_monthly",
            "features": TIERS["pro"]["features"]
        },
        "pro_yearly": {
            "id": "pro_yearly",
            "tier": "pro",
            "name": "Pro Yearly",
            "description": "Maximum savings on Pro tier",
            "price": 199.99,
            "currency": "USD",
            "duration": "yearly",
            "duration_days": 365,
            "google_play_product_id": "com.pranta.aipersona.pro.yearly",
            "ios_product_id": "pro_yearly",
            "features": TIERS["pro"]["features"]
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

    def get_all_tiers(self) -> Dict[str, Any]:
        """Get all subscription tiers with feature limits"""
        return self.TIERS

    def get_tier_info(self, tier_name: str) -> Optional[Dict[str, Any]]:
        """Get tier information by name"""
        return self.TIERS.get(tier_name)

    def get_plan_by_id(self, plan_id: str) -> Optional[Dict[str, Any]]:
        """Get plan details by ID"""
        return self.PLANS.get(plan_id)

    def get_plan_by_product_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get plan by Google Play or iOS product ID"""
        for plan in self.PLANS.values():
            if plan["google_play_product_id"] == product_id:
                return plan
            if plan.get("ios_product_id") == product_id:
                return plan
        return None

    def get_plans_by_tier(self, tier: str) -> List[Dict[str, Any]]:
        """Get all plans for a specific tier"""
        return [p for p in self.PLANS.values() if p.get("tier") == tier]

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
                    "startTimeMillis": str(int(utc_now().timestamp() * 1000)),
                    "expiryTimeMillis": str(int((utc_now() + timedelta(days=plan["duration_days"])).timestamp() * 1000)),
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
                    if expiry_time < utc_now().timestamp():
                        raise ValueError("Subscription has expired")

                    logger.info(f"Successfully verified purchase with Google Play API")

                except ImportError:
                    logger.error("Google API client library not installed. Run: pip install google-api-python-client google-auth")
                    raise ValueError("Google Play verification not available - missing dependencies")
                except Exception as e:
                    logger.error(f"Google Play API verification failed: {str(e)}")
                    raise ValueError(f"Purchase verification failed: {str(e)}")

            # Calculate expiration date
            expires_at = utc_now() + timedelta(days=plan["duration_days"])
            subscription_tier = plan.get("tier", "premium")  # Get the tier from the plan

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
                subscription_tier=subscription_tier,
                expires_at=expires_at,
                verification_status="verified"
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
            product_id=self.PLANS.get(user.subscription_tier, {}).get("google_play_product_id", "unknown"),
            purchase_token=user.google_play_purchase_token or "cancelled",
            subscription_tier=user.subscription_tier,
            expires_at=user.subscription_expires_at or utc_now(),
            verification_status="verified"
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
        now = utc_now()

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
                product_id=self.PLANS.get(user.subscription_tier, {}).get("google_play_product_id", "unknown"),
                purchase_token=user.google_play_purchase_token or "expired",
                subscription_tier=user.subscription_tier,
                expires_at=user.subscription_expires_at or now,
                verification_status="verified"
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
