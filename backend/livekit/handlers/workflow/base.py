"""
Base Workflow Handler

Shared functionality for all workflow types:
- Session management (create, resume, reset)
- Configuration validation
- Output message callback
- Common properties

Created: 2026-01-28
"""

import logging
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from shared.database.models.database import async_session_maker
from shared.database.repositories.workflow_repository import WorkflowRepository
from shared.monitoring.sentry_utils import capture_exception_with_context

# Schema validation import
try:
    from app.api.models.workflow_models import validate_workflow_config_by_type
except ImportError:
    validate_workflow_config_by_type = None

logger = logging.getLogger(__name__)


class BaseWorkflowHandler:
    """
    Base class for workflow handlers.

    Provides shared functionality:
    - Session management
    - Configuration validation
    - Output callback handling
    """

    def __init__(
        self,
        workflow_data: Optional[Dict[str, Any]],
        persona_id: UUID,
        output_callback: Callable,
        text_only_mode: bool = False,
        session_token: Optional[str] = None,
    ):
        """
        Initialize base workflow handler.

        Args:
            workflow_data: Workflow configuration
            persona_id: Persona UUID
            output_callback: Function to send messages to user
            text_only_mode: Whether in text-only mode
            session_token: Session token for linking workflow sessions to conversations
        """
        self.workflow_data = workflow_data
        self.persona_id = persona_id
        self._output_message = output_callback
        self.text_only_mode = text_only_mode
        self.session_token = session_token

        # Workflow session state
        self._workflow_session_id: Optional[UUID] = None

        self.logger = logging.getLogger(__name__)

        # Validate workflow_config schema at initialization
        self._validate_workflow_config()

        # Debug logging
        self.logger.info(
            f"🔍 [WORKFLOW_HANDLER] Initialized with workflow_data={bool(workflow_data)}"
        )
        if workflow_data:
            self.logger.info(
                f"🔍 [WORKFLOW_HANDLER] Workflow type: {workflow_data.get('workflow_type')}"
            )

    @property
    def is_active(self) -> bool:
        """Check if workflow is currently active."""
        return self._workflow_session_id is not None

    @property
    def workflow_type(self) -> Optional[str]:
        """Get current workflow type."""
        return self.workflow_data.get("workflow_type") if self.workflow_data else None

    def _validate_workflow_config(self) -> None:
        """
        Validate workflow_config schema at initialization.

        Catches invalid configs that bypassed API validation.
        Logs warning on failure but doesn't crash - allows graceful degradation.
        """
        if not self.workflow_data:
            return

        workflow_type = self.workflow_data.get("workflow_type")
        if not workflow_type:
            return

        # Build workflow_config from workflow_data for validation
        workflow_config = {}
        if "required_fields" in self.workflow_data:
            workflow_config = {
                "required_fields": self.workflow_data.get("required_fields", []),
                "optional_fields": self.workflow_data.get("optional_fields", []),
                "inference_rules": self.workflow_data.get("inference_rules", {}),
                "extraction_strategy": self.workflow_data.get("extraction_strategy", {}),
            }
        elif "workflow_config" in self.workflow_data:
            workflow_config = self.workflow_data.get("workflow_config", {})
        elif "steps" in self.workflow_data:
            workflow_config = {"steps": self.workflow_data.get("steps", [])}

        if not workflow_config:
            return

        if validate_workflow_config_by_type is not None:
            try:
                validate_workflow_config_by_type(workflow_type, workflow_config)
                self.logger.info(
                    f"✅ [WORKFLOW_HANDLER] workflow_config validated for {workflow_type}"
                )
            except ValueError as e:
                self.logger.warning(f"⚠️ [WORKFLOW_HANDLER] Config validation failed: {e}")
                capture_exception_with_context(
                    e,
                    extra={
                        "workflow_type": workflow_type,
                        "workflow_id": str(self.workflow_data.get("workflow_id", "unknown")),
                    },
                    tags={
                        "component": "workflow_handler",
                        "operation": "validate_config",
                        "severity": "medium",
                        "user_facing": "false",
                    },
                )

    async def resume_existing_session(self, session_token: Optional[str] = None) -> bool:
        """
        Check for and resume existing workflow session.

        Args:
            session_token: Session identifier to search for existing sessions

        Returns:
            True if existing session was found and resumed, False otherwise
        """
        if not self.workflow_data or not session_token:
            return False

        try:
            workflow_id = UUID(self.workflow_data["workflow_id"])

            async with async_session_maker() as session:
                from sqlalchemy import and_, select

                from shared.database.models.workflow import WorkflowSession

                stmt = (
                    select(WorkflowSession)
                    .where(
                        and_(
                            WorkflowSession.workflow_id == workflow_id,
                            WorkflowSession.persona_id == self.persona_id,
                            WorkflowSession.completed_at.is_(None),
                        )
                    )
                    .order_by(WorkflowSession.created_at.desc())
                    .limit(1)
                )

                result = await session.execute(stmt)
                existing_session = result.scalar_one_or_none()

                if existing_session:
                    self._workflow_session_id = existing_session.id
                    self.logger.info(f"🔄 [WORKFLOW] Resumed session: {existing_session.id}")
                    return True

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "workflow_id": self.workflow_data.get("workflow_id"),
                    "session_token": session_token,
                },
                tags={
                    "component": "workflow_handler",
                    "operation": "resume_existing_session",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to resume session: {e}", exc_info=True)

        return False

    async def _create_session(self) -> UUID:
        """
        Create a new workflow session in database.

        Returns:
            UUID of created session
        """
        workflow_id = UUID(self.workflow_data["workflow_id"])

        async with async_session_maker() as session:
            workflow_repo = WorkflowRepository(session)
            workflow_session = await workflow_repo.create_session(
                workflow_id=workflow_id,
                persona_id=self.persona_id,
                conversation_id=None,
                user_id=None,
                session_token=self.session_token,
            )
            return workflow_session.id

    def reset(self):
        """Reset workflow state. Override in subclasses for additional cleanup."""
        self._workflow_session_id = None
