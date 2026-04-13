"""
Persona Knowledge Management API Routes

Endpoints for managing knowledge sources attached to personas:
- Get persona's knowledge sources
- Attach knowledge to persona
- Detach knowledge from persona
- Toggle knowledge source enable/disable
- Get available sources for persona
- Create/update persona with knowledge
- Get LinkedIn-based introduction, expertise, thinking style, writing style
- Upload/delete persona-specific avatar
"""

import io
import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

import aioboto3
from botocore import UNSIGNED
from botocore.config import Config
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_auth import get_current_user
from app.services.knowledge_library_service import get_knowledge_library_service
from shared.config import settings
from shared.database.models.database import Persona, get_session
from shared.database.models.user import User
from shared.monitoring.sentry_utils import (
    add_breadcrumb,
    capture_exception_with_context,
    capture_message,
    start_span,
)
from shared.rag.advanced_prompt_creator import AdvancedPromptCreator
from shared.schemas.knowledge_library import (
    AttachKnowledgeRequest,
    AvailableKnowledgeSourcesResponse,
    PersonaCreateWithKnowledge,
    PersonaKnowledgeResponse,
    PersonaUpdateWithKnowledge,
    PersonaWithKnowledgeResponse,
    UserPersonasResponse,
)
from shared.services.s3_service import create_s3_service
from shared.services.tier_service import TierLimitExceeded, TierService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/personas", tags=["Persona Knowledge"])


# ============================================================================
# Get Persona's Knowledge Sources
# ============================================================================


@router.get(
    "/{persona_id}/knowledge-sources",
    response_model=PersonaKnowledgeResponse,
    summary="Get persona's knowledge sources",
    description="""
    Get all knowledge sources attached to a persona.

    Returns:
    - List of attached sources with metadata
    - Enabled/disabled status
    - Embeddings count per source
    - Total statistics
    """,
)
async def get_persona_knowledge_sources(
    persona_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PersonaKnowledgeResponse:
    """Get all knowledge sources for a persona"""
    try:
        # Verify persona exists
        persona_stmt = select(Persona).where(Persona.id == persona_id)
        persona = (await session.execute(persona_stmt)).scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona {persona_id} not found",
            )

        # Authorization check - verify user owns this persona
        if persona.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this persona",
            )

        service = get_knowledge_library_service()
        sources = await service.get_persona_knowledge_sources(persona_id)

        # Calculate statistics
        total_sources = len(sources)
        enabled_sources = sum(1 for s in sources if s.enabled)
        total_embeddings = sum(s.embeddings_count for s in sources if s.enabled)

        return PersonaKnowledgeResponse(
            persona_id=persona_id,
            persona_name=persona.persona_name,
            name=persona.name,
            sources=sources,
            total_sources=total_sources,
            enabled_sources=enabled_sources,
            total_embeddings=total_embeddings,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching knowledge sources for persona {persona_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch knowledge sources: {str(e)}",
        )


# ============================================================================
# Get Available Knowledge Sources for Persona
# ============================================================================


@router.get(
    "/{persona_id}/knowledge-sources/available",
    response_model=AvailableKnowledgeSourcesResponse,
    summary="Get available knowledge sources",
    description="""
    Get all knowledge sources available to attach to this persona.
    This includes the user's entire knowledge library with indicators
    for which sources are already attached.

    Perfect for building a knowledge selector UI.
    """,
)
async def get_available_knowledge_sources(
    persona_id: UUID,
    current_user: User = Depends(get_current_user),
) -> AvailableKnowledgeSourcesResponse:
    """Get all available knowledge sources for a persona"""
    try:
        service = get_knowledge_library_service()
        response = await service.get_available_knowledge_sources(persona_id)
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error fetching available sources for persona {persona_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch available sources: {str(e)}",
        )


# ============================================================================
# Attach Knowledge Sources to Persona
# ============================================================================


@router.post(
    "/{persona_id}/knowledge-sources",
    response_model=PersonaKnowledgeResponse,
    summary="Attach knowledge sources to persona",
    description="""
    Attach multiple knowledge sources to a persona.

    If a source is already attached but disabled, it will be re-enabled.
    If a source is already attached and enabled, no change occurs.

    Request body:
    ```json
    {
      "sources": [
        {"source_type": "linkedin", "source_record_id": "uuid"},
        {"source_type": "website", "source_record_id": "uuid"}
      ]
    }
    ```
    """,
)
async def attach_knowledge_to_persona(
    persona_id: UUID,
    request: AttachKnowledgeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PersonaKnowledgeResponse:
    """Attach knowledge sources to a persona"""
    try:
        # Verify persona exists
        persona_stmt = select(Persona).where(Persona.id == persona_id)
        persona = (await session.execute(persona_stmt)).scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona {persona_id} not found",
            )

        # Authorization check - verify user owns this persona
        if persona.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this persona",
            )

        service = get_knowledge_library_service()

        # Attach sources
        await service.attach_sources_to_persona(persona_id, request.sources)

        # Return updated knowledge sources
        sources = await service.get_persona_knowledge_sources(persona_id)

        total_sources = len(sources)
        enabled_sources = sum(1 for s in sources if s.enabled)
        total_embeddings = sum(s.embeddings_count for s in sources if s.enabled)

        return PersonaKnowledgeResponse(
            persona_id=persona_id,
            persona_name=persona.persona_name,
            name=persona.name,
            sources=sources,
            total_sources=total_sources,
            enabled_sources=enabled_sources,
            total_embeddings=total_embeddings,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error attaching knowledge sources to persona {persona_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to attach knowledge sources: {str(e)}",
        )


# ============================================================================
# Detach Knowledge Source from Persona
# ============================================================================


@router.delete(
    "/{persona_id}/knowledge-sources/{source_record_id}",
    summary="Detach knowledge source from persona",
    description="""
    Remove a knowledge source from a persona.

    This completely removes the persona_data_sources entry.
    The source and its embeddings remain in the user's library,
    but the persona will no longer have access to it.
    """,
)
async def detach_knowledge_from_persona(
    persona_id: UUID,
    source_record_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Detach a knowledge source from persona"""
    try:
        # Verify persona exists and user owns it
        persona_stmt = select(Persona).where(Persona.id == persona_id)
        persona = (await session.execute(persona_stmt)).scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona {persona_id} not found",
            )

        # Authorization check - verify user owns this persona
        if persona.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this persona",
            )

        service = get_knowledge_library_service()
        success = await service.detach_source_from_persona(persona_id, source_record_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge source attachment not found",
            )

        return {
            "success": True,
            "message": f"Successfully detached source {source_record_id} from persona {persona_id}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detaching source {source_record_id} from persona {persona_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to detach knowledge source: {str(e)}",
        )


# ============================================================================
# Toggle Knowledge Source Enable/Disable
# ============================================================================


@router.patch(
    "/{persona_id}/knowledge-sources/{source_record_id}/toggle",
    summary="Toggle knowledge source",
    description="""
    Enable or disable a knowledge source for a persona.

    This toggles the 'enabled' field without removing the attachment.
    Useful for temporarily disabling knowledge without losing the configuration.
    """,
)
async def toggle_knowledge_source(
    persona_id: UUID,
    source_record_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Toggle enabled state of a knowledge source"""
    try:
        # Verify persona exists and user owns it
        persona_stmt = select(Persona).where(Persona.id == persona_id)
        persona = (await session.execute(persona_stmt)).scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona {persona_id} not found",
            )

        # Authorization check - verify user owns this persona
        if persona.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this persona",
            )

        service = get_knowledge_library_service()
        success = await service.toggle_source(persona_id, source_record_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Knowledge source attachment not found",
            )

        return {
            "success": True,
            "message": f"Successfully toggled source {source_record_id} for persona {persona_id}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling source {source_record_id} for persona {persona_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle knowledge source: {str(e)}",
        )


