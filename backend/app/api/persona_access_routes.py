"""
Persona Access Routes - Public endpoints for visitor access to private personas

These endpoints handle the visitor flow:
1. GET /check-access - Check if visitor has active access (validates cookie)
2. POST /request-access - Visitor requests OTP via email
3. POST /verify-access - Visitor verifies OTP, gets access cookie
"""

import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_auth import get_current_user_optional
from app.auth.persona_access import VISITOR_COOKIE_NAME, set_visitor_cookie
from app.services.linkedin_oauth_service import LinkedInOAuthService
from app.services.otp_service import get_otp_service
from shared.database.models.database import Persona, get_session
from shared.database.models.user import User
from shared.database.repositories import (
    get_persona_access_repository,
    get_visitor_whitelist_repository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/personas/username", tags=["Persona Access"])


class RequestAccessRequest(BaseModel):
    """Request to access a private persona (sends OTP email)"""

    email: EmailStr = Field(..., description="Visitor's email address")
    first_name: Optional[str] = Field(None, max_length=100, alias="firstName")
    last_name: Optional[str] = Field(None, max_length=100, alias="lastName")

    class Config:
        populate_by_name = True  # Accept both camelCase and snake_case


class RequestAccessResponse(BaseModel):
    """Response from access request"""

    success: bool
    message: str


class VerifyAccessRequest(BaseModel):
    """Request to verify OTP and gain access"""

    email: EmailStr = Field(..., description="Visitor's email address")
    otp_code: str = Field(..., min_length=6, max_length=6, alias="otpCode")
    first_name: Optional[str] = Field(None, max_length=100, alias="firstName")
    last_name: Optional[str] = Field(None, max_length=100, alias="lastName")

    class Config:
        populate_by_name = True


class VerifyAccessResponse(BaseModel):
    """Response from access verification"""

    success: bool
    message: str
    visitor_name: Optional[str] = Field(None, alias="visitorName")


class CheckAccessResponse(BaseModel):
    """Response from access check"""

    has_access: bool = Field(..., description="Whether visitor has valid access", alias="hasAccess")
    is_private: bool = Field(..., description="Whether persona is private", alias="isPrivate")
    visitor_email: Optional[str] = Field(
        None, description="Visitor's email if authenticated", alias="visitorEmail"
    )
    message: str = Field(..., description="Human-readable status message")
    is_authenticated: bool = Field(
        False,
        description="Whether user is authenticated via JWT (logged-in user)",
        alias="isAuthenticated",
    )

    class Config:
        populate_by_name = True


@router.post("/{username}/request-access", response_model=RequestAccessResponse)
async def request_access(
    username: str,
    request: RequestAccessRequest,
    persona_name: str = "default",
    session: AsyncSession = Depends(get_session),
):
    """
    Request access to a private persona (sends OTP email)

    This endpoint:
    1. Looks up persona by username and persona_name
    2. Checks if persona is private
    3. **Checks if email is in whitelist** (403 if not authorized)
    4. Sends OTP email to whitelisted visitor

    Args:
        username: User's username
        persona_name: Persona name (query parameter, defaults to "default")

    Returns:
        - 200: OTP sent successfully
        - 403: Email not in whitelist
        - 404: Persona not found
        - 429: Too many OTP requests

    Rate limit: Max 3 OTP emails per hour per email/persona combination
    """
    try:
        # Look up persona by username and persona_name
        from shared.database.models.user import User

        stmt = (
            select(Persona)
            .join(User, User.id == Persona.user_id)
            .where(
                User.username == username,
                Persona.persona_name == persona_name,
                Persona.is_active == True,
            )
        )
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona '{persona_name}' not found for username: {username}",
            )

        # Check if persona is private
        if not persona.is_private:
            return RequestAccessResponse(
                success=True,
                message="This persona is public. No access request needed.",
            )

        # Check if visitor's email is in the whitelist
        visitor_repo = get_visitor_whitelist_repository()
        visitor = await visitor_repo.get_visitor_by_email(persona.user_id, request.email)

        if not visitor:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your email is not authorized to access this persona. Please contact admin to request access.",
            )

        # Email is whitelisted - proceed with sending OTP
        # Pass persona owner ID for whitelabel email support
        otp_service = get_otp_service()
        success, error_msg = await otp_service.send_otp_email(
            persona_id=persona.id,
            persona_name=persona.name,
            email=request.email,
            first_name=request.first_name,
            persona_owner_id=persona.user_id,  # For custom email domain lookup
        )

        if not success:
            raise HTTPException(
                status_code=(
                    status.HTTP_429_TOO_MANY_REQUESTS
                    if "too many" in error_msg.lower()
                    else status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=error_msg,
            )

        logger.info(f"Access request sent to {request.email} for persona {persona.id} ({username})")

        return RequestAccessResponse(
            success=True,
            message=f"Verification code sent to {request.email}. Please check your inbox.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting access for {username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please try again.",
        )


@router.post("/{username}/verify-access", response_model=VerifyAccessResponse)
async def verify_access(
    username: str,
    request: VerifyAccessRequest,
    response: Response,
    persona_name: str = "default",
    session: AsyncSession = Depends(get_session),
):
    """
    Verify OTP and grant access to private persona

    This endpoint:
    1. **Checks if email is in whitelist** (403 if not authorized)
    2. Verifies OTP code (401 if invalid/expired)
    3. Updates visitor's name if provided
    4. Assigns visitor to persona (creates junction table entry)
    5. Sets 14-day visitor authentication cookie
    6. Returns success

    Args:
        username: User's username
        persona_name: Persona name (query parameter, defaults to "default")

    Returns:
        - 200: Access granted, cookie set
        - 401: Invalid/expired OTP
        - 403: Email not in whitelist
        - 404: Persona not found

    The visitor can now access the persona for 14 days without re-verification.
    """
    try:
        # Look up persona by username and persona_name
        from shared.database.models.user import User

        stmt = (
            select(Persona)
            .join(User, User.id == Persona.user_id)
            .where(
                User.username == username,
                Persona.persona_name == persona_name,
                Persona.is_active == True,
            )
        )
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona '{persona_name}' not found for username: {username}",
            )

        # Check if persona is private
        if not persona.is_private:
            return VerifyAccessResponse(
                success=True,
                message="This persona is public. No verification needed.",
            )

        # Check if visitor's email is in the whitelist (prevent bypass)
        visitor_repo = get_visitor_whitelist_repository()
        visitor = await visitor_repo.get_visitor_by_email(persona.user_id, request.email)

        if not visitor:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your email is not authorized to access this persona. Please contact admin to request access.",
            )

        # Verify OTP
        persona_repo = get_persona_access_repository()
        is_valid, error_msg = await persona_repo.verify_otp(
            persona_id=persona.id,
            email=request.email,
            otp_code=request.otp_code,
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg,
            )

        # OTP verified! Update visitor's name if provided and not already set
        if (request.first_name and not visitor.first_name) or (
            request.last_name and not visitor.last_name
        ):
            await visitor_repo.update_visitor(
                visitor_id=visitor.id,
                first_name=request.first_name or visitor.first_name,
                last_name=request.last_name or visitor.last_name,
            )
            logger.info(f"Updated visitor {visitor.id} for user {persona.user_id}")

        # Assign visitor to persona (creates junction table entry if not exists)
        await persona_repo.assign_visitor_to_persona(
            persona_id=persona.id,
            visitor_id=visitor.id,
        )

        # Set 14-day visitor cookie
        set_visitor_cookie(response, persona_id=persona.id, visitor_id=visitor.id)

        visitor_display_name = visitor.first_name or request.email.split("@")[0]

        logger.info(f"Access granted to {request.email} for persona {persona.id} ({username})")

        return VerifyAccessResponse(
            success=True,
            message=f"Access granted! Welcome, {visitor_display_name}.",
            visitor_name=visitor_display_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying access for {username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify access. Please try again.",
        )


@router.get("/{username}/check-access", response_model=CheckAccessResponse)
async def check_access(
    username: str,
    persona_name: str = "default",
    visitor_token: Optional[str] = Cookie(None, alias=VISITOR_COOKIE_NAME),
    current_user: Optional[User] = Depends(get_current_user_optional),
    session: AsyncSession = Depends(get_session),
):
    """
    Check if visitor has active access to persona

    This endpoint checks:
    1. If user is authenticated via JWT (logged-in user) - has full access
    2. If persona exists
    3. If persona is private or public
    4. If private, validates visitor cookie and whitelist status

    Args:
        username: User's username
        persona_name: Persona name (query parameter, defaults to "default")
        visitor_token: Visitor JWT token from cookie (optional)
        current_user: Authenticated user from JWT (optional, via Depends)

    Returns:
        - 200: Access status with details
        - 404: Persona not found

    Use this endpoint to:
    - Determine if visitor needs to request access
    - Check if existing cookie is still valid
    - Show appropriate UI (access form vs. chat interface)
    """
    try:
        # Look up persona by username and persona_name
        from uuid import UUID

        from shared.database.models.user import User

        stmt = (
            select(Persona)
            .join(User, User.id == Persona.user_id)
            .where(
                User.username == username,
                Persona.persona_name == persona_name,
                Persona.is_active == True,
            )
        )
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona '{persona_name}' not found for username: {username}",
            )

        # Check if user is authenticated via JWT (logged-in user)
        # This takes priority over visitor cookie - authenticated users always have access
        if current_user:
            logger.info(
                f"Authenticated user {current_user.email} accessing persona {persona.id} ({username})"
            )
            return CheckAccessResponse(
                has_access=True,
                is_private=persona.is_private,
                visitor_email=current_user.email,
                message=f"Authenticated as {current_user.email}",
                is_authenticated=True,
            )

        # Public personas: always have access
        if not persona.is_private:
            return CheckAccessResponse(
                has_access=True,
                is_private=False,
                visitor_email=None,
                message="This persona is public. No verification needed.",
            )

        # Private persona: check visitor cookie
        if not visitor_token:
            return CheckAccessResponse(
                has_access=False,
                is_private=True,
                visitor_email=None,
                message="This persona is private. Please verify your email to access.",
            )

        # Verify visitor JWT token
        payload = LinkedInOAuthService.verify_jwt_token(visitor_token)

        if not payload:
            return CheckAccessResponse(
                has_access=False,
                is_private=True,
                visitor_email=None,
                message="Your access has expired. Please verify your email again.",
            )

        visitor_id = payload.get("visitor_id")
        persona_id_from_token = payload.get("persona_id")

        if not visitor_id or not persona_id_from_token:
            return CheckAccessResponse(
                has_access=False,
                is_private=True,
                visitor_email=None,
                message="Invalid access token. Please verify your email again.",
            )

        # Verify token is for THIS persona
        if str(persona.id) != persona_id_from_token:
            return CheckAccessResponse(
                has_access=False,
                is_private=True,
                visitor_email=None,
                message="Access token is not valid for this persona.",
            )

        # Load visitor from database
        visitor_repo = get_visitor_whitelist_repository()
        visitor = await visitor_repo.get_visitor_by_id(UUID(visitor_id))

        if not visitor:
            return CheckAccessResponse(
                has_access=False,
                is_private=True,
                visitor_email=None,
                message="Visitor not found. Please verify your email again.",
            )

        # Check if visitor is still in whitelist and assigned to persona
        persona_repo = get_persona_access_repository()
        is_allowed = await persona_repo.is_visitor_allowed(persona.id, visitor.email)

        if not is_allowed:
            return CheckAccessResponse(
                has_access=False,
                is_private=True,
                visitor_email=visitor.email,
                message="You no longer have access to this persona.",
            )

        # Valid access!
        visitor_display_name = visitor.first_name or visitor.email.split("@")[0]

        logger.info(f"Access check passed for {visitor.email} on persona {persona.id} ({username})")

        return CheckAccessResponse(
            has_access=True,
            is_private=True,
            visitor_email=visitor.email,
            message=f"Access granted. Welcome back, {visitor_display_name}!",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking access for {username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check access. Please try again.",
        )
