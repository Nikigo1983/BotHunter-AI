from pathlib import Path
import json
import uuid
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.deps import attach_dashboard_auth, validate_post_csrf
from app.database.session import get_db_session
from app.models.enums import AnalysisDecision
from app.repositories.admin_dashboard import StatusFilter
from app.schemas.channel_management import ChannelSettingsUpdateRequest
from app.services.admin_channel import AdminChannelService
from app.services.admin_ai import AdminAIService
from app.services.analytics import AnalyticsService
from app.services.admin_dashboard import AdminDashboardService, PAGE_SIZE
from app.services.admin_join_request_action import AdminJoinRequestActionService
from app.services.investigation import InvestigationService

ADMIN_TEMPLATES = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent / "templates"),
)

router = APIRouter(
    prefix="/admin",
    tags=["admin-web"],
    dependencies=[Depends(attach_dashboard_auth)],
)


async def get_admin_service(
    session: AsyncSession = Depends(get_db_session),
) -> AdminDashboardService:
    return AdminDashboardService(session)


async def get_action_service(
    session: AsyncSession = Depends(get_db_session),
) -> AdminJoinRequestActionService:
    return AdminJoinRequestActionService(session)


async def get_admin_ai_service(
    session: AsyncSession = Depends(get_db_session),
) -> AdminAIService:
    return AdminAIService(session)


async def get_analytics_service(
    session: AsyncSession = Depends(get_db_session),
) -> AnalyticsService:
    return AnalyticsService(session)


async def get_channel_service(
    session: AsyncSession = Depends(get_db_session),
) -> AdminChannelService:
    return AdminChannelService(session)


async def get_investigation_service(
    session: AsyncSession = Depends(get_db_session),
) -> InvestigationService:
    return InvestigationService(session)


def status_badge_class(status: str) -> str:
    mapping = {
        "Approved": "success",
        "Rejected": "danger",
        "ManualReview": "warning",
        "Pending": "secondary",
    }
    return mapping.get(status, "secondary")


def decision_badge_class(decision: str | None) -> str:
    if decision is None:
        return "secondary"
    return status_badge_class(decision)


def format_ai_status(status: str | None) -> str:
    mapping = {
        "SUCCESS": "Success",
        "FALLBACK": "Fallback",
        "SKIPPED": "Skipped",
        "AI_UNAVAILABLE": "Failed",
        "FAILED": "Failed",
    }
    if not status:
        return "—"
    return mapping.get(status, status)


def tojson_filter(value: object, indent: int = 2) -> str:
    return json.dumps(value, ensure_ascii=False, indent=indent, default=str)


def trust_badge_class(score: float) -> str:
    if score >= 80:
        return "success"
    if score >= 40:
        return "warning"
    return "danger"


def confidence_bar_class(confidence: float | None) -> str:
    if confidence is None:
        return "secondary"
    if confidence >= 0.75:
        return "success"
    if confidence >= 0.5:
        return "warning"
    return "danger"


def confidence_percent(confidence: float | None) -> int:
    if confidence is None:
        return 0
    return min(100, max(0, round(confidence * 100)))


