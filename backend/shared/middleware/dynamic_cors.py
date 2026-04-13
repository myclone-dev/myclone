"""
Dynamic CORS Middleware for Custom Domains

This middleware extends FastAPI's CORSMiddleware to support dynamic origins.
It allows:
1. Static platform domains (configurable via CORS_ORIGINS env var)
2. Dynamic custom domains that are verified and active in the database

For custom domains, it performs a database lookup (with caching) to verify
that the origin is a legitimate custom domain before allowing the request.
"""

import logging
import os
import re
import time
from typing import Callable, Optional, Set

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


def _load_platform_origins() -> Set[str]:
    """Load platform origins from CORS_ORIGINS env var, with sensible local defaults."""
    defaults = {
        "http://localhost:3000",
        "http://localhost:4321",
        "http://localhost:8000",
    }
    extra = os.getenv("CORS_ORIGINS", "")
    if extra:
        for origin in extra.split(","):
            origin = origin.strip()
            if origin:
                defaults.add(origin)
    return defaults


# Static platform domains that are always allowed
PLATFORM_ORIGINS: Set[str] = _load_platform_origins()

# Headers that are explicitly allowed in CORS preflight requests
# Note: "*" doesn't work with credentials, so we list them explicitly
ALLOWED_HEADERS: list[str] = [
    "Accept",
    "Accept-Language",
    "Content-Language",
    "Content-Type",
    "Authorization",
    "X-Requested-With",
    "X-CSRF-Token",
    "X-Request-ID",
    "Cache-Control",
    "Pragma",
]

# Methods that are explicitly allowed in CORS preflight requests
# Note: "*" doesn't work with credentials, so we list them explicitly
ALLOWED_METHODS: list[str] = [
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
    "HEAD",
]

# Cache for custom domain lookups
# Key: domain (without protocol), Value: (is_valid, expires_at)
_custom_domain_cache: dict[str, tuple[bool, float]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def extract_domain_from_origin(origin: str) -> str:
    """Extract domain from origin URL (e.g., 'https://example.com' -> 'example.com')"""
    # Remove protocol
    domain = re.sub(r"^https?://", "", origin)
    # Remove port if present
    domain = domain.split(":")[0]
    return domain.lower()


def is_platform_origin(origin: str) -> bool:
    """Check if origin is a known platform domain"""
    return origin in PLATFORM_ORIGINS


async def is_valid_custom_domain(domain: str) -> bool:
    """
    Check if domain is a valid (active) custom domain in database.
    Uses caching to avoid repeated database lookups.

    Args:
        domain: Domain name without protocol (e.g., 'example.com')

    Returns:
        True if domain is an active custom domain, False otherwise
    """
    now = time.time()

    # Check cache first
    if domain in _custom_domain_cache:
        is_valid, expires_at = _custom_domain_cache[domain]
        if now < expires_at:
            logger.debug(f"CORS cache hit for {domain}: valid={is_valid}")
            return is_valid
        else:
            # Cache expired, remove it
            del _custom_domain_cache[domain]

    # Database lookup
    try:
        # Import here to avoid circular imports
        from shared.database.models.database import async_session_maker
        from shared.database.repositories.custom_domain_repository import CustomDomainRepository

        async with async_session_maker() as session:
            custom_domain = await CustomDomainRepository.get_active_by_domain(session, domain)
            is_valid = custom_domain is not None

            # Cache the result
            _custom_domain_cache[domain] = (is_valid, now + CACHE_TTL_SECONDS)

            if is_valid:
                logger.info(f"CORS: Custom domain '{domain}' verified and allowed")
            else:
                logger.debug(f"CORS: Domain '{domain}' not found or not active")

            return is_valid

    except Exception as e:
        logger.error(f"CORS: Error checking custom domain '{domain}': {e}")
        # Cache negative result to prevent repeated DB queries on errors
        # This prevents connection pool exhaustion under attack scenarios
        _custom_domain_cache[domain] = (False, now + CACHE_TTL_SECONDS)
        return False


def clear_custom_domain_cache(domain: Optional[str] = None):
    """
    Clear custom domain cache.

    Args:
        domain: If provided, clear only that domain. Otherwise clear all.
    """
    global _custom_domain_cache
    if domain:
        _custom_domain_cache.pop(domain, None)
        logger.debug(f"Cleared CORS cache for domain: {domain}")
    else:
        _custom_domain_cache.clear()
        logger.debug("Cleared entire CORS cache")


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """
    Middleware that handles CORS with dynamic origin validation.

    Supports:
    - Static platform domains (always allowed)
    - Dynamic custom domains (validated against database)
    """

    def __init__(
        self,
        app: ASGIApp,
        allow_credentials: bool = True,
        allow_methods: list[str] = None,
        allow_headers: list[str] = None,
        expose_headers: list[str] = None,
        max_age: int = 600,
    ):
        super().__init__(app)
        self.allow_credentials = allow_credentials
        self.allow_methods = allow_methods or ["*"]
        self.allow_headers = allow_headers or ["*"]
        self.expose_headers = expose_headers or []
        self.max_age = max_age

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        origin = request.headers.get("origin")

        # No origin header = same-origin request, allow it
        if not origin:
            return await call_next(request)

        # Check if origin is allowed
        is_allowed = await self._is_origin_allowed(origin)

        # Handle preflight requests
        if request.method == "OPTIONS":
            if is_allowed:
                return self._preflight_response(origin)
            else:
                # Return 200 without CORS headers - browser will handle rejection
                # This is standard CORS behavior and results in clearer browser error messages
                return Response(content="", status_code=200)

        # Handle actual requests
        response = await call_next(request)

        if is_allowed:
            self._add_cors_headers(response, origin)

        return response

    async def _is_origin_allowed(self, origin: str) -> bool:
        """Check if the origin is allowed (platform or valid custom domain)"""
        # Check platform origins first (fast path)
        if is_platform_origin(origin):
            return True

        # Check if it's a valid custom domain
        domain = extract_domain_from_origin(origin)
        return await is_valid_custom_domain(domain)

    def _preflight_response(self, origin: str) -> Response:
        """Create a preflight response with CORS headers"""
        # When credentials are involved, "*" doesn't work for headers/methods
        # We must explicitly list them
        allowed_headers = (
            ", ".join(ALLOWED_HEADERS)
            if self.allow_headers == ["*"]
            else ", ".join(self.allow_headers)
        )
        allowed_methods = (
            ", ".join(ALLOWED_METHODS)
            if self.allow_methods == ["*"]
            else ", ".join(self.allow_methods)
        )

        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": allowed_methods,
            "Access-Control-Allow-Headers": allowed_headers,
            "Access-Control-Max-Age": str(self.max_age),
        }

        if self.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"

        if self.expose_headers:
            headers["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)

        return Response(
            content="",
            status_code=200,
            headers=headers,
        )

    def _add_cors_headers(self, response: Response, origin: str) -> None:
        """Add CORS headers to a response"""
        response.headers["Access-Control-Allow-Origin"] = origin

        if self.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"

        if self.expose_headers:
            response.headers["Access-Control-Expose-Headers"] = ", ".join(self.expose_headers)
