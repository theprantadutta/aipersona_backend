"""FileRunner service for handling file uploads to external storage"""
import httpx
import logging
from typing import Optional, Dict, Any, BinaryIO
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class FileRunnerService:
    """Service for uploading files to FileRunner external storage"""

    def __init__(self):
        self.base_url = settings.FILERUNNER_BASE_URL
        self.api_key = settings.FILERUNNER_API_KEY
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=60.0,
                headers={
                    "X-API-Key": self.api_key,
                }
            )
        return self._client

    async def close(self):
        """Close the HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _get_folder_path(self, category: str) -> str:
        """Map category to FileRunner folder path"""
        folder_mapping = {
            "avatar": "avatars",
            "persona_image": "persona_images",
            "chat_attachment": "chat_attachments",
            "knowledge_base": "knowledge_base",
        }
        return folder_mapping.get(category, "misc")

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        category: str = "misc"
    ) -> Dict[str, Any]:
        """
        Upload a file to FileRunner

        Args:
            file_content: Binary content of the file
            filename: Original filename
            content_type: MIME type of the file
            category: File category (avatar, persona_image, chat_attachment, knowledge_base)

        Returns:
            Dict containing:
                - file_id: UUID of the uploaded file
                - original_name: Original filename
                - size: File size in bytes
                - mime_type: MIME type
                - download_url: Relative URL to download the file
                - folder_path: The folder path where file is stored
        """
        try:
            client = await self._get_client()
            folder_path = self._get_folder_path(category)

            # Prepare multipart form data
            files = {
                "file": (filename, file_content, content_type)
            }
            data = {
                "folder_path": folder_path
            }

            response = await client.post(
                "/api/upload",
                files=files,
                data=data
            )

            if response.status_code != 200:
                logger.error(f"FileRunner upload failed: {response.status_code} - {response.text}")
                raise Exception(f"FileRunner upload failed: {response.text}")

            result = response.json()
            logger.info(f"File uploaded to FileRunner: {result.get('file_id')}")
            return result

        except httpx.RequestError as e:
            logger.error(f"FileRunner request error: {str(e)}")
            raise Exception(f"Failed to connect to FileRunner: {str(e)}")
        except Exception as e:
            logger.error(f"FileRunner upload error: {str(e)}")
            raise

    async def upload_file_from_path(
        self,
        file_path: str,
        category: str = "misc"
    ) -> Dict[str, Any]:
        """
        Upload a file from filesystem path to FileRunner

        Args:
            file_path: Path to the file on disk
            category: File category

        Returns:
            FileRunner upload response
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Determine content type
        extension = path.suffix.lower().lstrip('.')
        content_type_mapping = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'pdf': 'application/pdf',
            'txt': 'text/plain',
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'm4a': 'audio/m4a',
        }
        content_type = content_type_mapping.get(extension, 'application/octet-stream')

        with open(file_path, 'rb') as f:
            content = f.read()

        return await self.upload_file(
            file_content=content,
            filename=path.name,
            content_type=content_type,
            category=category
        )

    def get_file_url(self, file_id: str) -> str:
        """
        Get the full URL for a file

        Args:
            file_id: FileRunner file ID

        Returns:
            Full URL to access the file
        """
        return f"{self.base_url}/api/files/{file_id}"

    def get_download_url(self, download_url: str) -> str:
        """
        Get the full download URL from relative path

        Args:
            download_url: Relative download URL from upload response

        Returns:
            Full URL to download the file
        """
        if download_url.startswith('http'):
            return download_url
        return f"{self.base_url}{download_url}"


# Global service instance
filerunner_service = FileRunnerService()
