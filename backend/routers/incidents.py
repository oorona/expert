import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db, engine
from models.database import ChatMessage, Incident, RelatedIncident
from security import require_api_key, rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateNotesRequest(BaseModel):
    notes: str | None = None


class UpdateStatusRequest(BaseModel):
    status: Literal["created", "pending_review", "in_review", "analyzed", "closed"]


class SaveInfographicRequest(BaseModel):
    infographic_data: str  # Base64 encoded image
    infographic_prompt: str


@router.get("/incidents", dependencies=[Depends(require_api_key)])
async def list_incidents(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    source: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(Incident).order_by(Incident.created_at.desc())
    if source:
        query = query.where(Incident.source == source)
    # Exclude API-ingested incidents that haven't been analyzed yet
    if source is None:
        query = query.where(
            or_(
                Incident.source != "api",
                Incident.status.in_(["analyzed", "closed"]),
            )
        )
    result = await db.execute(query.offset(offset).limit(limit))
    return [
        {
            "id": i.id,
            "session_id": str(i.session_id),
            "error_text": i.error_text,
            "title": (i.raw_json or {}).get("title"),
            "error_summary": (i.raw_json or {}).get("error_summary"),
            "expert_id": (i.raw_json or {}).get("expert_id"),
            "categories": i.categories or [],
            "source": i.source,
            "status": i.status,
            "created_at": i.created_at.isoformat(),
        }
        for i in result.scalars().all()
    ]


@router.get("/incidents/incoming", dependencies=[Depends(require_api_key)])
async def list_incoming_errors(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List API-ingested errors that are pending review."""
    result = await db.execute(
        select(Incident)
        .where(
            Incident.source == "api",
            Incident.status.in_(["created", "in_review", "analyzed"]),
        )
        .order_by(Incident.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        {
            "id": i.id,
            "session_id": str(i.session_id),
            "error_text": i.error_text,
            "title": (i.raw_json or {}).get("title"),
            "error_summary": (i.raw_json or {}).get("error_summary"),
            "source_system": (i.raw_json or {}).get("source_system"),
            "client_name": (i.raw_json or {}).get("client_name"),
            "expert_id": (i.raw_json or {}).get("expert_id"),
            "source": i.source,
            "status": i.status,
            "created_at": i.created_at.isoformat(),
        }
        for i in result.scalars().all()
    ]


@router.get("/incidents/{session_id}", dependencies=[Depends(require_api_key)])
async def get_incident(session_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Incident).where(Incident.session_id == session_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.incident_id == incident.id)
        .order_by(ChatMessage.created_at)
    )
    chat_msgs = result.scalars().all()

    related_rows = await db.execute(
        select(RelatedIncident)
        .where(RelatedIncident.incident_id == incident.id)
    )
    related_links = related_rows.scalars().all()
    related_ids = [r.related_id for r in related_links]
    related_articles = []
    if related_ids:
        rel_result = await db.execute(
            select(Incident).where(Incident.id.in_(related_ids))
            .order_by(Incident.created_at)
        )
        for ri in rel_result.scalars().all():
            link = next((r for r in related_links if r.related_id == ri.id), None)
            related_articles.append({
                "id": ri.id,
                "session_id": str(ri.session_id),
                "error_text": ri.error_text,
                "title": (ri.raw_json or {}).get("title"),
                "error_summary": (ri.raw_json or {}).get("error_summary"),
                "relation_type": link.relation_type if link else "related",
                "created_at": ri.created_at.isoformat(),
            })

    return {
        "id": incident.id,
        "session_id": str(incident.session_id),
        "error_text": incident.error_text,
        "title": (incident.raw_json or {}).get("title"),
        "raw_json": incident.raw_json,
        "markdown_content": incident.markdown_content,
        "model_used": incident.model_used,
        "temperature": incident.temperature,
        "thinking_level": incident.thinking_level,
        "token_usage": incident.token_usage,
        "grounding_sources": incident.grounding_sources,
        "file_search_results": incident.file_search_results,
        "infographic_data": incident.infographic_data,
        "infographic_prompt": incident.infographic_prompt,
        "notes": incident.notes,
        "expert_id": (incident.raw_json or {}).get("expert_id"),
        "source": incident.source,
        "status": incident.status,
        "created_at": incident.created_at.isoformat(),
        "related_articles": related_articles,
        "chat_messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "diff_content": m.diff_content,
                "token_usage": m.token_usage,
                "created_at": m.created_at.isoformat(),
            }
            for m in chat_msgs
        ],
    }


@router.patch("/incidents/{incident_id}", dependencies=[Depends(require_api_key)])
async def update_incident(
    incident_id: int,
    body: UpdateNotesRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident.notes = body.notes or ""
    await db.flush()
    return {"status": "updated", "notes": incident.notes}


@router.patch("/incidents/{incident_id}/status", dependencies=[Depends(require_api_key)])
async def update_incident_status(
    incident_id: int,
    body: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident.status = body.status
    await db.flush()
    return {"status": incident.status, "incident_id": incident.id}


@router.patch("/incidents/{incident_id}/infographic", dependencies=[Depends(require_api_key)])
async def save_infographic(
    incident_id: int,
    body: SaveInfographicRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save a generated infographic to the incident."""
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.infographic_data = body.infographic_data
    incident.infographic_prompt = body.infographic_prompt
    await db.flush()

    return {
        "status": "saved",
        "incident_id": incident.id,
        "has_infographic": True
    }


@router.delete("/incidents/{incident_id}", dependencies=[Depends(require_api_key)])
async def delete_incident(incident_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(Incident).where(Incident.id == incident_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"status": "deleted"}


@router.delete("/incidents", dependencies=[Depends(require_api_key)])
async def delete_all_incidents(db: AsyncSession = Depends(get_db)):
    """Delete all incidents and VACUUM the table to reclaim TOAST storage."""
    result = await db.execute(delete(Incident))
    count = result.rowcount
    await db.commit()

    # VACUUM cannot run inside a transaction — use a raw autocommit connection
    raw_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    async with raw_engine.connect() as conn:
        await conn.execute(text("VACUUM FULL incidents"))
        logger.info("VACUUM FULL incidents completed after deleting %d rows", count)

    return {"status": "deleted", "count": count}


class LinkArticlesRequest(BaseModel):
    session_id_a: UUID
    session_id_b: UUID
    relation_type: Literal["related", "followup", "parent", "duplicate"] = "related"


@router.post("/incidents/link", dependencies=[Depends(require_api_key)])
async def link_articles(
    body: LinkArticlesRequest, db: AsyncSession = Depends(get_db)
):
    """Create a bidirectional link between two articles."""
    res_a = await db.execute(
        select(Incident).where(Incident.session_id == body.session_id_a)
    )
    res_b = await db.execute(
        select(Incident).where(Incident.session_id == body.session_id_b)
    )
    inc_a = res_a.scalar_one_or_none()
    inc_b = res_b.scalar_one_or_none()
    if not inc_a or not inc_b:
        raise HTTPException(status_code=404, detail="One or both incidents not found")

    for a_id, b_id, rtype in [
        (inc_a.id, inc_b.id, body.relation_type),
        (inc_b.id, inc_a.id, body.relation_type),
    ]:
        existing = await db.execute(
            select(RelatedIncident).where(
                RelatedIncident.incident_id == a_id,
                RelatedIncident.related_id == b_id,
            )
        )
        if not existing.scalar_one_or_none():
            db.add(RelatedIncident(
                incident_id=a_id,
                related_id=b_id,
                relation_type=rtype,
            ))
    await db.flush()
    return {"status": "linked"}
