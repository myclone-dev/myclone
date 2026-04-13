import json
import logging
import random
import time
from datetime import timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_auth import get_current_user_optional
from app.services.livekit_orchestrator import get_orchestrator
from livekit import api
from shared.config import settings
from shared.database.models.database import get_session
from shared.database.models.user import User
from shared.database.repositories.persona_repository import get_persona_repository
from shared.monitoring.sentry_utils import (
    add_breadcrumb,
    capture_exception_with_context,
)
from shared.services.text_usage_service import TextUsageService
from shared.services.voice_session_orchestrator import VoiceSessionOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/livekit", tags=["livekit-auth"])


class ConnectionDetailsRequest(BaseModel):
    expert_username: str
    persona_name: str = "default"
    room_config: Optional[dict] = None
    session_token: Optional[str] = None


class ConnectionDetailsResponse(BaseModel):
    serverUrl: str
    roomName: str
    participantName: str
    participantToken: str
    session_id: Optional[str] = None  # Voice session ID for tracking


class VoiceLimitExceededResponse(BaseModel):
    voice_limit_exceeded: bool = True
    message: str
    used_minutes: float
    limit_minutes: int


class HeartbeatRequest(BaseModel):
    duration_seconds: int


class HeartbeatResponse(BaseModel):
    continue_session: bool
    reason: Optional[str] = None