# ============================================================================
# Create Persona with Knowledge
# ============================================================================


@router.post(
    "/with-knowledge",
    response_model=PersonaWithKnowledgeResponse,
    summary="Create persona with knowledge sources",
    description="""
    Create a new persona and attach knowledge sources in one transaction.

    Request body:
    ```json
    {
      "persona_name": "professional",
      "name": "Professional Coach",
      "role": "Executive Coach",
      "description": "Helping leaders achieve their goals",
      "voice_id": "elevenlabs_voice_id",
      "knowledge_sources": [
        {"source_type": "linkedin", "source_record_id": "uuid"},
        {"source_type": "website", "source_record_id": "uuid"}
      ]
    }
    ```
    """,
)
async def create_persona_with_knowledge(
    request: PersonaCreateWithKnowledge,
    user_id: UUID,  # Query param for backward compatibility, use current_user.id instead
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PersonaWithKnowledgeResponse:
    """Create persona with knowledge sources"""
    try:
        # Authorization check - ensure user can only create personas for themselves
        if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to create personas for this user",
            )

        # Check persona creation limit based on user's tier
        tier_service = TierService(session)
        try:
            await tier_service.check_persona_creation_allowed(user_id)
        except TierLimitExceeded as e:
            # Get current usage for error response
            persona_count = await tier_service.get_persona_count(user_id)
            limits = await tier_service.get_user_tier_limits(user_id)
            tier_name = limits.get("tier_name", "current")
            max_personas = limits.get("max_personas", 1)

            # Log to Sentry with proper context
            capture_exception_with_context(
                e,
                extra={
                    "user_id": str(user_id),
                    "requested_persona_name": request.persona_name,
                    "current_persona_count": persona_count,
                    "max_personas": max_personas,
                    "tier_name": tier_name,
                },
                tags={
                    "component": "persona_creation",
                    "operation": "check_persona_limit",
                    "severity": "low",
                    "user_facing": "true",
                },
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": str(e),
                    "error_code": "PERSONA_LIMIT_EXCEEDED",
                    "current_count": persona_count,
                    "max_personas": max_personas,
                    "tier": tier_name,
                },
            )

        # Create persona
        persona = Persona(
            user_id=user_id,
            persona_name=request.persona_name,
            name=request.name,
            role=request.role,
            expertise=request.expertise,
            description=request.description,
            voice_id=request.voice_id,
            language=request.language,
        )
        session.add(persona)
        await session.commit()
        await session.refresh(persona)

        # Attach knowledge sources if provided
        if request.knowledge_sources:
            service = get_knowledge_library_service()
            await service.attach_sources_to_persona(persona.id, request.knowledge_sources)

            # Get knowledge stats
            sources = await service.get_persona_knowledge_sources(persona.id)
            knowledge_sources_count = len(sources)
            enabled_sources_count = sum(1 for s in sources if s.enabled)
            total_embeddings = sum(s.embeddings_count for s in sources if s.enabled)
        else:
            knowledge_sources_count = 0
            enabled_sources_count = 0
            total_embeddings = 0

        role, company = None, None

        # Parse suggested_questions from JSONB
        suggested_questions = None
        if persona.suggested_questions and isinstance(persona.suggested_questions, dict):
            suggested_questions = persona.suggested_questions.get("questions", [])

        return PersonaWithKnowledgeResponse(
            id=persona.id,
            user_id=persona.user_id,
            persona_name=persona.persona_name,
            name=persona.name,
            role=persona.role or role,
            expertise=persona.expertise,
            company=company,
            description=persona.description,
            voice_id=persona.voice_id,
            voice_enabled=persona.voice_enabled,
            language=persona.language or "auto",  # Convert NULL to 'auto'
            greeting_message=persona.greeting_message,
            suggested_questions=suggested_questions,
            persona_avatar_url=persona.persona_avatar_url,
            knowledge_sources_count=knowledge_sources_count,
            enabled_sources_count=enabled_sources_count,
            total_embeddings=total_embeddings,
            is_private=persona.is_private,
            access_control_enabled_at=persona.access_control_enabled_at,
            default_lead_capture_enabled=persona.default_lead_capture_enabled,
            content_mode_enabled=persona.content_mode_enabled,
            email_capture_enabled=persona.email_capture_enabled,
            email_capture_message_threshold=persona.email_capture_message_threshold,
            email_capture_require_fullname=persona.email_capture_require_fullname,
            email_capture_require_phone=persona.email_capture_require_phone,
            calendar_enabled=persona.calendar_enabled,
            calendar_url=persona.calendar_url,
            calendar_display_name=persona.calendar_display_name,
            send_summary_email_enabled=persona.send_summary_email_enabled,
            webhook_enabled=persona.webhook_enabled,
            webhook_url=persona.webhook_url,
            webhook_events=persona.webhook_events,
            session_time_limit_enabled=persona.session_time_limit_enabled,
            session_time_limit_minutes=persona.session_time_limit_minutes,
            session_time_limit_warning_minutes=persona.session_time_limit_warning_minutes,
            created_at=persona.created_at,
            updated_at=persona.updated_at,
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like persona limit exceeded) without wrapping
        raise
    except Exception as e:
        logger.error(f"Error creating persona with knowledge: {e}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user_id),
                "requested_persona_name": request.persona_name,
            },
            tags={
                "component": "persona_creation",
                "operation": "create_persona_with_knowledge",
                "severity": "high",
                "user_facing": "true",
            },
        )
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create persona: {str(e)}",
        )


