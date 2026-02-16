"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Extensions ---
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_textsearch")

    # --- incidents ---
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("error_text", sa.Text),
        sa.Column("image_data", sa.LargeBinary),
        sa.Column("image_mime_type", sa.String(50)),
        sa.Column("raw_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("markdown_content", sa.Text, nullable=False, server_default=sa.text("''")),
        sa.Column("embedding", Vector(768)),
        sa.Column("model_used", sa.String(100)),
        sa.Column("temperature", sa.Float),
        sa.Column("thinking_level", sa.String(20)),
        sa.Column("token_usage", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("grounding_sources", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("file_search_results", JSONB, server_default=sa.text("'[]'::jsonb")),
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
    op.create_index("idx_incidents_session", "incidents", ["session_id"])

    # --- chat_messages ---
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "incident_id",
            sa.Integer,
            sa.ForeignKey("incidents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("diff_content", sa.Text),
        sa.Column("token_usage", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="check_chat_role"),
    )
    op.create_index("idx_chat_incident", "chat_messages", ["incident_id"])

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.Text, unique=True, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("markdown_content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(768)),
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

    # --- version_history ---
    op.create_table(
        "version_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Integer, nullable=False),
        sa.Column("previous_content", sa.Text),
        sa.Column("new_content", sa.Text),
        sa.Column("changed_by", sa.String(100), server_default="system"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("idx_version_entity", "version_history", ["entity_type", "entity_id"])

    # --- prompts ---
    op.create_table(
        "prompts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("prompt_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
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
        sa.CheckConstraint("prompt_type IN ('system', 'user')", name="check_prompt_type"),
    )

    # --- output_schemas ---
    op.create_table(
        "output_schemas",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("schema_json", JSONB, nullable=False),
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

    # --- BM25 indexes (pg_textsearch) ---
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_incidents_error_bm25 "
        "ON incidents USING bm25(error_text) WITH (text_config='english')"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_incidents_markdown_bm25 "
        "ON incidents USING bm25(markdown_content) WITH (text_config='english')"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_documents_content_bm25 "
        "ON documents USING bm25(markdown_content) WITH (text_config='english')"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_documents_title_bm25 "
        "ON documents USING bm25(title) WITH (text_config='english')"
    )

    # --- pgvector HNSW indexes ---
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_incidents_embedding "
        "ON incidents USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_documents_embedding "
        "ON documents USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("output_schemas")
    op.drop_table("prompts")
    op.drop_table("version_history")
    op.drop_table("documents")
    op.drop_table("chat_messages")
    op.drop_table("incidents")
