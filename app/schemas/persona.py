"""Schemas for Persona endpoints"""
from pydantic import BaseModel, Field, field_validator, field_serializer
from typing import Optional, List
from datetime import datetime
import uuid

from app.utils.time_utils import to_utc_isoformat


class PersonaBase(BaseModel):
    """Base persona schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    bio: Optional[str] = None
    image_path: Optional[str] = None
    personality_traits: Optional[List[str]] = None
    language_style: Optional[str] = None
    expertise: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    voice_id: Optional[str] = None
    voice_settings: Optional[dict] = None
    is_public: bool = True
    is_marketplace: bool = False


class PersonaCreate(PersonaBase):
    """Schema for creating a persona"""
    pass


class PersonaUpdate(BaseModel):
    """Schema for updating a persona (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    bio: Optional[str] = None
    image_path: Optional[str] = None
    personality_traits: Optional[List[str]] = None
    language_style: Optional[str] = None
    expertise: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    voice_id: Optional[str] = None
    voice_settings: Optional[dict] = None
    is_public: Optional[bool] = None
    is_marketplace: Optional[bool] = None
    status: Optional[str] = None  # active, draft, archived


class PersonaResponse(PersonaBase):
    """Schema for persona response"""
    id: str
    creator_id: str
    creator_name: Optional[str] = None
    creator_avatar_url: Optional[str] = None
    image_path: Optional[str] = None
    status: str
    conversation_count: int
    clone_count: int
    like_count: int
    cloned_from_persona_id: Optional[str] = None
    original_creator_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_owner: bool = False  # Whether current user is the creator
    is_liked: bool = False  # Whether current user has liked this persona

    @field_validator('id', 'creator_id', 'cloned_from_persona_id', 'original_creator_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID objects to strings"""
        if isinstance(v, uuid.UUID):
            return str(v)
        return v

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_isoformat(value)

    class Config:
        from_attributes = True


class PersonaListResponse(BaseModel):
    """Schema for list of personas"""
    personas: List[PersonaResponse]
    total: int
    page: int
    page_size: int


class PersonaCloneRequest(BaseModel):
    """Request to clone a persona"""
    new_name: Optional[str] = None
    customize: bool = False  # If true, allows user to customize after cloning


class KnowledgeBaseCreate(BaseModel):
    """Schema for creating knowledge base entry"""
    source_type: str = Field(..., description="text, file, url, document")
    source_name: Optional[str] = None
    content: str = Field(..., min_length=1)
    meta_data: Optional[dict] = None


class KnowledgeBaseResponse(BaseModel):
    """Schema for knowledge base response"""
    id: str
    persona_id: str
    source_type: str
    source_name: Optional[str]
    content: str
    tokens: int
    status: str
    indexed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @field_validator('id', 'persona_id', mode='before')
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID objects to strings"""
        if isinstance(v, uuid.UUID):
            return str(v)
        return v

    @field_serializer('indexed_at', 'created_at', 'updated_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return to_utc_isoformat(value)

    class Config:
        from_attributes = True


class TrendingPersonasResponse(BaseModel):
    """Schema for trending personas"""
    personas: List[PersonaResponse]
    timeframe: str  # "day", "week", "month"
