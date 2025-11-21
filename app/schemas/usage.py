"""Schemas for Usage tracking endpoints"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date


class CurrentUsageResponse(BaseModel):
    """Current usage stats for the user"""
    messages_today: int
    messages_limit: Optional[int] = None  # None for premium
    personas_count: int
    personas_limit: Optional[int] = None  # None for premium
    storage_used_bytes: int
    storage_used_mb: float
    gemini_api_calls_today: int
    gemini_tokens_used_total: int
    last_reset_at: datetime
    is_premium: bool
    subscription_tier: str


class UsageHistoryEntry(BaseModel):
    """Single day's usage entry"""
    date: date
    messages_count: int
    api_calls: int
    tokens_used: int


class UsageHistoryResponse(BaseModel):
    """Historical usage data"""
    entries: List[UsageHistoryEntry]
    period_start: date
    period_end: date
    total_messages: int
    total_api_calls: int
    total_tokens: int


class UsageAnalyticsResponse(BaseModel):
    """Advanced usage analytics"""
    current_usage: CurrentUsageResponse
    daily_average: float
    peak_usage_day: Optional[date] = None
    peak_usage_count: int
    trend: str  # "increasing", "decreasing", "stable"
    usage_percentage: Optional[float] = None  # Percentage of limit used (free tier only)
    predictions: Dict[str, Any]  # Predicted usage patterns


class ExportUsageRequest(BaseModel):
    """Request to export usage data"""
    start_date: date = Field(..., description="Start date for export")
    end_date: date = Field(..., description="End date for export")
    format: str = Field("json", pattern="^(json|csv)$", description="Export format")
    include_details: bool = Field(True, description="Include detailed breakdown")
