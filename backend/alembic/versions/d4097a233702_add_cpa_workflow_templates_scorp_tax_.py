"""add_cpa_workflow_templates_scorp_tax_bookkeeping

Revision ID: d4097a233702
Revises: 64cd7502f03f
Create Date: 2026-01-30 22:54:02.902777

Adds 3 new CPA/Finance workflow templates:
1. S-Corp Election Consultation - Business owners considering S-Corp status
2. Tax Season Intake - Individual/business tax prep during busy season
3. Bookkeeping Services Inquiry - Ongoing monthly bookkeeping needs

"""

import json
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4097a233702"
down_revision: Union[str, Sequence[str], None] = "64cd7502f03f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =============================================================================
# Template 1: S-Corp Election Consultation
# =============================================================================
SCORP_TEMPLATE = {
    "template_key": "scorp_election_consultation",
    "template_name": "S-Corp Election Consultation",
    "template_category": "cpa",
    "minimum_plan_tier_id": 3,  # Enterprise
    "workflow_type": "conversational",
    "description": "Qualify business owners considering S-Corp election for tax savings. "
    "Capture business details, current structure, and revenue to assess S-Corp fit.",
    "workflow_objective": "Qualify business owners considering S-Corp election by gathering their "
    "contact information, current business structure, and key financial details. Ask conversational "
    "questions to capture required fields (name, email, phone, business type, current entity, annual revenue) "
    "and optional context (state, employee count, timeline). Confirm all information before completing.",
    "workflow_config": json.dumps(
        {
            "required_fields": [
                {
                    "field_id": "contact_name",
                    "label": "Full name",
                    "field_type": "text",
                    "clarifying_question": "What's your name?",
                },
                {
                    "field_id": "contact_email",
                    "label": "Email address",
                    "field_type": "email",
                    "clarifying_question": "What's the best email to reach you at?",
                },
                {
                    "field_id": "contact_phone",
                    "label": "Phone number",
                    "field_type": "phone",
                    "clarifying_question": "And a phone number in case we need to call?",
                },
                {
                    "field_id": "business_type",
                    "label": "Type of business",
                    "field_type": "text",
                    "description": "What industry or type of business do you operate?",
                    "clarifying_question": "What type of business do you have?",
                },
                {
                    "field_id": "current_entity",
                    "label": "Current entity structure",
                    "field_type": "choice",
                    "options": [
                        "Sole Proprietorship",
                        "Single-Member LLC",
                        "Multi-Member LLC",
                        "Partnership",
                        "C-Corp",
                        "Other",
                    ],
                    "clarifying_question": "How is your business currently structured?",
                },
                {
                    "field_id": "annual_revenue",
                    "label": "Annual revenue range",
                    "field_type": "choice",
                    "options": [
                        "Under $50K",
                        "$50K - $100K",
                        "$100K - $250K",
                        "$250K - $500K",
                        "$500K - $1M",
                        "Over $1M",
                    ],
                    "clarifying_question": "Roughly what's your annual revenue?",
                },
            ],
            "optional_fields": [
                {
                    "field_id": "state",
                    "label": "Business state",
                    "field_type": "text",
                    "description": "State where your business is registered",
                },
                {
                    "field_id": "employee_count",
                    "label": "Number of employees",
                    "field_type": "choice",
                    "options": ["Just me", "2-5", "6-10", "11-25", "25+"],
                },
                {
                    "field_id": "timeline",
                    "label": "Timeline",
                    "field_type": "choice",
                    "options": [
                        "ASAP - before next tax year",
                        "This quarter",
                        "Within 6 months",
                        "Just exploring",
                    ],
                },
                {
                    "field_id": "referral_source",
                    "label": "How did you hear about us?",
                    "field_type": "text",
                },
            ],
            "extraction_strategy": {
                "tone": "consultative",
                "confirmation_required": True,
                "max_clarifying_questions": 5,
            },
            "inference_rules": {
                "contact_name": "Extract full name from introduction or signature",
                "state": "Extract from location mentions or business address",
                "timeline": "Infer from urgency cues: 'before tax season' → ASAP",
                "annual_revenue": "Infer from context clues about business size",
            },
        }
    ),
    "output_template": json.dumps(
        {
            "format": "lead_summary",
            "sections": ["profile", "business_details", "scorp_fit", "follow_up_questions"],
            "scoring_rules": {
                "base_score": 50,
                "field_completeness_weight": 20,
                "quality_signals": [
                    {
                        "signal_id": "high_revenue",
                        "points": 15,
                        "condition": {
                            "field": "annual_revenue",
                            "operator": "in",
                            "value": ["$100K - $250K", "$250K - $500K", "$500K - $1M", "Over $1M"],
                        },
                    },
                    {
                        "signal_id": "llc_structure",
                        "points": 10,
                        "condition": {
                            "field": "current_entity",
                            "operator": "in",
                            "value": ["Single-Member LLC", "Multi-Member LLC"],
                        },
                    },
                    {
                        "signal_id": "urgent_timeline",
                        "points": 10,
                        "condition": {
                            "field": "timeline",
                            "operator": "equals",
                            "value": "ASAP - before next tax year",
                        },
                    },
                    {
                        "signal_id": "has_referral",
                        "points": 5,
                        "condition": {"field": "referral_source", "operator": "exists"},
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
                    {
                        "penalty_id": "low_revenue",
                        "points": -10,
                        "condition": {
                            "field": "annual_revenue",
                            "operator": "in",
                            "value": ["Under $50K", "$50K - $100K"],
                        },
                    },
                ],
            },
            "follow_up_rules": [],
            "max_follow_up_questions": 4,
        }
    ),
    "tags": ["cpa", "s-corp", "entity-election", "tax-savings", "business"],
}


# =============================================================================
# Template 2: Tax Season Intake
# =============================================================================
TAX_SEASON_TEMPLATE = {
    "template_key": "tax_season_intake",
    "template_name": "Tax Season Intake",
    "template_category": "cpa",
    "minimum_plan_tier_id": 3,  # Enterprise
    "workflow_type": "conversational",
    "description": "Streamline tax season client intake. Capture contact info, filing type, "
    "and key tax situations to triage and prioritize during busy season.",
    "workflow_objective": "Efficiently intake potential tax clients during busy season by gathering "
    "their contact information and understanding their tax filing needs. Ask conversational questions "
    "to capture required fields (name, email, phone, filing type, tax year) and optional context "
    "(has W2/1099, self-employed, state, deadline urgency). Confirm all information before completing.",
    "workflow_config": json.dumps(
        {
            "required_fields": [
                {
                    "field_id": "contact_name",
                    "label": "Full name",
                    "field_type": "text",
                    "clarifying_question": "What's your name?",
                },
                {
                    "field_id": "contact_email",
                    "label": "Email address",
                    "field_type": "email",
                    "clarifying_question": "What's the best email to reach you at?",
                },
                {
                    "field_id": "contact_phone",
                    "label": "Phone number",
                    "field_type": "phone",
                    "clarifying_question": "And a phone number in case we need to call?",
                },
                {
                    "field_id": "filing_type",
                    "label": "Filing type",
                    "field_type": "choice",
                    "options": [
                        "Individual (Personal)",
                        "Business (Schedule C/Self-employed)",
                        "Business (LLC/S-Corp/C-Corp)",
                        "Both Personal and Business",
                    ],
                    "clarifying_question": "Are you looking to file personal taxes, business taxes, or both?",
                },
                {
                    "field_id": "tax_year",
                    "label": "Tax year",
                    "field_type": "choice",
                    "options": ["Current year", "Prior year (amendment)", "Multiple years"],
                    "clarifying_question": "Is this for the current tax year or a prior year?",
                },
            ],
            "optional_fields": [
                {
                    "field_id": "income_sources",
                    "label": "Income sources",
                    "field_type": "multi_choice",
                    "options": [
                        "W2 Employment",
                        "1099 Contractor",
                        "Self-employed/Business",
                        "Investments",
                        "Rental Income",
                        "Other",
                    ],
                },
                {
                    "field_id": "state",
                    "label": "State",
                    "field_type": "text",
                    "description": "State for tax filing",
                },
                {
                    "field_id": "deadline_urgency",
                    "label": "Deadline urgency",
                    "field_type": "choice",
                    "options": [
                        "Standard deadline",
                        "Need extension",
                        "Already extended - due soon",
                        "Past due - need to file ASAP",
                    ],
                },
                {
                    "field_id": "referral_source",
                    "label": "How did you hear about us?",
                    "field_type": "text",
                },
            ],
            "extraction_strategy": {
                "tone": "efficient",
                "confirmation_required": True,
                "max_clarifying_questions": 4,
            },
            "inference_rules": {
                "contact_name": "Extract full name from introduction or signature",
                "state": "Extract from location mentions",
                "deadline_urgency": "Infer from mentions of 'deadline', 'late', 'extension', 'ASAP'",
                "filing_type": "Infer from mentions of business, W2, 1099, self-employed",
            },
        }
    ),
    "output_template": json.dumps(
        {
            "format": "lead_summary",
            "sections": ["profile", "tax_situation", "urgency", "follow_up_questions"],
            "scoring_rules": {
                "base_score": 50,
                "field_completeness_weight": 20,
                "quality_signals": [
                    {
                        "signal_id": "business_filing",
                        "points": 15,
                        "condition": {
                            "field": "filing_type",
                            "operator": "in",
                            "value": [
                                "Business (Schedule C/Self-employed)",
                                "Business (LLC/S-Corp/C-Corp)",
                                "Both Personal and Business",
                            ],
                        },
                    },
                    {
                        "signal_id": "urgent_deadline",
                        "points": 10,
                        "condition": {
                            "field": "deadline_urgency",
                            "operator": "in",
                            "value": [
                                "Already extended - due soon",
                                "Past due - need to file ASAP",
                            ],
                        },
                    },
                    {
                        "signal_id": "multiple_years",
                        "points": 10,
                        "condition": {
                            "field": "tax_year",
                            "operator": "equals",
                            "value": "Multiple years",
                        },
                    },
                    {
                        "signal_id": "has_referral",
                        "points": 5,
                        "condition": {"field": "referral_source", "operator": "exists"},
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
            "follow_up_rules": [],
            "max_follow_up_questions": 4,
        }
    ),
    "tags": ["cpa", "tax-season", "tax-prep", "individual", "business"],
}


# =============================================================================
# Template 3: Bookkeeping Services Inquiry
# =============================================================================
BOOKKEEPING_TEMPLATE = {
    "template_key": "bookkeeping_services",
    "template_name": "Bookkeeping Services Inquiry",
    "template_category": "cpa",
    "minimum_plan_tier_id": 3,  # Enterprise
    "workflow_type": "conversational",
    "description": "Qualify businesses seeking ongoing bookkeeping services. Capture business details, "
    "current bookkeeping situation, and transaction volume to scope engagement.",
    "workflow_objective": "Qualify businesses seeking bookkeeping services by gathering their contact "
    "information and understanding their bookkeeping needs. Ask conversational questions to capture "
    "required fields (name, email, phone, business type, current situation) and optional context "
    "(monthly transactions, software used, pain points, timeline). Confirm all information before completing.",
    "workflow_config": json.dumps(
        {
            "required_fields": [
                {
                    "field_id": "contact_name",
                    "label": "Full name",
                    "field_type": "text",
                    "clarifying_question": "What's your name?",
                },
                {
                    "field_id": "contact_email",
                    "label": "Email address",
                    "field_type": "email",
                    "clarifying_question": "What's the best email to reach you at?",
                },
                {
                    "field_id": "contact_phone",
                    "label": "Phone number",
                    "field_type": "phone",
                    "clarifying_question": "And a phone number in case we need to call?",
                },
                {
                    "field_id": "business_type",
                    "label": "Type of business",
                    "field_type": "text",
                    "description": "What industry or type of business do you operate?",
                    "clarifying_question": "What type of business do you have?",
                },
                {
                    "field_id": "current_situation",
                    "label": "Current bookkeeping situation",
                    "field_type": "choice",
                    "options": [
                        "No bookkeeping - need to start",
                        "Doing it myself - need help",
                        "Have someone - looking to switch",
                        "Backlog - need cleanup",
                    ],
                    "clarifying_question": "How are you currently handling your bookkeeping?",
                },
            ],
            "optional_fields": [
                {
                    "field_id": "monthly_transactions",
                    "label": "Monthly transaction volume",
                    "field_type": "choice",
                    "options": ["Under 50", "50-150", "150-300", "300-500", "500+"],
                },
                {
                    "field_id": "accounting_software",
                    "label": "Accounting software",
                    "field_type": "choice",
                    "options": [
                        "QuickBooks Online",
                        "QuickBooks Desktop",
                        "Xero",
                        "FreshBooks",
                        "Wave",
                        "None/Spreadsheets",
                        "Other",
                    ],
                },
                {
                    "field_id": "pain_points",
                    "label": "Main pain points",
                    "field_type": "text",
                    "description": "What's the biggest challenge with your current bookkeeping?",
                },
                {
                    "field_id": "timeline",
                    "label": "Timeline",
                    "field_type": "choice",
                    "options": [
                        "Immediately",
                        "Within 2 weeks",
                        "This month",
                        "Just exploring",
                    ],
                },
                {
                    "field_id": "referral_source",
                    "label": "How did you hear about us?",
                    "field_type": "text",
                },
            ],
            "extraction_strategy": {
                "tone": "concierge",
                "confirmation_required": True,
                "max_clarifying_questions": 5,
            },
            "inference_rules": {
                "contact_name": "Extract full name from introduction or signature",
                "current_situation": "Infer from context about their current setup",
                "timeline": "Infer from urgency cues",
                "monthly_transactions": "Infer from business size or mentions of volume",
            },
        }
    ),
    "output_template": json.dumps(
        {
            "format": "lead_summary",
            "sections": ["profile", "business_details", "bookkeeping_scope", "follow_up_questions"],
            "scoring_rules": {
                "base_score": 50,
                "field_completeness_weight": 20,
                "quality_signals": [
                    {
                        "signal_id": "high_volume",
                        "points": 15,
                        "condition": {
                            "field": "monthly_transactions",
                            "operator": "in",
                            "value": ["150-300", "300-500", "500+"],
                        },
                    },
                    {
                        "signal_id": "needs_cleanup",
                        "points": 10,
                        "condition": {
                            "field": "current_situation",
                            "operator": "equals",
                            "value": "Backlog - need cleanup",
                        },
                    },
                    {
                        "signal_id": "urgent_timeline",
                        "points": 10,
                        "condition": {
                            "field": "timeline",
                            "operator": "in",
                            "value": ["Immediately", "Within 2 weeks"],
                        },
                    },
                    {
                        "signal_id": "has_software",
                        "points": 5,
                        "condition": {
                            "field": "accounting_software",
                            "operator": "in",
                            "value": ["QuickBooks Online", "QuickBooks Desktop", "Xero"],
                        },
                    },
                    {
                        "signal_id": "has_referral",
                        "points": 5,
                        "condition": {"field": "referral_source", "operator": "exists"},
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
                    {
                        "penalty_id": "low_volume",
                        "points": -5,
                        "condition": {
                            "field": "monthly_transactions",
                            "operator": "equals",
                            "value": "Under 50",
                        },
                    },
                ],
            },
            "follow_up_rules": [],
            "max_follow_up_questions": 4,
        }
    ),
    "tags": ["cpa", "bookkeeping", "monthly", "recurring", "small-business"],
}


def escape_sql_string(s: str) -> str:
    """Escape single quotes for SQL by doubling them."""
    return s.replace("'", "''")


def upgrade() -> None:
    """Add 3 new CPA workflow templates."""

    # Insert all templates
    for template in [SCORP_TEMPLATE, TAX_SEASON_TEMPLATE, BOOKKEEPING_TEMPLATE]:
        # Escape all string values for SQL
        workflow_config_escaped = escape_sql_string(template["workflow_config"])
        output_template_escaped = escape_sql_string(template["output_template"])
        description_escaped = escape_sql_string(template["description"])
        objective_escaped = escape_sql_string(template["workflow_objective"])

        # Build tags array string
        tags_str = ", ".join(f"'{tag}'" for tag in template["tags"])

        op.execute(
            f"""
            INSERT INTO workflow_templates (
                template_key,
                template_name,
                template_category,
                minimum_plan_tier_id,
                workflow_type,
                description,
                workflow_objective,
                workflow_config,
                output_template,
                tags,
                is_active
            ) VALUES (
                '{template["template_key"]}',
                '{template["template_name"]}',
                '{template["template_category"]}',
                {template["minimum_plan_tier_id"]},
                '{template["workflow_type"]}',
                '{description_escaped}',
                '{objective_escaped}',
                '{workflow_config_escaped}'::jsonb,
                '{output_template_escaped}'::jsonb,
                ARRAY[{tags_str}]::text[],
                true
            )
            ON CONFLICT (template_key) DO NOTHING;
            """
        )


def downgrade() -> None:
    """Remove the 3 CPA workflow templates."""

    op.execute(
        """
        DELETE FROM workflow_templates
        WHERE template_key IN (
            'scorp_election_consultation',
            'tax_season_intake',
            'bookkeeping_services'
        );
        """
    )
