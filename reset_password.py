"""
Quick script to reset a user's password
Run with: python reset_password.py <email> <new_password>
"""
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash


def reset_password(email: str, new_password: str):
    """Reset password for a user"""
    db = SessionLocal()

    try:
        # Find user
        user = db.query(User).filter(User.email == email).first()

        if not user:
            print(f"[ERROR] User not found: {email}")
            return False

        print(f"[INFO] Found user: {email}")
        print(f"[INFO] User ID: {user.id}")
        print(f"[INFO] Current password hash: {user.password_hash[:30] if user.password_hash else 'None'}...")

        # Hash new password
        new_hash = get_password_hash(new_password)
        print(f"[INFO] New password hash: {new_hash[:30]}...")

        # Update password
        user.password_hash = new_hash
        db.commit()

        print(f"[SUCCESS] Password updated for: {email}")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to reset password: {e}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python reset_password.py <email> <new_password>")
        print("Example: python reset_password.py user@example.com mynewpassword123")
        sys.exit(1)

    email = sys.argv[1]
    new_password = sys.argv[2]

    print("=" * 50)
    print("Password Reset Script")
    print("=" * 50)

    success = reset_password(email, new_password)
    sys.exit(0 if success else 1)
