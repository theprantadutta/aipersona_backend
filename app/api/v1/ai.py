"""AI/Gemini API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import AsyncIterator
import json

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.chat import ChatSession, ChatMessage
from app.services.gemini_service import GeminiService
from app.schemas.ai import (
    GenerateRequest,
    GenerateResponse,
    StreamGenerateRequest,
    SentimentRequest,
    SentimentResponse,
    UsageLimitError
)

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/generate", response_model=GenerateResponse)
async def generate_response(
    request: GenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate AI response using Gemini

    - **persona_id**: ID of the persona to use for the response
    - **user_message**: The user's message
    - **session_id**: Optional chat session ID for conversation context
    - **temperature**: Creativity level (0.0-1.0), default 0.9
    - **max_tokens**: Maximum tokens in response (optional)

    Returns the AI's response, tokens used, sentiment, and usage info
    """
    try:
        # Get conversation history if session_id provided
        conversation_history = []
        if request.session_id:
            session = db.query(ChatSession).filter(
                ChatSession.id == request.session_id,
                ChatSession.user_id == current_user.id
            ).first()

            if session:
                # Get recent messages from this session
                conversation_history = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session.id
                ).order_by(ChatMessage.created_at.asc()).all()

        # Generate response
        gemini_service = GeminiService(db)
        result = await gemini_service.generate_response(
            user_id=str(current_user.id),
            persona_id=request.persona_id,
            user_message=request.user_message,
            conversation_history=conversation_history,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        # Check for usage limit error
        if "error" in result:
            if result["error"] == "usage_limit_exceeded":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": result["error"],
                        "message": result["message"],
                        "limit": result.get("limit"),
                        "used": result.get("used")
                    }
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=result.get("message", "Unknown error")
                )

        return GenerateResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating response: {str(e)}"
        )


@router.post("/stream")
async def generate_streaming_response(
    request: StreamGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate streaming AI response using Gemini (Server-Sent Events)

    - **persona_id**: ID of the persona to use for the response
    - **user_message**: The user's message
    - **session_id**: Optional chat session ID for conversation context
    - **temperature**: Creativity level (0.0-1.0), default 0.9

    Returns a stream of response chunks as Server-Sent Events
    """
    try:
        # Get conversation history if session_id provided
        conversation_history = []
        if request.session_id:
            session = db.query(ChatSession).filter(
                ChatSession.id == request.session_id,
                ChatSession.user_id == current_user.id
            ).first()

            if session:
                conversation_history = db.query(ChatMessage).filter(
                    ChatMessage.session_id == session.id
                ).order_by(ChatMessage.created_at.asc()).all()

        # Generate streaming response
        gemini_service = GeminiService(db)

        async def event_stream() -> AsyncIterator[str]:
            """Stream Server-Sent Events"""
            async for chunk in gemini_service.generate_streaming_response(
                user_id=str(current_user.id),
                persona_id=request.persona_id,
                user_message=request.user_message,
                conversation_history=conversation_history,
                temperature=request.temperature
            ):
                # Format as SSE
                yield f"data: {chunk}\n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating streaming response: {str(e)}"
        )


@router.post("/sentiment", response_model=SentimentResponse)
async def analyze_sentiment(
    request: SentimentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze sentiment of text

    - **text**: The text to analyze

    Returns sentiment (positive, negative, neutral) and confidence score
    """
    try:
        gemini_service = GeminiService(db)
        sentiment = gemini_service._analyze_sentiment(request.text)

        # Simple confidence based on text length and sentiment indicators
        # In production, use a proper sentiment model
        confidence = 0.7  # Basic confidence

        return SentimentResponse(
            text=request.text,
            sentiment=sentiment,
            confidence=confidence
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing sentiment: {str(e)}"
        )
