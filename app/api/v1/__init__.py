"""API v1 routes"""
from fastapi import APIRouter
from app.api.v1 import auth, auth_firebase, ai, personas

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(auth_firebase.router, prefix="/auth", tags=["authentication"])
api_router.include_router(ai.router)
api_router.include_router(personas.router)

# TODO: Add more routers as we build them
# from app.api.v1 import personas, chat, ai, subscription, usage, marketplace, files, notifications, admin
# api_router.include_router(personas.router, prefix="/personas", tags=["personas"])
# api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
# api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
# api_router.include_router(subscription.router, prefix="/subscription", tags=["subscription"])
# api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
# api_router.include_router(marketplace.router, prefix="/marketplace", tags=["marketplace"])
# api_router.include_router(files.router, prefix="/files", tags=["files"])
# api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
# api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
