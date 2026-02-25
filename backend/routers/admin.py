import hashlib
import json
import logging
import secrets as secrets_mod
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.database import ApiKey, Category, OutputSchema, Prompt, Schema, SchemaCategory, VersionHistory
from models.schemas import (
    PromptCreate,
    PromptUpdate,
    SchemaCreate,
    SchemaUpdate,
)
from security import require_api_key

logger = logging.getLogger(__name__)
router = APIRouter()

SCHEMAS_DIR = Path(__file__).parent.parent / "db" / "schemas" / "definitions"
PROMPTS_DIR = Path(__file__).parent.parent / "db" / "prompts" / "templates"

_PROMPT_TEMPLATE_FILES = {
    "Template - System (grounded)":    "grounded_system.txt",
    "Template - User (grounded)":      "grounded_user.txt",
    "Template - System (file_search)": "file_search_system.txt",
    "Template - User (file_search)":   "file_search_user.txt",
}


def _sync_prompt_to_disk(prompt: "Prompt") -> None:
    """Write a template prompt's content back to its canonical disk file."""
    filename = _PROMPT_TEMPLATE_FILES.get(prompt.name)
    if not filename:
        return  # not a template prompt — skip
    try:
        PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
        (PROMPTS_DIR / filename).write_text(prompt.content)
        logger.info("Synced prompt '%s' to disk: %s", prompt.name, filename)
    except Exception as exc:
        logger.warning("Failed to sync prompt to disk: %s", exc)


async def _auto_export_schemas(db: AsyncSession) -> None:
    """Write all schemas + category mappings to disk after any schema change."""
    try:
        SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)

        schemas_res = await db.execute(select(Schema).order_by(Schema.id))
        schemas = schemas_res.scalars().all()

        mappings_res = await db.execute(
            select(SchemaCategory).order_by(SchemaCategory.schema_id, SchemaCategory.category_name)
        )
        mappings = mappings_res.scalars().all()

        schema_cats: dict[int, list] = {}
        for m in mappings:
            schema_cats.setdefault(m.schema_id, []).append(
                {"category_name": m.category_name, "priority": m.priority}
            )

        manifest = []
        for s in schemas:
            cats = schema_cats.get(s.id, [])
            entry = {
                "name": s.name,
                "description": s.description,
                "json_schema": s.json_schema,
                "is_active": s.is_active,
                "categories": cats,
            }
            manifest.append(entry)
            safe_name = s.name.lower().replace(" ", "_")
            (SCHEMAS_DIR / f"{safe_name}.json").write_text(
                json.dumps({"schema": s.json_schema, "categories": cats}, indent=2)
            )

        (SCHEMAS_DIR / "schemas_manifest.json").write_text(json.dumps(manifest, indent=2))
        logger.info("Auto-exported %d schemas to %s", len(schemas), SCHEMAS_DIR)
    except Exception as exc:
        logger.warning("Auto-export schemas failed: %s", exc)


async def _auto_export_categories(db: AsyncSession) -> None:
    """Write all categories to categories_manifest.json after any category change."""
    try:
        SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
        result = await db.execute(select(Category).order_by(Category.name))
        categories = result.scalars().all()
        manifest = [
            {
                "name": c.name,
                "display_name": c.display_name,
                "description": c.description,
                "intent_description": c.intent_description,
                "example_inputs": c.example_inputs or [],
                "key_outputs": c.key_outputs or [],
            }
            for c in categories
        ]
        (SCHEMAS_DIR / "categories_manifest.json").write_text(json.dumps(manifest, indent=2))
        logger.info("Auto-exported %d categories to %s", len(categories), SCHEMAS_DIR)
    except Exception as exc:
        logger.warning("Auto-export categories failed: %s", exc)


# --- Prompts ---


@router.get("/prompts", dependencies=[Depends(require_api_key)])
async def list_prompts(
    expert_id: int | None = None,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Prompt).order_by(Prompt.prompt_type, Prompt.name)

    if expert_id is not None:
        query = query.where(Prompt.expert_id == expert_id)

    if category is not None:
        query = query.where(Prompt.prompt_category == category)

    result = await db.execute(query)
    return [p.to_dict() for p in result.scalars().all()]


