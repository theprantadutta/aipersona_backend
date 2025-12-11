"""
Application Configuration
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    DATABASE_CLIENT: str = "postgres"
    DATABASE_HOST: str
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str
    DATABASE_USERNAME: str
    DATABASE_PASSWORD: str
    DATABASE_SSL: bool = False

    @property
    def DATABASE_URL(self) -> str:
        """Construct database URL from components"""
        return (
            f"postgresql://{self.DATABASE_USERNAME}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "AI Persona API"
    DEBUG: bool = True
    ALLOWED_ORIGINS: str = "*"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        """Parse CORS origins from string"""
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    # Firebase (Auth + FCM only, NO Storage)
    FIREBASE_PROJECT_ID: str
    FIREBASE_AUTH_ENABLED: bool = True
    GOOGLE_WEB_CLIENT_ID: str
    FCM_CREDENTIALS_PATH: str = "firebase-admin-sdk.json"

    # Google Gemini AI (legacy - kept for reference)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Freeway AI Gateway
    FREEWAY_API_URL: str = "https://freeway.pranta.dev"
    FREEWAY_API_KEY: str = ""
    FREEWAY_MODEL: str = "free"  # "free" or "paid"

    # Google Play
    GOOGLE_PLAY_SERVICE_ACCOUNT_PATH: str = "google-play-service-account.json"
    GOOGLE_PLAY_PACKAGE_NAME: str = "com.aipersona.app"

    # File Storage (Backend, not Firebase)
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10485760  # 10MB
    ALLOWED_EXTENSIONS: str = "jpg,jpeg,png,gif,pdf,txt,mp3,wav,m4a"

    @property
    def ALLOWED_FILE_EXTENSIONS(self) -> List[str]:
        """Parse allowed file extensions"""
        return [ext.strip().lower() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    # FileRunner Configuration (External File Storage)
    FILERUNNER_BASE_URL: str = "https://pranta.vps.webdock.cloud/filerunner"
    FILERUNNER_API_KEY: str = ""

    # Email Configuration
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str
    SMTP_PASSWORD: str
    SMTP_FROM_EMAIL: str
    SMTP_FROM_NAME: str = "AI Persona"

    # Free Tier Limits
    FREE_TIER_MESSAGE_LIMIT: int = 25
    FREE_TIER_PERSONA_LIMIT: int = 3
    FREE_TIER_HISTORY_DAYS: int = 3
    FREE_TIER_STORAGE_MB: int = 50

    # Subscription Settings
    GRACE_PERIOD_DAYS: int = 3

    # Admin Panel Configuration
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    ADMIN_JWT_EXPIRE_MINUTES: int = 60

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
