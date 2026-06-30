from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.redis import RedisStorage

from app.config import get_settings


def create_fsm_storage() -> RedisStorage:
    settings = get_settings()
    return RedisStorage.from_url(settings.redis_url)
