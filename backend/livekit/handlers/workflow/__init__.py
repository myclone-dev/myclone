"""
Workflow Handlers Module

Provides modular workflow handling split by workflow type:
- BaseWorkflowHandler: Shared functionality (session management, validation)
- LinearWorkflowHandler: Step-by-step Q&A assessments (simple/scored)
- ConversationalWorkflowHandler: Natural language lead capture

Factory function creates the appropriate handler based on workflow type.

Created: 2026-01-28
"""

from typing import Any, Callable, Dict, Optional, Union
from uuid import UUID

from .base import BaseWorkflowHandler
from .conversational_handler import ConversationalWorkflowHandler
from .linear_handler import LinearWorkflowHandler

# Type alias for any workflow handler
WorkflowHandler = Union[LinearWorkflowHandler, ConversationalWorkflowHandler]


def create_workflow_handler(
    workflow_data: Optional[Dict[str, Any]],
    persona_id: UUID,
    output_callback: Callable,
    text_only_mode: bool = False,
    session_token: Optional[str] = None,
) -> Optional[WorkflowHandler]:
    """
    Factory function to create the appropriate workflow handler.

    Args:
        workflow_data: Workflow configuration
        persona_id: Persona UUID
        output_callback: Function to send messages to user
        text_only_mode: Whether in text-only mode
        session_token: Session token for linking sessions

    Returns:
        Appropriate workflow handler, or None if no workflow configured
    """
    if not workflow_data:
        return None

    workflow_type = workflow_data.get("workflow_type", "simple")

    if workflow_type == "conversational":
        return ConversationalWorkflowHandler(
            workflow_data=workflow_data,
            persona_id=persona_id,
            output_callback=output_callback,
            text_only_mode=text_only_mode,
            session_token=session_token,
        )
    else:
        # simple, scored, or any other type uses linear handler
        return LinearWorkflowHandler(
            workflow_data=workflow_data,
            persona_id=persona_id,
            output_callback=output_callback,
            text_only_mode=text_only_mode,
            session_token=session_token,
        )


__all__ = [
    "BaseWorkflowHandler",
    "LinearWorkflowHandler",
    "ConversationalWorkflowHandler",
    "WorkflowHandler",
    "create_workflow_handler",
]
