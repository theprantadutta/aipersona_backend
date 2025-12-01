"""
Seed script to populate database with personas from personas_data.json
Uses Gemini AI to find Wikipedia URLs and downloads images.

Run with: python seed_personas_from_json.py

Features:
- Loads personas from personas_data.json
- Uses Gemini to find Wikipedia page URLs
- Downloads images from Wikipedia
- Uploads images to FileRunner
- Creates new personas or updates existing ones
"""
import sys
import asyncio
import json
import re
import random
from pathlib import Path
from typing import Optional
import httpx

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models.user import User, UsageTracking
from app.models.persona import Persona
from app.core.security import get_password_hash
from app.services.filerunner_service import filerunner_service
from app.config import settings


# Constants
PERSONAS_JSON_PATH = Path(__file__).parent / "personas_data.json"
PERSONA_IMAGES_DIR = Path(__file__).parent / "persona_images"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Rate limiting
REQUEST_DELAY = 1.5  # Seconds between API requests to avoid rate limiting


def load_personas_data() -> list[dict]:
    """Load personas data from JSON file"""
    if not PERSONAS_JSON_PATH.exists():
        raise FileNotFoundError(f"personas_data.json not found at: {PERSONAS_JSON_PATH}")

    with open(PERSONAS_JSON_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_or_create_admin_user(db):
    """Get or create the admin user that will own all default personas"""
    admin_email = settings.ADMIN_EMAIL
    admin_password = settings.ADMIN_PASSWORD

    # Check if admin user exists
    user = db.query(User).filter(User.email == admin_email).first()

    if user:
        print(f"[OK] Using existing admin user: {admin_email}")
        if not user.is_admin:
            user.is_admin = True
            db.commit()
            print(f"[OK] Updated user to admin: {admin_email}")
        return user

    # Create admin user
    print(f"Creating admin user: {admin_email}")
    user = User(
        email=admin_email,
        password_hash=get_password_hash(admin_password),
        display_name="AI Persona Admin",
        is_active=True,
        is_admin=True,
        subscription_tier="lifetime",
        auth_provider="email",
        email_verified=True
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Create usage tracking
    usage = UsageTracking(user_id=user.id)
    db.add(usage)
    db.commit()

    print(f"[OK] Created admin user: {admin_email}")
    return user


async def get_wikipedia_url_from_gemini(
    client: httpx.AsyncClient,
    persona_name: str,
    persona_bio: str,
    search_hint: str
) -> Optional[str]:
    """
    Uses the Gemini API to find and verify an English Wikipedia URL for a given persona.

    Args:
        client: httpx async client
        persona_name: The name of the persona
        persona_bio: A short bio of the persona
        search_hint: Additional search context

    Returns:
        A verified Wikipedia URL string if found and valid; otherwise, None
    """
    print(f"  [WIKI] Searching Wikipedia URL for: {persona_name}")

    # Step 1: Ask Gemini for the URL
    prompt = (
        f"You are a helpful research assistant. Your task is to find the official English Wikipedia page URL for a given person or character. "
        f"The name is '{persona_name}' and their description is '{persona_bio}'. "
        f"Additional search context: '{search_hint}'. "
        f"Search Wikipedia for this person/character. If you find a direct and exact match, respond ONLY with the full URL (e.g., https://en.wikipedia.org/wiki/...). "
        f"Do not include any other text, explanation, or formatting. Just the URL. "
        f"If you are not certain, if no page exists, respond with the single word: null"
    )

    request_body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 256
        }
    }

    try:
        api_url = GEMINI_API_URL.format(model=settings.GEMINI_MODEL) + f"?key={settings.GEMINI_API_KEY}"
        response = await client.post(api_url, json=request_body, timeout=30.0)

        if response.status_code != 200:
            print(f"  [WARN] Gemini API request failed with status: {response.status_code}")
            return None

        response_data = response.json()
        potential_url = (
            response_data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )

    except Exception as e:
        print(f"  [ERROR] Gemini API error: {e}")
        return None

    # Step 2: Verify the URL
    if not potential_url or potential_url.lower() == "null":
        print(f"  [WARN] Gemini did not find a Wikipedia URL for {persona_name}")
        return None

    # Clean up the URL (remove any markdown or extra characters)
    potential_url = potential_url.strip('`').strip()

    # Basic check for valid Wikipedia URL
    if not potential_url.startswith("https://en.wikipedia.org/wiki/"):
        print(f"  [WARN] Invalid URL format for {persona_name}: {potential_url}")
        return None

    # Skip URL verification - we'll validate by trying to get the image from Wikipedia API
    # Wikipedia blocks direct requests, but the API works fine
    print(f"  [OK] Got Wikipedia URL from Gemini: {potential_url}")
    return potential_url


