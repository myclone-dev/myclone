"""
Mock Repositories for Testing

Provides mock implementations of database repositories
to enable unit testing without database connections.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4


def create_mock_session(
    session_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    persona_id: Optional[UUID] = None,
    status: str = "in_progress",
    extracted_fields: Optional[Dict[str, Any]] = None,
    progress_percentage: int = 0,
) -> MagicMock:
    """
    Create a mock WorkflowSession object.

    Args:
        session_id: Session UUID (auto-generated if not provided)
        workflow_id: Workflow UUID
        persona_id: Persona UUID
        status: Session status (in_progress, awaiting_confirmation, completed)
        extracted_fields: Dictionary of extracted field values
        progress_percentage: Progress percentage (0-100)

    Returns:
        MagicMock configured as a WorkflowSession
    """
    mock_session = MagicMock()
    mock_session.id = session_id or uuid4()
    mock_session.workflow_id = workflow_id or uuid4()
    mock_session.persona_id = persona_id or uuid4()
    mock_session.status = status
    mock_session.extracted_fields = extracted_fields or {}
    mock_session.progress_percentage = progress_percentage
    mock_session.created_at = datetime.now(timezone.utc)
    mock_session.updated_at = datetime.now(timezone.utc)
    mock_session.completed_at = None if status != "completed" else datetime.now(timezone.utc)
    mock_session.session_metadata = {}
    mock_session.result_data = None
    return mock_session


class MockWorkflowRepository:
    """
    Mock implementation of WorkflowRepository for testing.

    Tracks all method calls and allows configuring return values.
    """

    def __init__(self):
        self.sessions: Dict[UUID, MagicMock] = {}
        self.call_history: List[Dict[str, Any]] = []

        # Create async mock methods
        self.create_session = AsyncMock(side_effect=self._create_session)
        self.get_session_by_id = AsyncMock(side_effect=self._get_session_by_id)
        self.update_extracted_fields = AsyncMock(side_effect=self._update_extracted_fields)
        self.complete_session = AsyncMock(side_effect=self._complete_session)
        self.update_session_status = AsyncMock(side_effect=self._update_session_status)

    async def _create_session(
        self,
        workflow_id: UUID,
        persona_id: UUID,
        session_token: Optional[str] = None,
        **kwargs,
    ) -> MagicMock:
        """Create a new mock session."""
        session = create_mock_session(
            workflow_id=workflow_id,
            persona_id=persona_id,
        )
        self.sessions[session.id] = session
        self._log_call("create_session", workflow_id=workflow_id, persona_id=persona_id)
        return session

    async def _get_session_by_id(self, session_id: UUID) -> Optional[MagicMock]:
        """Get session by ID."""
        self._log_call("get_session_by_id", session_id=session_id)
        return self.sessions.get(session_id)

    async def _update_extracted_fields(
        self,
        session_id: UUID,
        extracted_fields: Dict[str, Any],
        progress_percentage: Optional[int] = None,
    ) -> Optional[MagicMock]:
        """Update extracted fields for a session."""
        self._log_call(
            "update_extracted_fields",
            session_id=session_id,
            extracted_fields=extracted_fields,
            progress_percentage=progress_percentage,
        )

        session = self.sessions.get(session_id)
        if not session:
            return None

        # Merge fields
        current_fields = dict(session.extracted_fields or {})
        current_fields.update(extracted_fields)
        session.extracted_fields = current_fields

        # Update progress
        if progress_percentage is not None:
            session.progress_percentage = progress_percentage

        session.updated_at = datetime.now(timezone.utc)
        return session

    async def _complete_session(
        self,
        session_id: UUID,
        result_data: Optional[Dict[str, Any]] = None,
        progress_percentage: int = 100,
    ) -> Optional[MagicMock]:
        """Complete a workflow session."""
        self._log_call(
            "complete_session",
            session_id=session_id,
            result_data=result_data,
        )

        session = self.sessions.get(session_id)
        if not session:
            return None

        session.status = "completed"
        session.progress_percentage = progress_percentage
        session.completed_at = datetime.now(timezone.utc)
        session.result_data = result_data
        return session

    async def _update_session_status(
        self,
        session_id: UUID,
        status: str,
    ) -> Optional[MagicMock]:
        """Update session status."""
        self._log_call(
            "update_session_status",
            session_id=session_id,
            status=status,
        )

        session = self.sessions.get(session_id)
        if not session:
            return None

        session.status = status
        session.updated_at = datetime.now(timezone.utc)
        return session

    def _log_call(self, method: str, **kwargs):
        """Log a method call for test assertions."""
        self.call_history.append(
            {
                "method": method,
                "timestamp": datetime.now(timezone.utc),
                **kwargs,
            }
        )

    def add_session(self, session: MagicMock) -> None:
        """Add a pre-configured session to the repository."""
        self.sessions[session.id] = session

    def get_calls(self, method: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get call history, optionally filtered by method name."""
        if method:
            return [c for c in self.call_history if c["method"] == method]
        return self.call_history

    def reset(self) -> None:
        """Reset all state for a fresh test."""
        self.sessions.clear()
        self.call_history.clear()
        self.create_session.reset_mock()
        self.get_session_by_id.reset_mock()
        self.update_extracted_fields.reset_mock()
        self.complete_session.reset_mock()
        self.update_session_status.reset_mock()
