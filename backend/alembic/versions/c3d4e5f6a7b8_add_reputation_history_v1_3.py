"""add_reputation_history_v1_3

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-30 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

reputation_reason_enum = postgresql.ENUM(
    "APPROVED",
    "REJECTED",
    "WHITELISTED",
    "BLACKLISTED",
    "MANUAL_APPROVED",
    "MANUAL_REJECTED",
    name="reputation_change_reason",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE reputation_change_reason AS ENUM (
                'APPROVED', 'REJECTED', 'WHITELISTED', 'BLACKLISTED',
                'MANUAL_APPROVED', 'MANUAL_REJECTED'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "reputation_history",
        sa.Column("telegram_user_id", sa.UUID(), nullable=False),
        sa.Column("old_score", sa.Float(), nullable=False),
        sa.Column("new_score", sa.Float(), nullable=False),
        sa.Column("reason", reputation_reason_enum, nullable=False),
        sa.Column("actor", sa.String(length=255), nullable=False, server_default="system"),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["telegram_user_id"], ["telegram_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reputation_history_telegram_user_id",
        "reputation_history",
        ["telegram_user_id"],
    )
    op.create_index("ix_reputation_history_reason", "reputation_history", ["reason"])
    op.create_index("ix_reputation_history_created_at", "reputation_history", ["created_at"])

    op.alter_column(
        "reputations",
        "reputation_score",
        server_default="50",
        existing_type=sa.Float(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "reputations",
        "reputation_score",
        server_default="0",
        existing_type=sa.Float(),
        existing_nullable=False,
    )

    op.drop_index("ix_reputation_history_created_at", table_name="reputation_history")
    op.drop_index("ix_reputation_history_reason", table_name="reputation_history")
    op.drop_index("ix_reputation_history_telegram_user_id", table_name="reputation_history")
    op.drop_table("reputation_history")

    op.execute("DROP TYPE IF EXISTS reputation_change_reason")
