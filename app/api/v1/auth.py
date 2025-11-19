"""Authentication endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from app.database import get_db
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.schemas.auth import Token
from app.services.auth_service import AuthService
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Register a new user

    - **email**: User email (must be unique)
    - **password**: User password (will be hashed)
    """
    auth_service = AuthService(db)

    # Check if user already exists
    existing_user = auth_service.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create user
    user = auth_service.create_user(user_data)

    # Create access token
    access_token = auth_service.create_access_token_for_user(user)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id)
    }


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Login with email and password

    Returns JWT access token
    """
    auth_service = AuthService(db)

    # Authenticate user
    user = auth_service.authenticate_user(
        credentials.email,
        credentials.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = auth_service.create_access_token_for_user(user)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id)
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information

    Requires: Bearer token in Authorization header
    """
    return current_user


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout (client should delete token)

    In JWT, logout is primarily handled client-side
    """
    return {"message": "Logged out successfully"}


class UserProfileUpdate(BaseModel):
    """User profile update request"""
    display_name: Optional[str] = None
    photo_url: Optional[str] = None


@router.put("/me", response_model=UserResponse)
async def update_user_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user profile

    - **display_name**: Update display name
    - **photo_url**: Update profile photo URL

    Requires: Bearer token in Authorization header
    """
    if profile_data.display_name is not None:
        current_user.display_name = profile_data.display_name

    if profile_data.photo_url is not None:
        current_user.photo_url = profile_data.photo_url

    db.commit()
    db.refresh(current_user)

    return current_user
