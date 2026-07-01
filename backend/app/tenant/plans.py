from dataclasses import dataclass

from app.models.enums import OrganizationPlan


@dataclass(frozen=True, slots=True)
class PlanLimits:
    max_channels: int
    max_ai_requests: int
    max_users: int
    max_storage_mb: int


PLAN_LIMITS: dict[OrganizationPlan, PlanLimits] = {
    OrganizationPlan.FREE: PlanLimits(
        max_channels=1,
        max_ai_requests=100,
        max_users=1,
        max_storage_mb=256,
    ),
    OrganizationPlan.STARTER: PlanLimits(
        max_channels=5,
        max_ai_requests=5_000,
        max_users=5,
        max_storage_mb=2_048,
    ),
    OrganizationPlan.PROFESSIONAL: PlanLimits(
        max_channels=20,
        max_ai_requests=100_000,
        max_users=20,
        max_storage_mb=10_240,
    ),
    OrganizationPlan.ENTERPRISE: PlanLimits(
        max_channels=999,
        max_ai_requests=10_000_000,
        max_users=999,
        max_storage_mb=102_400,
    ),
}


def get_plan_limits(plan: OrganizationPlan) -> PlanLimits:
    return PLAN_LIMITS[plan]
