import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.passwords import hash_password
from app.config import get_settings
from app.models.dashboard_user import DashboardUser
from app.models.enums import DashboardRole, InviteStatus, OrganizationPlan, OrganizationSecretType
from app.models.organization import Organization
from app.models.organization_invite import OrganizationInvite
from app.models.organization_member import OrganizationMember
from app.models.organization_secret import OrganizationSecret
from app.models.ai_usage import AIUsage
from app.models.workspace_member import WorkspaceMember
from app.repositories.deps import (
    get_dashboard_user_repository,
    get_organization_invite_repository,
    get_organization_member_repository,
    get_organization_repository,
    get_organization_secret_repository,
    get_organization_usage_repository,
    get_workspace_member_repository,
    get_workspace_repository,
)
from app.services.secrets_service import mask_secret
from app.tenant.context import TenantContext
from app.tenant.plans import get_plan_limits


@dataclass(slots=True)
class MemberView:
    user_id: uuid.UUID
    full_name: str
    email: str
    role: str
    workspace_names: list[str]
    is_active: bool
    last_login_at: datetime | None


@dataclass(slots=True)
class InviteView:
    id: uuid.UUID
    email: str
    role: str
    workspace_id: uuid.UUID | None
    token: str
    invite_url: str
    expires_at: datetime


@dataclass(slots=True)
class SecretView:
    secret_type: str
    masked_value: str
    configured: bool


@dataclass(slots=True)
class BillingMetricView:
    used: int | float
    limit: int | float
    remaining: int | float


@dataclass(slots=True)
class BillingDashboardView:
    plan: str
    ai_requests: BillingMetricView
    llm_tokens: BillingMetricView
    channels: BillingMetricView
    users: BillingMetricView
    storage_mb: BillingMetricView
    ai_cost_usd: BillingMetricView


class PlanEnforcementService:
    UNLIMITED_CHANNELS = 999_999

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._org_repo = get_organization_repository(session)
        self._org_member_repo = get_organization_member_repository(session)

    async def assert_can_add_channel(self, organization_id: uuid.UUID) -> None:
        organization = await self._org_repo.get_by_id(organization_id)
        if organization is None:
            raise ValueError("Organization not found")
        limits = get_plan_limits(OrganizationPlan(organization.plan))
        max_channels = limits.max_channels if organization.plan != OrganizationPlan.ENTERPRISE.value else self.UNLIMITED_CHANNELS
        current = await self._org_repo.count_channels(organization_id)
        if current >= max_channels:
            raise ValueError(
                f"Channel limit reached for plan {organization.plan} ({max_channels} max)"
            )

    async def assert_can_add_user(self, organization_id: uuid.UUID) -> None:
        organization = await self._org_repo.get_by_id(organization_id)
        if organization is None:
            raise ValueError("Organization not found")
        limits = get_plan_limits(OrganizationPlan(organization.plan))
        max_users = limits.max_users if organization.plan != OrganizationPlan.ENTERPRISE.value else self.UNLIMITED_CHANNELS
        current = await self._org_member_repo.count_members(organization_id)
        if current >= max_users:
            raise ValueError(
                f"User limit reached for plan {organization.plan} ({max_users} max)"
            )


class OrganizationSecretsRuntime:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._secret_repo = get_organization_secret_repository(session)
        self._settings = get_settings()

    async def resolve_openrouter_api_key(self, organization_id: uuid.UUID | None) -> str | None:
        if organization_id is None:
            return None
        row = await self._secret_repo.get_by_type(
            organization_id,
            OrganizationSecretType.OPENROUTER.value,
        )
        if row is not None and row.value.strip():
            return row.value.strip()
        return None

    async def resolve_telegram_bot_token(self, organization_id: uuid.UUID | None) -> str | None:
        if organization_id is None:
            return None
        row = await self._secret_repo.get_by_type(
            organization_id,
            OrganizationSecretType.TELEGRAM.value,
        )
        if row is not None and row.value.strip():
            return row.value.strip()
        return None


