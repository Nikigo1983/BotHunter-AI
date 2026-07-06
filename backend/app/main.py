from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis

from app.admin.auth_router import auth_router
from app.admin.pwa_router import mount_pwa_static, pwa_router
from app.admin.invite_router import invite_router
from app.admin.organization_router import organization_router
from app.admin.saas_router import saas_router
from app.admin.tenant_router import tenant_router
from app.admin.policy_router import policy_router
from app.admin.router import router as admin_web_router
from app.admin.system_router import system_router
from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.config.runtime_overrides import refresh_runtime_snapshot
from app.database import engine
from app.database.session import async_session_factory
from app.services.dashboard_auth import DashboardAuthService
from app.services.tenant_bootstrap import TenantBootstrapService
from app.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    settings = get_settings()
    logger.info(
        "Starting %s in %s mode on %s:%s",
        settings.app_name,
        settings.app_env,
        settings.app_host,
        settings.app_port,
    )
    logger.info(
        "PostgreSQL target: %s:%s/%s (ssl=%s, pooler=%s, pool_size=%s)",
        settings.postgres_host,
        settings.postgres_port,
        settings.postgres_db,
        settings.requires_postgres_ssl,
        settings.database_use_pooler,
        settings.database_pool_size,
    )
    app.state.redis = None
    try:
        app.state.redis = Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await app.state.redis.ping()
    except Exception:
        logger.warning("Redis unavailable; dashboard workspace cache disabled")
        app.state.redis = None
    try:
        async with async_session_factory() as session:
            auth_service = DashboardAuthService(session)
            await auth_service.ensure_default_owner()
            await TenantBootstrapService(session).ensure_default_tenant()
            await session.commit()
            await refresh_runtime_snapshot(session)
            await session.commit()
    except Exception:
        logger.exception(
            "Application startup failed while initializing database at %s:%s/%s",
            settings.postgres_host,
            settings.postgres_port,
            settings.postgres_db,
        )
        raise
    yield
    if app.state.redis is not None:
        await app.state.redis.aclose()
    await engine.dispose()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="BotHunter AI — Telegram bot detection and analysis platform.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        debug=settings.app_debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(pwa_router)
    mount_pwa_static(app)

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    app.include_router(auth_router)
    app.include_router(invite_router)
    app.include_router(admin_web_router)
    app.include_router(organization_router)
    app.include_router(saas_router)
    app.include_router(tenant_router)
    app.include_router(policy_router)
    app.include_router(system_router)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/admin/login", status_code=302)

    return app


app = create_app()
