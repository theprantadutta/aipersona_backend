"""
AI Persona Backend API - Main Application
"""
import logging
import os
import sys
import traceback
import uuid
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.api.v1 import api_router
from app.database import init_db

# Configure logging
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-powered persona chat backend with subscriptions and marketplace",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    redirect_slashes=False
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler that:
    - In DEBUG mode: returns detailed error info for development
    - In PRODUCTION mode: returns generic error message, logs details server-side
    """
    # Generate a unique error ID for tracking
    error_id = str(uuid.uuid4())[:8]

    # Always log the full error on the server
    logger.error(
        f"[ERROR_ID: {error_id}] Unhandled exception on {request.method} {request.url.path}",
        exc_info=True
    )

    if settings.DEBUG:
        # Development: return detailed error for debugging
        return JSONResponse(
            status_code=500,
            content={
                "detail": str(exc),
                "error_id": error_id,
                "type": type(exc).__name__,
                "path": str(request.url.path),
                "traceback": traceback.format_exc()
            }
        )
    else:
        # Production: return generic error, hide internal details
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An internal server error occurred. Please try again later.",
                "error_id": error_id
            }
        )


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploads directory for serving files
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.on_event("startup")
async def startup_event():
    """Initialize database and scheduler on startup"""
    print("=" * 70)
    print("[STARTUP] Starting AI Persona API...")
    print("=" * 70)

    # Start background scheduler
    from app.scheduler import start_scheduler
    start_scheduler()

    # Check for required configuration files
    print("[CHECK] Checking required configuration files...")

    required_files = {
        ".env": ".env file (contains database and API configuration)",
        settings.FCM_CREDENTIALS_PATH: "Firebase Admin SDK credentials (required for authentication)"
    }

    missing_files = []
    for file_path, description in required_files.items():
        if not os.path.exists(file_path):
            missing_files.append(f"  [ERROR] {file_path} - {description}")
            print(f"[ERROR] Missing: {file_path}")
        else:
            print(f"[OK] Found: {file_path}")

    if missing_files:
        error_msg = "\n\n" + "="*70 + "\n"
        error_msg += "[ERROR] CONFIGURATION ERROR: Required files are missing!\n"
        error_msg += "="*70 + "\n\n"
        error_msg += "Missing files:\n"
        error_msg += "\n".join(missing_files)
        error_msg += "\n\n"
        error_msg += "Please ensure all required files are present before starting the server.\n"
        error_msg += "See .env.example for environment variable template.\n"
        error_msg += "="*70 + "\n"

        print(error_msg, file=sys.stderr)
        sys.exit(1)

    # Ensure upload directories exist
    print("[MKDIR] Creating upload directories...")
    upload_dirs = [
        settings.UPLOAD_DIR,
        f"{settings.UPLOAD_DIR}/avatars",
        f"{settings.UPLOAD_DIR}/personas",
        f"{settings.UPLOAD_DIR}/chat_attachments",
        f"{settings.UPLOAD_DIR}/knowledge_base"
    ]
    for dir_path in upload_dirs:
        os.makedirs(dir_path, exist_ok=True)
    print("[OK] Upload directories ready")

    print(f"[DATABASE] {settings.DATABASE_HOST}:{settings.DATABASE_PORT}/{settings.DATABASE_NAME}")
    print(f"[DEBUG] Debug mode: {settings.DEBUG}")
    print(f"[AI] Gemini Model: {settings.GEMINI_MODEL}")
    print(f"[PACKAGE] {settings.GOOGLE_PLAY_PACKAGE_NAME}")

    # Initialize database tables
    try:
        init_db()
        print("[OK] Database initialized successfully")
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        sys.exit(1)

    # Ensure admin user exists
    try:
        from app.database import SessionLocal
        from app.utils.admin_setup import ensure_admin_user

        db = SessionLocal()
        ensure_admin_user(db)
        db.close()
        print("[OK] Admin user verified")
    except Exception as e:
        print(f"[WARNING] Admin user setup warning: {e}")
        # Don't exit - this is not critical for app startup

    print("=" * 70)
    print(f"[API] Running at: http://{settings.HOST}:{settings.PORT}")
    print(f"[DOCS] API Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"[DOCS] ReDoc: http://{settings.HOST}:{settings.PORT}/redoc")
    print("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("[SHUTDOWN] Shutting down AI Persona API...")

    # Stop background scheduler
    from app.scheduler import stop_scheduler
    stop_scheduler()


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ai-persona-api",
        "version": "1.0.0"
    }


# Include API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Welcome to AI Persona API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "features": [
            "Firebase Auth + Google Sign-In",
            "AI-powered persona chat",
            "Google Play subscriptions",
            "Persona marketplace",
            "Usage tracking & limits"
        ]
    }


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="AI Persona Backend API")
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload on file changes"
    )
    args = parser.parse_args()

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=not args.no_reload
    )
