"""
Conversational Workflow Handler

Handles natural language lead capture workflows. This is the main orchestrator
that coordinates the flow of a conversational lead capture session.

RESPONSIBILITIES:
- Session lifecycle (start, store fields, complete)
- Progress tracking
- Confirmation flow coordination
- Delegating to services for specific logic

WHAT IT DELEGATES:
- Tone formatting -> WorkflowToneService
- Lead scoring & summary -> LeadScoringService (background task, LLM-only)

WHY LLM-ONLY SCORING:
- Rule-based scoring is brittle ("Immediate" vs "immediately" vs "ASAP")
- LLM understands intent and nuance in free-form text
- Single source of truth - no conflicting scores
- Structured JSON output for easy frontend rendering

FLOW:
1. User completes all required fields
2. Handler saves extracted_fields to DB
3. Background task fires LeadScoringService.evaluate_lead()
4. LLM scores lead and generates summary
5. result_data updated with complete evaluation
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from livekit.services.workflow_field_extractor import ExtractedFieldValue
from livekit.services.workflow_tone_service import WorkflowToneService
from shared.database.models.database import async_session_maker
from shared.database.repositories.workflow_repository import WorkflowRepository
from shared.monitoring.sentry_utils import capture_exception_with_context

from .base import BaseWorkflowHandler

logger = logging.getLogger(__name__)


class ConversationalWorkflowHandler(BaseWorkflowHandler):
    """
    Handler for conversational (lead capture) workflows.

    Uses single-LLM approach where the main LLM extracts field values
    directly via update_lead_fields() tool calls (batch operation).

    Delegates to services:
    - WorkflowToneService: Tone/style formatting
    - WorkflowSummaryService: Lead summary generation
    """

    def __init__(
        self,
        workflow_data: Optional[Dict[str, Any]],
        persona_id: UUID,
        output_callback: Callable,
        text_only_mode: bool = False,
        session_token: Optional[str] = None,
    ):
        """Initialize conversational workflow handler."""
        super().__init__(
            workflow_data=workflow_data,
            persona_id=persona_id,
            output_callback=output_callback,
            text_only_mode=text_only_mode,
            session_token=session_token,
        )

        # Initialize services
        self.tone_service = WorkflowToneService(workflow_data)
        self._condition_evaluator = None
        # NOTE: scoring_engine and summary_service removed - now handled by
        # LeadScoringService in background task (LLM-only scoring)

        # Log field configuration
        if workflow_data:
            self.logger.info(
                f"🔍 [CONVERSATIONAL] Required fields: {len(workflow_data.get('required_fields', []))}"
            )
            self.logger.info(
                f"🔍 [CONVERSATIONAL] Optional fields: {len(workflow_data.get('optional_fields', []))}"
            )
            self.logger.info(f"🔍 [CONVERSATIONAL] Tone: {self.tone_service.tone}")

    # =========================================================================
    # Tone Control Methods (delegate to WorkflowToneService)
    # =========================================================================
    # These methods provide a convenient interface while delegating to the service.
    # This keeps the handler API stable even if the service implementation changes.

    def _get_tone(self) -> str:
        """Get the configured tone from extraction_strategy."""
        return self.tone_service.tone

    def _get_tone_config(self, tone: Optional[str] = None) -> Dict[str, Any]:
        """Get tone preset configuration."""
        return self.tone_service.get_tone_config(tone)

    def _get_acknowledgment(self, tone: Optional[str] = None) -> str:
        """Get an acknowledgment phrase for the given tone."""
        return self.tone_service.get_acknowledgment(tone)

    def _format_question_with_tone(
        self, base_question: Optional[str], field_label: str, tone: Optional[str] = None
    ) -> str:
        """Format a clarifying question using the tone's question prefix."""
        return self.tone_service.format_question(base_question, field_label, tone)

    def _build_confirmation_summary_with_tone(
        self,
        current_fields: Dict[str, Any],
        required_fields: List[Dict[str, Any]],
        required_field_ids: List[str],
    ) -> str:
        """Build confirmation summary with tone-appropriate intro."""
        return self.tone_service.build_confirmation_summary(
            current_fields, required_fields, required_field_ids
        )

    async def start_workflow(self, send_opening_message: bool = True) -> None:
        """
        Start the conversational workflow.

        Args:
            send_opening_message: Whether to send opening message (False for auto-start)
        """
        start_time = time.perf_counter()
        print("=" * 70)
        print("🚀 [CONVERSATIONAL_HANDLER] start_workflow() START")
        print(f"   send_opening_message: {send_opening_message}")

        if not self.workflow_data:
            return

        try:
            workflow_title = self.workflow_data.get("title", "Lead Capture")

            # Create session
            self._workflow_session_id = await self._create_session()
            print(f"   Session created: {self._workflow_session_id}")

            # Get extraction strategy
            extraction_strategy = self.workflow_data.get("extraction_strategy", {})

            # Send opening message only if explicitly starting
            if send_opening_message:
                if self.workflow_data.get("opening_message"):
                    await self._output_message(
                        self.workflow_data["opening_message"], allow_interruptions=False
                    )
                else:
                    opening_question = extraction_strategy.get(
                        "opening_question",
                        "Thanks for reaching out! I'd love to learn more about what you're looking for. What brings you here today?",
                    )
                    await self._output_message(opening_question, allow_interruptions=True)
            else:
                self.logger.info("⏩ [CONVERSATIONAL] Auto-started - skipping opening message")

            total_time = (time.perf_counter() - start_time) * 1000
            print(f"⏱️ [CONVERSATIONAL_HANDLER] start_workflow() TOTAL: {total_time:.2f}ms")
            print("=" * 70)

            self.logger.info(f"📋 [CONVERSATIONAL] Started workflow: {workflow_title}")

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "workflow_id": self.workflow_data.get("workflow_id"),
                },
                tags={
                    "component": "conversational_workflow_handler",
                    "operation": "start_workflow",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Workflow start failed: {e}", exc_info=True)

    async def store_extracted_fields(self, fields: dict[str, str]) -> str:
        """
        Store multiple extracted fields in a single atomic operation.

        This eliminates race conditions when the LLM extracts multiple fields
        from a single user message - all fields are stored together and
        progress is calculated accurately after all writes complete.

        Args:
            fields: Dictionary of field_id -> value pairs to store

        Returns:
            Status message with remaining fields to collect
        """
        total_start = time.perf_counter()

        # Filter out empty values
        fields = {k: v.strip() for k, v in fields.items() if v and v.strip()}

        if not fields:
            self.logger.debug("⏭️ Skipping - all values were empty")
            return "Skipped - no valid values provided. Only call with actual data."

        print("=" * 70)
        print("📥 [STORE_FIELDS] ===== store_extracted_fields() START =====")
        print(f"   Fields: {list(fields.keys())}")
        for field_id, value in fields.items():
            print(f"   - {field_id}: '{value[:50]}{'...' if len(value) > 50 else ''}'")
        print(f"   Session ID: {self._workflow_session_id}")

        self.logger.info(f"📥 [STORE_FIELDS] Storing {len(fields)} fields: {list(fields.keys())}")

        if not self._workflow_session_id:
            print("   ❌ ERROR: No active workflow session")
            return "Error: No active workflow session. Call start_workflow first."

        if not self.workflow_data:
            print("   ❌ ERROR: No workflow data configured")
            return "Error: No workflow data configured."

        # Get field definitions
        required_fields = self.workflow_data.get("required_fields", [])
        optional_fields = self.workflow_data.get("optional_fields", [])
        all_fields_def = required_fields + optional_fields
        all_field_ids = [f["field_id"] for f in all_fields_def]

        print(f"   Valid field IDs: {all_field_ids}")

        # Validate all field_ids
        invalid_fields = [fid for fid in fields.keys() if fid not in all_field_ids]
        if invalid_fields:
            print(f"   ❌ ERROR: Unknown field_ids: {invalid_fields}")
            return f"Error: Unknown field_ids: {invalid_fields}. Valid: {all_field_ids}"

        # Build extracted field values using Pydantic model
        extracted_values = {}
        for field_id, value in fields.items():
            field_def = next((f for f in all_fields_def if f["field_id"] == field_id), None)
            print(
                f"   ✓ Field '{field_id}' -> {field_def.get('label', field_id) if field_def else 'unknown'}"
            )

            extracted_values[field_id] = ExtractedFieldValue(
                value=value,
                confidence=1.0,
                extraction_method="direct_tool_call",
                raw_input=value,
            ).model_dump()

        # Update database - single atomic operation
        db_start = time.perf_counter()
        async with async_session_maker() as session:
            workflow_repo = WorkflowRepository(session)

            # Get current fields
            current_session = await workflow_repo.get_session_by_id(self._workflow_session_id)
            existing_fields = (
                dict(current_session.extracted_fields or {}) if current_session else {}
            )

            # Merge ALL new fields with existing
            merged_fields = {**existing_fields, **extracted_values}

            # Filter required fields to only those relevant given current extracted data
            relevant_required = self._get_relevant_fields(required_fields, merged_fields)
            required_field_ids = [f["field_id"] for f in relevant_required]
            captured_required = [fid for fid in required_field_ids if fid in merged_fields]
            missing_required = [fid for fid in required_field_ids if fid not in merged_fields]

            progress = (
                int((len(captured_required) / len(required_field_ids)) * 100)
                if required_field_ids
                else 100
            )

            # Save ALL fields to database in one operation
            updated_session = await workflow_repo.update_extracted_fields(
                self._workflow_session_id, extracted_values, progress_percentage=progress
            )

            if not updated_session:
                print("   ❌ ERROR: Failed to update workflow session")
                return "Error: Failed to update workflow session"

            current_fields = updated_session.extracted_fields or {}

        db_time = (time.perf_counter() - db_start) * 1000
        print(f"   ✓ DB update completed in {db_time:.2f}ms")
        print(f"   ✓ Saved {len(fields)} fields in single transaction")
        print(f"   ✓ Progress saved to DB: {progress}%")
        print(f"   Current fields: {list(current_fields.keys())}")

        self.logger.info(
            f"✅ [STORE_FIELDS] Saved {len(fields)} fields. "
            f"Total: {len(current_fields)}. Progress: {progress}%"
        )

        print(
            f"   📊 Progress: {progress}% ({len(captured_required)}/{len(required_field_ids)} required)"
        )
        print(f"   ✓ Captured: {captured_required}")
        print(f"   ✗ Missing: {missing_required}")

        # Check if all required fields captured
        if not missing_required:
            print("   🎉 ALL REQUIRED FIELDS CAPTURED!")
            return await self._handle_all_fields_captured(
                current_fields, relevant_required, required_field_ids, total_start
            )

        # Still missing fields - return status with next question
        return self._build_progress_response(
            list(fields.keys()),  # Pass list of saved fields
            progress,
            captured_required,
            missing_required,
            relevant_required,
            required_field_ids,
            current_fields,
            total_start,
        )

    async def _handle_all_fields_captured(
        self,
        current_fields: dict,
        required_fields: list,
        required_field_ids: list,
        total_start: float,
    ) -> str:
        """Handle case when all required fields are captured."""
        extraction_strategy = (
            self.workflow_data.get("extraction_strategy", {}) if self.workflow_data else {}
        )
        needs_confirmation = extraction_strategy.get("confirmation_required", True)
        print(f"   Needs confirmation: {needs_confirmation}")

        if needs_confirmation:
            # Build tone-aware confirmation summary
            confirmation_summary = self._build_confirmation_summary_with_tone(
                current_fields, required_fields, required_field_ids
            )

            total_time = (time.perf_counter() - total_start) * 1000
            print(f"   ⏱️ Total time: {total_time:.2f}ms")
            print("   → Returning: AWAITING_CONFIRMATION")
            print("=" * 70)

            # If workflow has agent_instructions, include them in the tool
            # response so the LLM sees them right at confirmation time.
            agent_instructions = ""
            if self.workflow_data and self.workflow_data.get("agent_instructions"):
                agent_instructions = (
                    f"\n\n⚠️ FOLLOW THESE RULES FOR YOUR CONFIRMATION:\n"
                    f"{self.workflow_data['agent_instructions']}"
                )

            return (
                f"AWAITING_CONFIRMATION - All required information collected!\n"
                f"{confirmation_summary}\n\n"
                f"INSTRUCTIONS:\n"
                f"1. Read the summary above to the user and ask if it's correct\n"
                f"2. Wait for user response\n"
                f"3. If user says YES/correct/confirmed → call confirm_lead_capture() tool\n"
                f"4. If user says NO or wants changes → ask what to update, then call update_lead_fields() with corrections"
                f"{agent_instructions}"
            )
        else:
            # Auto-complete without confirmation
            total_time = (time.perf_counter() - total_start) * 1000
            print(f"   ⏱️ Total time: {total_time:.2f}ms")
            print("   → Auto-completing workflow (no confirmation required)")
            print("=" * 70)
            return await self.complete_workflow(current_fields)

    def _get_relevant_fields(self, fields: list[dict], current_extracted: dict) -> list[dict]:
        """Filter fields to only those whose relevant_when condition is met.

        Fields without a relevant_when condition are always included.
        Fields with a condition are only included if the condition evaluates to True
        against the currently extracted data.
        """
        if self._condition_evaluator is None:
            from livekit.services.workflow_condition_evaluator import ConditionEvaluator

            self._condition_evaluator = ConditionEvaluator()

        relevant = []
        for f in fields:
            condition = f.get("relevant_when")
            if condition is None:
                relevant.append(f)
            elif self._condition_evaluator.evaluate(condition, current_extracted):
                relevant.append(f)
        return relevant

    def _build_progress_response(
        self,
        saved_fields: str | list,
        progress: int,
        captured_required: list,
        missing_required: list,
        required_fields: list,
        required_field_ids: list,
        current_fields: dict,
        total_start: float,
    ) -> str:
        """Build response message when fields are still missing."""
        # Normalize saved_fields to list
        if isinstance(saved_fields, str):
            saved_fields = [saved_fields]

        # Get next field to ask about
        next_field_def = next(
            (f for f in required_fields if f["field_id"] == missing_required[0]), None
        )
        next_question = ""
        if next_field_def:
            # Use tone-aware question formatting
            base_question = next_field_def.get("clarifying_question")
            field_label = next_field_def.get("label", missing_required[0])
            next_question = self._format_question_with_tone(base_question, field_label)

        total_time = (time.perf_counter() - total_start) * 1000
        print(f"   ⏱️ Total time: {total_time:.2f}ms")
        print(f"   → Next question: '{next_question[:50]}...'")
        print("=" * 70)

        # Format saved fields for response
        saved_str = ", ".join(saved_fields) if len(saved_fields) > 1 else saved_fields[0]

        # Build snapshot of all captured fields so the LLM never "forgets"
        # what was already collected — eliminates re-asking for captured data
        captured_snapshot = []
        for fid in captured_required:
            val = current_fields.get(fid, {})
            if isinstance(val, dict):
                val = val.get("value", str(val))
            captured_snapshot.append(f"{fid}={val}")
        captured_str = ", ".join(captured_snapshot)

        return (
            f"Saved {len(saved_fields)} field(s): {saved_str}. Progress: {progress}% "
            f"({len(captured_required)}/{len(required_field_ids)} required fields).\n"
            f"Already captured: [{captured_str}]\n"
            f"Still need: {missing_required}.\n"
            f"IMPORTANT: Do NOT re-ask for any field listed in 'Already captured'. "
            f"Ask user: '{next_question}'"
        )

    async def complete_workflow(self, extracted_fields: dict) -> str:
        """
        Complete the conversational workflow.

        Saves the session as completed, then fires a background task for
        LLM-based lead scoring. The scoring runs async - user gets instant
        response while scoring happens in background.

        Args:
            extracted_fields: All extracted field data (format: {field_id: {value, confidence, ...}})

        Returns:
            Completion message with tone-appropriate closing
        """
        self.logger.info("🎉 [COMPLETE] Completing workflow - firing background scoring")

        # Save session ID before reset
        session_id_for_scoring = self._workflow_session_id

        # Mark session as completed (scoring happens async in background)
        async with async_session_maker() as session:
            workflow_repo = WorkflowRepository(session)
            if self._workflow_session_id:
                # Just mark as completed - scoring happens in background
                # Using a simpler completion that doesn't require score yet
                workflow_session = await workflow_repo.get_session_by_id(self._workflow_session_id)
                if workflow_session:
                    workflow_session.status = "completed"
                    workflow_session.completed_at = datetime.now(timezone.utc)
                    workflow_session.progress_percentage = 100
                    workflow_session.updated_at = datetime.now(timezone.utc)
                    await session.commit()

        # Fire background task for LLM scoring (non-blocking)
        # This is the SINGLE SOURCE OF TRUTH for scoring and summary
        if session_id_for_scoring:
            self._fire_background_scoring(
                session_id=session_id_for_scoring,
                extracted_fields=extracted_fields,
            )

        # Get tone-appropriate completion message from service
        completion_msg = self.tone_service.get_completion_message()

        # Reset state
        self._workflow_session_id = None

        # Return generic completion message (score comes from background task)
        return (
            f"WORKFLOW COMPLETE - Lead captured successfully. "
            f"Say something like: '{completion_msg}' and help with their request."
        )

    def _fire_background_scoring(
        self,
        session_id: UUID,
        extracted_fields: Dict[str, Any],
    ) -> None:
        """
        Fire background task for LLM-based lead scoring.

        This is fire-and-forget - runs async without blocking the response.
        Errors are logged but don't affect the user experience.

        The workflow's scoring_rules are passed so the LLM can evaluate
        against workflow-specific quality signals and risk penalties.

        This is the SINGLE SOURCE OF TRUTH for:
        - Lead score (0-100)
        - Priority level (high/medium/low)
        - Lead quality (hot/warm/cold)
        - Structured lead summary (contact, service_need, follow_up_questions)
        - Scoring breakdown (signals matched, penalties applied)
        """
        import asyncio

        from livekit.services.lead_scoring_service import score_lead_background

        # Build workflow context for LLM - include scoring rules and output config
        workflow_context = None
        if self.workflow_data:
            output_template = self.workflow_data.get("output_template", {})
            workflow_context = {
                "template_name": self.workflow_data.get("title", "Lead Capture"),
                "workflow_type": self.workflow_data.get("workflow_type", "conversational"),
                "scoring_rules": output_template.get("scoring_rules", {}),
                "output_config": {
                    "max_follow_up_questions": output_template.get("max_follow_up_questions", 4),
                },
            }

        # Fire and forget - create task but don't await it
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(
                score_lead_background(
                    session_id=session_id,
                    extracted_fields=extracted_fields,
                    workflow_context=workflow_context,
                )
            )
            self.logger.info(f"🚀 [SCORING] Background scoring task fired for session {session_id}")
        except Exception as e:
            # Don't let scoring failures affect the main flow
            self.logger.warning(f"Failed to fire background scoring task: {e}")

    # =========================================================================
    # No Redundant Questions - Helper Methods
    # =========================================================================
    # These methods help avoid asking the same question twice during lead capture.
    # The agent tracks which fields have been asked about and skips them.

    def _get_next_clarifying_question(
        self,
        missing_fields: List[str],
        required_fields: List[Dict[str, Any]],
        asked_fields: Optional[List[str]] = None,
    ) -> tuple:
        """
        Get the next clarifying question, skipping already-asked fields.

        Args:
            missing_fields: List of field IDs that still need values
            required_fields: Full field definitions from workflow config
            asked_fields: List of field IDs we've already asked about (optional)

        Returns:
            Tuple of (question_text, field_id) or (None, None) if nothing to ask
        """
        asked_fields = asked_fields or []

        # Find the first missing field we haven't asked about yet
        for field_id in missing_fields:
            if field_id not in asked_fields:
                # Get field definition
                field_def = next((f for f in required_fields if f["field_id"] == field_id), None)
                if field_def:
                    # Build question using tone service
                    base_question = field_def.get("clarifying_question")
                    field_label = field_def.get("label", field_id)
                    question = self._format_question_with_tone(base_question, field_label)
                    return (question, field_id)

        # All missing fields have been asked - nothing new to ask
        return (None, None)

    def _detect_update_intent(self, message: str) -> bool:
        """
        Detect if user wants to update/correct a previously captured field.

        This allows re-asking fields when user explicitly requests it:
        - "I want to change my email"
        - "Let me update my phone number"
        - "Actually, it's john@different.com"

        Args:
            message: User's message

        Returns:
            True if user wants to update a field
        """
        message_lower = message.lower()

        # Explicit update patterns
        update_patterns = [
            "change my",
            "update my",
            "correct my",
            "fix my",
            "let me change",
            "let me update",
            "let me correct",
            "let me fix",
            "actually,",
            "actually my",
            "that's wrong",
            "that is wrong",
        ]

        return any(pattern in message_lower for pattern in update_patterns)

    def _add_to_asked_fields(self, current_asked: List[str], new_field: str) -> List[str]:
        """
        Add a field to the asked_fields list without duplicates.

        Args:
            current_asked: Current list of asked field IDs
            new_field: Field ID to add

        Returns:
            Updated list with new field added (if not already present)
        """
        if new_field not in current_asked:
            return current_asked + [new_field]
        return current_asked

    def _clear_asked_fields_for_correction(self, current_asked: List[str]) -> List[str]:
        """
        Clear asked_fields when entering correction flow.

        When user rejects confirmation ("That's wrong"), we need to allow
        re-asking about fields they want to correct.

        Args:
            current_asked: Current list of asked field IDs

        Returns:
            Empty list to allow re-asking all fields
        """
        return []
