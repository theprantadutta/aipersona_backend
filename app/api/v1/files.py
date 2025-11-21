"""File API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
import os

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.file_service import FileService
from app.schemas.file import FileUploadResponse, FileListResponse, FileDeleteResponse
from app.config import settings

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    category: str = Query("chat_attachment", pattern="^(avatar|persona_image|chat_attachment|knowledge_base)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a file

    - **file**: The file to upload
    - **category**: File category (avatar, persona_image, chat_attachment, knowledge_base)

    Supported formats: jpg, jpeg, png, gif, pdf, txt, mp3, wav, m4a
    Maximum file size: 10MB

    Returns file metadata including ID and URL to access the file
    """
    try:
        service = FileService(db)
        uploaded_file = await service.upload_file(
            user_id=str(current_user.id),
            file=file,
            category=category
        )

        # Build file URL
        base_url = f"https://{settings.DATABASE_HOST}" if settings.DATABASE_HOST != "localhost" else "http://localhost:8000"
        file_url = service.get_file_url(uploaded_file, base_url)

        response = FileUploadResponse(
            id=str(uploaded_file.id),
            file_path=uploaded_file.file_path,
            file_name=uploaded_file.file_name,
            file_size=uploaded_file.file_size,
            mime_type=uploaded_file.mime_type,
            category=uploaded_file.category,
            url=file_url,
            created_at=uploaded_file.created_at
        )

        return response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}"
        )


@router.get("", response_model=FileListResponse)
def get_user_files(
    category: Optional[str] = Query(None, pattern="^(avatar|persona_image|chat_attachment|knowledge_base)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all files uploaded by the current user

    - **category**: Optional filter by category
    - **page**: Page number (1-indexed)
    - **page_size**: Number of files per page (max 100)
    """
    try:
        skip = (page - 1) * page_size
        service = FileService(db)
        files, total = service.get_user_files(
            user_id=str(current_user.id),
            category=category,
            skip=skip,
            limit=page_size
        )

        # Build URLs
        base_url = f"https://{settings.DATABASE_HOST}" if settings.DATABASE_HOST != "localhost" else "http://localhost:8000"

        file_responses = [
            FileUploadResponse(
                id=str(f.id),
                file_path=f.file_path,
                file_name=f.file_name,
                file_size=f.file_size,
                mime_type=f.mime_type,
                category=f.category,
                url=service.get_file_url(f, base_url),
                created_at=f.created_at
            )
            for f in files
        ]

        return FileListResponse(
            files=file_responses,
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching files: {str(e)}"
        )


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download/view a file by ID

    Returns the actual file content
    User can only access their own files
    """
    try:
        service = FileService(db)
        file = service.get_file_by_id(file_id, str(current_user.id))

        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or access denied"
            )

        if not os.path.exists(file.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found on disk"
            )

        return FileResponse(
            path=file.file_path,
            media_type=file.mime_type,
            filename=file.file_name
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching file: {str(e)}"
        )


@router.delete("/{file_id}", response_model=FileDeleteResponse)
def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a file

    User can only delete their own files
    This will delete both the database record and the physical file
    """
    try:
        service = FileService(db)
        service.delete_file(file_id, str(current_user.id))

        return FileDeleteResponse(
            success=True,
            message="File deleted successfully"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting file: {str(e)}"
        )