# ============================================================================
# Update Persona with Knowledge
# ============================================================================


@router.get(
    "/{persona_id}/with-knowledge",
    response_model=PersonaWithKnowledgeResponse,
    summary="Get persona with knowledge stats",
    description="""
    Return a persona with language and knowledge statistics included.
    Use this for settings pages to keep UI state in sync after refresh.
    """,
)
async def get_persona_with_knowledge(
    persona_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PersonaWithKnowledgeResponse:
    try:
        # Get persona
        persona_stmt = select(Persona).where(Persona.id == persona_id)
        persona = (await session.execute(persona_stmt)).scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona {persona_id} not found",
            )

        # Authorization check - verify user owns this persona
        if persona.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this persona",
            )

        # Knowledge stats
        service = get_knowledge_library_service()
        sources = await service.get_persona_knowledge_sources(persona_id)
        knowledge_sources_count = len(sources)
        enabled_sources_count = sum(1 for s in sources if s.enabled)
        total_embeddings = sum(s.embeddings_count for s in sources if s.enabled)

        role, company = None, None

        # Parse suggested_questions from JSONB
        suggested_questions = None
        if persona.suggested_questions and isinstance(persona.suggested_questions, dict):
            suggested_questions = persona.suggested_questions.get("questions", [])

        return PersonaWithKnowledgeResponse(
            id=persona.id,
            user_id=persona.user_id,
            persona_name=persona.persona_name,
            name=persona.name,
            role=persona.role or role,
            expertise=persona.expertise,
            company=company,
            description=persona.description,
            voice_id=persona.voice_id,
            voice_enabled=persona.voice_enabled,
            language=persona.language or "auto",  # Convert NULL to 'auto'
            greeting_message=persona.greeting_message,
            suggested_questions=suggested_questions,
            persona_avatar_url=persona.persona_avatar_url,
            knowledge_sources_count=knowledge_sources_count,
            enabled_sources_count=enabled_sources_count,
            total_embeddings=total_embeddings,
            is_private=persona.is_private,
            access_control_enabled_at=persona.access_control_enabled_at,
            default_lead_capture_enabled=persona.default_lead_capture_enabled,
            content_mode_enabled=persona.content_mode_enabled,
            email_capture_enabled=persona.email_capture_enabled,
            email_capture_message_threshold=persona.email_capture_message_threshold,
            email_capture_require_fullname=persona.email_capture_require_fullname,
            email_capture_require_phone=persona.email_capture_require_phone,
            calendar_enabled=persona.calendar_enabled,
            calendar_url=persona.calendar_url,
            calendar_display_name=persona.calendar_display_name,
            send_summary_email_enabled=persona.send_summary_email_enabled,
            webhook_enabled=persona.webhook_enabled,
            webhook_url=persona.webhook_url,
            webhook_events=persona.webhook_events,
            session_time_limit_enabled=persona.session_time_limit_enabled,
            session_time_limit_minutes=persona.session_time_limit_minutes,
            session_time_limit_warning_minutes=persona.session_time_limit_warning_minutes,
            created_at=persona.created_at,
            updated_at=persona.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching persona with knowledge {persona_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch persona: {str(e)}",
        )


@router.patch(
    "/{persona_id}/with-knowledge",
    response_model=PersonaWithKnowledgeResponse,
    summary="Update persona with knowledge sources",
    description="""
    Update persona and optionally replace knowledge sources.

    If knowledge_sources is provided in the request, ALL existing sources
    will be replaced with the new list.

    If knowledge_sources is omitted, only persona metadata is updated.
    """,
)
async def update_persona_with_knowledge(
    persona_id: UUID,
    request: PersonaUpdateWithKnowledge,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PersonaWithKnowledgeResponse:
    """Update persona with optional knowledge sources replacement"""
    try:
        # Get persona
        persona_stmt = select(Persona).where(Persona.id == persona_id)
        persona = (await session.execute(persona_stmt)).scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona {persona_id} not found",
            )

        # Authorization check - verify user owns this persona
        if persona.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this persona",
            )

        # Update persona fields
        if request.persona_name is not None:
            persona.persona_name = request.persona_name
        if request.name is not None:
            persona.name = request.name
        if request.role is not None:
            persona.role = request.role
        if request.expertise is not None:
            persona.expertise = request.expertise
        if request.description is not None:
            persona.description = request.description
        if request.voice_id is not None:
            persona.voice_id = request.voice_id
        if request.voice_enabled is not None:
            persona.voice_enabled = request.voice_enabled
        if request.language is not None:
            persona.language = request.language
        # Update default lead capture settings
        if request.default_lead_capture_enabled is not None:
            persona.default_lead_capture_enabled = request.default_lead_capture_enabled
        # Update content mode settings
        if request.content_mode_enabled is not None:
            persona.content_mode_enabled = request.content_mode_enabled
        # Update email capture settings
        if request.email_capture_enabled is not None:
            persona.email_capture_enabled = request.email_capture_enabled
        if request.email_capture_message_threshold is not None:
            persona.email_capture_message_threshold = request.email_capture_message_threshold
        if request.email_capture_require_fullname is not None:
            persona.email_capture_require_fullname = request.email_capture_require_fullname
        if request.email_capture_require_phone is not None:
            persona.email_capture_require_phone = request.email_capture_require_phone
        # Update calendar integration settings
        if request.calendar_enabled is not None:
            persona.calendar_enabled = request.calendar_enabled
        if request.calendar_url is not None:
            persona.calendar_url = request.calendar_url
        if request.calendar_display_name is not None:
            persona.calendar_display_name = request.calendar_display_name
        # Update conversation summary email settings
        if request.send_summary_email_enabled is not None:
            persona.send_summary_email_enabled = request.send_summary_email_enabled
        # Update webhook integration settings
        if request.webhook_enabled is not None:
            persona.webhook_enabled = request.webhook_enabled
        if request.webhook_url is not None:
            # Validate HTTPS URL
            if request.webhook_url and not request.webhook_url.startswith("https://"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook URL must use HTTPS"
                )
            persona.webhook_url = request.webhook_url
        if request.webhook_events is not None:
            persona.webhook_events = request.webhook_events
        if request.webhook_secret is not None:
            persona.webhook_secret = request.webhook_secret
        if request.greeting_message is not None:
            persona.greeting_message = request.greeting_message
        if request.suggested_questions is not None:
            # Store in JSONB format with timestamp
            from datetime import datetime

            persona.suggested_questions = {
                "questions": request.suggested_questions,
                "generated_at": datetime.now().isoformat(),
            }
        # Update session time limit settings
        if request.session_time_limit_enabled is not None:
            persona.session_time_limit_enabled = request.session_time_limit_enabled
        if request.session_time_limit_minutes is not None:
            persona.session_time_limit_minutes = request.session_time_limit_minutes
        if request.session_time_limit_warning_minutes is not None:
            persona.session_time_limit_warning_minutes = request.session_time_limit_warning_minutes

        # Handle knowledge sources BEFORE committing (for transactional consistency)
        service = get_knowledge_library_service()

        if request.knowledge_sources is not None:
            # Replace all knowledge sources
            # First, detach all existing sources
            existing_sources = await service.get_persona_knowledge_sources(persona_id)
            for source in existing_sources:
                await service.detach_source_from_persona(persona_id, source.source_record_id)

            # Then attach new sources
            if request.knowledge_sources:
                await service.attach_sources_to_persona(persona_id, request.knowledge_sources)

        # Commit everything together (persona updates + knowledge changes)
        await session.commit()
        await session.refresh(persona)

        # Get final knowledge stats
        sources = await service.get_persona_knowledge_sources(persona_id)
        knowledge_sources_count = len(sources)
        enabled_sources_count = sum(1 for s in sources if s.enabled)
        total_embeddings = sum(s.embeddings_count for s in sources if s.enabled)

        role, company = None, None

        # Parse suggested_questions from JSONB
        suggested_questions = None
        if persona.suggested_questions and isinstance(persona.suggested_questions, dict):
            suggested_questions = persona.suggested_questions.get("questions", [])

        return PersonaWithKnowledgeResponse(
            id=persona.id,
            user_id=persona.user_id,
            persona_name=persona.persona_name,
            name=persona.name,
            role=persona.role or role,
            expertise=persona.expertise,
            company=company,
            description=persona.description,
            voice_id=persona.voice_id,
            voice_enabled=persona.voice_enabled,
            language=persona.language or "auto",  # Convert NULL to 'auto'
            greeting_message=persona.greeting_message,
            suggested_questions=suggested_questions,
            persona_avatar_url=persona.persona_avatar_url,
            knowledge_sources_count=knowledge_sources_count,
            enabled_sources_count=enabled_sources_count,
            total_embeddings=total_embeddings,
            is_private=persona.is_private,
            access_control_enabled_at=persona.access_control_enabled_at,
            default_lead_capture_enabled=persona.default_lead_capture_enabled,
            content_mode_enabled=persona.content_mode_enabled,
            email_capture_enabled=persona.email_capture_enabled,
            email_capture_message_threshold=persona.email_capture_message_threshold,
            email_capture_require_fullname=persona.email_capture_require_fullname,
            email_capture_require_phone=persona.email_capture_require_phone,
            calendar_enabled=persona.calendar_enabled,
            calendar_url=persona.calendar_url,
            calendar_display_name=persona.calendar_display_name,
            send_summary_email_enabled=persona.send_summary_email_enabled,
            webhook_enabled=persona.webhook_enabled,
            webhook_url=persona.webhook_url,
            webhook_events=persona.webhook_events,
            session_time_limit_enabled=persona.session_time_limit_enabled,
            session_time_limit_minutes=persona.session_time_limit_minutes,
            session_time_limit_warning_minutes=persona.session_time_limit_warning_minutes,
            created_at=persona.created_at,
            updated_at=persona.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating persona {persona_id} with knowledge: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update persona: {str(e)}",
        )


