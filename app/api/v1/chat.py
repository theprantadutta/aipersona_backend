"""Chat API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.chat_service import ChatService
from datetime import date
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatMessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    ChatExportRequest,
    ChatSessionUpdateRequest,
    ChatStatisticsResponse,
    ChatSessionSearchResponse,
    SessionSortField,
    SortOrder,
    PersonaActivitySummary,
    DailyActivityEntry
)

router = APIRouter(prefix="/chat", tags=["chat"])


def _enrich_session(session, db: Session) -> dict:
    """Enrich session with persona image URL, last message, title, and deleted persona info"""
    # Check if persona is deleted
    is_persona_deleted = session.persona_deleted_at is not None or (
        session.persona and session.persona.status == "deleted"
    )

    session_dict = {
        "id": session.id,
        "user_id": session.user_id,
        "persona_id": session.persona_id,
        "persona_name": session.persona_name,
        "persona_image_url": None,
        "title": None,
        "status": session.status,
        "is_pinned": session.is_pinned,
        "message_count": session.message_count,
        "last_message": None,
        "created_at": session.created_at,
        "last_message_at": session.last_message_at,
        "updated_at": session.updated_at,
        # Deleted persona tracking
        "is_persona_deleted": is_persona_deleted,
        "deleted_persona_name": session.deleted_persona_name,
        "deleted_persona_image": session.deleted_persona_image,
        "persona_deleted_at": session.persona_deleted_at,
    }

    # Get persona image URL (field is image_path in Persona model)
    # Use cached deleted_persona_image if persona was deleted
    if session.persona and not is_persona_deleted:
        session_dict["persona_image_url"] = session.persona.image_path
    elif session.deleted_persona_image:
        session_dict["persona_image_url"] = session.deleted_persona_image

    # Get title from metadata
    if session.meta_data and isinstance(session.meta_data, dict):
        session_dict["title"] = session.meta_data.get("title")

    # Get last message text
    from app.models.chat import ChatMessage
    last_msg = db.query(ChatMessage).filter(
        ChatMessage.session_id == session.id
    ).order_by(ChatMessage.created_at.desc()).first()

    if last_msg:
        session_dict["last_message"] = last_msg.text[:200] if last_msg.text else None

    return session_dict


@router.get("/sessions", response_model=ChatSessionListResponse)
def get_chat_sessions(
    status: Optional[str] = Query(None, pattern="^(active|archived|deleted)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all chat sessions for the current user

    - **status**: Optional filter by status (active, archived, deleted)
    - **page**: Page number (1-indexed)
    - **page_size**: Number of sessions per page (max 100)

    Sessions are ordered by pinned status and last message time
    """
    try:
        skip = (page - 1) * page_size
        service = ChatService(db)
        sessions, total = service.get_user_sessions(
            user_id=str(current_user.id),
            status=status,
            skip=skip,
            limit=page_size
        )

        enriched_sessions = [_enrich_session(s, db) for s in sessions]

        return ChatSessionListResponse(
            sessions=[ChatSessionResponse.model_validate(s) for s in enriched_sessions],
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching chat sessions: {str(e)}"
        )


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new chat session

    - **persona_id**: ID of the persona to chat with

    The persona must be public or owned by the user
    """
    try:
        service = ChatService(db)
        session = service.create_session(
            user_id=str(current_user.id),
            session_data=session_data
        )

        return ChatSessionResponse.model_validate(session)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating chat session: {str(e)}"
        )


# NOTE: /sessions/search MUST come BEFORE /sessions/{session_id} to avoid route conflict
@router.get("/sessions/search", response_model=ChatSessionSearchResponse)
def search_sessions(
    q: Optional[str] = Query(None, description="Search query for persona name or messages"),
    persona_id: Optional[str] = Query(None, description="Filter by persona ID"),
    search_status: Optional[str] = Query(None, alias="status", pattern="^(active|archived)$", description="Filter by status"),
    is_pinned: Optional[bool] = Query(None, description="Filter by pinned status"),
    start_date: Optional[date] = Query(None, description="Filter sessions from this date"),
    end_date: Optional[date] = Query(None, description="Filter sessions until this date"),
    sort_by: SessionSortField = Query(SessionSortField.last_message_at, description="Field to sort by"),
    sort_order: SortOrder = Query(SortOrder.desc, description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Advanced search for chat sessions with filtering and sorting

    - **q**: Search query (searches persona name and message content)
    - **persona_id**: Filter by specific persona
    - **status**: Filter by session status (active/archived)
    - **is_pinned**: Filter pinned sessions only
    - **start_date**: Filter sessions created after this date
    - **end_date**: Filter sessions created before this date
    - **sort_by**: Sort field (last_message_at, created_at, message_count, persona_name)
    - **sort_order**: Sort direction (asc/desc)

    Pinned sessions always appear first regardless of sort order
    """
    try:
        skip = (page - 1) * page_size
        service = ChatService(db)

        sessions, total, filters_applied = service.search_sessions(
            user_id=str(current_user.id),
            query=q,
            persona_id=persona_id,
            status=search_status,
            is_pinned=is_pinned,
            start_date=start_date,
            end_date=end_date,
            sort_by=sort_by.value,
            sort_order=sort_order.value,
            skip=skip,
            limit=page_size
        )

        enriched_sessions = [_enrich_session(s, db) for s in sessions]

        return ChatSessionSearchResponse(
            sessions=[ChatSessionResponse.model_validate(s) for s in enriched_sessions],
            total=total,
            page=page,
            page_size=page_size,
            query=q,
            filters_applied=filters_applied
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching sessions: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_chat_session(
    session_id: str,
    include_messages: bool = Query(True, description="Include messages in response"),
    messages_limit: int = Query(100, ge=1, le=500, description="Maximum number of messages to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific chat session by ID

    - **session_id**: Session ID
    - **include_messages**: Whether to include messages (default: true)
    - **messages_limit**: Maximum number of messages to return (default: 100, max: 500)
    """
    try:
        service = ChatService(db)
        session = service.get_session_by_id(session_id, str(current_user.id))

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied"
            )

        response_data = ChatSessionResponse.model_validate(session)

        if include_messages:
            messages = service.get_session_messages(
                session_id=session_id,
                user_id=str(current_user.id),
                limit=messages_limit
            )

            return ChatSessionDetailResponse(
                **response_data.model_dump(),
                messages=[ChatMessageResponse.model_validate(m) for m in messages]
            )

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching chat session: {str(e)}"
        )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a chat session (soft delete)

    - **session_id**: Session ID

    Only the session owner can delete it
    """
    try:
        service = ChatService(db)
        service.delete_session(session_id, str(current_user.id))

        return None

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting chat session: {str(e)}"
        )


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
def get_session_messages(
    session_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get messages from a chat session

    - **session_id**: Session ID
    - **skip**: Number of messages to skip (for pagination)
    - **limit**: Maximum number of messages to return (max: 500)

    Messages are returned in chronological order (oldest first)
    """
    try:
        service = ChatService(db)
        messages = service.get_session_messages(
            session_id=session_id,
            user_id=str(current_user.id),
            skip=skip,
            limit=limit
        )

        return [ChatMessageResponse.model_validate(m) for m in messages]

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching messages: {str(e)}"
        )


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(
    session_id: str,
    message_data: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Send a message in a chat session and get AI response

    - **session_id**: Session ID
    - **message**: Message text
    - **temperature**: Optional AI creativity level (0.0-1.0, default: 0.9)

    This will:
    1. Save the user's message
    2. Generate an AI response using the persona
    3. Save the AI response
    4. Update session metadata
    5. Return both messages

    May return 429 error if user has exceeded their daily message limit (free tier)
    """
    try:
        service = ChatService(db)
        result = await service.send_message(
            session_id=session_id,
            user_id=str(current_user.id),
            message_text=message_data.message,
            temperature=message_data.temperature
        )

        return SendMessageResponse(
            user_message=ChatMessageResponse.model_validate(result["user_message"]),
            ai_message=ChatMessageResponse.model_validate(result["ai_message"])
        )

    except ValueError as e:
        # Check if it's a usage limit error
        error_msg = str(e)
        if "limit" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending message: {str(e)}"
        )


@router.post("/sessions/{session_id}/export")
async def export_chat_session(
    session_id: str,
    export_data: ChatExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export a chat session

    - **session_id**: Session ID
    - **format**: Export format (pdf, txt, json)
    - **include_timestamps**: Include timestamps in export
    - **include_metadata**: Include session metadata

    Returns the chat in the requested format
    """
    try:
        service = ChatService(db)
        export_result = service.export_session(
            session_id=session_id,
            user_id=str(current_user.id),
            format=export_data.format,
            include_timestamps=export_data.include_timestamps,
            include_metadata=export_data.include_metadata
        )

        return JSONResponse(content=export_result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting chat session: {str(e)}"
        )


@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
def update_session(
    session_id: str,
    update_data: ChatSessionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a chat session's properties

    - **session_id**: Session ID to update
    - **title**: Custom title for the session
    - **is_pinned**: Pin or unpin the session
    - **status**: Change status (active/archived)

    Only the session owner can update it
    """
    try:
        service = ChatService(db)
        session = service.update_session(
            session_id=session_id,
            user_id=str(current_user.id),
            title=update_data.title,
            is_pinned=update_data.is_pinned,
            status=update_data.status
        )

        return ChatSessionResponse.model_validate(session)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating session: {str(e)}"
        )


@router.post("/sessions/{session_id}/pin", response_model=ChatSessionResponse)
def toggle_session_pin(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Toggle pin status of a chat session

    - **session_id**: Session ID to toggle pin

    Returns the updated session with new pin status
    """
    try:
        service = ChatService(db)
        session = service.toggle_pin(
            session_id=session_id,
            user_id=str(current_user.id)
        )

        return ChatSessionResponse.model_validate(session)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error toggling pin: {str(e)}"
        )


@router.get("/statistics", response_model=ChatStatisticsResponse)
def get_chat_statistics(
    days: int = Query(30, ge=7, le=365, description="Number of days to calculate stats for"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get chat activity statistics for the current user

    - **days**: Number of days to include in statistics (default: 30)

    Returns:
    - Total sessions and messages
    - Active, archived, and pinned session counts
    - Most active persona with message count
    - Weekly activity breakdown (last 7 days)
    - Top personas by activity
    - Average messages per session
    - Most active day of the week
    """
    try:
        service = ChatService(db)
        stats = service.get_statistics(
            user_id=str(current_user.id),
            days=days
        )

        # Convert to response model
        most_active = None
        if stats.get("most_active_persona"):
            most_active = PersonaActivitySummary(**stats["most_active_persona"])

        weekly_activity = [
            DailyActivityEntry(**entry) for entry in stats.get("weekly_activity", [])
        ]

        personas_activity = [
            PersonaActivitySummary(**p) for p in stats.get("personas_activity", [])
        ]

        return ChatStatisticsResponse(
            total_sessions=stats["total_sessions"],
            total_messages=stats["total_messages"],
            active_sessions=stats["active_sessions"],
            archived_sessions=stats["archived_sessions"],
            pinned_sessions=stats["pinned_sessions"],
            unique_personas=stats["unique_personas"],
            most_active_persona=most_active,
            weekly_activity=weekly_activity,
            personas_activity=personas_activity,
            avg_messages_per_session=stats["avg_messages_per_session"],
            most_active_day=stats.get("most_active_day")
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching statistics: {str(e)}"
        )
