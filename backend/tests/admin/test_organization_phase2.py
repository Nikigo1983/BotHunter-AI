import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DashboardRole, OrganizationPlan, OrganizationSecretType
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.organization_secret import OrganizationSecret
from app.models.telegram_bot import TelegramBot
from app.models.telegram_channel import TelegramChannel
from app.models.workspace import Workspace
from app.repositories.deps import (
    get_organization_repository,
    get_organization_secret_repository,
    get_telegram_bot_repository,
    get_telegram_channel_repository,
    get_user_repository,
    get_workspace_repository,
)
from app.services.organization import OrganizationInviteService, OrganizationSecretsRuntime, PlanEnforcementService
from app.services.tenant_bootstrap import TenantBootstrapService
from app.tenant.context import TenantContext
from app.services.organization import OrganizationService
from tests.conftest import make_user


async def _tenant_for_owner(session: AsyncSession, owner) -> TenantContext:
    bootstrap = await TenantBootstrapService(session).ensure_default_tenant()
    assert bootstrap is not None
    return TenantContext(
        organization_id=bootstrap.organization.id,
        workspace_id=bootstrap.workspace.id,
        user_id=owner.id,
        organization_name=bootstrap.organization.name,
        workspace_name=bootstrap.workspace.name,
        plan=OrganizationPlan(bootstrap.organization.plan),
        user=owner,
    )


@pytest.mark.asyncio
async def test_organization_api_endpoints(
    session: AsyncSession,
    admin_client: AsyncClient,
) -> None:
    org_response = await admin_client.get("/api/v1/organization")
    assert org_response.status_code == 200
    org_payload = org_response.json()
    assert "plan" in org_payload
    assert "slug" in org_payload

    patch_response = await admin_client.patch(
        "/api/v1/organization",
        json={"display_name": "Phase 2 Org", "brand_color": "#336699"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["display_name"] == "Phase 2 Org"

    members_response = await admin_client.get("/api/v1/organization/members")
    assert members_response.status_code == 200
    members = members_response.json()["items"]
    assert len(members) >= 1
    assert "email" in members[0]
    assert "workspace_names" in members[0]

    billing_response = await admin_client.get("/api/v1/billing")
    assert billing_response.status_code == 200
    billing = billing_response.json()
    assert billing["plan"]
    assert "channels" in billing
    assert "users" in billing
    assert "ai_requests" in billing


@pytest.mark.asyncio
async def test_organization_invite_flow(
    session: AsyncSession,
    admin_client: AsyncClient,
    dashboard_owner,
) -> None:
    tenant = await _tenant_for_owner(session, dashboard_owner)
    workspaces = await OrganizationService(session, tenant).list_workspaces_for_org()
    assert workspaces

    invite_response = await admin_client.post(
        "/api/v1/organization/invite",
        json={
            "email": "invited@example.com",
            "role": DashboardRole.VIEWER.value,
            "workspace_id": str(workspaces[0].id),
        },
    )
    assert invite_response.status_code == 200
    invite_payload = invite_response.json()
    assert invite_payload["invite_url"].endswith(f"/invite/{invite_payload['token']}")

    page_response = await admin_client.get(f"/invite/{invite_payload['token']}")
    assert page_response.status_code == 200
    assert "invited@example.com" in page_response.text

    invite_service = OrganizationInviteService(session)
    user = await invite_service.accept_invite(
        invite_payload["token"],
        full_name="Invited User",
        password="secure-pass-123",
    )
    assert user.email == "invited@example.com"

    members = await OrganizationService(session, tenant).list_members()
    emails = {item.email for item in members}
    assert "invited@example.com" in emails


@pytest.mark.asyncio
async def test_organization_secrets_mask_and_runtime(
    session: AsyncSession,
    admin_client: AsyncClient,
    dashboard_owner,
) -> None:
    tenant = await _tenant_for_owner(session, dashboard_owner)
    secret_value = "sk-or-test-key-1234567890abcd"

    save_response = await admin_client.post(
        "/api/v1/organization/secrets",
        json={"secret_type": OrganizationSecretType.OPENROUTER.value, "value": secret_value},
    )
    assert save_response.status_code == 200
    masked = save_response.json()["masked_value"]
    assert masked.endswith("abcd")
    assert secret_value not in masked

    list_response = await admin_client.get("/api/v1/organization/secrets")
    assert list_response.status_code == 200
    items = {item["secret_type"]: item for item in list_response.json()["items"]}
    assert items[OrganizationSecretType.OPENROUTER.value]["configured"] is True

    resolved = await OrganizationSecretsRuntime(session).resolve_openrouter_api_key(
        tenant.organization_id
    )
    assert resolved == secret_value


@pytest.mark.asyncio
async def test_organization_secret_isolation(session: AsyncSession) -> None:
    bootstrap = await TenantBootstrapService(session).ensure_default_tenant()
    assert bootstrap is not None

    org_repo = get_organization_repository(session)
    other_org = await org_repo.create(
        Organization(
            name="Isolated Org",
            slug=f"iso-{uuid.uuid4().hex[:6]}",
            plan=OrganizationPlan.FREE.value,
        )
    )
    secret_repo = get_organization_secret_repository(session)
    await secret_repo.create(
        OrganizationSecret(
            organization_id=bootstrap.organization.id,
            secret_type=OrganizationSecretType.OPENROUTER.value,
            value="org-a-secret-key",
            updated_by="test",
        )
    )

    runtime = OrganizationSecretsRuntime(session)
    assert await runtime.resolve_openrouter_api_key(bootstrap.organization.id) == "org-a-secret-key"
    assert await runtime.resolve_openrouter_api_key(other_org.id) is None


@pytest.mark.asyncio
async def test_free_plan_channel_limit(session: AsyncSession) -> None:
    bootstrap = await TenantBootstrapService(session).ensure_default_tenant()
    assert bootstrap is not None

    org_repo = get_organization_repository(session)
    free_org = await org_repo.create(
        Organization(
            name="Free Org",
            slug=f"free-{uuid.uuid4().hex[:6]}",
            plan=OrganizationPlan.FREE.value,
        )
    )
    ws_repo = get_workspace_repository(session)
    workspace = await ws_repo.create(
        Workspace(organization_id=free_org.id, name="Free WS", slug="free-ws")
    )

    user_repo = get_user_repository(session)
    bot_repo = get_telegram_bot_repository(session)
    channel_repo = get_telegram_channel_repository(session)
    owner = await user_repo.create(make_user("free-owner"))
    bot = await bot_repo.create(
        TelegramBot(owner_id=owner.id, bot_token="token", bot_username="free_bot")
    )
    await channel_repo.create(
        TelegramChannel(
            owner_id=owner.id,
            bot_id=bot.id,
            telegram_chat_id=-1007000001,
            title="Free Channel",
            is_active=True,
            organization_id=free_org.id,
            workspace_id=workspace.id,
        )
    )

    enforcement = PlanEnforcementService(session)
    with pytest.raises(ValueError, match="Channel limit"):
        await enforcement.assert_can_add_channel(free_org.id)


@pytest.mark.asyncio
async def test_organization_admin_pages(
    admin_client: AsyncClient,
) -> None:
    for path in (
        "/admin/organization/members",
        "/admin/organization/secrets",
        "/admin/organization/branding",
        "/admin/billing",
    ):
        response = await admin_client.get(path)
        assert response.status_code == 200, path
