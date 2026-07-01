import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.runtime_settings import RuntimeSettingsService


@dataclass(slots=True)
class BackupResult:
    filename: str
    content: bytes
    content_type: str


class BackupService:
    BACKUP_TABLES = (
        "dashboard_users",
        "system_settings",
        "users",
        "telegram_bots",
        "telegram_channels",
        "channel_settings",
        "join_requests",
        "ai_analyses",
        "ai_usage",
        "audit_logs",
        "reputations",
        "reputation_history",
    )

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def export_json(self) -> BackupResult:
        payload: dict[str, list[dict]] = {}
        for table in self.BACKUP_TABLES:
            payload[table] = await self._dump_table(table)
        content = json.dumps(
            {"exported_at": datetime.now(UTC).isoformat(), "tables": payload},
            ensure_ascii=False,
            indent=2,
            default=str,
        ).encode("utf-8")
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return BackupResult(
            filename=f"bothunter_backup_{stamp}.json",
            content=content,
            content_type="application/json",
        )

    async def export_sql(self) -> BackupResult:
        lines = [
            "-- BotHunter AI database backup",
            f"-- Generated at {datetime.now(UTC).isoformat()}",
            "",
        ]
        for table in self.BACKUP_TABLES:
            rows = await self._dump_table(table)
            if not rows:
                continue
            columns = list(rows[0].keys())
            for row in rows:
                values = ", ".join(self._sql_literal(row[col]) for col in columns)
                col_list = ", ".join(columns)
                lines.append(f"INSERT INTO {table} ({col_list}) VALUES ({values});")
            lines.append("")
        content = "\n".join(lines).encode("utf-8")
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return BackupResult(
            filename=f"bothunter_backup_{stamp}.sql",
            content=content,
            content_type="application/sql",
        )

    async def export_csv_bundle(self) -> BackupResult:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["table", "row_json"])
        for table in self.BACKUP_TABLES:
            for row in await self._dump_table(table):
                writer.writerow([table, json.dumps(row, ensure_ascii=False, default=str)])
        content = buffer.getvalue().encode("utf-8")
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return BackupResult(
            filename=f"bothunter_backup_{stamp}.csv",
            content=content,
            content_type="text/csv",
        )

    async def import_json(self, raw: bytes) -> int:
        payload = json.loads(raw.decode("utf-8"))
        tables = payload.get("tables", payload)
        imported = 0
        for table_name, rows in tables.items():
            if table_name not in self.BACKUP_TABLES or not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                columns = list(row.keys())
                placeholders = ", ".join(f":{col}" for col in columns)
                col_list = ", ".join(columns)
                stmt = text(
                    f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
                )
                await self._session.execute(stmt, row)
                imported += 1
        await RuntimeSettingsService(self._session).update_settings(
            {"backup_configured": "true"},
            updated_by="restore",
        )
        return imported

    async def mark_backup_configured(self, *, updated_by: str) -> None:
        await RuntimeSettingsService(self._session).update_settings(
            {"backup_configured": "true"},
            updated_by=updated_by,
        )

    async def _dump_table(self, table_name: str) -> list[dict]:
        try:
            result = await self._session.execute(text(f"SELECT * FROM {table_name}"))
            return [dict(row._mapping) for row in result]
        except Exception:
            return []

    @staticmethod
    def _sql_literal(value: object) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"
