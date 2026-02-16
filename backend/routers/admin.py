import hashlib
import json
import secrets as secrets_mod
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.database import ApiKey, OutputSchema, Prompt, VersionHistory
from models.schemas import (
    PromptCreate,
    PromptUpdate,
    SchemaCreate,
    SchemaUpdate,
)
from security import require_api_key

router = APIRouter()


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
    elif expert_id is None and category is None:
        # Default: show global prompts (no expert)
        pass

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
    return prompt.to_dict()


@router.delete("/prompts/{prompt_id}", dependencies=[Depends(require_api_key)])
async def delete_prompt(prompt_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Prompt).where(Prompt.id == prompt_id))
    return {"status": "deleted"}


# --- Output Schemas ---


@router.get("/schemas", dependencies=[Depends(require_api_key)])
async def list_schemas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(OutputSchema).order_by(OutputSchema.name))
    return [s.to_dict() for s in result.scalars().all()]


@router.get("/schemas/{schema_id}", dependencies=[Depends(require_api_key)])
async def get_schema(schema_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(OutputSchema).where(OutputSchema.id == schema_id)
    )
    schema = result.scalar_one_or_none()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    return schema.to_dict()


@router.post("/schemas", dependencies=[Depends(require_api_key)])
async def create_schema(body: SchemaCreate, db: AsyncSession = Depends(get_db)):
    schema = OutputSchema(name=body.name, schema_json=body.schema_json)
    db.add(schema)
    await db.flush()
    await db.refresh(schema)
    return schema.to_dict()


@router.put("/schemas/{schema_id}", dependencies=[Depends(require_api_key)])
async def update_schema(
    schema_id: int, body: SchemaUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(OutputSchema).where(OutputSchema.id == schema_id)
    )
    schema = result.scalar_one_or_none()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")

    if body.schema_json is not None:
        old_json = json.dumps(schema.schema_json)
        schema.schema_json = body.schema_json
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

    await db.flush()
    await db.refresh(schema)
    return schema.to_dict()


@router.delete("/schemas/{schema_id}", dependencies=[Depends(require_api_key)])
async def delete_schema(schema_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(OutputSchema).where(OutputSchema.id == schema_id))
    return {"status": "deleted"}


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
