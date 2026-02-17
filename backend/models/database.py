"""
SQLAlchemy ORM models — single source of truth for the database schema.
Alembic autogenerate reads these models to produce migration diffs.
"""

import uuid as uuid_mod
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class with a reusable serialisation helper."""

    def to_dict(self, exclude: set[str] | None = None) -> dict:
        """Convert an ORM instance to a JSON-friendly dict."""
        exclude = exclude or set()
        d: dict = {}
        for col in self.__table__.columns:
            if col.name in exclude:
                continue
            val = getattr(self, col.name)
            if isinstance(val, datetime):
                d[col.name] = val.isoformat()
            elif isinstance(val, uuid_mod.UUID):
                d[col.name] = str(val)
            else:
                d[col.name] = val
        return d


# ---------------------------------------------------------------------------
# Client API Keys (for external error ingestion)
# ---------------------------------------------------------------------------

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, server_default="''")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_api_keys_hash", "key_hash"),
    )


# ---------------------------------------------------------------------------
# Experts
# ---------------------------------------------------------------------------

class Expert(Base):
    __tablename__ = "experts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, server_default="''")
    file_search_store_name: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    documents: Mapped[list["ExpertDocument"]] = relationship(
        back_populates="expert", cascade="all, delete-orphan"
    )
    prompts: Mapped[list["Prompt"]] = relationship(back_populates="expert")


class ExpertDocument(Base):
    __tablename__ = "expert_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expert_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("experts.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gemini_file_name: Mapped[str | None] = mapped_column(String(500))
    operation_name: Mapped[str | None] = mapped_column(String(500))
    file_size: Mapped[int] = mapped_column(Integer, server_default="0")
    status: Mapped[str] = mapped_column(String(20), server_default="'pending'")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    expert: Mapped["Expert"] = relationship(back_populates="documents")

    __table_args__ = (
        Index("idx_expert_documents_expert", "expert_id"),
    )


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        default=uuid_mod.uuid4,
        server_default=func.gen_random_uuid(),
    )
    error_text: Mapped[str | None] = mapped_column(Text)
    image_data: Mapped[bytes | None] = mapped_column(LargeBinary)
    image_mime_type: Mapped[str | None] = mapped_column(String(50))
    raw_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="'{}'")
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False, server_default="''")
    embedding = mapped_column(Vector(768), nullable=True)
    embedding_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100))
    temperature: Mapped[float | None] = mapped_column(Float)
    thinking_level: Mapped[str | None] = mapped_column(String(20))
    token_usage: Mapped[dict] = mapped_column(JSONB, server_default="'{}'")
    grounding_sources: Mapped[list] = mapped_column(JSONB, server_default="'[]'")
    file_search_results: Mapped[list] = mapped_column(JSONB, server_default="'[]'")
    infographic_data: Mapped[str | None] = mapped_column(Text)  # Base64 encoded image
    infographic_prompt: Mapped[str | None] = mapped_column(Text)  # Prompt used to generate
    notes: Mapped[str] = mapped_column(Text, server_default="''", nullable=False)
    categories: Mapped[list] = mapped_column(JSONB, server_default="'[]'", nullable=False)
    schema_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classification_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(
        String(20), server_default="'manual'", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), server_default="'created'", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('manual', 'api')",
            name="check_incident_source",
        ),
        CheckConstraint(
            "status IN ('created', 'pending_review', 'in_review', 'analyzed', 'closed', 'resolved')",
            name="check_incident_status",
        ),
        Index("idx_incidents_session", "session_id"),
        Index("idx_incidents_source_status", "source", "status"),
    )


# ---------------------------------------------------------------------------
# Related Incidents (bidirectional links between articles)
# ---------------------------------------------------------------------------

class RelatedIncident(Base):
    __tablename__ = "related_incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    related_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(
        String(30), server_default="'followup'", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_related_pair", "incident_id", "related_id", unique=True),
    )


# ---------------------------------------------------------------------------
# Chat Messages
# ---------------------------------------------------------------------------

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    diff_content: Mapped[str | None] = mapped_column(Text)
    token_usage: Mapped[dict] = mapped_column(JSONB, server_default="'{}'")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    incident: Mapped["Incident"] = relationship(back_populates="chat_messages")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="check_chat_role"),
        Index("idx_chat_incident", "incident_id"),
    )


# ---------------------------------------------------------------------------
# Documents (knowledge base)
# ---------------------------------------------------------------------------

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Version History
# ---------------------------------------------------------------------------

class VersionHistory(Base):
    __tablename__ = "version_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_content: Mapped[str | None] = mapped_column(Text)
    new_content: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(String(100), server_default="'system'")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_version_entity", "entity_type", "entity_id"),
    )


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    prompt_type: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt_category: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="'grounded'"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    expert_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("experts.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    expert: Mapped["Expert | None"] = relationship(back_populates="prompts")

    __table_args__ = (
        CheckConstraint("prompt_type IN ('system', 'user')", name="check_prompt_type"),
        CheckConstraint(
            "prompt_category IN ('grounded', 'file_search')",
            name="check_prompt_category",
        ),
    )


# ---------------------------------------------------------------------------
# Output Schemas
# ---------------------------------------------------------------------------

class OutputSchema(Base):
    __tablename__ = "output_schemas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# Schemas (for category-based classification)
# ---------------------------------------------------------------------------

class Schema(Base):
    __tablename__ = "schemas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, server_default="", nullable=False)
    json_schema: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_schemas_active", "is_active"),
    )


# ---------------------------------------------------------------------------
# Categories (20 category types for classification)
# ---------------------------------------------------------------------------

class Category(Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(50), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    intent_description: Mapped[str] = mapped_column(Text, nullable=False)
    example_inputs: Mapped[list] = mapped_column(ARRAY(Text), server_default="{}", nullable=False)
    key_outputs: Mapped[list] = mapped_column(ARRAY(Text), server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Schema-Category Mappings
# ---------------------------------------------------------------------------

class SchemaCategory(Base):
    __tablename__ = "schema_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schemas.id", ondelete="CASCADE"), nullable=False
    )
    category_name: Mapped[str] = mapped_column(
        String(50), ForeignKey("categories.name", ondelete="CASCADE"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, server_default="1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("schema_id", "category_name", name="uq_schema_category"),
        Index("idx_schema_categories_schema", "schema_id"),
        Index("idx_schema_categories_category", "category_name"),
    )
