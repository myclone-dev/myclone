"""
Voice Session Orchestrator - Coordinates Session Management

Orchestrates all voice AND text session operations by coordinating:
1. VoiceUsageService - Voice usage tracking, limits, quotas
2. TextUsageService - Text usage tracking, limits, quotas
3. LiveKitEgressService - Recording management (voice only)

This provides clean separation of concerns:
- Usage tracking logic stays in VoiceUsageService/TextUsageService
- Recording logic stays in LiveKitEgressService
- Orchestrator coordinates both for complete session lifecycle

Usage:
    # Context manager (recommended - auto-cleanup)
    async with VoiceSessionOrchestrator(db) as orchestrator:
        # Voice session
        voice_session = await orchestrator.start_voice_session(
            persona_id=persona_id,
            room_name=room_name,
            session_token=session_token
        )

        # Text session
        text_session = await orchestrator.start_text_session(
            persona_id=persona_id,
            room_name=room_name,
            session_token=session_token
        )

    # Manual usage (must call aclose())
    orchestrator = VoiceSessionOrchestrator(db)
    session = await orchestrator.start_voice_session(...)
    await orchestrator.aclose()  # Important: cleanup HTTP connections
"""

import logging
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.constants.livekit_constants import is_recording_allowed_for_user
from shared.database.models.database import Persona
from shared.database.models.text_session import TextSession
from shared.database.models.voice_session import RecordingStatus, VoiceSession
from shared.services.livekit_egress_service import LiveKitEgressService
from shared.services.text_usage_service import TextUsageService
from shared.services.voice_usage_service import VoiceUsageService

logger = logging.getLogger(__name__)


