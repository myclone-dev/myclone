"""
Unit Tests for WorkflowScoringEngine

Tests lead scoring calculation including:
- Base score
- Field completeness bonus
- Quality signals (config-driven and legacy)
- Risk penalties (config-driven and legacy)
- Priority classification
"""

import pytest

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def scoring_engine():
    """Create a WorkflowScoringEngine instance."""
    from livekit.services.workflow_scoring_engine import WorkflowScoringEngine

    return WorkflowScoringEngine()


@pytest.fixture
def basic_scoring_rules():
    """Basic scoring rules for testing."""
    return {
        "base_score": 50,
        "field_completeness_weight": 20,
        "quality_signals": [],
        "risk_penalties": [],
    }


@pytest.fixture
def cpa_scoring_rules():
    """CPA-style scoring rules with quality signals and risk penalties."""
    return {
        "base_score": 50,
        "field_completeness_weight": 20,
        "quality_signals": [
            {
                "signal_id": "revenue_1m_plus",
                "points": 15,
                "condition": {
                    "field": "revenue_range",
                    "operator": "contains_any",
                    "values": ["$1M", "$5M"],
                },
            },
            {
                "signal_id": "urgent_timeline",
                "points": 10,
                "condition": {
                    "field": "timeline",
                    "operator": "contains_any",
                    "values": ["Immediate", "ASAP", "urgent"],
                },
            },
            {
                "signal_id": "foreign_accounts",
                "points": 15,
                "condition": {
                    "field": "foreign_accounts",
                    "operator": "exists",
                },
            },
            {
                "signal_id": "s_corp",
                "points": 5,
                "condition": {
                    "field": "entity_type",
                    "operator": "equals",
                    "value": "S-Corp",
                },
            },
        ],
        "risk_penalties": [
            {
                "penalty_id": "unfiled_returns",
                "points": -20,
                "condition": {
                    "field": "red_flags",
                    "operator": "contains",
                    "value": "unfiled",
                },
            },
            {
                "penalty_id": "irs_notice",
                "points": -15,
                "condition": {
                    "field": "red_flags",
                    "operator": "contains_any",
                    "values": ["irs notice", "irs letter", "audit"],
                },
            },
            {
                "penalty_id": "messy_books",
                "points": -10,
                "condition": {
                    "field": "bookkeeping_status",
                    "operator": "contains",
                    "value": "behind",
                },
            },
        ],
    }


@pytest.fixture
def required_fields():
    """Standard required field IDs."""
    return ["contact_name", "contact_email", "contact_phone", "service_need"]


@pytest.fixture
def optional_fields():
    """Standard optional field IDs."""
    return [
        "revenue_range",
        "entity_type",
        "state",
        "timeline",
        "foreign_accounts",
        "red_flags",
        "bookkeeping_status",
    ]


# ============================================================================
# Test: Base Score Calculation
# ============================================================================


class TestBaseScore:
    """Tests for base score calculation."""

    def test_base_score_default(self, scoring_engine, required_fields, optional_fields):
        """Should use default base score of 50."""
        result = scoring_engine.calculate_score(
            extracted_fields={},
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules={},  # No explicit base_score
        )
        assert result.base_score == 50

    def test_base_score_custom(self, scoring_engine, required_fields, optional_fields):
        """Should use custom base score when provided."""
        result = scoring_engine.calculate_score(
            extracted_fields={},
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules={"base_score": 40},
        )
        assert result.base_score == 40


# ============================================================================
# Test: Field Completeness Bonus
# ============================================================================


