import logging
from datetime import datetime
from typing import List, Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_api_key
from app.auth.jwt_auth import get_current_user, get_user_or_service
from shared.database.models.database import Persona, get_session
from shared.database.models.health import HealthCheckResponse
from shared.database.models.persona import PersonaResponse
from shared.database.models.user import User
from shared.database.repositories.persona_repository import PersonaRepository
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.utils.validators import validate_persona_name_format

logger = logging.getLogger(__name__)

router = APIRouter()


class VoiceUpdateRequest(BaseModel):
    voice_id: str


class PersonaNameAvailabilityResponse(BaseModel):
    """Response for persona name availability check"""

    original_name: str
    persona_name: str
    available: bool
    reason: Optional[str] = None


class PersonaDetailsResponse(BaseModel):
    """Complete persona details with user information - for authenticated access"""

    # Persona fields
    id: UUID
    persona_name: str
    name: str
    role: Optional[str] = None
    expertise: Optional[str] = None
    company: Optional[str] = None
    description: Optional[str] = None
    voice_id: Optional[str] = None
    voice_enabled: bool = True
    content_mode_enabled: bool = False
    is_private: bool = False
    suggested_questions: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    # Email Capture Settings
    email_capture_enabled: bool = False
    email_capture_message_threshold: int = 5
    email_capture_require_fullname: bool = True
    email_capture_require_phone: bool = False

    # Calendar Integration Settings
    calendar_enabled: bool = False
    calendar_url: Optional[str] = None
    calendar_display_name: Optional[str] = None

    # User fields
    username: str
    fullname: Optional[str] = None
    avatar: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None

    class Config:
        from_attributes = True


class PublicExpertProfileResponse(BaseModel):
    """Public expert profile combining persona and user data"""

    # Persona fields
    id: UUID
    persona_name: str
    name: str
    role: Optional[str] = None
    expertise: Optional[str] = None
    company: Optional[str] = None
    description: Optional[str] = None
    is_private: bool = False
    voice_enabled: bool = True
    content_mode_enabled: bool = False
    suggested_questions: Optional[List[str]] = None  # Suggested starter questions for chat UI
    created_at: datetime
    updated_at: datetime

    # Email Capture Settings
    email_capture_enabled: bool = False
    email_capture_message_threshold: int = 5
    email_capture_require_fullname: bool = True
    email_capture_require_phone: bool = False

    # Session Time Limit Settings
    session_time_limit_enabled: bool = False
    session_time_limit_minutes: float = 30.0
    session_time_limit_warning_minutes: float = 2.0

    # Calendar Integration Settings
    calendar_enabled: bool = False
    calendar_url: Optional[str] = None
    calendar_display_name: Optional[str] = None

    # Language Settings
    language: Optional[str] = "auto"  # Language code for i18n (auto, en, es, fr, ar, de, it, etc.)

    # Persona-specific avatar (overrides user avatar when set)
    persona_avatar_url: Optional[str] = None

    # User fields
    username: str
    fullname: Optional[str] = None  # User's full name
    avatar: Optional[str] = None  # User's profile avatar (fallback if no persona_avatar_url)

    # Widget customization settings (colors, sizes, branding, bubble icon, etc.)
    widget_config: Optional[dict] = None

    class Config:
        from_attributes = True


@router.get("/expert/{username}", response_model=PersonaResponse)
async def get_persona_by_username(
    username: str,
    persona_name: str = "default",  # Optional query param, defaults to "default"
    session: AsyncSession = Depends(get_session),
    api_key_valid: bool = Depends(require_api_key),
):
    """Get persona by username for /expert/{username} routing"""
    try:
        # Get persona by User.username + persona_name
        persona = await PersonaRepository.get_by_username_and_persona(
            session, username, persona_name
        )
        if not persona:
            raise HTTPException(
                status_code=404, detail=f"Expert '{username}' (persona: {persona_name}) not found"
            )

        return PersonaResponse.model_validate(persona)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting persona by username: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/expert/{username}/public", response_model=PublicExpertProfileResponse)
