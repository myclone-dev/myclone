"""
User routes for authenticated users
"""

import io
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import aioboto3
from botocore import UNSIGNED
from botocore.config import Config
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from PIL import Image
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.auth.jwt_auth import get_current_user
from app.auth.widget_token_service import WidgetTokenService
from app.services.claim_service import ClaimService
from shared.config import settings
from shared.database.models.database import Persona, get_session
from shared.database.models.user import OnboardingStatus, User
from shared.database.repositories.user_repository import UserRepository
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.services.s3_service import create_s3_service
from shared.services.slack_service import SlackService
from shared.utils.fuzzy_match import calculate_weighted_score
from shared.utils.validators import validate_username_format

logger = logging.getLogger(__name__)

# Initialize rate limiter for security-sensitive endpoints
# Note: This creates a separate limiter instance for this module
# The main app also has a global limiter in app.state.limiter
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/v1/users")


class UserResponse(BaseModel):
    id: str
    email: str
    phone: Optional[str]
    username: Optional[str]
    fullname: str
    avatar: Optional[str]
    linkedin_id: Optional[str]
    linkedin_url: Optional[str]
    location: Optional[str]
    company: Optional[str]
    role: Optional[str]
    llm_generated_expertise: Optional[str] = None
    email_confirmed: bool
    onboarding_status: OnboardingStatus
    account_type: str  # "creator" or "visitor"
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExpertOnboardingRequest(BaseModel):
    """Request for onboarding an expert with data sources"""

    username: str = Field(
        ...,
        description="Username for the expert persona (3-30 chars, alphanumeric only)",
        min_length=3,
        max_length=30,
    )
    role: Optional[str] = Field(None, description="Professional role/title", max_length=255)
    expertise: Optional[str] = Field(None, description="Areas of expertise")
    linkedin_url: Optional[str] = Field(
        None, alias="linkedinUrl", description="LinkedIn profile URL"
    )
    twitter_username: Optional[str] = Field(
        None, alias="twitterUsername", description="Twitter username (without @)"
    )
    website_urls: Optional[List[str]] = Field(
        None, alias="websiteUrl", description="Personal/company website URLs"
    )
    website_max_pages: int = Field(
        10, ge=1, le=50, alias="websiteMaxPages", description="Maximum pages to crawl per website"
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Validate username format and restrictions

        Uses shared validation function from shared.utils.validators
        to ensure consistency across all authentication flows.

        Rules:
        - 3-30 characters
        - Alphanumeric only (letters and numbers)
        - No special characters allowed
        - Case-insensitive (converted to lowercase)
        - Cannot be a reserved word
        """
        is_valid, error_message, normalized_username = validate_username_format(v)

        if not is_valid:
            raise ValueError(error_message)

        return normalized_username

    class Config:
        populate_by_name = True  # Accept both camelCase (alias) and snake_case


class ExpertOnboardingResponse(BaseModel):
    """Response from expert onboarding"""

    success: bool
    message: str
    user_id: UUID
    persona_id: UUID
    username: str
    jobs_queued: Dict[str, Any]  # {source_type: job_id or error message}
    total_jobs: int


class LinkedInSearchRequest(BaseModel):
    """Request for searching LinkedIn profiles"""

    name: str = Field(..., description="Person's name (required)", min_length=2)
    company: Optional[str] = Field(None, description="Company name filter")
    title: Optional[str] = Field(None, description="Job title filter")
    location: Optional[str] = Field(None, description="Location filter")


class LinkedInSearchResult(BaseModel):
    """Individual search result with similarity score"""

    name: str
    title: Optional[str]
    company: Optional[str]
    location: Optional[str]
    linkedin_url: Optional[str]
    profile_picture_url: Optional[str]
    similarity_score: float = Field(..., description="Weighted similarity score (0-1)")


class LinkedInSearchResponse(BaseModel):
    """Response from LinkedIn profile search"""

    success: bool
    results: List[LinkedInSearchResult]
    total_results: int


class WidgetTokenResponse(BaseModel):
    """Response with widget token information"""

    id: str = Field(..., description="Token ID")
    token: str = Field(..., description="Widget token with wgt_ prefix")
    name: str = Field(..., description="Token name (e.g., 'Main Website', 'Blog Widget')")
    description: Optional[str] = Field(
        None, description="Optional description with additional details"
    )
    created_at: datetime = Field(..., description="Token creation timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")
    is_active: bool = Field(..., description="Whether token is active (not revoked)")

    class Config:
        from_attributes = True


class CreateWidgetTokenRequest(BaseModel):
    """Request to create a new widget token"""

    name: str = Field(..., description="Token name", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="Optional description", max_length=500)


class WidgetTokenListResponse(BaseModel):
    """Response with list of widget tokens"""

    tokens: List[WidgetTokenResponse] = Field(..., description="List of widget tokens")
    total: int = Field(..., description="Total number of tokens")


class AvatarUploadResponse(BaseModel):
    """Response from avatar upload"""

    success: bool = Field(..., description="Whether upload was successful")
    message: str = Field(..., description="Success or error message")
    avatar_url: str = Field(..., description="S3 URL of uploaded avatar")


class AvatarDeleteResponse(BaseModel):
    """Response from avatar deletion"""

    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Success or error message")


class UsernameAvailabilityResponse(BaseModel):
    """Response for username availability check"""

    username: str = Field(..., description="The username that was checked")
    available: bool = Field(..., description="Whether the username is available")
    reason: Optional[str] = Field(None, description="Reason if username is not available")
    note: Optional[str] = Field(
        None,
        description="Advisory note about username availability (not reserved until onboarding complete)",
    )


class UpdateProfileRequest(BaseModel):
    """Request to update user profile"""

    fullname: Optional[str] = Field(
        None, description="User's full name", min_length=1, max_length=200
    )
    phone: Optional[str] = Field(
        None, description="User's phone number", min_length=10, max_length=15
    )
    company: Optional[str] = Field(None, description="User's company name", max_length=200)
    role: Optional[str] = Field(None, description="User's role/job title", max_length=200)


class RegenerateClaimCodeResponse(BaseModel):
    """Response from regenerating claim code"""

    success: bool = Field(..., description="Whether claim code was regenerated successfully")
    message: str = Field(..., description="Success message")
    claim_link: str = Field(..., description="Claim account link with new code")
    expires_at: datetime = Field(..., description="When the claim code expires")


class WidgetConfigResponse(BaseModel):
    """Response with widget configuration"""

    config: Optional[Dict[str, Any]] = Field(
        None, description="Widget configuration settings (null if not set)"
    )
    updated_at: Optional[datetime] = Field(None, description="When config was last updated")


class UpdateWidgetConfigRequest(BaseModel):
    """Request to update widget configuration"""

    config: Dict[str, Any] = Field(
        ...,
        description="Widget configuration object containing customization settings",
        examples=[
            {
                "primaryColor": "#f59e0b",
                "bubbleIcon": "https://example.com/icon.png",
                "avatarUrl": "https://example.com/avatar.png",
                "bubbleText": "Chat with me",
                "position": "bottom-right",
            }
        ],
    )


@router.get("/check-username/{username}", response_model=UsernameAvailabilityResponse)
@limiter.limit("10/minute")
async def check_username_availability(
    request: Request,
    username: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Check if a username is available

    This endpoint checks:
    1. Format validation (length, characters, reserved words) - uses shared.utils.validators
    2. Database uniqueness (if format is valid)

    Returns:
    - available: true if username can be used
    - available: false if username is taken, reserved, or invalid
    - reason: explanation when unavailable
    - note: advisory about username reservation

    This is a public endpoint (no auth required) for onboarding UX.

    **Security**: Rate limited to 10 requests per minute per IP to prevent enumeration attacks.
    """
    try:
        # Validate format using shared function from shared.utils.validators
        # (ensures consistency across all authentication flows)
        is_valid, error_message, username_lower = validate_username_format(username)

        if not is_valid:
            return UsernameAvailabilityResponse(
                username=username,
                available=False,
                reason=error_message,
                note=None,
            )

        # Check database for existing username (case-insensitive)
        stmt = select(User).where(User.username == username_lower)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            return UsernameAvailabilityResponse(
                username=username,
                available=False,
                reason="Username is already taken",
                note=None,
            )

        # Username is available!
        return UsernameAvailabilityResponse(
            username=username,
            available=True,
            reason=None,
            note="Username availability is not reserved until onboarding is complete",
        )

    except HTTPException:
        raise
    except Exception as e:
        # Capture unexpected errors in Sentry with context
        capture_exception_with_context(
            e,
            extra={"username": username},
            tags={
                "component": "api",
                "endpoint": "check_username_availability",
                "severity": "high",  # Username check is critical for onboarding UX
            },
            level="error",
        )
        logger.error(f"Error checking username availability for '{username}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check username availability",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: User = Depends(get_current_user)):
    """
    Get current authenticated user information

    This endpoint matches the frontend's useUserMe hook.
    The frontend calls this with credentials: "include" to send the cookie.
    """
    return UserResponse(
        id=str(user.id),
        email=user.email,
        phone=user.phone,
        username=user.username,
        fullname=user.fullname,
        avatar=user.avatar,
        linkedin_id=user.linkedin_id,
        linkedin_url=user.linkedin_url,
        location=user.location,
        company=user.company,
        role=user.role,
        llm_generated_expertise=user.llm_generated_expertise,
        email_confirmed=user.email_confirmed,
        onboarding_status=user.onboarding_status,
        account_type=user.account_type,  # Already a string from database
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/me", response_model=UserResponse)
async def update_current_user_profile(
    request: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Update current user profile

    This endpoint allows users to update their profile information:
    - fullname: User's full name
    - phone: User's phone number
    - company: User's company name
    - role: User's job title/role

    Only provided fields will be updated (partial updates supported).
    """
    try:
        # Build update dict with only provided fields
        update_data = {}
        if request.fullname is not None:
            update_data["fullname"] = request.fullname.strip()
        if request.phone is not None:
            update_data["phone"] = request.phone.strip() or None
        if request.company is not None:
            update_data["company"] = request.company.strip() or None
        if request.role is not None:
            update_data["role"] = request.role.strip() or None

        # If no fields to update, return current user
        if not update_data:
            return UserResponse(
                id=str(user.id),
                email=user.email,
                phone=user.phone,
                username=user.username,
                fullname=user.fullname,
                avatar=user.avatar,
                linkedin_id=user.linkedin_id,
                linkedin_url=user.linkedin_url,
                location=user.location,
                company=user.company,
                role=user.role,
                llm_generated_expertise=user.llm_generated_expertise,
                email_confirmed=user.email_confirmed,
                onboarding_status=user.onboarding_status,
                account_type=user.account_type,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )

        # Update user profile
        updated_user = await UserRepository.update_user(session, user, **update_data)

        logger.info(f"User {user.id} updated profile: {update_data}")

        return UserResponse(
            id=str(updated_user.id),
            email=updated_user.email,
            phone=updated_user.phone,
            username=updated_user.username,
            fullname=updated_user.fullname,
            avatar=updated_user.avatar,
            linkedin_id=updated_user.linkedin_id,
            linkedin_url=updated_user.linkedin_url,
            location=updated_user.location,
            company=updated_user.company,
            role=updated_user.role,
            llm_generated_expertise=updated_user.llm_generated_expertise,
            email_confirmed=updated_user.email_confirmed,
            onboarding_status=updated_user.onboarding_status,
            account_type=updated_user.account_type,
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at,
        )

    except HTTPException as e:
        # Send 500/502 errors to Sentry
        if e.status_code in [500, 502]:
            capture_exception_with_context(
                e,
                extra={"detail": e.detail, "user_id": str(user.id)},
                tags={
                    "component": "api",
                    "endpoint": "update_current_user_profile",
                    "http_status": str(e.status_code),
                },
                level="error",
            )
            logger.error(
                f"Internal server error updating profile: {e.status_code} - {e.detail} (user: {user.id})"
            )
        elif e.status_code >= 500:
            logger.error(
                f"External service error updating profile: {e.status_code} - {e.detail} (user: {user.id})"
            )
        else:
            logger.warning(
                f"Client error updating profile: {e.status_code} - {e.detail} (user: {user.id})"
            )

        raise
    except Exception as e:
        logger.error(f"Failed to update profile with unexpected error: {e} (user: {user.id})")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}",
        )


@router.post(
    "/expert/onboarding",
    response_model=ExpertOnboardingResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def onboard_expert(
    request: ExpertOnboardingRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Onboard authenticated user as an expert

    This endpoint:
    1. Updates user's username
    2. Creates a default persona for the authenticated user (or uses existing one)
    3. Queues scraping jobs for all provided data sources (LinkedIn, Twitter, Website)
    4. Updates user's onboarding_status to FULLY_ONBOARDED
    5. Returns immediately with job IDs for tracking

    Data sources are optional - users can onboard without any data sources and add them later.
    """
    # Capture user_id early while user is attached to session
    # This prevents SQLAlchemy lazy loading issues in exception handlers after rollback
    user_id_str = str(user.id)

    try:
        logger.info(f"Onboarding expert for user {user_id_str} with username {request.username}")

        # Update user's username and linkedin_url (unique constraint will catch conflicts on commit)
        user.username = request.username
        if request.linkedin_url:
            user.linkedin_url = request.linkedin_url
        session.add(user)

        # Check if user already has a default persona
        stmt = select(Persona).where(
            Persona.user_id == user.id, Persona.persona_name == "default", Persona.is_active == True
        )
        result = await session.execute(stmt)
        existing_persona = result.scalar_one_or_none()

        if existing_persona:
            persona = existing_persona
            # Update existing persona with role and expertise if provided
            if request.role is not None:
                persona.role = request.role
            if request.expertise is not None:
                persona.expertise = request.expertise
            session.add(persona)
            logger.info(f"Using existing default persona {persona.id} for user {user.id}")
        else:
            # Create default persona for the user
            persona = Persona(
                user_id=user.id,
                persona_name="default",
                name=user.fullname,
                role=request.role,
                expertise=request.expertise,
            )
            session.add(persona)
            await session.flush()  # Get persona.id
            logger.info(f"Created default persona {persona.id} for user {user.id}")

        # Update user's onboarding status to FULLY_ONBOARDED
        user.onboarding_status = OnboardingStatus.FULLY_ONBOARDED
        session.add(user)

        # CRITICAL: Commit changes BEFORE queuing jobs to prevent inconsistent state
        # If commit fails (e.g., username/linkedin_url conflict), no jobs will be queued
        try:
            await session.commit()
            logger.info(
                f"✅ User {user.id} onboarded successfully with username {request.username}"
            )
        except IntegrityError as e:
            await session.rollback()
            error_message = str(e.orig) if hasattr(e, "orig") else str(e)

            # Check which constraint was violated (for known user-facing errors)
            if "username" in error_message.lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Username '{request.username}' is already taken",
                )
            elif "linkedin_url" in error_message.lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This LinkedIn URL is already associated with another account",
                )
            else:
                # Unknown IntegrityError (foreign key, not null, check constraint, etc.)
                # Log full error for debugging but don't expose DB details to user
                logger.error(
                    f"Unexpected IntegrityError during onboarding for user {user_id_str}: {error_message}"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An unexpected database error occurred. Please try again or contact support.",
                )

        jobs_queued: Dict[str, Any] = {}
        total_jobs = 0

        # Send Slack notification asynchronously (don't block response if it fails)
        try:
            slack_service = SlackService()
            await slack_service.send_onboarding_notification(
                user_id=str(user.id),
                user_name=user.fullname,
                user_email=user.email,
                persona_name=persona.name,
                persona_username=user.username,
                linkedin_url=request.linkedin_url,
                twitter_url=(
                    f"https://twitter.com/{request.twitter_username}"
                    if request.twitter_username
                    else None
                ),
                website_url=request.website_urls[0] if request.website_urls else None,
            )
            logger.info(f"Slack onboarding notification sent for user: {user.username}")
        except Exception as slack_error:
            # Don't fail the entire onboarding if Slack notification fails
            logger.warning(f"Failed to send Slack notification (non-critical): {slack_error}")

        return ExpertOnboardingResponse(
            success=True,
            message="Expert onboarded successfully",
            user_id=user.id,
            persona_id=persona.id,
            username=user.username,
            jobs_queued=jobs_queued,
            total_jobs=total_jobs,
        )

    except HTTPException as e:
        # Ensure session is clean (defensive programming)
        try:
            await session.rollback()
        except Exception:
            pass  # Session might already be closed/rolled back

        # Send 500/502 errors to Sentry, log all errors
        if e.status_code in [500, 502]:
            capture_exception_with_context(
                e,
                extra={"detail": e.detail, "user_id": user_id_str},
                tags={
                    "component": "api",
                    "endpoint": "onboard_expert",
                    "http_status": str(e.status_code),
                },
                level="error",
            )
            logger.error(
                f"Internal server error in onboarding: {e.status_code} - {e.detail} (user: {user_id_str})"
            )
        elif e.status_code >= 500:
            # 503/504 - external service issues, log but don't send to Sentry
            logger.error(
                f"External service error in onboarding: {e.status_code} - {e.detail} (user: {user_id_str})"
            )
        else:
            # Client errors (4xx) - log as warning
            logger.warning(
                f"Client error in onboarding: {e.status_code} - {e.detail} (user: {user_id_str})"
            )

        raise  # Re-raise original exception with proper status code
    except Exception as e:
        logger.error(f"Expert onboarding failed with unexpected error: {e} (user: {user_id_str})")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Expert onboarding failed: {str(e)}",
        )


