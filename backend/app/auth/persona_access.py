"""
Persona Access Control - Middleware for checking visitor access to private personas

This module provides FastAPI dependencies for validating visitor access to personas.
For private personas, visitors must:
1. Have a verified email (via OTP)
2. Be on the persona's visitor allowlist
3. Have a valid visitor cookie (14-day expiry)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Cookie, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.linkedin_oauth_service import LinkedInOAuthService
from shared.config import settings
from shared.database.models.database import Persona, get_session
from shared.database.models.persona_access import VisitorWhitelist
from shared.database.repositories import (
    get_persona_access_repository,
    get_visitor_whitelist_repository,
)

logger = logging.getLogger(__name__)

# Cookie settings
VISITOR_COOKIE_NAME = "myclone_visitor"
VISITOR_COOKIE_MAX_AGE = 14 * 24 * 60 * 60  # 14 days in seconds


async def check_persona_access(
    persona_id: UUID,
    visitor_token: Optional[str] = Cookie(None, alias=VISITOR_COOKIE_NAME),
    session: AsyncSession = Depends(get_session),
) -> tuple[Persona, Optional[VisitorWhitelist]]:
    """
    Check if access to persona is allowed

    This dependency:
    1. Loads the persona from database
    2. If persona is public (is_private=False), allows access immediately
    3. If persona is private, validates visitor cookie and checks allowlist
    4. Returns (persona, visitor) tuple

    Args:
        persona_id: Persona UUID
        visitor_token: Visitor JWT token from cookie
        session: Database session

    Returns:
        Tuple of (Persona, Optional[VisitorWhitelist])
        - visitor is None for public personas
        - visitor is VisitorWhitelist for private personas

    Raises:
        HTTPException 404: Persona not found
        HTTPException 403: Access denied (private persona, no valid visitor cookie)
    """
    try:
        # Load persona
        stmt = select(Persona).where(Persona.id == persona_id)
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")

        # Public personas: allow access immediately
        if not persona.is_private:
            logger.debug(f"Public persona {persona_id} - access granted")
            return persona, None

        # Private persona: require visitor authentication
        if not visitor_token:
            logger.warning(f"Private persona {persona_id} - no visitor cookie")
            raise HTTPException(
                status_code=403,
                detail="This persona is private. Please verify your email to access.",
            )

        # Verify visitor JWT token
        payload = LinkedInOAuthService.verify_jwt_token(visitor_token)

        if not payload:
            logger.warning(f"Private persona {persona_id} - invalid visitor token")
            raise HTTPException(
                status_code=403,
                detail="Your access has expired. Please verify your email again.",
            )

        visitor_id = payload.get("visitor_id")
        persona_id_from_token = payload.get("persona_id")

        if not visitor_id or not persona_id_from_token:
            logger.warning(f"Private persona {persona_id} - invalid token payload")
            raise HTTPException(
                status_code=403,
                detail="Invalid access token. Please verify your email again.",
            )

        # Verify token is for THIS persona
        if str(persona_id) != persona_id_from_token:
            logger.warning(
                f"Private persona {persona_id} - token is for different persona {persona_id_from_token}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access token is not valid for this persona.",
            )

        # Load visitor from database
        visitor_repo = get_visitor_whitelist_repository()
        visitor = await visitor_repo.get_visitor_by_id(UUID(visitor_id))

        if not visitor:
            logger.warning(f"Private persona {persona_id} - visitor {visitor_id} not found")
            raise HTTPException(
                status_code=403,
                detail="Visitor not found. Please verify your email again.",
            )

        # Check if visitor is still assigned to this persona
        persona_repo = get_persona_access_repository()
        is_allowed = await persona_repo.is_visitor_allowed(persona_id, visitor.email)

        if not is_allowed:
            logger.warning(
                f"Private persona {persona_id} - visitor {visitor.email} not on allowlist"
            )
            raise HTTPException(
                status_code=403,
                detail="You no longer have access to this persona.",
            )

        # Update last_accessed_at timestamp
        await visitor_repo.update_last_accessed(visitor.id)

        logger.info(f"Private persona {persona_id} - access granted to visitor {visitor.email}")
        return persona, visitor

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking persona access: {e}")
        raise HTTPException(status_code=500, detail="Failed to check persona access")


def set_visitor_cookie(response: Response, persona_id: UUID, visitor_id: UUID) -> None:
    """
    Set visitor authentication cookie (14-day expiry)

    Args:
        response: FastAPI Response object
        persona_id: Persona UUID
        visitor_id: Visitor UUID (from visitor_whitelist table)

    Cookie Behavior:
        - Scope: Exact host only (domain not set for security)
        - Widget Integration: Each domain (app.myclone.is, widget.example.com) gets separate cookie
        - This prevents cookie leakage across unrelated domains
        - Visitors must verify separately for each domain they access persona from
    """
    # Create JWT token with visitor_id and persona_id
    expires_at = datetime.now(timezone.utc) + timedelta(days=14)

    payload = {
        "visitor_id": str(visitor_id),
        "persona_id": str(persona_id),
        "exp": int(expires_at.timestamp()),
        "iat": datetime.now(timezone.utc),
    }

    # Encode JWT token directly (using same secret/algorithm as user tokens)
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    # Determine if we're in production (HTTPS required)
    is_production = settings.environment.lower() in ["production", "staging"]

    # Set httpOnly cookie (14-day expiry)
    response.set_cookie(
        key=VISITOR_COOKIE_NAME,
        value=token,
        max_age=VISITOR_COOKIE_MAX_AGE,
        httponly=True,  # Prevent XSS attacks
        secure=is_production,  # HTTPS only in production, allow HTTP in development
        samesite="lax",  # CSRF protection while allowing navigation
        # Domain is NOT set - cookie is scoped to exact host only
        # This means:
        # - app.myclone.is gets its own cookie
        # - api.myclone.is gets its own cookie
        # - widget.example.com gets its own cookie
        # Visitors must verify OTP separately per domain (security best practice)
        # To share cookies across subdomains: domain=settings.cookie_domain (e.g., ".myclone.is")
    )

    logger.info(
        f"Set visitor cookie for visitor {visitor_id} on persona {persona_id} "
        f"(secure={is_production})"
    )


def clear_visitor_cookie(response: Response) -> None:
    """
    Clear visitor authentication cookie

    Args:
        response: FastAPI Response object
    """
    response.delete_cookie(key=VISITOR_COOKIE_NAME)
    logger.info("Cleared visitor cookie")
