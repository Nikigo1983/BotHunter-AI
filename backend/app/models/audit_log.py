import uuid

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.mixins import CreatedAtMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor", "actor"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_entity", "entity"),
        Index("ix_audit_logs_entity_id", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_entity_entity_id", "entity", "entity_id"),
    )

    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    entity: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
