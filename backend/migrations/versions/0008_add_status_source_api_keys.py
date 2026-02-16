"""Add source/status to incidents and api_keys table

Revision ID: 0008
Revises: 0007
Create Date: 2026-02-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Incident columns ---
    op.add_column(
        "incidents",
        sa.Column("source", sa.String(20), server_default="'manual'", nullable=False),
    )
    op.add_column(
        "incidents",
        sa.Column("status", sa.String(30), server_default="'created'", nullable=False),
    )
    op.create_check_constraint(
        "check_incident_source",
        "incidents",
        "source IN ('manual', 'api')",
    )
    op.create_check_constraint(
        "check_incident_status",
        "incidents",
        "status IN ('created', 'pending_review', 'in_review', 'resolved')",
    )
    op.create_index(
        "idx_incidents_source_status",
        "incidents",
        ["source", "status"],
    )

    # Set existing incidents to resolved (they were manually created before this feature)
    op.execute("UPDATE incidents SET status = 'resolved' WHERE source = 'manual'")

    # --- API Keys table ---
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key_hash", sa.String(128), unique=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), server_default="''"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_api_keys_hash", "api_keys", ["key_hash"])


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_index("idx_incidents_source_status", table_name="incidents")
    op.drop_constraint("check_incident_status", "incidents", type_="check")
    op.drop_constraint("check_incident_source", "incidents", type_="check")
    op.drop_column("incidents", "status")
    op.drop_column("incidents", "source")
