from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.passwords import (
    generate_csrf_token,
    generate_session_token,
    hash_session_token,
    verify_password,
)
from app.config import Settings, get_settings
from app.models.dashboard_session import DashboardSession
from app.models.dashboard_user import DashboardUser
from app.models.enums import DashboardRole
from app.repositories.deps import (
    get_dashboard_session_repository,
    get_dashboard_user_repository,
)

SESSION_COOKIE_NAME = "bothunter_session"


@dataclass(slots=True)
class DashboardAuthContext:
    user: DashboardUser
    session: DashboardSession
    csrf_token: str


class DashboardAuthService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._user_repo = get_dashboard_user_repository(session)
        self._session_repo = get_dashboard_session_repository(session)

    async def ensure_default_owner(self) -> None:
        count = await self.count_users()
        if count > 0:
            return
        from app.admin.auth.passwords import hash_password

        owner = DashboardUser(
            email=self._settings.dashboard_admin_email.lower().strip(),
            password_hash=hash_password(self._settings.dashboard_admin_password),
            full_name="System Owner",
            role=DashboardRole.OWNER.value,
            is_active=True,
        )
        await self._user_repo.create(owner)

    async def count_users(self) -> int:
        return await self._user_repo.count_all()

    async def authenticate(self, email: str, password: str) -> DashboardUser | None:
        user = await self._user_repo.get_by_email(email)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        user.last_login_at = datetime.now(UTC)
        await self._user_repo.update(user)
        return user

    async def create_session(
        self,
        user: DashboardUser,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, DashboardSession]:
        token = generate_session_token()
        csrf_token = generate_csrf_token()
        expires_at = datetime.now(UTC) + timedelta(hours=self._settings.dashboard_session_max_age_hours)
        session_entity = DashboardSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            csrf_token=csrf_token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._session_repo.create(session_entity)
        return token, session_entity

    async def destroy_session(self, token: str) -> None:
        await self._session_repo.delete_by_token_hash(hash_session_token(token))

    async def resolve_session(self, token: str | None) -> DashboardAuthContext | None:
        if not token:
            return None
        session_entity = await self._session_repo.get_by_token_hash(hash_session_token(token))
        if session_entity is None:
            return None
        if session_entity.expires_at < datetime.now(UTC):
            await self._session_repo.delete_by_token_hash(session_entity.token_hash)
            return None
        user = await self._user_repo.get_by_id(session_entity.user_id)
        if user is None or not user.is_active:
            return None
        return DashboardAuthContext(user=user, session=session_entity, csrf_token=session_entity.csrf_token)

    def set_session_cookie(self, response, token: str) -> None:
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            secure=self._settings.dashboard_cookie_secure,
            samesite="lax",
            max_age=self._settings.dashboard_session_max_age_hours * 3600,
            path="/",
        )

    def clear_session_cookie(self, response) -> None:
        response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def get_session_token_from_request(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE_NAME)