# ============================================================================
# List User's Personas with Knowledge Stats
# ============================================================================


@router.get(
    "/users/{user_id}/personas",
    response_model=UserPersonasResponse,
    summary="List user's personas with knowledge stats",
    description="""
    Get all personas for a user with knowledge statistics.

    Perfect for a persona management dashboard.
    """,
)
async def list_user_personas(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> UserPersonasResponse:
    """List all personas for a user with knowledge stats (optimized with bulk queries)"""
    try:
        # Verify user exists
        user_stmt = select(User).where(User.id == user_id)
        user = (await session.execute(user_stmt)).scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Authorization check - users can only list their own personas
        if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to list personas for this user",
            )

        # Get all active personas (exclude soft-deleted)
        personas_stmt = select(Persona).where(
            Persona.user_id == user_id,
            Persona.is_active == True,  # Only return active personas
        )
        result = await session.execute(personas_stmt)
        personas = result.scalars().all()

        if not personas:
            return UserPersonasResponse(
                user_id=user_id,
                personas=[],
                total_personas=0,
            )

        # Import repositories
        from shared.database.repositories.persona_knowledge_repository import (
            PersonaKnowledgeRepository,
        )

        # Bulk fetch knowledge sources for all personas (1 + 1 + max 5 queries instead of N*M)
        persona_ids = [p.id for p in personas]
        persona_knowledge_map = (
            await PersonaKnowledgeRepository.get_personas_knowledge_sources_bulk(
                session, persona_ids
            )
        )

        # LinkedIn repository removed; role/company come from user/persona fields only
        role, company = None, None

        # Build responses
        persona_responses = []
        for persona in personas:
            # Get knowledge stats from bulk-fetched data
            sources = persona_knowledge_map.get(persona.id, [])
            knowledge_sources_count = len(sources)
            enabled_sources_count = sum(1 for s in sources if s.enabled)
            total_embeddings = sum(s.embeddings_count for s in sources if s.enabled)

            # Parse suggested_questions from JSONB
            suggested_questions = None
            if persona.suggested_questions and isinstance(persona.suggested_questions, dict):
                suggested_questions = persona.suggested_questions.get("questions", [])

            persona_responses.append(
                PersonaWithKnowledgeResponse(
                    id=persona.id,
                    user_id=persona.user_id,
                    persona_name=persona.persona_name,
                    name=persona.name,
                    role=persona.role or role,  # Use persona.role if set, fallback to LinkedIn role
                    expertise=persona.expertise,
                    company=company,
                    description=persona.description,
                    voice_id=persona.voice_id,
                    voice_enabled=persona.voice_enabled,
                    language=persona.language or "auto",  # Convert NULL to 'auto'
                    greeting_message=persona.greeting_message,
                    suggested_questions=suggested_questions,
                    persona_avatar_url=persona.persona_avatar_url,
                    knowledge_sources_count=knowledge_sources_count,
                    enabled_sources_count=enabled_sources_count,
                    total_embeddings=total_embeddings,
                    is_private=persona.is_private,
                    access_control_enabled_at=persona.access_control_enabled_at,
                    default_lead_capture_enabled=persona.default_lead_capture_enabled,
                    email_capture_enabled=persona.email_capture_enabled,
                    email_capture_message_threshold=persona.email_capture_message_threshold,
                    email_capture_require_fullname=persona.email_capture_require_fullname,
                    email_capture_require_phone=persona.email_capture_require_phone,
                    calendar_enabled=persona.calendar_enabled,
                    calendar_url=persona.calendar_url,
                    calendar_display_name=persona.calendar_display_name,
                    send_summary_email_enabled=persona.send_summary_email_enabled,
                    webhook_enabled=persona.webhook_enabled,
                    webhook_url=persona.webhook_url,
                    webhook_events=persona.webhook_events,
                    session_time_limit_enabled=persona.session_time_limit_enabled,
                    session_time_limit_minutes=persona.session_time_limit_minutes,
                    session_time_limit_warning_minutes=persona.session_time_limit_warning_minutes,
                    created_at=persona.created_at,
                    updated_at=persona.updated_at,
                )
            )

        return UserPersonasResponse(
            user_id=user_id,
            personas=persona_responses,
            total_personas=len(persona_responses),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing personas for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list personas: {str(e)}",
        )


