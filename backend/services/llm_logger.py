"""LLM Observability Logger — records every LLM call to llm_events / llm_calls.

All methods swallow exceptions so that a logging failure never interrupts a
user-facing request.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from models.database import LLMCall, LLMEvent

logger = logging.getLogger(__name__)


class LLMLoggerService:
    """Thin service for creating event/call rows in the observability tables."""

    async def create_event(
        self,
        db: AsyncSession,
        event_type: str,
        entity_type: str | None = None,
        entity_id: int | None = None,
        session_id: str | None = None,
        metadata: dict | None = None,
    ) -> LLMEvent | None:
        """Insert a 'pending' event row and return the ORM object.

        Returns None on error so callers can safely do:
            event = await llm_logger.create_event(...)
            if event:
                ...
        """
        try:
            event = LLMEvent(
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                session_id=session_id,
                status="pending",
                metadata=metadata or {},
                started_at=datetime.now(timezone.utc),
            )
            db.add(event)
            await db.flush()  # get the id without committing
            return event
        except Exception:
            logger.warning("LLM logger: failed to create event", exc_info=True)
            return None

    async def complete_event(
        self,
        db: AsyncSession,
        event: LLMEvent | None,
        status: str = "success",
    ) -> None:
        """Set completed_at, duration_ms, and status on an event."""
        if event is None:
            return
        try:
            now = datetime.now(timezone.utc)
            event.completed_at = now
            event.status = status
            if event.started_at:
                delta_ms = int((now - event.started_at).total_seconds() * 1000)
                event.duration_ms = delta_ms
            await db.flush()
        except Exception:
            logger.warning("LLM logger: failed to complete event", exc_info=True)

    async def log_call(
        self,
        db: AsyncSession,
        event_id: int | None,
        call_index: int,
        call_type: str,
        model: str,
        *,
        temperature: float | None = None,
        thinking_level: str | None = None,
        extra_params: dict | None = None,
        prompt_name: str | None = None,
        prompt_text: str | None = None,
        response_text: str | None = None,
        is_streaming: bool = False,
        is_image_call: bool = False,
        image_data: str | None = None,
        image_prompt: str | None = None,
        usage: dict | None = None,
        time_to_first_token_ms: int | None = None,
        total_duration_ms: int | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> LLMCall | None:
        """Insert a call row and return the ORM object.

        Maps Gemini usage_metadata field names to our column names:
            prompt_token_count       → input_tokens
            candidates_token_count   → output_tokens
            cached_content_token_count → cache_read_tokens
            thoughts_token_count     → thinking_tokens
        """
        if event_id is None:
            return None
        try:
            u = usage or {}
            call = LLMCall(
                event_id=event_id,
                call_index=call_index,
                call_type=call_type,
                model=model,
                temperature=temperature,
                thinking_level=thinking_level,
                extra_params=extra_params or {},
                prompt_name=prompt_name,
                prompt_text=prompt_text,
                response_text=response_text,
                is_streaming=is_streaming,
                is_image_call=is_image_call,
                image_data=image_data,
                image_prompt=image_prompt,
                input_tokens=u.get("prompt_token_count", 0) or 0,
                output_tokens=u.get("candidates_token_count", 0) or 0,
                cache_read_tokens=u.get("cached_content_token_count", 0) or 0,
                cache_write_tokens=0,
                thinking_tokens=u.get("thoughts_token_count", 0) or 0,
                time_to_first_token_ms=time_to_first_token_ms,
                total_duration_ms=total_duration_ms,
                status=status,
                error_message=error_message,
            )
            db.add(call)
            await db.flush()
            return call
        except Exception:
            logger.warning("LLM logger: failed to log call", exc_info=True)
            return None


llm_logger = LLMLoggerService()
