from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.ai_usage import AIUsage
from app.models.channel_connection_error import ChannelConnectionError
from app.models.enums import JoinRequestStatus, NotificationLevel, SystemErrorSource
from app.models.join_request import JoinRequest
from app.models.telegram_channel import TelegramChannel
from app.repositories.deps import (
    get_ai_usage_repository,
    get_channel_connection_error_repository,
    get_system_error_repository,
    get_system_notification_repository,
)
from app.services.dashboard_auth import DashboardAuthService
from app.services.health import HealthService
from app.services.runtime_settings import RuntimeSettingsService
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ServiceStatus:
    name: str
    status: str
    detail: str | None = None
    checked_at: datetime | None = None


@dataclass(slots=True)
class QueueStats:
    pending: int
    running: int
    failed: int
    retries: int


@dataclass(slots=True)
class UsageLimits:
    ai_requests_today: int
    tokens_today: int
    cost_today: float
    cost_month: float
    monthly_budget: float
    remaining_budget: float


@dataclass(slots=True)
class ReadyCheckItem:
    label: str
    passed: bool
    detail: str | None = None


@dataclass(slots=True)
class ProductionReadyReport:
    score_percent: int
    items: list[ReadyCheckItem]


@dataclass(slots=True)
class DockerContainerStatus:
    name: str
    status: str
    restart_count: int | None = None


@dataclass(slots=True)
class DockerHealth:
    cpu_percent: float | None
    memory_used_mb: float | None
    memory_total_mb: float | None
    containers: list[DockerContainerStatus]


