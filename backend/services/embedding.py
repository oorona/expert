from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Document, Incident, VersionHistory
from services.gemini import gemini_service


async def update_document_with_embedding(
    db: AsyncSession,
    doc_id: int,
    title: str,
    markdown_content: str,
    previous_content: str,
):
    """Atomic: update markdown + re-generate embedding + record version history."""
    embedding = await gemini_service.generate_embedding(
        f"{title}\n{markdown_content}"
    )

    await db.execute(
        update(Document)
        .where(Document.id == doc_id)
        .values(
            title=title,
            markdown_content=markdown_content,
            embedding=embedding,
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        VersionHistory(
            entity_type="document",
            entity_id=doc_id,
            previous_content=previous_content,
            new_content=markdown_content,
        )
    )
    await db.flush()


async def update_incident_with_embedding(
    db: AsyncSession,
    incident_id: int,
    raw_json: dict,
    markdown_content: str,
    previous_markdown: str,
):
    """Atomic update for an incident's content + re-embed."""
    embedding = await gemini_service.generate_embedding(markdown_content)

    await db.execute(
        update(Incident)
        .where(Incident.id == incident_id)
        .values(
            raw_json=raw_json,
            markdown_content=markdown_content,
            embedding=embedding,
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        VersionHistory(
            entity_type="incident",
            entity_id=incident_id,
            previous_content=previous_markdown,
            new_content=markdown_content,
        )
    )
    await db.flush()