def ai_risk_level(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 30:
        return "low"
    if score < 70:
        return "medium"
    return "high"


def ai_risk_level_label(score: float | None) -> str:
    mapping = {
        "low": "Низкий риск",
        "medium": "Средний риск",
        "high": "Высокий риск",
        "unknown": "—",
    }
    return mapping.get(ai_risk_level(score), "—")


def ai_risk_badge_class(score: float | None) -> str:
    mapping = {
        "low": "success",
        "medium": "warning",
        "high": "danger",
        "unknown": "secondary",
    }
    return mapping.get(ai_risk_level(score), "secondary")


def format_decision_label(decision: str | None) -> str:
    mapping = {
        "Approved": "Одобрено",
        "ManualReview": "Ручная проверка",
        "Rejected": "Отклонено",
        "APPROVED": "Одобрено",
        "MANUAL_REVIEW": "Ручная проверка",
        "REJECTED": "Отклонено",
    }
    if not decision:
        return "—"
    return mapping.get(decision, decision)


ADMIN_TEMPLATES.env.globals["status_badge_class"] = status_badge_class
ADMIN_TEMPLATES.env.globals["decision_badge_class"] = decision_badge_class
ADMIN_TEMPLATES.env.globals["format_ai_status"] = format_ai_status
ADMIN_TEMPLATES.env.globals["trust_badge_class"] = trust_badge_class
ADMIN_TEMPLATES.env.globals["confidence_bar_class"] = confidence_bar_class
ADMIN_TEMPLATES.env.globals["confidence_percent"] = confidence_percent
ADMIN_TEMPLATES.env.globals["format_decision_label"] = format_decision_label
ADMIN_TEMPLATES.env.globals["ai_risk_level"] = ai_risk_level
ADMIN_TEMPLATES.env.globals["ai_risk_level_label"] = ai_risk_level_label
ADMIN_TEMPLATES.env.globals["ai_risk_badge_class"] = ai_risk_badge_class
ADMIN_TEMPLATES.env.filters["tojson"] = tojson_filter


def _parse_join_request_id(join_request_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(join_request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Join request not found") from exc


def _redirect_to_detail(join_request_id: uuid.UUID, result) -> RedirectResponse:
    flash = "success" if result.success else "error"
    url = f"/admin/join-request/{join_request_id}?flash={flash}&msg={quote(result.message)}"
    return RedirectResponse(url=url, status_code=303)


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    status: StatusFilter = Query(default="all"),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    service: AdminDashboardService = Depends(get_admin_service),
) -> HTMLResponse:
    join_requests = await service.list_join_requests(
        status_filter=status,
        search=search,
        page=page,
        page_size=PAGE_SIZE,
    )
    statistics = await service.get_statistics()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/index.html",
        {
            "join_requests": join_requests,
            "statistics": statistics,
            "status_filter": status,
            "search": search or "",
            "page": page,
        },
    )


@router.get("/partials/join-requests", response_class=HTMLResponse)
async def admin_join_requests_partial(
    request: Request,
    status: StatusFilter = Query(default="all"),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    service: AdminDashboardService = Depends(get_admin_service),
) -> HTMLResponse:
    join_requests = await service.list_join_requests(
        status_filter=status,
        search=search,
        page=page,
        page_size=PAGE_SIZE,
    )
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/partials/join_requests_table.html",
        {
            "join_requests": join_requests,
            "status_filter": status,
            "search": search or "",
            "page": page,
        },
    )


