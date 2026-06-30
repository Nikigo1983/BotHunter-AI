from pathlib import Path
import json
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.repositories.admin_dashboard import StatusFilter
from app.services.admin_ai import AdminAIService
from app.services.admin_dashboard import AdminDashboardService, PAGE_SIZE
from app.services.admin_join_request_action import AdminJoinRequestActionService

ADMIN_TEMPLATES = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent / "templates"),
)

router = APIRouter(prefix="/admin", tags=["admin-web"])


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
) -> HTMLResponse:
    parsed_id = _parse_join_request_id(join_request_id)
    detail = await service.get_join_request_detail(parsed_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Join request not found")

    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/detail.html",
        {
            "detail": detail,
            "flash": flash,
            "flash_message": msg,
        },
    )


@router.post("/join-request/{join_request_id}/approve")
async def admin_approve_action(
    join_request_id: str,
    action_service: AdminJoinRequestActionService = Depends(get_action_service),
) -> RedirectResponse:
    parsed_id = _parse_join_request_id(join_request_id)
    result = await action_service.approve(parsed_id)
    return _redirect_to_detail(parsed_id, result)


@router.post("/join-request/{join_request_id}/reject")
async def admin_reject_action(
    join_request_id: str,
    action_service: AdminJoinRequestActionService = Depends(get_action_service),
) -> RedirectResponse:
    parsed_id = _parse_join_request_id(join_request_id)
    result = await action_service.reject(parsed_id)
    return _redirect_to_detail(parsed_id, result)


@router.post("/join-request/{join_request_id}/whitelist")
async def admin_whitelist_action(
    join_request_id: str,
    action_service: AdminJoinRequestActionService = Depends(get_action_service),
) -> RedirectResponse:
    parsed_id = _parse_join_request_id(join_request_id)
    result = await action_service.whitelist(parsed_id)
    return _redirect_to_detail(parsed_id, result)


@router.post("/join-request/{join_request_id}/blacklist")
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

