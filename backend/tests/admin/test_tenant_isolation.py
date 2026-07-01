import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DashboardRole, OrganizationPlan
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.repositories.deps import (
    get_admin_dashboard_repository,
    get_organization_member_repository,
    get_organization_repository,
    get_workspace_member_repository,
    get_workspace_repository,
)
from app.services.admin_dashboard import AdminDashboardService
from app.services.tenant_bootstrap import TenantBootstrapService
from tests.admin.test_investigations import seed_investigation_case


@pytest.mark.asyncio
async def test_tenant_bootstrap_creates_default_org(session: AsyncSession, dashboard_owner) -> None:
    result = await TenantBootstrapService(session).ensure_default_tenant()
    assert result is not None
    assert result.organization.slug == "default"
    assert result.workspace.slug == "default"


@pytest.mark.asyncio
async def test_cross_organization_join_request_isolation(session: AsyncSession, dashboard_owner) -> None:
    await TenantBootstrapService(session).ensure_default_tenant()
    join_request = await seed_investigation_case(session, suffix="tenant-a")

    org_repo = get_organization_repository(session)
    other_org = await org_repo.create(
        Organization(name="Other Corp", slug=f"other-{uuid.uuid4().hex[:6]}", plan=OrganizationPlan.FREE.value)
    )
    ws_repo = get_workspace_repository(session)
    other_ws = await ws_repo.create(
        Workspace(organization_id=other_org.id, name="Other WS", slug="other-ws")
    )
    await get_organization_member_repository(session).create(
        OrganizationMember(
            organization_id=other_org.id,
            user_id=dashboard_owner.id,
            role=DashboardRole.OWNER.value,
        )
    )
    await get_workspace_member_repository(session).create(
        WorkspaceMember(
            workspace_id=other_ws.id,
            user_id=dashboard_owner.id,
            role=DashboardRole.OWNER.value,
        )
    )

    from app.tenant.context import TenantContext

    tenant_b = TenantContext(
        organization_id=other_org.id,
        workspace_id=other_ws.id,
        user_id=dashboard_owner.id,
        organization_name=other_org.name,
        workspace_name=other_ws.name,
        plan=OrganizationPlan.FREE,
        user=dashboard_owner,
    )
    service = AdminDashboardService(session, tenant=tenant_b)
    detail = await service.get_join_request_detail(join_request.id)
    assert detail is None


@pytest.mark.asyncio
async def test_same_organization_sees_join_request(session: AsyncSession, dashboard_owner) -> None:
    bootstrap = await TenantBootstrapService(session).ensure_default_tenant()
    assert bootstrap is not None
    join_request = await seed_investigation_case(session, suffix="tenant-visible")

    from app.tenant.context import TenantContext
    from app.models.enums import OrganizationPlan

    tenant = TenantContext(
        organization_id=bootstrap.organization.id,
        workspace_id=bootstrap.workspace.id,
        user_id=dashboard_owner.id,
        organization_name=bootstrap.organization.name,
        workspace_name=bootstrap.workspace.name,
        plan=OrganizationPlan(bootstrap.organization.plan),
        user=dashboard_owner,
    )
    service = AdminDashboardService(session, tenant=tenant)
    detail = await service.get_join_request_detail(join_request.id)
    assert detail is not None