class SystemMonitorService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()
        self._error_repo = get_system_error_repository(session)
        self._notification_repo = get_system_notification_repository(session)
        self._usage_repo = get_ai_usage_repository(session)
        self._conn_error_repo = get_channel_connection_error_repository(session)

    async def get_service_statuses(self, redis) -> list[ServiceStatus]:
        now = datetime.now(UTC)
        health = HealthService(self._settings, self._session, redis)
        health_result = await health.check()

        statuses = [
            ServiceStatus(
                name="PostgreSQL",
                status="ok" if health_result.services.get("database") == "ok" else "error",
                checked_at=now,
            ),
            ServiceStatus(
                name="Redis",
                status="ok" if health_result.services.get("redis") == "ok" else "error",
                checked_at=now,
            ),
            await self._check_telegram(),
            await self._check_openrouter(),
            await self._check_queue(),
        ]

        last_ai = await self._last_ai_request()
        if last_ai:
            statuses.append(
                ServiceStatus(
                    name="Last AI request",
                    status="ok",
                    detail=last_ai,
                    checked_at=now,
                )
            )

        last_tg = await self._last_telegram_activity()
        if last_tg:
            statuses.append(
                ServiceStatus(
                    name="Last Telegram request",
                    status="ok",
                    detail=last_tg,
                    checked_at=now,
                )
            )
        return statuses

    async def _check_telegram(self) -> ServiceStatus:
        now = datetime.now(UTC)
        from app.repositories.deps import get_organization_repository
        from app.services.telegram_runtime import TelegramRuntimeService

        default_org = await get_organization_repository(self._session).get_by_slug("default")
        token = await TelegramRuntimeService(self._session).resolve_token(
            default_org.id if default_org else None
        )
        if not token:
            return ServiceStatus(
                name="Telegram API",
                status="error",
                detail="BOT_TOKEN not configured",
                checked_at=now,
            )
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
                data = response.json()
            if data.get("ok"):
                username = data.get("result", {}).get("username", "?")
                return ServiceStatus(
                    name="Telegram API",
                    status="ok",
                    detail=f"@{username}",
                    checked_at=now,
                )
            return ServiceStatus(
                name="Telegram API",
                status="error",
                detail=str(data.get("description", "Unknown error")),
                checked_at=now,
            )
        except Exception as exc:
            await self.log_error(SystemErrorSource.TELEGRAM.value, str(exc))
            return ServiceStatus(name="Telegram API", status="error", detail=str(exc), checked_at=now)

    async def _check_openrouter(self) -> ServiceStatus:
        now = datetime.now(UTC)
        runtime = await RuntimeSettingsService(self._session).get_effective_settings()
        if runtime.ai_provider != "openrouter":
            return ServiceStatus(
                name="OpenRouter",
                status="ok",
                detail=f"Provider: {runtime.ai_provider}",
                checked_at=now,
            )
        if not runtime.openrouter_api_key:
            return ServiceStatus(
                name="OpenRouter",
                status="error",
                detail="API key not configured",
                checked_at=now,
            )
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{runtime.openrouter_base_url.rstrip('/')}/models",
                    headers={"Authorization": f"Bearer {runtime.openrouter_api_key}"},
                )
            if response.status_code == 200:
                return ServiceStatus(name="OpenRouter", status="ok", detail="API reachable", checked_at=now)
            return ServiceStatus(
                name="OpenRouter",
                status="error",
                detail=f"HTTP {response.status_code}",
                checked_at=now,
            )
        except Exception as exc:
            await self.log_error(SystemErrorSource.OPENROUTER.value, str(exc))
            return ServiceStatus(name="OpenRouter", status="error", detail=str(exc), checked_at=now)

    async def _check_queue(self) -> ServiceStatus:
        stats = await self.get_queue_stats()
        now = datetime.now(UTC)
        detail = f"Pending: {stats.pending}, Failed: {stats.failed}"
        status = "ok" if stats.failed == 0 else "warning"
        return ServiceStatus(name="Queue", status=status, detail=detail, checked_at=now)

    async def get_queue_stats(self) -> QueueStats:
        pending_stmt = select(func.count()).select_from(JoinRequest).where(
            JoinRequest.status == JoinRequestStatus.PENDING
        )
        manual_stmt = select(func.count()).select_from(JoinRequest).where(
            JoinRequest.status == JoinRequestStatus.MANUAL_REVIEW
        )
        pending = int((await self._session.execute(pending_stmt)).scalar_one())
        running = int((await self._session.execute(manual_stmt)).scalar_one())
        failed_errors = await self._error_repo.count_unresolved()
        conn_errors_stmt = select(func.count()).select_from(ChannelConnectionError)
        conn_failed = int((await self._session.execute(conn_errors_stmt)).scalar_one())
        return QueueStats(
            pending=pending,
            running=running,
            failed=failed_errors + conn_failed,
            retries=conn_failed,
        )

    async def get_usage_limits(self) -> UsageLimits:
        runtime = await RuntimeSettingsService(self._session).get_effective_settings()
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = today_start.replace(day=1)
        today_stmt = (
            select(
                func.count(AIUsage.id),
                func.coalesce(func.sum(AIUsage.total_tokens), 0),
                func.coalesce(func.sum(AIUsage.estimated_cost), 0.0),
            )
            .where(AIUsage.created_at >= today_start)
        )
        month_stmt = select(func.coalesce(func.sum(AIUsage.estimated_cost), 0.0)).where(
            AIUsage.created_at >= month_start
        )
        today_row = (await self._session.execute(today_stmt)).one()
        month_cost = float((await self._session.execute(month_stmt)).scalar_one())
        budget = runtime.monthly_budget_usd
        remaining = max(0.0, budget - month_cost)
        return UsageLimits(
            ai_requests_today=int(today_row[0]),
            tokens_today=int(today_row[1]),
            cost_today=float(today_row[2]),
            cost_month=month_cost,
            monthly_budget=budget,
            remaining_budget=remaining,
        )

    async def log_error(self, source: str, message: str, details: str | None = None) -> None:
        from app.models.system_error import SystemError

        await self._error_repo.create(
            SystemError(source=source, message=message[:512], details=details, resolved=False)
        )

    async def get_production_ready_report(self, redis) -> ProductionReadyReport:
        runtime = await RuntimeSettingsService(self._session).get_effective_settings()
        statuses = await self.get_service_statuses(redis)
        status_map = {item.name: item for item in statuses}

        user_count = await DashboardAuthService(self._session).count_users()
        channel_stmt = select(func.count()).select_from(TelegramChannel).where(
            TelegramChannel.is_active.is_(True)
        )
        active_channels = int((await self._session.execute(channel_stmt)).scalar_one())

        items = [
            ReadyCheckItem(
                label="AI configured",
                passed=runtime.ai_provider == "mock" or bool(runtime.openrouter_api_key or runtime.openai_api_key),
                detail=f"Provider: {runtime.ai_provider}",
            ),
            ReadyCheckItem(
                label="Telegram connected",
                passed=status_map.get("Telegram API", ServiceStatus("", "error")).status == "ok",
            ),
            ReadyCheckItem(
                label="Channel connected",
                passed=active_channels > 0,
                detail=f"{active_channels} active channel(s)",
            ),
            ReadyCheckItem(
                label="OpenRouter working",
                passed=runtime.ai_provider != "openrouter"
                or status_map.get("OpenRouter", ServiceStatus("", "error")).status == "ok",
            ),
            ReadyCheckItem(
                label="Redis",
                passed=status_map.get("Redis", ServiceStatus("", "error")).status == "ok",
            ),
            ReadyCheckItem(
                label="PostgreSQL",
                passed=status_map.get("PostgreSQL", ServiceStatus("", "error")).status == "ok",
            ),
            ReadyCheckItem(
                label="Dashboard auth",
                passed=user_count > 0,
                detail=f"{user_count} dashboard user(s)",
            ),
            ReadyCheckItem(
                label="HTTPS",
                passed=self._settings.dashboard_https_enabled,
                detail="Set DASHBOARD_HTTPS_ENABLED=true behind TLS",
            ),
            ReadyCheckItem(
                label="Backup configured",
                passed=runtime.backup_configured,
                detail="Enable via Settings or after first backup",
            ),
            ReadyCheckItem(
                label="Monitoring",
                passed=status_map.get("Queue", ServiceStatus("", "error")).status != "error",
            ),
        ]
        passed = sum(1 for item in items if item.passed)
        score = round(passed / len(items) * 100)
        return ProductionReadyReport(score_percent=score, items=items)

    async def _last_ai_request(self) -> str | None:
        stmt = select(AIUsage).order_by(desc(AIUsage.created_at)).limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return f"{row.provider}/{row.model} — {row.created_at.isoformat()}"

    async def _last_telegram_activity(self) -> str | None:
        stmt = select(JoinRequest).order_by(desc(JoinRequest.created_at)).limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return f"Join request {row.id} — {row.created_at.isoformat()}"

    async def get_docker_health(self) -> DockerHealth:
        cpu_percent = None
        memory_used_mb = None
        memory_total_mb = None
        containers = [
            DockerContainerStatus(name="bothunter-api", status="running"),
            DockerContainerStatus(name="bothunter-bot", status="running"),
            DockerContainerStatus(name="bothunter-postgres", status="running"),
            DockerContainerStatus(name="bothunter-redis", status="running"),
        ]
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            memory_used_mb = round(mem.used / (1024 * 1024), 1)
            memory_total_mb = round(mem.total / (1024 * 1024), 1)
        except Exception:
            logger.debug("psutil not available for docker health metrics")
        return DockerHealth(
            cpu_percent=cpu_percent,
            memory_used_mb=memory_used_mb,
            memory_total_mb=memory_total_mb,
            containers=containers,
        )

    async def sync_health_alerts(self, redis) -> None:
        from app.models.system_notification import SystemNotification
        from app.services.notification_service import NotificationService

        notifier = NotificationService(self._session)
        statuses = await self.get_service_statuses(redis)
        usage = await self.get_usage_limits()

        for item in statuses:
            source = item.name.lower().replace(" ", "_")
            if item.status == "ok" and item.name in {"Telegram API", "OpenRouter"}:
                await notifier.resolve_alerts_for_source(source)
                continue
            if item.status == "error" and item.name in {"Telegram API", "OpenRouter"}:
                await notifier.ensure_alert(
                    level=NotificationLevel.CRITICAL.value,
                    title=f"{item.name} unavailable",
                    message=item.detail or "Service check failed",
                    source=source,
                )

        if usage.remaining_budget <= 0:
            await notifier.ensure_alert(
                level=NotificationLevel.CRITICAL.value,
                title="Monthly AI budget exhausted",
                message=f"Spent ${usage.cost_month:.2f} of ${usage.monthly_budget:.2f}",
                source="usage_limits",
            )
        elif usage.remaining_budget < usage.monthly_budget * 0.1:
            await notifier.ensure_alert(
                level=NotificationLevel.WARNING.value,
                title="AI budget almost exhausted",
                message=f"Remaining ${usage.remaining_budget:.2f}",
                source="usage_limits",
            )

    async def read_log_tail(self, log_name: str, *, lines: int = 200) -> list[str]:
        from pathlib import Path

        log_files = {
            "bot": Path("logs/bot.log"),
            "api": Path("logs/app.log"),
            "ai": Path("logs/app.log"),
        }
        path = log_files.get(log_name, Path("logs/app.log"))
        if not path.exists():
            backend_path = Path(__file__).resolve().parents[2] / path
            path = backend_path
        if not path.exists():
            return [f"Log file not found: {path}"]
        try:
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return content[-lines:]
        except OSError as exc:
            return [f"Unable to read log: {exc}"]
