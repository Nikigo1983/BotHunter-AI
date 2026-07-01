import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.deps import attach_dashboard_auth, require_dashboard_auth, validate_post_csrf
from app.admin.router import ADMIN_TEMPLATES
from app.api.deps import get_redis
from app.database.session import get_db_session
from app.models.enums import DashboardRole, OrganizationPlan
from app.repositories.deps import get_dashboard_session_repository
from app.services.dashboard_auth import DashboardAuthContext
from app.services.onboarding_wizard import OnboardingWizardService
from app.services.organization_management import OrganizationManagementService, WorkspaceManagementService
from app.services.release_validation import ReleaseValidationService
from app.tenant.middleware import resolve_tenant_context

saas_router = APIRouter(
    prefix="/admin",
    tags=["admin-saas"],
    dependencies=[Depends(attach_dashboard_auth)],
)


def _ctx(request: Request, auth: DashboardAuthContext, **extra) -> dict:
    return {
        "request": request,
        "current_user": auth.user,
        "csrf_token": auth.csrf_token,
        "tenant": getattr(request.state, "tenant", None),
        **extra,
    }


async def _tenant(request: Request, auth: DashboardAuthContext, session: AsyncSession):
    return await resolve_tenant_context(request, auth, session)


@saas_router.get("/organizations", response_class=HTMLResponse)
async def organizations_page(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    if auth.user.role != DashboardRole.OWNER.value:
        raise HTTPException(status_code=403, detail="Owner access required")
    service = OrganizationManagementService(session, auth.user)
    organizations = await service.list_organizations(include_archived=True)
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/saas/organizations.html",
        _ctx(request, auth, organizations=organizations, plans=OrganizationPlan, error=None),
    )


@saas_router.post("/organizations/create", dependencies=[Depends(validate_post_csrf)])
async def organizations_create(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
    name: str = Form(...),
    plan: str = Form(default=OrganizationPlan.FREE.value),
) -> RedirectResponse:
    service = OrganizationManagementService(session, auth.user)
    organization = await service.create_organization(name=name, plan=plan)
    session_repo = get_dashboard_session_repository(session)
    db_session = auth.session
    db_session.active_organization_id = organization.id
    from app.repositories.deps import get_workspace_repository

    default_ws = await get_workspace_repository(session).get_default_for_organization(organization.id)
    if default_ws is not None:
        db_session.active_workspace_id = default_ws.id
    await session_repo.update(db_session)
    return RedirectResponse(f"/admin/onboarding?org_id={organization.id}", status_code=303)


@saas_router.post("/organizations/{organization_id}/update", dependencies=[Depends(validate_post_csrf)])
async def organizations_update(
    organization_id: uuid.UUID,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
    name: str = Form(...),
    display_name: str = Form(default=""),
    plan: str = Form(...),
) -> RedirectResponse:
    service = OrganizationManagementService(session, auth.user)
    await service.update_organization(
        organization_id,
        name=name,
        display_name=display_name or None,
        plan=plan,
    )
    return RedirectResponse("/admin/organizations?saved=1", status_code=303)


