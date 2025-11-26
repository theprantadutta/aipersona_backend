"""
Script to clear all data from the database while preserving table structure.
Run with: python clear_database.py

WARNING: This will delete ALL data from the database!
"""
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal, engine
from app.models import (
    User,
    UsageTracking,
    Persona,
    KnowledgeBase,
    ChatSession,
    ChatMessage,
    MessageAttachment,
    SubscriptionEvent,
    FCMToken,
    UploadedFile,
    MarketplacePersona,
    MarketplacePurchase,
    MarketplaceReview,
)


# Order matters for foreign key constraints - delete children first
TABLES_IN_ORDER = [
    # Chat related (depends on Persona and User)
    MessageAttachment,
    ChatMessage,
    ChatSession,

    # Marketplace related (depends on Persona and User)
    MarketplaceReview,
    MarketplacePurchase,
    MarketplacePersona,

    # Persona related (depends on User)
    KnowledgeBase,
    Persona,

    # User related
    SubscriptionEvent,
    FCMToken,
    UploadedFile,
    UsageTracking,

    # Finally, users
    User,
]


def clear_all_data(confirm: bool = False):
    """
    Delete all data from all tables in the correct order.

    Args:
        confirm: If True, skip confirmation prompt
    """
    print("=" * 60)
    print("AI Persona Database - Clear All Data")
    print("=" * 60)
    print()
    print("WARNING: This will permanently delete ALL data!")
    print("Tables and structure will be preserved.")
    print()

    if not confirm:
        response = input("Type 'DELETE ALL' to confirm: ")
        if response != "DELETE ALL":
            print("\n[CANCELLED] Operation cancelled.")
            return False

    print()
    print("Clearing database...")
    print("-" * 40)

    db = SessionLocal()

    try:
        total_deleted = 0

        for model in TABLES_IN_ORDER:
            table_name = model.__tablename__
            count = db.query(model).count()

            if count > 0:
                db.query(model).delete()
                print(f"[DELETED] {table_name}: {count} rows")
                total_deleted += count
            else:
                print(f"[EMPTY]   {table_name}: 0 rows")

        db.commit()

        print("-" * 40)
        print()
        print("=" * 60)
        print(f"[SUCCESS] Cleared {total_deleted} total rows from database")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n[ERROR] Failed to clear database: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False

    finally:
        db.close()


def show_stats():
    """Show current row counts for all tables"""
    print("=" * 60)
    print("AI Persona Database - Current Statistics")
    print("=" * 60)
    print()

    db = SessionLocal()

    try:
        total = 0
        for model in TABLES_IN_ORDER:
            table_name = model.__tablename__
            count = db.query(model).count()
            total += count
            print(f"  {table_name}: {count} rows")

        print()
        print(f"  Total: {total} rows")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clear all data from AI Persona database")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--stats", "-s", action="store_true", help="Show database statistics only")

    args = parser.parse_args()

    if args.stats:
        show_stats()
    else:
        clear_all_data(confirm=args.yes)
