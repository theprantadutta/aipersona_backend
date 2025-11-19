"""Schemas for File endpoints"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FileUploadResponse(BaseModel):
    """Response after file upload"""
    id: str
    file_path: str
    file_name: str
    file_size: int
    mime_type: str
    category: str
    url: str  # URL to access the file
    created_at: datetime

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """Response for list of files"""
    files: list[FileUploadResponse]
    total: int
    page: int
    page_size: int


class FileDeleteResponse(BaseModel):
    """Response after file deletion"""
    success: bool
    message: str
