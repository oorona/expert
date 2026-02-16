import difflib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.database import ChatMessage, Incident, Prompt
from security import (
    MAX_CHAT_MESSAGE_LENGTH,
    rate_limit,
    require_api_key,
    validate_model,
    validate_temperature,
)
from services.gemini import gemini_service

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=MAX_CHAT_MESSAGE_LENGTH)
    model: str = "gemini-2.5-flash"
    temperature: float = 1.0
    request_update: bool = False


@router.post("/chat/{incident_id}", dependencies=[Depends(require_api_key), Depends(rate_limit(20, 60))])
async def send_chat_message(
    incident_id: int, body: ChatRequest, db: AsyncSession = Depends(get_db)
):
    # Validate model and temperature
    validate_model(body.model)
    validate_temperature(body.temperature)

    # Load incident
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Load chat history
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.incident_id == incident_id)
        .order_by(ChatMessage.created_at)
    )
    chat_rows = result.scalars().all()

    # Load system prompt
    result = await db.execute(
        select(Prompt)
        .where(Prompt.prompt_type == "system", Prompt.is_active == True)  # noqa: E712
        .order_by(Prompt.id)
        .limit(1)
    )
    system_row = result.scalar_one_or_none()
    system_prompt = (
        system_row.content if system_row else "You are a diagnostic expert."
    )

    # Build history with original diagnosis as first assistant message
    history = [
        {"role": "user", "content": f"Error: {incident.error_text}"},
        {"role": "model", "content": incident.markdown_content},
    ]
    for msg in chat_rows:
        history.append(
            {
                "role": "user" if msg.role == "user" else "model",
                "content": msg.content,
            }
        )

    # Call Gemini
    llm_result = await gemini_service.chat_followup(
        system_prompt=system_prompt,
        history=history,
        user_message=body.message,
        model=body.model,
        temperature=body.temperature,
    )

    # Generate diff if this is an update request
    diff_content = None
    if body.request_update:
        diff_lines = list(
            difflib.unified_diff(
                incident.markdown_content.splitlines(keepends=True),
                llm_result["content"].splitlines(keepends=True),
                fromfile="original",
                tofile="updated",
            )
        )
        diff_content = "".join(diff_lines) if diff_lines else None

    # Save user message
    db.add(
        ChatMessage(
            incident_id=incident_id,
            role="user",
            content=body.message,
            token_usage={},
        )
    )

    # Save assistant response
    assistant_msg = ChatMessage(
        incident_id=incident_id,
        role="assistant",
        content=llm_result["content"],
        diff_content=diff_content,
        token_usage=llm_result["usage"],
    )
    db.add(assistant_msg)
    await db.flush()
    await db.refresh(assistant_msg)

    return {
        "id": assistant_msg.id,
        "role": "assistant",
        "content": llm_result["content"],
        "diff_content": diff_content,
        "token_usage": llm_result["usage"],
        "created_at": assistant_msg.created_at.isoformat(),
    }
