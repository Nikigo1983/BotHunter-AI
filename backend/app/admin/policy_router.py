import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.deps import attach_dashboard_auth, require_dashboard_auth, validate_post_csrf
from app.admin.auth.permissions import PERMISSION_CHANGE_SYSTEM_SETTINGS, has_permission
from app.admin.router import ADMIN_TEMPLATES
from app.database.session import get_db_session
from app.policy.types import PolicyThresholdConfig
from app.services.dashboard_auth import DashboardAuthContext
from app.services.policy import PolicyService
from app.services.policy_simulation import PolicySimulationService, SimulationRequest

policy_router = APIRouter(
    prefix="/admin",
    tags=["admin-policies-web"],
    dependencies=[Depends(attach_dashboard_auth)],
)


async def get_policy_service(
    session: AsyncSession = Depends(get_db_session),
) -> PolicyService:
    return PolicyService(session)


async def get_simulation_service(
    session: AsyncSession = Depends(get_db_session),
) -> PolicySimulationService:
    return PolicySimulationService(session)


def _ctx(request: Request, auth: DashboardAuthContext, **extra) -> dict:
    return {
        "request": request,
        "current_user": auth.user,
        "csrf_token": auth.csrf_token,
        "can_edit": has_permission(auth.user.role, PERMISSION_CHANGE_SYSTEM_SETTINGS),
        **extra,
    }


@policy_router.get("/policies", response_class=HTMLResponse)
async def policies_index(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: PolicyService = Depends(get_policy_service),
) -> HTMLResponse:
    rules = await service.list_rules()
    policy = await service.get_effective_policy()
    history = await service.list_history(limit=5)
    comparison = None
    if len(history) > 1:
        try:
            comparison = await service.compare_versions()
        except ValueError:
            comparison = None
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/policies/index.html",
        _ctx(
            request,
            auth,
            rules=rules,
            policy=policy,
            history=history,
            comparison=comparison,
        ),
    )


@policy_router.get("/policies/history", response_class=HTMLResponse)
async def policies_history(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: PolicyService = Depends(get_policy_service),
) -> HTMLResponse:
    history = await service.list_history(limit=50)
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/policies/history.html",
        _ctx(request, auth, history=history),
    )


@policy_router.get("/policies/compare", response_class=HTMLResponse)
async def policies_compare(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: PolicyService = Depends(get_policy_service),
) -> HTMLResponse:
    try:
        comparison = await service.compare_versions()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/policies/compare.html",
        _ctx(request, auth, comparison=comparison),
    )


@policy_router.get("/policies/thresholds", response_class=HTMLResponse)
async def policies_thresholds(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: PolicyService = Depends(get_policy_service),
) -> HTMLResponse:
    policy = await service.get_effective_policy()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/policies/thresholds.html",
        _ctx(request, auth, thresholds=policy.thresholds, version_number=policy.version_number),
    )


@policy_router.post("/policies/thresholds", dependencies=[Depends(validate_post_csrf)])
async def policies_thresholds_save(
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: PolicyService = Depends(get_policy_service),
    approve_below: int = Form(...),
    reject_from: int = Form(...),
    trust_auto_approve: int = Form(...),
    trust_auto_reject: int = Form(...),
    ai_threshold: float = Form(...),
    comment: str | None = Form(default=None),
) -> RedirectResponse:
    if not has_permission(auth.user.role, PERMISSION_CHANGE_SYSTEM_SETTINGS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    await service.update_thresholds(
        approve_below=approve_below,
        reject_from=reject_from,
        trust_auto_approve=trust_auto_approve,
        trust_auto_reject=trust_auto_reject,
        ai_threshold=ai_threshold,
        author=auth.user.email,
        comment=comment,
    )
    return RedirectResponse("/admin/policies/thresholds?saved=1", status_code=303)


@policy_router.get("/policies/{rule_key}", response_class=HTMLResponse)
async def policy_rule_detail(
    rule_key: str,
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: PolicyService = Depends(get_policy_service),
    simulation_service: PolicySimulationService = Depends(get_simulation_service),
) -> HTMLResponse:
    rule = await service.get_rule(rule_key)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    simulation = await simulation_service.simulate(
        SimulationRequest(rule_key=rule_key, score=rule.score, enabled=rule.enabled)
    )
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/policies/detail.html",
        _ctx(request, auth, rule=rule, simulation=simulation),
    )


@policy_router.post("/policies/{rule_key}", dependencies=[Depends(validate_post_csrf)])
async def policy_rule_save(
    rule_key: str,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: PolicyService = Depends(get_policy_service),
    score: int = Form(...),
    enabled: str = Form(default="on"),
    description: str = Form(...),
    admin_comment: str | None = Form(default=None),
) -> RedirectResponse:
    if not has_permission(auth.user.role, PERMISSION_CHANGE_SYSTEM_SETTINGS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        await service.update_rule(
            rule_key,
            score=score,
            enabled=enabled == "on",
            description=description,
            admin_comment=admin_comment or None,
            author=auth.user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse(f"/admin/policies/{rule_key}?saved=1", status_code=303)


@policy_router.post("/policies/{rule_key}/simulate", dependencies=[Depends(validate_post_csrf)])
async def policy_rule_simulate(
    rule_key: str,
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    simulation_service: PolicySimulationService = Depends(get_simulation_service),
    service: PolicyService = Depends(get_policy_service),
    score: int = Form(...),
    enabled: str = Form(default="on"),
) -> HTMLResponse:
    rule = await service.get_rule(rule_key)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    simulation = await simulation_service.simulate(
        SimulationRequest(
            rule_key=rule_key,
            score=score,
            enabled=enabled == "on",
        )
    )
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/policies/detail.html",
        _ctx(request, auth, rule=rule, simulation=simulation, preview=True),
    )


@policy_router.post("/policies/rollback/{version_id}", dependencies=[Depends(validate_post_csrf)])
async def policy_rollback(
    version_id: uuid.UUID,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: PolicyService = Depends(get_policy_service),
) -> RedirectResponse:
    if not has_permission(auth.user.role, PERMISSION_CHANGE_SYSTEM_SETTINGS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        await service.rollback(version_id, author=auth.user.email)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RedirectResponse("/admin/policies/history?rolled_back=1", status_code=303)
