"""
Quick start script for running the AI Persona backend
"""
import uvicorn
from app.config import settings

if __name__ == "__main__":
    print("=" * 70)
    print("🚀 Starting AI Persona Backend API")
    print("=" * 70)
    print(f"📍 Host: {settings.HOST}:{settings.PORT}")
    print(f"📊 Database: {settings.DATABASE_HOST}/{settings.DATABASE_NAME}")
    print(f"📚 API Docs: http://{settings.HOST}:{settings.PORT}/docs")
    print(f"🔧 Debug: {settings.DEBUG}")
    print(f"🤖 Gemini Model: {settings.GEMINI_MODEL}")
    print("=" * 70)

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
