"""add_channel_settings_v1_8

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-30 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("telegram_channels", sa.Column("username", sa.String(length=255), nullable=True))

    op.create_table(
        "channel_settings",
        sa.Column("channel_id", sa.UUID(), nullable=False),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("rule_auto_approve", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("rule_auto_reject", sa.Integer(), nullable=False, server_default="70"),
        sa.Column("trust_auto_approve", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("trust_auto_reject", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("join_request_timeout_hours", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["telegram_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", name="uq_channel_settings_channel_id"),
    )
    op.create_index("ix_channel_settings_channel_id", "channel_settings", ["channel_id"])


def downgrade() -> None:
    op.drop_index("ix_channel_settings_channel_id", table_name="channel_settings")
    op.drop_table("channel_settings")
    op.drop_column("telegram_channels", "username")
