import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Patterns to strip before embedding so timestamps / dates don't
# reduce similarity between otherwise-identical errors.
_TIMESTAMP_PATTERNS = [
    # Day Mon DD HH:MM:SS YYYY  (e.g. Tue Feb 17 09:12:44 2026)
    r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4}",
    # ISO-style  YYYY-MM-DD[T ]HH:MM:SS
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?",
    # DD-Mon-YYYY HH:MM:SS (Oracle style, e.g. 17-FEB-2026 09:12:44)
    r"\d{1,2}-[A-Za-z]{3}-\d{4}\s+\d{2}:\d{2}:\d{2}",
    # Standalone time HH:MM:SS.nnn (only if preceded by whitespace/start)
    r"(?<=\s)\d{2}:\d{2}:\d{2}(?:\.\d+)?",
    # Standalone date YYYY-MM-DD or MM/DD/YYYY
    r"\d{4}-\d{2}-\d{2}",
    r"\d{1,2}/\d{1,2}/\d{4}",
]
_TIMESTAMP_RE = re.compile("|".join(_TIMESTAMP_PATTERNS))


def normalize_error_text(text: str) -> str:
    """Strip timestamps, collapse whitespace — produces a stable string
    that embeds the same regardless of when the error occurred."""
    out = _TIMESTAMP_RE.sub("", text)
    out = re.sub(r"\s+", " ", out).strip()
    return out


async def find_similar_incidents(
    db: AsyncSession,
    embedding: list[float],
    threshold: float = 0.85,
    limit: int = 3,
    exclude_id: int | None = None,
) -> list[dict]:
    """Query pgvector for similar past incidents. Called before the LLM call.
    Only matches incidents that have been analyzed (have markdown_content)."""
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

    where_clauses = [
        "embedding IS NOT NULL",
        "markdown_content IS NOT NULL",
        "markdown_content != ''",
    ]
    if exclude_id is not None:
        where_clauses.append(f"id != {int(exclude_id)}")
    where_sql = " AND ".join(where_clauses)

    result = await db.execute(
        text(
            "SELECT id, session_id::text, error_text, markdown_content, raw_json,"
            "       1 - (embedding <=> CAST(:embedding AS vector)) AS similarity"
            " FROM incidents"
            f" WHERE {where_sql}"
            " ORDER BY embedding <=> CAST(:embedding AS vector)"
            " LIMIT :limit"
        ),
        {"embedding": embedding_str, "limit": limit},
    )
    results: list[dict] = []
    for row in result.mappings():
        sim = float(row["similarity"])
        if sim >= threshold:
            rj = row["raw_json"] or {}
            results.append(
                {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "error_text": row["error_text"],
                    "title": rj.get("title") if isinstance(rj, dict) else None,
                    "markdown_content": row["markdown_content"],
                    "similarity": sim,
                }
            )
    return results
