import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db, async_session
from models.database import Expert, ExpertDocument, Prompt
from models.schemas import ExpertCreate, ExpertUpdate
from security import require_api_key, sanitize_filename, validate_file_upload, rate_limit
from services.gemini import gemini_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _expert_to_dict(expert: Expert, doc_count: int = 0, store_doc_count: int = 0) -> dict:
    d = expert.to_dict()
    d["document_count"] = doc_count
    d["store_document_count"] = store_doc_count
    return d


# -----------------------------------------------------------------------
# File Search Stores – Gemini-level management
# (MUST come before parameterized /experts/{expert_id} routes)
# -----------------------------------------------------------------------


@router.get("/experts/file-stores", dependencies=[Depends(require_api_key)])
async def list_file_stores():
    """List all Gemini file search stores owned by the API key."""
    try:
        stores = await gemini_service.list_file_search_stores()
        return stores
    except Exception as exc:
        logger.error("Failed to list file search stores: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to list file search stores")


# -----------------------------------------------------------------------
# Experts CRUD
# -----------------------------------------------------------------------


@router.get("/experts", dependencies=[Depends(require_api_key)])
async def list_experts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Expert, func.count(ExpertDocument.id).label("doc_count"))
        .outerjoin(ExpertDocument, Expert.id == ExpertDocument.expert_id)
        .group_by(Expert.id)
        .order_by(Expert.name)
    )
    rows = result.all()

    async def _store_count(store_name: str | None) -> int:
        if not store_name:
            return 0
        try:
            docs = await gemini_service.list_store_documents(store_name)
            return len(docs)
        except Exception:
            return 0

    store_counts = await asyncio.gather(
        *[_store_count(row.Expert.file_search_store_name) for row in rows]
    )
    return [
        _expert_to_dict(row.Expert, row.doc_count, sc)
        for row, sc in zip(rows, store_counts)
    ]


