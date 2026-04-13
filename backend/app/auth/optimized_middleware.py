"""
Optimized authentication middleware
Supports JWT (cookie-based), Widget Token, and API key (Bearer token) authentication
"""

import logging
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database.models.database import get_session

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


class OptimizedAuth:
    """Optimized authentication with environment variable validation"""

    @staticmethod
    def authenticate_request(credentials: HTTPAuthorizationCredentials) -> dict:
        """
        Authenticate using environment variable API key
        Returns: {"type": "api_key", "data": auth_data}
        """
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Provide API key in Authorization header.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = credentials.credentials

        # Check against environment variable
        if settings.api_key and token == settings.api_key:
            logger.debug(f"API key validated against environment variable: {token[:8]}...")
            return {"type": "api_key", "data": {"source": "environment"}}
        else:
            logger.warning(f"Invalid API key provided: {token[:8]}...")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


async def require_auth_optimized(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Optimized authentication dependency with widget token support
    """
    if not settings.require_api_key:
        logger.debug("Authentication disabled - allowing request")
        return {"type": "disabled", "data": None}

    # Check if this is a widget token
    if credentials and credentials.credentials.startswith("wgt_"):
        try:

            from app.auth.widget_token_service import WidgetTokenService
            from shared.database.repositories.user_repository import UserRepository

            # Extract username from request path
            path_parts = request.url.path.split("/")
            username_idx = path_parts.index("username") + 1 if "username" in path_parts else -1

            if username_idx > 0 and username_idx < len(path_parts):
                expected_username = path_parts[username_idx]

                # Validate widget token
                widget_token = await WidgetTokenService.validate_widget_token(
                    token=credentials.credentials,
                    expected_username=expected_username,
                    session=session,
                )

                if widget_token:
                    # Get user from widget token
                    user = await UserRepository.get_by_id(session, widget_token.user_id)
                    if user:
                        logger.debug(f"Widget token authenticated user: {user.email}")
                        return {
                            "type": "widget_token",
                            "data": {"user": user, "widget_token": widget_token},
                        }
            else:
                logger.warning("Widget token provided but no username in path")
        except Exception as e:
            logger.debug(f"Widget token authentication failed: {e}")

    return OptimizedAuth.authenticate_request(credentials)


async def require_api_key_only(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Require API key (same as require_auth_optimized now)
    """
    if not settings.require_api_key:
        return {"type": "disabled", "data": None}

    return OptimizedAuth.authenticate_request(credentials)


async def require_jwt_or_api_key(
    request: Request,
    myclone_token: Optional[str] = Cookie(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Support JWT (via cookie), Widget Token (via Bearer token), and API key (via Bearer token)

    Priority:
    1. If myclone_token cookie exists and is valid -> JWT auth (returns user)
    2. If Bearer token starts with 'wgt_' -> Widget token auth (returns user)
    3. Otherwise -> fall back to API key auth

    Returns:
        - {"type": "jwt", "data": {"user": User}} if JWT authenticated
        - {"type": "widget_token", "data": {"user": User, "widget_token": WidgetToken}} if widget authenticated
        - {"type": "api_key", "data": {"source": "environment"}} if API key authenticated
        - {"type": "disabled", "data": None} if auth disabled
    """
    # Try JWT authentication first (if cookie present)
    if myclone_token:
        try:
            from uuid import UUID

            from app.services.linkedin_oauth_service import LinkedInOAuthService
            from shared.database.repositories.user_repository import UserRepository

            # Verify JWT token
            payload = LinkedInOAuthService.verify_jwt_token(myclone_token)
            if payload:
                user_id = payload.get("user_id")
                if user_id:
                    # Get user from database
                    user = await UserRepository.get_by_id(session, UUID(user_id))
                    if user:
                        logger.debug(f"JWT authenticated user: {user.email}")
                        return {"type": "jwt", "data": {"user": user}}
        except Exception as e:
            logger.debug(f"JWT authentication failed, trying other methods: {e}")

    # Try widget token authentication (if Bearer token starts with wgt_)
    if credentials and credentials.credentials.startswith("wgt_"):
        try:
            from uuid import UUID

            from app.auth.widget_token_service import WidgetTokenService
            from shared.database.repositories.user_repository import UserRepository

            # Extract username from request path
            # Path format: /api/v1/personas/username/{username}/...
            path_parts = request.url.path.split("/")
            username_idx = path_parts.index("username") + 1 if "username" in path_parts else -1

            if username_idx > 0 and username_idx < len(path_parts):
                expected_username = path_parts[username_idx]

                # Validate widget token
                widget_token = await WidgetTokenService.validate_widget_token(
                    token=credentials.credentials,
                    expected_username=expected_username,
                    session=session,
                )

                if widget_token:
                    # Get user from widget token
                    user = await UserRepository.get_by_id(session, widget_token.user_id)
                    if user:
                        logger.debug(f"Widget token authenticated user: {user.email}")
                        return {
                            "type": "widget_token",
                            "data": {"user": user, "widget_token": widget_token},
                        }
            else:
                logger.warning("Widget token provided but no username in path")
        except Exception as e:
            logger.debug(f"Widget token authentication failed, falling back to API key: {e}")

    # Fall back to API key authentication
    if not settings.require_api_key:
        return {"type": "disabled", "data": None}

    return OptimizedAuth.authenticate_request(credentials)


# Convenience functions
def get_auth_data(auth_result: dict) -> Optional[dict]:
    """Extract auth data from auth result"""
    return auth_result.get("data")


def get_auth_type(auth_result: dict) -> str:
    """Get authentication type"""
    return auth_result.get("type", "unknown")
