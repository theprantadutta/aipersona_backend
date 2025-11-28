"""Chat service for managing chat sessions and messages"""
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func, case
from app.models.chat import ChatSession, ChatMessage
from app.models.persona import Persona
from app.models.user import User
from app.schemas.chat import ChatSessionCreate, ChatMessageCreate
from app.services.gemini_service import GeminiService
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
from collections import defaultdict
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

    # =========================================================================
    # Activity History Methods
    # =========================================================================

    def search_sessions(
        self,
        user_id: str,
        query: Optional[str] = None,
        persona_id: Optional[str] = None,
        status: Optional[str] = None,
        is_pinned: Optional[bool] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        sort_by: str = "last_message_at",
        sort_order: str = "desc",
        skip: int = 0,
        limit: int = 20
    ) -> tuple[List[ChatSession], int, dict]:
        """
        Advanced search for chat sessions with filters

        Returns:
            Tuple of (sessions, total_count, filters_applied)
        """
        base_query = self.db.query(ChatSession).filter(
            ChatSession.user_id == user_id,
            ChatSession.status != "deleted"  # Never show deleted sessions
        )

        filters_applied = {}

        # Text search on persona_name
        if query:
            search_term = f"%{query}%"
            base_query = base_query.filter(
                ChatSession.persona_name.ilike(search_term)
            )
            filters_applied["query"] = query

        # Persona filter
        if persona_id:
            base_query = base_query.filter(ChatSession.persona_id == persona_id)
            filters_applied["persona_id"] = persona_id

        # Status filter (active or archived, not deleted)
        if status and status in ["active", "archived"]:
            base_query = base_query.filter(ChatSession.status == status)
            filters_applied["status"] = status

        # Pinned filter
        if is_pinned is not None:
            base_query = base_query.filter(ChatSession.is_pinned == is_pinned)
            filters_applied["is_pinned"] = is_pinned

        # Date range filters
        if start_date:
            base_query = base_query.filter(
                func.date(ChatSession.last_message_at) >= start_date
            )
            filters_applied["start_date"] = start_date.isoformat()

        if end_date:
            base_query = base_query.filter(
                func.date(ChatSession.last_message_at) <= end_date
            )
            filters_applied["end_date"] = end_date.isoformat()

        # Get total count before pagination
        total = base_query.count()

        # Sorting - pinned items always first
        sort_column = getattr(ChatSession, sort_by, ChatSession.last_message_at)
        if sort_order == "asc":
            base_query = base_query.order_by(
                desc(ChatSession.is_pinned),
                sort_column.asc()
            )
        else:
            base_query = base_query.order_by(
                desc(ChatSession.is_pinned),
                sort_column.desc()
            )

        # Apply pagination
        sessions = base_query.offset(skip).limit(limit).all()

        return sessions, total, filters_applied

    def update_session(
        self,
        session_id: str,
        user_id: str,
        title: Optional[str] = None,
        is_pinned: Optional[bool] = None,
        status: Optional[str] = None
    ) -> ChatSession:
        """
        Update a chat session's properties

        Args:
            session_id: Session ID
            user_id: User ID (for access control)
            title: Custom session title (stored in meta_data)
            is_pinned: Pin status
            status: Session status (active or archived)

        Returns:
            Updated ChatSession
        """
        session = self.get_session_by_id(session_id, user_id)

        if not session:
            raise ValueError("Session not found or access denied")

        if title is not None:
            # Store title in meta_data JSON field
            meta = session.meta_data or {}
            meta["title"] = title
            session.meta_data = meta

        if is_pinned is not None:
            session.is_pinned = is_pinned

        if status is not None and status in ["active", "archived"]:
            session.status = status

        session.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(session)

        return session

    def toggle_pin(self, session_id: str, user_id: str) -> ChatSession:
        """Toggle the pin status of a session"""
        session = self.get_session_by_id(session_id, user_id)

        if not session:
            raise ValueError("Session not found or access denied")

        session.is_pinned = not session.is_pinned
        session.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(session)

        return session

    def get_statistics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive chat activity statistics for a user

        Args:
            user_id: User ID
            days: Number of days to include in weekly activity (default 30, but we show last 7)

        Returns:
            Dict with statistics data
        """
        # Base query for user's sessions (excluding deleted)
        base_query = self.db.query(ChatSession).filter(
            ChatSession.user_id == user_id,
            ChatSession.status != "deleted"
        )

        # Count by status
        status_counts = self.db.query(
            ChatSession.status,
            func.count(ChatSession.id).label("count")
        ).filter(
            ChatSession.user_id == user_id,
            ChatSession.status != "deleted"
        ).group_by(ChatSession.status).all()

        status_dict = {row.status: row.count for row in status_counts}
        active_sessions = status_dict.get("active", 0)
        archived_sessions = status_dict.get("archived", 0)
        total_sessions = active_sessions + archived_sessions

        # Pinned count
        pinned_sessions = base_query.filter(ChatSession.is_pinned == True).count()

        # Total messages
        total_messages = self.db.query(func.sum(ChatSession.message_count)).filter(
            ChatSession.user_id == user_id,
            ChatSession.status != "deleted"
        ).scalar() or 0

        # Unique personas
        unique_personas = self.db.query(
            func.count(func.distinct(ChatSession.persona_id))
        ).filter(
            ChatSession.user_id == user_id,
            ChatSession.status != "deleted"
        ).scalar() or 0

        # Average messages per session
        avg_messages = (total_messages / total_sessions) if total_sessions > 0 else 0

        # Most active personas (top 5)
        persona_activity = self.db.query(
            ChatSession.persona_id,
            ChatSession.persona_name,
            Persona.image_path,
            func.count(ChatSession.id).label("session_count"),
            func.sum(ChatSession.message_count).label("message_count")
        ).outerjoin(
            Persona, ChatSession.persona_id == Persona.id
        ).filter(
            ChatSession.user_id == user_id,
            ChatSession.status != "deleted"
        ).group_by(
            ChatSession.persona_id,
            ChatSession.persona_name,
            Persona.image_path
        ).order_by(
            desc("message_count")
        ).limit(5).all()

        personas_activity = [
            {
                "persona_id": str(row.persona_id),
                "persona_name": row.persona_name,
                "persona_image_url": row.image_path,
                "session_count": row.session_count,
                "message_count": row.message_count or 0
            }
            for row in persona_activity
        ]

        most_active_persona = personas_activity[0] if personas_activity else None

        # Weekly activity (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        # Sessions per day
        daily_sessions = self.db.query(
            func.date(ChatSession.created_at).label("date"),
            func.count(ChatSession.id).label("count")
        ).filter(
            ChatSession.user_id == user_id,
            ChatSession.status != "deleted",
            ChatSession.created_at >= seven_days_ago
        ).group_by(
            func.date(ChatSession.created_at)
        ).all()

        daily_sessions_dict = {row.date: row.count for row in daily_sessions}

        # Messages per day (from ChatMessage)
        daily_messages = self.db.query(
            func.date(ChatMessage.created_at).label("date"),
            func.count(ChatMessage.id).label("count")
        ).join(
            ChatSession, ChatMessage.session_id == ChatSession.id
        ).filter(
            ChatSession.user_id == user_id,
            ChatSession.status != "deleted",
            ChatMessage.created_at >= seven_days_ago
        ).group_by(
            func.date(ChatMessage.created_at)
        ).all()

        daily_messages_dict = {row.date: row.count for row in daily_messages}

        # Build weekly activity list
        weekly_activity = []
        for i in range(6, -1, -1):
            day = (datetime.utcnow() - timedelta(days=i)).date()
            weekly_activity.append({
                "date": day.isoformat(),
                "sessions_created": daily_sessions_dict.get(day, 0),
                "messages_sent": daily_messages_dict.get(day, 0)
            })

        # Most active day of week
        day_of_week_counts = defaultdict(int)
        all_sessions = base_query.all()
        for session in all_sessions:
            day_name = session.last_message_at.strftime("%A")
            day_of_week_counts[day_name] += session.message_count

        most_active_day = None
        if day_of_week_counts:
            most_active_day = max(day_of_week_counts, key=day_of_week_counts.get)

        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "active_sessions": active_sessions,
            "archived_sessions": archived_sessions,
            "pinned_sessions": pinned_sessions,
            "unique_personas": unique_personas,
            "most_active_persona": most_active_persona,
            "weekly_activity": weekly_activity,
            "personas_activity": personas_activity,
            "avg_messages_per_session": round(avg_messages, 1),
            "most_active_day": most_active_day
        }
