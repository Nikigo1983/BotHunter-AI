import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DashboardRole
from app.repositories.deps import get_audit_log_repository, get_dashboard_user_repository
from app.services.dashboard_user import DashboardUserService


@pytest.mark.asyncio
async def test_upsert_creates_user_with_audit(session: AsyncSession) -> None:
    service = DashboardUserService(session)
    email = f"created-{uuid.uuid4().hex[:8]}@example.com"
    result = await service.upsert_user(
        full_name="Veronika",
        email=email,
        role=DashboardRole.OWNER,
        password="SecretPass123!",
        actor="test",
    )
    assert result.status == "created"
    assert result.user.role == DashboardRole.OWNER.value

    audit_repo = get_audit_log_repository(session)
    logs = await audit_repo.list_by_entity(entity="dashboard_user", entity_id=result.user.id)
    actions = {log.action for log in logs}
    assert "User created" in actions
    assert "Role assigned" in actions

    assert await service.verify_login(email, "SecretPass123!")


@pytest.mark.asyncio
async def test_upsert_no_duplicate_updates_role(session: AsyncSession) -> None:
    service = DashboardUserService(session)
    await service.upsert_user(
        full_name="Julia",
        email="iuliia.zhdanovich@gmail.com",
        role=DashboardRole.MODERATOR,
        password="PassOne123!",
        actor="test",
    )
    result = await service.upsert_user(
        full_name="Julia",
        email="iuliia.zhdanovich@gmail.com",
        role=DashboardRole.ADMINISTRATOR,
        password="PassTwo456!",
        actor="test",
    )
    assert result.status == "updated"
    assert result.role_changed is True
    assert result.user.role == DashboardRole.ADMINISTRATOR.value

    repo = get_dashboard_user_repository(session)
    users = await repo.get_all(limit=100)
    emails = [user.email for user in users if user.email == "iuliia.zhdanovich@gmail.com"]
    assert len(emails) == 1

    assert await service.verify_login("iuliia.zhdanovich@gmail.com", "PassTwo456!")
    assert not await service.verify_login("iuliia.zhdanovich@gmail.com", "PassOne123!")
