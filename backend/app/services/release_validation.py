import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.organization import Organization
from app.models.telegram_channel import TelegramChannel
from app.models.workspace import Workspace
from app.repositories.deps import get_organization_repository
from app.services.analytics import AnalyticsService
from app.services.organization import OrganizationSecretsRuntime
from app.services.system_monitor import SystemMonitorService
from app.services.telegram_runtime import TelegramRuntimeService
from app.tenant.context import TenantContext


@dataclass(slots=True)
class ReleaseCheckItem:
    name: str
    passed: bool
    detail: str


@dataclass(slots=True)
class ReleaseValidationReport:
    items: list[ReleaseCheckItem]

    @property
    def ready_for_production(self) -> bool:
        return bool(self.items) and all(item.passed for item in self.items)


class ReleaseValidationService:
    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self._session = session
        self._tenant = tenant
        self._settings = get_settings()
        self._monitor = SystemMonitorService(session)
        self._org_repo = get_organization_repository(session)

    async def run_checks(self, redis) -> ReleaseValidationReport:
        organization = await self._org_repo.get_by_id(self._tenant.organization_id)
        workspace = await self._get_workspace()
        statuses = await self._monitor.get_service_statuses(redis)
        status_map = {item.name: item for item in statuses}
        secrets = OrganizationSecretsRuntime(self._session)
        telegram = TelegramRuntimeService(self._session)

        org_openrouter = await secrets.resolve_openrouter_api_key(self._tenant.organization_id)
        global_openrouter = self._settings.openrouter_api_key.strip()
        ai_configured = bool(org_openrouter or global_openrouter) or self._settings.ai_provider == "mock"

        org_telegram = await telegram.resolve_token(self._tenant.organization_id)
        telegram_ok = bool(org_telegram) and status_map.get("Telegram API", None) is not None

        channel_count = await self._org_repo.count_channels(self._tenant.organization_id)
        try:
            await AnalyticsService(self._session, tenant=self._tenant).get_accuracy()
            analytics_ok = True
        except Exception:
            analytics_ok = False

        items = [
            ReleaseCheckItem(
                name="Database",
                passed=status_map.get("PostgreSQL", None) is not None
                and status_map["PostgreSQL"].status == "ok",
                detail=status_map.get("PostgreSQL", None).detail
                if status_map.get("PostgreSQL")
                else "PostgreSQL unavailable",
            ),
            ReleaseCheckItem(
                name="Redis",
                passed=status_map.get("Redis", None) is not None
                and status_map["Redis"].status == "ok",
                detail=status_map.get("Redis", None).detail if status_map.get("Redis") else "Redis unavailable",
            ),
            ReleaseCheckItem(
                name="Telegram",
                passed=bool(org_telegram),
                detail="Organization or global Telegram token configured",
            ),
            ReleaseCheckItem(
                name="OpenRouter",
                passed=ai_configured,
                detail="Organization or global OpenRouter key configured",
            ),
            ReleaseCheckItem(
                name="Billing",
                passed=organization is not None and bool(organization.plan),
                detail=f"Plan: {organization.plan}" if organization else "Organization missing",
            ),
            ReleaseCheckItem(
                name="Workspace",
                passed=workspace is not None and not workspace.is_archived,
                detail=workspace.name if workspace else "Active workspace missing",
            ),
            ReleaseCheckItem(
                name="Organization",
                passed=organization is not None
                and not organization.is_archived
                and organization.onboarding_completed,
                detail=organization.display_name or organization.name if organization else "Organization missing",
            ),
            ReleaseCheckItem(
                name="AI",
                passed=ai_configured,
                detail=f"Provider: {self._settings.ai_provider}",
            ),
            ReleaseCheckItem(
                name="Analytics",
                passed=analytics_ok,
                detail="Tenant-scoped analytics queries available",
            ),
        ]
        return ReleaseValidationReport(items=items)

    async def _get_workspace(self) -> Workspace | None:
        stmt = select(Workspace).where(
            Workspace.id == self._tenant.workspace_id,
            Workspace.organization_id == self._tenant.organization_id,
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
