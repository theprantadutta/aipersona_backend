"""File service for handling file uploads"""
from sqlalchemy.orm import Session
from app.models.file import UploadedFile
from app.models.user import User, UsageTracking
from app.config import settings
from typing import Optional, List, Dict, Any
from fastapi import UploadFile
from PIL import Image
import os
import uuid
import aiofiles
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FileService:
    """Service for file upload and management"""

    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = settings.UPLOAD_DIR
        self._ensure_upload_directories()

    def _ensure_upload_directories(self):
        """Create upload directories if they don't exist"""
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

    async def upload_file(
        self,
        user_id: str,
        file: UploadFile,
        category: str = "chat_attachment"
    ) -> UploadedFile:
        """
        Upload a file

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

            # Generate unique filename
            extension = self._get_file_extension(file.filename)
            unique_filename = f"{uuid.uuid4()}.{extension}"

            # Determine save path
            category_dir = Path(self.upload_dir) / category
            file_path = category_dir / unique_filename

            # Save file
            async with aiofiles.open(file_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)

            # Get file size
            file_size = os.path.getsize(file_path)

            # Optimize image if it's an image
            if category in ["avatar", "persona_image"] and extension in ["jpg", "jpeg", "png"]:
                await self._optimize_image(file_path)
                file_size = os.path.getsize(file_path)  # Update size after optimization

            # Create database record
            uploaded_file = UploadedFile(
                user_id=user_id,
                file_name=file.filename,
                file_path=str(file_path),
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

            return uploaded_file

        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise

    async def _optimize_image(self, file_path: Path, max_size: int = 800):
        """
        Optimize image file (resize and compress)

        Args:
            file_path: Path to the image file
            max_size: Maximum width/height in pixels
        """
        try:
            with Image.open(file_path) as img:
                # Convert RGBA to RGB if necessary
                if img.mode == 'RGBA':
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[3])
                    img = rgb_img

                # Resize if too large
                if img.width > max_size or img.height > max_size:
                    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                # Save with optimization
                img.save(file_path, optimize=True, quality=85)

        except Exception as e:
            logger.warning(f"Could not optimize image {file_path}: {str(e)}")
            # Don't fail upload if optimization fails

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

        # Delete physical file
        try:
            if os.path.exists(file.file_path):
                os.remove(file.file_path)
        except Exception as e:
            logger.warning(f"Could not delete physical file {file.file_path}: {str(e)}")

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

    def get_file_url(self, file: UploadedFile, base_url: str) -> str:
        """
        Get URL to access the file

        Args:
            file: UploadedFile instance
            base_url: Base URL of the API

        Returns:
            Full URL to access the file
        """
        return f"{base_url}/api/v1/files/{file.id}"
