"""
Security utilities: API key authentication, rate limiting, input validation.
"""

import logging
import os
import re
import time
from collections import defaultdict
from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API Key authentication
# ---------------------------------------------------------------------------

_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def _load_api_key() -> str:
    """Load the API key from Docker secret or env var, or generate one."""
    secret_path = "/run/secrets/api_key"
    if os.path.exists(secret_path):
        with open(secret_path, "r") as f:
            return f.read().strip()
    key = os.getenv("API_KEY", "")
    if not key:
        # If no key is configured, generate a random one and log it
        import secrets as _secrets

        key = _secrets.token_urlsafe(32)
        logger.warning(
            "No API_KEY configured — generated ephemeral key: %s",
            key,
        )
    return key


API_KEY = _load_api_key()


async def require_api_key(
    api_key: Optional[str] = Depends(_API_KEY_HEADER),
):
    """Dependency that enforces API key on protected endpoints."""
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


# ---------------------------------------------------------------------------
# Simple in-memory rate limiter (per IP)
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Token-bucket style rate limiter keyed by client IP."""

    def __init__(self):
        # {ip: [(timestamp, ...),]}
        self._requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, ip: str, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        # Prune old entries
        self._requests[ip] = [
            t for t in self._requests[ip] if t > cutoff
        ]
        if len(self._requests[ip]) >= max_requests:
            return False
        self._requests[ip].append(now)
        return True


_limiter = _RateLimiter()


def rate_limit(max_requests: int = 20, window_seconds: int = 60):
    """FastAPI dependency factory for rate limiting."""

    async def _check(request: Request):
        ip = request.client.host if request.client else "unknown"
        if not _limiter.is_allowed(ip, max_requests, window_seconds):
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
            )

    return _check


# ---------------------------------------------------------------------------
# Allowed models / parameters
# ---------------------------------------------------------------------------

ALLOWED_MODELS = {
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
}

ALLOWED_THINKING_LEVELS = {"off", "low", "medium", "high"}


def validate_model(model: str) -> str:
    if model not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Model not allowed. Use one of: {sorted(ALLOWED_MODELS)}",
        )
    return model


def validate_temperature(temperature: float) -> float:
    if temperature < 0.0 or temperature > 2.0:
        raise HTTPException(
            status_code=400,
            detail="Temperature must be between 0.0 and 2.0",
        )
    return temperature


def validate_thinking_level(level: str) -> str:
    if level not in ALLOWED_THINKING_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"Thinking level must be one of: {sorted(ALLOWED_THINKING_LEVELS)}",
        )
    return level


# ---------------------------------------------------------------------------
# File upload validation
# ---------------------------------------------------------------------------

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILE_SIZE = 50 * 1024 * 1024   # 50 MB

ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
ALLOWED_FILE_EXTENSIONS = {
    ".pdf", ".txt", ".md", ".docx", ".csv", ".json", ".xml",
    ".log", ".html", ".htm", ".yaml", ".yml",
}


def validate_image(content_type: Optional[str], size: int):
    """Validate an uploaded image file."""
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid image type '{content_type}'. Allowed: {sorted(ALLOWED_IMAGE_TYPES)}",
        )
    if size > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large ({size} bytes). Max: {MAX_IMAGE_SIZE} bytes (10 MB)",
        )


def validate_file_upload(filename: Optional[str], size: int):
    """Validate an uploaded document file."""
    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size} bytes). Max: {MAX_FILE_SIZE} bytes (50 MB)",
        )
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext and ext not in ALLOWED_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{ext}' not allowed. Allowed: {sorted(ALLOWED_FILE_EXTENSIONS)}",
            )


def sanitize_filename(filename: str) -> str:
    """Remove dangerous characters from a filename."""
    # Strip path components
    name = os.path.basename(filename)
    # Keep only safe characters
    name = re.sub(r"[^\w\-.]", "_", name)
    return name or "unnamed"


# ---------------------------------------------------------------------------
# Input length constants
# ---------------------------------------------------------------------------

MAX_ERROR_TEXT_LENGTH = 50_000      # 50 KB of error text
MAX_CHAT_MESSAGE_LENGTH = 20_000   # 20 KB per chat message
MAX_DOCUMENT_CONTENT_LENGTH = 500_000  # 500 KB of markdown
MAX_PROMPT_CONTENT_LENGTH = 100_000    # 100 KB for prompts
MAX_SLUG_LENGTH = 200
MAX_TITLE_LENGTH = 500
