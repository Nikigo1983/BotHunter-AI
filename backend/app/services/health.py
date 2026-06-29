from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.schemas.health import HealthResponse


class HealthService:
    def __init__(
        self,
        settings: Settings,
        db: AsyncSession | None = None,
        redis: Redis | None = None,
    ) -> None:
        self._settings = settings
        self._db = db
        self._redis = redis

    async def check(self) -> HealthResponse:
        services: dict[str, str] = {
            "api": "ok",
            "database": await self._check_database(),
            "redis": await self._check_redis(),
        }

        overall_status = "ok" if all(v == "ok" for v in services.values()) else "degraded"

        return HealthResponse(
            status=overall_status,
            app_name=self._settings.app_name,
            environment=self._settings.app_env,
            timestamp=datetime.now(UTC),
            services=services,
        )

    async def _check_database(self) -> str:
        if self._db is None:
            return "unknown"
        try:
            await self._db.execute(text("SELECT 1"))
            return "ok"
        except Exception:
            return "error"

    async def _check_redis(self) -> str:
        if self._redis is None:
            return "unknown"
        try:
            await self._redis.ping()
            return "ok"
        except Exception:
            return "error"
