"""API key authentication for BSS SaaS."""

from __future__ import annotations

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from src.database import validate_api_key

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(_api_key_header)) -> dict:
    """FastAPI dependency: validate API key from X-API-Key header."""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    key_info = validate_api_key(api_key)
    if not key_info:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return key_info