async def get_wikipedia_image_url(client: httpx.AsyncClient, wiki_url: str) -> Optional[str]:
    """
    Extract the main image URL from a Wikipedia page using the Wikipedia API.

    Args:
        client: httpx async client
        wiki_url: The Wikipedia page URL

    Returns:
        The image URL if found, otherwise None
    """
    try:
        # Extract the page title from the URL
        page_title = wiki_url.split("/wiki/")[-1]

        # Use Wikipedia API to get page images
        api_url = (
            f"https://en.wikipedia.org/w/api.php?"
            f"action=query&titles={page_title}&prop=pageimages&format=json&pithumbsize=500"
        )

        headers = {
            "User-Agent": "AIPersonaBot/1.0 (https://aipersona.app; contact@aipersona.app)",
            "Accept": "application/json",
        }

        response = await client.get(api_url, headers=headers, timeout=15.0)

        if response.status_code != 200:
            print(f"  [WARN] Wikipedia API failed: {response.status_code}")
            return None

        data = response.json()
        pages = data.get("query", {}).get("pages", {})

        for page_id, page_data in pages.items():
            if page_id == "-1":
                continue
            thumbnail = page_data.get("thumbnail", {})
            image_url = thumbnail.get("source")
            if image_url:
                print(f"  [OK] Found Wikipedia image")
                return image_url

        print(f"  [WARN] No image found on Wikipedia page")
        return None

    except Exception as e:
        print(f"  [ERROR] Failed to get Wikipedia image: {e}")
        return None


async def download_image(client: httpx.AsyncClient, image_url: str, persona_name: str) -> Optional[bytes]:
    """
    Download an image from a URL.

    Args:
        client: httpx async client
        image_url: URL of the image to download
        persona_name: Name of the persona (for logging)

    Returns:
        Image bytes if successful, otherwise None
    """
    try:
        # Wikimedia requires a proper User-Agent with contact info per their policy
        # https://meta.wikimedia.org/wiki/User-Agent_policy
        headers = {
            "User-Agent": "AIPersonaBot/1.0 (https://aipersona.app; contact@aipersona.app) Python/httpx",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://en.wikipedia.org/",
        }

        response = await client.get(image_url, headers=headers, timeout=30.0, follow_redirects=True)

        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            if "image" in content_type:
                print(f"  [OK] Downloaded image ({len(response.content)} bytes)")
                return response.content
            else:
                print(f"  [WARN] Response is not an image: {content_type}")
                return None
        else:
            print(f"  [WARN] Failed to download image: {response.status_code}")
            return None

    except Exception as e:
        print(f"  [ERROR] Image download error: {e}")
        return None


def sanitize_filename(name: str) -> str:
    """Convert persona name to a safe filename"""
    # Replace spaces and special characters
    safe_name = re.sub(r'[^\w\s-]', '', name)
    safe_name = re.sub(r'[-\s]+', '_', safe_name)
    return safe_name


def get_content_type(image_url: str) -> str:
    """Determine content type from URL or default to JPEG"""
    url_lower = image_url.lower()
    if '.png' in url_lower:
        return 'image/png'
    elif '.gif' in url_lower:
        return 'image/gif'
    elif '.webp' in url_lower:
        return 'image/webp'
    return 'image/jpeg'


def get_file_extension(content_type: str) -> str:
    """Get file extension from content type"""
    extensions = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp'
    }
    return extensions.get(content_type, '.jpg')


async def process_persona_image(
    client: httpx.AsyncClient,
    persona: dict
) -> Optional[str]:
    """
    Process a single persona: find Wikipedia URL, download image, upload to FileRunner.

    Args:
        client: httpx async client
        persona: Persona data dictionary

    Returns:
        FileRunner URL if successful, otherwise None
    """
    persona_name = persona["name"]
    persona_bio = persona["bio"]
    search_hint = persona.get("wikipedia_search", persona_name)

    print(f"\n[PROCESSING] {persona_name}")

    # Step 1: Get Wikipedia URL from Gemini
    wiki_url = await get_wikipedia_url_from_gemini(client, persona_name, persona_bio, search_hint)

    if not wiki_url:
        print(f"  [SKIP] Could not find Wikipedia URL")
        return None

    # Small delay to avoid rate limiting
    await asyncio.sleep(0.5)

    # Step 2: Get image URL from Wikipedia
    image_url = await get_wikipedia_image_url(client, wiki_url)

    if not image_url:
        print(f"  [SKIP] Could not find image on Wikipedia")
        return None

    # Step 3: Download the image
    image_data = await download_image(client, image_url, persona_name)

    if not image_data:
        print(f"  [SKIP] Could not download image")
        return None

    # Step 4: Save image locally
    content_type = get_content_type(image_url)
    extension = get_file_extension(content_type)
    filename = f"{sanitize_filename(persona_name)}{extension}"

    # Ensure directory exists
    PERSONA_IMAGES_DIR.mkdir(exist_ok=True)
    local_path = PERSONA_IMAGES_DIR / filename

    with open(local_path, 'wb') as f:
        f.write(image_data)
    print(f"  [OK] Saved locally: {filename}")

    # Step 5: Upload to FileRunner
    try:
        result = await filerunner_service.upload_file(
            file_content=image_data,
            filename=filename,
            content_type=content_type,
            category="persona_image"
        )

        file_id = result.get('file_id')
        file_url = filerunner_service.get_file_url(file_id)
        print(f"  [OK] Uploaded to FileRunner: {file_url}")
        return file_url

    except Exception as e:
        print(f"  [ERROR] FileRunner upload failed: {e}")
        return None