@router.get("/join-request/{join_request_id}", response_class=HTMLResponse)
async def admin_join_request_detail(
    request: Request,
    join_request_id: str,
    flash: str | None = Query(default=None),
    msg: str | None = Query(default=None),
    service: AdminDashboardService = Depends(get_admin_service),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> HTMLResponse:
    parsed_id = _parse_join_request_id(join_request_id)
    detail = await service.get_join_request_detail(parsed_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Join request not found")

    investigation = await investigation_service.get_investigation_detail(parsed_id)
    replay = None
    if flash == "replay" and msg:
        try:
            replay = json.loads(msg)
        except json.JSONDecodeError:
            replay = None

    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/detail.html",
        {
            "detail": detail,
            "investigation": investigation,
            "replay": replay,
            "flash": flash,
            "flash_message": msg if flash != "replay" else None,
        },
    )


@router.post("/join-request/{join_request_id}/replay", dependencies=[Depends(validate_post_csrf)])
async def admin_replay_action(
    join_request_id: str,
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> RedirectResponse:
    parsed_id = _parse_join_request_id(join_request_id)
    replay = await investigation_service.replay_analysis(parsed_id)
    if replay is None:
        raise HTTPException(status_code=404, detail="Join request not found")
    payload = quote(json.dumps(
        {
            "rule_score": replay.rule_score,
            "rule_engine_decision": replay.rule_engine_decision,
            "ai_status": replay.ai_status,
            "ai_decision": replay.ai_decision,
            "ai_score": replay.ai_score,
            "final_decision": replay.final_decision,
        },
        ensure_ascii=False,
        default=str,
    ))
    url = f"/admin/join-request/{parsed_id}?flash=replay&msg={payload}"
    return RedirectResponse(url=url, status_code=303)


@router.get("/join-request/{join_request_id}/export/json")
async def admin_export_json(
    join_request_id: str,
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> Response:
    parsed_id = _parse_join_request_id(join_request_id)
    exported = await investigation_service.export_case(parsed_id, export_format="json")
    if exported is None:
        raise HTTPException(status_code=404, detail="Join request not found")
    content, media_type, filename = exported
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/join-request/{join_request_id}/export/pdf")
async def admin_export_pdf(
    join_request_id: str,
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> Response:
    parsed_id = _parse_join_request_id(join_request_id)
    exported = await investigation_service.export_case(parsed_id, export_format="pdf")
    if exported is None:
        raise HTTPException(status_code=404, detail="Join request not found")
    content, media_type, filename = exported
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/investigations", response_class=HTMLResponse)
async def admin_investigations(
    request: Request,
    channel_id: str | None = Query(default=None),
    status: StatusFilter = Query(default="all"),
    ai_decision: AnalysisDecision | None = Query(default=None),
    human_decision: AnalysisDecision | None = Query(default=None),
    trust_min: float | None = Query(default=None),
    trust_max: float | None = Query(default=None),
    rule_min: float | None = Query(default=None),
    rule_max: float | None = Query(default=None),
    ai_min: float | None = Query(default=None),
    ai_max: float | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    service: InvestigationService = Depends(get_investigation_service),
) -> HTMLResponse:
    parsed_channel_id = None
    if channel_id:
        try:
            parsed_channel_id = uuid.UUID(channel_id)
        except ValueError:
            parsed_channel_id = None
    filters = InvestigationService.build_filters(
        channel_id=parsed_channel_id,
        status=status,
        ai_decision=ai_decision,
        human_decision=human_decision,
        trust_min=trust_min,
        trust_max=trust_max,
        rule_min=rule_min,
        rule_max=rule_max,
        ai_min=ai_min,
        ai_max=ai_max,
        date_from=date_from,
        date_to=date_to,
        search=search,
    )
    investigations = await service.list_investigations(filters=filters, page=page)
    channels = await service.list_channels_for_filter()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/investigations/index.html",
        {
            "investigations": investigations,
            "channels": channels,
            "filters": {
                "channel_id": channel_id or "",
                "status": status,
                "ai_decision": ai_decision.value if ai_decision else "",
                "human_decision": human_decision.value if human_decision else "",
                "trust_min": trust_min if trust_min is not None else "",
                "trust_max": trust_max if trust_max is not None else "",
                "rule_min": rule_min if rule_min is not None else "",
                "rule_max": rule_max if rule_max is not None else "",
                "ai_min": ai_min if ai_min is not None else "",
                "ai_max": ai_max if ai_max is not None else "",
                "date_from": date_from.strftime("%Y-%m-%d") if date_from else "",
                "date_to": date_to.strftime("%Y-%m-%d") if date_to else "",
                "search": search or "",
            },
            "page": page,
        },
    )


@router.post("/join-request/{join_request_id}/approve", dependencies=[Depends(validate_post_csrf)])
async def admin_approve_action(
    join_request_id: str,
    action_service: AdminJoinRequestActionService = Depends(get_action_service),
) -> RedirectResponse:
    parsed_id = _parse_join_request_id(join_request_id)
    result = await action_service.approve(parsed_id)
    return _redirect_to_detail(parsed_id, result)


@router.post("/join-request/{join_request_id}/reject", dependencies=[Depends(validate_post_csrf)])
async def admin_reject_action(
    join_request_id: str,
    action_service: AdminJoinRequestActionService = Depends(get_action_service),
) -> RedirectResponse:
    parsed_id = _parse_join_request_id(join_request_id)
    result = await action_service.reject(parsed_id)
    return _redirect_to_detail(parsed_id, result)


@router.post("/join-request/{join_request_id}/whitelist", dependencies=[Depends(validate_post_csrf)])
async def admin_whitelist_action(
    join_request_id: str,
    action_service: AdminJoinRequestActionService = Depends(get_action_service),
) -> RedirectResponse:
    parsed_id = _parse_join_request_id(join_request_id)
    result = await action_service.whitelist(parsed_id)
    return _redirect_to_detail(parsed_id, result)


@router.post("/join-request/{join_request_id}/blacklist", dependencies=[Depends(validate_post_csrf)])
async def admin_blacklist_action(
    join_request_id: str,
    action_service: AdminJoinRequestActionService = Depends(get_action_service),
) -> RedirectResponse:
    parsed_id = _parse_join_request_id(join_request_id)
    result = await action_service.blacklist(parsed_id)
    return _redirect_to_detail(parsed_id, result)


@router.get("/ai", response_class=HTMLResponse)
async def admin_ai_usage(
    request: Request,
    service: AdminAIService = Depends(get_admin_ai_service),
) -> HTMLResponse:
    stats = await service.get_usage_statistics()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/ai.html",
        {"stats": stats},
    )


@router.get("/analytics", response_class=HTMLResponse)
async def admin_analytics(
    request: Request,
    days: int = Query(default=30, ge=7, le=90),
    service: AnalyticsService = Depends(get_analytics_service),
) -> HTMLResponse:
    overview = await service.get_overview()
    timeline = await service.get_timeline(days=days)
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/analytics.html",
        {
            "overview": overview,
            "timeline": timeline,
            "timeline_days": days if days in {7, 30, 90} else 30,
        },
    )


def _parse_channel_id(channel_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Channel not found") from exc


def _redirect_to_channel(channel_id: uuid.UUID, *, flash: str, msg: str) -> RedirectResponse:
    url = f"/admin/channels/{channel_id}?flash={flash}&msg={quote(msg)}"
    return RedirectResponse(url=url, status_code=303)


@router.get("/channels", response_class=HTMLResponse)
async def admin_channels_list(
    request: Request,
    service: AdminChannelService = Depends(get_channel_service),
) -> HTMLResponse:
    channels = await service.list_channels()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/channels/index.html",
        {"channels": channels},
    )


@router.get("/channels/{channel_id}", response_class=HTMLResponse)
async def admin_channel_detail(
    request: Request,
    channel_id: str,
    days: int = Query(default=30, ge=7, le=90),
    flash: str | None = Query(default=None),
    msg: str | None = Query(default=None),
    service: AdminChannelService = Depends(get_channel_service),
) -> HTMLResponse:
    parsed_id = _parse_channel_id(channel_id)
    detail = await service.get_channel_detail(parsed_id, timeline_days=days)
    if detail is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/channels/detail.html",
        {
            "channel": detail,
            "timeline_days": days if days in {7, 30, 90} else 30,
            "flash": flash,
            "flash_message": msg,
        },
    )


