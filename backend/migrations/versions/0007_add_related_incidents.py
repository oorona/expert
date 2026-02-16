"""Add related_incidents table for article linking

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "related_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "incident_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "related_id",
            sa.Integer(),
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relation_type",
            sa.String(30),
            server_default="'followup'",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_related_pair",
        "related_incidents",
        ["incident_id", "related_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_related_pair", table_name="related_incidents")
    op.drop_table("related_incidents")
