from fastapi import APIRouter

from app.api.v1.admin import router as admin_api_router
from app.api.v1.analytics import router as analytics_api_router
from app.api.v1.channels import router as channels_api_router
from app.api.v1.investigations import router as investigations_api_router
from app.api.v1.health import router as health_router

api_v1_router = APIRouter()
api_v1_router.include_router(investigations_api_router)
api_v1_router.include_router(health_router)
api_v1_router.include_router(admin_api_router)
api_v1_router.include_router(analytics_api_router)
api_v1_router.include_router(channels_api_router)
