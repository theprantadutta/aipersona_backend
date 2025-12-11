"""User model"""
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import timedelta
import uuid
from app.database import Base
from app.config import settings
from app.utils.time_utils import utc_now


class User(Base):
    """User account model with Firebase Auth support"""

    __tablename__ = "users"

    # Identity
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for Google-only users

    # Firebase/Google Authentication (like pinpoint)
    firebase_uid = Column(String(255), unique=True, nullable=True, index=True)
    auth_provider = Column(String(50), default="email", nullable=False)  # 'email', 'google', 'firebase'
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    display_name = Column(String(255), nullable=True)
    photo_url = Column(Text, nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False)

    # Profile
    bio = Column(String(500), nullable=True)  # User bio/description, max 500 chars
    created_at = Column(DateTime, default=utc_now, nullable=False)
    last_login = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    # Google Play Subscriptions (NO Stripe)
    subscription_tier = Column(String(50), default="free", nullable=False)
    # Tiers: free, basic, premium, pro
    subscription_expires_at = Column(DateTime, nullable=True)
    grace_period_ends_at = Column(DateTime, nullable=True)
    google_play_purchase_token = Column(String(500), nullable=True)

    # Relationships
    personas = relationship("Persona", foreign_keys="Persona.creator_id", back_populates="creator", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    subscription_events = relationship("SubscriptionEvent", back_populates="user", cascade="all, delete-orphan")
    fcm_tokens = relationship("FCMToken", back_populates="user", cascade="all, delete-orphan")
    usage_tracking = relationship("UsageTracking", back_populates="user", cascade="all, delete-orphan", uselist=False)
    uploaded_files = relationship("UploadedFile", back_populates="user", cascade="all, delete-orphan")
    marketplace_purchases = relationship("MarketplacePurchase", back_populates="buyer", cascade="all, delete-orphan")

    # Valid paid subscription tiers
    PAID_TIERS = ["basic", "premium", "pro"]

    @property
    def is_premium(self) -> bool:
        """Check if user has any active paid subscription or in grace period"""
        # Check if in grace period first
        if self.is_in_grace_period():
            return True

        if self.subscription_tier == "free":
            return False

        # Check if user has a valid paid tier
        if self.subscription_tier in self.PAID_TIERS:
            # If no expiration date set, treat as expired
            if self.subscription_expires_at is None:
                return False
            # Check if subscription hasn't expired
            return utc_now() < self.subscription_expires_at

        # Unknown tier, treat as not premium
        return False

    @property
    def is_basic_or_higher(self) -> bool:
        """Check if user has Basic tier or higher"""
        return self.is_premium and self.subscription_tier in ["basic", "premium", "pro"]

    @property
    def is_premium_or_higher(self) -> bool:
        """Check if user has Premium tier or higher"""
        return self.is_premium and self.subscription_tier in ["premium", "pro"]

    @property
    def is_pro(self) -> bool:
        """Check if user has Pro tier"""
        return self.is_premium and self.subscription_tier == "pro"

    def is_in_grace_period(self) -> bool:
        """Check if user is currently in grace period"""
        if self.grace_period_ends_at is None:
            return False
        return utc_now() < self.grace_period_ends_at

    def start_grace_period(self, days: int = None):
        """Start grace period for user"""
        if days is None:
            days = settings.GRACE_PERIOD_DAYS
        self.grace_period_ends_at = utc_now() + timedelta(days=days)

    def clear_grace_period(self):
        """Clear grace period (e.g., when payment succeeds)"""
        self.grace_period_ends_at = None

    def get_subscription_status(self) -> str:
        """Get detailed subscription status"""
        if self.is_in_grace_period():
            return "grace_period"
        elif self.is_premium:
            return f"active_{self.subscription_tier}"  # e.g., "active_premium"
        else:
            return "free"

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, tier={self.subscription_tier})>"


class UsageTracking(Base):
    """
    Track user usage for rate limiting and premium features
    """

    __tablename__ = "usage_tracking"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Message limits (free: 10/day, premium: unlimited)
    messages_today = Column(Integer, default=0, nullable=False)
    messages_count_reset_at = Column(DateTime, default=utc_now, nullable=False)

    # Persona limits (free: 2, premium: unlimited)
    personas_count = Column(Integer, default=0, nullable=False)

    # Storage tracking
    storage_used_bytes = Column(Integer, default=0, nullable=False)

    # API usage tracking
    gemini_api_calls_today = Column(Integer, default=0, nullable=False)
    gemini_tokens_used_total = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="usage_tracking")

    def check_and_reset_daily(self) -> bool:
        """
        Check if daily counters should be reset and reset them if needed.
        Returns True if reset was performed.
        """
        now = utc_now()
        last_reset = self.messages_count_reset_at

        # Check if we're in a new day
        if now.date() > last_reset.date():
            self.messages_today = 0
            self.gemini_api_calls_today = 0
            self.messages_count_reset_at = now
            self.updated_at = now
            return True

        return False

    def __repr__(self):
        return f"<UsageTracking(user_id={self.user_id}, messages={self.messages_today}, personas={self.personas_count})>"
