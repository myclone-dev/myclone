"""
Unit Tests for ConversationalWorkflowHandler and Related Services

Tests tone controls, lead summary templates, no-redundant-questions feature,
and other handler functionality.

Architecture Note:
- Single-LLM approach: Main LLM handles field extraction via update_lead_field() tool
- Handler orchestrates workflow lifecycle (start, progress, completion)
- Services provide specific functionality (tone, summary, scoring)
"""

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from livekit.tests.fixtures.cpa_workflow import CPA_WORKFLOW_DATA

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def workflow_data():
    """CPA workflow configuration."""
    return CPA_WORKFLOW_DATA.copy()


@pytest.fixture
def test_persona_id():
    """Test persona UUID."""
    return UUID("e99721c3-c2cd-434f-a00b-fd1aa98a9e6f")


@pytest.fixture
def mock_output():
    """Mock output callback."""
    callback = AsyncMock()
    callback.messages = []

    async def record(msg, allow_interruptions=True):
        callback.messages.append(msg)

    callback.side_effect = record
    return callback


# ============================================================================
# Test: Lead Summary Templates (CPA-Facing)
# ============================================================================


class TestLeadSummaryTemplates:
    """Tests for configurable lead summary templates (CPA/expert-facing).

    The lead summary is what the CPA/business owner sees - it includes
    score, priority, and detailed information for follow-up.

    Templates:
    - structured (default): Current format with headers
    - synopsis: Narrative paragraph format
    - minimal: One-liner format
    - detailed: Structured + score breakdown
    """

    @pytest.fixture
    def summary_service(self):
        """Create summary service instance."""
        from livekit.services.workflow_summary_service import WorkflowSummaryService

        return WorkflowSummaryService()

    @pytest.fixture
    def sample_extracted_fields(self):
        """Sample extracted fields for testing."""
        return {
            "contact_name": {"value": "Raj Patel"},
            "contact_email": {"value": "raj@email.com"},
            "contact_phone": {"value": "555-987-6543"},
            "service_need": {"value": "FBAR filing and 1040"},
            "business_type": {"value": "Software Engineer"},
            "timeline": {"value": "30 days"},
        }

    @pytest.fixture
    def sample_score_result(self):
        """Sample score result for testing."""
        return {
            "total_score": 85,
            "priority_level": "high",
            "base_score": 50,
            "field_completeness_bonus": 15,
            "quality_signals_bonus": 25,
            "risk_penalty": -5,
            "quality_signals_matched": ["foreign_accounts", "urgent_timeline"],
            "risk_signals_matched": ["first_time_filer"],
        }

    # -------------------------------------------------------------------------
    # Test: Structured Template (Default)
    # -------------------------------------------------------------------------

    def test_structured_template_default(
        self, summary_service, sample_extracted_fields, sample_score_result
    ):
        """Structured template should be used by default (no config)."""
        summary = summary_service.build_summary(
            extracted_fields=sample_extracted_fields,
            score_result=sample_score_result,
        )

        # Should have header
        assert "LEAD SUMMARY" in summary
        assert "=" in summary  # Separator line

        # Should have labeled fields
        assert "CONTACT:" in summary or "Raj Patel" in summary
        assert "EMAIL:" in summary or "raj@email.com" in summary
        assert "PHONE:" in summary or "555-987-6543" in summary
        assert "SERVICE" in summary or "FBAR" in summary

        # Should have score
        assert "85" in summary
        assert "HIGH" in summary.upper()

    def test_structured_template_explicit(
        self, summary_service, sample_extracted_fields, sample_score_result
    ):
        """Structured template should work when explicitly specified."""
        summary = summary_service.build_summary(
            extracted_fields=sample_extracted_fields,
            score_result=sample_score_result,
            template="structured",
        )

        # Should have structured format with headers
        assert "LEAD SUMMARY" in summary or "CONTACT" in summary
        assert "85" in summary

    # -------------------------------------------------------------------------
    # Test: Synopsis Template
    # -------------------------------------------------------------------------

    def test_synopsis_template_narrative_format(
        self, summary_service, sample_extracted_fields, sample_score_result
    ):
        """Synopsis template should produce a narrative paragraph."""
        summary = summary_service.build_summary(
            extracted_fields=sample_extracted_fields,
            score_result=sample_score_result,
            template="synopsis",
        )

        # Should NOT have section headers like "CONTACT:" or "EMAIL:"
        assert "CONTACT:" not in summary
        assert "EMAIL:" not in summary

        # Should be narrative (contains connecting words)
        assert "Raj Patel" in summary
        assert "raj@email.com" in summary
        assert "85" in summary or "85/100" in summary

        # Should mention priority
        assert "high" in summary.lower() or "priority" in summary.lower()

    def test_synopsis_template_includes_service(
        self, summary_service, sample_extracted_fields, sample_score_result
    ):
        """Synopsis should mention the service need."""
        summary = summary_service.build_summary(
            extracted_fields=sample_extracted_fields,
            score_result=sample_score_result,
            template="synopsis",
        )

        # Should mention what they need
        assert "FBAR" in summary or "filing" in summary.lower()

    # -------------------------------------------------------------------------
    # Test: Minimal Template
    # -------------------------------------------------------------------------

    def test_minimal_template_compact(
        self, summary_service, sample_extracted_fields, sample_score_result
    ):
        """Minimal template should produce a compact one-liner."""
        summary = summary_service.build_summary(
            extracted_fields=sample_extracted_fields,
            score_result=sample_score_result,
            template="minimal",
        )

        # Should be compact (single line or very short)
        lines = [line for line in summary.strip().split("\n") if line.strip()]
        assert len(lines) <= 3  # At most 3 lines

        # Should have essential info
        assert "Raj Patel" in summary
        assert "raj@email.com" in summary or "555-987-6543" in summary
        assert "85" in summary

    def test_minimal_template_no_verbose_headers(
        self, summary_service, sample_extracted_fields, sample_score_result
    ):
        """Minimal template should not have verbose headers."""
        summary = summary_service.build_summary(
            extracted_fields=sample_extracted_fields,
            score_result=sample_score_result,
            template="minimal",
        )

        # Should NOT have verbose headers
        assert "LEAD SUMMARY" not in summary
        assert "SERVICE NEEDED:" not in summary
        assert "=" * 10 not in summary  # No separator lines

    # -------------------------------------------------------------------------
    # Test: Detailed Template
    # -------------------------------------------------------------------------

    def test_detailed_template_includes_breakdown(
        self, summary_service, sample_extracted_fields, sample_score_result
    ):
        """Detailed template should include score breakdown."""
        summary = summary_service.build_summary(
            extracted_fields=sample_extracted_fields,
            score_result=sample_score_result,
            template="detailed",
            include_score_breakdown=True,
        )

        # Should have all structured content
        assert "Raj Patel" in summary
        assert "85" in summary

        # Should have score breakdown
        assert "base" in summary.lower() or "50" in summary
        assert "bonus" in summary.lower() or "15" in summary or "25" in summary

    def test_detailed_template_shows_signals(
        self, summary_service, sample_extracted_fields, sample_score_result
    ):
        """Detailed template should show quality/risk signals matched."""
        summary = summary_service.build_summary(
            extracted_fields=sample_extracted_fields,
            score_result=sample_score_result,
            template="detailed",
            include_score_breakdown=True,
        )

        # Should mention signals that were matched
        assert (
            "foreign" in summary.lower()
            or "urgent" in summary.lower()
            or "quality" in summary.lower()
        )

    # -------------------------------------------------------------------------
    # Test: Edge Cases
    # -------------------------------------------------------------------------

    def test_unknown_template_falls_back_to_structured(
        self, summary_service, sample_extracted_fields, sample_score_result
    ):
        """Unknown template should fall back to structured."""
        summary = summary_service.build_summary(
            extracted_fields=sample_extracted_fields,
            score_result=sample_score_result,
            template="unknown_template",
        )

        # Should produce valid output (structured format)
        assert "Raj Patel" in summary
        assert "85" in summary

    def test_empty_output_config_uses_structured(
        self, summary_service, sample_extracted_fields, sample_score_result
    ):
        """Empty output config should use structured template."""
        summary = summary_service.build_summary(
            extracted_fields=sample_extracted_fields,
            score_result=sample_score_result,
        )

        # Should have structured format
        assert "LEAD SUMMARY" in summary or "CONTACT" in summary

    def test_missing_fields_handled_gracefully(self, summary_service, sample_score_result):
        """Should handle missing fields gracefully in all templates."""
        minimal_fields = {
            "contact_name": {"value": "John"},
            "contact_email": {"value": "john@test.com"},
        }

        for template in ["structured", "synopsis", "minimal", "detailed"]:
            summary = summary_service.build_summary(
                extracted_fields=minimal_fields,
                score_result=sample_score_result,
                template=template,
            )

            # Should not crash and should have some content
            assert summary is not None
            assert len(summary) > 0
            assert "John" in summary


