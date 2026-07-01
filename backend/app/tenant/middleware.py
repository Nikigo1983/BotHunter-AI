import uuid

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_session import DashboardSession
from app.repositories.deps import get_dashboard_session_repository
from app.services.dashboard_auth import DashboardAuthContext
from app.tenant.context import TenantContext
from app.tenant.resolver import TenantResolver


async def resolve_tenant_context(
    request: Request,
    auth: DashboardAuthContext,
    session: AsyncSession,
) -> TenantContext:
    resolver = TenantResolver(session)
    header_org = request.headers.get("X-Organization-Id")
    header_workspace = request.headers.get("X-Workspace-Id")
    organization_id = uuid.UUID(header_org) if header_org else auth.session.active_organization_id
    workspace_id = uuid.UUID(header_workspace) if header_workspace else auth.session.active_workspace_id
    tenant = await resolver.resolve(
        user_id=auth.user.id,
        user=auth.user,
        organization_id=organization_id,
        workspace_id=workspace_id,
    )
    if (
        auth.session.active_organization_id != tenant.organization_id
        or auth.session.active_workspace_id != tenant.workspace_id
    ):
        session_repo = get_dashboard_session_repository(session)
        db_session: DashboardSession = auth.session
        db_session.active_organization_id = tenant.organization_id
        db_session.active_workspace_id = tenant.workspace_id
        await session_repo.update(db_session)
    request.state.tenant = tenant
    return tenant


async def require_tenant_from_request(request: Request) -> TenantContext:
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context missing",
        )
    return tenant