@router.get("/experts/{expert_id}", dependencies=[Depends(require_api_key)])
async def get_expert(expert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    expert = result.scalar_one_or_none()
    if not expert:
        raise HTTPException(status_code=404, detail="Expert not found")

    doc_result = await db.execute(
        select(func.count(ExpertDocument.id)).where(
            ExpertDocument.expert_id == expert_id
        )
    )
    doc_count = doc_result.scalar() or 0

    store_doc_count = 0
    if expert.file_search_store_name:
        try:
            docs = await gemini_service.list_store_documents(
                expert.file_search_store_name
            )
            store_doc_count = len(docs)
        except Exception:
            pass

    return _expert_to_dict(expert, doc_count, store_doc_count)


@router.post("/experts", dependencies=[Depends(require_api_key)])
async def create_expert(body: ExpertCreate, db: AsyncSession = Depends(get_db)):

    async def event_stream():
        """SSE generator that yields progress events during expert creation."""

        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        total_steps = 5  # store + expert + grounded prompts + file_search prompts + save
        step = 0

        # Step 1: Create file search store
        step += 1
        yield sse("progress", {"step": step, "total": total_steps, "message": "Creating file search store…"})
        store_name = None
        try:
            store_name = await gemini_service.create_file_search_store(
                f"expert-{body.name}"
            )
            logger.info(
                "Created file search store: %s for expert: %s",
                store_name,
                body.name,
            )
        except Exception as exc:
            logger.warning("Could not create file search store: %s", exc)

        # Step 2: Create expert record
        step += 1
        yield sse("progress", {"step": step, "total": total_steps, "message": "Creating expert record…"})
        expert = Expert(
            name=body.name,
            description=body.description,
            file_search_store_name=store_name,
        )
        db.add(expert)
        await db.flush()
        await db.refresh(expert)

        # Load global (no-expert) prompts as templates
        global_prompts = await db.execute(
            select(Prompt).where(Prompt.expert_id.is_(None))
        )
        global_list = global_prompts.scalars().all()

        # Group templates by category (grounded vs file_search)
        templates_by_cat: dict[str, dict[str, str]] = {}
        for gp in global_list:
            cat = gp.prompt_category
            if cat not in templates_by_cat:
                templates_by_cat[cat] = {}
            templates_by_cat[cat][gp.prompt_type] = gp.content

        # Steps 3-4: Generate domain-specific prompts for EACH category
        generated: dict[str, dict[str, str]] = {}
        category_labels = {"grounded": "grounded (model knowledge)", "file_search": "file search (RAG)"}
        if body.description.strip():
            for cat, tpls in templates_by_cat.items():
                step += 1
                label = category_labels.get(cat, cat)
                yield sse("progress", {"step": step, "total": total_steps, "message": f"Generating {label} prompts…"})
                sys_tpl = tpls.get("system", "")
                usr_tpl = tpls.get("user", "")
                if not sys_tpl:
                    continue
                try:
                    result = await gemini_service.generate_expert_prompts(
                        expert_name=body.name,
                        expert_description=body.description,
                        system_template=sys_tpl,
                        user_template=usr_tpl,
                        category=cat,
                    )
                    generated[cat] = result
                    logger.info(
                        "LLM generated tailored %s prompts for expert '%s'",
                        cat, body.name,
                    )
                except Exception as exc:
                    logger.warning(
                        "LLM prompt generation failed for expert '%s' (%s): %s — falling back to template",
                        body.name, cat, exc,
                    )
        else:
            # No description — skip LLM generation, fast-forward steps
            step += 2

        # Step 5: Save prompt records
        step = total_steps
        yield sse("progress", {"step": step, "total": total_steps, "message": "Saving prompts…"})
        for gp in global_list:
            cat_generated = generated.get(gp.prompt_category, {})
            if gp.prompt_type == "system" and "system_prompt" in cat_generated:
                content = cat_generated["system_prompt"]
            elif gp.prompt_type == "user" and "user_prompt" in cat_generated:
                content = cat_generated["user_prompt"]
            else:
                content = gp.content
            prompt_name = f"{body.name} - {gp.prompt_type.capitalize()} ({gp.prompt_category})"
            db.add(
                Prompt(
                    name=prompt_name,
                    prompt_type=gp.prompt_type,
                    prompt_category=gp.prompt_category,
                    content=content,
                    expert_id=expert.id,
                )
            )

        await db.commit()
        yield sse("done", _expert_to_dict(expert, 0))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.put("/experts/{expert_id}", dependencies=[Depends(require_api_key)])
async def update_expert(
    expert_id: int, body: ExpertUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    expert = result.scalar_one_or_none()
    if not expert:
        raise HTTPException(status_code=404, detail="Expert not found")

    if body.name is not None:
        expert.name = body.name
    if body.description is not None:
        expert.description = body.description
    if body.is_active is not None:
        expert.is_active = body.is_active
    expert.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(expert)

    doc_result = await db.execute(
        select(func.count(ExpertDocument.id)).where(
            ExpertDocument.expert_id == expert_id
        )
    )
    doc_count = doc_result.scalar() or 0
    return _expert_to_dict(expert, doc_count)


@router.post("/experts/{expert_id}/regenerate-prompts", dependencies=[Depends(require_api_key)])
async def regenerate_prompts(expert_id: int, db: AsyncSession = Depends(get_db)):
    """Regenerate AI-tailored prompts for an existing expert using the same
    logic as expert creation: load global prompt templates → run LLM for each
    category → overwrite existing expert prompts."""

    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    expert = result.scalar_one_or_none()
    if not expert:
        raise HTTPException(status_code=404, detail="Expert not found")

    if not expert.description or not expert.description.strip():
        raise HTTPException(
            status_code=400,
            detail="Expert has no description — add a description first so the AI can generate domain-specific prompts.",
        )

    async def event_stream():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        # Load global (no-expert) prompts as templates
        global_prompts = await db.execute(
            select(Prompt).where(Prompt.expert_id.is_(None))
        )
        global_list = global_prompts.scalars().all()

        if not global_list:
            yield sse("error", {"message": "No global prompt templates found"})
            return

        # Group templates by category (grounded vs file_search)
        templates_by_cat: dict[str, dict[str, str]] = {}
        for gp in global_list:
            cat = gp.prompt_category
            if cat not in templates_by_cat:
                templates_by_cat[cat] = {}
            templates_by_cat[cat][gp.prompt_type] = gp.content

        total_steps = len(global_list)  # one per individual prompt
        step = 0
        category_labels = {"grounded": "grounded (model knowledge)", "file_search": "file search (RAG)"}
        generated: dict[str, dict[str, str]] = {}

        for cat, tpls in templates_by_cat.items():
            label = category_labels.get(cat, cat)
            for ptype in sorted(tpls.keys()):  # system, then user
                step += 1
                yield sse("progress", {"step": step, "total": total_steps, "message": f"Generating {ptype} prompt ({label})…"})
            sys_tpl = tpls.get("system", "")
            usr_tpl = tpls.get("user", "")
            if not sys_tpl:
                continue
            try:
                gen_result = await gemini_service.generate_expert_prompts(
                    expert_name=expert.name,
                    expert_description=expert.description,
                    system_template=sys_tpl,
                    user_template=usr_tpl,
                    category=cat,
                )
                generated[cat] = gen_result
                logger.info(
                    "LLM regenerated tailored %s prompts for expert '%s'",
                    cat, expert.name,
                )
            except Exception as exc:
                logger.warning(
                    "LLM prompt regeneration failed for expert '%s' (%s): %s",
                    expert.name, cat, exc,
                )

        # Save: delete old expert prompts and insert new ones
        await db.execute(delete(Prompt).where(Prompt.expert_id == expert_id))

        for gp in global_list:
            cat_generated = generated.get(gp.prompt_category, {})
            if gp.prompt_type == "system" and "system_prompt" in cat_generated:
                content = cat_generated["system_prompt"]
            elif gp.prompt_type == "user" and "user_prompt" in cat_generated:
                content = cat_generated["user_prompt"]
            else:
                content = gp.content
            prompt_name = f"{expert.name} - {gp.prompt_type.capitalize()} ({gp.prompt_category})"
            db.add(
                Prompt(
                    name=prompt_name,
                    prompt_type=gp.prompt_type,
                    prompt_category=gp.prompt_category,
                    content=content,
                    expert_id=expert.id,
                )
            )

        await db.commit()
        yield sse("done", {"status": "ok", "categories": list(generated.keys())})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/experts/{expert_id}", dependencies=[Depends(require_api_key)])
async def delete_expert(expert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    expert = result.scalar_one_or_none()
    if expert and expert.file_search_store_name:
        try:
            await gemini_service.delete_file_search_store(
                expert.file_search_store_name
            )
        except Exception as exc:
            logger.warning("Could not delete file search store: %s", exc)

    await db.execute(delete(Prompt).where(Prompt.expert_id == expert_id))
    await db.execute(delete(Expert).where(Expert.id == expert_id))
    return {"status": "deleted"}


# -----------------------------------------------------------------------
# File Search Store details – per expert
# -----------------------------------------------------------------------


@router.get("/experts/{expert_id}/store-info", dependencies=[Depends(require_api_key)])
async def get_store_info(expert_id: int, db: AsyncSession = Depends(get_db)):
    """Get details of the expert's Gemini file search store."""
    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    expert = result.scalar_one_or_none()
    if not expert:
        raise HTTPException(status_code=404, detail="Expert not found")
    if not expert.file_search_store_name:
        raise HTTPException(status_code=404, detail="No file search store configured")

    try:
        info = await gemini_service.get_file_search_store(
            expert.file_search_store_name
        )
        return info
    except Exception as exc:
        logger.error("Failed to get store info: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to get store info")


@router.get("/experts/{expert_id}/store-documents", dependencies=[Depends(require_api_key)])
async def list_store_documents(
    expert_id: int, db: AsyncSession = Depends(get_db)
):
    """List documents in the expert's Gemini file search store."""
    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    expert = result.scalar_one_or_none()
    if not expert:
        raise HTTPException(status_code=404, detail="Expert not found")
    if not expert.file_search_store_name:
        raise HTTPException(status_code=404, detail="No file search store configured")

    try:
        docs = await gemini_service.list_store_documents(
            expert.file_search_store_name
        )
        return docs
    except Exception as exc:
        logger.error("Failed to list store documents: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to list store documents")


@router.delete("/experts/{expert_id}/store-documents/{document_name:path}", dependencies=[Depends(require_api_key)])
async def delete_store_document(
    expert_id: int, document_name: str, db: AsyncSession = Depends(get_db)
):
    """Delete a document directly from the Gemini file search store."""
    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    expert = result.scalar_one_or_none()
    if not expert:
        raise HTTPException(status_code=404, detail="Expert not found")

    try:
        await gemini_service.delete_file_search_document(
            expert.file_search_store_name or "", document_name
        )
    except Exception as exc:
        logger.warning("Could not delete from store: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to delete document from store")

    doc_result = await db.execute(
        select(ExpertDocument).where(
            ExpertDocument.expert_id == expert_id,
            ExpertDocument.gemini_file_name == document_name,
        )
    )
    doc = doc_result.scalar_one_or_none()
    if doc:
        await db.execute(
            delete(ExpertDocument).where(ExpertDocument.id == doc.id)
        )

    return {"status": "deleted"}


# -----------------------------------------------------------------------
# Expert Documents – upload / list / delete / sync
# -----------------------------------------------------------------------


@router.get("/experts/{expert_id}/documents", dependencies=[Depends(require_api_key)])
async def list_expert_documents(
    expert_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ExpertDocument)
        .where(ExpertDocument.expert_id == expert_id)
        .order_by(ExpertDocument.created_at.desc())
    )
    return [d.to_dict() for d in result.scalars().all()]


async def _background_upload_and_poll(
    doc_id: int, store_name: str, file_bytes: bytes, file_name: str
):
    """Background task: uploads file to Gemini then polls until indexed."""
    # 1. Start the upload
    try:
        op_result = await gemini_service.start_file_upload(
            store_name=store_name,
            file_bytes=file_bytes,
            file_name=file_name,
        )
    except Exception as exc:
        logger.error("Background upload failed for doc %d: %s", doc_id, exc)
        async with async_session() as session:
            db_result = await session.execute(
                select(ExpertDocument).where(ExpertDocument.id == doc_id)
            )
            doc = db_result.scalar_one_or_none()
            if doc:
                doc.status = "error"
                await session.commit()
        return

    # 2. Save operation info
    async with async_session() as session:
        db_result = await session.execute(
            select(ExpertDocument).where(ExpertDocument.id == doc_id)
        )
        doc = db_result.scalar_one_or_none()
        if not doc:
            return
        doc.operation_name = op_result.get("operation_name", "")
        if op_result["done"]:
            if op_result.get("error"):
                doc.status = "error"
                logger.error(
                    "Upload failed for doc %d: %s", doc_id, op_result["error"]
                )
            else:
                doc.status = "indexed"
                doc.gemini_file_name = op_result.get("document_name", "")
            await session.commit()
            return
        await session.commit()

    # 3. Poll until done
    operation_name = op_result.get("operation_name", "")
    max_polls = 120  # up to ~10 minutes
    for _ in range(max_polls):
        await asyncio.sleep(5)
        try:
            result = await gemini_service.poll_upload_operation(operation_name)
        except Exception as exc:
            logger.error("Poll error for doc %d: %s", doc_id, exc)
            break

        if result["done"]:
            async with async_session() as session:
                db_result = await session.execute(
                    select(ExpertDocument).where(ExpertDocument.id == doc_id)
                )
                doc = db_result.scalar_one_or_none()
                if doc:
                    if result.get("error"):
                        doc.status = "error"
                        logger.error(
                            "Upload failed for doc %d: %s",
                            doc_id,
                            result["error"],
                        )
                    else:
                        doc.status = "indexed"
                        doc.gemini_file_name = result.get("document_name", "")
                    await session.commit()
            return

    # Timed out
    logger.warning("Upload poll timed out for doc %d", doc_id)
    async with async_session() as session:
        db_result = await session.execute(
            select(ExpertDocument).where(ExpertDocument.id == doc_id)
        )
        doc = db_result.scalar_one_or_none()
        if doc and doc.status == "uploading":
            doc.status = "error"
            await session.commit()


@router.post("/experts/{expert_id}/documents", dependencies=[Depends(require_api_key)])
async def upload_expert_document(
    expert_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a file to the expert's Gemini file search store.

    Returns immediately with the document record in ``uploading`` status.
    The actual upload + polling happens entirely in a background task.
    """
    result = await db.execute(select(Expert).where(Expert.id == expert_id))
    expert = result.scalar_one_or_none()
    if not expert:
        raise HTTPException(status_code=404, detail="Expert not found")

    # Auto-create file search store if it doesn't exist yet
    if not expert.file_search_store_name:
        try:
            store_name = await gemini_service.create_file_search_store(
                f"expert-{expert.name}"
            )
            expert.file_search_store_name = store_name
            expert.updated_at = datetime.now(timezone.utc)
            await db.flush()
            await db.refresh(expert)
            logger.info(
                "Auto-created file search store %s for expert %s",
                store_name,
                expert.name,
            )
        except Exception as exc:
            logger.error("Failed to create file search store: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Could not create file search store",
            )

    file_bytes = await file.read()
    validate_file_upload(file.filename, len(file_bytes))
    safe_name = sanitize_filename(file.filename or "unnamed")
    file_size = len(file_bytes)

    doc = ExpertDocument(
        expert_id=expert_id,
        file_name=safe_name,
        file_size=file_size,
        status="uploading",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    doc_dict = doc.to_dict()

    background_tasks.add_task(
        _background_upload_and_poll,
        doc.id,
        expert.file_search_store_name,
        file_bytes,
        safe_name,
    )

    return doc_dict


@router.post("/experts/{expert_id}/documents/{doc_id}/sync", dependencies=[Depends(require_api_key)])
async def sync_document_status(
    expert_id: int, doc_id: int, db: AsyncSession = Depends(get_db)
):
    """Sync a document's status from its Gemini upload operation or store."""
    result = await db.execute(
        select(ExpertDocument).where(
            ExpertDocument.id == doc_id,
            ExpertDocument.expert_id == expert_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.operation_name and doc.status in ("uploading", "pending"):
        try:
            op_result = await gemini_service.poll_upload_operation(
                doc.operation_name
            )
            if op_result["done"]:
                if op_result.get("error"):
                    doc.status = "error"
                else:
                    doc.status = "indexed"
                    doc.gemini_file_name = op_result.get("document_name", "")
                await db.flush()
                await db.refresh(doc)
        except Exception as exc:
            logger.warning("Could not poll operation: %s", exc)

    elif doc.gemini_file_name:
        try:
            store_doc = await gemini_service.get_store_document(
                doc.gemini_file_name
            )
            state = store_doc.get("state", "")
            if "ACTIVE" in state:
                doc.status = "indexed"
            elif "PENDING" in state:
                doc.status = "uploading"
            elif "FAILED" in state:
                doc.status = "error"
            await db.flush()
            await db.refresh(doc)
        except Exception as exc:
            logger.warning("Could not get store document: %s", exc)

    return doc.to_dict()


@router.delete("/experts/{expert_id}/documents/{doc_id}", dependencies=[Depends(require_api_key)])
async def delete_expert_document(
    expert_id: int, doc_id: int, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ExpertDocument).where(
            ExpertDocument.id == doc_id,
            ExpertDocument.expert_id == expert_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.gemini_file_name:
        result_expert = await db.execute(
            select(Expert).where(Expert.id == expert_id)
        )
        expert = result_expert.scalar_one_or_none()
        if expert and expert.file_search_store_name:
            try:
                await gemini_service.delete_file_search_document(
                    expert.file_search_store_name, doc.gemini_file_name
                )
            except Exception as exc:
                logger.warning(
                    "Could not delete from file search store: %s", exc
                )

    await db.execute(
        delete(ExpertDocument).where(ExpertDocument.id == doc_id)
    )
    return {"status": "deleted"}
