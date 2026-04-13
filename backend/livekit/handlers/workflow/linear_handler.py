"""
Linear Workflow Handler

Handles step-by-step Q&A workflows (simple and scored):
- Sequential question flow
- Answer validation
- Score calculation (for scored workflows)
- Result categories

Created: 2026-01-28
"""

import logging
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from livekit.agents.llm.tool_context import ToolError
from shared.database.models.database import async_session_maker
from shared.database.repositories.workflow_repository import WorkflowRepository
from shared.monitoring.sentry_utils import capture_exception_with_context

from .base import BaseWorkflowHandler

logger = logging.getLogger(__name__)


class LinearWorkflowHandler(BaseWorkflowHandler):
    """
    Handler for linear (step-by-step) workflows.

    Supports:
    - Simple workflows (Q&A without scoring)
    - Scored workflows (Q&A with scoring and result categories)
    """

    def __init__(
        self,
        workflow_data: Optional[Dict[str, Any]],
        persona_id: UUID,
        output_callback: Callable,
        text_only_mode: bool = False,
        session_token: Optional[str] = None,
    ):
        """Initialize linear workflow handler."""
        super().__init__(
            workflow_data=workflow_data,
            persona_id=persona_id,
            output_callback=output_callback,
            text_only_mode=text_only_mode,
            session_token=session_token,
        )

        # Linear-specific state
        self._workflow_current_step: Optional[int] = None
        self._workflow_answers: Dict[str, Any] = {}

    async def start_workflow(self, send_opening_message: bool = True) -> None:
        """
        Start the linear workflow.

        Args:
            send_opening_message: Whether to send opening message

        Raises:
            ToolError: If workflow cannot be started
        """
        import time

        start_time = time.perf_counter()
        print("=" * 70)
        print("🚀 [LINEAR_HANDLER] start_workflow() START")

        if not self.workflow_data:
            raise ToolError("No assessment workflow available for this persona")

        try:
            workflow_title = self.workflow_data.get("title", "Assessment")
            steps = self.workflow_data.get("steps", [])

            print(f"   Workflow title: {workflow_title}")
            print(f"   Steps: {len(steps)}")

            # Create session
            self._workflow_session_id = await self._create_session()
            print(f"   Session created: {self._workflow_session_id}")

            # Send opening message if configured
            if send_opening_message and self.workflow_data.get("opening_message"):
                await self._output_message(
                    self.workflow_data["opening_message"], allow_interruptions=False
                )

            # Initialize state
            self._workflow_current_step = 0
            self._workflow_answers = {}

            # Ask first question
            await self._ask_current_question()

            total_time = (time.perf_counter() - start_time) * 1000
            print(f"⏱️ [LINEAR_HANDLER] start_workflow() TOTAL: {total_time:.2f}ms")
            print("=" * 70)

            self.logger.info(f"🚀 Started linear workflow: {workflow_title} ({len(steps)} steps)")

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "workflow_id": self.workflow_data.get("workflow_id"),
                },
                tags={
                    "component": "linear_workflow_handler",
                    "operation": "start_workflow",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Workflow start failed: {e}", exc_info=True)
            raise ToolError(f"Failed to start assessment: {str(e)}")

    async def submit_answer(self, answer: str) -> str:
        """
        Submit answer for current step.

        Args:
            answer: User's answer

        Returns:
            Status message

        Raises:
            ToolError: If workflow is not active or answer is invalid
        """
        if not self._workflow_session_id:
            raise ToolError("No active workflow. Please call start_assessment first.")

        if self._workflow_current_step is None:
            raise ToolError("Workflow data or current step is missing")

        try:
            steps = self.workflow_data.get("steps", [])
            step = steps[self._workflow_current_step]

            self.logger.info(
                f"📝 Processing answer for step {self._workflow_current_step + 1}/{len(steps)}: {step['step_id']}"
            )

            # Validate and process answer
            validated_answer = await self._validate_answer(step, answer)

            # Save answer
            await self._save_answer(step, validated_answer)

            # Move to next step
            self._workflow_current_step += 1

            if self._workflow_current_step >= len(steps):
                # Workflow complete
                return await self._complete_workflow()
            else:
                # Ask next question
                await self._ask_current_question()
                return f"Answer recorded. Moving to question {self._workflow_current_step + 1} of {len(steps)}."

        except ToolError:
            raise
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "workflow_session_id": str(self._workflow_session_id),
                    "current_step": self._workflow_current_step,
                    "answer_preview": answer[:200] if answer else None,
                },
                tags={
                    "component": "linear_workflow_handler",
                    "operation": "submit_answer",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Error processing answer: {e}", exc_info=True)
            raise ToolError(f"Failed to process answer: {str(e)}")

    async def _validate_answer(self, step: Dict[str, Any], answer: str) -> str:
        """Validate answer based on step type."""
        if step["step_type"] == "multiple_choice":
            valid_labels = [opt.get("label", "").upper() for opt in step.get("options", [])]
            answer_normalized = answer.strip().upper()

            # Extract first valid letter
            parsed_answer = None
            for char in answer_normalized:
                if char in valid_labels:
                    parsed_answer = char
                    break

            if not parsed_answer:
                error_msg = (
                    f"Invalid answer '{answer}'. Please choose from: {', '.join(valid_labels)}"
                )
                await self._output_message(error_msg, allow_interruptions=True)
                raise ToolError(error_msg)

            return parsed_answer
        else:
            # Text/number questions - accept as is
            return answer

    async def _save_answer(self, step: Dict[str, Any], answer: str):
        """Save answer to database and in-memory for scoring."""
        from datetime import datetime, timezone

        # Build answer data
        answer_data = {
            "question": step.get("question_text", ""),
            "answer": answer,
            "answered_at": datetime.now(timezone.utc).isoformat(),
        }

        # Calculate score if applicable
        score = None
        if step["step_type"] == "multiple_choice":
            for opt in step.get("options", []):
                if opt.get("label", "").upper() == answer.upper():
                    if "score" in opt:
                        score = opt["score"]
                        answer_data["score"] = score
                    break

        # Store in memory for scoring
        self._workflow_answers[step["step_id"]] = {"answer": answer, "score": score}

        # Update database
        async with async_session_maker() as session:
            workflow_repo = WorkflowRepository(session)
            await workflow_repo.save_answer(self._workflow_session_id, step["step_id"], answer_data)

    async def _ask_current_question(self):
        """Ask the current workflow question."""
        steps = self.workflow_data.get("steps", [])
        if self._workflow_current_step >= len(steps):
            return

        step = steps[self._workflow_current_step]
        question_text = step.get("question_text", "")

        # Only show question text - options are in system prompt for LLM context
        await self._output_message(question_text, allow_interruptions=True)

    async def _complete_workflow(self) -> str:
        """Complete workflow and calculate results."""
        self.logger.info("✅ Workflow completed - calculating results")

        workflow_type = self.workflow_data.get("workflow_type", "simple")

        # Calculate score for scored workflows
        if workflow_type == "scored":
            total_score = sum(
                a["score"] for a in self._workflow_answers.values() if a.get("score") is not None
            )
            self.logger.info(f"📊 Total score: {total_score}")

            # Find matching category
            categories = self.workflow_data.get("result_config", {}).get("categories", [])
            matching_category = None

            for category in categories:
                min_score = category.get("min_score", 0)
                max_score = category.get("max_score", 0)
                if min_score <= total_score <= max_score:
                    matching_category = category
                    break

            if not matching_category and categories:
                matching_category = categories[0]

            category_message = matching_category.get("message", "") if matching_category else ""
            result = f"🎉 Assessment complete! Your score is {total_score}. {category_message}"
        else:
            result = "🎉 Assessment complete! Thank you for your responses."

        # Add closing message
        if self.workflow_data.get("closing_message"):
            result += f"\n\n{self.workflow_data['closing_message']}"

        # Mark session complete
        async with async_session_maker() as session:
            workflow_repo = WorkflowRepository(session)
            await workflow_repo.complete_session(self._workflow_session_id)

        # Send results
        await self._output_message(result, allow_interruptions=False)

        # Reset state
        self.reset()

        return result

    def reset(self):
        """Reset workflow state."""
        super().reset()
        self._workflow_current_step = None
        self._workflow_answers = {}
