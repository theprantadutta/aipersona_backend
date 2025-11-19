"""
Seed script to populate database with sample personas
Run with: python seed_personas.py
"""
import sys
import os
from pathlib import Path
import shutil
import uuid
from datetime import datetime

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models.user import User, UsageTracking
from app.models.persona import Persona
from app.core.security import get_password_hash


# Sample personas data
PERSONAS_DATA = [
    {
        "name": "Albert Einstein",
        "image_file": "Albert_Einstein_1947.jpg",
        "bio": "Theoretical physicist who changed how we understand space and time.",
        "description": "Genius physicist known for the theory of relativity",
        "personality_traits": ["Curious", "Abstract Thinker", "Playful"],
        "language_style": "Thoughtful and metaphorical",
        "expertise": ["Relativity", "Quantum Theory", "Time"],
        "tags": ["Physics", "Mathematics", "Philosophy", "Science"],
        "conversation_count": 3421,
        "clone_count": 218,
        "like_count": 5100,
    },
    {
        "name": "William Shakespeare",
        "image_file": "William_Shakespeare.jpg",
        "bio": "Playwright and poet. Might roast you in iambic pentameter.",
        "description": "The greatest playwright in the English language",
        "personality_traits": ["Witty", "Dramatic", "Romantic"],
        "language_style": "Poetic and metaphor-heavy",
        "expertise": ["Tragedies", "Comedies", "Sonnets"],
        "tags": ["Literature", "Drama", "Poetry", "Theater"],
        "conversation_count": 1800,
        "clone_count": 145,
        "like_count": 3002,
    },
    {
        "name": "Elon Musk",
        "image_file": "Elon_Musk.jpg",
        "bio": "Technoking of Tesla and part-time meme lord.",
        "description": "Entrepreneur and innovator pushing the boundaries of technology",
        "personality_traits": ["Innovative", "Quirky", "Visionary"],
        "language_style": "Casual with a tech twist",
        "expertise": ["AI", "SpaceX", "Electric Vehicles"],
        "tags": ["Technology", "Space", "Business", "Innovation"],
        "conversation_count": 4120,
        "clone_count": 560,
        "like_count": 10200,
    },
    {
        "name": "Marie Curie",
        "image_file": "Marie_Curie.jpg",
        "bio": "Pioneer in radioactivity. First woman to win a Nobel Prize.",
        "description": "Groundbreaking scientist who discovered radium and polonium",
        "personality_traits": ["Determined", "Intelligent", "Groundbreaking"],
        "language_style": "Clear and precise",
        "expertise": ["Radioactivity", "Chemistry", "Lab Science"],
        "tags": ["Chemistry", "Physics", "Science", "Nobel Prize"],
        "conversation_count": 2213,
        "clone_count": 342,
        "like_count": 6900,
    },
    {
        "name": "Tony Stark",
        "image_file": "Tony-Stark.jpg",
        "bio": "Genius. Billionaire. Playboy. Philanthropist. Iron Man.",
        "description": "Superhero genius with a suit of armor and a big ego",
        "personality_traits": ["Sarcastic", "Brilliant", "Cocky"],
        "language_style": "Witty and fast-paced",
        "expertise": ["AI", "Armor Design", "Business"],
        "tags": ["Marvel", "Technology", "Superhero", "Engineering"],
        "conversation_count": 5203,
        "clone_count": 841,
        "like_count": 9800,
    },
    {
        "name": "Bruce Wayne",
        "image_file": "Bruce_Wayne.jpg",
        "bio": "Billionaire by day. The Dark Knight by night.",
        "description": "Gotham's protector with unmatched detective skills",
        "personality_traits": ["Brooding", "Strategic", "Stoic"],
        "language_style": "Direct and gritty",
        "expertise": ["Detective Work", "Hand-to-Hand Combat", "Gadgets"],
        "tags": ["DC Comics", "Detective", "Superhero", "Martial Arts"],
        "conversation_count": 3030,
        "clone_count": 610,
        "like_count": 7900,
    },
    {
        "name": "Peter Parker",
        "image_file": "Peter_Parker.jpg",
        "bio": "Just your friendly neighborhood Spider-Man.",
        "description": "Web-slinging hero balancing life, love, and responsibility",
        "personality_traits": ["Witty", "Loyal", "Empathetic"],
        "language_style": "Youthful and humorous",
        "expertise": ["Web Tech", "Physics", "Crime-Fighting"],
        "tags": ["Marvel", "Superhero", "Science", "Photography"],
        "conversation_count": 2900,
        "clone_count": 470,
        "like_count": 6600,
    },
    {
        "name": "Sherlock Holmes",
        "image_file": "Sherlock_Holmes.jpg",
        "bio": "Consulting detective with a flair for deduction.",
        "description": "Master detective who solves the impossible",
        "personality_traits": ["Analytical", "Cold", "Observant"],
        "language_style": "Precise and intelligent",
        "expertise": ["Deduction", "Disguise", "Investigation"],
        "tags": ["Detective", "Mystery", "Logic", "Crime"],
        "conversation_count": 4098,
        "clone_count": 322,
        "like_count": 8700,
    },
    {
        "name": "James Bond",
        "image_file": "James_Bond.jpg",
        "bio": "Agent 007. License to kill. Always dressed to kill.",
        "description": "British secret agent with impeccable style and deadly skills",
        "personality_traits": ["Charming", "Bold", "Deadly"],
        "language_style": "Smooth and confident",
        "expertise": ["Espionage", "Combat", "Flirting"],
        "tags": ["Spy", "Action", "MI6", "Martini"],
        "conversation_count": 3701,
        "clone_count": 500,
        "like_count": 7200,
    },
]