@router.post("/connection-details", response_model=ConnectionDetailsResponse)
async def get_connection_details(
    request: ConnectionDetailsRequest,
    current_user: User | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_session),
):
    """Get LiveKit connection details using proper LiveKit SDK.

    Supports unified agent architecture for both voice and text modes:
    - Voice mode: audio_input=True, audio_output=True (STT → llm_node → TTS)
    - Text mode: text_input=True, text_output=True (lk.chat → llm_node → lk.transcription)

    Set room_config.text_only_mode=True for text-only chat.

    Checks the persona owner's usage limits before allowing connection:
    - Text mode: Checks text message quota (messages per month)
    - Voice mode: Checks voice minute quota (minutes per month)

    Returns 403 with limit_exceeded details if owner's quota is exhausted.
    """
    try:
        # Log authenticated user status
        if current_user:
            logger.info(
                f"🔐 Authenticated user starting voice call: {current_user.email} (user_id: {current_user.id})"
            )
        else:
            logger.info("👤 Anonymous user starting voice call")

        # Get LiveKit configuration from centralized settings
        livekit_url = settings.livekit_url
        api_key = settings.livekit_api_key
        api_secret = settings.livekit_api_secret

        if not api_key or not api_secret or not livekit_url:
            raise HTTPException(status_code=500, detail="LiveKit configuration missing")

        # Get persona by username and persona name
        persona_repo = get_persona_repository()
        persona = await persona_repo.get_by_username(request.expert_username, request.persona_name)
        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"Expert '{request.expert_username}' and persona '{request.persona_name}' not found",
            )

        # Check if text-only mode is requested FIRST (before voice limit check)
        text_only_mode = False
        if request.room_config:
            text_only_mode = request.room_config.get("text_only_mode", False)

        # Check if voice is enabled for this persona (skip for text-only mode)
        if not text_only_mode and not persona.voice_enabled:
            raise HTTPException(
                status_code=403,
                detail={
                    "voice_disabled": True,
                    "message": "Voice chat is disabled for this persona",
                },
            )

        # Check usage limits based on mode (text vs voice)
        session_orchestrator = VoiceSessionOrchestrator(db)
        remaining_seconds = 0
        limit_seconds = 0

        if text_only_mode:
            # Text-only mode - check TEXT usage limits
            logger.info(f"📝 Text-only mode - checking text limits for persona {persona.id}")
            text_usage_service = TextUsageService(db)
            can_send, remaining_messages, limit_messages = (
                await text_usage_service.check_owner_text_limit(persona.id)
            )

            if not can_send:
                # Owner's text quota is exhausted
                usage = await text_usage_service.get_owner_text_usage(persona.user_id)
                logger.warning(
                    f"Text limit exceeded for persona {persona.id}, owner {persona.user_id}"
                )
                # Track text limit exceeded in Sentry
                add_breadcrumb(
                    message="Text connection rejected - limit exceeded",
                    category="text_session",
                    level="warning",
                    data={
                        "persona_id": str(persona.id),
                        "owner_id": str(persona.user_id),
                        "used_messages": usage["messages_used"],
                        "limit_messages": usage["messages_limit"],
                    },
                )
                # Cleanup before raising
                await session_orchestrator.aclose()
                raise HTTPException(
                    status_code=403,
                    detail={
                        "text_limit_exceeded": True,
                        "message": "Text chat is currently unavailable",
                        "messages_used": usage["messages_used"],
                        "messages_limit": usage["messages_limit"],
                    },
                )
        else:
            # Voice mode - check VOICE usage limits
            logger.info(f"🎙️ Voice mode - checking voice limits for persona {persona.id}")
            can_start, remaining_seconds, limit_seconds = (
                await session_orchestrator.check_owner_voice_limit(persona.id)
            )

            if not can_start:
                # Owner's voice quota is exhausted
                usage = await session_orchestrator.usage_service.get_owner_voice_usage(
                    persona.user_id
                )
                logger.warning(
                    f"Voice limit exceeded for persona {persona.id}, owner {persona.user_id}"
                )
                # Track voice limit exceeded in Sentry
                add_breadcrumb(
                    message="Voice connection rejected - limit exceeded",
                    category="voice_session",
                    level="warning",
                    data={
                        "persona_id": str(persona.id),
                        "owner_id": str(persona.user_id),
                        "used_minutes": usage["minutes_used"],
                        "limit_minutes": usage["minutes_limit"],
                    },
                )
                # Cleanup before raising
                await session_orchestrator.aclose()
                raise HTTPException(
                    status_code=403,
                    detail={
                        "voice_limit_exceeded": True,
                        "message": "Voice chat is currently unavailable",
                        "used_minutes": usage["minutes_used"],
                        "limit_minutes": usage["minutes_limit"],
                    },
                )

        # Generate user ID from participant details
        user_id = f"voice_assistant_user_{random.randint(1, 10000)}"

        # Step 1: Generate room name first
        room_name = f"persona-{persona.id}-user-{user_id}-{int(time.time())}"

        # Generate participant details (matching frontend pattern)
        participant_name = "user"
        participant_identity = user_id  # Use the same user_id for consistency

        # Step 2: Create AccessToken with metadata (user connects with this info)
        video_grants = api.VideoGrants(
            room=room_name,
            room_join=True,
            can_publish=True,
            can_publish_data=True,
            can_subscribe=True,
        )

        # Prepare metadata for the participant (agent will use this to find user)
        participant_metadata = {
            "expert_username": request.expert_username,
            "persona_id": str(persona.id),
            "user_id": user_id,
            "owner_id": str(persona.user_id),  # Persona owner's user_id for search enablement
        }
        if request.session_token:
            participant_metadata["session_token"] = request.session_token

        # Add text-only mode to metadata if enabled (already checked earlier)
        if text_only_mode:
            participant_metadata["text_only_mode"] = True
            logger.info("📝 Text-only mode requested - unified agent will use:")
            logger.info("   • Input:  lk.chat (native text channel)")
            logger.info("   • Output: lk.transcription.final")
            logger.info("   • Processing: llm_node() pipeline")
        else:
            logger.info("🎙️ Voice mode - unified agent will use:")
            logger.info("   • Input:  STT (speech-to-text)")
            logger.info("   • Output: TTS (text-to-speech)")
            logger.info("   • Processing: llm_node() pipeline")

        access_token = (
            api.AccessToken(api_key, api_secret)
            .with_identity(participant_identity)
            .with_name(participant_name)
            .with_ttl(timedelta(minutes=15))
            .with_grants(video_grants)
            .with_metadata(json.dumps(participant_metadata))  # Add metadata here
            .to_jwt()
        )

        # Step 3: Use orchestrator to dispatch agent (agent will find user with metadata)
        orchestrator = await get_orchestrator()
        try:
            await orchestrator.request_persona_chat(
                user_id=user_id,
                persona_id=persona.id,
                agent_name=settings.livekit_agent_name,
                room_name=room_name,  # Pass the pre-generated room name
                session_token=request.session_token,  # Pass session_token to orchestrator
                authenticated_user_id=(
                    str(current_user.id) if current_user else None
                ),  # NEW: Pass authenticated user ID
            )
        except Exception as e:
            logger.error(f"Failed to dispatch agent for persona {persona.id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to dispatch agent for {request.expert_username}: {str(e)}",
            )

        logger.info(f"🎫 Generated SDK token for {request.expert_username} in room: {room_name}")
        logger.info(
            f"🏠 Room created by orchestrator for persona: {persona.id} ({request.expert_username})"
        )

        # Create session record for tracking (voice or text)
        if text_only_mode:
            # Text mode - create text_session record
            text_session = await session_orchestrator.start_text_session(
                persona_id=persona.id,
                room_name=room_name,
                session_token=request.session_token,
            )
            await db.commit()
            session_id = text_session.id
            logger.info(f"📝 Text session started: {text_session.id}")
        else:
            # Voice mode - create voice_session record (with recording if enabled)
            voice_session = await session_orchestrator.start_session(
                persona_id=persona.id,
                room_name=room_name,
                session_token=request.session_token,
            )
            await db.commit()
            session_id = voice_session.id
            logger.info(f"📞 Voice session started: {voice_session.id}")

        # Log the full connection details being returned
        response = ConnectionDetailsResponse(
            serverUrl=livekit_url,
            roomName=room_name,
            participantName=participant_name,
            participantToken=access_token,
            session_id=str(session_id),
        )

        logger.info(
            f"🔗 Connection details: serverUrl={livekit_url}, room={room_name}, participant={participant_name}"
        )
        logger.info(f"🎫 Token preview: {access_token[:50]}...")

        # Track successful session start in Sentry
        session_type = "text" if text_only_mode else "voice"
        add_breadcrumb(
            message=f"{session_type.capitalize()} session initiated successfully",
            category=f"{session_type}_session",
            level="info",
            data={
                "session_id": str(session_id),
                "room_name": room_name,
                "persona_id": str(persona.id),
                "expert_username": request.expert_username,
                "session_type": session_type,
                "remaining_seconds": remaining_seconds if not text_only_mode else None,
            },
        )

        # Cleanup HTTP connections before returning
        await session_orchestrator.aclose()

        return response

    except HTTPException:
        # Re-raise HTTP exceptions (like 403 for limit exceeded)
        # Cleanup before re-raising
        if "session_orchestrator" in locals():
            await session_orchestrator.aclose()
        raise
    except Exception as e:
        logger.error(f"Failed to get connection details: {e}")
        # Capture unexpected errors in Sentry
        capture_exception_with_context(
            e,
            extra={
                "expert_username": request.expert_username,
                "persona_name": request.persona_name,
            },
            tags={
                "component": "livekit",
                "operation": "get_connection_details",
            },
        )
        # Cleanup before raising
        if "session_orchestrator" in locals():
            await session_orchestrator.aclose()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/{session_id}/heartbeat", response_model=HeartbeatResponse)
