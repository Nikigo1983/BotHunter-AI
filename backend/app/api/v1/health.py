from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis, get_settings_dep
from app.config import Settings
from app.database import get_db_session
from app.schemas.health import HealthResponse
from app.services.health import HealthService

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns application and dependency health status.",
)
async def health_check(
    settings: Settings = Depends(get_settings_dep),
    db: AsyncSession = Depends(get_db_session),
    redis: Redis = Depends(get_redis),
) -> HealthResponse:
    service = HealthService(settings=settings, db=db, redis=redis)
    return await service.check()
