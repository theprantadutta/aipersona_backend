"""Chat API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.chat_service import ChatService
from app.schemas.chat import (
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatMessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    ChatExportRequest
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions", response_model=ChatSessionListResponse)
def get_chat_sessions(
    status: Optional[str] = Query(None, regex="^(active|archived|deleted)$"),
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

        return ChatSessionListResponse(
            sessions=[ChatSessionResponse.model_validate(s) for s in sessions],
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
