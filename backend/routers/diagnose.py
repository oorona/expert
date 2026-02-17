import json
import logging
import uuid as uuid_mod
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.exc import InternalError
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.database import Expert, Incident, OutputSchema, Prompt, RelatedIncident, Schema
from security import (
    MAX_ERROR_TEXT_LENGTH,
    rate_limit,
    require_api_key,
    validate_image,
    validate_model,
    validate_temperature,
    validate_thinking_level,
)
from services.classification import classification_service
from services.gemini import gemini_service
from services.similarity import find_similar_incidents, normalize_error_text

logger = logging.getLogger(__name__)

router = APIRouter()


async def _repair_corrupted_embeddings(db: AsyncSession) -> int:
    """Null out any incident embedding that has corrupted TOAST data.
    Returns number of rows repaired."""
    result = await db.execute(text("""
        DO $$
        DECLARE
            r RECORD;
            repaired INT := 0;
        BEGIN
            FOR r IN SELECT id FROM incidents WHERE embedding IS NOT NULL ORDER BY id LOOP
                BEGIN
                    PERFORM embedding FROM incidents WHERE id = r.id;
                EXCEPTION WHEN others THEN
                    UPDATE incidents SET embedding = NULL WHERE id = r.id;
                    repaired := repaired + 1;
                END;
            END LOOP;
        END;
        $$
    """))
    await db.commit()
    return 0  # PL/pgSQL doesn't return, but repair is done


def _json_to_markdown(data: dict) -> str:
    """Convert structured JSON output to readable markdown."""
    lines: list[str] = []
    for key, value in data.items():
        if key == "title":
            continue  # title is metadata, not a content section
        header = key.replace("_", " ").title()
        lines.append(f"## {header}")
        lines.append("")  # blank line after heading
        if isinstance(value, list):
            for i, item in enumerate(value, 1):
                if isinstance(item, dict) and "action" in item:
                    lines.append(f"{i}. {item['action']}")
                    if item.get("command"):
                        lines.append("")
                        lines.append("```")
                        lines.append(item["command"])
                        lines.append("```")
                    lines.append("")
                elif isinstance(item, dict):
                    for k, v in item.items():
                        lines.append(f"- **{k}**: {v}")
                else:
                    # Use numbered list for steps-like arrays
                    if key in ("resolution_steps", "preventive_measures"):
                        lines.append(f"{i}. {item}")
                    else:
                        lines.append(f"- {item}")
            lines.append("")  # blank line after list
        elif isinstance(value, dict):
            for k, v in value.items():
                lines.append(f"**{k}**: {v}")
            lines.append("")  # blank line
        else:
            lines.append(str(value))
            lines.append("")  # blank line after text
    return "\n".join(lines)


