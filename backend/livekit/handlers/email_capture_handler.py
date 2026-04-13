"""
Email Capture Handler

Manages email capture functionality for lead generation:
- Triggers email capture dialog after threshold
- Handles RPC communication with frontend
- Tracks completion status

Created: 2026-01-25
"""

import json
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class EmailCaptureHandler:
    """
    Handles email capture for lead generation.

    Responsibilities:
    - Tracking message count for threshold
    - Triggering email capture RPC when threshold reached
    - Managing completion state
    """

    def __init__(
        self,
        persona_id: UUID,
        room,
        email_capture_settings: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize email capture handler.

        Args:
            persona_id: Persona UUID
            room: LiveKit room instance
            email_capture_settings: Email capture configuration dict
        """
        self.persona_id = persona_id
        self.room = room

        # Email capture settings
        self.email_capture_enabled = False
        self.email_capture_threshold = 5  # Default threshold
        self.email_capture_require_fullname = False
        self.email_capture_require_phone = False

        if email_capture_settings:
            self.email_capture_enabled = email_capture_settings.get("enabled", False)
            self.email_capture_threshold = email_capture_settings.get("threshold", 5)
            self.email_capture_require_fullname = email_capture_settings.get(
                "require_fullname", False
            )
            self.email_capture_require_phone = email_capture_settings.get("require_phone", False)

        # State tracking - respect orchestrator's completed flag
        self._email_capture_completed = (
            email_capture_settings.get("completed", False) if email_capture_settings else False
        )
        self._message_count = 0

        self.logger = logging.getLogger(__name__)

        # Log initialization
        if self.email_capture_enabled:
            if self._email_capture_completed:
                self.logger.info(
                    "📧 Email capture enabled but already completed for this session - skipping"
                )
            else:
                self.logger.info(
                    f"📧 Email capture enabled (threshold: {self.email_capture_threshold} messages)"
                )

    def increment_message_count(self):
        """Increment message count for threshold tracking."""
        self._message_count += 1

    def mark_completed(self):
        """Mark email capture as completed (from orchestrator or user submission)."""
        self._email_capture_completed = True
        self.logger.info("✅ Email capture marked as completed")

    async def check_and_trigger(self) -> bool:
        """
        Check if email capture should be triggered and prompt user via RPC.

        Returns:
            True if session should continue, False if user declined and should disconnect
        """
        # Check if email capture is enabled
        if not self.email_capture_enabled:
            return True

        # Check if email capture already completed
        if self._email_capture_completed:
            self.logger.info("✅ Email capture already completed for this session - skipping")
            return True

        # Check if threshold reached
        if self._message_count < self.email_capture_threshold:
            self.logger.info(
                f"💬 Message count: {self._message_count}/{self.email_capture_threshold} - continuing normally"
            )
            return True

        self.logger.warning(
            f"📧 Email capture threshold reached ({self._message_count} messages) - prompting user for email"
        )

        try:
            # Get user participant identity
            if not self.room or not self.room.remote_participants:
                self.logger.error("No remote participants found - cannot send RPC")
                return False

            participants = list(self.room.remote_participants.values())
            user_participant = participants[0]
            participant_identity = user_participant.identity

            # Call frontend RPC to show email capture dialog
            # Frontend already has email capture settings from persona endpoint
            self.logger.info(
                f"📞 Calling frontend RPC: requestEmailCapture (to participant: {participant_identity})"
            )
            payload = json.dumps(
                {
                    "action": "email_capture_required",
                    "message": "To continue this conversation, please share your contact information.",
                    "message_count": self._message_count,
                }
            )

            # Perform RPC call from LOCAL participant (agent) to REMOTE participant (user)
            try:
                response = await self.room.local_participant.perform_rpc(
                    destination_identity=participant_identity,
                    method="requestEmailCapture",
                    payload=payload,
                    response_timeout=60.0,  # Wait up to 60 seconds
                )

                response_data = json.loads(response)
                self.logger.info(f"✅ RPC response received: {response_data}")

                # Check user response
                if response_data.get("action") == "submitted":
                    self.logger.info("✅ User submitted email - continuing session")
                    # Mark as completed to prevent re-prompting
                    self._email_capture_completed = True
                    # Email will be saved by frontend via API
                    return True
                else:
                    self.logger.info("❌ User declined email capture - will disconnect")
                    return False

            except TimeoutError:
                self.logger.warning(
                    "⏱️ RPC timeout - frontend didn't respond. "
                    "Email capture handler not registered on frontend. Session continuing."
                )
                return True  # Allow session to continue
            except Exception as rpc_error:
                # Catch any RPC-related errors (including LiveKit SDK RpcError)
                self.logger.warning(
                    f"⚠️ RPC failed: {type(rpc_error).__name__}. "
                    f"Frontend may not have email capture handler registered. Session continuing."
                )
                return True  # Allow session to continue

        except Exception as e:
            self.logger.error(f"❌ Error checking email capture: {e}", exc_info=True)
            capture_exception_with_context(
                e,
                extra={
                    "message_count": self._message_count,
                    "persona_id": str(self.persona_id),
                    "email_capture_enabled": self.email_capture_enabled,
                },
                tags={
                    "component": "email_capture_handler",
                    "operation": "check_and_trigger",
                    "severity": "medium",
                    "user_facing": "true",
                },
            )
            # On error, allow session to continue (graceful degradation)
            return True
