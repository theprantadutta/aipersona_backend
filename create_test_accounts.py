#!/usr/bin/env python3
"""
AI Persona Test Account Creator

Creates two test accounts for development/testing:
1. Free tier user
2. Premium tier user (paid)

Usage:
    python create_test_accounts.py

Requirements:
    pip install requests psycopg2-binary python-dotenv
"""

import os
import sys
import requests
import psycopg2
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
API_BASE_URL = f"http://localhost:{os.getenv('PORT', '8001')}"
API_PREFIX = os.getenv('API_V1_PREFIX', '/api/v1')

# Test account credentials
FREE_USER = {
    "email": "freeuser@test.com",
    "password": "TestPassword123!"
}

PAID_USER = {
    "email": "paiduser@test.com",
    "password": "TestPassword123!",
    "subscription_tier": "premium",  # Options: basic, premium, pro
    "subscription_days": 30  # How many days until expiration
}

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DATABASE_HOST"),
    "port": os.getenv("DATABASE_PORT", "5432"),
    "database": os.getenv("DATABASE_NAME"),
    "user": os.getenv("DATABASE_USERNAME"),
    "password": os.getenv("DATABASE_PASSWORD")
}


def print_header():
    """Print script header"""
    print("=" * 60)
    print("  AI Persona - Test Account Creator")
    print("=" * 60)
    print()


def check_server():
    """Check if the backend server is running"""
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


def register_user(email: str, password: str) -> dict | None:
    """Register a new user via API"""
    url = f"{API_BASE_URL}{API_PREFIX}/auth/register"
    payload = {"email": email, "password": password}

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 201:
            data = response.json()
            print(f"  [OK] User registered successfully")
            print(f"       User ID: {data.get('user_id')}")
            return data
        elif response.status_code == 400:
            error = response.json()
            if "already registered" in str(error).lower():
                print(f"  [INFO] User already exists, attempting login...")
                return login_user(email, password)
            else:
                print(f"  [ERROR] Registration failed: {error}")
                return None
        else:
            print(f"  [ERROR] Unexpected response: {response.status_code}")
            print(f"         {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Request failed: {e}")
        return None


def login_user(email: str, password: str) -> dict | None:
    """Login existing user via API"""
    url = f"{API_BASE_URL}{API_PREFIX}/auth/login"
    payload = {"email": email, "password": password}

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            print(f"  [OK] User logged in successfully")
            print(f"       User ID: {data.get('user_id')}")
            return data
        else:
            print(f"  [ERROR] Login failed: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Request failed: {e}")
        return None


def update_subscription_tier(user_id: str, tier: str, days: int) -> bool:
    """Update user's subscription tier directly in database"""

    if not all(DB_CONFIG.values()):
        print("  [ERROR] Database configuration incomplete")
        print(f"         Check your .env file for DATABASE_* variables")
        return False

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        expires_at = datetime.utcnow() + timedelta(days=days)

        cursor.execute("""
            UPDATE users
            SET subscription_tier = %s,
                subscription_expires_at = %s,
                grace_period_ends_at = NULL
            WHERE id = %s::uuid
        """, (tier, expires_at, user_id))

        if cursor.rowcount == 0:
            print(f"  [ERROR] User not found in database")
            conn.rollback()
            return False

        conn.commit()
        cursor.close()
        conn.close()

        print(f"  [OK] Subscription updated to '{tier}'")
        print(f"       Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        return True

    except psycopg2.Error as e:
        print(f"  [ERROR] Database error: {e}")
        return False


def get_subscription_status(access_token: str) -> dict | None:
    """Get subscription status via API"""
    url = f"{API_BASE_URL}{API_PREFIX}/subscription/status"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            return None

    except requests.exceptions.RequestException:
        return None


def create_free_user():
    """Create free tier test user"""
    print(f"Creating FREE user: {FREE_USER['email']}")
    print("-" * 40)

    result = register_user(FREE_USER['email'], FREE_USER['password'])

    if result:
        # Verify subscription status
        status = get_subscription_status(result.get('access_token'))
        if status:
            print(f"  [OK] Subscription tier: {status.get('subscription_tier', 'free')}")
        print()
        return True

    print()
    return False


def create_paid_user():
    """Create paid tier test user"""
    print(f"Creating PAID user: {PAID_USER['email']}")
    print("-" * 40)

    result = register_user(PAID_USER['email'], PAID_USER['password'])

    if result:
        user_id = result.get('user_id')
        access_token = result.get('access_token')

        # Update subscription tier in database
        if update_subscription_tier(
            user_id,
            PAID_USER['subscription_tier'],
            PAID_USER['subscription_days']
        ):
            # Verify subscription status
            status = get_subscription_status(access_token)
            if status:
                print(f"  [OK] Verified tier: {status.get('subscription_tier')}")
                print(f"       Is premium: {status.get('is_premium')}")

        print()
        return True

    print()
    return False


def print_summary():
    """Print summary of created accounts"""
    print("=" * 60)
    print("  Test Accounts Summary")
    print("=" * 60)
    print()
    print("  FREE USER:")
    print(f"    Email:    {FREE_USER['email']}")
    print(f"    Password: {FREE_USER['password']}")
    print(f"    Tier:     free")
    print()
    print("  PAID USER:")
    print(f"    Email:    {PAID_USER['email']}")
    print(f"    Password: {PAID_USER['password']}")
    print(f"    Tier:     {PAID_USER['subscription_tier']}")
    print(f"    Expires:  {PAID_USER['subscription_days']} days from now")
    print()
    print("=" * 60)


def main():
    """Main function"""
    print_header()

    # Check if server is running
    print("Checking backend server...")
    if not check_server():
        print(f"  [ERROR] Backend server not running at {API_BASE_URL}")
        print("  Please start the server first:")
        print("    cd aipersona_backend")
        print("    python -m app.main")
        print()
        sys.exit(1)
    print(f"  [OK] Server is running at {API_BASE_URL}")
    print()

    # Create accounts
    free_success = create_free_user()
    paid_success = create_paid_user()

    # Print summary
    if free_success or paid_success:
        print_summary()
        print("You can now use these accounts in the Flutter app!")
        print()
    else:
        print("[ERROR] Failed to create test accounts")
        print()
        sys.exit(1)


if __name__ == "__main__":
    main()
