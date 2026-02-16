from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from security import require_api_key, rate_limit
from services.gemini import gemini_service

router = APIRouter()


@router.get("/search", dependencies=[Depends(require_api_key), Depends(rate_limit(30, 60))])
async def search(
    q: str = Query(..., min_length=1),
    search_type: str = Query("text", regex="^(text|semantic|hybrid)$"),
    entity: str = Query("all", regex="^(all|incidents|documents)$"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Search across incidents and documents.
    - text: BM25 full-text search via pg_textsearch (<@> operator)
    - semantic: pgvector cosine similarity
    - hybrid: reciprocal rank fusion of both
    """
    results: list[dict] = []

    if search_type == "text":
        results = await _bm25_search(db, q, entity, limit)
    elif search_type == "semantic":
        results = await _semantic_search(db, q, entity, limit)
    elif search_type == "hybrid":
        results = await _hybrid_search(db, q, entity, limit)

    return results


async def _bm25_search(
    db: AsyncSession, query: str, entity: str, limit: int
) -> list[dict]:
    """BM25 ranked search using pg_textsearch <@> operator across all text fields."""
    results: list[dict] = []

    if entity in ("all", "incidents"):
        rows = await db.execute(
            text(
                "SELECT id, session_id::text, 'incident' AS entity_type, error_text,"
                "       (raw_json->>'title') AS title,"
                "       (raw_json->>'error_summary') AS error_summary,"
                "       markdown_content,"
                "       LEAST("
                "         error_text <@> to_bm25query(:query, 'idx_incidents_error_bm25'),"
                "         markdown_content <@> to_bm25query(:query, 'idx_incidents_markdown_bm25'),"
                "         notes <@> to_bm25query(:query, 'idx_incidents_notes_bm25')"
                "       ) AS score"
                " FROM incidents"
                " WHERE error_text <@> to_bm25query(:query, 'idx_incidents_error_bm25') < 0"
                "    OR markdown_content <@> to_bm25query(:query, 'idx_incidents_markdown_bm25') < 0"
                "    OR notes <@> to_bm25query(:query, 'idx_incidents_notes_bm25') < 0"
                " ORDER BY score"
                " LIMIT :limit"
            ),
            {"query": query, "limit": limit},
        )
        results.extend(dict(row) for row in rows.mappings())

    if entity in ("all", "documents"):
        rows = await db.execute(
            text(
                "SELECT id, 'document' AS entity_type, title,"
                "       markdown_content,"
                "       markdown_content <@> to_bm25query(:query, 'idx_documents_content_bm25') AS score"
                " FROM documents"
                " WHERE markdown_content <@> to_bm25query(:query, 'idx_documents_content_bm25') < 0"
                " ORDER BY score"
                " LIMIT :limit"
            ),
            {"query": query, "limit": limit},
        )
        results.extend(dict(row) for row in rows.mappings())

    # Sort by score (more negative = better match)
    results.sort(key=lambda x: x.get("score", 0))
    return results[:limit]


async def _semantic_search(
    db: AsyncSession, query: str, entity: str, limit: int
) -> list[dict]:
    """Semantic similarity search using pgvector."""
    embedding = await gemini_service.generate_query_embedding(query)
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

    results: list[dict] = []

    if entity in ("all", "incidents"):
        rows = await db.execute(
            text(
                "SELECT id, session_id::text, 'incident' AS entity_type, error_text,"
                "       (raw_json->>'title') AS title,"
                "       (raw_json->>'error_summary') AS error_summary,"
                "       markdown_content,"
                "       1 - (embedding <=> CAST(:embedding AS vector)) AS score"
                " FROM incidents"
                " WHERE embedding IS NOT NULL"
                " ORDER BY embedding <=> CAST(:embedding AS vector)"
                " LIMIT :limit"
            ),
            {"embedding": embedding_str, "limit": limit},
        )
        results.extend(dict(row) for row in rows.mappings())

    if entity in ("all", "documents"):
        rows = await db.execute(
            text(
                "SELECT id, 'document' AS entity_type, title,"
                "       markdown_content,"
                "       1 - (embedding <=> CAST(:embedding AS vector)) AS score"
                " FROM documents"
                " WHERE embedding IS NOT NULL"
                " ORDER BY embedding <=> CAST(:embedding AS vector)"
                " LIMIT :limit"
            ),
            {"embedding": embedding_str, "limit": limit},
        )
        results.extend(dict(row) for row in rows.mappings())

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:limit]


async def _hybrid_search(
    db: AsyncSession, query: str, entity: str, limit: int
) -> list[dict]:
    """Hybrid search using reciprocal rank fusion of BM25 + vector."""
    embedding = await gemini_service.generate_query_embedding(query)
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

    results: list[dict] = []

    if entity in ("all", "incidents"):
        rows = await db.execute(
            text(
                "WITH vector_search AS ("
                "    SELECT id, ROW_NUMBER() OVER ("
                "        ORDER BY embedding <=> CAST(:embedding AS vector)"
                "    ) AS rank"
                "    FROM incidents"
                "    WHERE embedding IS NOT NULL"
                "    ORDER BY embedding <=> CAST(:embedding AS vector)"
                "    LIMIT :limit"
                "),"
                " keyword_search AS ("
                "    SELECT id, ROW_NUMBER() OVER ("
                "        ORDER BY LEAST("
                "            error_text <@> to_bm25query(:query, 'idx_incidents_error_bm25'),"
                "            markdown_content <@> to_bm25query(:query, 'idx_incidents_markdown_bm25'),"
                "            notes <@> to_bm25query(:query, 'idx_incidents_notes_bm25')"
                "        )"
                "    ) AS rank"
                "    FROM incidents"
                "    WHERE error_text <@> to_bm25query(:query, 'idx_incidents_error_bm25') < 0"
                "       OR markdown_content <@> to_bm25query(:query, 'idx_incidents_markdown_bm25') < 0"
                "       OR notes <@> to_bm25query(:query, 'idx_incidents_notes_bm25') < 0"
                "    LIMIT :limit"
                ")"
                " SELECT i.id, i.session_id::text AS session_id, 'incident' AS entity_type, i.error_text,"
                "        (i.raw_json->>'title') AS title,"
                "        (i.raw_json->>'error_summary') AS error_summary,"
                "        i.markdown_content,"
                "        0.5 * COALESCE(1.0 / (60 + v.rank), 0.0) +"
                "        0.5 * COALESCE(1.0 / (60 + k.rank), 0.0) AS score"
                " FROM incidents i"
                " LEFT JOIN vector_search v ON i.id = v.id"
                " LEFT JOIN keyword_search k ON i.id = k.id"
                " WHERE v.id IS NOT NULL OR k.id IS NOT NULL"
                " ORDER BY score DESC"
                " LIMIT :limit"
            ),
            {"embedding": embedding_str, "query": query, "limit": limit},
        )
        results.extend(dict(row) for row in rows.mappings())

    if entity in ("all", "documents"):
        rows = await db.execute(
            text(
                "WITH vector_search AS ("
                "    SELECT id, ROW_NUMBER() OVER ("
                "        ORDER BY embedding <=> CAST(:embedding AS vector)"
                "    ) AS rank"
                "    FROM documents"
                "    WHERE embedding IS NOT NULL"
                "    ORDER BY embedding <=> CAST(:embedding AS vector)"
                "    LIMIT :limit"
                "),"
                " keyword_search AS ("
                "    SELECT id, ROW_NUMBER() OVER ("
                "        ORDER BY markdown_content <@> to_bm25query(:query, 'idx_documents_content_bm25')"
                "    ) AS rank"
                "    FROM documents"
                "    ORDER BY markdown_content <@> to_bm25query(:query, 'idx_documents_content_bm25')"
                "    LIMIT :limit"
                ")"
                " SELECT d.id, 'document' AS entity_type, d.title,"
                "        d.markdown_content,"
                "        0.5 * COALESCE(1.0 / (60 + v.rank), 0.0) +"
                "        0.5 * COALESCE(1.0 / (60 + k.rank), 0.0) AS score"
                " FROM documents d"
                " LEFT JOIN vector_search v ON d.id = v.id"
                " LEFT JOIN keyword_search k ON d.id = k.id"
                " WHERE v.id IS NOT NULL OR k.id IS NOT NULL"
                " ORDER BY score DESC"
                " LIMIT :limit"
            ),
            {"embedding": embedding_str, "query": query, "limit": limit},
        )
        results.extend(dict(row) for row in rows.mappings())

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:limit]
