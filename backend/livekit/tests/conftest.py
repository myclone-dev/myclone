"""
Pytest Configuration and Fixtures

Provides shared fixtures for all LiveKit agent tests.
"""

import os
import sys
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
import pytest_asyncio

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from livekit.tests.fixtures.cpa_workflow import (
    CPA_WORKFLOW_DATA,
    CPA_WORKFLOW_EXTENDED,
    CPA_WORKFLOW_MINIMAL,
    FAKE_PERSONA_INFO,
    FAKE_PERSONA_PROMPT,
)
from livekit.tests.fixtures.mock_repositories import (
    MockWorkflowRepository,
    create_mock_session,
)

# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test (requires LLM)"
    )
    config.addinivalue_line("markers", "slow: mark test as slow (may take > 10s)")


# ============================================================================
# Workflow Data Fixtures
# ============================================================================


@pytest.fixture
def cpa_workflow_data() -> Dict[str, Any]:
    """Standard CPA workflow configuration."""
    return CPA_WORKFLOW_DATA.copy()


@pytest.fixture
def cpa_workflow_minimal() -> Dict[str, Any]:
    """Minimal CPA workflow (only name + email)."""
    return CPA_WORKFLOW_MINIMAL.copy()


@pytest.fixture
def cpa_workflow_extended() -> Dict[str, Any]:
    """Extended CPA workflow with business fields."""
    return CPA_WORKFLOW_EXTENDED.copy()


# ============================================================================
# Persona Fixtures
# ============================================================================


@pytest.fixture
def fake_persona_info() -> Dict[str, Any]:
    """Fake persona info for testing."""
    return FAKE_PERSONA_INFO.copy()


@pytest.fixture
def fake_persona_prompt() -> Dict[str, Any]:
    """Fake persona prompt for testing."""
    return FAKE_PERSONA_PROMPT.copy()


@pytest.fixture
def test_persona_id() -> UUID:
    """Standard test persona ID."""
    return UUID(FAKE_PERSONA_INFO["id"])


# ============================================================================
# Mock Repository Fixtures
# ============================================================================


@pytest.fixture
def mock_workflow_repo() -> MockWorkflowRepository:
    """Create a fresh MockWorkflowRepository for each test."""
    return MockWorkflowRepository()


@pytest.fixture
def mock_session_empty(test_persona_id):
    """Mock session with no extracted fields."""
    return create_mock_session(
        persona_id=test_persona_id,
        workflow_id=UUID(CPA_WORKFLOW_DATA["workflow_id"]),
        extracted_fields={},
        progress_percentage=0,
    )


@pytest.fixture
def mock_session_partial(test_persona_id):
    """Mock session with some fields extracted."""
    return create_mock_session(
        persona_id=test_persona_id,
        workflow_id=UUID(CPA_WORKFLOW_DATA["workflow_id"]),
        extracted_fields={
            "contact_name": {
                "value": "John Doe",
                "confidence": 0.95,
                "extraction_method": "direct_tool_call",
            },
            "contact_email": {
                "value": "john@example.com",
                "confidence": 0.98,
                "extraction_method": "direct_tool_call",
            },
        },
        progress_percentage=50,
    )


@pytest.fixture
def mock_session_complete(test_persona_id):
    """Mock session with all required fields extracted."""
    return create_mock_session(
        persona_id=test_persona_id,
        workflow_id=UUID(CPA_WORKFLOW_DATA["workflow_id"]),
        extracted_fields={
            "contact_name": {"value": "John Doe", "confidence": 0.95},
            "contact_email": {"value": "john@example.com", "confidence": 0.98},
            "contact_phone": {"value": "555-123-4567", "confidence": 0.92},
            "service_need": {"value": "quarterly tax filing", "confidence": 0.88},
        },
        progress_percentage=100,
        status="awaiting_confirmation",
    )


# ============================================================================
# Output Callback Fixtures
# ============================================================================


@pytest.fixture
def mock_output_callback():
    """Mock output callback that records messages."""
    callback = AsyncMock()
    callback.messages = []

    async def record_message(msg, allow_interruptions=True):
        callback.messages.append(msg)

    callback.side_effect = record_message
    return callback


# ============================================================================
# Database Session Mocking
# ============================================================================


@pytest.fixture
def mock_async_session_maker():
    """Mock the async_session_maker context manager."""
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "livekit.handlers.workflow.conversational_handler.async_session_maker",
        return_value=mock_session,
    ):
        yield mock_session


# ============================================================================
# Handler Factory Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def workflow_handler(
    cpa_workflow_data,
    test_persona_id,
    mock_output_callback,
):
    """Create a WorkflowHandler for testing conversational workflows."""
    from livekit.handlers.workflow_handler import WorkflowHandler

    handler = WorkflowHandler(
        workflow_data=cpa_workflow_data,
        persona_id=test_persona_id,
        output_callback=mock_output_callback,
        text_only_mode=True,
    )
    return handler


@pytest_asyncio.fixture
async def linear_workflow_handler(
    test_persona_id,
    mock_output_callback,
):
    """Create a WorkflowHandler for testing linear workflows."""
    from livekit.handlers.workflow_handler import WorkflowHandler

    # Simple scored workflow for testing
    workflow_data = {
        "workflow_id": "test-linear-workflow",
        "title": "Test Assessment",
        "workflow_type": "scored",
        "steps": [
            {
                "step_id": "q1",
                "step_type": "multiple_choice",
                "question_text": "How would you rate your experience?",
                "options": [
                    {"label": "A", "text": "Poor", "score": 1},
                    {"label": "B", "text": "Good", "score": 2},
                    {"label": "C", "text": "Excellent", "score": 3},
                ],
            }
        ],
        "result_config": {
            "categories": [
                {"min_score": 0, "max_score": 1, "message": "Needs improvement"},
                {"min_score": 2, "max_score": 3, "message": "Great job!"},
            ]
        },
    }

    handler = WorkflowHandler(
        workflow_data=workflow_data,
        persona_id=test_persona_id,
        output_callback=mock_output_callback,
        text_only_mode=True,
    )
    return handler


@pytest.fixture
def conversational_coordinator():
    """Create a ConversationalWorkflowCoordinator for testing."""
    from livekit.services.conversational_workflow_coordinator import (
        ConversationalWorkflowCoordinator,
    )

    return ConversationalWorkflowCoordinator()
