"""Authentication service"""
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.user import User, UsageTracking
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, verify_password, create_access_token
from typing import Optional
from datetime import datetime


class AuthService:
    """Service for user authentication"""

    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        try:
            user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id
            return self.db.query(User).filter(User.id == user_uuid).first()
        except (ValueError, TypeError):
            return None

    def create_user(self, user_data: UserCreate) -> User:
        """Create a new user with usage tracking"""
        # Hash the password
        hashed_password = get_password_hash(user_data.password)

        # Create user instance
        db_user = User(
            email=user_data.email,
            password_hash=hashed_password,
            is_active=True,
            subscription_tier="free",
            auth_provider="email"
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)

        # Create usage tracking for new user
        usage_tracking = UsageTracking(user_id=db_user.id)
        self.db.add(usage_tracking)
        self.db.commit()

        return db_user

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate user with email and password

        Returns:
            User object if authentication successful, None otherwise
        """
        user = self.get_user_by_email(email)

        if not user:
            return None

        if not verify_password(password, user.password_hash):
            return None

        # Update last login
        user.last_login = datetime.utcnow()
        self.db.commit()

        return user

    def create_access_token_for_user(self, user: User) -> str:
        """Create JWT access token for user"""
        return create_access_token(data={"sub": str(user.id)})
