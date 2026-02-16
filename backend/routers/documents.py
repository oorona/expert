from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.database import Document
from models.schemas import DocumentCreate, DocumentUpdate
from security import require_api_key, rate_limit
from services.embedding import update_document_with_embedding
from services.gemini import gemini_service

router = APIRouter()


@router.get("/documents", dependencies=[Depends(require_api_key)])
async def list_documents(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Document)
        .order_by(Document.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [d.to_dict(exclude={"embedding"}) for d in result.scalars().all()]


@router.get("/documents/{slug}", dependencies=[Depends(require_api_key)])
async def get_document(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.slug == slug))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc.to_dict(exclude={"embedding"})


@router.post("/documents", dependencies=[Depends(require_api_key)])
async def create_document(body: DocumentCreate, db: AsyncSession = Depends(get_db)):
    embedding = await gemini_service.generate_embedding(
        f"{body.title}\n{body.markdown_content}"
    )
    doc = Document(
        slug=body.slug,
        title=body.title,
        markdown_content=body.markdown_content,
        embedding=embedding,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    return doc.to_dict(exclude={"embedding"})


@router.put("/documents/{doc_id}", dependencies=[Depends(require_api_key)])
async def update_document(
    doc_id: int, body: DocumentUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Document).where(Document.id == doc_id))
    current = result.scalar_one_or_none()
    if not current:
        raise HTTPException(status_code=404, detail="Document not found")

    title = body.title if body.title is not None else current.title
    content = (
        body.markdown_content
        if body.markdown_content is not None
        else current.markdown_content
    )

    # Atomic update: content + embedding + version history
    await update_document_with_embedding(
        db, doc_id, title, content, current.markdown_content
    )

    await db.refresh(current)
    return current.to_dict(exclude={"embedding"})


@router.delete("/documents/{doc_id}", dependencies=[Depends(require_api_key)])
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Document).where(Document.id == doc_id))
    return {"status": "deleted"}
