"""
LiveKit Egress Service - Audio Recording for Voice Sessions

Handles recording of voice agent conversations using LiveKit Cloud egress.
Records full conversations (user + agent) and uploads to S3.

Architecture:
- Room composite egress (records entire room as single audio file)
- Direct S3 upload (no intermediate storage)
- Non-blocking (recording failures don't block voice sessions)

Usage:
    # Context manager (recommended - auto-cleanup)
    async with LiveKitEgressService() as service:
        egress_id = await service.start_room_recording(
            room_name="persona-123-user-456",
            persona_id=persona_id,
            session_id=session_id
        )

    # Manual usage (must call aclose())
    service = LiveKitEgressService()
    egress_id = await service.start_room_recording(...)
    await service.aclose()  # Important: cleanup aiohttp session
"""

import logging
from typing import Optional
from uuid import UUID

from livekit import api
from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class LiveKitEgressService:
    """Stateful service for managing LiveKit egress (recording) operations

    Pattern: Instance methods (maintains API client, logger, config)
    Follows CLAUDE.md service pattern for stateful services.
    """

    def __init__(self):
        """Initialize LiveKit egress service with API client and configuration

        SECURITY: Uses dedicated IAM credentials for egress with fallback to main credentials.
        See docs/LIVEKIT_S3_SECURITY_OPTIONS.md for security best practices.
        """
        self.livekit_url = settings.livekit_url
        self.livekit_api_key = settings.livekit_api_key
        self.livekit_api_secret = settings.livekit_api_secret
        self.s3_bucket = settings.user_data_bucket
        self.aws_region = settings.aws_region

        # SECURITY: Use dedicated egress credentials if set, fallback to main credentials
        # Recommended: Create IAM user "livekit-egress-only" with write-only access to recordings/*
        # This follows principle of least privilege (see LIVEKIT_S3_SECURITY_OPTIONS.md)
        self.aws_access_key_id = (
            settings.aws_livekit_egress_access_key_id or settings.aws_access_key_id
        )
        self.aws_secret_access_key = (
            settings.aws_livekit_egress_secret_access_key or settings.aws_secret_access_key
        )

        # Track which credentials are being used (for logging/monitoring)
        using_dedicated_creds = bool(settings.aws_livekit_egress_access_key_id)

        # Initialize LiveKit API client (one-time setup)
        self.livekit_client = api.LiveKitAPI(
            self.livekit_url, self.livekit_api_key, self.livekit_api_secret
        )

        # Logger for this instance
        self.logger = logging.getLogger(__name__)

        self.logger.info(
            f"LiveKitEgressService initialized (bucket: {self.s3_bucket}, region: {self.aws_region}, "
            f"credentials: {'dedicated egress user' if using_dedicated_creds else 'main AWS credentials'})"
        )

    async def __aenter__(self):
        """Async context manager entry - returns self"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - closes HTTP connections"""
        await self.aclose()
        return False  # Don't suppress exceptions

    async def aclose(self):
        """Close the LiveKit API client and cleanup aiohttp sessions

        IMPORTANT: Call this when done with the service to avoid resource leaks.
        Or use async context manager (async with LiveKitEgressService() as service).
        """
        try:
            await self.livekit_client.aclose()
            self.logger.debug("LiveKitEgressService closed successfully")
        except Exception as e:
            self.logger.warning(f"Error closing LiveKitEgressService: {e}")

    async def start_room_recording(
        self,
        room_name: str,
        persona_id: UUID,
        session_id: UUID,
        output_filename: Optional[str] = None,
    ) -> Optional[str]:
        """Start recording a room conversation (user + agent)

        Records full conversation to S3 as audio-only MP4 file.
        Non-blocking: Returns None on failure but doesn't raise exceptions.

        Args:
            room_name: LiveKit room name to record
            persona_id: Persona ID for organizing recordings
            session_id: Voice session ID for tracking
            output_filename: Optional custom filename (default: {session_id}.mp4)

        Returns:
            egress_id: LiveKit egress ID for tracking, or None if failed

        Example:
            service = LiveKitEgressService()
            egress_id = await service.start_room_recording(
                room_name="persona-123-user-456-1234567890",
                persona_id=UUID("..."),
                session_id=UUID("...")
            )
            if egress_id:
                # Recording started successfully
                # Save egress_id to database for tracking
        """
        try:
            # Generate S3 path: recordings/voice/{persona_id}/{session_id}.mp4
            if not output_filename:
                output_filename = f"{session_id}.mp4"

            s3_path = f"recordings/voice/{persona_id}/{output_filename}"

            self.logger.info(f"🎙️ Starting room recording: room={room_name}, s3_path={s3_path}")

            # Validate AWS credentials
            if not self.aws_access_key_id or not self.aws_secret_access_key:
                self.logger.warning("AWS credentials not configured - cannot start recording")
                return None

            # Create room composite egress request
            egress_request = api.RoomCompositeEgressRequest(
                room_name=room_name,
                # Audio-only recording (no video layout needed for voice agent)
                audio_only=True,
                # Output to S3
                file_outputs=[
                    api.EncodedFileOutput(
                        # File type: MP4 (standard, widely supported)
                        file_type=api.EncodedFileType.MP4,
                        # S3 path (filepath is on EncodedFileOutput, not S3Upload)
                        filepath=s3_path,
                        # S3 configuration
                        s3=api.S3Upload(
                            access_key=self.aws_access_key_id,
                            secret=self.aws_secret_access_key,
                            region=self.aws_region,
                            bucket=self.s3_bucket,
                        ),
                    )
                ],
            )

            # Start egress (async call to LiveKit Cloud)
            egress_info = await self.livekit_client.egress.start_room_composite_egress(
                egress_request
            )

            self.logger.info(f"✅ Room recording started: egress_id={egress_info.egress_id}")
            self.logger.info(f"   S3 destination: s3://{self.s3_bucket}/{s3_path}")

            return egress_info.egress_id

        except Exception as e:
            self.logger.error(f"❌ Failed to start room recording: {e}")

            # REQUIRED: Sentry capture per CLAUDE.md
            capture_exception_with_context(
                e,
                extra={
                    "room_name": room_name,
                    "persona_id": str(persona_id),
                    "session_id": str(session_id),
                    "s3_path": s3_path if "s3_path" in locals() else "unknown",
                    "s3_bucket": self.s3_bucket,
                },
                tags={
                    "component": "livekit_egress",
                    "operation": "start_room_recording",
                    "severity": "medium",  # Non-blocking for voice sessions
                    "user_facing": "false",  # Background recording failure
                },
            )

            # Return None instead of raising - recording is non-critical
            return None

    async def stop_recording(self, egress_id: str) -> bool:
        """Stop an active recording

        Gracefully stops the egress process. LiveKit will finalize the recording
        and upload to S3 before completely stopping.

        Args:
            egress_id: LiveKit egress ID

        Returns:
            True if stopped successfully, False otherwise

        Example:
            service = LiveKitEgressService()
            success = await service.stop_recording(egress_id="EG_...")
            if success:
                # Recording stopped, file will be uploaded to S3
        """
        try:
            self.logger.info(f"🛑 Stopping recording: egress_id={egress_id}")

            # Create StopEgressRequest (required by LiveKit API)
            stop_request = api.StopEgressRequest(egress_id=egress_id)

            # Stop egress (async call to LiveKit Cloud)
            await self.livekit_client.egress.stop_egress(stop_request)

            self.logger.info(f"✅ Recording stopped: egress_id={egress_id}")
            self.logger.info("   S3 upload will complete in background")

            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to stop recording: {e}")

            # REQUIRED: Sentry capture per CLAUDE.md
            capture_exception_with_context(
                e,
                extra={"egress_id": egress_id},
                tags={
                    "component": "livekit_egress",
                    "operation": "stop_recording",
                    "severity": "low",  # Recording may still complete
                    "user_facing": "false",
                },
            )

            # Return False but don't raise - recording may still complete
            return False

    async def get_recording_status(self, egress_id: str) -> Optional[dict]:
        """Get status of a recording

        Retrieves current status from LiveKit Cloud API.

        Args:
            egress_id: LiveKit egress ID

        Returns:
            Recording status information, or None if failed

        Example:
            service = LiveKitEgressService()
            status = await service.get_recording_status(egress_id="EG_...")
            if status:
                print(f"Status: {status['status']}")
                # Status values: EGRESS_STARTING, EGRESS_ACTIVE, EGRESS_ENDING, EGRESS_COMPLETE
        """
        try:
            # List all egress (filter client-side)
            # Note: LiveKit API doesn't have direct get-by-id, so we list and filter
            egress_list = await self.livekit_client.egress.list_egress(room_name="")

            # Find matching egress by ID
            for egress in egress_list:
                if egress.egress_id == egress_id:
                    return {
                        "egress_id": egress.egress_id,
                        "status": str(egress.status),  # EGRESS_STARTING, EGRESS_ACTIVE, etc.
                        "started_at": egress.started_at,
                        "ended_at": egress.ended_at,
                        "error": egress.error if egress.error else None,
                    }

            self.logger.warning(f"Recording not found: egress_id={egress_id}")
            return None

        except Exception as e:
            self.logger.error(f"Failed to get recording status: {e}")

            # REQUIRED: Sentry capture per CLAUDE.md
            capture_exception_with_context(
                e,
                extra={"egress_id": egress_id},
                tags={
                    "component": "livekit_egress",
                    "operation": "get_recording_status",
                    "severity": "low",
                    "user_facing": "false",
                },
            )

            return None
