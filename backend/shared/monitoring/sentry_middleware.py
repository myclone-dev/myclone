"""
FastAPI middleware for automatic Sentry context enrichment.

Extracts context from:
- JWT tokens (user_id, email)
- Path parameters (persona_id, user_id)
- Request metadata (URL, method, client IP)
"""

import logging
from typing import Callable

import sentry_sdk
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class SentryContextMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically enrich Sentry context from requests."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and enrich Sentry context."""

        # 1. Extract user context from JWT (if authenticated)
        if hasattr(request.state, "user") and request.state.user:
            sentry_sdk.set_user(
                {
                    "id": str(request.state.user.id),
                    "email": request.state.user.email,
                    "username": getattr(request.state.user, "username", None),
                }
            )

        # 2. Extract persona_id from path params (if present)
        # Handles routes like: /api/v1/personas/{persona_id}/...
        path_params = request.path_params
        if "persona_id" in path_params:
            sentry_sdk.set_tag("persona_id", path_params["persona_id"])

        if "user_id" in path_params:
            sentry_sdk.set_tag("target_user_id", path_params["user_id"])

        # 3. Add request metadata
        sentry_sdk.set_context(
            "request",
            {
                "url": str(request.url),
                "method": request.method,
                "path": request.url.path,
                "client_host": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )

        # 4. Add breadcrumb for request start
        sentry_sdk.add_breadcrumb(
            message=f"{request.method} {request.url.path}",
            category="http.request",
            level="info",
            data={
                "method": request.method,
                "url": str(request.url),
            },
        )

        try:
            response = await call_next(request)
            return response
        except Exception as e:
            # Exception will be auto-captured by Sentry FastAPI integration
            # This catch is just for logging/cleanup
            logger.error(f"Unhandled exception in request: {e}")
            raise
        finally:
            # Clear user context after request
            sentry_sdk.set_user(None)
