"""Firebase Authentication endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.user import (
    FirebaseAuthRequest,
    GoogleAuthRequest,
    LinkAccountRequest,
    AuthProvidersResponse,
)
from app.schemas.auth import Token
from app.services.firebase_auth_service import verify_firebase_token, get_user_info_from_token
from app.services.auth_service import AuthService
from app.core.dependencies import get_current_user
from app.core.security import verify_password
from app.models.user import User, UsageTracking
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/firebase", response_model=Token, status_code=status.HTTP_200_OK)
async def authenticate_with_firebase(
    request: FirebaseAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user with Firebase ID token

    This endpoint:
    1. Verifies the Firebase ID token
    2. Extracts user information
    3. Creates user if doesn't exist or logs in existing user
    4. Returns backend JWT token

    - **firebase_token**: Firebase ID token from client
    """
    try:
        logger.info("🔐 [Firebase Auth] Starting Firebase authentication...")

        # Verify Firebase token
        logger.info("🔐 [Firebase Auth] Step 1: Verifying Firebase token...")
        decoded_token = verify_firebase_token(request.firebase_token)
        logger.info(f"✅ [Firebase Auth] Token verified for UID: {decoded_token.get('uid')}")

        logger.info("🔐 [Firebase Auth] Step 2: Extracting user info from token...")
        user_info = get_user_info_from_token(decoded_token)
        logger.info(f"✅ [Firebase Auth] User info extracted: {user_info.get('email')}")

        auth_service = AuthService(db)

        # Check if user exists by Firebase UID
        logger.info(f"🔐 [Firebase Auth] Step 3: Checking if user exists (UID: {user_info['firebase_uid']})...")
        user = db.query(User).filter(User.firebase_uid == user_info['firebase_uid']).first()

        if user:
            # Existing Firebase user - update last login
            logger.info(f"✅ [Firebase Auth] Found existing user: {user.email}")
            user.last_login = datetime.utcnow()
            db.commit()
            db.refresh(user)
        else:
            logger.info("🔐 [Firebase Auth] User not found by UID, checking by email...")
            # Check if user exists by email (for account linking scenario)
            user = auth_service.get_user_by_email(user_info['email'])

            if user:
                # Email exists but no Firebase UID - this is a conflict
                # User needs to use account linking endpoint with password
                logger.warning(f"⚠️ [Firebase Auth] Email exists but not linked: {user_info['email']}")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": "Account with this email already exists",
                        "email": user_info['email'],
                        "requires_linking": True
                    }
                )

            # Create new user with Firebase auth
            logger.info(f"🔐 [Firebase Auth] Creating new user: {user_info['email']}")
            user = User(
                email=user_info['email'],
                firebase_uid=user_info['firebase_uid'],
                auth_provider=user_info['auth_provider'],
                google_id=user_info.get('google_id'),
                display_name=user_info.get('display_name'),
                photo_url=user_info.get('photo_url'),
                email_verified=user_info['email_verified'],
                password_hash=None,  # No password for Firebase-only users
                is_active=True,
                subscription_tier="free"
            )

            db.add(user)
            db.commit()
            db.refresh(user)

            logger.info(f"✅ [Firebase Auth] User created with ID: {user.id} (type: {type(user.id).__name__})")

            # Create usage tracking for new user
            usage_tracking = UsageTracking(user_id=user.id)
            db.add(usage_tracking)
            db.commit()

            logger.info(f"✅ [Firebase Auth] Created new Firebase user: {user.email}")

        # Create backend JWT token
        logger.info("🔐 [Firebase Auth] Step 4: Creating JWT token...")
        logger.info(f"🔐 [Firebase Auth] User ID for token: {user.id} (str: {str(user.id)})")
        access_token = auth_service.create_access_token_for_user(user)
        logger.info(f"🎉 [Firebase Auth] Authentication successful for user: {user.email}")
        logger.info(f"🎉 [Firebase Auth] Token created, returning user_id: {str(user.id)}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": str(user.id)
        }

    except ValueError as e:
        # Firebase token verification failed
        logger.error(f"❌ [Firebase Auth] ValueError: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase token: {str(e)}"
        )
    except RuntimeError as e:
        # Firebase SDK not initialized
        logger.error(f"❌ [Firebase Auth] RuntimeError: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Firebase initialization error: {str(e)}"
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like 409 conflict)
        raise
    except Exception as e:
        logger.error(f"❌ [Firebase Auth] Unexpected error: {type(e).__name__}: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {type(e).__name__}: {str(e)}"
        )


