"""Schemas for Chat endpoints"""
from pydantic import BaseModel, Field, field_serializer
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID


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
    status: str
    is_pinned: bool
    message_count: int
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
    ai_response: ChatMessageResponse
