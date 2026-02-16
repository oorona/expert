"""Add experts, expert documents, and update prompts

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- experts ---
    op.create_table(
        "experts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text, server_default=sa.text("''")),
        sa.Column("file_search_store_name", sa.String(500)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # --- expert_documents ---
    op.create_table(
        "expert_documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "expert_id",
            sa.Integer,
            sa.ForeignKey("experts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("gemini_file_name", sa.String(500)),
        sa.Column("file_size", sa.Integer, server_default=sa.text("0")),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("idx_expert_documents_expert", "expert_documents", ["expert_id"])

    # --- update prompts: add expert_id and prompt_category ---
    op.add_column(
        "prompts",
        sa.Column(
            "expert_id",
            sa.Integer,
            sa.ForeignKey("experts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "prompts",
        sa.Column(
            "prompt_category",
            sa.String(20),
            server_default=sa.text("'grounded'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "check_prompt_category",
        "prompts",
        "prompt_category IN ('grounded', 'file_search')",
    )


def downgrade() -> None:
    op.drop_constraint("check_prompt_category", "prompts", type_="check")
    op.drop_column("prompts", "prompt_category")
    op.drop_column("prompts", "expert_id")
    op.drop_table("expert_documents")
    op.drop_table("experts")
