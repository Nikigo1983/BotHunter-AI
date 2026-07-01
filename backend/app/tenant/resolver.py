import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DashboardRole, OrganizationPlan
from app.repositories.deps import (
    get_organization_member_repository,
    get_organization_repository,
    get_workspace_member_repository,
    get_workspace_repository,
)
from app.tenant.context import TenantContext


class TenantResolver:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._org_repo = get_organization_repository(session)
        self._workspace_repo = get_workspace_repository(session)
        self._org_member_repo = get_organization_member_repository(session)
        self._workspace_member_repo = get_workspace_member_repository(session)

    async def resolve(
        self,
        *,
        user_id: uuid.UUID,
        user,
        organization_id: uuid.UUID | None,
        workspace_id: uuid.UUID | None,
    ) -> TenantContext:
        orgs = await self._org_repo.list_for_user(user_id)
        if not orgs:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User is not assigned to any organization",
            )

        organization = next((item for item in orgs if item.id == organization_id), None)
        if organization is None:
            organization = orgs[0]

        membership = await self._org_member_repo.get_membership(
            organization_id=organization.id,
            user_id=user_id,
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization membership required",
            )

        workspaces = await self._workspace_repo.list_for_user(
            user_id,
            organization_id=organization.id,
        )
        if not workspaces:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No workspace access for organization",
            )

        workspace = next((item for item in workspaces if item.id == workspace_id), None)
        if workspace is None:
            workspace = workspaces[0]

        ws_membership = await self._workspace_member_repo.get_membership(
            workspace_id=workspace.id,
            user_id=user_id,
        )
        if ws_membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace membership required",
            )

        effective_role = membership.role
        if membership.role != DashboardRole.OWNER.value:
            effective_role = ws_membership.role

        user.role = effective_role
        plan = OrganizationPlan(organization.plan)
        return TenantContext(
            organization_id=organization.id,
            workspace_id=workspace.id,
            user_id=user_id,
            organization_name=organization.display_name or organization.name,
            workspace_name=workspace.name,
            plan=plan,
            user=user,
        )

    async def list_accessible_workspaces(self, user_id: uuid.UUID) -> list[tuple]:
        orgs = await self._org_repo.list_for_user(user_id)
        result = []
        for org in orgs:
            workspaces = await self._workspace_repo.list_for_user(user_id, organization_id=org.id)
            for workspace in workspaces:
                result.append((org, workspace))
        return result
