"""
Default Lead Capture Handler

Lightweight handler that captures basic visitor contact info (name, email, phone)
for ALL agents, regardless of whether a workflow is configured.

This is NOT a workflow — it's a simple always-on lead capture layer.
When a full conversational workflow is active, this handler is disabled
since the workflow handles field capture (including these basics).

Flow:
1. Agent extracts name/email/phone naturally in conversation
2. Agent calls update_lead_fields() tool (same tool as workflows)
3. Handler tracks progress, returns "still need X" or "all captured"
4. On completion → sends RPC to frontend with captured data
5. Frontend calls POST /sessions/{token}/capture-lead
6. Backend creates visitor User, sets JWT cookie
"""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)

# Hardcoded field definitions for default lead capture
DEFAULT_CAPTURE_FIELDS: List[Dict[str, Any]] = [
    {
        "field_id": "contact_name",
        "field_type": "text",
        "label": "Full Name",
        "description": "The visitor's full name",
        "clarifying_question": "Could I get your name?",
    },
    {
        "field_id": "contact_email",
        "field_type": "email",
        "label": "Email Address",
        "description": "The visitor's email address",
        "clarifying_question": "What's the best email to reach you at?",
    },
    {
        "field_id": "contact_phone",
        "field_type": "phone",
        "label": "Phone Number",
        "description": "The visitor's phone number",
        "clarifying_question": "And what's a good phone number for you?",
    },
]

DEFAULT_FIELD_IDS = [f["field_id"] for f in DEFAULT_CAPTURE_FIELDS]

# Value the LLM is instructed to use when user refuses a field.
# Keep this minimal to avoid false-positive data loss.
DECLINED_VALUES = {"declined"}


