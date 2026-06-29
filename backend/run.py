import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.utils.logging import setup_logging


def run_api() -> None:
    import uvicorn

    from app.config import get_settings

    setup_logging()
    settings = get_settings()

    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.log_level.lower(),
    )


def run_bot() -> None:
    from app.bot.main import start_bot

    setup_logging()
    asyncio.run(start_bot())


if __name__ == "__main__":
    run_api()