# ============================================================================
# Soft Delete Persona
# ============================================================================


@router.delete(
    "/{persona_id}",
    summary="Soft delete persona",
    description="""
    Soft delete a persona by marking it as inactive.

    This sets:
    - is_active = False
    - deleted_at = current timestamp

    The persona data remains in the database but is marked as deleted.
    All related data (prompts, data sources, etc.) are preserved.
    """,
)
async def soft_delete_persona(
    persona_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Soft delete a persona"""
    try:
        from datetime import datetime, timezone

        # Get persona
        persona_stmt = select(Persona).where(Persona.id == persona_id)
        persona = (await session.execute(persona_stmt)).scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona {persona_id} not found",
            )

        # Authorization check - verify user owns this persona
        if persona.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this persona",
            )

        # Check if already deleted
        if not persona.is_active:
            return {
                "success": True,
                "message": f"Persona '{persona.name}' is already deleted",
                "persona_id": str(persona_id),
            }

        # Soft delete - mark as inactive
        persona.is_active = False
        persona.deleted_at = datetime.now(timezone.utc)

        await session.commit()

        logger.info(
            f"Soft deleted persona {persona_id} ({persona.name}) for user {current_user.id}"
        )

        return {
            "success": True,
            "message": f"Persona '{persona.name}' has been deleted successfully",
            "persona_id": str(persona_id),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error soft deleting persona {persona_id}: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete persona: {str(e)}",
        )


# ============================================================================
# Toggle Summary Email Setting
# ============================================================================


@router.patch(
    "/{persona_id}/summary-email",
    summary="Toggle conversation summary email notifications",
    description="""
    Enable or disable automatic conversation summary emails for a persona.

    When enabled (default), persona owners receive email summaries after
    voice conversations end. Disable for debugging or testing purposes.

    **Request Body:**
    - `enabled` (boolean): Set to `true` to enable, `false` to disable

    **Response:**
    - `success`: Whether the operation was successful
    - `message`: Human-readable status message
    - `persona_id`: The persona ID
    - `send_summary_email_enabled`: The new value of the setting
    """,
)
async def toggle_summary_email(
    persona_id: UUID,
    enabled: bool,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Toggle conversation summary email notifications for a persona"""
    try:
        # Get persona
        persona_stmt = select(Persona).where(Persona.id == persona_id)
        persona = (await session.execute(persona_stmt)).scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona {persona_id} not found",
            )

        # Authorization check - verify user owns this persona
        if persona.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this persona",
            )

        # Update the setting
        old_value = persona.send_summary_email_enabled
        persona.send_summary_email_enabled = enabled

        await session.commit()
        await session.refresh(persona)

        status_text = "enabled" if enabled else "disabled"
        logger.info(
            f"Summary email {status_text} for persona {persona_id} "
            f"(was: {old_value}, now: {enabled})"
        )

        return {
            "success": True,
            "message": f"Conversation summary emails {status_text} successfully",
            "persona_id": str(persona_id),
            "send_summary_email_enabled": persona.send_summary_email_enabled,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling summary email for persona {persona_id}: {e}")
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle summary email setting: {str(e)}",
        )


# ============================================================================
# LinkedIn-Based Knowledge Component Endpoints
# ============================================================================