async def update_session_heartbeat(
    session_id: UUID,
    request: HeartbeatRequest,
    db: AsyncSession = Depends(get_session),
):
    """Update voice session duration (called every 30s by frontend).

    Checks if persona owner's limit has been reached.
    Returns continue_session=False if limit exceeded (triggers disconnect).
    """
    try:
        session_orchestrator = VoiceSessionOrchestrator(db)
        should_continue, reason = await session_orchestrator.update_session_duration(
            session_id=session_id,
            duration_seconds=request.duration_seconds,
        )
        await db.commit()

        if not should_continue:
            logger.warning(f"Voice session {session_id} should disconnect: {reason}")
            # Track disconnect signal in Sentry
            add_breadcrumb(
                message=f"Voice session disconnect signal: {reason}",
                category="voice_session",
                level="warning",
                data={
                    "session_id": str(session_id),
                    "reason": reason,
                    "duration_seconds": request.duration_seconds,
                },
            )

        # Cleanup HTTP connections before returning
        await session_orchestrator.aclose()

        return HeartbeatResponse(
            continue_session=should_continue,
            reason=reason,
        )

    except ValueError as e:
        logger.error(f"Heartbeat error for session {session_id}: {e}")
        # Cleanup before raising
        if "session_orchestrator" in locals():
            await session_orchestrator.aclose()
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Heartbeat failed for session {session_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"session_id": str(session_id), "duration_seconds": request.duration_seconds},
            tags={"component": "livekit", "operation": "heartbeat"},
        )
        # Cleanup before raising
        if "session_orchestrator" in locals():
            await session_orchestrator.aclose()
        raise HTTPException(status_code=500, detail=str(e))
