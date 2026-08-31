"""Observability router — browse and search LLM events and calls."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.database import LLMCall, LLMEvent
from models.schemas import (
    LLMCallResponse,
    LLMEventDetail,
    LLMEventResponse,
    ObservabilityStatsResponse,
)
from security import require_api_key, rate_limit

router = APIRouter()


def _format_event(event: LLMEvent, call_count: int = 0, total_tokens: int = 0) -> dict:
    d = event.to_dict()
    d["call_count"] = call_count
    d["total_tokens"] = total_tokens
    return d


@router.get(
    "/observability/events",
    dependencies=[Depends(require_api_key), Depends(rate_limit(30, 60))],
)
async def list_events(
    event_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List LLM events with optional filters, including per-event call counts and token totals."""
    # Build aggregated query
    stmt = (
        select(
            LLMEvent,
            func.count(LLMCall.id).label("call_count"),
            func.coalesce(
                func.sum(LLMCall.input_tokens + LLMCall.output_tokens), 0
            ).label("total_tokens"),
        )
        .outerjoin(LLMCall, LLMCall.event_id == LLMEvent.id)
        .group_by(LLMEvent.id)
        .order_by(LLMEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if event_type:
        stmt = stmt.where(LLMEvent.event_type == event_type)
    if status:
        stmt = stmt.where(LLMEvent.status == status)
    if date_from:
        stmt = stmt.where(LLMEvent.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        stmt = stmt.where(LLMEvent.created_at <= datetime.fromisoformat(date_to))

    result = await db.execute(stmt)
    rows = result.all()

    return [_format_event(row[0], row[1], row[2]) for row in rows]


@router.get(
    "/observability/events/{event_id}",
    dependencies=[Depends(require_api_key), Depends(rate_limit(30, 60))],
)
async def get_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single event with all its nested LLM calls."""
    result = await db.execute(select(LLMEvent).where(LLMEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Event not found")

    calls_result = await db.execute(
        select(LLMCall)
        .where(LLMCall.event_id == event_id)
        .order_by(LLMCall.call_index)
    )
    calls = calls_result.scalars().all()

    total_tokens = sum(c.input_tokens + c.output_tokens for c in calls)
    d = _format_event(event, len(calls), total_tokens)
    d["calls"] = [c.to_dict() for c in calls]
    return d


@router.get(
    "/observability/search",
    dependencies=[Depends(require_api_key), Depends(rate_limit(30, 60))],
)
async def search_calls(
    q: str = Query(..., min_length=1),
    search_type: str = Query("text", regex="^(text|hybrid)$"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """BM25 full-text search across llm_calls.prompt_text and response_text.

    search_type=text  → pure BM25
    search_type=hybrid → BM25 across both fields combined
    """
    if search_type == "text":
        rows = await db.execute(
            text(
                "SELECT c.*, e.event_type, e.entity_type, e.entity_id, e.session_id,"
                "       LEAST("
                "         CASE WHEN c.prompt_text IS NOT NULL AND c.prompt_text != '' THEN"
                "           c.prompt_text <@> to_bm25query(:q, 'idx_llm_calls_prompt_bm25')"
                "         ELSE 0 END,"
                "         CASE WHEN c.response_text IS NOT NULL AND c.response_text != '' THEN"
                "           c.response_text <@> to_bm25query(:q, 'idx_llm_calls_response_bm25')"
                "         ELSE 0 END"
                "       ) AS score"
                " FROM llm_calls c"
                " JOIN llm_events e ON e.id = c.event_id"
                " WHERE ("
                "   (c.prompt_text IS NOT NULL AND c.prompt_text != '' AND"
                "    c.prompt_text <@> to_bm25query(:q, 'idx_llm_calls_prompt_bm25') < 0)"
                "   OR"
                "   (c.response_text IS NOT NULL AND c.response_text != '' AND"
                "    c.response_text <@> to_bm25query(:q, 'idx_llm_calls_response_bm25') < 0)"
                " )"
                " ORDER BY score"
                " LIMIT :limit"
            ),
            {"q": q, "limit": limit},
        )
    else:
        # hybrid: union of both field results, de-duplicated by best score
        rows = await db.execute(
            text(
                "SELECT DISTINCT ON (c.id) c.*, e.event_type, e.entity_type, e.entity_id, e.session_id,"
                "       LEAST("
                "         CASE WHEN c.prompt_text IS NOT NULL AND c.prompt_text != '' THEN"
                "           c.prompt_text <@> to_bm25query(:q, 'idx_llm_calls_prompt_bm25')"
                "         ELSE 0 END,"
                "         CASE WHEN c.response_text IS NOT NULL AND c.response_text != '' THEN"
                "           c.response_text <@> to_bm25query(:q, 'idx_llm_calls_response_bm25')"
                "         ELSE 0 END"
                "       ) AS score"
                " FROM llm_calls c"
                " JOIN llm_events e ON e.id = c.event_id"
                " WHERE ("
                "   (c.prompt_text IS NOT NULL AND c.prompt_text != '' AND"
                "    c.prompt_text <@> to_bm25query(:q, 'idx_llm_calls_prompt_bm25') < 0)"
                "   OR"
                "   (c.response_text IS NOT NULL AND c.response_text != '' AND"
                "    c.response_text <@> to_bm25query(:q, 'idx_llm_calls_response_bm25') < 0)"
                " )"
                " ORDER BY c.id, score"
                " LIMIT :limit"
            ),
            {"q": q, "limit": limit},
        )

    return [dict(row) for row in rows.mappings()]


@router.get(
    "/observability/stats",
    dependencies=[Depends(require_api_key), Depends(rate_limit(30, 60))],
)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate statistics across all LLM events and calls."""
    # Overall totals
    totals = await db.execute(
        text(
            "SELECT"
            "  COUNT(DISTINCT e.id) AS total_events,"
            "  COUNT(c.id) AS total_calls,"
            "  COALESCE(SUM(c.input_tokens), 0) AS total_input_tokens,"
            "  COALESCE(SUM(c.output_tokens), 0) AS total_output_tokens,"
            "  COALESCE(SUM(c.cache_read_tokens), 0) AS total_cache_tokens,"
            "  COALESCE(SUM(c.thinking_tokens), 0) AS total_thinking_tokens,"
            "  AVG(e.duration_ms) AS avg_duration_ms"
            " FROM llm_events e"
            " LEFT JOIN llm_calls c ON c.event_id = e.id"
        )
    )
    row = totals.mappings().one()

    # Events by type
    by_type = await db.execute(
        text(
            "SELECT event_type, COUNT(*) AS cnt"
            " FROM llm_events"
            " GROUP BY event_type"
            " ORDER BY cnt DESC"
        )
    )
    events_by_type = {r["event_type"]: r["cnt"] for r in by_type.mappings()}

    return {
        "total_events": row["total_events"] or 0,
        "total_calls": row["total_calls"] or 0,
        "total_input_tokens": row["total_input_tokens"] or 0,
        "total_output_tokens": row["total_output_tokens"] or 0,
        "total_cache_tokens": row["total_cache_tokens"] or 0,
        "total_thinking_tokens": row["total_thinking_tokens"] or 0,
        "avg_duration_ms": float(row["avg_duration_ms"]) if row["avg_duration_ms"] else None,
        "events_by_type": events_by_type,
    }
