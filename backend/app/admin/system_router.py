from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.deps import attach_dashboard_auth, require_dashboard_auth, validate_post_csrf
from app.admin.auth.permissions import (
    PERMISSION_CHANGE_AI_SETTINGS,
    PERMISSION_CHANGE_SYSTEM_SETTINGS,
    PERMISSION_MANAGE_BACKUP,
    PERMISSION_VIEW_SECRETS,
    has_permission,
)
from app.admin.router import ADMIN_TEMPLATES
from app.api.deps import get_redis
from app.database.session import get_db_session
from app.services.backup_service import BackupService
from app.services.dashboard_auth import DashboardAuthContext
from app.services.notification_service import NotificationService
from app.services.runtime_settings import RuntimeSettingsService
from app.services.secrets_service import SecretsService
from app.services.system_monitor import SystemMonitorService

system_router = APIRouter(
    prefix="/admin",
    tags=["admin-system"],
    dependencies=[Depends(attach_dashboard_auth)],
)


async def get_monitor(session: AsyncSession = Depends(get_db_session)) -> SystemMonitorService:
    return SystemMonitorService(session)


def _require(auth: DashboardAuthContext, permission: str) -> None:
    if not has_permission(auth.user.role, permission):
        raise HTTPException(status_code=403, detail="Insufficient permissions")


def _ctx(request: Request, auth: DashboardAuthContext, **extra) -> dict:
    notifications = getattr(request.state, "notifications", [])
    return {
        "request": request,
        "current_user": auth.user,
        "csrf_token": auth.csrf_token,
        "notifications": notifications,
        "has_critical_alerts": any(item.level == "critical" for item in notifications),
        **extra,
    }


@system_router.get("/system", response_class=HTMLResponse)
async def system_dashboard(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    monitor: SystemMonitorService = Depends(get_monitor),
    redis=Depends(get_redis),
) -> HTMLResponse:
    await monitor.sync_health_alerts(redis)
    services = await monitor.get_service_statuses(redis)
    ready = await monitor.get_production_ready_report(redis)
    docker = await monitor.get_docker_health()
    usage = await monitor.get_usage_limits()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/system/index.html",
        _ctx(
            request,
            auth,
            services=services,
            ready=ready,
            docker=docker,
            usage=usage,
        ),
    )


@system_router.get("/system/errors", response_class=HTMLResponse)
async def system_errors(
    request: Request,
    source: str | None = None,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    from app.repositories.deps import get_system_error_repository

    repo = get_system_error_repository(session)
    errors = await repo.list_recent(limit=200, source=source)
    counts = await repo.count_by_source()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/system/errors.html",
        _ctx(request, auth, errors=errors, counts=counts, source_filter=source),
    )


@system_router.get("/system/queue", response_class=HTMLResponse)
async def system_queue(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    monitor: SystemMonitorService = Depends(get_monitor),
) -> HTMLResponse:
    stats = await monitor.get_queue_stats()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/system/queue.html",
        _ctx(request, auth, stats=stats),
    )


@system_router.get("/system/usage", response_class=HTMLResponse)
async def system_usage(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    monitor: SystemMonitorService = Depends(get_monitor),
) -> HTMLResponse:
    usage = await monitor.get_usage_limits()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/system/usage.html",
        _ctx(request, auth, usage=usage),
    )


@system_router.get("/system/backup", response_class=HTMLResponse)
async def system_backup_page(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
) -> HTMLResponse:
    _require(auth, PERMISSION_MANAGE_BACKUP)
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/system/backup.html",
        _ctx(request, auth),
    )


@system_router.get("/system/backup/export")
async def system_backup_export(
    format: str = Query("json"),
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    _require(auth, PERMISSION_MANAGE_BACKUP)
    service = BackupService(session)
    if format == "sql":
        result = await service.export_sql()
    elif format == "csv":
        result = await service.export_csv_bundle()
    else:
        result = await service.export_json()
    await service.mark_backup_configured(updated_by=auth.user.email)
    return Response(
        content=result.content,
        media_type=result.content_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )


@system_router.post("/system/backup/restore")
async def system_backup_restore(
    auth: DashboardAuthContext = Depends(validate_post_csrf),
    session: AsyncSession = Depends(get_db_session),
    file: UploadFile = File(...),
) -> Response:
    _require(auth, PERMISSION_MANAGE_BACKUP)
    raw = await file.read()
    imported = await BackupService(session).import_json(raw)
    return Response(content=f"Imported {imported} rows", media_type="text/plain")


@system_router.get("/system/secrets", response_class=HTMLResponse)
async def system_secrets(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    _require(auth, PERMISSION_VIEW_SECRETS)
    secrets = await SecretsService(session).list_secrets()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/system/secrets.html",
        _ctx(request, auth, secrets=secrets),
    )


@system_router.get("/system/logs", response_class=HTMLResponse)
async def system_logs(
    request: Request,
    log: str = Query("api"),
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    monitor: SystemMonitorService = Depends(get_monitor),
) -> HTMLResponse:
    lines = await monitor.read_log_tail(log)
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/system/logs.html",
        _ctx(request, auth, log_name=log, log_lines=lines),
    )


@system_router.get("/system/notifications", response_class=HTMLResponse)
async def system_notifications(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    notifications = await NotificationService(session).list_all(limit=100)
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/system/notifications.html",
        _ctx(request, auth, notifications=notifications),
    )


@system_router.post("/system/notifications/read-all")
async def system_notifications_read_all(
    auth: DashboardAuthContext = Depends(validate_post_csrf),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await NotificationService(session).mark_all_read()
    return Response(status_code=204)


@system_router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    _require(auth, PERMISSION_CHANGE_AI_SETTINGS)
    service = RuntimeSettingsService(session)
    effective = await service.get_effective_settings()
    overrides = await service.get_db_overrides()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/settings/index.html",
        _ctx(request, auth, settings=effective, overrides=overrides, can_edit_system=has_permission(auth.user.role, PERMISSION_CHANGE_SYSTEM_SETTINGS)),
    )


@system_router.post("/settings")
async def settings_save(
    request: Request,
    auth: DashboardAuthContext = Depends(validate_post_csrf),
    session: AsyncSession = Depends(get_db_session),
    ai_provider: str = Form(...),
    openrouter_model: str = Form(""),
    openai_model: str = Form(""),
    ai_timeout: str = Form("30"),
    ai_max_retries: str = Form("2"),
    decision_approve_below: str = Form("30"),
    decision_reject_from: str = Form("70"),
    monthly_budget_usd: str = Form("100"),
) -> Response:
    _require(auth, PERMISSION_CHANGE_AI_SETTINGS)
    values = {
        "ai_provider": ai_provider.strip().lower(),
        "openrouter_model": openrouter_model.strip(),
        "openai_model": openai_model.strip(),
        "ai_timeout": ai_timeout.strip(),
        "ai_max_retries": ai_max_retries.strip(),
    }
    if has_permission(auth.user.role, PERMISSION_CHANGE_SYSTEM_SETTINGS):
        values.update(
            {
                "decision_approve_below": decision_approve_below.strip(),
                "decision_reject_from": decision_reject_from.strip(),
                "monthly_budget_usd": monthly_budget_usd.strip(),
            }
        )
    await RuntimeSettingsService(session).update_settings(values, updated_by=auth.user.email)
    return RedirectResponse(url="/admin/settings?saved=1", status_code=303)