@router.post("/linkedin/search", response_model=LinkedInSearchResponse)
async def search_linkedin_profiles(
    request: LinkedInSearchRequest,
    user: User = Depends(get_current_user),
):
    """
    Search for LinkedIn profiles with fuzzy matching

    This endpoint:
    1. Uses CrustData to search for LinkedIn profiles by name
    2. Applies fuzzy matching with weighted scoring:
       - Name: 40%
       - Title: 30%
       - Company: 20%
       - Location: 10%
    3. Returns top 10 results sorted by similarity score

    Requires authentication.
    """
    # LinkedIn scraping infrastructure has been removed
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="LinkedIn search is not available in this version.",
    )


@router.post(
    "/me/widget-tokens", response_model=WidgetTokenResponse, status_code=status.HTTP_201_CREATED
)
async def create_widget_token(
    request: CreateWidgetTokenRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new widget token

    This endpoint:
    1. Creates a new widget token
    2. Requires a name (e.g., "Blog Widget", "Documentation Site")
    3. Optionally accepts a description
    4. Returns the new token

    Use this to create multiple tokens for different websites/domains.
    Each token can be independently revoked without affecting others.

    Requires user to have a username set.
    """
    try:
        # Verify user has username
        if not user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must have a username to generate widget token. Complete onboarding first.",
            )

        # Create new token
        new_token = await WidgetTokenService.create_token(
            user_id=user.id,
            expert_username=user.username,
            name=request.name,
            description=request.description,
            session=session,
        )

        logger.info(f"Created widget token '{request.name}' for user {user.id}")

        return WidgetTokenResponse(
            id=str(new_token.id),
            token=new_token.token,
            name=new_token.name,
            description=new_token.description,
            created_at=new_token.created_at,
            last_used_at=new_token.last_used_at,
            is_active=new_token.is_active,
        )

    except HTTPException as e:
        # Ensure session is clean
        try:
            await session.rollback()
        except Exception:
            pass

        # Send 500/502 errors to Sentry
        if e.status_code in [500, 502]:
            capture_exception_with_context(
                e,
                extra={"detail": e.detail, "user_id": str(user.id)},
                tags={
                    "component": "api",
                    "endpoint": "create_widget_token",
                    "http_status": str(e.status_code),
                },
                level="error",
            )
            logger.error(
                f"Internal server error creating widget token: {e.status_code} - {e.detail} (user: {user.id})"
            )
        elif e.status_code >= 500:
            logger.error(
                f"External service error creating widget token: {e.status_code} - {e.detail} (user: {user.id})"
            )
        else:
            logger.warning(
                f"Client error creating widget token: {e.status_code} - {e.detail} (user: {user.id})"
            )

        raise
    except Exception as e:
        logger.error(f"Failed to create widget token with unexpected error: {e} (user: {user.id})")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create widget token: {str(e)}",
        )


@router.get("/me/widget-tokens", response_model=WidgetTokenListResponse)
async def list_widget_tokens(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    List all widget tokens for the authenticated user

    This endpoint:
    1. Returns all widget tokens
    2. Includes both active and revoked tokens
    3. Tokens are ordered by creation date (newest first)

    Use this to manage and view all widget tokens for different websites.
    """
    try:
        # Verify user has username
        if not user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must have a username to view widget tokens. Complete onboarding first.",
            )

        # Get all tokens
        tokens = await WidgetTokenService.get_all_tokens(user_id=user.id, session=session)

        # Convert to response models
        token_responses = [
            WidgetTokenResponse(
                id=str(token.id),
                token=token.token,
                name=token.name,
                description=token.description,
                created_at=token.created_at,
                last_used_at=token.last_used_at,
                is_active=token.is_active,
            )
            for token in tokens
        ]

        return WidgetTokenListResponse(
            tokens=token_responses,
            total=len(token_responses),
        )

    except HTTPException as e:
        # Ensure session is clean
        try:
            await session.rollback()
        except Exception:
            pass

        # Send 500/502 errors to Sentry
        if e.status_code in [500, 502]:
            capture_exception_with_context(
                e,
                extra={"detail": e.detail, "user_id": str(user.id)},
                tags={
                    "component": "api",
                    "endpoint": "list_widget_tokens",
                    "http_status": str(e.status_code),
                },
                level="error",
            )
            logger.error(
                f"Internal server error listing widget tokens: {e.status_code} - {e.detail} (user: {user.id})"
            )
        elif e.status_code >= 500:
            logger.error(
                f"External service error listing widget tokens: {e.status_code} - {e.detail} (user: {user.id})"
            )
        else:
            logger.warning(
                f"Client error listing widget tokens: {e.status_code} - {e.detail} (user: {user.id})"
            )

        raise
    except Exception as e:
        logger.error(f"Failed to list widget tokens with unexpected error: {e} (user: {user.id})")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list widget tokens: {str(e)}",
        )


