"""v3_0_phase2_org_management

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-06-30 23:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("favicon_url", sa.String(length=512), nullable=True))
    op.add_column("organization_invites", sa.Column("workspace_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_organization_invites_workspace_id",
        "organization_invites",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_organization_invites_workspace_id",
        "organization_invites",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_organization_invites_workspace_id", table_name="organization_invites")
    op.drop_constraint("fk_organization_invites_workspace_id", "organization_invites", type_="foreignkey")
    op.drop_column("organization_invites", "workspace_id")
    op.drop_column("organizations", "favicon_url")