class OrganizationService:
    INVITE_TTL_DAYS = 7

    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self._session = session
        self._tenant = tenant
        self._org_repo = get_organization_repository(session)
        self._org_member_repo = get_organization_member_repository(session)
        self._workspace_repo = get_workspace_repository(session)
        self._workspace_member_repo = get_workspace_member_repository(session)
        self._invite_repo = get_organization_invite_repository(session)
        self._secret_repo = get_organization_secret_repository(session)
        self._usage_repo = get_organization_usage_repository(session)
        self._user_repo = get_dashboard_user_repository(session)
        self._enforcement = PlanEnforcementService(session)

    async def get_organization(self) -> Organization | None:
        return await self._org_repo.get_by_id(self._tenant.organization_id)

    async def update_organization(
        self,
        *,
        name: str | None = None,
        display_name: str | None = None,
        logo_url: str | None = None,
        brand_color: str | None = None,
        favicon_url: str | None = None,
    ) -> Organization:
        organization = await self.get_organization()
        if organization is None:
            raise ValueError("Organization not found")
        if name is not None:
            organization.name = name
        if display_name is not None:
            organization.display_name = display_name
        if logo_url is not None:
            organization.logo_url = logo_url or None
        if brand_color is not None:
            organization.brand_color = brand_color or None
        if favicon_url is not None:
            organization.favicon_url = favicon_url or None
        await self._org_repo.update(organization)
        return organization

    async def list_members(self) -> list[MemberView]:
        rows = await self._org_member_repo.list_members_with_users(self._tenant.organization_id)
        views: list[MemberView] = []
        for membership, user in rows:
            workspaces = await self._workspace_repo.list_for_user(
                user.id,
                organization_id=self._tenant.organization_id,
            )
            views.append(
                MemberView(
                    user_id=user.id,
                    full_name=user.full_name,
                    email=user.email,
                    role=membership.role,
                    workspace_names=[item.name for item in workspaces],
                    is_active=user.is_active,
                    last_login_at=user.last_login_at,
                )
            )
        return views

    async def create_invite(
        self,
        *,
        email: str,
        role: str,
        workspace_id: uuid.UUID,
        invited_by: str,
        base_url: str = "http://localhost:8000",
    ) -> InviteView:
        await self._enforcement.assert_can_add_user(self._tenant.organization_id)
        workspace = await self._workspace_repo.get_by_id(workspace_id)
        if workspace is None or workspace.organization_id != self._tenant.organization_id:
            raise ValueError("Workspace not found in organization")
        token = secrets.token_urlsafe(32)
        invite = OrganizationInvite(
            organization_id=self._tenant.organization_id,
            workspace_id=workspace_id,
            email=email.lower().strip(),
            role=role,
            token=token,
            status=InviteStatus.PENDING.value,
            invited_by=invited_by,
            expires_at=datetime.now(UTC) + timedelta(days=self.INVITE_TTL_DAYS),
        )
        await self._invite_repo.create(invite)
        return InviteView(
            id=invite.id,
            email=invite.email,
            role=invite.role,
            workspace_id=invite.workspace_id,
            token=invite.token,
            invite_url=f"{base_url.rstrip('/')}/invite/{invite.token}",
            expires_at=invite.expires_at,
        )

    async def list_secrets(self) -> list[SecretView]:
        existing = {
            row.secret_type: row
            for row in await self._secret_repo.list_for_organization(self._tenant.organization_id)
        }
        views: list[SecretView] = []
        for secret_type in OrganizationSecretType:
            row = existing.get(secret_type.value)
            value = row.value if row else ""
            views.append(
                SecretView(
                    secret_type=secret_type.value,
                    masked_value=mask_secret(value),
                    configured=bool(value.strip()),
                )
            )
        return views

    async def upsert_secret(
        self,
        *,
        secret_type: str,
        value: str,
        updated_by: str,
    ) -> SecretView:
        if secret_type not in {item.value for item in OrganizationSecretType}:
            raise ValueError(f"Unsupported secret type: {secret_type}")
        row = await self._secret_repo.get_by_type(self._tenant.organization_id, secret_type)
        if row is None:
            row = OrganizationSecret(
                organization_id=self._tenant.organization_id,
                secret_type=secret_type,
                value=value.strip(),
                updated_by=updated_by,
            )
            await self._secret_repo.create(row)
        else:
            row.value = value.strip()
            row.updated_by = updated_by
            await self._secret_repo.update(row)
        return SecretView(
            secret_type=secret_type,
            masked_value=mask_secret(row.value),
            configured=True,
        )

    async def get_billing_dashboard(self) -> BillingDashboardView:
        organization = await self.get_organization()
        if organization is None:
            raise ValueError("Organization not found")
        plan = OrganizationPlan(organization.plan)
        limits = get_plan_limits(plan)
        unlimited = organization.plan == OrganizationPlan.ENTERPRISE.value

        ai_requests_used = await self._count_ai_requests()
        tokens_used = await self._count_llm_tokens()
        channels_used = await self._org_repo.count_channels(self._tenant.organization_id)
        users_used = await self._org_member_repo.count_members(self._tenant.organization_id)
        storage_used = await self._estimate_storage_mb()
        ai_cost_used = await self._sum_ai_cost()

        return BillingDashboardView(
            plan=organization.plan,
            ai_requests=self._metric(ai_requests_used, limits.max_ai_requests, unlimited),
            llm_tokens=self._metric(tokens_used, limits.max_ai_requests * 1000, unlimited),
            channels=self._metric(channels_used, limits.max_channels, unlimited),
            users=self._metric(users_used, limits.max_users, unlimited),
            storage_mb=self._metric(storage_used, limits.max_storage_mb, unlimited),
            ai_cost_usd=BillingMetricView(used=round(ai_cost_used, 4), limit=0, remaining=0),
        )

    async def list_workspaces_for_org(self) -> list:
        return await self._workspace_repo.list_for_user(
            self._tenant.user_id,
            organization_id=self._tenant.organization_id,
        )

    @staticmethod
    def _metric(used: int | float, limit: int, unlimited: bool) -> BillingMetricView:
        if unlimited:
            return BillingMetricView(used=used, limit=0, remaining=0)
        remaining = max(0, limit - used)
        return BillingMetricView(used=used, limit=limit, remaining=remaining)

    async def _count_ai_requests(self) -> int:
        stmt = select(func.count()).select_from(AIUsage).where(
            AIUsage.organization_id == self._tenant.organization_id
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def _count_llm_tokens(self) -> int:
        stmt = select(func.coalesce(func.sum(AIUsage.total_tokens), 0)).where(
            AIUsage.organization_id == self._tenant.organization_id
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def _sum_ai_cost(self) -> float:
        stmt = select(func.coalesce(func.sum(AIUsage.estimated_cost), 0.0)).where(
            AIUsage.organization_id == self._tenant.organization_id
        )
        return float((await self._session.execute(stmt)).scalar_one())

    async def _estimate_storage_mb(self) -> int:
        from app.models.join_request import JoinRequest
        from app.models.telegram_channel import TelegramChannel

        stmt = (
            select(func.count())
            .select_from(JoinRequest)
            .join(TelegramChannel, TelegramChannel.id == JoinRequest.channel_id)
            .where(TelegramChannel.organization_id == self._tenant.organization_id)
        )
        join_count = int((await self._session.execute(stmt)).scalar_one())
        return max(1, join_count // 10)


class OrganizationInviteService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._invite_repo = get_organization_invite_repository(session)
        self._user_repo = get_dashboard_user_repository(session)
        self._org_member_repo = get_organization_member_repository(session)
        self._workspace_member_repo = get_workspace_member_repository(session)
        self._org_repo = get_organization_repository(session)
        self._workspace_repo = get_workspace_repository(session)
        self._enforcement = PlanEnforcementService(session)

    async def get_invite(self, token: str) -> OrganizationInvite | None:
        invite = await self._invite_repo.get_by_token(token)
        if invite is None:
            return None
        if invite.status != InviteStatus.PENDING.value:
            return None
        if invite.expires_at < datetime.now(UTC):
            invite.status = InviteStatus.EXPIRED.value
            await self._invite_repo.update(invite)
            return None
        return invite

    async def accept_invite(
        self,
        token: str,
        *,
        full_name: str,
        password: str,
    ) -> DashboardUser:
        invite = await self.get_invite(token)
        if invite is None:
            raise ValueError("Invite is invalid or expired")

        await self._enforcement.assert_can_add_user(invite.organization_id)

        user = await self._user_repo.get_by_email(invite.email)
        if user is None:
            user = DashboardUser(
                email=invite.email,
                password_hash=hash_password(password),
                full_name=full_name,
                role=invite.role,
                is_active=True,
            )
            await self._user_repo.create(user)
        else:
            user.password_hash = hash_password(password)
            user.full_name = full_name
            user.is_active = True
            await self._user_repo.update(user)

        if await self._org_member_repo.get_membership(
            organization_id=invite.organization_id,
            user_id=user.id,
        ) is None:
            await self._org_member_repo.create(
                OrganizationMember(
                    organization_id=invite.organization_id,
                    user_id=user.id,
                    role=invite.role,
                )
            )

        workspace_id = invite.workspace_id
        if workspace_id is None:
            default_ws = await self._workspace_repo.get_default_for_organization(invite.organization_id)
            workspace_id = default_ws.id if default_ws else None

        if workspace_id is not None:
            if await self._workspace_member_repo.get_membership(
                workspace_id=workspace_id,
                user_id=user.id,
            ) is None:
                await self._workspace_member_repo.create(
                    WorkspaceMember(
                        workspace_id=workspace_id,
                        user_id=user.id,
                        role=invite.role,
                    )
                )

        invite.status = InviteStatus.ACCEPTED.value
        await self._invite_repo.update(invite)
        return user

    async def get_invite_context(self, token: str) -> tuple[OrganizationInvite, Organization] | None:
        invite = await self.get_invite(token)
        if invite is None:
            return None
        organization = await self._org_repo.get_by_id(invite.organization_id)
        if organization is None:
            return None
        return invite, organization
