from datetime import UTC, datetime, timedelta
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_usage import AIUsage
from app.repositories.base import BaseRepository


class AIUsageRepository(BaseRepository[AIUsage]):
    def __init__(
        self,
        session: AsyncSession,
        *,
        organization_id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(session, AIUsage)
        self._organization_id = organization_id

    def _scoped(self, stmt):
        if self._organization_id is not None:
            stmt = stmt.where(AIUsage.organization_id == self._organization_id)
        return stmt

    async def get_statistics(self, *, days: int = 30) -> dict:
        total_requests = int(
            (
                await self._session.execute(
                    self._scoped(select(func.count()).select_from(AIUsage))
                )
            ).scalar_one()
        )
        totals = (
            await self._session.execute(
                self._scoped(
                    select(
                        func.coalesce(func.sum(AIUsage.total_tokens), 0),
                        func.coalesce(func.sum(AIUsage.estimated_cost), 0.0),
                        func.coalesce(func.avg(AIUsage.latency_ms), 0.0),
                    )
                )
            )
        ).one()
        total_tokens, total_cost, avg_latency = totals

        top_models_stmt = (
            self._scoped(
                select(
                    AIUsage.model,
                    func.count().label("requests"),
                    func.sum(AIUsage.total_tokens).label("tokens"),
                )
            )
            .group_by(AIUsage.model)
            .order_by(func.count().desc())
            .limit(5)
        )
        top_models = [
            {"model": row.model, "requests": int(row.requests), "tokens": int(row.tokens or 0)}
            for row in (await self._session.execute(top_models_stmt)).all()
        ]

        since = datetime.now(UTC) - timedelta(days=days)
        daily_stmt = (
            self._scoped(
                select(
                    func.date_trunc("day", AIUsage.created_at).label("day"),
                    func.count().label("requests"),
                    func.sum(AIUsage.total_tokens).label("tokens"),
                    func.sum(AIUsage.estimated_cost).label("cost"),
                )
            )
            .where(AIUsage.created_at >= since)
            .group_by("day")
            .order_by("day")
        )
        daily_stats = [
            {
                "date": row.day.date().isoformat() if row.day else "",
                "requests": int(row.requests),
                "tokens": int(row.tokens or 0),
                "cost": float(row.cost or 0.0),
            }
            for row in (await self._session.execute(daily_stmt)).all()
        ]

        return {
            "total_requests": total_requests,
            "total_tokens": int(total_tokens or 0),
            "total_cost": round(float(total_cost or 0.0), 6),
            "avg_latency_ms": round(float(avg_latency or 0.0), 2),
            "top_models": top_models,
            "daily_stats": daily_stats,
        }
