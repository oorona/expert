"""Add BM25 index on incidents notes column

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-13
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Set notes to empty string where NULL so BM25 can index it
    op.execute("UPDATE incidents SET notes = '' WHERE notes IS NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_incidents_notes_bm25 "
        "ON incidents USING bm25 (notes) WITH (text_config='english')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_incidents_notes_bm25")
