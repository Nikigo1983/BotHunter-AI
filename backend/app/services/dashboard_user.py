import json
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.auth.passwords import hash_password
from app.models.audit_log import AuditLog
from app.models.dashboard_user import DashboardUser
from app.models.enums import DashboardRole
from app.repositories.deps import get_audit_log_repository, get_dashboard_user_repository
from app.services.dashboard_auth import DashboardAuthService


@dataclass(slots=True)
class DashboardUserUpsertResult:
    user: DashboardUser
    status: str
    role_changed: bool
    password_updated: bool


class DashboardUserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_repo = get_dashboard_user_repository(session)
        self._audit_repo = get_audit_log_repository(session)

    async def upsert_user(
        self,
        *,
        full_name: str,
        email: str,
        role: DashboardRole,
        password: str,
        actor: str = "system",
    ) -> DashboardUserUpsertResult:
        normalized_email = email.lower().strip()
        role_value = role.value if isinstance(role, DashboardRole) else str(role)
        existing = await self._user_repo.get_by_email(normalized_email)

        if existing is None:
            user = DashboardUser(
                email=normalized_email,
                password_hash=hash_password(password),
                full_name=full_name.strip(),
                role=role_value,
                is_active=True,
            )
            created = await self._user_repo.create(user)
            await self._write_audit(
                actor=actor,
                action="User created",
                user=created,
                details={"email": normalized_email, "full_name": full_name, "role": role_value},
            )
            await self._write_audit(
                actor=actor,
                action="Role assigned",
                user=created,
                details={"email": normalized_email, "role": role_value},
            )
            return DashboardUserUpsertResult(
                user=created,
                status="created",
                role_changed=True,
                password_updated=True,
            )

        role_changed = existing.role != role_value
        password_updated = bool(password)
        name_changed = existing.full_name != full_name.strip()
        previous_role = existing.role
        updated = role_changed or password_updated or name_changed

        if role_changed:
            existing.role = role_value
        if name_changed:
            existing.full_name = full_name.strip()
        if password_updated:
            existing.password_hash = hash_password(password)

        if updated:
            existing = await self._user_repo.update(existing)

        if role_changed:
            await self._write_audit(
                actor=actor,
                action="Role assigned",
                user=existing,
                details={
                    "email": normalized_email,
                    "role": role_value,
                    "previous_role": previous_role,
                },
            )

        return DashboardUserUpsertResult(
            user=existing,
            status="updated" if updated else "unchanged",
            role_changed=role_changed,
            password_updated=password_updated,
        )

    async def verify_login(self, email: str, password: str) -> bool:
        user = await DashboardAuthService(self._session).authenticate(email, password)
        return user is not None

    async def _write_audit(
        self,
        *,
        actor: str,
        action: str,
        user: DashboardUser,
        details: dict,
    ) -> None:
        await self._audit_repo.create(
            AuditLog(
                actor=actor,
                action=action,
                entity="dashboard_user",
                entity_id=user.id,
                details=json.dumps(details, ensure_ascii=False),
            )
        )
