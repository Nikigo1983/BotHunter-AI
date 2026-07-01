"""v2_1_policy_center

Revision ID: h8i9j0k2l3m4
Revises: g7h8i9j0k1l2
Create Date: 2026-06-30 22:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h8i9j0k2l3m4"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=320), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_number", name="uq_policy_versions_version_number"),
    )
    op.create_index("ix_policy_versions_is_current", "policy_versions", ["is_current"], unique=False)
    op.create_index("ix_policy_versions_created_at", "policy_versions", ["created_at"], unique=False)

    op.create_table(
        "policy_rule_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("rule_key", sa.String(length=128), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("admin_comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["version_id"], ["policy_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id", "rule_key", name="uq_policy_rule_configs_version_rule"),
    )
    op.create_index("ix_policy_rule_configs_rule_key", "policy_rule_configs", ["rule_key"], unique=False)

    op.create_table(
        "policy_threshold_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("approve_below", sa.Integer(), nullable=False),
        sa.Column("reject_from", sa.Integer(), nullable=False),
        sa.Column("trust_auto_approve", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("trust_auto_reject", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("ai_threshold", sa.Float(), nullable=False, server_default="0.75"),
        sa.ForeignKeyConstraint(["version_id"], ["policy_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version_id"),
    )


def downgrade() -> None:
    op.drop_table("policy_threshold_configs")
    op.drop_index("ix_policy_rule_configs_rule_key", table_name="policy_rule_configs")
    op.drop_table("policy_rule_configs")
    op.drop_index("ix_policy_versions_created_at", table_name="policy_versions")
    op.drop_index("ix_policy_versions_is_current", table_name="policy_versions")
    op.drop_table("policy_versions")
