import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DashboardRole, OrganizationPlan
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.repositories.deps import get_organization_repository, get_workspace_repository
from app.services.analytics import AnalyticsService
from app.services.investigation import InvestigationService
from app.services.organization_management import OrganizationManagementService
from app.services.tenant_bootstrap import TenantBootstrapService
from app.tenant.context import TenantContext
from tests.admin.test_investigations import seed_investigation_case


@pytest.mark.asyncio
async def test_create_organization_and_workspace_onboarding(
    session: AsyncSession,
    dashboard_owner,
) -> None:
    mgmt = OrganizationManagementService(session, dashboard_owner)
    organization = await mgmt.create_organization(name="Acme Corp", plan=OrganizationPlan.STARTER.value)
    assert organization.onboarding_completed is False
    assert organization.slug.startswith("acme-corp")

    workspaces = await get_workspace_repository(session).list_for_organization(organization.id)
    assert len(workspaces) == 1

    membership = await get_organization_repository(session).get_by_id(organization.id)
    assert membership is not None


@pytest.mark.asyncio
async def test_analytics_tenant_isolation(session: AsyncSession, dashboard_owner) -> None:
    bootstrap = await TenantBootstrapService(session).ensure_default_tenant()
    assert bootstrap is not None
    await seed_investigation_case(session, suffix="analytics-a")

    org_repo = get_organization_repository(session)
    other_org = await org_repo.create(
        Organization(name="Analytics Other", slug=f"an-{uuid.uuid4().hex[:6]}", plan=OrganizationPlan.FREE.value)
    )
    ws = await get_workspace_repository(session).create(
        Workspace(organization_id=other_org.id, name="Other WS", slug="other-ws")
    )

    tenant_a = TenantContext(
        organization_id=bootstrap.organization.id,
        workspace_id=bootstrap.workspace.id,
        user_id=dashboard_owner.id,
        organization_name=bootstrap.organization.name,
        workspace_name=bootstrap.workspace.name,
        plan=OrganizationPlan(bootstrap.organization.plan),
        user=dashboard_owner,
    )
    tenant_b = TenantContext(
        organization_id=other_org.id,
        workspace_id=ws.id,
        user_id=dashboard_owner.id,
        organization_name=other_org.name,
        workspace_name=ws.name,
        plan=OrganizationPlan.FREE,
        user=dashboard_owner,
    )

    overview_a = await AnalyticsService(session, tenant=tenant_a).get_overview()
    overview_b = await AnalyticsService(session, tenant=tenant_b).get_overview()
    assert overview_a.accuracy.total_decisions >= 0
    assert overview_b.accuracy.total_decisions == 0


@pytest.mark.asyncio
async def test_investigation_cross_org_blocked(session: AsyncSession, dashboard_owner) -> None:
    bootstrap = await TenantBootstrapService(session).ensure_default_tenant()
    join_request = await seed_investigation_case(session, suffix="inv-cross")

    other_org = await get_organization_repository(session).create(
        Organization(name="Inv Other", slug=f"inv-{uuid.uuid4().hex[:6]}", plan=OrganizationPlan.FREE.value)
    )
    other_ws = await get_workspace_repository(session).create(
        Workspace(organization_id=other_org.id, name="Inv WS", slug="inv-ws")
    )
    tenant_b = TenantContext(
        organization_id=other_org.id,
        workspace_id=other_ws.id,
        user_id=dashboard_owner.id,
        organization_name=other_org.name,
        workspace_name=other_ws.name,
        plan=OrganizationPlan.FREE,
        user=dashboard_owner,
    )
    service = InvestigationService(session, tenant=tenant_b)
    detail = await service.get_investigation_detail(join_request.id)
    assert detail is None


@pytest.mark.asyncio
async def test_organization_management_pages(
    admin_client: AsyncClient,
) -> None:
    for path in (
        "/admin/organizations",
        "/admin/workspaces",
        "/admin/onboarding",
        "/admin/release-check",
    ):
        response = await admin_client.get(path)
        assert response.status_code == 200, path


@pytest.mark.asyncio
async def test_non_owner_cannot_access_organizations_page(
    session: AsyncSession,
    admin_client: AsyncClient,
) -> None:
    from app.repositories.deps import get_dashboard_user_repository
    from app.admin.auth.passwords import hash_password
    from app.models.dashboard_user import DashboardUser
    from app.services.dashboard_auth import DashboardAuthService, SESSION_COOKIE_NAME
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.database.session import get_db_session

    viewer = await get_dashboard_user_repository(session).create(
        DashboardUser(
            email="viewer@test.local",
            password_hash=hash_password("testpass"),
            full_name="Viewer",
            role=DashboardRole.VIEWER.value,
            is_active=True,
        )
    )
    bootstrap = await TenantBootstrapService(session).ensure_default_tenant()
    assert bootstrap is not None
    from app.repositories.deps import get_organization_member_repository, get_workspace_member_repository

    org_member_repo = get_organization_member_repository(session)
    if await org_member_repo.get_membership(
        organization_id=bootstrap.organization.id,
        user_id=viewer.id,
    ) is None:
        await org_member_repo.create(
            OrganizationMember(
                organization_id=bootstrap.organization.id,
                user_id=viewer.id,
                role=DashboardRole.VIEWER.value,
            )
        )
    ws_member_repo = get_workspace_member_repository(session)
    if await ws_member_repo.get_membership(workspace_id=bootstrap.workspace.id, user_id=viewer.id) is None:
        await ws_member_repo.create(
            WorkspaceMember(
                workspace_id=bootstrap.workspace.id,
                user_id=viewer.id,
                role=DashboardRole.VIEWER.value,
            )
        )

    async def override_get_db_session():
        yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    token, _ = await DashboardAuthService(session).create_session(viewer)
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test", follow_redirects=False)
    client.cookies.set(SESSION_COOKIE_NAME, token)
    response = await client.get("/admin/organizations")
    assert response.status_code == 403
    await client.aclose()
    app.dependency_overrides.clear()
