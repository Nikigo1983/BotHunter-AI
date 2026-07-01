import uuid

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_user import DashboardUser
from app.models.organization import Organization
from app.models.organization_invite import OrganizationInvite
from app.models.organization_member import OrganizationMember
from app.models.organization_secret import OrganizationSecret
from app.models.organization_usage import OrganizationUsage
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Organization)

    async def get_by_slug(self, slug: str) -> Organization | None:
        stmt = select(Organization).where(Organization.slug == slug)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Organization]:
        stmt = (
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
            .order_by(Organization.name.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def count_channels(self, organization_id: uuid.UUID) -> int:
        from app.models.telegram_channel import TelegramChannel

        stmt = select(func.count()).select_from(TelegramChannel).where(
            TelegramChannel.organization_id == organization_id
        )
        return int((await self._session.execute(stmt)).scalar_one())


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Workspace)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        organization_id: uuid.UUID | None = None,
    ) -> list[Workspace]:
        stmt = (
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.name.asc())
        )
        if organization_id is not None:
            stmt = stmt.where(Workspace.organization_id == organization_id)
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_default_for_organization(self, organization_id: uuid.UUID) -> Workspace | None:
        stmt = (
            select(Workspace)
            .where(Workspace.organization_id == organization_id)
            .order_by(Workspace.created_at.asc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()


class OrganizationMemberRepository(BaseRepository[OrganizationMember]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OrganizationMember)

    async def get_membership(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> OrganizationMember | None:
        stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def count_members(self, organization_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def list_members_with_users(self, organization_id: uuid.UUID) -> list[tuple[OrganizationMember, DashboardUser]]:
        stmt = (
            select(OrganizationMember, DashboardUser)
            .join(DashboardUser, DashboardUser.id == OrganizationMember.user_id)
            .where(OrganizationMember.organization_id == organization_id)
            .order_by(DashboardUser.full_name.asc())
        )
        return list((await self._session.execute(stmt)).all())


class WorkspaceMemberRepository(BaseRepository[WorkspaceMember]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkspaceMember)

    async def get_membership(
        self,
        *,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> WorkspaceMember | None:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()


class OrganizationInviteRepository(BaseRepository[OrganizationInvite]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OrganizationInvite)

    async def get_by_token(self, token: str) -> OrganizationInvite | None:
        stmt = select(OrganizationInvite).where(OrganizationInvite.token == token)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_pending(self, organization_id: uuid.UUID) -> list[OrganizationInvite]:
        stmt = (
            select(OrganizationInvite)
            .where(
                OrganizationInvite.organization_id == organization_id,
                OrganizationInvite.status == "pending",
            )
            .order_by(desc(OrganizationInvite.created_at))
        )
        return list((await self._session.execute(stmt)).scalars().all())


class OrganizationSecretRepository(BaseRepository[OrganizationSecret]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OrganizationSecret)

    async def get_by_type(
        self,
        organization_id: uuid.UUID,
        secret_type: str,
    ) -> OrganizationSecret | None:
        stmt = select(OrganizationSecret).where(
            OrganizationSecret.organization_id == organization_id,
            OrganizationSecret.secret_type == secret_type,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[OrganizationSecret]:
        stmt = (
            select(OrganizationSecret)
            .where(OrganizationSecret.organization_id == organization_id)
            .order_by(OrganizationSecret.secret_type.asc())
        )
        return list((await self._session.execute(stmt)).scalars().all())


class OrganizationUsageRepository(BaseRepository[OrganizationUsage]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OrganizationUsage)

    async def increment_int(
        self,
        *,
        organization_id: uuid.UUID,
        metric: str,
        period_start,
        delta: int = 1,
    ) -> OrganizationUsage:
        stmt = select(OrganizationUsage).where(
            OrganizationUsage.organization_id == organization_id,
            OrganizationUsage.metric == metric,
            OrganizationUsage.period_start == period_start,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = OrganizationUsage(
                organization_id=organization_id,
                metric=metric,
                period_start=period_start,
                int_value=delta,
            )
            await self.create(row)
            return row
        row.int_value += delta
        await self._session.flush()
        return row
