"""Add llm_events and llm_calls tables for LLM observability logging.

Revision ID: 0012
Revises: 0011
Create Date: 2026-02-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- llm_events ---
    op.create_table(
        "llm_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.Integer, nullable=True),
        sa.Column("session_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("metadata", JSONB, nullable=False, server_default="'{}'"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("idx_llm_events_type", "llm_events", ["event_type"])
    op.create_index("idx_llm_events_status", "llm_events", ["status"])
    op.create_index("idx_llm_events_created", "llm_events", ["created_at"])
    op.create_index("idx_llm_events_entity", "llm_events", ["entity_type", "entity_id"])

    # --- llm_calls ---
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "event_id",
            sa.Integer,
            sa.ForeignKey("llm_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("call_index", sa.Integer, nullable=False, server_default="0"),
        sa.Column("call_type", sa.String(20), nullable=False, server_default="'text'"),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("temperature", sa.Float, nullable=True),
        sa.Column("thinking_level", sa.String(20), nullable=True),
        sa.Column("extra_params", JSONB, nullable=False, server_default="'{}'"),
        sa.Column("prompt_name", sa.String(200), nullable=True),
        sa.Column("prompt_text", sa.Text, nullable=True),
        sa.Column("response_text", sa.Text, nullable=True),
        sa.Column("is_streaming", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_image_call", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("image_data", sa.Text, nullable=True),
        sa.Column("image_prompt", sa.Text, nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cache_write_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("thinking_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("time_to_first_token_ms", sa.Integer, nullable=True),
        sa.Column("total_duration_ms", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="'success'"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("idx_llm_calls_event", "llm_calls", ["event_id"])
    op.create_index("idx_llm_calls_model", "llm_calls", ["model"])
    op.create_index("idx_llm_calls_created", "llm_calls", ["created_at"])
    op.create_index("idx_llm_calls_type", "llm_calls", ["call_type"])

    # --- BM25 indexes for full-text search ---
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_calls_prompt_bm25 "
        "ON llm_calls USING bm25(prompt_text) WITH (text_config='english')"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_calls_response_bm25 "
        "ON llm_calls USING bm25(response_text) WITH (text_config='english')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_llm_calls_response_bm25")
    op.execute("DROP INDEX IF EXISTS idx_llm_calls_prompt_bm25")
    op.drop_index("idx_llm_calls_type", table_name="llm_calls")
    op.drop_index("idx_llm_calls_created", table_name="llm_calls")
    op.drop_index("idx_llm_calls_model", table_name="llm_calls")
    op.drop_index("idx_llm_calls_event", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_index("idx_llm_events_entity", table_name="llm_events")
    op.drop_index("idx_llm_events_created", table_name="llm_events")
    op.drop_index("idx_llm_events_status", table_name="llm_events")
    op.drop_index("idx_llm_events_type", table_name="llm_events")
    op.drop_table("llm_events")