@saas_router.post("/organizations/{organization_id}/archive", dependencies=[Depends(validate_post_csrf)])
async def organizations_archive(
    organization_id: uuid.UUID,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    service = OrganizationManagementService(session, auth.user)
    await service.archive_organization(organization_id)
    return RedirectResponse("/admin/organizations?archived=1", status_code=303)


@saas_router.post("/organizations/{organization_id}/delete", dependencies=[Depends(validate_post_csrf)])
async def organizations_delete(
    organization_id: uuid.UUID,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    service = OrganizationManagementService(session, auth.user)
    try:
        await service.delete_organization(organization_id)
    except ValueError as exc:
        return RedirectResponse(f"/admin/organizations?error={exc}", status_code=303)
    return RedirectResponse("/admin/organizations?deleted=1", status_code=303)


@saas_router.get("/workspaces", response_class=HTMLResponse)
async def workspaces_page(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    tenant = await _tenant(request, auth, session)
    service = WorkspaceManagementService(session, tenant)
    workspaces = await service.list_workspaces(include_archived=True)
    members = await service.list_org_members_for_assignment()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/saas/workspaces.html",
        _ctx(request, auth, workspaces=workspaces, members=members, roles=DashboardRole),
    )


@saas_router.post("/workspaces/create", dependencies=[Depends(validate_post_csrf)])
async def workspaces_create(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
    name: str = Form(...),
) -> RedirectResponse:
    tenant = await _tenant(request, auth, session)
    service = WorkspaceManagementService(session, tenant)
    await service.create_workspace(name=name)
    return RedirectResponse("/admin/workspaces?saved=1", status_code=303)


@saas_router.post("/workspaces/{workspace_id}/rename", dependencies=[Depends(validate_post_csrf)])
async def workspaces_rename(
    workspace_id: uuid.UUID,
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
    name: str = Form(...),
) -> RedirectResponse:
    tenant = await _tenant(request, auth, session)
    service = WorkspaceManagementService(session, tenant)
    await service.rename_workspace(workspace_id, name=name)
    return RedirectResponse("/admin/workspaces?saved=1", status_code=303)


@saas_router.post("/workspaces/{workspace_id}/archive", dependencies=[Depends(validate_post_csrf)])
async def workspaces_archive(
    workspace_id: uuid.UUID,
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> RedirectResponse:
    tenant = await _tenant(request, auth, session)
    service = WorkspaceManagementService(session, tenant)
    await service.archive_workspace(workspace_id)
    return RedirectResponse("/admin/workspaces?archived=1", status_code=303)


@saas_router.post("/workspaces/{workspace_id}/assign", dependencies=[Depends(validate_post_csrf)])
async def workspaces_assign(
    workspace_id: uuid.UUID,
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
    user_id: uuid.UUID = Form(...),
    role: str = Form(...),
) -> RedirectResponse:
    tenant = await _tenant(request, auth, session)
    service = WorkspaceManagementService(session, tenant)
    await service.assign_user(workspace_id, user_id=user_id, role=role)
    return RedirectResponse("/admin/workspaces?assigned=1", status_code=303)


@saas_router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
    step: int = Query(default=1, ge=1, le=8),
) -> HTMLResponse:
    tenant = await _tenant(request, auth, session)
    wizard = OnboardingWizardService(session, tenant)
    organization = await wizard.get_organization()
    verify = None
    if step == 7:
        verify = await wizard.verify_connections()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/saas/onboarding.html",
        _ctx(
            request,
            auth,
            step=step,
            organization=organization,
            plans=OrganizationPlan,
            verify=verify,
        ),
    )


@saas_router.post("/onboarding", dependencies=[Depends(validate_post_csrf)])
async def onboarding_submit(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
    step: int = Form(...),
    name: str = Form(default=""),
    display_name: str = Form(default=""),
    plan: str = Form(default=""),
    workspace_name: str = Form(default=""),
    telegram_token: str = Form(default=""),
    openrouter_key: str = Form(default=""),
    telegram_chat_id: str = Form(default=""),
    channel_title: str = Form(default=""),
) -> RedirectResponse:
    tenant = await _tenant(request, auth, session)
    wizard = OnboardingWizardService(session, tenant)
    next_step = step + 1
    if step == 1 and name:
        await wizard.save_organization_step(name=name, display_name=display_name or None)
    elif step == 2 and plan:
        await wizard.save_plan_step(plan=plan)
    elif step == 3 and workspace_name:
        await wizard.save_workspace_step(workspace_name=workspace_name)
    elif step == 4 and telegram_token:
        await wizard.save_telegram_step(token=telegram_token, updated_by=auth.user.email)
    elif step == 5 and openrouter_key:
        await wizard.save_openrouter_step(api_key=openrouter_key, updated_by=auth.user.email)
    elif step == 6 and telegram_chat_id:
        await wizard.save_channel_step(
            telegram_chat_id=int(telegram_chat_id),
            title=channel_title or "Onboarding Channel",
        )
    elif step == 8:
        await wizard.complete()
        return RedirectResponse("/admin/release-check", status_code=303)
    return RedirectResponse(f"/admin/onboarding?step={next_step}", status_code=303)


@saas_router.get("/release-check", response_class=HTMLResponse)
async def release_check_page(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
    redis=Depends(get_redis),
) -> HTMLResponse:
    tenant = await _tenant(request, auth, session)
    report = await ReleaseValidationService(session, tenant).run_checks(redis)
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/saas/release_check.html",
        _ctx(request, auth, report=report),
    )
