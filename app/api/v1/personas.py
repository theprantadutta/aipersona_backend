"""Persona API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.core.dependencies import get_current_user, get_optional_current_user
from app.models.user import User
from app.models.persona import Persona
from app.services.persona_service import PersonaService
from app.schemas.persona import (
    PersonaCreate,
    PersonaUpdate,
    PersonaResponse,
    PersonaListResponse,
    PersonaCloneRequest,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    TrendingPersonasResponse
)

router = APIRouter(prefix="/personas", tags=["personas"])


def persona_to_response(persona: Persona, current_user_id: Optional[UUID] = None) -> PersonaResponse:
    """Convert Persona model to PersonaResponse with is_owner flag"""
    response = PersonaResponse.model_validate(persona)
    if current_user_id is not None:
        response.is_owner = str(persona.creator_id) == str(current_user_id)
    return response


@router.get("", response_model=PersonaListResponse)
def get_user_personas(
    status: Optional[str] = Query(None, description="Filter by status: active, draft, archived"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all personas created by the current user

    - **status**: Optional filter by status (active, draft, archived)
    - **page**: Page number (1-indexed)
    - **page_size**: Number of personas per page (max 100)
    """
    try:
        skip = (page - 1) * page_size
        service = PersonaService(db)
        personas, total = service.get_user_personas(
            user_id=str(current_user.id),
            status=status,
            skip=skip,
            limit=page_size
        )

        return PersonaListResponse(
            personas=[persona_to_response(p, current_user.id) for p in personas],
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching personas: {str(e)}"
        )


@router.post("", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
def create_persona(
    persona_data: PersonaCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new persona

    - **name**: Persona name (required)
    - **description**: Short description
    - **bio**: Detailed bio
    - **personality_traits**: List of personality traits
    - **language_style**: Communication style (casual, formal, friendly, etc.)
    - **expertise**: List of expertise areas
    - **tags**: List of tags for discovery
    - **voice_id**: Voice ID for TTS
    - **voice_settings**: Voice configuration
    - **is_public**: Whether persona is publicly discoverable
    - **is_marketplace**: Whether persona is listed in marketplace
    """
    try:
        service = PersonaService(db)
        persona = service.create_persona(
            user_id=str(current_user.id),
            persona_data=persona_data
        )

        return persona_to_response(persona, current_user.id)

    except ValueError as e:
        # User-facing errors (limits, validation)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating persona: {str(e)}"
        )


@router.get("/trending", response_model=TrendingPersonasResponse)
def get_trending_personas(
    timeframe: str = Query("week", pattern="^(day|week|month)$"),
    limit: int = Query(20, ge=1, le=50),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Get trending personas

    - **timeframe**: Time period (day, week, month)
    - **limit**: Number of personas to return (max 50)
    """
    try:
        service = PersonaService(db)
        personas = service.get_trending_personas(timeframe=timeframe, limit=limit)
        user_id = current_user.id if current_user else None

        return TrendingPersonasResponse(
            personas=[persona_to_response(p, user_id) for p in personas],
            timeframe=timeframe
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching trending personas: {str(e)}"
        )


@router.get("/public", response_model=PersonaListResponse)
def get_public_personas(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all public personas (no authentication required)

    - **page**: Page number (1-indexed)
    - **page_size**: Number of personas per page (max 100)
    """
    try:
        skip = (page - 1) * page_size

        # Get all public personas with creator info
        query = db.query(Persona).options(joinedload(Persona.creator)).filter(
            Persona.is_public == True,
            Persona.status == "active"
        )
        total = query.count()
        personas = query.order_by(Persona.created_at.desc()).offset(skip).limit(page_size).all()
        user_id = current_user.id if current_user else None

        return PersonaListResponse(
            personas=[persona_to_response(p, user_id) for p in personas],
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching public personas: {str(e)}"
        )


@router.get("/search", response_model=PersonaListResponse)
def search_personas(
    q: str = Query(..., min_length=1, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search public personas

    - **q**: Search query (searches name, description, bio, tags)
    - **page**: Page number
    - **page_size**: Results per page
    """
    try:
        skip = (page - 1) * page_size
        service = PersonaService(db)
        personas, total = service.search_personas(
            query=q,
            user_id=str(current_user.id),
            skip=skip,
            limit=page_size
        )

        return PersonaListResponse(
            personas=[persona_to_response(p, current_user.id) for p in personas],
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching personas: {str(e)}"
        )


@router.get("/{persona_id}", response_model=PersonaResponse)
def get_persona(
    persona_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific persona by ID

    User can access their own personas or public personas
    """
    try:
        service = PersonaService(db)
        persona = service.get_persona_by_id(persona_id, str(current_user.id))

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Persona not found or access denied"
            )

        return persona_to_response(persona, current_user.id)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching persona: {str(e)}"
        )


@router.put("/{persona_id}", response_model=PersonaResponse)
def update_persona(
    persona_id: str,
    persona_data: PersonaUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a persona

    Only the creator can update a persona
    All fields are optional - only provided fields will be updated
    """
    try:
        service = PersonaService(db)
        persona = service.update_persona(
            persona_id=persona_id,
            user_id=str(current_user.id),
            persona_data=persona_data
        )

        return persona_to_response(persona, current_user.id)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating persona: {str(e)}"
        )


@router.delete("/{persona_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_persona(
    persona_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a persona (soft delete)

    Only the creator can delete a persona
    """
    try:
        service = PersonaService(db)
        service.delete_persona(persona_id=persona_id, user_id=str(current_user.id))

        return None

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting persona: {str(e)}"
        )


@router.post("/{persona_id}/clone", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
def clone_persona(
    persona_id: str,
    clone_data: PersonaCloneRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Clone a persona

    - **new_name**: Optional new name for the cloned persona
    - **customize**: If true, returns the clone in draft mode for customization

    Cloned personas include all knowledge bases from the original
    """
    try:
        service = PersonaService(db)
        persona = service.clone_persona(
            persona_id=persona_id,
            user_id=str(current_user.id),
            new_name=clone_data.new_name
        )

        # If customize is true, set status to draft
        if clone_data.customize:
            persona.status = "draft"
            db.commit()
            db.refresh(persona)

        return persona_to_response(persona, current_user.id)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cloning persona: {str(e)}"
        )


@router.post("/{persona_id}/knowledge", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
def add_knowledge_base(
    persona_id: str,
    kb_data: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add knowledge base entry to a persona

    - **source_type**: Type of source (text, file, url, document)
    - **source_name**: Name/title of the source
    - **content**: The actual knowledge content
    - **meta_data**: Optional metadata

    Only the persona creator can add knowledge bases
    """
    try:
        service = PersonaService(db)
        kb = service.add_knowledge_base(
            persona_id=persona_id,
            user_id=str(current_user.id),
            kb_data=kb_data
        )

        return KnowledgeBaseResponse.model_validate(kb)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding knowledge base: {str(e)}"
        )


@router.get("/{persona_id}/knowledge", response_model=List[KnowledgeBaseResponse])
def get_persona_knowledge_bases(
    persona_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all knowledge bases for a persona

    User must have access to the persona (creator or public)
    """
    try:
        service = PersonaService(db)
        knowledge_bases = service.get_persona_knowledge_bases(
            persona_id=persona_id,
            user_id=str(current_user.id)
        )

        return [KnowledgeBaseResponse.model_validate(kb) for kb in knowledge_bases]

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching knowledge bases: {str(e)}"
        )