@router.get("/prompts/{prompt_id}", dependencies=[Depends(require_api_key)])
async def get_prompt(prompt_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt.to_dict()


@router.post("/prompts", dependencies=[Depends(require_api_key)])
async def create_prompt(body: PromptCreate, db: AsyncSession = Depends(get_db)):
    prompt = Prompt(
        name=body.name,
        prompt_type=body.prompt_type,
        prompt_category=body.prompt_category,
        content=body.content,
        expert_id=body.expert_id,
    )
    db.add(prompt)
    await db.flush()
    await db.refresh(prompt)
    return prompt.to_dict()


@router.put("/prompts/{prompt_id}", dependencies=[Depends(require_api_key)])
async def update_prompt(
    prompt_id: int, body: PromptUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")

    if body.content is not None:
        old_content = prompt.content
        prompt.content = body.content
        prompt.updated_at = datetime.now(timezone.utc)
        db.add(
            VersionHistory(
                entity_type="prompt",
                entity_id=prompt_id,
                previous_content=old_content,
                new_content=body.content,
            )
        )

    if body.is_active is not None:
        prompt.is_active = body.is_active
        prompt.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(prompt)

    # Keep disk in sync for template prompts
    if body.content is not None:
        _sync_prompt_to_disk(prompt)

    return prompt.to_dict()


@router.delete("/prompts/{prompt_id}", dependencies=[Depends(require_api_key)])
async def delete_prompt(prompt_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Prompt).where(Prompt.id == prompt_id))
    return {"status": "deleted"}


# --- Output Schemas ---


@router.get("/schemas")
async def list_schemas(db: AsyncSession = Depends(get_db)):
    """List all category-based schemas (public endpoint - no auth required)."""
    result = await db.execute(select(Schema).order_by(Schema.name))
    return [s.to_dict() for s in result.scalars().all()]


@router.get("/schemas/{schema_id}")
async def get_schema(schema_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific schema by ID (public endpoint - no auth required)."""
    result = await db.execute(
        select(Schema).where(Schema.id == schema_id)
    )
    schema = result.scalar_one_or_none()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    return schema.to_dict()


@router.post("/schemas")
async def create_schema(body: SchemaCreate, db: AsyncSession = Depends(get_db)):
    """Create a new category-based schema (public endpoint - no auth required)."""
    schema = Schema(
        name=body.name,
        description=getattr(body, 'description', ''),
        json_schema=body.schema_json
    )
    db.add(schema)
    await db.commit()
    await db.refresh(schema)
    await _auto_export_schemas(db)
    return schema.to_dict()


@router.put("/schemas/{schema_id}")
async def update_schema(
    schema_id: int, body: SchemaUpdate, db: AsyncSession = Depends(get_db)
):
    """Update an existing schema (public endpoint - no auth required)."""
    result = await db.execute(
        select(Schema).where(Schema.id == schema_id)
    )
    schema = result.scalar_one_or_none()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    if body.schema_json is not None:
        old_json = json.dumps(schema.json_schema)
        schema.json_schema = body.schema_json
        schema.updated_at = datetime.now(timezone.utc)
        db.add(
            VersionHistory(
                entity_type="schema",
                entity_id=schema_id,
                previous_content=old_json,
                new_content=json.dumps(body.schema_json),
            )
        )

    if body.is_active is not None:
        schema.is_active = body.is_active
        schema.updated_at = datetime.now(timezone.utc)

    if hasattr(body, 'description') and body.description is not None:
        schema.description = body.description
        schema.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(schema)
    await _auto_export_schemas(db)
    return schema.to_dict()


@router.delete("/schemas/{schema_id}", dependencies=[Depends(require_api_key)])
async def delete_schema(schema_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a schema by ID."""
    await db.execute(delete(Schema).where(Schema.id == schema_id))
    await db.commit()
    return {"status": "deleted"}


# --- Categories ---

@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """List all categories (public endpoint - no auth required)."""
    result = await db.execute(select(Category).order_by(Category.display_name))
    categories = result.scalars().all()
    return [
        {
            "name": c.name,
            "display_name": c.display_name,
            "description": c.description,
            "intent_description": c.intent_description,
            "example_inputs": c.example_inputs,
            "key_outputs": c.key_outputs,
        }
        for c in categories
    ]


# --- Schema-Category Mappings ---

@router.get("/schemas/{schema_id}/categories")
async def get_schema_categories(schema_id: int, db: AsyncSession = Depends(get_db)):
    """Get all category mappings for a schema."""
    from models.database import SchemaCategory

    result = await db.execute(
        select(SchemaCategory)
        .where(SchemaCategory.schema_id == schema_id)
        .order_by(SchemaCategory.priority, SchemaCategory.category_name)
    )
    mappings = result.scalars().all()

    return [
        {
            "category_name": m.category_name,
            "priority": m.priority,
        }
        for m in mappings
    ]


class SchemaCategoryMapping(BaseModel):
    category_name: str
    priority: int = 1


class UpdateSchemaCategoriesRequest(BaseModel):
    categories: list[SchemaCategoryMapping]


@router.put("/schemas/{schema_id}/categories")
async def update_schema_categories(
    schema_id: int,
    body: UpdateSchemaCategoriesRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update category mappings for a schema."""
    from models.database import SchemaCategory
    from sqlalchemy import delete as sql_delete

    result = await db.execute(select(Schema).where(Schema.id == schema_id))
    schema = result.scalar_one_or_none()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    await db.execute(
        sql_delete(SchemaCategory).where(SchemaCategory.schema_id == schema_id)
    )

    for mapping in body.categories:
        result = await db.execute(
            select(Category).where(Category.name == mapping.category_name)
        )
        category = result.scalar_one_or_none()
        if not category:
            raise HTTPException(
                status_code=400,
                detail=f"Category '{mapping.category_name}' not found"
            )

        schema_category = SchemaCategory(
            schema_id=schema_id,
            category_name=mapping.category_name,
            priority=mapping.priority
        )
        db.add(schema_category)

    await db.commit()

    result = await db.execute(
        select(SchemaCategory)
        .where(SchemaCategory.schema_id == schema_id)
        .order_by(SchemaCategory.priority, SchemaCategory.category_name)
    )
    mappings = result.scalars().all()

    return [
        {
            "category_name": m.category_name,
            "priority": m.priority,
        }
        for m in mappings
    ]


# --- Client API Keys ---

def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=2000)


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    description: str
    is_active: bool
    last_used_at: str | None
    created_at: str
    key_preview: str  # first 8 chars


class CreateApiKeyResponse(ApiKeyResponse):
    raw_key: str  # Only shown once, at creation time


class UpdateApiKeyRequest(BaseModel):
    name: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=2000)
    is_active: bool | None = None


def _api_key_to_response(ak: ApiKey, preview: str = "") -> dict:
    return {
        "id": ak.id,
        "name": ak.name,
        "description": ak.description or "",
        "is_active": ak.is_active,
        "last_used_at": ak.last_used_at.isoformat() if ak.last_used_at else None,
        "created_at": ak.created_at.isoformat() if ak.created_at else None,
        "key_preview": preview,
    }


@router.get("/api-keys", dependencies=[Depends(require_api_key)])
async def list_api_keys(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
    keys = result.scalars().all()
    return [
        _api_key_to_response(k, k.key_hash[:8] + "…")
        for k in keys
    ]


@router.post("/api-keys", dependencies=[Depends(require_api_key)])
async def create_api_key(
    body: CreateApiKeyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new client API key.

    Returns the raw key ONCE — it cannot be retrieved again.
    """
    raw_key = secrets_mod.token_urlsafe(48)
    key_hash = _hash_key(raw_key)

    ak = ApiKey(
        key_hash=key_hash,
        name=body.name,
        description=body.description,
    )
    db.add(ak)
    await db.flush()
    await db.refresh(ak)

    resp = _api_key_to_response(ak, raw_key[:8] + "…")
    resp["raw_key"] = raw_key
    return resp


@router.put("/api-keys/{key_id}", dependencies=[Depends(require_api_key)])
async def update_api_key(
    key_id: int,
    body: UpdateApiKeyRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    ak = result.scalar_one_or_none()
    if not ak:
        raise HTTPException(status_code=404, detail="API key not found")

    if body.name is not None:
        ak.name = body.name
    if body.description is not None:
        ak.description = body.description
    if body.is_active is not None:
        ak.is_active = body.is_active

    await db.flush()
    await db.refresh(ak)
    return _api_key_to_response(ak, ak.key_hash[:8] + "…")


@router.delete("/api-keys/{key_id}", dependencies=[Depends(require_api_key)])
async def delete_api_key(key_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(ApiKey).where(ApiKey.id == key_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "deleted"}


# --- Context Caching ---


@router.get("/cache/status", dependencies=[Depends(require_api_key)])
async def get_cache_status():
    """Get status of all active context caches for monitoring/debugging."""
    from services.gemini import gemini_service

    caches = await gemini_service.list_active_caches()
    return {
        "active_caches": caches,
        "total_count": len(caches),
    }


@router.post("/cache/clear-expired", dependencies=[Depends(require_api_key)])
async def clear_expired_caches():
    """Manually trigger cleanup of expired caches."""
    from services.gemini import gemini_service

    cleared_count = await gemini_service.clear_expired_caches()
    return {
        "status": "success",
        "cleared_count": cleared_count,
    }


# --- Reload Defaults ---


@router.post("/reload-defaults", dependencies=[Depends(require_api_key)])
async def reload_defaults(db: AsyncSession = Depends(get_db)):
    """Reload prompt templates, categories and schemas from disk, overwriting DB values.

    Canonical on-disk locations:
      - backend/db/prompts/templates/          (prompt templates)
      - backend/db/schemas/definitions/        (schemas + category mappings)
      - backend/db/schemas/definitions/categories_manifest.json  (categories)
    """
    from db.init import reload_defaults as _reload

    await _reload(db)
    await db.commit()

    # Re-export everything back to disk so the files reflect the final DB state
    await _auto_export_schemas(db)
    await _auto_export_categories(db)

    return {"status": "ok", "message": "Defaults reloaded from disk"}
