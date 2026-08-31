import base64
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from security import require_api_key, rate_limit
from services.gemini import gemini_service
from services.llm_logger import llm_logger

router = APIRouter()


class ImageGenerationRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "4:3"
    model: str = "gemini-2.5-flash-image"
    image_size: str = "1K"  # 1K, 2K, or 4K


class ImageGenerationResponse(BaseModel):
    image_data: str  # Base64 encoded image
    prompt_used: str


@router.post(
    "/generate-infographic",
    response_model=ImageGenerationResponse,
    dependencies=[Depends(require_api_key), Depends(rate_limit(10, 60))],
)
async def generate_infographic(
    request: ImageGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate an infographic using Gemini's Imagen API."""
    log_event = await llm_logger.create_event(
        db,
        "image",
        metadata={
            "model": request.model,
            "aspect_ratio": request.aspect_ratio,
            "image_size": request.image_size,
        },
    )

    _start = time.monotonic()
    try:
        image_bytes, enhanced_prompt = await gemini_service.generate_infographic(
            prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
            model=request.model,
            image_size=request.image_size,
        )
        _duration_ms = int((time.monotonic() - _start) * 1000)

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        await llm_logger.log_call(
            db,
            log_event.id if log_event else None,
            0,
            "image",
            request.model,
            prompt_text=request.prompt,
            is_image_call=True,
            image_data=image_base64,
            image_prompt=enhanced_prompt,
            total_duration_ms=_duration_ms,
            status="success",
        )
        await llm_logger.complete_event(db, log_event, status="success")

        return ImageGenerationResponse(
            image_data=image_base64,
            prompt_used=enhanced_prompt,
        )

    except Exception as e:
        _duration_ms = int((time.monotonic() - _start) * 1000)
        await llm_logger.log_call(
            db,
            log_event.id if log_event else None,
            0,
            "image",
            request.model,
            prompt_text=request.prompt,
            is_image_call=True,
            total_duration_ms=_duration_ms,
            status="failed",
            error_message=str(e),
        )
        await llm_logger.complete_event(db, log_event, status="failed")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate image: {str(e)}",
        )
