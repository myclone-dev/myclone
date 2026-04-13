"""
Integration Tests for Workflow Completion

Tests the complete_workflow() flow:
1. Handler marks session as completed
2. Background task fires for LLM-based scoring
3. LeadScoringService evaluates lead and stores result

These tests verify the full integration between:
- ConversationalWorkflowHandler.complete_workflow()
- LeadScoringService (background task)
- WorkflowRepository.update_session_lead_evaluation()
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from livekit.handlers.workflow.conversational_handler import ConversationalWorkflowHandler
from livekit.tests.fixtures.cpa_workflow import CPA_WORKFLOW_DATA

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def workflow_data_with_scoring():
    """CPA workflow with full scoring rules."""
    return CPA_WORKFLOW_DATA.copy()


@pytest.fixture
def workflow_data_high_value():
    """Workflow configured for high-value lead detection."""
    data = CPA_WORKFLOW_DATA.copy()
    data["output_template"] = {
        "format": "lead_summary",
        "summary_template": "structured",
        "max_follow_up_questions": 4,
        "scoring_rules": {
            "base_score": 50,
            "field_completeness_weight": 20,
            "quality_signals": [
                {
                    "signal_id": "urgent_timeline",
                    "points": 15,
                    "condition": {
                        "field": "timeline",
                        "operator": "equals",
                        "value": "Immediate",
                    },
                },
                {
                    "signal_id": "has_referral",
                    "points": 10,
                    "condition": {"field": "referral_source", "operator": "exists"},
                },
                {
                    "signal_id": "high_revenue",
                    "points": 20,
                    "condition": {
                        "field": "annual_revenue",
                        "operator": "in_list",
                        "values": ["$500K-$1M", "$1M-$5M", "Over $5M"],
                    },
                },
            ],
            "risk_penalties": [
                {
                    "penalty_id": "incomplete_contact",
                    "points": -15,
                    "condition": {
                        "any_of": [
                            {"field": "contact_email", "operator": "not_exists"},
                            {"field": "contact_phone", "operator": "not_exists"},
                        ]
                    },
                },
            ],
        },
    }
    return data


@pytest.fixture
def extracted_fields_basic():
    """Basic extracted fields (required only)."""
    return {
        "contact_name": {"value": "John Smith", "confidence": 1.0},
        "contact_email": {"value": "john@example.com", "confidence": 1.0},
        "contact_phone": {"value": "555-123-4567", "confidence": 1.0},
        "service_need": {"value": "Tax preparation for my small business", "confidence": 1.0},
    }


@pytest.fixture
def extracted_fields_high_value():
    """High-value lead with quality signals."""
    return {
        "contact_name": {"value": "Sarah Johnson", "confidence": 1.0},
        "contact_email": {"value": "sarah@bigcorp.com", "confidence": 1.0},
        "contact_phone": {"value": "555-987-6543", "confidence": 1.0},
        "service_need": {"value": "S-Corp election and tax planning", "confidence": 1.0},
        "timeline": {"value": "Immediate", "confidence": 1.0},
        "referral_source": {"value": "Google search", "confidence": 1.0},
        "annual_revenue": {"value": "$1M-$5M", "confidence": 1.0},
        "state": {"value": "California", "confidence": 1.0},
    }


@pytest.fixture
def mock_output():
    """Mock output callback."""
    return AsyncMock()


# ============================================================================
# Test: Complete Workflow Integration
# ============================================================================


class TestCompleteWorkflowIntegration:
    """Tests for complete_workflow() with background scoring."""

    @pytest.fixture
    def handler(self, workflow_data_high_value, mock_output):
        """Create handler with high-value workflow config."""
        return ConversationalWorkflowHandler(
            workflow_data=workflow_data_high_value,
            persona_id=uuid4(),
            output_callback=mock_output,
            text_only_mode=True,
        )

    @pytest.mark.asyncio
    async def test_complete_workflow_marks_session_completed(self, handler, extracted_fields_basic):
        """complete_workflow should mark session as completed in DB."""
        session_id = uuid4()
        handler._workflow_session_id = session_id

        # Mock the repository and session
        mock_workflow_session = MagicMock()
        mock_workflow_session.status = "in_progress"

        with patch(
            "livekit.handlers.workflow.conversational_handler.async_session_maker"
        ) as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            mock_repo = MagicMock()
            mock_repo.get_session_by_id = AsyncMock(return_value=mock_workflow_session)

            with patch(
                "livekit.handlers.workflow.conversational_handler.WorkflowRepository",
                return_value=mock_repo,
            ):
                # Mock the background task to not actually run
                with patch(
                    "livekit.handlers.workflow.conversational_handler.ConversationalWorkflowHandler._fire_background_scoring"
                ):
                    await handler.complete_workflow(extracted_fields_basic)

            # Verify session was marked as completed
            assert mock_workflow_session.status == "completed"
            assert mock_workflow_session.progress_percentage == 100
            assert mock_workflow_session.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_workflow_fires_background_scoring(
        self, handler, extracted_fields_high_value
    ):
        """complete_workflow should fire background scoring task."""
        session_id = uuid4()
        handler._workflow_session_id = session_id

        mock_workflow_session = MagicMock()

        with patch(
            "livekit.handlers.workflow.conversational_handler.async_session_maker"
        ) as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            mock_repo = MagicMock()
            mock_repo.get_session_by_id = AsyncMock(return_value=mock_workflow_session)

            with patch(
                "livekit.handlers.workflow.conversational_handler.WorkflowRepository",
                return_value=mock_repo,
            ):
                with patch.object(handler, "_fire_background_scoring") as mock_fire_scoring:
                    await handler.complete_workflow(extracted_fields_high_value)

                    # Verify background scoring was fired
                    mock_fire_scoring.assert_called_once()
                    call_kwargs = mock_fire_scoring.call_args.kwargs
                    assert call_kwargs["session_id"] == session_id
                    assert call_kwargs["extracted_fields"] == extracted_fields_high_value

    @pytest.mark.asyncio
    async def test_complete_workflow_returns_completion_message(
        self, handler, extracted_fields_basic
    ):
        """complete_workflow should return completion message."""
        handler._workflow_session_id = uuid4()

        mock_workflow_session = MagicMock()

        with patch(
            "livekit.handlers.workflow.conversational_handler.async_session_maker"
        ) as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            mock_repo = MagicMock()
            mock_repo.get_session_by_id = AsyncMock(return_value=mock_workflow_session)

            with patch(
                "livekit.handlers.workflow.conversational_handler.WorkflowRepository",
                return_value=mock_repo,
            ):
                with patch.object(handler, "_fire_background_scoring"):
                    result = await handler.complete_workflow(extracted_fields_basic)

        assert "WORKFLOW COMPLETE" in result
        assert "Lead captured" in result

    @pytest.mark.asyncio
    async def test_complete_workflow_handles_no_session_id(self, handler, extracted_fields_basic):
        """complete_workflow should handle missing session_id gracefully."""
        handler._workflow_session_id = None  # No session

        result = await handler.complete_workflow(extracted_fields_basic)

        # Should still return completion message
        assert "WORKFLOW COMPLETE" in result

    @pytest.mark.asyncio
    async def test_complete_workflow_resets_state(self, handler, extracted_fields_basic):
        """complete_workflow should reset handler state."""
        handler._workflow_session_id = uuid4()

        mock_workflow_session = MagicMock()

        with patch(
            "livekit.handlers.workflow.conversational_handler.async_session_maker"
        ) as mock_session_maker:
            mock_session = MagicMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.commit = AsyncMock()
            mock_session_maker.return_value = mock_session

            mock_repo = MagicMock()
            mock_repo.get_session_by_id = AsyncMock(return_value=mock_workflow_session)

            with patch(
                "livekit.handlers.workflow.conversational_handler.WorkflowRepository",
                return_value=mock_repo,
            ):
                with patch.object(handler, "_fire_background_scoring"):
                    await handler.complete_workflow(extracted_fields_basic)

        # Session ID should be reset
        assert handler._workflow_session_id is None


# ============================================================================
# Test: Background Scoring Task
# ============================================================================


class TestBackgroundScoringTask:
    """Tests for the background scoring task integration."""

    @pytest.fixture
    def handler(self, workflow_data_high_value, mock_output):
        """Create handler with workflow config."""
        return ConversationalWorkflowHandler(
            workflow_data=workflow_data_high_value,
            persona_id=uuid4(),
            output_callback=mock_output,
            text_only_mode=True,
        )

    def test_fire_background_scoring_creates_task(self, handler, extracted_fields_basic):
        """_fire_background_scoring should create async task."""

        session_id = uuid4()

        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop

            with patch("livekit.services.lead_scoring_service.score_lead_background"):
                handler._fire_background_scoring(
                    session_id=session_id,
                    extracted_fields=extracted_fields_basic,
                )

                # Verify task was created
                mock_loop.create_task.assert_called_once()

    def test_fire_background_scoring_includes_workflow_context(
        self, handler, extracted_fields_basic
    ):
        """_fire_background_scoring should pass workflow context."""
        session_id = uuid4()
        captured_args = {}

        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()

            def capture_task(coro):
                # Store the coroutine arguments for inspection
                captured_args["coro"] = coro

            mock_loop.create_task = capture_task
            mock_get_loop.return_value = mock_loop

            with patch("livekit.services.lead_scoring_service.score_lead_background") as mock_score:
                handler._fire_background_scoring(
                    session_id=session_id,
                    extracted_fields=extracted_fields_basic,
                )

                # Verify score_lead_background was called with correct args
                mock_score.assert_called_once()
                call_kwargs = mock_score.call_args.kwargs
                assert call_kwargs["session_id"] == session_id
                assert call_kwargs["extracted_fields"] == extracted_fields_basic
                assert "workflow_context" in call_kwargs
                assert call_kwargs["workflow_context"]["template_name"] is not None

    def test_fire_background_scoring_handles_errors(self, handler, extracted_fields_basic):
        """_fire_background_scoring should not raise on errors."""
        session_id = uuid4()

        with patch("asyncio.get_event_loop", side_effect=RuntimeError("No event loop")):
            # Should not raise - just log warning
            handler._fire_background_scoring(
                session_id=session_id,
                extracted_fields=extracted_fields_basic,
            )


# ============================================================================
# Test: Workflow Context Building
# ============================================================================


class TestWorkflowContextBuilding:
    """Tests for workflow context passed to scoring service."""

    @pytest.fixture
    def handler(self, workflow_data_high_value, mock_output):
        """Create handler with workflow config."""
        return ConversationalWorkflowHandler(
            workflow_data=workflow_data_high_value,
            persona_id=uuid4(),
            output_callback=mock_output,
            text_only_mode=True,
        )

    def test_workflow_context_includes_template_name(self, handler, extracted_fields_basic):
        """Workflow context should include template name."""
        session_id = uuid4()

        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop

            with patch("livekit.services.lead_scoring_service.score_lead_background") as mock_score:
                handler._fire_background_scoring(
                    session_id=session_id,
                    extracted_fields=extracted_fields_basic,
                )

                call_kwargs = mock_score.call_args.kwargs
                context = call_kwargs["workflow_context"]
                assert "template_name" in context

    def test_workflow_context_includes_scoring_rules(self, handler, extracted_fields_basic):
        """Workflow context should include scoring rules."""
        session_id = uuid4()

        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop

            with patch("livekit.services.lead_scoring_service.score_lead_background") as mock_score:
                handler._fire_background_scoring(
                    session_id=session_id,
                    extracted_fields=extracted_fields_basic,
                )

                call_kwargs = mock_score.call_args.kwargs
                context = call_kwargs["workflow_context"]
                assert "scoring_rules" in context
                assert "quality_signals" in context["scoring_rules"]

    def test_workflow_context_includes_output_config(self, handler, extracted_fields_basic):
        """Workflow context should include output config."""
        session_id = uuid4()

        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_get_loop.return_value = mock_loop

            with patch("livekit.services.lead_scoring_service.score_lead_background") as mock_score:
                handler._fire_background_scoring(
                    session_id=session_id,
                    extracted_fields=extracted_fields_basic,
                )

                call_kwargs = mock_score.call_args.kwargs
                context = call_kwargs["workflow_context"]
                assert "output_config" in context
                assert "max_follow_up_questions" in context["output_config"]