# ============================================================================
# Test: Advice Redirect
# ============================================================================
# NOTE: Advice redirect is handled by the LLM via system prompt instructions.
# The LLM contextually determines when to redirect advice questions to the expert.
# Integration tests for this behavior can be added to test_cpa_lead_capture.py
# if needed to verify LLM compliance with redirect instructions.
# ============================================================================


# ============================================================================
# Test: No Redundant Questions
# ============================================================================


class TestNoRedundantQuestions:
    """Tests for no redundant questions feature.

    The bot should NOT ask for information that:
    1. Has already been captured (in extracted_fields)
    2. Has already been asked (in session_metadata.asked_fields)

    Override scenarios where we SHOULD re-ask:
    1. User explicitly asks to update: "I want to change my email"
    2. Correction flow: User says "that's wrong" during confirmation
    """

    @pytest.fixture
    def handler(self, workflow_data):
        """Create handler instance for no-redundant-questions testing."""
        from livekit.handlers.workflow.conversational_handler import (
            ConversationalWorkflowHandler,
        )

        return ConversationalWorkflowHandler(
            workflow_data=workflow_data,
            persona_id=uuid4(),
            output_callback=AsyncMock(),
            text_only_mode=True,
        )

    @pytest.fixture
    def required_fields(self, workflow_data):
        """Get required fields from CPA workflow."""
        return workflow_data["required_fields"]

    # -------------------------------------------------------------------------
    # Test: _get_next_clarifying_question skips asked fields
    # -------------------------------------------------------------------------

    def test_skips_already_asked_fields(self, handler, required_fields):
        """Should skip fields that have already been asked."""
        missing_fields = ["contact_name", "contact_email", "contact_phone"]
        asked_fields = ["contact_name"]  # Already asked for name

        question, field_id = handler._get_next_clarifying_question(
            missing_fields=missing_fields,
            required_fields=required_fields,
            asked_fields=asked_fields,
        )

        # Should ask for email (next field), not name (already asked)
        assert field_id == "contact_email"
        assert "email" in question.lower()

    def test_skips_multiple_asked_fields(self, handler, required_fields):
        """Should skip multiple fields that have been asked."""
        missing_fields = ["contact_name", "contact_email", "contact_phone", "service_need"]
        asked_fields = ["contact_name", "contact_email"]  # Already asked name and email

        question, field_id = handler._get_next_clarifying_question(
            missing_fields=missing_fields,
            required_fields=required_fields,
            asked_fields=asked_fields,
        )

        # Should ask for phone (next unanswered, unasked field)
        assert field_id == "contact_phone"
        assert "phone" in question.lower()

    def test_returns_none_when_all_missing_fields_already_asked(self, handler, required_fields):
        """Should return None when all missing fields have been asked."""
        missing_fields = ["contact_name", "contact_email"]
        asked_fields = ["contact_name", "contact_email"]  # All missing fields already asked

        question, field_id = handler._get_next_clarifying_question(
            missing_fields=missing_fields,
            required_fields=required_fields,
            asked_fields=asked_fields,
        )

        # Should return None - nothing new to ask
        assert field_id is None
        assert question is None

    def test_empty_asked_fields_asks_first_missing(self, handler, required_fields):
        """With no asked_fields, should ask for first missing field."""
        missing_fields = ["contact_email", "contact_phone"]
        asked_fields = []  # Nothing asked yet

        question, field_id = handler._get_next_clarifying_question(
            missing_fields=missing_fields,
            required_fields=required_fields,
            asked_fields=asked_fields,
        )

        # Should ask for first missing field
        assert field_id == "contact_email"
        assert "email" in question.lower()

    def test_backwards_compatible_without_asked_fields(self, handler, required_fields):
        """Should work without asked_fields parameter (backwards compatible)."""
        missing_fields = ["contact_name", "contact_email"]

        # Call without asked_fields parameter
        question, field_id = handler._get_next_clarifying_question(
            missing_fields=missing_fields,
            required_fields=required_fields,
        )

        # Should ask for first missing field
        assert field_id == "contact_name"
        assert question is not None

    # -------------------------------------------------------------------------
    # Test: Update intent detection (override to re-ask)
    # -------------------------------------------------------------------------

    def test_detect_update_intent_explicit_change(self, handler):
        """Should detect when user explicitly wants to change a field."""
        # Explicit update requests
        assert handler._detect_update_intent("I want to change my email")
        assert handler._detect_update_intent("Let me update my phone number")
        assert handler._detect_update_intent("Can I correct my name?")
        assert handler._detect_update_intent("I need to fix my email address")
        assert handler._detect_update_intent("Actually, let me change that")

    def test_detect_update_intent_actually_pattern(self, handler):
        """Should detect 'actually' pattern as update intent."""
        assert handler._detect_update_intent("Actually my email is different@test.com")
        assert handler._detect_update_intent("Actually, it's john.doe@example.com")

    def test_not_detect_update_intent_normal_messages(self, handler):
        """Should NOT detect update intent in normal messages."""
        assert not handler._detect_update_intent("My email is john@test.com")
        assert not handler._detect_update_intent("Yes, that's correct")
        assert not handler._detect_update_intent("I need help with taxes")
        assert not handler._detect_update_intent("The phone number is 555-1234")

    # -------------------------------------------------------------------------
    # Test: Asked fields tracking in process_message
    # -------------------------------------------------------------------------

    def test_asked_fields_added_after_asking_question(self, handler):
        """After asking a clarifying question, field should be added to asked_fields."""
        # This is an integration-level test that will be tested in integration tests
        # Here we just verify the helper method works
        current_asked = ["contact_name"]
        new_field = "contact_email"

        updated = handler._add_to_asked_fields(current_asked, new_field)

        assert "contact_name" in updated
        assert "contact_email" in updated
        assert len(updated) == 2

    def test_asked_fields_not_duplicated(self, handler):
        """Should not add duplicate fields to asked_fields."""
        current_asked = ["contact_name", "contact_email"]
        new_field = "contact_email"  # Already in list

        updated = handler._add_to_asked_fields(current_asked, new_field)

        assert updated.count("contact_email") == 1
        assert len(updated) == 2

    def test_asked_fields_cleared_on_correction_flow(self, handler):
        """When user rejects confirmation, asked_fields should be cleared."""
        current_asked = ["contact_name", "contact_email", "contact_phone"]

        cleared = handler._clear_asked_fields_for_correction(current_asked)

        # Should return empty list to allow re-asking
        assert cleared == []


