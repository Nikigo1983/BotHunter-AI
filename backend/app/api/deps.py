from collections.abc import AsyncGenerator

from fastapi import Depends
from redis.asyncio import Redis

from app.config import Settings, get_settings


async def get_settings_dep() -> Settings:
    return get_settings()


async def get_redis(
    settings: Settings = Depends(get_settings_dep),
) -> AsyncGenerator[Redis, None]:
    redis = Redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        yield redis
    finally:
        await redis.aclose()