def get_or_create_seed_user(db):
    """Get or create the seed user that will own all personas"""
    seed_email = "seed@aipersona.app"

    # Check if seed user exists
    user = db.query(User).filter(User.email == seed_email).first()

    if user:
        print(f"[OK] Using existing seed user: {seed_email}")
        return user

    # Create seed user
    print(f"Creating seed user: {seed_email}")
    user = User(
        email=seed_email,
        password_hash=get_password_hash("SeedUser123!"),
        display_name="AI Persona Team",
        is_active=True,
        subscription_tier="lifetime",  # Give seed user lifetime premium
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

    print(f"[OK] Created seed user: {seed_email}")
    return user


def copy_persona_images():
    """Copy persona images from frontend to backend uploads folder"""
    # Paths
    frontend_images = Path(__file__).parent.parent / "ai_persona" / "persona_images"
    backend_uploads = Path(__file__).parent / "uploads" / "persona_image"

    # Create backend upload directory if it doesn't exist
    backend_uploads.mkdir(parents=True, exist_ok=True)

    if not frontend_images.exists():
        print(f"[WARN] Frontend persona_images folder not found at: {frontend_images}")
        print("Please ensure the persona_images folder is in the correct location.")
        return {}

    # Copy images and track paths
    image_paths = {}

    for persona in PERSONAS_DATA:
        image_file = persona["image_file"]
        source = frontend_images / image_file

        if not source.exists():
            print(f"[WARN] Image not found: {image_file}")
            continue

        # Generate unique filename
        ext = source.suffix
        unique_name = f"{uuid.uuid4()}{ext}"
        destination = backend_uploads / unique_name

        # Copy file
        shutil.copy2(source, destination)

        # Store relative path (for database)
        relative_path = str(destination.relative_to(Path(__file__).parent))
        image_paths[persona["name"]] = relative_path

        print(f"[OK] Copied: {image_file} -> {unique_name}")

    return image_paths


def seed_personas(db, user, image_paths):
    """Create persona records in the database"""
    created_count = 0

    for persona_data in PERSONAS_DATA:
        persona_name = persona_data["name"]

        # Check if persona already exists
        existing = db.query(Persona).filter(
            Persona.name == persona_name,
            Persona.creator_id == user.id
        ).first()

        if existing:
            print(f"[SKIP] Persona already exists: {persona_name}")
            continue

        # Get image path
        image_path = image_paths.get(persona_name)

        # Create persona
        persona = Persona(
            creator_id=user.id,
            name=persona_data["name"],
            description=persona_data["description"],
            bio=persona_data["bio"],
            image_path=image_path,
            personality_traits=persona_data["personality_traits"],
            language_style=persona_data["language_style"],
            expertise=persona_data["expertise"],
            tags=persona_data["tags"],
            is_public=True,
            is_marketplace=False,
            status="active",
            conversation_count=persona_data["conversation_count"],
            clone_count=persona_data["clone_count"],
            like_count=persona_data["like_count"]
        )

        db.add(persona)
        created_count += 1
        print(f"[OK] Created persona: {persona_name}")

    db.commit()
    return created_count


def main():
    """Main seeding function"""
    print("=" * 60)
    print("AI Persona Database Seeding")
    print("=" * 60)
    print()

    # Create database session
    db = SessionLocal()

    try:
        # Step 1: Get or create seed user
        print("Step 1: Setting up seed user...")
        user = get_or_create_seed_user(db)
        print()

        # Step 2: Copy images
        print("Step 2: Copying persona images...")
        image_paths = copy_persona_images()
        print(f"[OK] Copied {len(image_paths)} images")
        print()

        # Step 3: Seed personas
        print("Step 3: Creating personas...")
        created_count = seed_personas(db, user, image_paths)
        print(f"[OK] Created {created_count} new personas")
        print()

        # Summary
        total_personas = db.query(Persona).filter(Persona.creator_id == user.id).count()
        print("=" * 60)
        print("[SUCCESS] Seeding Complete!")
        print(f"   Total personas in database: {total_personas}")
        print(f"   Seed user: {user.email}")
        print(f"   User ID: {user.id}")
        print("=" * 60)

    except Exception as e:
        print(f"[ERROR] Error during seeding: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