async def get_public_expert_profile(
    username: str,
    persona_name: str = "default",  # Optional query param, defaults to "default"
    session: AsyncSession = Depends(get_session),
):
    """
    Get public expert profile with combined persona and user data

    This endpoint returns:
    - Persona information (name, role, company, description, etc.)
    - User information (username, avatar, location, linkedin_url)

    This is useful for public-facing pages like /{username} chat interface
    """
    try:
        # Get persona with joined user data
        stmt = (
            select(Persona, User)
            .join(User, Persona.user_id == User.id)
            .where(
                User.username == username,
                Persona.persona_name == persona_name,
                Persona.is_active == True,
            )
        )
        result = await session.execute(stmt)
        row = result.first()

        if not row:
            raise HTTPException(
                status_code=404, detail=f"Expert '{username}' (persona: {persona_name}) not found"
            )

        persona, user = row

        # Prioritize user-updated role/company (LinkedIn fallback removed)
        role = user.role
        company = user.company

        # Prioritize persona role over user role (persona-specific override)
        if persona.role:
            role = persona.role

        # Use user.avatar
        avatar = user.avatar

        # Parse suggested_questions from JSONB
        suggested_questions = None
        if persona.suggested_questions and isinstance(persona.suggested_questions, dict):
            suggested_questions = persona.suggested_questions.get("questions", [])

        # Build combined response
        return PublicExpertProfileResponse(
            # Persona fields
            id=persona.id,
            persona_name=persona.persona_name,
            name=persona.name,
            role=role,
            expertise=persona.expertise,
            company=company,
            description=persona.description,
            is_private=persona.is_private,
            voice_enabled=persona.voice_enabled,
            suggested_questions=suggested_questions,
            created_at=persona.created_at,
            updated_at=persona.updated_at,
            # Email Capture Settings
            email_capture_enabled=persona.email_capture_enabled,
            email_capture_message_threshold=persona.email_capture_message_threshold,
            email_capture_require_fullname=persona.email_capture_require_fullname,
            email_capture_require_phone=persona.email_capture_require_phone,
            # Session Time Limit Settings
            session_time_limit_enabled=persona.session_time_limit_enabled,
            session_time_limit_minutes=persona.session_time_limit_minutes,
            session_time_limit_warning_minutes=persona.session_time_limit_warning_minutes,
            # Calendar Integration Settings
            calendar_enabled=persona.calendar_enabled,
            calendar_url=persona.calendar_url,
            calendar_display_name=persona.calendar_display_name,
            # Language Settings
            language=persona.language or "auto",
            # Persona-specific avatar (overrides user avatar when set)
            persona_avatar_url=persona.persona_avatar_url,
            # User fields
            username=user.username,
            fullname=user.fullname,
            avatar=avatar,
            # Widget customization (bubble icon, colors, etc.)
            widget_config=user.widget_config,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting public expert profile for {username}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/expert/{username}/voice", response_model=PersonaResponse)
async def update_persona_voice_by_username(
    username: str,
    voice_update: VoiceUpdateRequest,
    persona_name: str = "default",  # Optional query param, defaults to "default"
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """Update persona voice_id by username (supports JWT cookies and API keys)"""
    try:
        # Find persona by User.username + persona_name
        persona = await PersonaRepository.get_by_username_and_persona(
            session, username, persona_name
        )
        if not persona:
            raise HTTPException(
                status_code=404, detail=f"Expert '{username}' (persona: {persona_name}) not found"
            )

        # Authorization: Users can only update their own personas
        if isinstance(auth, User):
            if auth.id != persona.user_id:
                raise HTTPException(
                    status_code=403, detail="Access denied: You can only update your own personas"
                )

        # Update the voice_id
        persona.voice_id = voice_update.voice_id
        await session.commit()
        await session.refresh(persona)

        logger.info(f"Updated voice_id for persona {username} to {voice_update.voice_id}")
        return PersonaResponse.model_validate(persona)

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating persona voice_id: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/persona/{persona_id}/voice", response_model=PersonaResponse)
async def update_persona_voice_by_id(
    persona_id: UUID,
    voice_update: VoiceUpdateRequest,
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """Update persona voice_id by persona ID (supports JWT cookies and API keys)"""
    try:
        # Find the persona by ID
        stmt = select(Persona).where(Persona.id == persona_id)
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona with ID '{persona_id}' not found")

        # Authorization: Users can only update their own personas
        if isinstance(auth, User):
            if auth.id != persona.user_id:
                raise HTTPException(
                    status_code=403, detail="Access denied: You can only update your own personas"
                )

        # Update the voice_id
        persona.voice_id = voice_update.voice_id
        await session.commit()
        await session.refresh(persona)

        logger.info(f"Updated voice_id for persona ID {persona_id} to {voice_update.voice_id}")
        return PersonaResponse.model_validate(persona)

    except HTTPException:
        raise
    except Exception as e:
        await session.rollback()
        logger.error(f"Error updating persona voice_id: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/personas/check-persona-name", response_model=PersonaNameAvailabilityResponse)
async def check_persona_name_availability(
    persona_name: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PersonaNameAvailabilityResponse:
    """Check if a persona name is available for the current user

    The endpoint will:
    1. Convert display name to URL-safe slug (e.g., "My Persona" → "my-persona")
    2. Validate format (length, pattern, reserved words, starts with letter)
    3. Check if user already has an active persona with that slug

    Returns:
    - available: true if persona name can be used
    - available: false if name is invalid or already in use
    - reason: explanation when unavailable

    This is used during persona creation to prevent duplicate name errors.

    Args:
        persona_name: Display name to check (will be slugified)
        session: Database session
        current_user: Authenticated user

    Returns:
        PersonaNameAvailabilityResponse with availability status
    """
    try:
        # Step 1: Validate and slugify the persona name
        is_valid, error_message, slugified_name = validate_persona_name_format(persona_name)

        if not is_valid:
            # Name format is invalid (too short, reserved, bad pattern, etc.)
            return PersonaNameAvailabilityResponse(
                original_name=persona_name,
                persona_name=slugified_name,  # Return the attempted slug
                available=False,
                reason=error_message,
            )

        # Step 2: Check if user already has an active persona with this slug
        stmt = select(Persona).where(
            Persona.user_id == current_user.id,
            Persona.persona_name == slugified_name,
            Persona.is_active == True,  # Only check active personas
        )
        result = await session.execute(stmt)
        existing_persona = result.scalar_one_or_none()

        if existing_persona:
            return PersonaNameAvailabilityResponse(
                original_name=persona_name,
                persona_name=slugified_name,
                available=False,
                reason=f"You already have a persona named '{persona_name}'",
            )

        # Persona name is available!
        return PersonaNameAvailabilityResponse(
            original_name=persona_name,
            persona_name=slugified_name,
            available=True,
            reason=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Capture unexpected errors in Sentry with context
        capture_exception_with_context(
            e,
            extra={
                "persona_name_input": persona_name,
                "user_id": str(current_user.id),
            },
            tags={
                "component": "api",
                "endpoint": "check_persona_name_availability",
                "severity": "medium",
                "user_facing": "true",
            },
            level="error",
        )
        logger.error(
            f"Error checking persona name availability for '{persona_name}' (user: {current_user.id}): {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check persona name availability",
        )


@router.get("/personas/{persona_id}", response_model=PersonaDetailsResponse)
async def get_persona_details(
    persona_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Get complete persona details by ID (authenticated)

    This endpoint returns:
    - Persona information (name, role, company, description, voice_id, etc.)
    - User information (username, fullname, avatar, location, linkedin_url)
    - Email capture settings
    - Calendar integration settings
    - Suggested questions

    Requires JWT authentication.
    """
    try:
        # Get persona with joined user data
        stmt = (
            select(Persona, User)
            .join(User, Persona.user_id == User.id)
            .where(Persona.id == persona_id, Persona.is_active == True)
        )
        result = await session.execute(stmt)
        row = result.first()

        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Persona with ID '{persona_id}' not found or has been deleted",
            )

        persona, user = row

        # Prioritize user-updated role/company (LinkedIn fallback removed)
        role = user.role
        company = user.company

        # Prioritize persona role over user role (persona-specific override)
        if persona.role:
            role = persona.role

        # Use user.avatar
        avatar = user.avatar

        # Parse suggested_questions from JSONB
        suggested_questions = None
        if persona.suggested_questions and isinstance(persona.suggested_questions, dict):
            suggested_questions = persona.suggested_questions.get("questions", [])

        # Build complete response
        return PersonaDetailsResponse(
            # Persona fields
            id=persona.id,
            persona_name=persona.persona_name,
            name=persona.name,
            role=role,
            expertise=persona.expertise,
            company=company,
            description=persona.description,
            voice_id=persona.voice_id,
            voice_enabled=persona.voice_enabled,
            is_private=persona.is_private,
            suggested_questions=suggested_questions,
            created_at=persona.created_at,
            updated_at=persona.updated_at,
            # Email Capture Settings
            email_capture_enabled=persona.email_capture_enabled,
            email_capture_message_threshold=persona.email_capture_message_threshold,
            email_capture_require_fullname=persona.email_capture_require_fullname,
            email_capture_require_phone=persona.email_capture_require_phone,
            # Calendar Integration Settings
            calendar_enabled=persona.calendar_enabled,
            calendar_url=persona.calendar_url,
            calendar_display_name=persona.calendar_display_name,
            # User fields
            username=user.username,
            fullname=user.fullname,
            avatar=avatar,
            location=user.location,
            linkedin_url=user.linkedin_url,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting persona details for ID {persona_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(session: AsyncSession = Depends(get_session)):
    """Health check endpoint - verifies database connectivity"""
    from datetime import datetime

    try:
        # Test database connection
        await session.execute(select(1))
        database_status = "healthy"
        overall_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        database_status = "unhealthy"
        overall_status = "unhealthy"

    return HealthCheckResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="1.0.0",
        database_status=database_status,
        openai_status="not_checked",  # OpenAI failures shouldn't kill container
    )