# ============================================================================
# Test: Tone Controls
# ============================================================================


class TestToneControls:
    """Tests for configurable conversation tone.

    Available tones:
    - concierge: White-glove premium service (warm, appreciative)
    - professional: Friendly but efficient (default)
    - casual: Relaxed, conversational
    - efficient: Minimal, fast-paced

    Configure via extraction_strategy.tone in workflow config.
    """

    @pytest.fixture
    def handler(self):
        """Create handler instance for tone testing."""
        from livekit.handlers.workflow.conversational_handler import (
            ConversationalWorkflowHandler,
        )

        return ConversationalWorkflowHandler(
            workflow_data={"workflow_type": "conversational"},
            persona_id=uuid4(),
            output_callback=AsyncMock(),
            text_only_mode=True,
        )

    # Alias for backwards compatibility with existing tests
    @pytest.fixture
    def coordinator(self, handler):
        """Alias handler as coordinator for test compatibility."""
        return handler

    # -------------------------------------------------------------------------
    # Test: Tone Presets Exist
    # -------------------------------------------------------------------------

    def test_all_tone_presets_exist(self, coordinator):
        """All expected tone presets should be defined."""
        expected_tones = ["concierge", "professional", "casual", "efficient"]

        for tone in expected_tones:
            config = coordinator._get_tone_config(tone)
            assert config is not None
            assert "acknowledgments" in config
            assert "question_prefix" in config
            assert "confirmation_intro" in config

    def test_unknown_tone_falls_back_to_professional(self, coordinator):
        """Unknown tone should fall back to professional."""
        config = coordinator._get_tone_config("unknown_tone")
        professional_config = coordinator._get_tone_config("professional")

        assert config == professional_config

    def test_none_tone_defaults_to_professional(self, coordinator):
        """None tone should default to professional."""
        config = coordinator._get_tone_config(None)
        professional_config = coordinator._get_tone_config("professional")

        assert config == professional_config

    # -------------------------------------------------------------------------
    # Test: Acknowledgments
    # -------------------------------------------------------------------------

    def test_concierge_acknowledgment_is_warm(self, coordinator):
        """Concierge acknowledgment should be warm and appreciative."""
        ack = coordinator._get_acknowledgment("concierge")

        # Should contain warm language
        assert any(word in ack.lower() for word in ["wonderful", "thank you", "appreciate"])

    def test_professional_acknowledgment_is_polite(self, coordinator):
        """Professional acknowledgment should be polite but efficient."""
        ack = coordinator._get_acknowledgment("professional")

        assert "thank" in ack.lower() or "got it" in ack.lower()

    def test_efficient_acknowledgment_is_minimal(self, coordinator):
        """Efficient acknowledgment should be minimal."""
        ack = coordinator._get_acknowledgment("efficient")

        # Should be short
        assert len(ack) < 15

    # -------------------------------------------------------------------------
    # Test: Question Formatting
    # -------------------------------------------------------------------------

    def test_concierge_question_has_polite_prefix(self, coordinator):
        """Concierge questions should have polite prefix."""
        question = coordinator._format_question_with_tone(None, "email", "concierge")

        assert "may i ask" in question.lower()

    def test_professional_question_has_standard_prefix(self, coordinator):
        """Professional questions should have standard prefix."""
        question = coordinator._format_question_with_tone(None, "email", "professional")

        assert "could you tell me" in question.lower()

    def test_efficient_question_is_direct(self, coordinator):
        """Efficient questions should be direct with no prefix."""
        question = coordinator._format_question_with_tone(None, "email", "efficient")

        # Should be direct - just "Email?"
        assert question == "email?" or question == "Email?"

    def test_custom_question_overrides_tone(self, coordinator):
        """Custom clarifying question should override tone formatting."""
        custom_q = "What email address can we reach you at?"
        question = coordinator._format_question_with_tone(custom_q, "email", "efficient")

        # Should use the custom question as-is
        assert question == custom_q

    # -------------------------------------------------------------------------
    # Test: Confirmation Summary with Tone
    # -------------------------------------------------------------------------

    def test_confirmation_summary_uses_tone_intro(self, handler, workflow_data):
        """Confirmation summary should use tone-appropriate intro."""
        from livekit.services.workflow_tone_service import WorkflowToneService

        extracted_fields = {
            "contact_name": {"value": "John"},
            "contact_email": {"value": "john@test.com"},
        }
        required_field_ids = ["contact_name", "contact_email"]

        # Test concierge tone - create fresh service with concierge config
        concierge_data = {**workflow_data, "extraction_strategy": {"tone": "concierge"}}
        handler.workflow_data = concierge_data
        handler.tone_service = WorkflowToneService(concierge_data)
        concierge_summary = handler._build_confirmation_summary_with_tone(
            extracted_fields,
            workflow_data["required_fields"],
            required_field_ids,
        )
        assert "make sure" in concierge_summary.lower() or "correct" in concierge_summary.lower()

        # Test professional tone
        professional_data = {**workflow_data, "extraction_strategy": {"tone": "professional"}}
        handler.workflow_data = professional_data
        handler.tone_service = WorkflowToneService(professional_data)
        professional_summary = handler._build_confirmation_summary_with_tone(
            extracted_fields,
            workflow_data["required_fields"],
            required_field_ids,
        )
        assert (
            "perfect" in professional_summary.lower() or "confirm" in professional_summary.lower()
        )

        # Test efficient tone
        efficient_data = {**workflow_data, "extraction_strategy": {"tone": "efficient"}}
        handler.workflow_data = efficient_data
        handler.tone_service = WorkflowToneService(efficient_data)
        efficient_summary = handler._build_confirmation_summary_with_tone(
            extracted_fields,
            workflow_data["required_fields"],
            required_field_ids,
        )
        assert "confirming" in efficient_summary.lower()

    # -------------------------------------------------------------------------
    # Test: Question Generation with Tone
    # -------------------------------------------------------------------------

    def test_get_next_question_uses_tone(self, handler, workflow_data):
        """Question formatting should use configured tone."""
        from livekit.services.workflow_tone_service import WorkflowToneService

        # Test concierge tone - polite prefix
        concierge_data = {"extraction_strategy": {"tone": "concierge"}}
        handler.workflow_data = concierge_data
        handler.tone_service = WorkflowToneService(concierge_data)
        question = handler._format_question_with_tone(None, "email")
        assert "may i ask" in question.lower()

        # Test efficient tone - direct, no prefix
        efficient_data = {"extraction_strategy": {"tone": "efficient"}}
        handler.workflow_data = efficient_data
        handler.tone_service = WorkflowToneService(efficient_data)
        question = handler._format_question_with_tone(None, "email")
        assert question.lower() == "email?"
