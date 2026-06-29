"""add_channel_connection_errors_v0_4

Revision ID: a1b2c3d4e5f6
Revises: 657650f1297c
Create Date: 2026-06-29 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "657650f1297c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "channel_connection_errors",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_channel_connection_errors_channel_id",
        "channel_connection_errors",
        ["channel_id"],
        unique=False,
    )
    op.create_index(
        "ix_channel_connection_errors_created_at",
        "channel_connection_errors",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_channel_connection_errors_telegram_id",
        "channel_connection_errors",
        ["telegram_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_channel_connection_errors_telegram_id",
        table_name="channel_connection_errors",
    )
    op.drop_index(
        "ix_channel_connection_errors_created_at",
        table_name="channel_connection_errors",
    )
    op.drop_index(
        "ix_channel_connection_errors_channel_id",
        table_name="channel_connection_errors",
    )
    op.drop_table("channel_connection_errors")
