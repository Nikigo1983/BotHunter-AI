"""add_manual_review_ai_feedback_v1_2

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-30 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

admin_action_type = postgresql.ENUM(
    "APPROVE",
    "REJECT",
    "WHITELIST",
    "BLACKLIST",
    name="admin_action",
    create_type=False,
)

analysis_decision_type = postgresql.ENUM(
    "Approved",
    "Rejected",
    "ManualReview",
    name="analysis_decision",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE admin_action AS ENUM (
                'APPROVE', 'REJECT', 'WHITELIST', 'BLACKLIST'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "manual_reviews",
        sa.Column("join_request_id", sa.UUID(), nullable=False),
        sa.Column("telegram_user_id", sa.UUID(), nullable=False),
        sa.Column("admin_action", admin_action_type, nullable=False),
        sa.Column("previous_decision", analysis_decision_type, nullable=False),
        sa.Column("final_decision", analysis_decision_type, nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["join_request_id"], ["join_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["telegram_user_id"], ["telegram_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_manual_reviews_join_request_id", "manual_reviews", ["join_request_id"])
    op.create_index("ix_manual_reviews_telegram_user_id", "manual_reviews", ["telegram_user_id"])
    op.create_index("ix_manual_reviews_admin_action", "manual_reviews", ["admin_action"])
    op.create_index("ix_manual_reviews_created_at", "manual_reviews", ["created_at"])

    op.create_table(
        "ai_feedbacks",
        sa.Column("join_request_id", sa.UUID(), nullable=False),
        sa.Column("rule_score", sa.Float(), nullable=True),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("ai_decision", analysis_decision_type, nullable=False),
        sa.Column("human_decision", analysis_decision_type, nullable=False),
        sa.Column("was_ai_correct", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["join_request_id"], ["join_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_feedbacks_join_request_id", "ai_feedbacks", ["join_request_id"])
    op.create_index("ix_ai_feedbacks_was_ai_correct", "ai_feedbacks", ["was_ai_correct"])
    op.create_index("ix_ai_feedbacks_created_at", "ai_feedbacks", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_feedbacks_created_at", table_name="ai_feedbacks")
    op.drop_index("ix_ai_feedbacks_was_ai_correct", table_name="ai_feedbacks")
    op.drop_index("ix_ai_feedbacks_join_request_id", table_name="ai_feedbacks")
    op.drop_table("ai_feedbacks")

    op.drop_index("ix_manual_reviews_created_at", table_name="manual_reviews")
    op.drop_index("ix_manual_reviews_admin_action", table_name="manual_reviews")
    op.drop_index("ix_manual_reviews_telegram_user_id", table_name="manual_reviews")
    op.drop_index("ix_manual_reviews_join_request_id", table_name="manual_reviews")
    op.drop_table("manual_reviews")

    op.execute("DROP TYPE IF EXISTS admin_action")
