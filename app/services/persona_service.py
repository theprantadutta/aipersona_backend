"""Persona service for business logic"""
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
from app.models.persona import Persona, KnowledgeBase
from app.models.user import User, UsageTracking
from app.schemas.persona import PersonaCreate, PersonaUpdate, KnowledgeBaseCreate
from app.config import settings
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import logging

logger = logging.getLogger(__name__)


class PersonaService:
    """Service for persona management"""

    def __init__(self, db: Session):
        self.db = db

    def get_persona_by_id(self, persona_id: str, user_id: Optional[str] = None) -> Optional[Persona]:
        """
        Get persona by ID
        If user_id provided, checks if user has access
        """
        query = self.db.query(Persona).filter(Persona.id == persona_id)

        if user_id:
            # User can access their own personas or public personas
            query = query.filter(
                or_(
                    Persona.creator_id == user_id,
                    Persona.is_public == True
                )
            )

        return query.first()

    def get_user_personas(
        self,
        user_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[List[Persona], int]:
        """Get all personas created by a user"""
        query = self.db.query(Persona).filter(Persona.creator_id == user_id)

        if status:
            query = query.filter(Persona.status == status)

        total = query.count()
        personas = query.order_by(desc(Persona.created_at)).offset(skip).limit(limit).all()

        return personas, total

    def check_persona_limit(self, user: User, usage: UsageTracking) -> Dict[str, Any]:
        """Check if user can create more personas"""
        if user.is_premium:
            return {"allowed": True}

        # Free tier limit
        if usage.personas_count >= settings.FREE_TIER_PERSONA_LIMIT:
            return {
                "allowed": False,
                "reason": f"Free tier persona limit reached ({settings.FREE_TIER_PERSONA_LIMIT} personas)",
                "limit": settings.FREE_TIER_PERSONA_LIMIT,
                "current": usage.personas_count
            }

        return {"allowed": True}

    def create_persona(
        self,
        user_id: str,
        persona_data: PersonaCreate
    ) -> Persona:
        """Create a new persona"""
        # Get user and usage
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        usage = user.usage_tracking
        if not usage:
            usage = UsageTracking(user_id=user_id)
            self.db.add(usage)
            self.db.commit()
            self.db.refresh(usage)

        # Check limits
        limit_check = self.check_persona_limit(user, usage)
        if not limit_check["allowed"]:
            raise ValueError(limit_check["reason"])

        # Create persona
        persona = Persona(
            creator_id=user_id,
            name=persona_data.name,
            description=persona_data.description,
            bio=persona_data.bio,
            image_path=persona_data.image_path,
            personality_traits=persona_data.personality_traits,
            language_style=persona_data.language_style,
            expertise=persona_data.expertise,
            tags=persona_data.tags,
            voice_id=persona_data.voice_id,
            voice_settings=persona_data.voice_settings,
            is_public=persona_data.is_public,
            is_marketplace=persona_data.is_marketplace,
            status="active"
        )

        self.db.add(persona)

        # Update usage count
        usage.personas_count += 1

        self.db.commit()
        self.db.refresh(persona)

        return persona

    def update_persona(
        self,
        persona_id: str,
        user_id: str,
        persona_data: PersonaUpdate
    ) -> Persona:
        """Update an existing persona"""
        persona = self.db.query(Persona).filter(
            Persona.id == persona_id,
            Persona.creator_id == user_id
        ).first()

        if not persona:
            raise ValueError("Persona not found or access denied")

        # Update fields if provided
        update_data = persona_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(persona, field, value)

        persona.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(persona)

        return persona

    def delete_persona(self, persona_id: str, user_id: str) -> bool:
        """Delete a persona (soft delete by setting status to 'deleted')"""
        persona = self.db.query(Persona).filter(
            Persona.id == persona_id,
            Persona.creator_id == user_id
        ).first()

        if not persona:
            raise ValueError("Persona not found or access denied")

        # Soft delete
        persona.status = "deleted"
        persona.updated_at = datetime.utcnow()

        # Update usage count
        usage = self.db.query(UsageTracking).filter(UsageTracking.user_id == user_id).first()
        if usage and usage.personas_count > 0:
            usage.personas_count -= 1

        self.db.commit()

        return True

    def clone_persona(
        self,
        persona_id: str,
        user_id: str,
        new_name: Optional[str] = None
    ) -> Persona:
        """Clone a persona"""
        # Get original persona
        original = self.get_persona_by_id(persona_id, user_id)
        if not original:
            raise ValueError("Persona not found or not accessible")

        # Check if user can create more personas
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        usage = user.usage_tracking
        limit_check = self.check_persona_limit(user, usage)
        if not limit_check["allowed"]:
            raise ValueError(limit_check["reason"])

        # Create cloned persona
        cloned_name = new_name or f"{original.name} (Clone)"

        cloned_persona = Persona(
            creator_id=user_id,
            name=cloned_name,
            description=original.description,
            bio=original.bio,
            personality_traits=original.personality_traits,
            language_style=original.language_style,
            expertise=original.expertise,
            tags=original.tags,
            voice_id=original.voice_id,
            voice_settings=original.voice_settings,
            is_public=False,  # Cloned personas start as private
            is_marketplace=False,
            status="active",
            cloned_from_persona_id=original.id,
            original_creator_id=original.creator_id
        )

        self.db.add(cloned_persona)

        # Update clone count on original
        original.clone_count += 1

        # Update usage count
        usage.personas_count += 1

        # Clone knowledge bases
        knowledge_bases = self.db.query(KnowledgeBase).filter(
            KnowledgeBase.persona_id == original.id,
            KnowledgeBase.status == "active"
        ).all()

        for kb in knowledge_bases:
            cloned_kb = KnowledgeBase(
                persona_id=cloned_persona.id,
                source_type=kb.source_type,
                source_name=kb.source_name,
                content=kb.content,
                tokens=kb.tokens,
                status=kb.status,
                meta_data=kb.meta_data
            )
            self.db.add(cloned_kb)

        self.db.commit()
        self.db.refresh(cloned_persona)

        return cloned_persona

    def get_trending_personas(
        self,
        timeframe: str = "week",
        limit: int = 20
    ) -> List[Persona]:
        """Get trending personas based on conversation count"""
        # Calculate date threshold
        now = datetime.utcnow()
        if timeframe == "day":
            threshold = now - timedelta(days=1)
        elif timeframe == "week":
            threshold = now - timedelta(days=7)
        else:  # month
            threshold = now - timedelta(days=30)

        # Get public personas sorted by conversation count
        # For simplicity, we're just sorting by conversation_count
        # In production, you might want a more sophisticated algorithm
        personas = self.db.query(Persona).filter(
            Persona.is_public == True,
            Persona.status == "active",
            Persona.created_at >= threshold
        ).order_by(
            desc(Persona.conversation_count),
            desc(Persona.like_count)
        ).limit(limit).all()

        return personas

    def add_knowledge_base(
        self,
        persona_id: str,
        user_id: str,
        kb_data: KnowledgeBaseCreate
    ) -> KnowledgeBase:
        """Add knowledge base entry to a persona"""
        # Verify persona ownership
        persona = self.db.query(Persona).filter(
            Persona.id == persona_id,
            Persona.creator_id == user_id
        ).first()

        if not persona:
            raise ValueError("Persona not found or access denied")

        # Estimate tokens (rough: 1 token ≈ 4 chars)
        tokens = len(kb_data.content) // 4

        # Create knowledge base entry
        kb = KnowledgeBase(
            persona_id=persona_id,
            source_type=kb_data.source_type,
            source_name=kb_data.source_name,
            content=kb_data.content,
            tokens=tokens,
            status="active",
            meta_data=kb_data.meta_data,
            indexed_at=datetime.utcnow()
        )

        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)

        return kb

    def get_persona_knowledge_bases(self, persona_id: str, user_id: str) -> List[KnowledgeBase]:
        """Get all knowledge bases for a persona"""
        # Verify access
        persona = self.get_persona_by_id(persona_id, user_id)
        if not persona:
            raise ValueError("Persona not found or access denied")

        return self.db.query(KnowledgeBase).filter(
            KnowledgeBase.persona_id == persona_id,
            KnowledgeBase.status == "active"
        ).all()

    def search_personas(
        self,
        query: str,
        user_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[Persona], int]:
        """Search public personas by name, description, or tags"""
        db_query = self.db.query(Persona).filter(
            Persona.is_public == True,
            Persona.status == "active"
        )

        # Search in name, description, bio, and tags
        search_filter = or_(
            Persona.name.ilike(f"%{query}%"),
            Persona.description.ilike(f"%{query}%"),
            Persona.bio.ilike(f"%{query}%")
        )

        db_query = db_query.filter(search_filter)

        total = db_query.count()
        personas = db_query.order_by(
            desc(Persona.conversation_count)
        ).offset(skip).limit(limit).all()

        return personas, total
