"""v3_0_multi_tenant

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k2l3m4
Create Date: 2026-06-30 23:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k2l3m4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("plan", sa.String(length=32), nullable=False, server_default="free"),
        sa.Column("logo_url", sa.String(length=512), nullable=True),
        sa.Column("brand_color", sa.String(length=32), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=False)
    op.create_index("ix_organizations_plan", "organizations", ["plan"], unique=False)

    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_workspaces_org_slug"),
    )
    op.create_index("ix_workspaces_organization_id", "workspaces", ["organization_id"], unique=False)

    op.create_table(
        "organization_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["dashboard_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_members_org_user"),
    )
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"], unique=False)
    op.create_index(
        "ix_organization_members_organization_id",
        "organization_members",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "workspace_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["dashboard_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_ws_user"),
    )
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"], unique=False)
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"], unique=False)

    op.create_table(
        "organization_invites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("invited_by", sa.String(length=320), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_organization_invites_token"),
    )
    op.create_index("ix_organization_invites_organization_id", "organization_invites", ["organization_id"])
    op.create_index("ix_organization_invites_email", "organization_invites", ["email"])

    op.create_table(
        "organization_secrets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("secret_type", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_by", sa.String(length=320), nullable=True),
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "secret_type", name="uq_org_secrets_org_type"),
    )
    op.create_index("ix_organization_secrets_organization_id", "organization_secrets", ["organization_id"])

    op.create_table(
        "organization_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("int_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("float_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "metric",
            "period_start",
            name="uq_organization_usage_org_metric_period",
        ),
    )
    op.create_index("ix_organization_usage_organization_id", "organization_usage", ["organization_id"])

    op.add_column("dashboard_sessions", sa.Column("active_organization_id", sa.Uuid(), nullable=True))
    op.add_column("dashboard_sessions", sa.Column("active_workspace_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_dashboard_sessions_active_organization_id",
        "dashboard_sessions",
        "organizations",
        ["active_organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_dashboard_sessions_active_workspace_id",
        "dashboard_sessions",
        "workspaces",
        ["active_workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("telegram_channels", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.add_column("telegram_channels", sa.Column("workspace_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_telegram_channels_organization_id",
        "telegram_channels",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_telegram_channels_workspace_id",
        "telegram_channels",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_telegram_channels_organization_id", "telegram_channels", ["organization_id"])
    op.create_index("ix_telegram_channels_workspace_id", "telegram_channels", ["workspace_id"])

    op.add_column("policy_versions", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_policy_versions_organization_id",
        "policy_versions",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_policy_versions_organization_id", "policy_versions", ["organization_id"])
    op.drop_constraint("uq_policy_versions_version_number", "policy_versions", type_="unique")
    op.create_unique_constraint(
        "uq_policy_versions_org_version",
        "policy_versions",
        ["organization_id", "version_number"],
    )

    op.add_column("audit_logs", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.add_column("audit_logs", sa.Column("workspace_id", sa.Uuid(), nullable=True))
    op.add_column("audit_logs", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])

    op.add_column("ai_usage", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_ai_usage_organization_id",
        "ai_usage",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_ai_usage_organization_id", "ai_usage", ["organization_id"])

    op.add_column("system_settings", sa.Column("organization_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_system_settings_organization_id",
        "system_settings",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_system_settings_organization_id", "system_settings", ["organization_id"])
    op.drop_index("ix_system_settings_key", table_name="system_settings")
    op.create_unique_constraint(
        "uq_system_settings_org_key",
        "system_settings",
        ["organization_id", "key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_system_settings_org_key", "system_settings", type_="unique")
    op.create_index("ix_system_settings_key", "system_settings", ["key"], unique=True)
    op.drop_constraint("fk_system_settings_organization_id", "system_settings", type_="foreignkey")
    op.drop_index("ix_system_settings_organization_id", table_name="system_settings")
    op.drop_column("system_settings", "organization_id")

    op.drop_constraint("fk_ai_usage_organization_id", "ai_usage", type_="foreignkey")
    op.drop_index("ix_ai_usage_organization_id", table_name="ai_usage")
    op.drop_column("ai_usage", "organization_id")

    op.drop_index("ix_audit_logs_organization_id", table_name="audit_logs")
    op.drop_column("audit_logs", "user_id")
    op.drop_column("audit_logs", "workspace_id")
    op.drop_column("audit_logs", "organization_id")

    op.drop_constraint("uq_policy_versions_org_version", "policy_versions", type_="unique")
    op.create_unique_constraint("uq_policy_versions_version_number", "policy_versions", ["version_number"])
    op.drop_index("ix_policy_versions_organization_id", table_name="policy_versions")
    op.drop_constraint("fk_policy_versions_organization_id", "policy_versions", type_="foreignkey")
    op.drop_column("policy_versions", "organization_id")

    op.drop_index("ix_telegram_channels_workspace_id", table_name="telegram_channels")
    op.drop_index("ix_telegram_channels_organization_id", table_name="telegram_channels")
    op.drop_constraint("fk_telegram_channels_workspace_id", "telegram_channels", type_="foreignkey")
    op.drop_constraint("fk_telegram_channels_organization_id", "telegram_channels", type_="foreignkey")
    op.drop_column("telegram_channels", "workspace_id")
    op.drop_column("telegram_channels", "organization_id")

    op.drop_constraint("fk_dashboard_sessions_active_workspace_id", "dashboard_sessions", type_="foreignkey")
    op.drop_constraint("fk_dashboard_sessions_active_organization_id", "dashboard_sessions", type_="foreignkey")
    op.drop_column("dashboard_sessions", "active_workspace_id")
    op.drop_column("dashboard_sessions", "active_organization_id")

    op.drop_table("organization_usage")
    op.drop_table("organization_secrets")
    op.drop_table("organization_invites")
    op.drop_table("workspace_members")
    op.drop_table("organization_members")
    op.drop_table("workspaces")
    op.drop_table("organizations")
