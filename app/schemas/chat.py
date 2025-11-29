"""Schemas for Chat endpoints"""
from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List, Any
from datetime import datetime, date
from uuid import UUID
from enum import Enum


class ChatSessionCreate(BaseModel):
    """Schema for creating a chat session"""
    persona_id: str = Field(..., description="ID of the persona to chat with")


class ChatMessageCreate(BaseModel):
    """Schema for creating a chat message"""
    text: str = Field(..., min_length=1, description="Message text")
    message_type: str = Field("text", description="Message type: text, image, file, voice")


class ChatMessageResponse(BaseModel):
    """Schema for chat message response"""
    id: Any  # Accept UUID or str
    session_id: Any
    sender_id: Any
    sender_type: str  # "user" or "ai"
    text: str
    message_type: str
    sentiment: Optional[str] = None
    tokens_used: int
    created_at: datetime

    @field_serializer('id', 'session_id', 'sender_id')
    def serialize_uuid(self, value: Any) -> str:
        if isinstance(value, UUID):
            return str(value)
        return str(value) if value else ""

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    """Schema for chat session response"""
    id: Any  # Accept UUID or str
    user_id: Any
    persona_id: Any
    persona_name: str
    persona_image_url: Optional[str] = None
    title: Optional[str] = None
    status: str
    is_pinned: bool
    message_count: int
    last_message: Optional[str] = None
    created_at: datetime
    last_message_at: datetime
    updated_at: datetime

    @field_serializer('id', 'user_id', 'persona_id')
    def serialize_uuid(self, value: Any) -> str:
        if isinstance(value, UUID):
            return str(value)
        return str(value) if value else ""

    class Config:
        from_attributes = True


class ChatSessionDetailResponse(ChatSessionResponse):
    """Schema for chat session with messages"""
    messages: List[ChatMessageResponse] = []


class ChatSessionListResponse(BaseModel):
    """Schema for list of chat sessions"""
    sessions: List[ChatSessionResponse]
    total: int
    page: int
    page_size: int


class ChatExportRequest(BaseModel):
    """Request to export chat"""
    format: str = Field(..., pattern="^(pdf|txt|json)$", description="Export format: pdf, txt, or json")
    include_timestamps: bool = Field(True, description="Include timestamps in export")
    include_metadata: bool = Field(False, description="Include session metadata")


class SendMessageRequest(BaseModel):
    """Request to send a message in a session"""
    message: str = Field(..., min_length=1, description="Message text")
    temperature: Optional[float] = Field(0.9, ge=0.0, le=1.0, description="AI creativity level")


class SendMessageResponse(BaseModel):
    """Response after sending a message"""
    user_message: ChatMessageResponse
    ai_message: ChatMessageResponse


# ============================================================================
# Activity History Schemas
# ============================================================================

class SessionSortField(str, Enum):
    """Fields available for sorting sessions"""
    last_message_at = "last_message_at"
    created_at = "created_at"
    message_count = "message_count"
    persona_name = "persona_name"


class SortOrder(str, Enum):
    """Sort order options"""
    asc = "asc"
    desc = "desc"


class ChatSessionUpdateRequest(BaseModel):
    """Schema for updating a chat session"""
    title: Optional[str] = Field(None, max_length=200, description="Custom session title")
    is_pinned: Optional[bool] = Field(None, description="Pin status")
    status: Optional[str] = Field(None, pattern="^(active|archived)$", description="Session status")


class PersonaActivitySummary(BaseModel):
    """Summary of activity with a specific persona"""
    persona_id: str
    persona_name: str
    persona_image_url: Optional[str] = None
    session_count: int
    message_count: int

    class Config:
        from_attributes = True


class DailyActivityEntry(BaseModel):
    """Activity for a single day"""
    date: date
    sessions_created: int
    messages_sent: int


class ChatStatisticsResponse(BaseModel):
    """Response for chat activity statistics"""
    total_sessions: int
    total_messages: int
    active_sessions: int
    archived_sessions: int
    pinned_sessions: int
    unique_personas: int

    # Most active persona
    most_active_persona: Optional[PersonaActivitySummary] = None

    # Weekly activity breakdown (last 7 days)
    weekly_activity: List[DailyActivityEntry] = []

    # Top personas by message count
    personas_activity: List[PersonaActivitySummary] = []

    # Averages
    avg_messages_per_session: float = 0.0

    # Time-based insights
    most_active_day: Optional[str] = None  # e.g., "Monday"


class ChatSessionSearchResponse(BaseModel):
    """Response for session search"""
    sessions: List[ChatSessionResponse]
    total: int
    page: int
    page_size: int
    query: Optional[str] = None
    filters_applied: dict = {}
