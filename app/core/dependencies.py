"""
FastAPI dependencies for request handling
"""
from uuid import UUID as PyUUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
import logging

security = HTTPBearer()
logger = logging.getLogger(__name__)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token

    Usage:
        @router.get("/me")
        async def get_me(current_user: User = Depends(get_current_user)):
            return current_user
    """
    token = credentials.credentials

    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        logger.error("❌ [Auth] Failed to decode JWT token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user ID from token
    user_id: str = payload.get("sub")
    logger.info(f"🔐 [Auth] Extracted user_id from token: {user_id}")
    if user_id is None:
        logger.error("❌ [Auth] No 'sub' claim in token payload")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    logger.info(f"🔐 [Auth] Looking up user with ID: {user_id}")
    try:
        user_uuid = PyUUID(user_id)
    except (ValueError, TypeError) as e:
        logger.error(f"❌ [Auth] Invalid UUID format for user_id: {user_id}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_uuid).first()
    if user is None:
        logger.error(f"❌ [Auth] User not found in database for ID: {user_id}")
        # Let's also check how many users exist in total
        total_users = db.query(User).count()
        logger.error(f"❌ [Auth] Total users in database: {total_users}")
        # Log all existing user IDs for debugging
        all_users = db.query(User).all()
        for u in all_users:
            logger.error(f"❌ [Auth] Existing user: id={u.id}, email={u.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"✅ [Auth] User found: {user.email}")
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (not disabled/deleted)
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_premium_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency to check if user has premium subscription
    """
    if not current_user.is_premium:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Premium subscription required. Upgrade to unlock unlimited access!"
        )
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Dependency to check if user is an admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# Optional security for endpoints that can work with or without auth
optional_security = HTTPBearer(auto_error=False)


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(optional_security),
    db: Session = Depends(get_db)
) -> User | None:
    """
    Get current authenticated user if token provided, otherwise return None.
    Used for endpoints that work for both authenticated and anonymous users.
    """
    if credentials is None:
        return None

    token = credentials.credentials

    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        return None

    # Extract user ID from token
    user_id: str = payload.get("sub")
    if user_id is None:
        return None

    # Get user from database
    try:
        user_uuid = PyUUID(user_id)
    except (ValueError, TypeError):
        return None

    user = db.query(User).filter(User.id == user_uuid).first()
    return user
