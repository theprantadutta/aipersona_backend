"""File service for handling file uploads via FileRunner"""
from sqlalchemy.orm import Session
from app.models.file import UploadedFile
from app.models.user import User, UsageTracking
from app.config import settings
from app.services.filerunner_service import filerunner_service
from typing import Optional, List, Dict, Any
from fastapi import UploadFile
from PIL import Image
import os
import uuid
import aiofiles
import logging
import io
from pathlib import Path

logger = logging.getLogger(__name__)


class FileService:
    """Service for file upload and management using FileRunner"""

    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = settings.UPLOAD_DIR
        self._ensure_upload_directories()

    def _ensure_upload_directories(self):
        """Create upload directories if they don't exist (for temporary processing)"""
        categories = ["avatar", "persona_image", "chat_attachment", "knowledge_base"]
        for category in categories:
            path = Path(self.upload_dir) / category
            path.mkdir(parents=True, exist_ok=True)

    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension"""
        return os.path.splitext(filename)[1].lower().lstrip('.')

    def _validate_file(self, file: UploadFile, category: str) -> Dict[str, Any]:
        """
        Validate file type and size
        Returns dict with 'valid' boolean and 'error' message if invalid
        """
        # Check file size
        if hasattr(file, 'size') and file.size and file.size > settings.MAX_FILE_SIZE:
            return {
                "valid": False,
                "error": f"File too large. Maximum size: {settings.MAX_FILE_SIZE // 1024 // 1024}MB"
            }

        # Check file extension
        extension = self._get_file_extension(file.filename)
        if extension not in settings.ALLOWED_FILE_EXTENSIONS:
            return {
                "valid": False,
                "error": f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_FILE_EXTENSIONS)}"
            }

        return {"valid": True}

    def _optimize_image_bytes(self, content: bytes, extension: str, max_size: int = 800) -> bytes:
        """
        Optimize image in memory (resize and compress)

        Args:
            content: Image bytes
            extension: File extension
            max_size: Maximum width/height in pixels

        Returns:
            Optimized image bytes
        """
        try:
            img = Image.open(io.BytesIO(content))

            # Convert RGBA to RGB if necessary
            if img.mode == 'RGBA':
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])
                img = rgb_img

            # Resize if too large
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Save to bytes with optimization
            output = io.BytesIO()
            format_map = {'jpg': 'JPEG', 'jpeg': 'JPEG', 'png': 'PNG', 'gif': 'GIF'}
            save_format = format_map.get(extension.lower(), 'JPEG')

            if save_format == 'JPEG':
                img.save(output, format=save_format, optimize=True, quality=85)
            else:
                img.save(output, format=save_format, optimize=True)

            return output.getvalue()

        except Exception as e:
            logger.warning(f"Could not optimize image: {str(e)}")
            # Return original content if optimization fails
            return content

    async def upload_file(
        self,
        user_id: str,
        file: UploadFile,
        category: str = "chat_attachment"
    ) -> UploadedFile:
        """
        Upload a file to FileRunner

        Args:
            user_id: User uploading the file
            file: The file to upload
            category: File category (avatar, persona_image, chat_attachment, knowledge_base)

        Returns:
            UploadedFile model instance
        """
        try:
            # Validate file
            validation = self._validate_file(file, category)
            if not validation["valid"]:
                raise ValueError(validation["error"])

            # Get user
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            # Read file content
            content = await file.read()
            file_size = len(content)
            extension = self._get_file_extension(file.filename)

            # Optimize image if it's an avatar or persona image
            if category in ["avatar", "persona_image"] and extension in ["jpg", "jpeg", "png"]:
                content = self._optimize_image_bytes(content, extension)
                file_size = len(content)

            # Upload to FileRunner
            filerunner_response = await filerunner_service.upload_file(
                file_content=content,
                filename=file.filename,
                content_type=file.content_type or f"application/{extension}",
                category=category
            )

            # Extract FileRunner file ID and construct URL
            filerunner_file_id = filerunner_response.get('file_id')
            filerunner_url = filerunner_service.get_file_url(filerunner_file_id)

            # Create database record with FileRunner URL as file_path
            uploaded_file = UploadedFile(
                user_id=user_id,
                original_name=file.filename,
                file_path=filerunner_url,  # Store full FileRunner URL
                file_size=file_size,
                mime_type=file.content_type or f"application/{extension}",
                category=category
            )

            self.db.add(uploaded_file)

            # Update user storage usage
            usage = user.usage_tracking
            if usage:
                usage.storage_used_bytes += file_size

            self.db.commit()
            self.db.refresh(uploaded_file)

            logger.info(f"File uploaded to FileRunner: {filerunner_file_id} for user {user_id}")
            return uploaded_file

        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise

    def get_file_by_id(self, file_id: str, user_id: Optional[str] = None) -> Optional[UploadedFile]:
        """
        Get file by ID

        Args:
            file_id: File ID
            user_id: Optional user ID for access control

        Returns:
            UploadedFile if found and accessible
        """
        query = self.db.query(UploadedFile).filter(UploadedFile.id == file_id)

        if user_id:
            query = query.filter(UploadedFile.user_id == user_id)

        return query.first()

    def get_user_files(
        self,
        user_id: str,
        category: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[List[UploadedFile], int]:
        """Get files uploaded by a user"""
        query = self.db.query(UploadedFile).filter(UploadedFile.user_id == user_id)

        if category:
            query = query.filter(UploadedFile.category == category)

        total = query.count()
        files = query.order_by(UploadedFile.created_at.desc()).offset(skip).limit(limit).all()

        return files, total

    def delete_file(self, file_id: str, user_id: str) -> bool:
        """
        Delete a file

        Args:
            file_id: File ID
            user_id: User ID (for access control)

        Returns:
            True if deleted successfully
        """
        file = self.db.query(UploadedFile).filter(
            UploadedFile.id == file_id,
            UploadedFile.user_id == user_id
        ).first()

        if not file:
            raise ValueError("File not found or access denied")

        # Note: FileRunner file deletion requires JWT auth
        # For now, we just delete the database record
        # The FileRunner file will remain (could implement cleanup later)
        logger.warning(f"FileRunner file not deleted (requires JWT): {file.file_path}")

        # Update storage usage
        user = self.db.query(User).filter(User.id == user_id).first()
        if user and user.usage_tracking:
            user.usage_tracking.storage_used_bytes -= file.file_size
            if user.usage_tracking.storage_used_bytes < 0:
                user.usage_tracking.storage_used_bytes = 0

        # Delete database record
        self.db.delete(file)
        self.db.commit()

        return True

    def get_file_url(self, file: UploadedFile, base_url: str = None) -> str:
        """
        Get URL to access the file

        Args:
            file: UploadedFile instance
            base_url: Base URL (ignored, file_path already contains FileRunner URL)

        Returns:
            Full URL to access the file (FileRunner URL)
        """
        # file_path now contains the full FileRunner URL
        return file.file_path
