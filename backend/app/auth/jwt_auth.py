"""
JWT authentication dependency for FastAPI routes
"""

import logging
from typing import Optional, Union

from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.linkedin_oauth_service import LinkedInOAuthService
from shared.config import settings
from shared.database.models.database import get_session
from shared.database.models.user import User
from shared.database.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


async def get_current_user(
    myclone_token: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    Dependency to get current authenticated user from JWT cookie or Authorization header

    Authentication priority:
    1. myclone_token cookie (PRIORITY)
    2. Authorization: Bearer <token> header (FALLBACK for iframe/widget contexts)

    Rejects widget tokens (wgt_*) - widget tokens are not supported here.

    Usage:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id, "email": user.email}
    """
    jwt_token = None

    # Priority 1: Cookie
    if myclone_token:
        jwt_token = myclone_token
        logger.debug("Authenticating via cookie")
    # Priority 2: Authorization header
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:]  # Remove "Bearer " prefix
        if token.startswith("wgt_"):
            raise HTTPException(
                status_code=401,
                detail="Widget tokens are not supported for user authentication. Use visitor JWT tokens instead.",
            )
        jwt_token = token
        logger.debug("Authenticating via Authorization header")

    if not jwt_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Verify JWT token
    payload = LinkedInOAuthService.verify_jwt_token(jwt_token)

    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("user_id")

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Get user from database
    try:
        from uuid import UUID

        user = await UserRepository.get_by_id(session, UUID(user_id))
    except Exception as e:
        logger.error(f"Error getting user from token: {e}")
        raise HTTPException(status_code=401, detail="User not found")

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_current_user_optional(
    myclone_token: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """
    Optional authentication - returns User if authenticated, None otherwise

    Supports same authentication methods as get_current_user:
    1. Cookie (priority)
    2. Authorization header (fallback)

    Usage:
        @router.get("/maybe-protected")
        async def route(user: Optional[User] = Depends(get_current_user_optional)):
            if user:
                return {"authenticated": True, "user_id": user.id}
            return {"authenticated": False}
    """
    if not myclone_token and not authorization:
        return None

    try:
        return await get_current_user(myclone_token, authorization, session)
    except HTTPException:
        return None


async def get_user_or_service(
    myclone_token: Optional[str] = Cookie(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session),
) -> Union[User, str]:
    """
    Dual authentication: Support both JWT (users) and API Key (services/operators).

    Returns:
        User object for JWT authentication
        "service" string for API key authentication

    Usage:
        @router.post("/endpoint")
        async def endpoint(
            request: RequestModel,
            auth: Union[User, str] = Depends(get_user_or_service)
        ):
            # Validate authorization
            if isinstance(auth, User):
                # User JWT auth - verify ownership
                if auth.id != request.user_id:
                    raise HTTPException(status_code=403, detail="Unauthorized")
            # else: auth == "service" - operators can act on behalf of any user

    Raises:
        HTTPException: 401 if neither JWT nor API key is valid
    """
    # Try JWT authentication first (from cookie or Authorization header)
    if myclone_token or authorization:
        try:
            user = await get_current_user(myclone_token, authorization, session)
            logger.debug(f"Authenticated via JWT: user_id={user.id}")
            return user
        except HTTPException:
            pass  # Fall through to API key check

    # Try API key authentication (from X-API-Key header or Authorization header)
    api_key = None

    # Check X-API-Key header
    if x_api_key:
        api_key = x_api_key

    # Check Authorization header (Bearer token)
    if not api_key and authorization and authorization.startswith("Bearer "):
        api_key = authorization[7:]  # Remove "Bearer " prefix

    # Validate API key against environment variable
    if api_key and settings.api_key and api_key == settings.api_key:
        logger.debug("Authenticated via API key (service account)")
        return "service"

    # No valid authentication found
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide JWT cookie or X-API-Key header.",
    )
