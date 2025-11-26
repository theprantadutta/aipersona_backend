"""Chat service for managing chat sessions and messages"""
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from app.models.chat import ChatSession, ChatMessage
from app.models.persona import Persona
from app.models.user import User
from app.schemas.chat import ChatSessionCreate, ChatMessageCreate
from app.services.gemini_service import GeminiService
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


class ChatService:
    """Service for chat session and message management"""

    def __init__(self, db: Session):
        self.db = db

    def create_session(
        self,
        user_id: str,
        session_data: ChatSessionCreate
    ) -> ChatSession:
        """Create a new chat session"""
        # Verify persona exists and is accessible
        persona = self.db.query(Persona).filter(
            Persona.id == session_data.persona_id
        ).first()

        if not persona:
            raise ValueError("Persona not found")

        # Check if user can access this persona
        if not persona.is_public and persona.creator_id != user_id:
            raise ValueError("Access denied to this persona")

        # Create session
        session = ChatSession(
            user_id=user_id,
            persona_id=session_data.persona_id,
            persona_name=persona.name,
            status="active"
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return session

    def get_session_by_id(
        self,
        session_id: str,
        user_id: str
    ) -> Optional[ChatSession]:
        """Get a chat session by ID (with access control)"""
        return self.db.query(ChatSession).filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id
        ).first()

    def get_user_sessions(
        self,
        user_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[List[ChatSession], int]:
        """Get all chat sessions for a user"""
        query = self.db.query(ChatSession).filter(ChatSession.user_id == user_id)

        if status:
            query = query.filter(ChatSession.status == status)

        total = query.count()
        sessions = query.order_by(
            desc(ChatSession.is_pinned),
            desc(ChatSession.last_message_at)
        ).offset(skip).limit(limit).all()

        return sessions, total

    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a chat session (soft delete)"""
        session = self.get_session_by_id(session_id, user_id)

        if not session:
            raise ValueError("Session not found or access denied")

        # Soft delete
        session.status = "deleted"
        session.updated_at = datetime.utcnow()

        self.db.commit()

        return True

    def get_session_messages(
        self,
        session_id: str,
        user_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[ChatMessage]:
        """Get messages from a chat session"""
        # Verify session access
        session = self.get_session_by_id(session_id, user_id)

        if not session:
            raise ValueError("Session not found or access denied")

        messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).offset(skip).limit(limit).all()

        return messages

    async def send_message(
        self,
        session_id: str,
        user_id: str,
        message_text: str,
        temperature: float = 0.9
    ) -> Dict[str, ChatMessage]:
        """
        Send a message in a chat session and get AI response

        Returns dict with 'user_message' and 'ai_message'

        Special marker [GREETING] triggers an in-character greeting from the persona
        """
        # Verify session access
        session = self.get_session_by_id(session_id, user_id)

        if not session:
            raise ValueError("Session not found or access denied")

        # Check if this is a greeting request
        is_greeting = message_text.strip() == "[GREETING]"

        if is_greeting:
            # For greetings, create a prompt asking the persona to introduce themselves
            actual_message = "Please introduce yourself in character. Give a brief, engaging greeting that shows your personality."
        else:
            actual_message = message_text

        # Create user message (hidden for greetings)
        user_message = ChatMessage(
            session_id=session_id,
            sender_id=user_id,
            sender_type="user",
            text="[System: User opened chat]" if is_greeting else message_text,
            message_type="system" if is_greeting else "text",
            tokens_used=0
        )

        self.db.add(user_message)

        # Get conversation history for context
        conversation_history = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()

        # Generate AI response
        gemini_service = GeminiService(self.db)
        ai_result = await gemini_service.generate_response(
            user_id=user_id,
            persona_id=str(session.persona_id),
            user_message=actual_message,
            conversation_history=[] if is_greeting else conversation_history,  # No history for greeting
            temperature=temperature
        )

        # Check for errors (usage limits)
        if "error" in ai_result:
            # Still save the user message but return error
            self.db.commit()
            raise ValueError(ai_result.get("message", "Error generating AI response"))

        # Create AI message
        ai_message = ChatMessage(
            session_id=session_id,
            sender_id=str(session.persona_id),
            sender_type="ai",
            text=ai_result["response"],
            message_type="text",
            sentiment=ai_result.get("sentiment"),
            tokens_used=ai_result.get("tokens_used", 0)
        )

        self.db.add(ai_message)

        # Update session
        session.message_count += 2  # User message + AI response
        session.last_message_at = datetime.utcnow()
        session.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(user_message)
        self.db.refresh(ai_message)

        return {
            "user_message": user_message,
            "ai_message": ai_message
        }

    def export_session(
        self,
        session_id: str,
        user_id: str,
        format: str = "json",
        include_timestamps: bool = True,
        include_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        Export chat session

        Args:
            session_id: Session ID
            user_id: User ID (for access control)
            format: Export format (json, txt, pdf)
            include_timestamps: Include message timestamps
            include_metadata: Include session metadata

        Returns:
            Dict with export data
        """
        # Verify session access
        session = self.get_session_by_id(session_id, user_id)

        if not session:
            raise ValueError("Session not found or access denied")

        # Get all messages
        messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()

        export_data = {
            "format": format,
            "session_id": str(session.id),
            "persona_name": session.persona_name,
            "exported_at": datetime.utcnow().isoformat()
        }

        if include_metadata:
            export_data["metadata"] = {
                "created_at": session.created_at.isoformat(),
                "message_count": session.message_count,
                "status": session.status
            }

        # Format messages based on export format
        if format == "json":
            export_data["messages"] = [
                {
                    "sender": msg.sender_type,
                    "text": msg.text,
                    "timestamp": msg.created_at.isoformat() if include_timestamps else None
                }
                for msg in messages
            ]

        elif format == "txt":
            lines = []
            if include_metadata:
                lines.append(f"Chat with {session.persona_name}")
                lines.append(f"Created: {session.created_at}")
                lines.append("-" * 50)
                lines.append("")

            for msg in messages:
                sender_label = "You" if msg.sender_type == "user" else session.persona_name
                timestamp_str = f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] " if include_timestamps else ""
                lines.append(f"{timestamp_str}{sender_label}: {msg.text}")
                lines.append("")

            export_data["content"] = "\n".join(lines)

        elif format == "pdf":
            # For PDF, return structured data that frontend can render
            # Frontend should handle PDF generation
            export_data["title"] = f"Chat with {session.persona_name}"
            export_data["messages"] = [
                {
                    "sender": "You" if msg.sender_type == "user" else session.persona_name,
                    "text": msg.text,
                    "timestamp": msg.created_at.isoformat() if include_timestamps else None
                }
                for msg in messages
            ]

        return export_data

    def cleanup_old_free_tier_sessions(self, days: int = 7):
        """
        Clean up old chat sessions for free tier users
        Called by background scheduler
        """
        threshold = datetime.utcnow() - timedelta(days=days)

        # Get free tier users
        free_users = self.db.query(User).filter(User.subscription_tier == "free").all()
        free_user_ids = [str(u.id) for u in free_users]

        if not free_user_ids:
            return

        # Delete old sessions
        deleted_count = self.db.query(ChatSession).filter(
            and_(
                ChatSession.user_id.in_(free_user_ids),
                ChatSession.last_message_at < threshold,
                ChatSession.status == "active"
            )
        ).update({"status": "deleted"}, synchronize_session=False)

        self.db.commit()

        logger.info(f"Cleaned up {deleted_count} old free tier chat sessions")

        return deleted_count
