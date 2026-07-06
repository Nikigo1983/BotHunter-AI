from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant.resolver import TenantResolver

CACHE_PREFIX = "bothunter:dashboard:workspaces:"
CACHE_TTL_SECONDS = 300


@dataclass(slots=True)
class CachedOrganization:
    id: uuid.UUID
    name: str
    display_name: str | None


@dataclass(slots=True)
class CachedWorkspace:
    id: uuid.UUID
    name: str
    organization_id: uuid.UUID


class DashboardWorkspaceCache:
    @staticmethod
    async def get_workspaces(
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        redis: Redis | None = None,
    ) -> list[tuple[CachedOrganization, CachedWorkspace]]:
        if redis is not None:
            cached = await redis.get(f"{CACHE_PREFIX}{user_id}")
            if cached:
                return _deserialize(cached)

        rows = await TenantResolver(session).list_accessible_workspaces(user_id)
        entries = [
            (
                CachedOrganization(
                    id=org.id,
                    name=org.name,
                    display_name=org.display_name,
                ),
                CachedWorkspace(
                    id=workspace.id,
                    name=workspace.name,
                    organization_id=org.id,
                ),
            )
            for org, workspace in rows
        ]
        if redis is not None and entries:
            await redis.setex(
                f"{CACHE_PREFIX}{user_id}",
                CACHE_TTL_SECONDS,
                _serialize(entries),
            )
        return entries

    @staticmethod
    async def invalidate(redis: Redis | None, user_id: uuid.UUID) -> None:
        if redis is None:
            return
        await redis.delete(f"{CACHE_PREFIX}{user_id}")


def _serialize(entries: list[tuple[CachedOrganization, CachedWorkspace]]) -> str:
    payload = [
        {
            "organization_id": str(org.id),
            "organization_name": org.name,
            "organization_display_name": org.display_name,
            "workspace_id": str(workspace.id),
            "workspace_name": workspace.name,
        }
        for org, workspace in entries
    ]
    return json.dumps(payload)


def _deserialize(raw: str) -> list[tuple[CachedOrganization, CachedWorkspace]]:
    return [
        (
            CachedOrganization(
                id=uuid.UUID(item["organization_id"]),
                name=item["organization_name"],
                display_name=item.get("organization_display_name"),
            ),
            CachedWorkspace(
                id=uuid.UUID(item["workspace_id"]),
                name=item["workspace_name"],
                organization_id=uuid.UUID(item["organization_id"]),
            ),
        )
        for item in json.loads(raw)
    ]
