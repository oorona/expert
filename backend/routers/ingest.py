"""
External error ingestion API.

Accepts errors from external systems via client API keys.
Errors are queued for human review in the dashboard.
"""

import hashlib
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.database import ApiKey, Expert, ExpertDocument, Incident, Prompt
from security import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Client API key validation (separate from the internal admin key)
# ---------------------------------------------------------------------------

def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def require_client_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    """Validate the X-Client-Key header against stored client API keys."""
    client_key = request.headers.get("X-Client-Key")
    if not client_key:
        raise HTTPException(status_code=401, detail="Missing X-Client-Key header")

    key_hash = _hash_key(client_key)
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=403, detail="Invalid or inactive client key")

    # Update last_used_at
    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key.id)
        .values(last_used_at=sa_func.now())
    )

    return api_key


# ---------------------------------------------------------------------------
# Ingest schema
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Expert listing for external clients
# ---------------------------------------------------------------------------

class ExpertListItem(BaseModel):
    id: int
    name: str
    description: str
    is_active: bool
    document_count: int = 0
    system_prompt: Optional[str] = None


@router.get("/ingest/experts", response_model=list[ExpertListItem])
async def list_available_experts(
    client: ApiKey = Depends(require_client_key),
    db: AsyncSession = Depends(get_db),
):
    """List all active experts available for error diagnosis.

    Returns each expert's system prompt so clients can understand
    the expert's behaviour and what types of errors it handles.
    """
    result = await db.execute(
        select(
            Expert,
            sa_func.count(ExpertDocument.id).label("doc_count"),
        )
        .outerjoin(ExpertDocument, Expert.id == ExpertDocument.expert_id)
        .where(Expert.is_active == True)
        .group_by(Expert.id)
        .order_by(Expert.name)
    )
    rows = result.all()

    # Load the active system prompt for each expert
    expert_ids = [row.Expert.id for row in rows]
    prompts_result = await db.execute(
        select(Prompt)
        .where(
            Prompt.expert_id.in_(expert_ids),
            Prompt.prompt_type == "system",
            Prompt.is_active == True,
        )
    )
    # Map expert_id -> system prompt content
    system_prompts: dict[int, str] = {}
    for p in prompts_result.scalars().all():
        if p.expert_id is not None:
            system_prompts[p.expert_id] = p.content

    return [
        ExpertListItem(
            id=row.Expert.id,
            name=row.Expert.name,
            description=row.Expert.description or "",
            is_active=row.Expert.is_active,
            document_count=row.doc_count,
            system_prompt=system_prompts.get(row.Expert.id),
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Ingest schema
# ---------------------------------------------------------------------------

class IngestErrorRequest(BaseModel):
    error_text: str = Field(..., min_length=1, max_length=50_000)
    expert_id: int = Field(..., description="Target expert ID (from GET /ingest/experts)")
    source_system: Optional[str] = Field(None, max_length=200)
    metadata: Optional[dict] = None


class IngestErrorResponse(BaseModel):
    incident_id: int
    session_id: str
    status: str


class IngestBatchRequest(BaseModel):
    errors: list[IngestErrorRequest] = Field(..., min_length=1, max_length=100)


class IngestBatchResponse(BaseModel):
    ingested: list[IngestErrorResponse]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _create_incident(err: IngestErrorRequest, client_name: str) -> Incident:
    """Build an Incident ORM object for an ingested error."""
    return Incident(
        error_text=err.error_text,
        source="api",
        status="created",
        raw_json={
            "source_system": err.source_system,
            "client_name": client_name,
            "expert_id": err.expert_id,
            **(err.metadata or {}),
        },
    )


@router.post(
    "/ingest",
    response_model=IngestErrorResponse,
    dependencies=[Depends(rate_limit(60, 60))],
)
async def ingest_single_error(
    body: IngestErrorRequest,
    client: ApiKey = Depends(require_client_key),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a single error from an external system.

    The error is stored with status='created' and source='api'.
    It will appear in the Incoming Errors queue on the dashboard
    for human review.
    """
    # Validate expert exists and is active
    expert = await db.execute(
        select(Expert).where(Expert.id == body.expert_id, Expert.is_active == True)
    )
    if not expert.scalar_one_or_none():
        raise HTTPException(status_code=422, detail=f"Expert {body.expert_id} not found or inactive")

    incident = _create_incident(body, client.name)
    db.add(incident)
    await db.flush()

    logger.info(
        "Ingested error #%d from client '%s'",
        incident.id,
        client.name,
    )

    return IngestErrorResponse(
        incident_id=incident.id,
        session_id=str(incident.session_id),
        status=incident.status,
    )


@router.post(
    "/ingest/batch",
    response_model=IngestBatchResponse,
    dependencies=[Depends(rate_limit(10, 60))],
)
async def ingest_batch_errors(
    body: IngestBatchRequest,
    client: ApiKey = Depends(require_client_key),
    db: AsyncSession = Depends(get_db),
):
    """Ingest multiple errors in a single request (max 100).

    All errors are inserted in a single transaction for efficiency.
    Each gets status='created' and source='api'.
    """
    # Validate all expert_ids exist and are active
    expert_ids = {err.expert_id for err in body.errors}
    result = await db.execute(
        select(Expert.id).where(Expert.id.in_(expert_ids), Expert.is_active == True)
    )
    valid_ids = {row[0] for row in result.all()}
    invalid_ids = expert_ids - valid_ids
    if invalid_ids:
        raise HTTPException(
            status_code=422,
            detail=f"Expert(s) not found or inactive: {sorted(invalid_ids)}",
        )

    incidents: list[Incident] = []

    for err in body.errors:
        inc = _create_incident(err, client.name)
        db.add(inc)
        incidents.append(inc)

    await db.flush()  # assigns IDs + session_ids

    results = [
        IngestErrorResponse(
            incident_id=inc.id,
            session_id=str(inc.session_id),
            status=inc.status,
        )
        for inc in incidents
    ]

    logger.info(
        "Batch ingested %d errors from client '%s'",
        len(results),
        client.name,
    )

    return IngestBatchResponse(ingested=results, total=len(results))