class DefaultCaptureHandler:
    """
    Lightweight handler for capturing basic visitor contact info.

    Unlike workflow handlers, this:
    - Has no WorkflowSession DB record
    - Has no scoring, confirmation, or tone control
    - Tracks state in memory only
    - Sends RPC to frontend on completion for User creation + cookie
    """

    def __init__(
        self,
        persona_id: UUID,
        room: Any,
        session_token: Optional[str] = None,
    ):
        self.persona_id = persona_id
        self.room = room
        self.session_token = session_token
        self.logger = logging.getLogger(__name__)

        # In-memory field tracking
        self._captured_fields: Dict[str, str] = {}
        self._is_active = False
        self._capture_completed = False

        self.logger.info("✅ [DEFAULT_CAPTURE] Handler initialized")

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_active(self) -> bool:
        """Whether capture is currently in progress."""
        return self._is_active

    @property
    def is_captured(self) -> bool:
        """Whether all fields have been captured and sent to backend."""
        return self._capture_completed

    @property
    def field_definitions(self) -> List[Dict[str, Any]]:
        """Return the hardcoded field definitions."""
        return DEFAULT_CAPTURE_FIELDS

    @property
    def required_field_ids(self) -> List[str]:
        """Return the field IDs."""
        return DEFAULT_FIELD_IDS

    @property
    def captured_fields(self) -> Dict[str, str]:
        """Return a copy of captured fields with declined values stripped (for backfill)."""
        return {
            k: v
            for k, v in self._captured_fields.items()
            if v.lower().strip() not in DECLINED_VALUES
        }

    # =========================================================================
    # Core Methods
    # =========================================================================

    def start(self) -> None:
        """Mark capture as active (called on first field extraction)."""
        if not self._is_active:
            self._is_active = True
            self.logger.info("🚀 [DEFAULT_CAPTURE] Capture started")

    async def store_extracted_fields(self, fields: Dict[str, str]) -> str:
        """
        Store extracted fields and return progress status.

        Args:
            fields: Dict of field_id -> value pairs

        Returns:
            Status message for the LLM
        """
        # Auto-start on first call
        if not self._is_active and not self._capture_completed:
            self.start()

        # Filter empty values
        fields = {k: v.strip() for k, v in fields.items() if v and v.strip()}
        if not fields:
            return "Skipped - no valid values provided. Only call with actual data."

        self.logger.info(f"📥 [DEFAULT_CAPTURE] Storing fields: {list(fields.keys())}")

        # Validate field IDs
        invalid_fields = [fid for fid in fields if fid not in DEFAULT_FIELD_IDS]
        if invalid_fields:
            return f"Error: Unknown field_ids: {invalid_fields}. Valid fields: {DEFAULT_FIELD_IDS}"

        # Merge with existing
        self._captured_fields.update(fields)

        # Late arrival after completion (e.g., phone comes in after user initially declined)
        # → re-send RPC with the updated data so backend gets the full picture
        if self._capture_completed:
            self.logger.info(
                f"📥 [DEFAULT_CAPTURE] Late field(s) after completion: {list(fields.keys())} "
                "— re-sending RPC with updated data"
            )
            await self._notify_frontend()
            return (
                "LEAD CAPTURED — Additional contact info saved. "
                "Continue helping the visitor naturally."
            )

        # Calculate progress (declined counts as "resolved" — not missing)
        captured = [fid for fid in DEFAULT_FIELD_IDS if fid in self._captured_fields]
        missing = [fid for fid in DEFAULT_FIELD_IDS if fid not in self._captured_fields]

        self.logger.info(
            f"📊 [DEFAULT_CAPTURE] Progress: {len(captured)}/{len(DEFAULT_FIELD_IDS)} "
            f"Captured: {captured}, Missing: {missing}"
        )

        # All fields resolved (captured or declined)?
        if not missing:
            return await self._handle_capture_complete()

        # Still missing — tell LLM what to ask next
        next_field = next((f for f in DEFAULT_CAPTURE_FIELDS if f["field_id"] == missing[0]), None)
        next_question = next_field["clarifying_question"] if next_field else ""

        saved_str = ", ".join(fields.keys())
        return f"Saved: {saved_str}. Still need: {missing}. Ask user: '{next_question}'"

    async def _handle_capture_complete(self) -> str:
        """Handle when all fields are resolved (captured or declined) — notify frontend."""
        # Log which fields were declined vs actually provided
        declined = [
            fid
            for fid, val in self._captured_fields.items()
            if val.lower().strip() in DECLINED_VALUES
        ]
        provided = [
            fid
            for fid, val in self._captured_fields.items()
            if val.lower().strip() not in DECLINED_VALUES
        ]

        self.logger.info(
            f"🎉 [DEFAULT_CAPTURE] All fields resolved — notifying frontend. "
            f"Provided: {provided}, Declined: {declined}"
        )

        # Mark as completed BEFORE sending RPC to prevent race condition
        # (if another tool call arrives during the RPC await, the late-arrival
        # path at store_extracted_fields will handle it correctly)
        self._capture_completed = True
        self._is_active = False

        # Send RPC to frontend so it can call the capture-lead endpoint
        await self._notify_frontend()

        # RPC success/failure doesn't affect the conversation — _notify_frontend
        # already logs specific failure reasons (timeout, RPC error, exception)
        return (
            "LEAD CAPTURED — Contact information has been saved. "
            "Continue the conversation naturally and help the visitor with their needs."
        )

    async def _notify_frontend(self) -> bool:
        """
        Send captured lead data to frontend via RPC.

        Frontend will call POST /sessions/{token}/capture-lead
        to create the visitor user and set the JWT cookie.
        """
        try:
            if not self.room or not self.room.remote_participants:
                self.logger.warning("No remote participants — cannot send RPC")
                return False

            participants = list(self.room.remote_participants.values())
            user_participant = participants[0]
            participant_identity = user_participant.identity

            # Send actual values to frontend; declined fields → empty string
            def _clean(field_id: str) -> str:
                val = self._captured_fields.get(field_id, "")
                return "" if val.lower().strip() in DECLINED_VALUES else val

            payload = json.dumps(
                {
                    "action": "lead_captured",
                    "session_token": self.session_token,
                    "fullname": _clean("contact_name"),
                    "email": _clean("contact_email"),
                    "phone": _clean("contact_phone"),
                }
            )

            self.logger.info(
                f"📞 [DEFAULT_CAPTURE] Sending leadCaptured RPC to {participant_identity}"
            )

            try:
                response = await self.room.local_participant.perform_rpc(
                    destination_identity=participant_identity,
                    method="leadCaptured",
                    payload=payload,
                    response_timeout=10.0,
                )

                response_data = json.loads(response)
                self.logger.info(f"✅ [DEFAULT_CAPTURE] RPC response: {response_data}")
                return response_data.get("action") == "saved"

            except TimeoutError:
                self.logger.warning(
                    "⏱️ [DEFAULT_CAPTURE] RPC timeout — frontend may not have handler registered"
                )
                return False
            except Exception as rpc_error:
                self.logger.warning(
                    f"⚠️ [DEFAULT_CAPTURE] RPC failed: {type(rpc_error).__name__}: {rpc_error}"
                )
                return False

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "session_token": self.session_token,
                    "captured_fields": list(self._captured_fields.keys()),
                },
                tags={
                    "component": "default_capture_handler",
                    "operation": "notify_frontend",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ [DEFAULT_CAPTURE] Error notifying frontend: {e}")
            return False

    def reset(self) -> None:
        """Reset capture state."""
        self._captured_fields = {}
        self._is_active = False
        self._capture_completed = False
