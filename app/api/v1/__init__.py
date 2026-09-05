from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.doctors import router as doctors_router
from app.api.v1.admin import router as admin_router
from app.api.v1.health import router as health_router
from app.api.v1.chat import router as chat_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(analysis_router)
api_v1_router.include_router(doctors_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(health_router)
api_v1_router.include_router(chat_router)

__all__ = ["api_v1_router"]