@router.post("/diagnose", dependencies=[Depends(require_api_key), Depends(rate_limit(15, 60))])
async def diagnose_error(
    error_text: str = Form(""),
    image: Optional[UploadFile] = File(None),
    model: str = Form("gemini-2.5-flash"),
    temperature: float = Form(1.0),
    thinking_level: str = Form("medium"),
    use_grounding: bool = Form(True),
    use_file_search: bool = Form(False),
    expert_id: int = Form(...),
    force: bool = Form(False),
    parent_session_id: Optional[str] = Form(None),
    incident_id: Optional[int] = Form(None),
    auto_classify: bool = Form(True),
    schema_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    # Validate inputs eagerly (before streaming)
    validate_model(model)
    validate_temperature(temperature)
    validate_thinking_level(thinking_level)

    if len(error_text) > MAX_ERROR_TEXT_LENGTH:
        raise HTTPException(400, f"Error text too long (max {MAX_ERROR_TEXT_LENGTH} chars)")

    # Read image bytes eagerly so the UploadFile is consumed before streaming
    image_bytes, image_mime = None, None
    if image and image.filename:
        image_bytes = await image.read()
        validate_image(image.content_type, len(image_bytes))
        image_mime = image.content_type

    async def event_stream():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        total_steps = 6 if (auto_classify and error_text and not schema_id) else 5
        step = 0

        classification_result = None
        selected_schema_id = schema_id  # Use override if provided
        selected_schema_name = None

        # Step 1: Check for similar incidents
        step += 1
        yield sse("progress", {"step": step, "total": total_steps, "message": "Checking for similar incidents…"})
        embedding = None
        similar: list[dict] = []
        if error_text:
            normalized = normalize_error_text(error_text)
            embedding = await gemini_service.generate_embedding(normalized)
            similar = await find_similar_incidents(
                db, embedding, exclude_id=incident_id
            )

        if similar and not force:
            best = similar[0]
            if best["similarity"] >= 0.90:
                yield sse("done", {"duplicate_of": best})
                return

        # Step 2 (optional): Classify input
        if auto_classify and error_text and not schema_id:
            step += 1
            yield sse("progress", {"step": step, "total": total_steps, "message": "Classifying input…"})
            try:
                classification_result = await classification_service.classify_input(
                    error_text, db, model=model
                )
                selected_schema_id, selected_schema_name = await classification_service.select_schema(
                    classification_result, db
                )
                logger.info(f"Auto-classified to schema: {selected_schema_name} (id={selected_schema_id})")
            except Exception as e:
                logger.warning(f"Classification failed, will use default schema: {e}")
                # Continue without classification - will use OutputSchema fallback

        # Step 3: Load prompts & schema
        step += 1
        yield sse("progress", {"step": step, "total": total_steps, "message": "Loading prompts & schema…"})

        prompt_category = "file_search" if use_file_search else "grounded"

        system_prompt_content = "You are a diagnostic expert."
        user_template = "Diagnose this error: {error_text}"

        result = await db.execute(
            select(Prompt).where(
                Prompt.prompt_type == "system",
                Prompt.prompt_category == prompt_category,
                Prompt.is_active == True,  # noqa: E712
                Prompt.expert_id == expert_id,
            ).order_by(Prompt.id).limit(1)
        )
        system_row = result.scalar_one_or_none()
        if not system_row:
            yield sse("error", {"message": f"No active system prompt found for expert {expert_id}"})
            return
        system_prompt_content = system_row.content

        result = await db.execute(
            select(Prompt).where(
                Prompt.prompt_type == "user",
                Prompt.prompt_category == prompt_category,
                Prompt.is_active == True,  # noqa: E712
                Prompt.expert_id == expert_id,
            ).order_by(Prompt.id).limit(1)
        )
        user_row = result.scalar_one_or_none()
        if not user_row:
            yield sse("error", {"message": f"No active user prompt found for expert {expert_id}"})
            return
        user_template = user_row.content

        output_schema = None
        if selected_schema_id:
            result = await db.execute(
                select(Schema).where(
                    Schema.id == selected_schema_id,
                    Schema.is_active == True  # noqa: E712
                )
            )
            schema_row = result.scalar_one_or_none()
            if schema_row:
                output_schema = schema_row.json_schema
                selected_schema_name = schema_row.name
                logger.info(f"Using schema: {selected_schema_name} (id={selected_schema_id})")

        # Fallback to old OutputSchema if no categorized schema
        if not output_schema:
            result = await db.execute(
                select(OutputSchema)
                .where(OutputSchema.is_active == True)  # noqa: E712
                .order_by(OutputSchema.id)
                .limit(1)
            )
            schema_row = result.scalar_one_or_none()
            output_schema = schema_row.schema_json if schema_row else None
            if schema_row:
                logger.info("Using legacy OutputSchema")
        user_prompt = user_template.replace("{error_text}", error_text)

        file_search_store_names: list[str] | None = None
        if use_file_search and expert_id:
            result = await db.execute(
                select(Expert).where(Expert.id == expert_id)
            )
            expert = result.scalar_one_or_none()
            if expert and expert.file_search_store_name:
                file_search_store_names = [expert.file_search_store_name]

        # Step 4: Call Gemini LLM (streaming thoughts)
        step += 1
        yield sse("progress", {"step": step, "total": total_steps, "message": "Analyzing with Gemini…"})

        llm_result = None
        async for item in gemini_service.diagnose_error_stream(
            error_text=error_text,
            image_bytes=image_bytes,
            image_mime=image_mime,
            system_prompt=system_prompt_content,
            user_prompt=user_prompt,
            output_schema=output_schema,
            model=model,
            temperature=temperature,
            thinking_level=thinking_level,
            use_grounding=use_grounding,
            use_file_search=use_file_search,
            file_search_store_names=file_search_store_names,
            expert_id=expert_id,
            prompt_category=prompt_category,
        ):
            if item["type"] == "thought":
                yield sse("thought", {"text": item["text"]})
            elif item["type"] == "result":
                llm_result = item["data"]

        if not llm_result:
            yield sse("error", {"message": "No result from Gemini"})
            return

        # Step 5: Generate markdown
        step += 1
        yield sse("progress", {"step": step, "total": total_steps, "message": "Generating report…"})

        # Add expert_id to raw_json so it's saved with the incident
        llm_result["raw_json"]["expert_id"] = expert_id
        markdown = _json_to_markdown(llm_result["raw_json"])

        # Step 6: Save to database
        step += 1
        yield sse("progress", {"step": step, "total": total_steps, "message": "Saving results…"})

        if incident_id:
            result = await db.execute(
                select(Incident).where(Incident.id == incident_id)
            )
            incident = result.scalar_one_or_none()
            if not incident:
                yield sse("error", {"message": f"Incident {incident_id} not found"})
                return
            incident.error_text = error_text
            incident.image_data = image_bytes
            incident.image_mime_type = image_mime
            incident.raw_json = llm_result["raw_json"]
            incident.markdown_content = markdown
            incident.embedding = embedding
            incident.embedding_version = 2
            incident.model_used = model
            incident.temperature = temperature
            incident.thinking_level = thinking_level
            incident.token_usage = llm_result["usage"]
            incident.grounding_sources = llm_result["sources"]
            incident.file_search_results = llm_result.get("file_search_results", [])
            incident.status = "analyzed"
            if classification_result:
                incident.categories = [
                    {
                        "category": cat["category"],
                        "confidence": cat["confidence"],
                        "primary": i == 0
                    }
                    for i, cat in enumerate(classification_result["categories"])
                ]
                incident.schema_id = selected_schema_id
                incident.classification_reasoning = classification_result.get("primary_intent")
            await db.flush()
            await db.refresh(incident)
        else:
            categories_json = []
            if classification_result:
                categories_json = [
                    {
                        "category": cat["category"],
                        "confidence": cat["confidence"],
                        "primary": i == 0
                    }
                    for i, cat in enumerate(classification_result["categories"])
                ]

            incident = Incident(
                error_text=error_text,
                image_data=image_bytes,
                image_mime_type=image_mime,
                raw_json=llm_result["raw_json"],
                markdown_content=markdown,
                embedding=embedding,
                embedding_version=2,
                model_used=model,
                temperature=temperature,
                thinking_level=thinking_level,
                token_usage=llm_result["usage"],
                grounding_sources=llm_result["sources"],
                file_search_results=llm_result.get("file_search_results", []),
                source="manual",
                status="resolved",
                categories=categories_json,
                schema_id=selected_schema_id,
                classification_reasoning=classification_result.get("primary_intent") if classification_result else None,
            )
            db.add(incident)
            try:
                await db.flush()
            except InternalError as e:
                if "missing chunk" in str(e) or "DataCorruptedError" in str(e):
                    logger.warning("TOAST corruption detected on insert — repairing corrupted embeddings and retrying")
                    await db.rollback()
                    await _repair_corrupted_embeddings(db)
                    # Retry without embedding to avoid the index touching corrupted rows
                    incident.embedding = None
                    db.add(incident)
                    await db.flush()
                else:
                    raise
            await db.refresh(incident)

        if parent_session_id:
            try:
                parent_uuid = uuid_mod.UUID(parent_session_id)
            except ValueError:
                parent_uuid = None
            if parent_uuid:
                parent_result = await db.execute(
                    select(Incident).where(Incident.session_id == parent_uuid)
                )
                parent = parent_result.scalar_one_or_none()
                if parent:
                    db.add(RelatedIncident(
                        incident_id=parent.id,
                        related_id=incident.id,
                        relation_type="followup",
                    ))
                    db.add(RelatedIncident(
                        incident_id=incident.id,
                        related_id=parent.id,
                        relation_type="parent",
                    ))
                    await db.flush()

        await db.commit()

        yield sse("done", {
            "incident_id": incident.id,
            "session_id": str(incident.session_id),
            "raw_json": llm_result["raw_json"],
            "markdown_content": markdown,
            "sources": llm_result["sources"],
            "file_search_results": llm_result.get("file_search_results", []),
            "usage": llm_result["usage"],
            "similar_incidents": similar,
            "classification": classification_result,
            "schema_used": {"id": selected_schema_id, "name": selected_schema_name} if selected_schema_id else None,
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