@router.delete("/me/widget-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_widget_token(
    token_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Revoke a specific widget token

    This endpoint:
    1. Soft-deletes the token by setting revoked_at timestamp
    2. The token will no longer work for authentication
    3. Returns 204 No Content on success
    4. Returns 404 if token not found or already revoked

    Use this to revoke tokens for specific websites without affecting others.
    """
    try:
        # Verify user has username
        if not user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User must have a username to manage widget tokens. Complete onboarding first.",
            )

        # Parse token_id
        try:
            token_uuid = UUID(token_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid token ID format",
            )

        # Revoke token
        revoked = await WidgetTokenService.revoke_token(
            token_id=token_uuid,
            user_id=user.id,
            session=session,
        )

        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found or already revoked",
            )

        logger.info(f"Revoked widget token {token_id} for user {user.id}")
        return None  # 204 No Content

    except HTTPException as e:
        # Ensure session is clean
        try:
            await session.rollback()
        except Exception:
            pass

        # Send 500/502 errors to Sentry
        if e.status_code in [500, 502]:
            capture_exception_with_context(
                e,
                extra={"detail": e.detail, "user_id": str(user.id), "token_id": token_id},
                tags={
                    "component": "api",
                    "endpoint": "revoke_widget_token",
                    "http_status": str(e.status_code),
                },
                level="error",
            )
            logger.error(
                f"Internal server error revoking widget token: {e.status_code} - {e.detail} (user: {user.id})"
            )
        elif e.status_code >= 500:
            logger.error(
                f"External service error revoking widget token: {e.status_code} - {e.detail} (user: {user.id})"
            )
        else:
            logger.warning(
                f"Client error revoking widget token: {e.status_code} - {e.detail} (user: {user.id})"
            )

        raise
    except Exception as e:
        logger.error(f"Failed to revoke widget token with unexpected error: {e} (user: {user.id})")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke widget token: {str(e)}",
        )


# Avatar upload constants
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_AVATAR_SIZE = 10 * 1024 * 1024  # 10MB
MAX_AVATAR_DIMENSION = 4096  # 4096x4096 max


@router.post("/me/avatar", response_model=AvatarUploadResponse, status_code=status.HTTP_200_OK)
async def upload_avatar(
    file: UploadFile = File(..., description="Avatar image file (JPEG, PNG, WebP)"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Upload or update user avatar (profile picture)

    This endpoint:
    1. Validates file type (JPEG, PNG, WebP only)
    2. Validates file size (max 10MB)
    3. Validates image dimensions (max 4096x4096)
    4. Optimizes/compresses image for web (JPEG quality 85%, max 1024x1024)
    5. Uploads to S3 storage (avatars/{user_id}.{ext})
    6. Updates user.avatar field with S3 URL
    7. Deletes old avatar from S3 (if exists and is S3-hosted)

    Security:
    - User authentication required (JWT)
    - File type validation via content type and magic bytes (PIL)
    - Size and dimension limits enforced
    - User can only update their own avatar

    Returns:
    - success: True if upload succeeded
    - message: Success message
    - avatar_url: S3 URL of new avatar
    """
    try:
        # Validate file type
        content_type = file.content_type
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Allowed: JPEG, PNG, WebP. Got: {content_type}",
            )

        # Validate file extension
        file_extension = None
        if file.filename:
            file_extension = "." + file.filename.rsplit(".", 1)[-1].lower()
            if file_extension not in ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file extension. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
                )

        # Read file content
        file_content = await file.read()

        # Validate file size
        if len(file_content) > MAX_AVATAR_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size: {MAX_AVATAR_SIZE / 1024 / 1024}MB",
            )

        # Validate image using PIL (checks magic bytes, not just extension)
        try:
            image = Image.open(io.BytesIO(file_content))
            image.verify()  # Verify it's a valid image

            # Re-open for processing (verify() closes the file)
            image = Image.open(io.BytesIO(file_content))

            # Validate dimensions
            width, height = image.size
            if width > MAX_AVATAR_DIMENSION or height > MAX_AVATAR_DIMENSION:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image dimensions too large. Max: {MAX_AVATAR_DIMENSION}x{MAX_AVATAR_DIMENSION}. Got: {width}x{height}",
                )

            logger.info(
                f"Avatar image validated: {width}x{height}, format={image.format}, size={len(file_content)} bytes"
            )

        except Exception as e:
            logger.error(f"Invalid image file: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or corrupted image file",
            )

        # Optimize image for web (resize + compress)
        try:
            optimized_content, final_extension = await optimize_avatar_image(
                image, original_content=file_content, original_extension=file_extension
            )

            logger.info(
                f"Image optimized: original={len(file_content)} bytes, optimized={len(optimized_content)} bytes, ext={final_extension}"
            )
        except Exception as e:
            logger.error(f"Image optimization failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process image. The file may be corrupted or in an unsupported format.",
            )

        # Upload to S3 (using aioboto3 directly like LinkedIn OAuth)
        # Generate S3 key: avatars/{user_id}_{timestamp}.{ext}
        # Timestamp ensures unique URL to bust browser cache on re-upload
        timestamp = int(time.time())
        s3_key = f"avatars/{user.id}_{timestamp}{final_extension}"

        # Detect LocalStack usage (port 4566 or 'localstack' in URL)
        use_localstack = bool(
            settings.aws_endpoint_url
            and (
                "localstack" in settings.aws_endpoint_url.lower()
                or "4566" in settings.aws_endpoint_url
            )
        )

        # Build session kwargs
        session_kwargs = {"region_name": settings.aws_region}
        client_kwargs = {"region_name": settings.aws_region}

        # Add endpoint_url for LocalStack
        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url

        # Determine authentication strategy
        if use_localstack:
            # LocalStack: Use unsigned requests (no credentials needed)
            client_kwargs["config"] = Config(signature_version=UNSIGNED)
        elif settings.aws_access_key_id and settings.aws_secret_access_key:
            # Production with explicit credentials
            session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        s3_session = aioboto3.Session(**session_kwargs)

        async with s3_session.client("s3", **client_kwargs) as s3_client:
            await s3_client.put_object(
                Bucket=settings.user_data_bucket,
                Key=s3_key,
                Body=optimized_content,
                ContentType=get_content_type_from_extension(final_extension),
            )

        # Generate S3 URL (standard AWS format, works for both AWS and LocalStack)
        avatar_url = (
            f"https://{settings.user_data_bucket}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
        )

        # Store old avatar URL for cleanup
        old_avatar_url = user.avatar

        # CRITICAL: Delete old avatar BEFORE committing to prevent orphaned files
        # If S3 deletion fails, we can still rollback the transaction
        if old_avatar_url and old_avatar_url != avatar_url:
            try:
                # Create S3Service for deletion
                s3_service = create_s3_service(
                    endpoint_url=settings.aws_endpoint_url,
                    bucket_name=settings.user_data_bucket,
                    access_key_id=settings.aws_access_key_id,
                    secret_access_key=settings.aws_secret_access_key,
                    region=settings.aws_region,
                    directory="avatars",
                )
                await delete_old_avatar_from_s3(old_avatar_url, s3_service)
            except Exception as e:
                # Log but don't fail the upload if old avatar deletion fails
                # (old avatar might be external URL or already deleted)
                logger.warning(f"Failed to delete old avatar (non-critical): {e}")

        # Now safe to commit - if we reach here, old avatar is cleaned up
        user.avatar = avatar_url
        await UserRepository.update_user(session, user, avatar=avatar_url)

        logger.info(f"Avatar uploaded successfully for user {user.id}: {avatar_url}")

        return AvatarUploadResponse(
            success=True,
            message="Avatar uploaded successfully",
            avatar_url=avatar_url,
        )

    except HTTPException as e:
        # Send 500/502 errors to Sentry
        if e.status_code in [500, 502]:
            capture_exception_with_context(
                e,
                extra={"detail": e.detail, "user_id": str(user.id)},
                tags={
                    "component": "api",
                    "endpoint": "upload_avatar",
                    "http_status": str(e.status_code),
                },
                level="error",
            )
            logger.error(
                f"Internal server error uploading avatar: {e.status_code} - {e.detail} (user: {user.id})"
            )
        elif e.status_code >= 500:
            logger.error(
                f"External service error uploading avatar: {e.status_code} - {e.detail} (user: {user.id})"
            )
        else:
            logger.warning(
                f"Client error uploading avatar: {e.status_code} - {e.detail} (user: {user.id})"
            )

        raise
    except Exception as e:
        logger.error(
            f"Avatar upload failed with unexpected error for user {user.id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Avatar upload failed: {str(e)}",
        )


