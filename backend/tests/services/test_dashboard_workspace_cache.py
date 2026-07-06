import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.dashboard_workspace_cache import (
    CACHE_PREFIX,
    DashboardWorkspaceCache,
)


@pytest.mark.asyncio
async def test_workspace_cache_reads_from_redis() -> None:
    org_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()
    payload = json.dumps(
        [
            {
                "organization_id": str(org_id),
                "organization_name": "Default Organization",
                "organization_display_name": "Default Organization",
                "workspace_id": str(workspace_id),
                "workspace_name": "Default Workspace",
            }
        ]
    )
    redis = AsyncMock()
    redis.get.return_value = payload
    session = MagicMock()

    entries = await DashboardWorkspaceCache.get_workspaces(session, user_id, redis=redis)

    assert len(entries) == 1
    org, workspace = entries[0]
    assert org.id == org_id
    assert workspace.id == workspace_id
    redis.get.assert_awaited_once_with(f"{CACHE_PREFIX}{user_id}")


@pytest.mark.asyncio
async def test_workspace_cache_invalidates_user_entries() -> None:
    user_id = uuid.uuid4()
    redis = AsyncMock()

    await DashboardWorkspaceCache.invalidate(redis, user_id)

    redis.delete.assert_awaited_once_with(f"{CACHE_PREFIX}{user_id}")