@router.post("/google", response_model=Token, status_code=status.HTTP_200_OK)
async def authenticate_with_google(
    request: GoogleAuthRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user with Google Sign-In (via Firebase)

    This is an alias for /firebase endpoint but explicitly for Google Sign-In

    - **firebase_token**: Firebase ID token from Google Sign-In
    """
    # Reuse Firebase authentication logic
    firebase_request = FirebaseAuthRequest(firebase_token=request.firebase_token)
    return await authenticate_with_firebase(firebase_request, db)


@router.post("/link-google", status_code=status.HTTP_200_OK)
async def link_google_account(
    request: LinkAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Link Google account to existing email/password account

    Requires:
    - User must be authenticated (has JWT token)
    - Must provide correct password for verification
    - Must provide valid Firebase token from Google Sign-In

    - **firebase_token**: Firebase ID token from Google Sign-In
    - **password**: Current account password for verification
    """
    try:
        # Verify password
        if not current_user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account has no password set"
            )

        if not verify_password(request.password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password"
            )

        # Verify Firebase token
        decoded_token = verify_firebase_token(request.firebase_token)
        user_info = get_user_info_from_token(decoded_token)

        # Check if Firebase UID is already linked to another account
        existing_user = db.query(User).filter(
            User.firebase_uid == user_info['firebase_uid']
        ).first()

        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Google account is already linked to another user"
            )

        # Check if Google ID is already linked to another account
        if user_info.get('google_id'):
            existing_google_user = db.query(User).filter(
                User.google_id == user_info['google_id']
            ).first()

            if existing_google_user and existing_google_user.id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This Google account is already linked to another user"
                )

        # Link the accounts
        current_user.firebase_uid = user_info['firebase_uid']
        current_user.google_id = user_info.get('google_id')
        current_user.display_name = user_info.get('display_name') or current_user.display_name
        current_user.photo_url = user_info.get('photo_url') or current_user.photo_url
        current_user.email_verified = user_info['email_verified']

        # Update auth provider to indicate both methods available
        if current_user.auth_provider == 'email':
            current_user.auth_provider = 'google'  # Primary becomes Google

        db.commit()
        db.refresh(current_user)

        logger.info(f"Linked Google account to user: {current_user.email}")

        return {
            "message": "Google account linked successfully",
            "user_id": str(current_user.id)
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase token: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Account linking error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account linking failed"
        )


@router.post("/unlink-google", status_code=status.HTTP_200_OK)
async def unlink_google_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Unlink Google account from user account

    Requires:
    - User must have password set (cannot unlink only auth method)
    """
    # Check if user has password as fallback
    if not current_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot unlink Google account. Please set a password first."
        )

    # Check if user actually has Google linked
    if not current_user.firebase_uid and not current_user.google_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Google account is linked"
        )

    # Unlink Google account
    current_user.firebase_uid = None
    current_user.google_id = None
    current_user.auth_provider = 'email'  # Revert to email-only

    db.commit()
    db.refresh(current_user)

    logger.info(f"Unlinked Google account from user: {current_user.email}")

    return {
        "message": "Google account unlinked successfully",
        "user_id": str(current_user.id)
    }


@router.get("/providers", response_model=AuthProvidersResponse)
async def get_auth_providers(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of authentication providers linked to current user

    Returns information about which authentication methods are available
    """
    providers = []
    has_password = bool(current_user.password_hash)
    has_google = bool(current_user.firebase_uid or current_user.google_id)

    if has_password:
        providers.append('email')
    if has_google:
        providers.append('google')

    return {
        "providers": providers,
        "has_password": has_password,
        "has_google": has_google
    }
