import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.passwords import hash_password, verify_password
from app.admin.auth.permissions import has_permission, PERMISSION_CHANGE_AI_SETTINGS
from app.main import app
from app.models.enums import DashboardRole
from app.repositories.deps import get_dashboard_user_repository
from app.services.dashboard_auth import DashboardAuthService
from app.services.runtime_settings import RuntimeSettingsService
from app.services.secrets_service import mask_secret


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_role_permissions() -> None:
    assert has_permission(DashboardRole.OWNER.value, PERMISSION_CHANGE_AI_SETTINGS)
    assert has_permission(DashboardRole.ADMINISTRATOR.value, PERMISSION_CHANGE_AI_SETTINGS)
    assert not has_permission(DashboardRole.MODERATOR.value, PERMISSION_CHANGE_AI_SETTINGS)
    assert not has_permission(DashboardRole.VIEWER.value, PERMISSION_CHANGE_AI_SETTINGS)


def test_mask_secret() -> None:
    assert mask_secret("sk-abcdefghijklmnop").endswith("mnop")
    assert mask_secret("") == "—"


@pytest.mark.asyncio
async def test_login_and_protected_admin_redirect(session: AsyncSession, dashboard_owner) -> None:
    from app.database.session import get_db_session

    async def override_get_db_session():
        yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=False) as client:
        protected = await client.get("/admin")
        assert protected.status_code == 303
        assert "/admin/login" in protected.headers["location"]

        login = await client.post(
            "/admin/login",
            data={"email": "admin@test.local", "password": "testpass", "next": "/admin/system"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        assert login.headers["location"] == "/admin/system"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_system_page_requires_auth_and_loads(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/admin/system")
    assert response.status_code == 200
    assert "Production Ready" in response.text
    assert "Health Monitor" in response.text


@pytest.mark.asyncio
async def test_runtime_settings_update(session: AsyncSession, dashboard_owner) -> None:
    service = RuntimeSettingsService(session)
    updated = await service.update_settings(
        {"ai_provider": "mock", "ai_timeout": "15", "ai_max_retries": "1"},
        updated_by=dashboard_owner.email,
    )
    assert updated.ai_provider == "mock"
    assert updated.ai_timeout == 15.0
    assert updated.ai_max_retries == 1


@pytest.mark.asyncio
async def test_settings_page_save(admin_client: AsyncClient, admin_csrf: str) -> None:
    response = await admin_client.post(
        "/admin/settings",
        data={
            "csrf_token": admin_csrf,
            "ai_provider": "mock",
            "openrouter_model": "openai/gpt-4.1",
            "openai_model": "gpt-4o-mini",
            "ai_timeout": "20",
            "ai_max_retries": "3",
            "decision_approve_below": "30",
            "decision_reject_from": "70",
            "monthly_budget_usd": "150",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "saved=1" in response.headers["location"]