@router.delete("/me/avatar", response_model=AvatarDeleteResponse, status_code=status.HTTP_200_OK)
async def delete_avatar(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete user avatar (profile picture)

    This endpoint:
    1. Deletes avatar from S3 (if S3-hosted)
    2. Sets user.avatar to NULL in database
    3. Returns success message

    Security:
    - User authentication required (JWT)
    - User can only delete their own avatar

    Returns:
    - success: True if deletion succeeded
    - message: Success message
    """
    try:
        if not user.avatar:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No avatar found for user",
            )

        old_avatar_url = user.avatar

        # Update user.avatar to NULL
        await UserRepository.update_user(session, user, avatar=None)

        # Delete from S3 (if S3-hosted)
        s3_service = create_s3_service(
            endpoint_url=settings.aws_endpoint_url,
            bucket_name=settings.user_data_bucket,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
            region=settings.aws_region,
            directory="avatars",
        )

        await delete_old_avatar_from_s3(old_avatar_url, s3_service)

        logger.info(f"Avatar deleted successfully for user {user.id}")

        return AvatarDeleteResponse(
            success=True,
            message="Avatar deleted successfully",
        )

    except HTTPException as e:
        # Send 500/502 errors to Sentry
        if e.status_code in [500, 502]:
            capture_exception_with_context(
                e,
                extra={"detail": e.detail, "user_id": str(user.id)},
                tags={
                    "component": "api",
                    "endpoint": "delete_avatar",
                    "http_status": str(e.status_code),
                },
                level="error",
            )
            logger.error(
                f"Internal server error deleting avatar: {e.status_code} - {e.detail} (user: {user.id})"
            )
        elif e.status_code >= 500:
            logger.error(
                f"External service error deleting avatar: {e.status_code} - {e.detail} (user: {user.id})"
            )
        else:
            logger.warning(
                f"Client error deleting avatar: {e.status_code} - {e.detail} (user: {user.id})"
            )

        raise
    except Exception as e:
        logger.error(
            f"Avatar deletion failed with unexpected error for user {user.id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Avatar deletion failed: {str(e)}",
        )


@router.get("/me/widget-config", response_model=WidgetConfigResponse)
async def get_widget_config(
    user: User = Depends(get_current_user),
):
    """
    Get current user's widget configuration

    This endpoint returns the saved widget customization settings including:
    - Colors (primary, background, text, bubble, etc.)
    - Sizes (width, height, bubble size, border radius)
    - Branding (avatar URL, bubble icon, header title, welcome message)
    - Layout (position, offsets, modal position)
    - Behavior (enable voice, show branding)

    Returns null config if no settings have been saved yet.
    """
    try:
        return WidgetConfigResponse(
            config=user.widget_config,
            updated_at=user.updated_at if user.widget_config else None,
        )
    except Exception as e:
        logger.error(f"Failed to get widget config for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve widget configuration",
        )


@router.put("/me/widget-config", response_model=WidgetConfigResponse)
async def update_widget_config(
    request: UpdateWidgetConfigRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Update current user's widget configuration

    This endpoint saves widget customization settings including:
    - Colors: primaryColor, backgroundColor, textColor, bubbleBackgroundColor, etc.
    - Sizes: width, height, bubbleSize, borderRadius, chatbotWidth, chatbotHeight
    - Branding: avatarUrl, bubbleIcon, headerTitle, headerSubtitle, welcomeMessage
    - Layout: position, offsetX, offsetY, modalPosition, chatbotStyle
    - Behavior: enableVoice, showBranding, showAvatar, bubbleText

    The config is stored as JSONB and completely replaces any existing config.
    """
    try:
        # Update widget config
        user.widget_config = request.config
        session.add(user)
        await session.commit()
        await session.refresh(user)

        logger.info(f"Widget config updated for user {user.id}")

        return WidgetConfigResponse(
            config=user.widget_config,
            updated_at=user.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update widget config for user {user.id}: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update widget configuration",
        )


@router.delete("/me/widget-config", status_code=status.HTTP_204_NO_CONTENT)
async def delete_widget_config(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete current user's widget configuration

    Resets widget config to null, allowing the user to start fresh
    with default settings.
    """
    try:
        user.widget_config = None
        session.add(user)
        await session.commit()

        logger.info(f"Widget config deleted for user {user.id}")
        return None

    except Exception as e:
        logger.error(f"Failed to delete widget config for user {user.id}: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete widget configuration",
        )


@router.post(
    "/{user_id}/regenerate-claim-code",
    response_model=RegenerateClaimCodeResponse,
    status_code=status.HTTP_200_OK,
)
async def regenerate_claim_code(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(require_api_key),
):
    """
    Regenerate claim code for a user (admin/operator endpoint)

    This endpoint:
    1. Generates a new claim code for the specified user
    2. Resets expiration to 7 days from now
    3. Resets attempt counter to 0
    4. Returns new claim link and expiration

    Use cases:
    - Original claim code expired
    - User lost the claim link
    - Too many failed claim attempts

    Security:
    - API key required (admin/operator only)
    - Cannot regenerate if user already has password auth

    Returns:
    - claim_link: Full URL to claim account page
    - expires_at: When the new code expires
    """
    try:
        # Initialize claim service
        claim_service = ClaimService()

        # Generate new claim code
        claim_code, expires_at = await claim_service.update_user_claim_code(session, user_id)

        # Build claim link
        claim_link = f"{settings.frontend_url}/claim-account?code={claim_code}"

        logger.info(f"✅ Regenerated claim code for user {user_id}")

        return RegenerateClaimCodeResponse(
            success=True,
            message="Claim code regenerated successfully",
            claim_link=claim_link,
            expires_at=expires_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={"user_id": str(user_id)},
            tags={
                "component": "api",
                "endpoint": "regenerate_claim_code",
                "severity": "medium",
                "user_facing": "false",
            },
            level="error",
        )
        logger.error(f"Failed to regenerate claim code for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate claim code. Please try again.",
        )


# Helper functions


async def optimize_avatar_image(
    image: Image.Image, original_content: bytes, original_extension: Optional[str]
) -> tuple[bytes, str]:
    """
    Optimize avatar image for web display

    Strategy:
    1. Resize to max 1024x1024 (maintain aspect ratio)
    2. Convert to RGB if needed (for JPEG)
    3. Compress with quality 85% (good balance between quality and size)
    4. Use JPEG for photos, PNG for graphics/transparency

    Returns:
        Tuple of (optimized_content, file_extension)
    """
    # Target max dimension
    max_size = 1024

    # Resize if needed (maintain aspect ratio)
    width, height = image.size
    if width > max_size or height > max_size:
        # Calculate new dimensions
        ratio = min(max_size / width, max_size / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)

        # Resize with high-quality resampling
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        logger.info(f"Resized image from {width}x{height} to {new_width}x{new_height}")

    # Determine output format
    # Use PNG for images with transparency, JPEG for everything else
    has_transparency = image.mode in ("RGBA", "LA", "P") and (
        image.info.get("transparency") is not None or image.mode == "RGBA"
    )

    if has_transparency:
        # Keep PNG for transparency
        output_format = "PNG"
        extension = ".png"
        save_kwargs = {"optimize": True}

        # Ensure RGBA mode
        if image.mode != "RGBA":
            image = image.convert("RGBA")
    else:
        # Use JPEG for everything else (better compression)
        output_format = "JPEG"
        extension = ".jpg"
        save_kwargs = {"quality": 85, "optimize": True}

        # Convert to RGB (JPEG doesn't support RGBA)
        if image.mode != "RGB":
            # Create white background for transparency
            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                image = background
            else:
                image = image.convert("RGB")

    # Save to bytes
    output_buffer = io.BytesIO()
    image.save(output_buffer, format=output_format, **save_kwargs)
    optimized_content = output_buffer.getvalue()

    logger.info(
        f"Optimized image: format={output_format}, original_size={len(original_content)}, optimized_size={len(optimized_content)}"
    )

    return optimized_content, extension


async def delete_old_avatar_from_s3(avatar_url: str, s3_service) -> None:
    """
    Delete old avatar from S3 (if S3-hosted)

    Args:
        avatar_url: URL of avatar to delete
        s3_service: S3 service instance
    """
    # Check if avatar is S3-hosted (in our bucket)
    if not avatar_url:
        return

    # Check if it's an S3 URL in our bucket
    # We now always use standard AWS S3 URL format (even for LocalStack)
    is_our_s3_avatar = (
        ".s3" in avatar_url
        and "amazonaws.com" in avatar_url
        and settings.user_data_bucket in avatar_url
        and "/avatars/" in avatar_url
    )

    if not is_our_s3_avatar:
        logger.info(
            f"Avatar is not S3-hosted or not in our bucket, skipping deletion: {avatar_url}"
        )
        return

    try:
        # Convert URL to s3:// path
        # Standard AWS S3 URL: https://bucket.s3.region.amazonaws.com/avatars/user_id/file.jpg
        s3_path_part = avatar_url.split(f"{settings.user_data_bucket}.s3.")[-1]
        s3_path_part = s3_path_part.split("amazonaws.com/")[-1]
        s3_path = f"s3://{settings.user_data_bucket}/{s3_path_part}"

        # Delete from S3
        deleted = await s3_service.delete_file(s3_path)

        if deleted:
            logger.info(f"Deleted old avatar from S3: {s3_path}")
        else:
            logger.warning(f"Failed to delete old avatar from S3: {s3_path}")

    except Exception as e:
        # Non-critical error - log but don't fail the request
        logger.warning(f"Error deleting old avatar from S3: {e}")


def get_content_type_from_extension(extension: str) -> str:
    """Get content type from file extension"""
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    return content_types.get(extension.lower(), "image/jpeg")
