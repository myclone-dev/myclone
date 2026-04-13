"""
SSE-compatible authentication middleware
Handles authentication for both regular HTTP requests and SSE connections
Simplified to use environment variable only (no database)
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.config import settings

logger = logging.getLogger(__name__)

# HTTP Bearer with auto_error=False to allow checking other auth methods
security = HTTPBearer(auto_error=False)


async def require_api_key_sse_compatible(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> bool:
    """
    SSE-compatible authentication that checks multiple sources

    Priority order:
    1. Query parameter (for SSE compatibility)
    2. Authorization header (for regular API calls)
    3. X-API-Key header (alternative header)

    This ensures SSE endpoints work while maintaining backward compatibility
    """

    # If API key requirement is disabled, allow all requests
    if not settings.require_api_key:
        logger.debug("API key requirement disabled - allowing request")
        return True

    api_key = None
    source = None

    # Priority 1: Check query parameter first (SSE-compatible)
    api_key_param = request.query_params.get("api_key")
    if api_key_param:
        api_key = api_key_param
        source = "query_param"
        logger.debug(f"API key found in query parameter: {api_key[:8]}...")

    # Priority 2: Check Authorization header if no query param
    if not api_key and credentials:
        api_key = credentials.credentials
        source = "auth_header"
        logger.debug(f"API key found in Authorization header: {api_key[:8]}...")

    # Priority 3: Check X-API-Key header
    if not api_key:
        x_api_key = request.headers.get("X-API-Key")
        if x_api_key:
            api_key = x_api_key
            source = "x_api_key_header"
            logger.debug(f"API key found in X-API-Key header: {api_key[:8]}...")

    # No API key found in any location
    if not api_key:
        logger.error("API key required but not provided in any supported location")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide via: query param (?api_key=...), Authorization header (Bearer ...), or X-API-Key header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Log warning for query param usage (less secure)
    if source == "query_param":
        logger.warning(
            "API key provided via query parameter - consider using headers for non-SSE endpoints"
        )

    # Verify the API key against environment variable
    if settings.api_key and api_key == settings.api_key:
        logger.debug(f"API key validated against environment variable via {source}")
        return True

    logger.error(f"Invalid API key provided: {api_key[:8]}... (source: {source})")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )
