"""
LiveKit Agent Handlers

Modular handlers for agent functionality:
- Workflow handlers: Workflow lifecycle management (split by type)
  - LinearWorkflowHandler: Step-by-step Q&A assessments
  - ConversationalWorkflowHandler: Natural language lead capture
- DefaultCaptureHandler: Always-on basic lead capture (name, email, phone)
- ToolHandler: Function tools (search, fetch, calendar)
- SessionContext: Session and conversation tracking
- DocumentHandler: Document upload and processing
- LifecycleHandler: Agent lifecycle events (enter, exit, citations)
- EmailCaptureHandler: Lead generation email capture

Created: 2026-01-25
Updated: 2026-01-28 - Split WorkflowHandler into modular handlers
Updated: 2026-02-12 - Added DefaultCaptureHandler for always-on lead capture
"""

from .content_handler import ContentHandler
from .default_capture_handler import DefaultCaptureHandler
from .document_handler import DocumentHandler
from .email_capture_handler import EmailCaptureHandler
from .lifecycle_handler import LifecycleHandler
from .session_context import SessionContext
from .tool_handler import ToolHandler

# New modular workflow handlers
from .workflow import (
    BaseWorkflowHandler,
    ConversationalWorkflowHandler,
    LinearWorkflowHandler,
    WorkflowHandler,
    create_workflow_handler,
)

__all__ = [
    "ContentHandler",
    "SessionContext",
    "ToolHandler",
    # Workflow handlers
    "WorkflowHandler",
    "BaseWorkflowHandler",
    "LinearWorkflowHandler",
    "ConversationalWorkflowHandler",
    "create_workflow_handler",
    # Other handlers
    "DefaultCaptureHandler",
    "DocumentHandler",
    "LifecycleHandler",
    "EmailCaptureHandler",
]
