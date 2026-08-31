import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from security import rate_limit, require_api_key
from services.classification import classification_service
from services.llm_logger import llm_logger

logger = logging.getLogger(__name__)

router = APIRouter()


class ClassifyRequest(BaseModel):
    user_input: str = Field(..., min_length=1, max_length=10000)
    model: str = Field("gemini-2.5-flash")


class CategoryResult(BaseModel):
    category: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str


class ExtractedEntities(BaseModel):
    error_codes: list[str] = Field(default_factory=list)
    system_components: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    action_verbs: list[str] = Field(default_factory=list)


class SchemaRecommendation(BaseModel):
    id: int
    name: str


class ClassifyResponse(BaseModel):
    primary_intent: str
    categories: list[CategoryResult]
    extracted_entities: Optional[ExtractedEntities] = None
    recommended_schema: SchemaRecommendation


@router.post(
    "/classify",
    response_model=ClassifyResponse,
    dependencies=[Depends(require_api_key), Depends(rate_limit(30, 60))],
    summary="Classify user input into categories",
    description="Analyze user input and classify it into 1-3 of the 20 predefined categories. Returns recommended schema for generating the response.",
)
async def classify_input(
    request: ClassifyRequest,
    db: AsyncSession = Depends(get_db),
) -> ClassifyResponse:
    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="user_input cannot be empty")

    log_event = await llm_logger.create_event(
        db,
        "classify",
        metadata={"model": request.model},
    )

    _start = time.monotonic()
    try:
        classification = await classification_service.classify_input(
            request.user_input, db, model=request.model
        )
        schema_id, schema_name = await classification_service.select_schema(
            classification, db
        )
        _duration_ms = int((time.monotonic() - _start) * 1000)

        await llm_logger.log_call(
            db,
            log_event.id if log_event else None,
            0,
            "text",
            request.model,
            temperature=0.3,
            thinking_level="off",
            prompt_name="classification_prompt",
            prompt_text=request.user_input,
            response_text=json.dumps(classification),
            total_duration_ms=_duration_ms,
            status="success",
        )
        await llm_logger.complete_event(db, log_event, status="success")

        return ClassifyResponse(
            primary_intent=classification["primary_intent"],
            categories=[
                CategoryResult(**cat) for cat in classification["categories"]
            ],
            extracted_entities=ExtractedEntities(
                **classification.get("extracted_entities", {})
            )
            if classification.get("extracted_entities")
            else None,
            recommended_schema=SchemaRecommendation(id=schema_id, name=schema_name),
        )

    except ValueError as e:
        _duration_ms = int((time.monotonic() - _start) * 1000)
        await llm_logger.log_call(
            db,
            log_event.id if log_event else None,
            0,
            "text",
            request.model,
            prompt_text=request.user_input,
            total_duration_ms=_duration_ms,
            status="failed",
            error_message=str(e),
        )
        await llm_logger.complete_event(db, log_event, status="failed")
        logger.error(f"Classification error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        _duration_ms = int((time.monotonic() - _start) * 1000)
        await llm_logger.log_call(
            db,
            log_event.id if log_event else None,
            0,
            "text",
            request.model,
            prompt_text=request.user_input,
            total_duration_ms=_duration_ms,
            status="failed",
            error_message=str(e),
        )
        await llm_logger.complete_event(db, log_event, status="failed")
        logger.error(f"Unexpected error during classification: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Classification failed. Please try again."
        )