@router.post("/channels/{channel_id}/settings", dependencies=[Depends(validate_post_csrf)])
async def admin_channel_settings_update(
    channel_id: str,
    ai_enabled: bool = Form(...),
    rule_auto_approve: int = Form(...),
    rule_auto_reject: int = Form(...),
    trust_auto_approve: int = Form(...),
    trust_auto_reject: int = Form(...),
    join_request_timeout_hours: str = Form(default=""),
    service: AdminChannelService = Depends(get_channel_service),
) -> RedirectResponse:
    parsed_id = _parse_channel_id(channel_id)
    if rule_auto_reject <= rule_auto_approve:
        return _redirect_to_channel(
            parsed_id,
            flash="error",
            msg="Auto Reject порог должен быть больше Auto Approve",
        )
    timeout_raw = join_request_timeout_hours.strip()
    timeout_value = int(timeout_raw) if timeout_raw else None
    payload = ChannelSettingsUpdateRequest(
        ai_enabled=ai_enabled,
        rule_auto_approve=rule_auto_approve,
        rule_auto_reject=rule_auto_reject,
        trust_auto_approve=trust_auto_approve,
        trust_auto_reject=trust_auto_reject,
        join_request_timeout_hours=timeout_value,
    )
    detail = await service.update_channel(parsed_id, payload)
    if detail is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return _redirect_to_channel(parsed_id, flash="success", msg="Настройки канала сохранены")


@router.post("/channels/{channel_id}/disable", dependencies=[Depends(validate_post_csrf)])
async def admin_channel_disable(
    channel_id: str,
    service: AdminChannelService = Depends(get_channel_service),
) -> RedirectResponse:
    parsed_id = _parse_channel_id(channel_id)
    detail = await service.set_channel_active(parsed_id, is_active=False)
    if detail is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return _redirect_to_channel(parsed_id, flash="success", msg="Канал отключён")


@router.post("/channels/{channel_id}/enable", dependencies=[Depends(validate_post_csrf)])
async def admin_channel_enable(
    channel_id: str,
    service: AdminChannelService = Depends(get_channel_service),
) -> RedirectResponse:
    parsed_id = _parse_channel_id(channel_id)
    detail = await service.set_channel_active(parsed_id, is_active=True)
    if detail is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return _redirect_to_channel(parsed_id, flash="success", msg="Канал включён")


@router.get("/settings/ai", response_class=HTMLResponse)
async def admin_ai_settings(
    request: Request,
    service: AdminAIService = Depends(get_admin_ai_service),
) -> HTMLResponse:
    settings = service.get_ai_settings()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/ai_settings.html",
        {"settings": settings},
    )