class VoiceSessionOrchestrator:
    """Orchestrates voice and text session lifecycle (usage tracking + recording)

    Pattern: Composition over inheritance
    - Delegates voice usage tracking to VoiceUsageService
    - Delegates text usage tracking to TextUsageService
    - Delegates recording to LiveKitEgressService (voice only)
    - Coordinates all for complete session management
    """

    def __init__(self, db: AsyncSession):
        """Initialize orchestrator with database session

        Args:
            db: SQLAlchemy async session for database operations
        """
        self.db = db
        self.usage_service = VoiceUsageService(db)  # Voice usage
        self.text_usage_service = TextUsageService(db)  # Text usage
        self.recording_service = LiveKitEgressService()
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """Async context manager entry - returns self"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - closes HTTP connections"""
        await self.aclose()
        return False  # Don't suppress exceptions

    async def aclose(self):
        """Close the orchestrator and cleanup resources

        IMPORTANT: Call this when done with the orchestrator to avoid resource leaks.
        Or use async context manager (async with VoiceSessionOrchestrator(db) as orchestrator).
        """
        try:
            await self.recording_service.aclose()
            self.logger.debug("VoiceSessionOrchestrator closed successfully")
        except Exception as e:
            self.logger.warning(f"Error closing VoiceSessionOrchestrator: {e}")

    async def check_owner_voice_limit(self, persona_id: UUID) -> Tuple[bool, int, int]:
        """Check if persona owner has remaining voice quota

        Delegates to VoiceUsageService.

        Args:
            persona_id: The persona being called

        Returns:
            Tuple of (can_start, remaining_seconds, limit_seconds)
        """
        return await self.usage_service.check_owner_voice_limit(persona_id)

    async def start_session(
        self,
        persona_id: UUID,
        room_name: str,
        session_token: Optional[str] = None,
    ) -> VoiceSession:
        """Start a new voice session with optional recording

        Coordinates:
        1. Create session record (via VoiceUsageService)
        2. Start recording if enabled (via LiveKitEgressService)

        Recording is non-blocking - failures don't prevent voice sessions.

        Args:
            persona_id: The persona being called
            room_name: LiveKit room name
            session_token: Caller's session token (for analytics)

        Returns:
            Created VoiceSession with recording info populated if enabled
        """
        # Step 1: Create session (usage tracking)
        self.logger.info(f"📞 Starting voice session for persona {persona_id}")
        session = await self.usage_service.start_voice_session(
            persona_id=persona_id,
            room_name=room_name,
            session_token=session_token,
        )

        # Step 2: Start recording if enabled (non-blocking)
        if settings.enable_voice_recording:
            # Check if recording is allowed for this user (persona owner)
            # Enterprise tier users get recording enabled
            if await is_recording_allowed_for_user(session.persona_owner_id, self.db):
                self.logger.info(
                    f"🎙️ Recording enabled for session {session.id} (user {session.persona_owner_id} is allowed)"
                )
                try:
                    egress_id = await self.recording_service.start_room_recording(
                        room_name=room_name,
                        persona_id=persona_id,
                        session_id=session.id,
                    )

                    if egress_id:
                        # Update session with recording info
                        session.egress_id = egress_id
                        session.recording_status = RecordingStatus.ACTIVE
                        session.recording_s3_path = (
                            f"recordings/voice/{persona_id}/{session.id}.mp4"
                        )
                        await self.db.flush()
                        self.logger.info(
                            f"✅ Recording started for session {session.id}, egress_id={egress_id}"
                        )
                    else:
                        # Recording failed but don't block voice session
                        session.recording_status = RecordingStatus.FAILED
                        await self.db.flush()
                        self.logger.warning(f"⚠️ Recording failed to start for session {session.id}")

                except Exception as e:
                    # Recording errors should not block voice sessions
                    session.recording_status = RecordingStatus.FAILED
                    await self.db.flush()
                    self.logger.error(f"❌ Recording error for session {session.id}: {e}")
                    # Exception already captured in LiveKitEgressService
            else:
                self.logger.info(
                    f"ℹ️ Recording not allowed for session {session.id} (user {session.persona_owner_id} not on enterprise tier)"
                )
        else:
            self.logger.info(f"ℹ️ Recording disabled globally for session {session.id}")

        return session

    async def update_session_duration(
        self, session_id: UUID, duration_seconds: int
    ) -> Tuple[bool, Optional[str]]:
        """Update session duration (heartbeat) and check limits

        Delegates to VoiceUsageService.

        Args:
            session_id: Voice session ID
            duration_seconds: Current session duration in seconds

        Returns:
            Tuple of (should_continue, reason)
        """
        return await self.usage_service.update_session_duration(session_id, duration_seconds)

    async def end_session(self, session_id: UUID, final_duration_seconds: int) -> VoiceSession:
        """End a voice session and stop recording

        Coordinates:
        1. Stop recording if active (via LiveKitEgressService)
        2. Update session and usage (via VoiceUsageService)

        Args:
            session_id: Voice session ID
            final_duration_seconds: Final session duration in seconds

        Returns:
            Updated VoiceSession
        """
        self.logger.info(f"🛑 Ending voice session {session_id}")

        # Get session to check recording status
        session = await self.usage_service.get_session_by_id(session_id)
        if not session:
            raise ValueError(f"Voice session {session_id} not found")

        # Step 1: Stop recording if active (non-blocking)
        if session.egress_id and session.recording_status == RecordingStatus.ACTIVE:
            self.logger.info(f"🛑 Stopping recording for session {session_id}")
            try:
                success = await self.recording_service.stop_recording(session.egress_id)

                if success:
                    session.recording_status = RecordingStatus.COMPLETED
                    self.logger.info(f"✅ Recording stopped for session {session_id}")
                else:
                    session.recording_status = RecordingStatus.FAILED
                    self.logger.warning(f"⚠️ Recording stop failed for session {session_id}")

            except Exception as e:
                # Recording errors should not block session end
                session.recording_status = RecordingStatus.FAILED
                self.logger.error(f"❌ Recording stop error for session {session_id}: {e}")
                # Exception already captured in LiveKitEgressService

        # Step 2: Update session and usage (delegates to VoiceUsageService)
        # Note: We need to pass the recording_status update to the service
        session = await self.usage_service.end_voice_session(
            session_id=session_id,
            final_duration_seconds=final_duration_seconds,
        )

        # Update recording status if we changed it
        if session.egress_id:
            await self.db.flush()

        return session

    # ======================================================================
    # TEXT SESSION METHODS (New)
    # ======================================================================

    async def check_owner_text_limit(self, persona_id: UUID) -> Tuple[bool, int, int]:
        """Check if persona owner has remaining text message quota

        Delegates to TextUsageService.

        Args:
            persona_id: The persona being called

        Returns:
            Tuple of (can_send, remaining_messages, limit_messages)
        """
        return await self.text_usage_service.check_owner_text_limit(persona_id)

    async def start_text_session(
        self,
        persona_id: UUID,
        room_name: str,
        session_token: Optional[str] = None,
    ) -> TextSession:
        """Start a new text session (text-only chat)

        Creates text_sessions record for tracking message count.
        No recording - text sessions don't need LiveKit egress.

        Args:
            persona_id: The persona being called
            room_name: LiveKit room name
            session_token: Caller's session token (for analytics)

        Returns:
            Created TextSession
        """
        from sqlalchemy import select

        self.logger.info(f"📝 Starting text session for persona {persona_id}")

        # Get persona to find owner
        persona_result = await self.db.execute(select(Persona).where(Persona.id == persona_id))
        persona = persona_result.scalar_one_or_none()

        if not persona:
            raise ValueError(f"Persona {persona_id} not found")

        # Create text session record
        text_session = TextSession(
            persona_id=persona_id,
            persona_owner_id=persona.user_id,
            room_name=room_name,
            session_token=session_token,
            message_count=0,
        )

        self.db.add(text_session)
        await self.db.flush()

        self.logger.info(f"✅ Text session created: {text_session.id}")
        return text_session

    async def end_text_session(self, session_id: UUID, final_message_count: int) -> TextSession:
        """End a text session and record usage

        Coordinates:
        1. Mark session as ended
        2. Record text usage (bulk update to user_usage_cache)

        Args:
            session_id: Text session ID
            final_message_count: Total messages sent in session

        Returns:
            Updated TextSession
        """
        from datetime import datetime, timezone

        from sqlalchemy import select

        self.logger.info(f"🛑 Ending text session {session_id}")

        # Get session
        result = await self.db.execute(select(TextSession).where(TextSession.id == session_id))
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError(f"Text session {session_id} not found")

        # Update session
        session.message_count = final_message_count
        session.ended_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Record usage in bulk (one DB write for entire session)
        if final_message_count > 0:
            await self.text_usage_service.record_multiple_messages(
                persona_id=session.persona_id, message_count=final_message_count
            )
            self.logger.info(
                f"✅ Text session ended: {session_id}, recorded {final_message_count} messages"
            )
        else:
            self.logger.info(f"✅ Text session ended: {session_id}, no messages sent")

        return session

    async def get_text_session_by_room(self, room_name: str) -> Optional[TextSession]:
        """Get text session by room name

        Args:
            room_name: LiveKit room name

        Returns:
            TextSession if found, None otherwise
        """
        from sqlalchemy import select

        result = await self.db.execute(
            select(TextSession).where(TextSession.room_name == room_name)
        )
        return result.scalar_one_or_none()
