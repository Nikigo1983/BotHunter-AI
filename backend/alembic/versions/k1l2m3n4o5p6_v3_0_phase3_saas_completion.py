"""v3_0_phase3_saas_completion

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-06-30 23:59:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "organizations",
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "workspaces",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_organizations_is_archived", "organizations", ["is_archived"], unique=False)
    op.create_index("ix_workspaces_is_archived", "workspaces", ["is_archived"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_workspaces_is_archived", table_name="workspaces")
    op.drop_index("ix_organizations_is_archived", table_name="organizations")
    op.drop_column("workspaces", "is_archived")
    op.drop_column("organizations", "onboarding_completed")
    op.drop_column("organizations", "is_archived")
