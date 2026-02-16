"""Add analyzed/closed to incident status check constraint

Revision ID: 0009
Revises: 0008
Create Date: 2026-02-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("check_incident_status", "incidents", type_="check")
    op.create_check_constraint(
        "check_incident_status",
        "incidents",
        "status IN ('created', 'pending_review', 'in_review', 'analyzed', 'closed', 'resolved')",
    )


def downgrade() -> None:
    op.drop_constraint("check_incident_status", "incidents", type_="check")
    op.create_check_constraint(
        "check_incident_status",
        "incidents",
        "status IN ('created', 'pending_review', 'in_review', 'resolved')",
    )
