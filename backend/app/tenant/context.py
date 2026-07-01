import uuid
from dataclasses import dataclass

from app.models.dashboard_user import DashboardUser
from app.models.enums import OrganizationPlan


@dataclass(slots=True, frozen=True)
class TenantContext:
    organization_id: uuid.UUID
    workspace_id: uuid.UUID
    user_id: uuid.UUID
    organization_name: str
    workspace_name: str
    plan: OrganizationPlan
    user: DashboardUser

    def ensure_organization(self, organization_id: uuid.UUID) -> None:
        if organization_id != self.organization_id:
            raise PermissionError("Cross-organization access denied")

    def ensure_workspace(self, workspace_id: uuid.UUID) -> None:
        if workspace_id != self.workspace_id:
            raise PermissionError("Cross-workspace access denied")
