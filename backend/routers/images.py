from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import base64

from security import require_api_key, rate_limit
from services.gemini import gemini_service

router = APIRouter()


class ImageGenerationRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "4:3"  # Standard aspect ratio
    model: str = "gemini-2.5-flash-image"  # Default to Nano Banana (fast)
    image_size: str = "1K"  # 1K, 2K, or 4K


class ImageGenerationResponse(BaseModel):
    image_data: str  # Base64 encoded image
    prompt_used: str


@router.post("/generate-infographic", response_model=ImageGenerationResponse, dependencies=[Depends(require_api_key), Depends(rate_limit(10, 60))])
async def generate_infographic(request: ImageGenerationRequest):
    """
    Generate an infographic using Gemini's Imagen API.
    """
    try:
        # Use the shared gemini_service to generate the image
        image_bytes, enhanced_prompt = await gemini_service.generate_infographic(
            prompt=request.prompt,
            aspect_ratio=request.aspect_ratio,
            model=request.model,
            image_size=request.image_size
        )

        # Convert image bytes to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')

        return ImageGenerationResponse(
            image_data=image_base64,
            prompt_used=enhanced_prompt
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate image: {str(e)}"
        )