@router.get(
    "/generate_persona_intro",
    summary="Generate persona introduction from LinkedIn data",
    description="""
    Generate and return the persona's professional introduction based on LinkedIn content.
    This is optimized to generate only the introduction without other components.
    Takes user_id as input and uses the default persona for that user.
    """,
)
async def generate_persona_intro(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Return the persona introduction (uses LinkedIn content where available).

    This endpoint is optimized to generate only the introduction component,
    making it more efficient than generating the full prompt.
    """
    try:
        # Get default persona for user (or first persona if no default)
        stmt = select(Persona).where(
            Persona.user_id == user_id, Persona.persona_name == "default", Persona.is_active == True
        )
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        # If no default persona, get the first persona for this user
        if not persona:
            stmt = select(Persona).where(Persona.user_id == user_id).limit(1)
            result = await session.execute(stmt)
            persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"No persona found for user {user_id}"
            )

        # SECURITY: Explicit ownership validation
        if persona.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Persona does not belong to user"
            )

        # Generate introduction only
        creator = AdvancedPromptCreator()
        introduction = await creator.get_persona_introduction_only(session, persona.id, user_id)

        return {
            "user_id": str(user_id),
            "persona_id": str(persona.id),
            "persona_name": persona.name,
            "introduction": introduction,
            "character_count": len(introduction),
        }

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error generating introduction for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate persona introduction",
        )


@router.get(
    "/generate_persona_expertise",
    summary="Generate persona expertise from LinkedIn data",
    description="""
    Analyze and return primary and secondary areas of expertise derived from LinkedIn content.
    This is optimized to generate only the expertise analysis without other components.
    Takes user_id as input and uses the default persona for that user.
    """,
)
async def generate_persona_expertise(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Return primary and secondary areas of expertise derived from LinkedIn content.

    This endpoint is optimized to analyze only the expertise component,
    making it more efficient than generating the full prompt.
    """
    try:
        # Get default persona for user (or first persona if no default)
        stmt = select(Persona).where(
            Persona.user_id == user_id, Persona.persona_name == "default", Persona.is_active == True
        )
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        # If no default persona, get the first persona for this user
        if not persona:
            stmt = select(Persona).where(Persona.user_id == user_id).limit(1)
            result = await session.execute(stmt)
            persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"No persona found for user {user_id}"
            )

        # SECURITY: Explicit ownership validation
        if persona.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Persona does not belong to user"
            )

        # Generate expertise only
        creator = AdvancedPromptCreator()
        expertise = await creator.get_persona_expertise_only(session, persona.id, user_id)

        return {
            "user_id": str(user_id),
            "persona_id": str(persona.id),
            "persona_name": persona.name,
            "expertise": {"primary": expertise.primary, "secondary": expertise.secondary},
            "primary_count": len(expertise.primary),
            "secondary_count": len(expertise.secondary),
        }

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error analyzing expertise for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze persona expertise",
        )


