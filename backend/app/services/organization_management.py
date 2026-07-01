import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_user import DashboardUser
from app.models.enums import DashboardRole, OrganizationPlan
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.repositories.deps import (
    get_organization_member_repository,
    get_organization_repository,
    get_workspace_member_repository,
    get_workspace_repository,
)
from app.services.policy import PolicyService
from app.tenant.context import TenantContext


def slugify_name(value: str, *, fallback: str = "org") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:96] if slug else fallback


@dataclass(slots=True)
class OrganizationListItem:
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    display_name: str | None
    is_archived: bool
    onboarding_completed: bool
    workspace_count: int
    channel_count: int


@dataclass(slots=True)
class WorkspaceListItem:
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    is_archived: bool
    member_count: int


class OrganizationManagementService:
    DEFAULT_ORG_SLUG = "default"

    def __init__(self, session: AsyncSession, user: DashboardUser) -> None:
        self._session = session
        self._user = user
        self._org_repo = get_organization_repository(session)
        self._org_member_repo = get_organization_member_repository(session)
        self._workspace_repo = get_workspace_repository(session)
        self._workspace_member_repo = get_workspace_member_repository(session)

    async def list_organizations(self, *, include_archived: bool = False) -> list[OrganizationListItem]:
        orgs = await self._org_repo.list_for_user(self._user.id, include_archived=include_archived)
        items: list[OrganizationListItem] = []
        for org in orgs:
            workspace_count = await self._count_workspaces(org.id)
            channel_count = await self._org_repo.count_channels(org.id)
            items.append(
                OrganizationListItem(
                    id=org.id,
                    name=org.name,
                    slug=org.slug,
                    plan=org.plan,
                    display_name=org.display_name,
                    is_archived=org.is_archived,
                    onboarding_completed=org.onboarding_completed,
                    workspace_count=workspace_count,
                    channel_count=channel_count,
                )
            )
        return items

    async def create_organization(
        self,
        *,
        name: str,
        plan: str = OrganizationPlan.FREE.value,
        display_name: str | None = None,
    ) -> Organization:
        if self._user.role != DashboardRole.OWNER.value:
            raise ValueError("Only owners can create organizations")
        base_slug = slugify_name(name)
        slug = base_slug
        suffix = 1
        while await self._org_repo.get_by_slug(slug) is not None:
            slug = f"{base_slug}-{suffix}"
            suffix += 1

        organization = Organization(
            name=name.strip(),
            slug=slug,
            plan=plan,
            display_name=display_name or name.strip(),
            onboarding_completed=False,
        )
        await self._org_repo.create(organization)
        workspace = Workspace(
            organization_id=organization.id,
            name="Default Workspace",
            slug="default",
        )
        await self._workspace_repo.create(workspace)
        await self._org_member_repo.create(
            OrganizationMember(
                organization_id=organization.id,
                user_id=self._user.id,
                role=DashboardRole.OWNER.value,
            )
        )
        await self._workspace_member_repo.create(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=self._user.id,
                role=DashboardRole.OWNER.value,
            )
        )
        await PolicyService(self._session, organization_id=organization.id).ensure_initial_policy(
            organization.id
        )
        return organization

    async def update_organization(
        self,
        organization_id: uuid.UUID,
        *,
        name: str | None = None,
        display_name: str | None = None,
        plan: str | None = None,
    ) -> Organization:
        organization = await self._require_owner_membership(organization_id)
        if name is not None:
            organization.name = name.strip()
        if display_name is not None:
            organization.display_name = display_name.strip() or None
        if plan is not None:
            organization.plan = plan
        await self._org_repo.update(organization)
        return organization

    async def archive_organization(self, organization_id: uuid.UUID) -> Organization:
        organization = await self._require_owner_membership(organization_id)
        if organization.slug == self.DEFAULT_ORG_SLUG:
            raise ValueError("Default organization cannot be archived")
        organization.is_archived = True
        await self._org_repo.update(organization)
        return organization

    async def unarchive_organization(self, organization_id: uuid.UUID) -> Organization:
        organization = await self._require_owner_membership(organization_id)
        organization.is_archived = False
        await self._org_repo.update(organization)
        return organization

    async def delete_organization(self, organization_id: uuid.UUID) -> None:
        organization = await self._require_owner_membership(organization_id)
        if organization.slug == self.DEFAULT_ORG_SLUG:
            raise ValueError("Default organization cannot be deleted")
        channels = await self._org_repo.count_channels(organization_id)
        if channels > 0:
            raise ValueError("Organization has connected channels and cannot be deleted")
        members = await self._org_member_repo.count_members(organization_id)
        if members > 1:
            raise ValueError("Organization has multiple members and cannot be deleted")
        await self._org_repo.delete(organization)

    async def _require_owner_membership(self, organization_id: uuid.UUID) -> Organization:
        membership = await self._org_member_repo.get_membership(
            organization_id=organization_id,
            user_id=self._user.id,
        )
        if membership is None or membership.role != DashboardRole.OWNER.value:
            raise ValueError("Owner access required for this organization")
        organization = await self._org_repo.get_by_id(organization_id)
        if organization is None:
            raise ValueError("Organization not found")
        return organization

    async def _count_workspaces(self, organization_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Workspace).where(
            Workspace.organization_id == organization_id,
            Workspace.is_archived.is_(False),
        )
        return int((await self._session.execute(stmt)).scalar_one())


