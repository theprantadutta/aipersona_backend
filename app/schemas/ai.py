"""Schemas for AI/Gemini endpoints"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class GenerateRequest(BaseModel):
    """Request to generate AI response"""
    persona_id: str = Field(..., description="ID of the persona to use")
    user_message: str = Field(..., description="The user's message")
    session_id: Optional[str] = Field(None, description="Chat session ID for context")
    temperature: Optional[float] = Field(0.9, ge=0.0, le=1.0, description="Creativity level (0.0-1.0)")
    max_tokens: Optional[int] = Field(None, gt=0, description="Maximum tokens in response")


class StreamGenerateRequest(BaseModel):
    """Request to generate streaming AI response"""
    persona_id: str = Field(..., description="ID of the persona to use")
    user_message: str = Field(..., description="The user's message")
    session_id: Optional[str] = Field(None, description="Chat session ID for context")
    temperature: Optional[float] = Field(0.9, ge=0.0, le=1.0, description="Creativity level (0.0-1.0)")


class UsageInfo(BaseModel):
    """Usage information"""
    messages_today: int
    limit: Optional[int] = None  # None for premium users


class GenerateResponse(BaseModel):
    """Response from AI generation"""
    response: str = Field(..., description="The AI's response")
    tokens_used: int = Field(..., description="Number of tokens used")
    sentiment: str = Field(..., description="Sentiment analysis: positive, negative, neutral")
    usage: UsageInfo = Field(..., description="Current usage information")


class UsageLimitError(BaseModel):
    """Error response for usage limit exceeded"""
    error: str = "usage_limit_exceeded"
    message: str
    limit: int
    used: int


class SentimentRequest(BaseModel):
    """Request for sentiment analysis"""
    text: str = Field(..., description="Text to analyze")


class SentimentResponse(BaseModel):
    """Response from sentiment analysis"""
    text: str
    sentiment: str  # positive, negative, neutral
    confidence: float  # 0.0-1.0
