"""Seed Dashboard users from environment variables and print a report."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.session import async_session_factory
from app.models.enums import DashboardRole
from app.services.dashboard_user import DashboardUserService

SEED_USERS = (
    {
        "full_name": "Veronika",
        "email": "virineya1983@gmail.com",
        "role": DashboardRole.OWNER,
        "password_env": "DASHBOARD_USER_VERONIKA_PASSWORD",
    },
    {
        "full_name": "Zlata",
        "email": "gujenova220371@gmail.com",
        "role": DashboardRole.ADMINISTRATOR,
        "password_env": "DASHBOARD_USER_ZLATA_PASSWORD",
    },
    {
        "full_name": "Julia",
        "email": "iuliia.zhdanovich@gmail.com",
        "role": DashboardRole.MODERATOR,
        "password_env": "DASHBOARD_USER_JULIA_PASSWORD",
    },
)


def _load_passwords() -> dict[str, str]:
    missing: list[str] = []
    passwords: dict[str, str] = {}
    for item in SEED_USERS:
        value = os.getenv(item["password_env"], "").strip()
        if not value:
            missing.append(item["password_env"])
        else:
            passwords[item["email"]] = value
    if missing:
        print("ERROR: missing password environment variables:")
        for name in missing:
            print(f"  - {name}")
        print("\nAdd them to .env and rerun:")
        print("  docker exec bothunter-api python scripts/seed_dashboard_users.py")
        raise SystemExit(1)
    return passwords


async def main() -> int:
    passwords = _load_passwords()
    report_rows: list[dict] = []
    login_checks: list[dict] = []

    async with async_session_factory() as session:
        service = DashboardUserService(session)
        for item in SEED_USERS:
            result = await service.upsert_user(
                full_name=item["full_name"],
                email=item["email"],
                role=item["role"],
                password=passwords[item["email"]],
                actor="dashboard_seed_script",
            )
            can_login = await service.verify_login(item["email"], passwords[item["email"]])
            report_rows.append(
                {
                    "full_name": result.user.full_name,
                    "email": result.user.email,
                    "role": result.user.role,
                    "status": result.status,
                }
            )
            login_checks.append(
                {
                    "email": result.user.email,
                    "role": result.user.role,
                    "login_ok": can_login,
                }
            )
        await session.commit()

    print("\n=== Dashboard Users Report ===\n")
    print(f"{'Name':<12} {'Email':<32} {'Role':<16} {'Status':<10}")
    print("-" * 74)
    for row in report_rows:
        print(
            f"{row['full_name']:<12} {row['email']:<32} {row['role']:<16} {row['status']:<10}"
        )

    print("\n=== Login Verification ===\n")
    all_ok = True
    for check in login_checks:
        mark = "OK" if check["login_ok"] else "FAILED"
        print(f"{check['email']:<32} role={check['role']:<16} login={mark}")
        all_ok = all_ok and check["login_ok"]

    if not all_ok:
        print("\nSome login checks failed.")
        return 1

    print("\nAll users can log in successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