def seed_or_update_persona(db, user, persona_data: dict, image_url: Optional[str]) -> tuple[bool, bool]:
    """
    Create a new persona or update an existing one.

    Args:
        db: Database session
        user: Admin user
        persona_data: Persona data from JSON
        image_url: FileRunner image URL (or None)

    Returns:
        Tuple of (was_created, was_updated)
    """
    persona_name = persona_data["name"]

    # Check if persona already exists
    existing = db.query(Persona).filter(
        Persona.name == persona_name,
        Persona.creator_id == user.id
    ).first()

    if existing:
        # Update existing persona
        updated = False

        # Update image if we have a new one and it's different
        if image_url and existing.image_path != image_url:
            existing.image_path = image_url
            updated = True

        # Update other fields if they differ
        if existing.bio != persona_data["bio"]:
            existing.bio = persona_data["bio"]
            updated = True
        if existing.description != persona_data["description"]:
            existing.description = persona_data["description"]
            updated = True
        if existing.personality_traits != persona_data["personality_traits"]:
            existing.personality_traits = persona_data["personality_traits"]
            updated = True
        if existing.language_style != persona_data["language_style"]:
            existing.language_style = persona_data["language_style"]
            updated = True
        if existing.expertise != persona_data["expertise"]:
            existing.expertise = persona_data["expertise"]
            updated = True
        if existing.tags != persona_data["tags"]:
            existing.tags = persona_data["tags"]
            updated = True

        if updated:
            db.commit()
            print(f"  [UPDATE] Updated persona: {persona_name}")
            return (False, True)
        else:
            print(f"  [SKIP] Persona unchanged: {persona_name}")
            return (False, False)

    else:
        # Create new persona with random initial stats
        persona = Persona(
            creator_id=user.id,
            name=persona_data["name"],
            description=persona_data["description"],
            bio=persona_data["bio"],
            image_path=image_url,
            personality_traits=persona_data["personality_traits"],
            language_style=persona_data["language_style"],
            expertise=persona_data["expertise"],
            tags=persona_data["tags"],
            is_public=True,
            is_marketplace=False,
            status="active",
            conversation_count=random.randint(500, 5000),
            clone_count=random.randint(50, 500),
            like_count=random.randint(1000, 10000)
        )

        db.add(persona)
        db.commit()
        print(f"  [CREATE] Created persona: {persona_name}")
        return (True, False)


async def main_async():
    """Main seeding function (async)"""
    print("=" * 70)
    print("AI Persona Database Seeding - From JSON with Wikipedia Images")
    print("=" * 70)
    print()

    # Load personas data
    print("Step 1: Loading personas data from JSON...")
    try:
        personas_data = load_personas_data()
        print(f"[OK] Loaded {len(personas_data)} personas from JSON")
    except Exception as e:
        print(f"[ERROR] Failed to load personas data: {e}")
        return
    print()

    # Create database session
    db = SessionLocal()

    try:
        # Step 2: Get or create admin user
        print("Step 2: Setting up admin user...")
        user = get_or_create_admin_user(db)
        print()

        # Step 3: Process personas
        print("Step 3: Processing personas (fetching Wikipedia images)...")
        print(f"[INFO] Using Gemini model: {settings.GEMINI_MODEL}")
        print()

        created_count = 0
        updated_count = 0
        skipped_count = 0
        image_success_count = 0

        async with httpx.AsyncClient() as client:
            for i, persona_data in enumerate(personas_data):
                print(f"\n{'='*50}")
                print(f"[{i+1}/{len(personas_data)}] Processing: {persona_data['name']}")
                print(f"{'='*50}")

                # Process image
                image_url = await process_persona_image(client, persona_data)

                if image_url:
                    image_success_count += 1

                # Seed or update persona
                was_created, was_updated = seed_or_update_persona(db, user, persona_data, image_url)

                if was_created:
                    created_count += 1
                elif was_updated:
                    updated_count += 1
                else:
                    skipped_count += 1

                # Rate limiting delay
                if i < len(personas_data) - 1:
                    print(f"\n[WAIT] Waiting {REQUEST_DELAY}s before next persona...")
                    await asyncio.sleep(REQUEST_DELAY)

        # Summary
        total_personas = db.query(Persona).filter(Persona.creator_id == user.id).count()

        print("\n" + "=" * 70)
        print("[SUCCESS] Seeding Complete!")
        print("=" * 70)
        print(f"   Total personas processed: {len(personas_data)}")
        print(f"   Images successfully fetched: {image_success_count}")
        print(f"   New personas created: {created_count}")
        print(f"   Existing personas updated: {updated_count}")
        print(f"   Personas skipped (unchanged): {skipped_count}")
        print(f"   Total personas in database: {total_personas}")
        print(f"   Admin user: {user.email}")
        print(f"   Storage: FileRunner")
        print("=" * 70)

    except Exception as e:
        print(f"[ERROR] Error during seeding: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        # Close FileRunner client
        await filerunner_service.close()
        db.close()


def main():
    """Entry point - runs the async main function"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
