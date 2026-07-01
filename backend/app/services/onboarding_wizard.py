import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import OrganizationPlan, OrganizationSecretType
from app.models.organization import Organization
from app.repositories.deps import get_organization_repository, get_telegram_channel_repository
from app.services.organization import OrganizationService
from app.services.telegram_runtime import TelegramRuntimeService
from app.tenant.context import TenantContext


@dataclass(slots=True)
class OnboardingConnectionResult:
    telegram_ok: bool
    openrouter_ok: bool
    telegram_detail: str
    openrouter_detail: str


class OnboardingWizardService:
    STEPS = (
        "organization",
        "plan",
        "workspace",
        "telegram",
        "openrouter",
        "channel",
        "verify",
        "done",
    )

    def __init__(self, session: AsyncSession, tenant: TenantContext) -> None:
        self._session = session
        self._tenant = tenant
        self._org_repo = get_organization_repository(session)

    async def get_organization(self) -> Organization | None:
        return await self._org_repo.get_by_id(self._tenant.organization_id)

    async def save_organization_step(
        self,
        *,
        name: str,
        display_name: str | None = None,
    ) -> Organization:
        service = OrganizationService(self._session, self._tenant)
        return await service.update_organization(name=name, display_name=display_name)

    async def save_plan_step(self, *, plan: str) -> Organization:
        if plan not in {item.value for item in OrganizationPlan}:
            raise ValueError("Invalid plan")
        organization = await self.get_organization()
        if organization is None:
            raise ValueError("Organization not found")
        organization.plan = plan
        await self._org_repo.update(organization)
        return organization

    async def save_workspace_step(self, *, workspace_name: str) -> None:
        from app.repositories.deps import get_workspace_repository

        workspace_repo = get_workspace_repository(self._session)
        workspace = await workspace_repo.get_by_id(self._tenant.workspace_id)
        if workspace is None or workspace.organization_id != self._tenant.organization_id:
            raise ValueError("Workspace not found")
        workspace.name = workspace_name.strip()
        await workspace_repo.update(workspace)

    async def save_telegram_step(self, *, token: str, updated_by: str) -> None:
        service = OrganizationService(self._session, self._tenant)
        await service.upsert_secret(
            secret_type=OrganizationSecretType.TELEGRAM.value,
            value=token,
            updated_by=updated_by,
        )

    async def save_openrouter_step(self, *, api_key: str, updated_by: str) -> None:
        service = OrganizationService(self._session, self._tenant)
        await service.upsert_secret(
            secret_type=OrganizationSecretType.OPENROUTER.value,
            value=api_key,
            updated_by=updated_by,
        )

    async def save_channel_step(self, *, telegram_chat_id: int, title: str) -> uuid.UUID:
        from app.models.telegram_bot import TelegramBot
        from app.models.telegram_channel import TelegramChannel
        from app.models.user import User
        from app.repositories.deps import get_telegram_bot_repository, get_user_repository

        channel_repo = get_telegram_channel_repository(self._session)
        existing = await channel_repo.get_by_telegram_chat_id(telegram_chat_id)
        if existing is not None:
            raise ValueError("Channel already connected")
        user_repo = get_user_repository(self._session)
        bot_repo = get_telegram_bot_repository(self._session)
        owner = await user_repo.create(
            User(
                email=f"onboard-{abs(telegram_chat_id)}@bothunter.local",
                password_hash="onboarding",
                full_name="Onboarding Owner",
                telegram_id=9_000_000_000 + abs(telegram_chat_id) % 1_000_000,
            )
        )
        runtime = TelegramRuntimeService(self._session)
        token = await runtime.resolve_token(self._tenant.organization_id)
        bot = await bot_repo.create(
            TelegramBot(owner_id=owner.id, bot_token=token, bot_username="onboarding_bot")
        )
        channel = await channel_repo.create(
            TelegramChannel(
                owner_id=owner.id,
                bot_id=bot.id,
                telegram_chat_id=telegram_chat_id,
                title=title,
                is_active=True,
                organization_id=self._tenant.organization_id,
                workspace_id=self._tenant.workspace_id,
            )
        )
        return channel.id

    async def verify_connections(self) -> OnboardingConnectionResult:
        telegram = TelegramRuntimeService(self._session)
        token = await telegram.resolve_token(self._tenant.organization_id)
        telegram_ok = False
        telegram_detail = "Telegram token missing"
        if token:
            try:
                bot = await telegram.get_bot(self._tenant.organization_id)
                me = await bot.get_me()
                telegram_ok = me is not None
                telegram_detail = f"Connected as @{me.username}" if me else "Telegram check failed"
                await bot.session.close()
            except Exception as exc:
                telegram_detail = str(exc)

        from app.services.organization import OrganizationSecretsRuntime

        org_key = await OrganizationSecretsRuntime(self._session).resolve_openrouter_api_key(
            self._tenant.organization_id
        )
        openrouter_ok = False
        openrouter_detail = "OpenRouter key missing"
        if org_key:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        "https://openrouter.ai/api/v1/models",
                        headers={"Authorization": f"Bearer {org_key}"},
                    )
                openrouter_ok = response.status_code == 200
                openrouter_detail = "OpenRouter API reachable" if openrouter_ok else f"HTTP {response.status_code}"
            except Exception as exc:
                openrouter_detail = str(exc)

        return OnboardingConnectionResult(
            telegram_ok=telegram_ok,
            openrouter_ok=openrouter_ok,
            telegram_detail=telegram_detail,
            openrouter_detail=openrouter_detail,
        )

    async def complete(self) -> Organization:
        organization = await self.get_organization()
        if organization is None:
            raise ValueError("Organization not found")
        organization.onboarding_completed = True
        await self._org_repo.update(organization)
        return organization
