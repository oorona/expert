import json
import logging
import uuid as uuid_mod
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.database import Expert, Incident, OutputSchema, Prompt, RelatedIncident
from security import (
    MAX_ERROR_TEXT_LENGTH,
    rate_limit,
    require_api_key,
    validate_image,
    validate_model,
    validate_temperature,
    validate_thinking_level,
)
from services.gemini import gemini_service
from services.similarity import find_similar_incidents, normalize_error_text

logger = logging.getLogger(__name__)

router = APIRouter()


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
                    # Structured step with action + command
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

        total_steps = 5
        step = 0

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

        # Duplicate detection
        if similar and not force:
            best = similar[0]
            if best["similarity"] >= 0.90:
                yield sse("done", {"duplicate_of": best})
                return

        # Step 2: Load prompts & schema
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

        result = await db.execute(
            select(OutputSchema)
            .where(OutputSchema.is_active == True)  # noqa: E712
            .order_by(OutputSchema.id)
            .limit(1)
        )
        schema_row = result.scalar_one_or_none()
        output_schema = schema_row.schema_json if schema_row else None
        user_prompt = user_template.replace("{error_text}", error_text)

        file_search_store_names: list[str] | None = None
        if use_file_search and expert_id:
            result = await db.execute(
                select(Expert).where(Expert.id == expert_id)
            )
            expert = result.scalar_one_or_none()
            if expert and expert.file_search_store_name:
                file_search_store_names = [expert.file_search_store_name]

        # Step 3: Call Gemini LLM (streaming thoughts)
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

        # Step 4: Generate markdown
        step += 1
        yield sse("progress", {"step": step, "total": total_steps, "message": "Generating report…"})

        # Add expert_id to raw_json so it's saved with the incident
        llm_result["raw_json"]["expert_id"] = expert_id
        markdown = _json_to_markdown(llm_result["raw_json"])

        # Step 5: Save to database
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
            await db.flush()
            await db.refresh(incident)
        else:
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
            )
            db.add(incident)
            await db.flush()
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
        })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
