"""
Integration Tests for Lead Scoring Service

Tests the LLM-based lead scoring that runs in the background
after workflow completion.

Test Categories:
1. OBVIOUS CASES - Clear-cut scenarios that should definitely work
2. NUANCED CASES - Requires LLM understanding of intent/context
3. EDGE CASES - Missing data, malformed input, error handling
4. WORKFLOW CONTEXT - How context affects evaluation
5. BACKGROUND TASK - Fire-and-forget behavior

Run with: poetry run pytest livekit/tests/integration/test_lead_scoring.py -v
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from livekit.services.lead_scoring_service import (
    LeadContact,
    LeadEvaluationResult,
    LeadScoring,
    LeadScoringService,
    LeadSummary,
    score_lead_background,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def scoring_service():
    """Create scoring service instance."""
    return LeadScoringService()


@pytest.fixture
def mock_openai_response():
    """Factory for creating mock OpenAI responses."""

    def _create_response(content: dict):
        import json

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(content)
        return mock_response

    return _create_response


@pytest.fixture
def valid_llm_response():
    """Valid LLM response matching LeadEvaluationResult schema."""
    return {
        "lead_score": 85,
        "priority_level": "high",
        "lead_quality": "hot",
        "urgency_level": "high",
        "lead_summary": {
            "contact": {
                "name": "John Smith",
                "email": "john@example.com",
                "phone": "555-123-4567",
            },
            "service_need": "S-Corp election for startup",
            "additional_info": {"timeline": "Immediate", "state": "California"},
            "follow_up_questions": [
                "What is your current business structure?",
                "Have you consulted with a tax professional before?",
            ],
        },
        "scoring": {
            "score": 85,
            "priority": "high",
            "signals_matched": [
                {"signal_id": "urgent_timeline", "points": 15, "reason": "Immediate timeline"},
                {"signal_id": "high_revenue", "points": 20, "reason": "$500K revenue"},
            ],
            "penalties_applied": [],
            "reasoning": "Hot lead with urgent need and high revenue potential.",
        },
        "confidence": 0.92,
    }


# ============================================================================
# 1. OBVIOUS CASES - Clear-cut scenarios
# ============================================================================


class TestObviousCases:
    """Tests for clear-cut lead scenarios that should be easy to evaluate."""

    @pytest.mark.asyncio
    async def test_hot_lead_all_signals(
        self, scoring_service, mock_openai_response, valid_llm_response
    ):
        """
        HOT LEAD: Urgent + Complete info + High revenue
        Expected: high urgency, hot quality, high priority
        """
        extracted_fields = {
            "contact_name": {"value": "Michael Chen", "confidence": 1.0},
            "contact_email": {"value": "mchen@bigcorp.com", "confidence": 1.0},
            "contact_phone": {"value": "555-888-9999", "confidence": 1.0},
            "service_need": {
                "value": "S-Corp election for my $500K revenue startup",
                "confidence": 1.0,
            },
            "timeline": {"value": "Immediately - before tax deadline", "confidence": 1.0},
        }

        mock_response = mock_openai_response(valid_llm_response)

        with patch.object(
            scoring_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await scoring_service.evaluate_lead(extracted_fields)

        assert result.urgency_level == "high"
        assert result.lead_quality == "hot"
        assert result.priority_level == "high"
        assert result.lead_score >= 80
        assert result.confidence >= 0.9
        assert len(result.scoring.signals_matched) > 0

    @pytest.mark.asyncio
    async def test_cold_lead_minimal_info(self, scoring_service, mock_openai_response):
        """
        COLD LEAD: Vague need + No urgency + Minimal info
        Expected: low urgency, cold quality, low priority
        """
        extracted_fields = {
            "contact_name": {"value": "Someone", "confidence": 0.5},
            "contact_email": {"value": "test@test.com", "confidence": 1.0},
            "service_need": {"value": "just looking around", "confidence": 0.6},
        }

        mock_response = mock_openai_response(
            {
                "lead_score": 35,
                "priority_level": "low",
                "lead_quality": "cold",
                "urgency_level": "low",
                "lead_summary": {
                    "contact": {"name": "Someone", "email": "test@test.com", "phone": None},
                    "service_need": "Browsing",
                    "additional_info": {},
                    "follow_up_questions": ["What specific service are you looking for?"],
                },
                "scoring": {
                    "score": 35,
                    "priority": "low",
                    "signals_matched": [],
                    "penalties_applied": [
                        {
                            "penalty_id": "vague_need",
                            "points": -15,
                            "reason": "Unclear requirements",
                        }
                    ],
                    "reasoning": "Vague interest with incomplete info suggests tire kicker.",
                },
                "confidence": 0.85,
            }
        )

        with patch.object(
            scoring_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await scoring_service.evaluate_lead(extracted_fields)

        assert result.urgency_level == "low"
        assert result.lead_quality == "cold"
        assert result.priority_level == "low"
        assert result.lead_score < 50

    @pytest.mark.asyncio
    async def test_warm_lead_good_but_not_urgent(self, scoring_service, mock_openai_response):
        """
        WARM LEAD: Clear need + Complete info + No urgency
        Expected: low urgency, warm quality, medium priority
        """
        extracted_fields = {
            "contact_name": {"value": "Sarah Johnson", "confidence": 1.0},
            "contact_email": {"value": "sarah@company.com", "confidence": 1.0},
            "contact_phone": {"value": "555-123-4567", "confidence": 1.0},
            "service_need": {
                "value": "Annual tax preparation for my small business",
                "confidence": 1.0,
            },
            "timeline": {"value": "Sometime this quarter", "confidence": 0.8},
        }

        mock_response = mock_openai_response(
            {
                "lead_score": 65,
                "priority_level": "medium",
                "lead_quality": "warm",
                "urgency_level": "low",
                "lead_summary": {
                    "contact": {
                        "name": "Sarah Johnson",
                        "email": "sarah@company.com",
                        "phone": "555-123-4567",
                    },
                    "service_need": "Annual tax preparation",
                    "additional_info": {"timeline": "This quarter"},
                    "follow_up_questions": ["What is your business structure?"],
                },
                "scoring": {
                    "score": 65,
                    "priority": "medium",
                    "signals_matched": [
                        {
                            "signal_id": "business_owner",
                            "points": 10,
                            "reason": "Small business owner",
                        }
                    ],
                    "penalties_applied": [],
                    "reasoning": "Clear business need with complete info but no urgency.",
                },
                "confidence": 0.88,
            }
        )

        with patch.object(
            scoring_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await scoring_service.evaluate_lead(extracted_fields)

        assert result.urgency_level == "low"
        assert result.lead_quality == "warm"
        assert result.priority_level == "medium"


# ============================================================================
# 2. EDGE CASES - Missing data, malformed input, errors
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_extracted_fields(self, scoring_service, mock_openai_response):
        """Handle empty extracted fields gracefully."""
        extracted_fields = {}

        mock_response = mock_openai_response(
            {
                "lead_score": 30,
                "priority_level": "low",
                "lead_quality": "cold",
                "urgency_level": "low",
                "lead_summary": {
                    "contact": {"name": "Unknown", "email": None, "phone": None},
                    "service_need": "Not specified",
                    "additional_info": {},
                    "follow_up_questions": [],
                },
                "scoring": {
                    "score": 30,
                    "priority": "low",
                    "signals_matched": [],
                    "penalties_applied": [],
                    "reasoning": "No lead information provided.",
                },
                "confidence": 0.5,
            }
        )

        with patch.object(
            scoring_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await scoring_service.evaluate_lead(extracted_fields)

        assert result.priority_level == "low"
        assert result.confidence <= 0.6

    @pytest.mark.asyncio
    async def test_llm_returns_invalid_json(self, scoring_service):
        """Handle invalid JSON response from LLM."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is not valid JSON {{{}"

        with patch.object(
            scoring_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await scoring_service.evaluate_lead({"contact_name": {"value": "Test"}})

        # Should return default evaluation, not crash
        assert result is not None
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_llm_api_error(self, scoring_service):
        """Handle LLM API errors gracefully."""
        with patch.object(
            scoring_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=Exception("API rate limit exceeded"),
        ):
            result = await scoring_service.evaluate_lead({"contact_name": {"value": "Test"}})

        # Should return default evaluation, not crash
        assert result is not None
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_plain_value_format(
        self, scoring_service, mock_openai_response, valid_llm_response
    ):
        """Handle plain string values (not dict with 'value' key)."""
        extracted_fields = {
            "contact_name": "John Smith",  # Plain string
            "contact_email": "john@test.com",
            "service_need": "Tax help",
        }

        mock_response = mock_openai_response(valid_llm_response)

        with patch.object(
            scoring_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await scoring_service.evaluate_lead(extracted_fields)

        # Should not crash - should handle plain values
        assert result is not None
        assert isinstance(result, LeadEvaluationResult)


# ============================================================================
# 3. WORKFLOW CONTEXT - How context affects evaluation
# ============================================================================


class TestWorkflowContext:
    """Tests for how workflow context affects evaluation."""

    @pytest.mark.asyncio
    async def test_scoring_rules_included_in_prompt(
        self, scoring_service, mock_openai_response, valid_llm_response
    ):
        """Workflow scoring rules should be passed to LLM."""
        extracted_fields = {
            "contact_name": {"value": "Test User", "confidence": 1.0},
            "annual_revenue": {"value": "$500K - $1M", "confidence": 1.0},
        }

        workflow_context = {
            "template_name": "S-Corp Election Consultation",
            "scoring_rules": {
                "quality_signals": [
                    {
                        "signal_id": "high_revenue",
                        "points": 15,
                        "condition": {
                            "field": "annual_revenue",
                            "operator": "in",
                            "value": ["$500K - $1M", "Over $1M"],
                        },
                    },
                ],
                "risk_penalties": [
                    {
                        "penalty_id": "low_revenue",
                        "points": -10,
                        "condition": {
                            "field": "annual_revenue",
                            "operator": "equals",
                            "value": "Under $50K",
                        },
                    },
                ],
            },
        }

        mock_response = mock_openai_response(valid_llm_response)

        with patch.object(
            scoring_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await scoring_service.evaluate_lead(extracted_fields, workflow_context)

            # Verify scoring rules were included in system prompt
            call_args = mock_create.call_args
            messages = call_args.kwargs["messages"]
            system_message = messages[0]["content"]

            assert "high_revenue" in system_message
            assert "low_revenue" in system_message

    @pytest.mark.asyncio
    async def test_no_context_still_works(
        self, scoring_service, mock_openai_response, valid_llm_response
    ):
        """Service should work without workflow context."""
        extracted_fields = {
            "contact_name": {"value": "Test User", "confidence": 1.0},
        }

        mock_response = mock_openai_response(valid_llm_response)

        with patch.object(
            scoring_service.client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await scoring_service.evaluate_lead(extracted_fields, workflow_context=None)

        assert result is not None


# ============================================================================
# 4. BACKGROUND TASK - Fire-and-forget behavior
# ============================================================================


class TestBackgroundTask:
    """Tests for background task behavior."""

    @pytest.mark.asyncio
    async def test_background_task_updates_database(self, mock_openai_response, valid_llm_response):
        """Background task should update session with evaluation."""
        session_id = uuid4()
        extracted_fields = {
            "contact_name": {"value": "Test User", "confidence": 1.0},
        }

        # Mock session and repo
        mock_session_ctx = MagicMock()
        mock_db_session = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_repo = MagicMock()
        mock_repo.update_session_lead_evaluation = AsyncMock(return_value=True)

        with patch("livekit.services.lead_scoring_service.LeadScoringService") as MockService:
            mock_service_instance = MagicMock()
            mock_service_instance.evaluate_lead = AsyncMock(
                return_value=LeadEvaluationResult(**valid_llm_response)
            )
            MockService.return_value = mock_service_instance

            with patch(
                "shared.database.models.database.async_session_maker",
                return_value=mock_session_ctx,
            ):
                with patch(
                    "shared.database.repositories.workflow_repository.WorkflowRepository",
                    return_value=mock_repo,
                ):
                    await score_lead_background(session_id, extracted_fields)

                    # Verify service was called
                    mock_service_instance.evaluate_lead.assert_called_once()

    @pytest.mark.asyncio
    async def test_background_task_error_does_not_raise(self):
        """Background task errors should be logged, not raised."""
        session_id = uuid4()
        extracted_fields = {"contact_name": {"value": "Test"}}

        # Mock service to raise exception
        with patch("livekit.services.lead_scoring_service.LeadScoringService") as MockService:
            mock_service_instance = MagicMock()
            mock_service_instance.evaluate_lead = AsyncMock(
                side_effect=Exception("Simulated failure")
            )
            MockService.return_value = mock_service_instance

            # Should not raise - fire and forget
            try:
                await score_lead_background(session_id, extracted_fields)
            except Exception as e:
                pytest.fail(f"Background task should not raise exceptions: {e}")


# ============================================================================
# 5. PYDANTIC MODEL VALIDATION
# ============================================================================


class TestPydanticModels:
    """Tests for Pydantic model validation."""

    def test_lead_evaluation_result_valid(self, valid_llm_response):
        """Create valid LeadEvaluationResult."""
        result = LeadEvaluationResult(**valid_llm_response)

        assert result.lead_score == 85
        assert result.priority_level == "high"
        assert result.lead_quality == "hot"
        assert result.lead_summary.contact.name == "John Smith"
        assert len(result.scoring.signals_matched) == 2

    def test_lead_contact_model(self):
        """Test LeadContact model."""
        contact = LeadContact(name="Jane Doe", email="jane@test.com", phone="555-0000")

        assert contact.name == "Jane Doe"
        assert contact.email == "jane@test.com"

    def test_lead_summary_model(self):
        """Test LeadSummary model."""
        summary = LeadSummary(
            contact=LeadContact(name="Test", email=None, phone=None),
            service_need="Tax help",
            additional_info={"state": "CA"},
            follow_up_questions=["What is your timeline?"],
        )

        assert summary.service_need == "Tax help"
        assert len(summary.follow_up_questions) == 1

    def test_lead_scoring_model(self):
        """Test LeadScoring model."""
        scoring = LeadScoring(
            score=75,
            priority="medium",
            signals_matched=[],
            penalties_applied=[],
            reasoning="Good lead",
        )

        assert scoring.score == 75
        assert scoring.priority == "medium"

    def test_model_dump(self, valid_llm_response):
        """Test model can be dumped to dict for database storage."""
        result = LeadEvaluationResult(**valid_llm_response)
        data = result.model_dump()

        assert isinstance(data, dict)
        assert data["lead_score"] == 85
        assert data["lead_summary"]["contact"]["name"] == "John Smith"