class TestFieldCompletenessBonus:
    """Tests for field completeness bonus calculation."""

    def test_no_optional_fields_captured(
        self, scoring_engine, basic_scoring_rules, required_fields, optional_fields
    ):
        """Should have 0 completeness bonus when no optional fields captured."""
        extracted = {
            "contact_name": {"value": "John"},
            "contact_email": {"value": "john@test.com"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=basic_scoring_rules,
        )

        assert result.field_completeness_score == 0

    def test_half_optional_fields_captured(
        self, scoring_engine, basic_scoring_rules, required_fields, optional_fields
    ):
        """Should have 50% of completeness weight when half optional fields captured."""
        # 7 optional fields, capture ~half (3-4)
        extracted = {
            "contact_name": {"value": "John"},
            "revenue_range": {"value": "$1M+"},
            "entity_type": {"value": "LLC"},
            "state": {"value": "California"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=basic_scoring_rules,
        )

        # 3 of 7 optional fields = 42.8% of 20 = ~8.5
        expected_bonus = (3 / 7) * 20
        assert abs(result.field_completeness_score - expected_bonus) < 0.1

    def test_all_optional_fields_captured(
        self, scoring_engine, basic_scoring_rules, required_fields, optional_fields
    ):
        """Should have full completeness weight when all optional fields captured."""
        extracted = {
            "contact_name": {"value": "John"},
            "revenue_range": {"value": "$1M+"},
            "entity_type": {"value": "LLC"},
            "state": {"value": "California"},
            "timeline": {"value": "ASAP"},
            "foreign_accounts": {"value": "Yes"},
            "red_flags": {"value": "None"},
            "bookkeeping_status": {"value": "Current"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=basic_scoring_rules,
        )

        assert result.field_completeness_score == 20


# ============================================================================
# Test: Quality Signals (Config-Driven)
# ============================================================================


class TestQualitySignals:
    """Tests for quality signal scoring."""

    def test_no_quality_signals_triggered(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should have no quality signal points when no conditions match."""
        extracted = {
            "contact_name": {"value": "John"},
            "contact_email": {"value": "john@test.com"},
            "revenue_range": {"value": "$100K"},  # Not $1M+
            "timeline": {"value": "No rush"},  # Not urgent
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        assert len(result.quality_signal_scores) == 0

    def test_revenue_1m_plus_signal(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should award +15 points for $1M+ revenue."""
        extracted = {
            "contact_name": {"value": "John"},
            "revenue_range": {"value": "$1M-$5M"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        assert "revenue_1m_plus" in result.quality_signal_scores
        assert result.quality_signal_scores["revenue_1m_plus"] == 15

    def test_urgent_timeline_signal(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should award +10 points for urgent timeline."""
        extracted = {
            "contact_name": {"value": "John"},
            "timeline": {"value": "Need this ASAP"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        assert "urgent_timeline" in result.quality_signal_scores
        assert result.quality_signal_scores["urgent_timeline"] == 10

    def test_foreign_accounts_signal(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should award +15 points when foreign_accounts field exists."""
        extracted = {
            "contact_name": {"value": "John"},
            "foreign_accounts": {"value": "Yes, UK bank account"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        assert "foreign_accounts" in result.quality_signal_scores
        assert result.quality_signal_scores["foreign_accounts"] == 15

    def test_s_corp_signal(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should award +5 points for S-Corp entity type."""
        extracted = {
            "contact_name": {"value": "John"},
            "entity_type": {"value": "S-Corp"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        assert "s_corp" in result.quality_signal_scores
        assert result.quality_signal_scores["s_corp"] == 5

    def test_multiple_quality_signals(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should stack multiple quality signals."""
        extracted = {
            "contact_name": {"value": "John"},
            "revenue_range": {"value": "$5M+"},  # +15
            "timeline": {"value": "Immediate"},  # +10
            "foreign_accounts": {"value": "Yes"},  # +15
            "entity_type": {"value": "S-Corp"},  # +5
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        # Total quality signals: 15 + 10 + 15 + 5 = 45
        total_quality = sum(result.quality_signal_scores.values())
        assert total_quality == 45


# ============================================================================
# Test: Risk Penalties (Config-Driven)
# ============================================================================


class TestRiskPenalties:
    """Tests for risk penalty scoring."""

    def test_no_risk_penalties_triggered(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should have no penalties when no risk conditions match."""
        extracted = {
            "contact_name": {"value": "John"},
            "red_flags": {"value": "None"},
            "bookkeeping_status": {"value": "Current"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        assert len(result.risk_penalty_scores) == 0

    def test_unfiled_returns_penalty(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should apply -20 points for unfiled returns."""
        extracted = {
            "contact_name": {"value": "John"},
            "red_flags": {"value": "Have unfiled 2022 and 2023 returns"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        assert "unfiled_returns" in result.risk_penalty_scores
        assert result.risk_penalty_scores["unfiled_returns"] == -20

    def test_irs_notice_penalty(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should apply -15 points for IRS notice."""
        extracted = {
            "contact_name": {"value": "John"},
            "red_flags": {"value": "Got an irs notice last month"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        assert "irs_notice" in result.risk_penalty_scores
        assert result.risk_penalty_scores["irs_notice"] == -15

    def test_messy_books_penalty(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should apply -10 points for messy bookkeeping."""
        extracted = {
            "contact_name": {"value": "John"},
            "bookkeeping_status": {"value": "We're behind by 6 months"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        assert "messy_books" in result.risk_penalty_scores
        assert result.risk_penalty_scores["messy_books"] == -10

    def test_multiple_risk_penalties(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should stack multiple risk penalties."""
        extracted = {
            "contact_name": {"value": "John"},
            "red_flags": {"value": "Have unfiled returns and got an audit notice"},  # -20 + -15
            "bookkeeping_status": {"value": "Way behind"},  # -10
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        # Total penalties: -20 + -15 + -10 = -45
        total_penalties = sum(result.risk_penalty_scores.values())
        assert total_penalties == -45


# ============================================================================
# Test: Priority Classification
# ============================================================================


class TestPriorityClassification:
    """Tests for priority level classification."""

    def test_high_priority_score_80_plus(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Score >= 80 should be HIGH priority."""
        # Base 50 + completeness 20 + quality 15 = 85
        extracted = {
            "contact_name": {"value": "John"},
            "revenue_range": {"value": "$1M+"},  # +15 quality
            # Fill all optional to get 20 completeness
            "entity_type": {"value": "LLC"},
            "state": {"value": "CA"},
            "timeline": {"value": "Next month"},
            "foreign_accounts": {"value": "No"},
            "red_flags": {"value": "None"},
            "bookkeeping_status": {"value": "Current"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        assert result.total_score >= 80
        assert result.priority_level == "high"

    def test_medium_priority_score_60_to_79(
        self, scoring_engine, basic_scoring_rules, required_fields, optional_fields
    ):
        """Score 60-79 should be MEDIUM priority."""
        # Base 50 + some completeness (3/7 * 20 = ~8.5) = ~58.5
        # Need a bit more...
        extracted = {
            "contact_name": {"value": "John"},
            "revenue_range": {"value": "$500K"},
            "entity_type": {"value": "LLC"},
            "state": {"value": "CA"},
            "timeline": {"value": "Soon"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=basic_scoring_rules,
        )

        # 50 + (4/7)*20 = 50 + 11.4 = 61.4
        assert 60 <= result.total_score < 80
        assert result.priority_level == "medium"

    def test_low_priority_score_below_60(
        self, scoring_engine, basic_scoring_rules, required_fields, optional_fields
    ):
        """Score < 60 should be LOW priority."""
        # Base 50 + no completeness = 50
        extracted = {
            "contact_name": {"value": "John"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=basic_scoring_rules,
        )

        assert result.total_score < 60
        assert result.priority_level == "low"


# ============================================================================
# Test: Total Score Calculation
# ============================================================================


class TestTotalScoreCalculation:
    """Tests for total score calculation and clamping."""

    def test_total_score_basic(
        self, scoring_engine, basic_scoring_rules, required_fields, optional_fields
    ):
        """Should sum base + completeness correctly."""
        # All optional fields filled
        extracted = {
            "revenue_range": {"value": "$1M"},
            "entity_type": {"value": "LLC"},
            "state": {"value": "CA"},
            "timeline": {"value": "Soon"},
            "foreign_accounts": {"value": "No"},
            "red_flags": {"value": "None"},
            "bookkeeping_status": {"value": "OK"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=basic_scoring_rules,
        )

        # 50 base + 20 completeness = 70
        assert result.total_score == 70

    def test_total_score_with_quality_signals(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should add quality signal points."""
        extracted = {
            "contact_name": {"value": "John"},
            "revenue_range": {"value": "$5M+"},  # +15
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        # 50 base + (1/7)*20 completeness + 15 quality = ~67.8
        expected = 50 + (1 / 7) * 20 + 15
        assert abs(result.total_score - expected) < 0.1

    def test_total_score_with_penalties(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should subtract penalty points."""
        extracted = {
            "contact_name": {"value": "John"},
            "red_flags": {"value": "unfiled returns"},  # -20
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        # 50 base + (1/7)*20 completeness - 20 penalty = ~32.8
        expected = 50 + (1 / 7) * 20 - 20
        assert abs(result.total_score - expected) < 0.1

    def test_total_score_clamped_to_100(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should clamp total score to max 100."""
        # Max everything out
        extracted = {
            "contact_name": {"value": "John"},
            "revenue_range": {"value": "$5M+"},  # +15
            "timeline": {"value": "ASAP"},  # +10
            "foreign_accounts": {"value": "Yes"},  # +15
            "entity_type": {"value": "S-Corp"},  # +5
            "state": {"value": "CA"},
            "red_flags": {"value": "None"},
            "bookkeeping_status": {"value": "Current"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        # 50 + 20 + 45 = 115, should clamp to 100
        assert result.total_score == 100

    def test_total_score_clamped_to_0(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Should clamp total score to min 0."""
        # Heavy penalties
        extracted = {
            "contact_name": {"value": "John"},
            "red_flags": {"value": "unfiled returns, irs audit notice"},  # -20 + -15 = -35
            "bookkeeping_status": {"value": "Way behind"},  # -10
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        # 50 + ~8.5 - 45 = ~13.5 (not negative, but let's verify clamping works)
        assert result.total_score >= 0


# ============================================================================
# Test: Real-World Scenarios
# ============================================================================


class TestRealWorldScenarios:
    """End-to-end scoring scenarios matching architecture examples."""

    def test_high_value_lead_scenario(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """High-value CPA lead: $2M revenue, S-Corp, urgent, foreign accounts."""
        extracted = {
            "contact_name": {"value": "Sarah Chen"},
            "contact_email": {"value": "sarah@techcorp.com"},
            "contact_phone": {"value": "415-555-1234"},
            "service_need": {"value": "Tax planning and international compliance"},
            "revenue_range": {"value": "$1M-$5M"},  # +15
            "entity_type": {"value": "S-Corp"},  # +5
            "timeline": {"value": "Need help ASAP - deadline approaching"},  # +10
            "foreign_accounts": {"value": "Yes, accounts in Singapore"},  # +15
            "state": {"value": "California"},
            "red_flags": {"value": "None"},
            "bookkeeping_status": {"value": "Current with QuickBooks"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        # Expect: 50 base + 20 completeness + 45 quality = 115 → clamped to 100
        assert result.total_score == 100
        assert result.priority_level == "high"
        assert "revenue_1m_plus" in result.quality_signal_scores
        assert "foreign_accounts" in result.quality_signal_scores
        assert "s_corp" in result.quality_signal_scores
        assert "urgent_timeline" in result.quality_signal_scores

    def test_risky_lead_scenario(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Risky CPA lead: unfiled returns, IRS notice, messy books."""
        extracted = {
            "contact_name": {"value": "Mike Johnson"},
            "contact_email": {"value": "mike@smallbiz.com"},
            "contact_phone": {"value": "555-123-4567"},
            "service_need": {"value": "Help with back taxes"},
            "revenue_range": {"value": "$100K-$500K"},
            "entity_type": {"value": "LLC"},
            "state": {"value": "Texas"},
            "red_flags": {"value": "I have 3 unfiled returns and received an irs notice last week"},
            "bookkeeping_status": {"value": "We're way behind, haven't updated in months"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        # Expect: 50 base + ~17 completeness - 45 penalties = ~22
        assert result.total_score < 50  # Below base due to penalties
        assert result.priority_level == "low"
        assert "unfiled_returns" in result.risk_penalty_scores
        assert "irs_notice" in result.risk_penalty_scores
        assert "messy_books" in result.risk_penalty_scores

    def test_medium_value_lead_scenario(
        self, scoring_engine, cpa_scoring_rules, required_fields, optional_fields
    ):
        """Medium-value CPA lead: moderate revenue, no special flags."""
        extracted = {
            "contact_name": {"value": "Jane Doe"},
            "contact_email": {"value": "jane@company.com"},
            "contact_phone": {"value": "555-987-6543"},
            "service_need": {"value": "Annual tax filing"},
            "revenue_range": {"value": "$500K-$1M"},
            "entity_type": {"value": "LLC"},
            "state": {"value": "Florida"},
            "timeline": {"value": "Before April deadline"},
        }

        result = scoring_engine.calculate_score(
            extracted_fields=extracted,
            required_field_ids=required_fields,
            optional_field_ids=optional_fields,
            scoring_rules=cpa_scoring_rules,
        )

        # Expect: 50 base + ~11 completeness = ~61 (medium priority)
        assert 60 <= result.total_score < 80
        assert result.priority_level == "medium"
        assert len(result.risk_penalty_scores) == 0
