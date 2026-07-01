import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.deps import attach_dashboard_auth, require_dashboard_auth, validate_post_csrf
from app.admin.auth.permissions import PERMISSION_MANAGE_USERS, PERMISSION_VIEW_SECRETS, has_permission
from app.admin.router import ADMIN_TEMPLATES
from app.config import get_settings
from app.database.session import get_db_session
from app.services.dashboard_auth import DashboardAuthContext
from app.services.organization import OrganizationService
from app.tenant.middleware import resolve_tenant_context

organization_router = APIRouter(
    prefix="/admin",
    tags=["admin-organization"],
    dependencies=[Depends(attach_dashboard_auth)],
)


async def get_organization_service(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationService:
    tenant = await resolve_tenant_context(request, auth, session)
    return OrganizationService(session, tenant)


def _ctx(request: Request, auth: DashboardAuthContext, **extra) -> dict:
    tenant = getattr(request.state, "tenant", None)
    return {
        "request": request,
        "current_user": auth.user,
        "csrf_token": auth.csrf_token,
        "tenant": tenant,
        "can_manage_users": has_permission(auth.user.role, PERMISSION_MANAGE_USERS),
        "can_manage_secrets": has_permission(auth.user.role, PERMISSION_VIEW_SECRETS),
        **extra,
    }


@organization_router.get("/organization/members", response_class=HTMLResponse)
async def organization_members(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: OrganizationService = Depends(get_organization_service),
) -> HTMLResponse:
    members = await service.list_members()
    workspaces = await service.list_workspaces_for_org()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/organization/members.html",
        _ctx(request, auth, members=members, workspaces=workspaces),
    )


@organization_router.post("/organization/members/invite", dependencies=[Depends(validate_post_csrf)])
async def organization_members_invite(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: OrganizationService = Depends(get_organization_service),
    email: str = Form(...),
    role: str = Form(...),
    workspace_id: uuid.UUID = Form(...),
) -> HTMLResponse:
    if not has_permission(auth.user.role, PERMISSION_MANAGE_USERS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    base_url = str(request.base_url).rstrip("/")
    error = None
    invite = None
    try:
        invite = await service.create_invite(
            email=email,
            role=role,
            workspace_id=workspace_id,
            invited_by=auth.user.email,
            base_url=base_url,
        )
    except ValueError as exc:
        error = str(exc)
    members = await service.list_members()
    workspaces = await service.list_workspaces_for_org()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/organization/members.html",
        _ctx(request, auth, members=members, workspaces=workspaces, invite=invite, error=error),
    )


@organization_router.get("/organization/secrets", response_class=HTMLResponse)
async def organization_secrets(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: OrganizationService = Depends(get_organization_service),
) -> HTMLResponse:
    secrets = await service.list_secrets()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/organization/secrets.html",
        _ctx(request, auth, secrets=secrets),
    )


@organization_router.post("/organization/secrets", dependencies=[Depends(validate_post_csrf)])
async def organization_secrets_save(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: OrganizationService = Depends(get_organization_service),
    secret_type: str = Form(...),
    value: str = Form(...),
) -> RedirectResponse:
    if not has_permission(auth.user.role, PERMISSION_VIEW_SECRETS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    await service.upsert_secret(
        secret_type=secret_type,
        value=value,
        updated_by=auth.user.email,
    )
    return RedirectResponse("/admin/organization/secrets?saved=1", status_code=303)


@organization_router.get("/organization/branding", response_class=HTMLResponse)
async def organization_branding(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: OrganizationService = Depends(get_organization_service),
) -> HTMLResponse:
    organization = await service.get_organization()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/organization/branding.html",
        _ctx(request, auth, organization=organization),
    )


@organization_router.post("/organization/branding", dependencies=[Depends(validate_post_csrf)])
async def organization_branding_save(
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: OrganizationService = Depends(get_organization_service),
    name: str = Form(...),
    display_name: str = Form(default=""),
    logo_url: str = Form(default=""),
    brand_color: str = Form(default=""),
    favicon_url: str = Form(default=""),
) -> RedirectResponse:
    if not has_permission(auth.user.role, PERMISSION_MANAGE_USERS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    await service.update_organization(
        name=name,
        display_name=display_name or None,
        logo_url=logo_url or None,
        brand_color=brand_color or None,
        favicon_url=favicon_url or None,
    )
    return RedirectResponse("/admin/organization/branding?saved=1", status_code=303)


@organization_router.get("/billing", response_class=HTMLResponse)
async def billing_dashboard(
    request: Request,
    auth: DashboardAuthContext = Depends(require_dashboard_auth),
    service: OrganizationService = Depends(get_organization_service),
) -> HTMLResponse:
    billing = await service.get_billing_dashboard()
    return ADMIN_TEMPLATES.TemplateResponse(
        request,
        "dashboard/organization/billing.html",
        _ctx(request, auth, billing=billing),
    )