@router.get(
    "/generate_communication_style",
    summary="Generate persona communication style from content",
    description="""
    Extract and return the complete communication style (thinking, speaking, writing)
    from persona's LinkedIn/social content.
    This is optimized to generate only the communication style without other components.
    Takes user_id as input and uses the default persona for that user.
    """,
)
async def generate_communication_style(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Return the complete communication style extracted from persona's LinkedIn/social content.

    This includes:
    - Thinking style: How they approach problems and ideas
    - Speaking style: Tone, formality, energy level
    - Writing style: Sentence structure, vocabulary, formatting
    - Catch phrases: Recurring expressions
    - Transition words: Commonly used connecting words
    - Tone characteristics: Key personality traits

    This endpoint is optimized to analyze only the communication style component,
    making it more efficient than generating the full prompt.
    """
    try:
        # Get default persona for user (or first persona if no default)
        stmt = select(Persona).where(
            Persona.user_id == user_id, Persona.persona_name == "default", Persona.is_active == True
        )
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        # If no default persona, get the first persona for this user
        if not persona:
            stmt = select(Persona).where(Persona.user_id == user_id).limit(1)
            result = await session.execute(stmt)
            persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"No persona found for user {user_id}"
            )

        # SECURITY: Explicit ownership validation
        if persona.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Persona does not belong to user"
            )

        # Get full communication style
        creator = AdvancedPromptCreator()
        communication_style = await creator.get_full_communication_style_only(
            session, persona.id, user_id
        )

        return {
            "user_id": str(user_id),
            "persona_id": str(persona.id),
            "persona_name": persona.name,
            "communication_style": {
                "thinking_style": communication_style.thinking_style,
                "speaking_style": communication_style.speaking_style,
                "writing_style": communication_style.writing_style,
                "catch_phrases": communication_style.catch_phrases,
                "transition_words": communication_style.transition_words,
                "tone_characteristics": communication_style.tone_characteristics,
            },
            "total_catch_phrases": len(communication_style.catch_phrases),
            "total_transition_words": len(communication_style.transition_words),
            "total_tone_characteristics": len(communication_style.tone_characteristics),
        }

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error analyzing communication style for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze persona communication style",
        )


# ============================================================================
# Persona Avatar Management
# ============================================================================

# Avatar upload constants
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_AVATAR_SIZE = 10 * 1024 * 1024  # 10MB
MAX_AVATAR_DIMENSION = 4096  # 4096x4096 max


class PersonaAvatarUploadResponse(BaseModel):
    """Response from persona avatar upload"""

    success: bool = Field(..., description="Whether upload was successful")
    message: str = Field(..., description="Success or error message")
    persona_avatar_url: str = Field(..., description="S3 URL of uploaded persona avatar")


class PersonaAvatarDeleteResponse(BaseModel):
    """Response from persona avatar deletion"""

    success: bool = Field(..., description="Whether deletion was successful")
    message: str = Field(..., description="Success or error message")


async def _optimize_persona_avatar(
    image: Image.Image, original_content: bytes, original_extension: Optional[str]
) -> tuple[bytes, str]:
    """
    Optimize persona avatar image for web display

    Strategy:
    1. Resize to max 1024x1024 (maintain aspect ratio)
    2. Convert to RGB if needed (for JPEG)
    3. Compress with quality 85% (good balance between quality and size)
    4. Use JPEG for photos, PNG for graphics/transparency

    Returns:
        Tuple of (optimized_content, file_extension)
    """
    max_size = 1024

    # Resize if needed (maintain aspect ratio)
    width, height = image.size
    if width > max_size or height > max_size:
        ratio = min(max_size / width, max_size / height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        logger.info(f"Resized persona avatar from {width}x{height} to {new_width}x{new_height}")

    # Determine output format
    has_transparency = image.mode in ("RGBA", "LA", "P") and (
        image.info.get("transparency") is not None or image.mode == "RGBA"
    )

    if has_transparency:
        output_format = "PNG"
        extension = ".png"
        save_kwargs = {"optimize": True}
        if image.mode != "RGBA":
            image = image.convert("RGBA")
    else:
        output_format = "JPEG"
        extension = ".jpg"
        save_kwargs = {"quality": 85, "optimize": True}
        if image.mode != "RGB":
            if image.mode in ("RGBA", "LA"):
                background = Image.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1])
                image = background
            else:
                image = image.convert("RGB")

    output_buffer = io.BytesIO()
    image.save(output_buffer, format=output_format, **save_kwargs)
    optimized_content = output_buffer.getvalue()

    logger.info(
        f"Optimized persona avatar: format={output_format}, original_size={len(original_content)}, optimized_size={len(optimized_content)}"
    )

    return optimized_content, extension


async def _delete_old_persona_avatar_from_s3(avatar_url: str, s3_service) -> None:
    """Delete old persona avatar from S3 (if S3-hosted)"""
    if not avatar_url:
        return

    is_our_s3_avatar = (
        ".s3" in avatar_url
        and "amazonaws.com" in avatar_url
        and settings.user_data_bucket in avatar_url
        and "/avatars/personas/" in avatar_url
    )

    if not is_our_s3_avatar:
        logger.info(f"Persona avatar is not S3-hosted, skipping deletion: {avatar_url}")
        return

    try:
        s3_path_part = avatar_url.split(f"{settings.user_data_bucket}.s3.")[-1]
        s3_path_part = s3_path_part.split("amazonaws.com/")[-1]
        s3_path = f"s3://{settings.user_data_bucket}/{s3_path_part}"

        deleted = await s3_service.delete_file(s3_path)
        if deleted:
            logger.info(f"Deleted old persona avatar from S3: {s3_path}")
        else:
            logger.warning(f"Failed to delete old persona avatar from S3: {s3_path}")
    except Exception as e:
        logger.warning(f"Error deleting old persona avatar from S3: {e}")


def _get_content_type_from_extension(extension: str) -> str:
    """Get content type from file extension"""
    content_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    return content_types.get(extension.lower(), "image/jpeg")


@router.post(
    "/{persona_id}/avatar",
    response_model=PersonaAvatarUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload persona avatar",
    description="""
    Upload or update a persona-specific avatar image.

    This endpoint:
    1. Validates file type (JPEG, PNG, WebP only)
    2. Validates file size (max 10MB)
    3. Validates image dimensions (max 4096x4096)
    4. Optimizes/compresses image for web (JPEG quality 85%, max 1024x1024)
    5. Uploads to S3 storage (avatars/personas/{persona_id}_{timestamp}.{ext})
    6. Updates persona.persona_avatar_url field with S3 URL
    7. Deletes old avatar from S3 (if exists and is S3-hosted)

    The persona avatar overrides the user's profile avatar when displayed in the widget.
    """,
)
async def upload_persona_avatar(
    persona_id: UUID,
    file: UploadFile = File(..., description="Avatar image file (JPEG, PNG, WebP)"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PersonaAvatarUploadResponse:
    """Upload or update persona avatar"""
    # Track operation start
    add_breadcrumb(
        message="persona_avatar_upload_started",
        category="persona_avatar",
        level="info",
        data={
            "persona_id": str(persona_id),
            "user_id": str(current_user.id),
            "filename": file.filename,
            "content_type": file.content_type,
        },
    )

    try:
        with start_span(op="persona_avatar.upload", description="Upload persona avatar"):
            # Verify persona exists and user owns it
            persona_stmt = select(Persona).where(Persona.id == persona_id)
            persona = (await session.execute(persona_stmt)).scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona {persona_id} not found",
            )

        if persona.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this persona's avatar",
            )

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

        # Read and validate file content
        file_content = await file.read()

        if len(file_content) > MAX_AVATAR_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size: {MAX_AVATAR_SIZE / 1024 / 1024}MB",
            )

        # Validate image using PIL
        try:
            image = Image.open(io.BytesIO(file_content))
            image.verify()
            image = Image.open(io.BytesIO(file_content))

            width, height = image.size
            if width > MAX_AVATAR_DIMENSION or height > MAX_AVATAR_DIMENSION:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image dimensions too large. Max: {MAX_AVATAR_DIMENSION}x{MAX_AVATAR_DIMENSION}. Got: {width}x{height}",
                )

            logger.info(
                f"Persona avatar validated: {width}x{height}, format={image.format}, size={len(file_content)} bytes"
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Invalid persona avatar image: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or corrupted image file",
            )

        # Optimize image
        try:
            optimized_content, final_extension = await _optimize_persona_avatar(
                image, original_content=file_content, original_extension=file_extension
            )
        except Exception as e:
            logger.error(f"Persona avatar optimization failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to process image. The file may be corrupted.",
            )

        # Upload to S3
        timestamp = int(time.time())
        s3_key = f"avatars/personas/{persona_id}_{timestamp}{final_extension}"

        use_localstack = bool(
            settings.aws_endpoint_url
            and (
                "localstack" in settings.aws_endpoint_url.lower()
                or "4566" in settings.aws_endpoint_url
            )
        )

        session_kwargs = {"region_name": settings.aws_region}
        client_kwargs = {"region_name": settings.aws_region}

        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url

        if use_localstack:
            client_kwargs["config"] = Config(signature_version=UNSIGNED)
        elif settings.aws_access_key_id and settings.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        s3_session = aioboto3.Session(**session_kwargs)

        async with s3_session.client("s3", **client_kwargs) as s3_client:
            await s3_client.put_object(
                Bucket=settings.user_data_bucket,
                Key=s3_key,
                Body=optimized_content,
                ContentType=_get_content_type_from_extension(final_extension),
            )

        avatar_url = (
            f"https://{settings.user_data_bucket}.s3.{settings.aws_region}.amazonaws.com/{s3_key}"
        )

        # Delete old avatar (non-critical, don't fail if deletion fails)
        old_avatar_url = persona.persona_avatar_url
        if old_avatar_url and old_avatar_url != avatar_url:
            try:
                s3_service = create_s3_service(
                    endpoint_url=settings.aws_endpoint_url,
                    bucket_name=settings.user_data_bucket,
                    access_key_id=settings.aws_access_key_id,
                    secret_access_key=settings.aws_secret_access_key,
                    region=settings.aws_region,
                    directory="avatars/personas",
                )
                await _delete_old_persona_avatar_from_s3(old_avatar_url, s3_service)
            except Exception as e:
                logger.warning(f"Failed to delete old persona avatar (non-critical): {e}")

        # Update persona (MUST be outside the if block above)
        persona.persona_avatar_url = avatar_url
        await session.commit()

        logger.info(f"Persona avatar uploaded for persona {persona_id}: {avatar_url}")

        # Track successful upload
        add_breadcrumb(
            message="persona_avatar_upload_success",
            category="persona_avatar",
            level="info",
            data={
                "persona_id": str(persona_id),
                "avatar_url": avatar_url,
                "optimized_size": len(optimized_content),
            },
        )
        capture_message(
            message="Persona avatar uploaded successfully",
            level="info",
            tags={
                "operation": "persona_avatar_upload",
                "status": "success",
                "persona_id": str(persona_id),
            },
            extra={
                "persona_id": str(persona_id),
                "user_id": str(current_user.id),
                "avatar_url": avatar_url,
                "original_filename": file.filename,
                "optimized_size_bytes": len(optimized_content),
            },
        )

        return PersonaAvatarUploadResponse(
            success=True,
            message="Persona avatar uploaded successfully",
            persona_avatar_url=avatar_url,
        )

    except HTTPException:
        # Track validation/auth errors
        add_breadcrumb(
            message="persona_avatar_upload_rejected",
            category="persona_avatar",
            level="warning",
            data={"persona_id": str(persona_id)},
        )
        raise
    except Exception as e:
        logger.error(f"Persona avatar upload failed: {e}", exc_info=True)
        capture_exception_with_context(
            e,
            extra={
                "persona_id": str(persona_id),
                "user_id": str(current_user.id),
                "filename": file.filename,
                "content_type": file.content_type,
            },
            tags={
                "component": "api",
                "endpoint": "upload_persona_avatar",
                "operation": "persona_avatar_upload",
                "severity": "high",
                "user_facing": "true",
                "status": "error",
            },
            level="error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Persona avatar upload failed: {str(e)}",
        )


@router.delete(
    "/{persona_id}/avatar",
    response_model=PersonaAvatarDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete persona avatar",
    description="""
    Delete a persona's custom avatar.

    This endpoint:
    1. Deletes avatar from S3 (if S3-hosted)
    2. Sets persona.persona_avatar_url to NULL in database
    3. The persona will fall back to user's profile avatar
    """,
)
async def delete_persona_avatar(
    persona_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PersonaAvatarDeleteResponse:
    """Delete persona avatar"""
    # Track operation start
    add_breadcrumb(
        message="persona_avatar_delete_started",
        category="persona_avatar",
        level="info",
        data={
            "persona_id": str(persona_id),
            "user_id": str(current_user.id),
        },
    )

    try:
        with start_span(op="persona_avatar.delete", description="Delete persona avatar"):
            # Verify persona exists and user owns it
            persona_stmt = select(Persona).where(Persona.id == persona_id)
            persona = (await session.execute(persona_stmt)).scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Persona {persona_id} not found",
            )

        if persona.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this persona's avatar",
            )

        if not persona.persona_avatar_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Persona has no custom avatar to delete",
            )

        # Delete from S3 (non-critical, don't fail if deletion fails)
        try:
            s3_service = create_s3_service(
                endpoint_url=settings.aws_endpoint_url,
                bucket_name=settings.user_data_bucket,
                access_key_id=settings.aws_access_key_id,
                secret_access_key=settings.aws_secret_access_key,
                region=settings.aws_region,
                directory="avatars/personas",
            )
            await _delete_old_persona_avatar_from_s3(persona.persona_avatar_url, s3_service)
        except Exception as e:
            logger.warning(f"Failed to delete persona avatar from S3 (non-critical): {e}")

        # Update persona (MUST be outside the try-except block above)
        persona.persona_avatar_url = None
        await session.commit()

        logger.info(f"Persona avatar deleted for persona {persona_id}")

        # Track successful deletion
        add_breadcrumb(
            message="persona_avatar_delete_success",
            category="persona_avatar",
            level="info",
            data={"persona_id": str(persona_id)},
        )
        capture_message(
            message="Persona avatar deleted successfully",
            level="info",
            tags={
                "operation": "persona_avatar_delete",
                "status": "success",
                "persona_id": str(persona_id),
            },
            extra={
                "persona_id": str(persona_id),
                "user_id": str(current_user.id),
            },
        )

        return PersonaAvatarDeleteResponse(
            success=True,
            message="Persona avatar deleted successfully. Will now use user's profile avatar.",
        )

    except HTTPException:
        # Track validation/auth errors
        add_breadcrumb(
            message="persona_avatar_delete_rejected",
            category="persona_avatar",
            level="warning",
            data={"persona_id": str(persona_id)},
        )
        raise
    except Exception as e:
        logger.error(f"Persona avatar deletion failed: {e}", exc_info=True)
        capture_exception_with_context(
            e,
            extra={
                "persona_id": str(persona_id),
                "user_id": str(current_user.id),
            },
            tags={
                "component": "api",
                "endpoint": "delete_persona_avatar",
                "operation": "persona_avatar_delete",
                "severity": "high",
                "user_facing": "true",
                "status": "error",
            },
            level="error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Persona avatar deletion failed: {str(e)}",
        )