class WorkspaceManagementService:
    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self._session = session
        self._tenant = tenant
        self._workspace_repo = get_workspace_repository(session)
        self._workspace_member_repo = get_workspace_member_repository(session)
        self._org_member_repo = get_organization_member_repository(session)

    async def list_workspaces(self, *, include_archived: bool = False) -> list[WorkspaceListItem]:
        await self._require_org_owner()
        stmt = select(Workspace).where(Workspace.organization_id == self._tenant.organization_id)
        if not include_archived:
            stmt = stmt.where(Workspace.is_archived.is_(False))
        stmt = stmt.order_by(Workspace.name.asc())
        workspaces = list((await self._session.execute(stmt)).scalars().all())
        items: list[WorkspaceListItem] = []
        for workspace in workspaces:
            member_count = await self._count_members(workspace.id)
            items.append(
                WorkspaceListItem(
                    id=workspace.id,
                    organization_id=workspace.organization_id,
                    name=workspace.name,
                    slug=workspace.slug,
                    is_archived=workspace.is_archived,
                    member_count=member_count,
                )
            )
        return items

    async def create_workspace(self, *, name: str) -> Workspace:
        await self._require_org_owner()
        base_slug = slugify_name(name, fallback="workspace")
        slug = base_slug
        suffix = 1
        while await self._workspace_repo.get_by_org_slug(self._tenant.organization_id, slug) is not None:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        workspace = Workspace(
            organization_id=self._tenant.organization_id,
            name=name.strip(),
            slug=slug,
        )
        await self._workspace_repo.create(workspace)
        await self._workspace_member_repo.create(
            WorkspaceMember(
                workspace_id=workspace.id,
                user_id=self._tenant.user_id,
                role=DashboardRole.OWNER.value,
            )
        )
        return workspace

    async def rename_workspace(self, workspace_id: uuid.UUID, *, name: str) -> Workspace:
        await self._require_org_owner()
        workspace = await self._get_workspace_in_org(workspace_id)
        workspace.name = name.strip()
        await self._workspace_repo.update(workspace)
        return workspace

    async def archive_workspace(self, workspace_id: uuid.UUID) -> Workspace:
        await self._require_org_owner()
        workspace = await self._get_workspace_in_org(workspace_id)
        if workspace.slug == "default":
            raise ValueError("Default workspace cannot be archived")
        workspace.is_archived = True
        await self._workspace_repo.update(workspace)
        return workspace

    async def assign_user(
        self,
        workspace_id: uuid.UUID,
        *,
        user_id: uuid.UUID,
        role: str,
    ) -> None:
        await self._require_org_owner()
        workspace = await self._get_workspace_in_org(workspace_id)
        org_membership = await self._org_member_repo.get_membership(
            organization_id=self._tenant.organization_id,
            user_id=user_id,
        )
        if org_membership is None:
            raise ValueError("User is not a member of this organization")
        existing = await self._workspace_member_repo.get_membership(
            workspace_id=workspace.id,
            user_id=user_id,
        )
        if existing is None:
            await self._workspace_member_repo.create(
                WorkspaceMember(workspace_id=workspace.id, user_id=user_id, role=role)
            )
        else:
            existing.role = role
            await self._workspace_member_repo.update(existing)

    async def list_org_members_for_assignment(self) -> list[tuple[uuid.UUID, str, str]]:
        await self._require_org_owner()
        rows = await self._org_member_repo.list_members_with_users(self._tenant.organization_id)
        return [(user.id, user.full_name, user.email) for _, user in rows]

    async def _get_workspace_in_org(self, workspace_id: uuid.UUID) -> Workspace:
        workspace = await self._workspace_repo.get_by_id(workspace_id)
        if workspace is None or workspace.organization_id != self._tenant.organization_id:
            raise ValueError("Workspace not found")
        return workspace

    async def _require_org_owner(self) -> None:
        membership = await self._org_member_repo.get_membership(
            organization_id=self._tenant.organization_id,
            user_id=self._tenant.user_id,
        )
        if membership is None or membership.role != DashboardRole.OWNER.value:
            raise ValueError("Owner access required")

    async def _count_members(self, workspace_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id
        )
        return int((await self._session.execute(stmt)).scalar_one())
