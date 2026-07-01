import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.deps import require_api_dashboard_auth
from app.admin.auth.permissions import PERMISSION_MANAGE_USERS, PERMISSION_VIEW_SECRETS, has_permission
from app.config import get_settings
from app.database.session import get_db_session
from app.schemas.organization import (
    BillingDashboardResponse,
    BillingMetricResponse,
    OrganizationInviteRequest,
    OrganizationInviteResponse,
    OrganizationMemberResponse,
    OrganizationMembersListResponse,
    OrganizationResponse,
    OrganizationSecretsListResponse,
    OrganizationSecretsUpdateRequest,
    OrganizationSecretItemResponse,
    OrganizationUpdateRequest,
)
from app.services.dashboard_auth import DashboardAuthContext
from app.services.organization import OrganizationService
from app.tenant.middleware import resolve_tenant_context

router = APIRouter(
    prefix="/organization",
    tags=["organization"],
    dependencies=[Depends(require_api_dashboard_auth)],
)


async def get_organization_service(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    auth: DashboardAuthContext = Depends(require_api_dashboard_auth),
) -> OrganizationService:
    tenant = await resolve_tenant_context(request, auth, session)
    return OrganizationService(session, tenant)


@router.get("", response_model=OrganizationResponse)
async def get_organization(
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    organization = await service.get_organization()
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        plan=organization.plan,
        logo_url=organization.logo_url,
        brand_color=organization.brand_color,
        display_name=organization.display_name,
        favicon_url=organization.favicon_url,
    )


@router.patch("", response_model=OrganizationResponse)
async def patch_organization(
    payload: OrganizationUpdateRequest,
    auth: DashboardAuthContext = Depends(require_api_dashboard_auth),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationResponse:
    if not has_permission(auth.user.role, PERMISSION_MANAGE_USERS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    organization = await service.update_organization(
        name=payload.name,
        display_name=payload.display_name,
        logo_url=payload.logo_url,
        brand_color=payload.brand_color,
        favicon_url=payload.favicon_url,
    )
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        plan=organization.plan,
        logo_url=organization.logo_url,
        brand_color=organization.brand_color,
        display_name=organization.display_name,
        favicon_url=organization.favicon_url,
    )


@router.get("/members", response_model=OrganizationMembersListResponse)
async def list_members(
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationMembersListResponse:
    members = await service.list_members()
    return OrganizationMembersListResponse(
        items=[
            OrganizationMemberResponse(
                user_id=item.user_id,
                full_name=item.full_name,
                email=item.email,
                role=item.role,
                workspace_names=item.workspace_names,
                is_active=item.is_active,
                last_login_at=item.last_login_at,
            )
            for item in members
        ]
    )


@router.post("/invite", response_model=OrganizationInviteResponse)
async def create_invite(
    payload: OrganizationInviteRequest,
    request: Request,
    auth: DashboardAuthContext = Depends(require_api_dashboard_auth),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationInviteResponse:
    if not has_permission(auth.user.role, PERMISSION_MANAGE_USERS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    settings = get_settings()
    base_url = str(request.base_url).rstrip("/")
    try:
        invite = await service.create_invite(
            email=payload.email,
            role=payload.role,
            workspace_id=payload.workspace_id,
            invited_by=auth.user.email,
            base_url=base_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OrganizationInviteResponse(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        workspace_id=invite.workspace_id,
        token=invite.token,
        invite_url=invite.invite_url,
        expires_at=invite.expires_at,
    )


@router.post("/secrets", response_model=OrganizationSecretItemResponse)
async def upsert_secret(
    payload: OrganizationSecretsUpdateRequest,
    auth: DashboardAuthContext = Depends(require_api_dashboard_auth),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationSecretItemResponse:
    if not has_permission(auth.user.role, PERMISSION_VIEW_SECRETS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    try:
        secret = await service.upsert_secret(
            secret_type=payload.secret_type,
            value=payload.value,
            updated_by=auth.user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OrganizationSecretItemResponse(
        secret_type=secret.secret_type,
        masked_value=secret.masked_value,
        configured=secret.configured,
    )


@router.get("/secrets", response_model=OrganizationSecretsListResponse)
async def list_secrets(
    auth: DashboardAuthContext = Depends(require_api_dashboard_auth),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationSecretsListResponse:
    if not has_permission(auth.user.role, PERMISSION_VIEW_SECRETS):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    items = await service.list_secrets()
    return OrganizationSecretsListResponse(
        items=[
            OrganizationSecretItemResponse(
                secret_type=item.secret_type,
                masked_value=item.masked_value,
                configured=item.configured,
            )
            for item in items
        ]
    )


billing_router = APIRouter(
    prefix="/billing",
    tags=["billing"],
    dependencies=[Depends(require_api_dashboard_auth)],
)


@billing_router.get("", response_model=BillingDashboardResponse)
async def get_billing(
    service: OrganizationService = Depends(get_organization_service),
) -> BillingDashboardResponse:
    dashboard = await service.get_billing_dashboard()

    def map_metric(item) -> BillingMetricResponse:
        return BillingMetricResponse(used=item.used, limit=item.limit, remaining=item.remaining)

    return BillingDashboardResponse(
        plan=dashboard.plan,
        ai_requests=map_metric(dashboard.ai_requests),
        llm_tokens=map_metric(dashboard.llm_tokens),
        channels=map_metric(dashboard.channels),
        users=map_metric(dashboard.users),
        storage_mb=map_metric(dashboard.storage_mb),
        ai_cost_usd=map_metric(dashboard.ai_cost_usd),
    )
