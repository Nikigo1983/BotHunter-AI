import uuid
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_user import DashboardUser
from app.models.enums import DashboardRole, OrganizationPlan
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.policy_version import PolicyVersion
from app.models.system_setting import SystemSetting
from app.models.telegram_channel import TelegramChannel
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.repositories.deps import (
    get_dashboard_user_repository,
    get_organization_member_repository,
    get_organization_repository,
    get_workspace_member_repository,
    get_workspace_repository,
)
from app.services.policy import PolicyService


@dataclass(slots=True)
class BootstrapResult:
    organization: Organization
    workspace: Workspace


class TenantBootstrapService:
    DEFAULT_ORG_SLUG = "default"
    DEFAULT_ORG_NAME = "Default Organization"
    DEFAULT_WORKSPACE_SLUG = "default"
    DEFAULT_WORKSPACE_NAME = "Default Workspace"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._org_repo = get_organization_repository(session)
        self._workspace_repo = get_workspace_repository(session)
        self._org_member_repo = get_organization_member_repository(session)
        self._workspace_member_repo = get_workspace_member_repository(session)
        self._user_repo = get_dashboard_user_repository(session)

    async def ensure_default_tenant(self) -> BootstrapResult | None:
        existing = await self._org_repo.get_by_slug(self.DEFAULT_ORG_SLUG)
        if existing is not None:
            workspace = await self._workspace_repo.get_default_for_organization(existing.id)
            if workspace is None:
                raise RuntimeError("Default organization exists without workspace")
            await self._ensure_memberships(existing, workspace)
            await self._backfill_tenant_ids(existing, workspace)
            return BootstrapResult(organization=existing, workspace=workspace)

        organization = Organization(
            name=self.DEFAULT_ORG_NAME,
            slug=self.DEFAULT_ORG_SLUG,
            plan=OrganizationPlan.PROFESSIONAL.value,
            display_name=self.DEFAULT_ORG_NAME,
        )
        await self._org_repo.create(organization)
        workspace = Workspace(
            organization_id=organization.id,
            name=self.DEFAULT_WORKSPACE_NAME,
            slug=self.DEFAULT_WORKSPACE_SLUG,
        )
        await self._workspace_repo.create(workspace)
        await self._ensure_memberships(organization, workspace)
        await self._backfill_tenant_ids(organization, workspace)
        await PolicyService(self._session).ensure_initial_policy(organization.id)
        return BootstrapResult(organization=organization, workspace=workspace)

    async def _ensure_memberships(self, organization: Organization, workspace: Workspace) -> None:
        users = await self._user_repo.get_all(limit=500)
        for user in users:
            if await self._org_member_repo.get_membership(
                organization_id=organization.id,
                user_id=user.id,
            ) is None:
                await self._org_member_repo.create(
                    OrganizationMember(
                        organization_id=organization.id,
                        user_id=user.id,
                        role=user.role if user.role == DashboardRole.OWNER.value else DashboardRole.ADMINISTRATOR.value,
                    )
                )
            if await self._workspace_member_repo.get_membership(
                workspace_id=workspace.id,
                user_id=user.id,
            ) is None:
                await self._workspace_member_repo.create(
                    WorkspaceMember(
                        workspace_id=workspace.id,
                        user_id=user.id,
                        role=user.role,
                    )
                )

    async def _backfill_tenant_ids(self, organization: Organization, workspace: Workspace) -> None:
        await self._session.execute(
            update(TelegramChannel)
            .where(TelegramChannel.organization_id.is_(None))
            .values(organization_id=organization.id, workspace_id=workspace.id)
        )
        await self._session.execute(
            update(PolicyVersion)
            .where(PolicyVersion.organization_id.is_(None))
            .values(organization_id=organization.id)
        )
        settings = list(
            (await self._session.execute(select(SystemSetting).where(SystemSetting.organization_id.is_(None)))).scalars()
        )
        for setting in settings:
            setting.organization_id = organization.id
        await self._session.flush()

