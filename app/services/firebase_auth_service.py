"""Firebase Authentication Service"""
import firebase_admin
from firebase_admin import auth, credentials
from typing import Dict, Optional
import logging
import os
from app.config import settings

logger = logging.getLogger(__name__)


def _ensure_firebase_initialized():
    """
    Ensure Firebase Admin SDK is initialized before use
    Raises RuntimeError if not initialized
    """
    if not firebase_admin._apps:
        # Try to initialize if credentials exist
        if os.path.exists(settings.FCM_CREDENTIALS_PATH):
            try:
                cred = credentials.Certificate(settings.FCM_CREDENTIALS_PATH)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
                raise RuntimeError(
                    f"Firebase Admin SDK initialization failed: {e}\n"
                    f"Check that {settings.FCM_CREDENTIALS_PATH} is valid."
                )
        else:
            raise RuntimeError(
                f"Firebase Admin SDK not initialized and credentials file not found: {settings.FCM_CREDENTIALS_PATH}\n"
                f"Please download credentials from Firebase Console.\n"
                f"See .env.example for setup instructions."
            )


def verify_firebase_token(id_token: str) -> Optional[Dict]:
    """
    Verify Firebase ID token and return decoded token

    Args:
        id_token: Firebase ID token from client

    Returns:
        Decoded token dict or None if invalid

    Raises:
        ValueError: If token is invalid
        RuntimeError: If Firebase Admin SDK not initialized
    """
    # Ensure Firebase is initialized
    _ensure_firebase_initialized()

    try:
        # Verify the ID token
        decoded_token = auth.verify_id_token(id_token)
        logger.info(f"Firebase token verified for UID: {decoded_token['uid']}")
        return decoded_token
    except auth.InvalidIdTokenError as e:
        logger.error(f"Invalid Firebase ID token: {e}")
        raise ValueError(f"Invalid Firebase token: {str(e)}")
    except auth.ExpiredIdTokenError as e:
        logger.error(f"Expired Firebase ID token: {e}")
        raise ValueError(f"Firebase token expired: {str(e)}")
    except Exception as e:
        logger.error(f"Error verifying Firebase token: {e}")
        raise ValueError(f"Token verification failed: {str(e)}")


def get_user_info_from_token(decoded_token: Dict) -> Dict:
    """
    Extract user information from decoded Firebase token

    Args:
        decoded_token: Decoded Firebase ID token

    Returns:
        Dictionary with user information
    """
    # Get sign-in provider
    provider_data = decoded_token.get('firebase', {}).get('sign_in_provider', 'unknown')

    user_info = {
        'firebase_uid': decoded_token['uid'],
        'email': decoded_token.get('email'),
        'email_verified': decoded_token.get('email_verified', False),
        'display_name': decoded_token.get('name'),
        'photo_url': decoded_token.get('picture'),
        'auth_provider': 'google' if provider_data == 'google.com' else 'firebase',
    }

    # If Google Sign-In, try to get Google ID from sub claim
    if provider_data == 'google.com':
        # For Google Sign-In, the sub claim contains the Google user ID
        user_info['google_id'] = decoded_token.get('sub') if decoded_token.get('firebase', {}).get('sign_in_provider') == 'google.com' else None

    logger.info(f"Extracted user info for: {user_info['email']}")
    return user_info


def get_firebase_user_by_uid(firebase_uid: str) -> Optional[auth.UserRecord]:
    """
    Get Firebase user by UID

    Args:
        firebase_uid: Firebase user UID

    Returns:
        UserRecord or None if not found
    """
    _ensure_firebase_initialized()

    try:
        user = auth.get_user(firebase_uid)
        return user
    except auth.UserNotFoundError:
        logger.warning(f"Firebase user not found: {firebase_uid}")
        return None
    except Exception as e:
        logger.error(f"Error getting Firebase user: {e}")
        return None


def get_firebase_user_by_email(email: str) -> Optional[auth.UserRecord]:
    """
    Get Firebase user by email

    Args:
        email: User email address

    Returns:
        UserRecord or None if not found
    """
    _ensure_firebase_initialized()

    try:
        user = auth.get_user_by_email(email)
        return user
    except auth.UserNotFoundError:
        logger.warning(f"Firebase user not found for email: {email}")
        return None
    except Exception as e:
        logger.error(f"Error getting Firebase user by email: {e}")
        return None
