"""seed_cpa_lead_capture_template

Revision ID: 7df6a751b3c0
Revises: 346f0e7a1fad
Create Date: 2026-01-25 04:39:50.515445

Seeds the base "CPA Lead Capture" template for enterprise users.

This template provides a minimal starting point that CPA firms can customize:
- 4 required fields (contact info + service need)
- 3 optional fields (state, timeline, referral)
- Basic scoring (50 base + completeness + urgency + referral)
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7df6a751b3c0'
down_revision: Union[str, Sequence[str], None] = '346f0e7a1fad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Seed base CPA Lead Capture template."""

    # Define base template configuration
    workflow_config = {
        "required_fields": [
            {
                "field_id": "contact_name",
                "field_type": "text",
                "label": "Full name",
                "clarifying_question": "What's your name?",
            },
            {
                "field_id": "contact_email",
                "field_type": "email",
                "label": "Email address",
                "clarifying_question": "What's the best email to reach you at?",
            },
            {
                "field_id": "contact_phone",
                "field_type": "phone",
                "label": "Phone number",
                "clarifying_question": "And a phone number in case we need to call?",
            },
            {
                "field_id": "service_need",
                "field_type": "text",
                "label": "Service needed",
                "description": "What accounting or tax services are you looking for?",
            },
        ],
        "optional_fields": [
            {
                "field_id": "state",
                "field_type": "text",
                "label": "State",
                "description": "State where you or your business is located",
            },
            {
                "field_id": "timeline",
                "field_type": "choice",
                "label": "Timeline",
                "options": ["Immediate", "This month", "This quarter", "Just exploring"],
            },
            {
                "field_id": "referral_source",
                "field_type": "text",
                "label": "How did you hear about us?",
            },
        ],
        "inference_rules": {
            "contact_name": "Extract full name from introduction or signature",
            "state": "Extract from location mentions. If city mentioned, infer state.",
            "timeline": "Infer from urgency cues: 'ASAP', 'before deadline' → Immediate",
        },
        "extraction_strategy": {
            "opening_question": "Thanks for reaching out! I'd love to learn more about what you're looking for. What brings you here today?",
            "max_clarifying_questions": 5,
            "confirmation_required": True,
            "confidence_threshold": 0.8,
        },
    }

    output_template = {
        "format": "lead_summary",
        "sections": ["profile", "need", "score", "follow_up_questions"],
        "scoring_rules": {
            "base_score": 50,
            "field_completeness_weight": 20,
            "quality_signals": [
                {
                    "signal_id": "urgent_timeline",
                    "points": 10,
                    "condition": {"field": "timeline", "operator": "equals", "value": "Immediate"},
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
                }
            ],
        },
        "follow_up_rules": [],
        "max_follow_up_questions": 4,
    }

    # Insert template using raw SQL with bound parameters
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
        INSERT INTO workflow_templates (
            template_key,
            template_name,
            template_category,
            minimum_plan_tier_id,
            workflow_type,
            workflow_config,
            output_template,
            description,
            workflow_objective,
            tags,
            version,
            is_active,
            created_at,
            updated_at
        ) VALUES (
            :template_key,
            :template_name,
            :template_category,
            :minimum_plan_tier_id,
            :workflow_type,
            CAST(:workflow_config AS jsonb),
            CAST(:output_template AS jsonb),
            :description,
            :workflow_objective,
            STRING_TO_ARRAY(:tags, ','),
            :version,
            :is_active,
            NOW(),
            NOW()
        )
        ON CONFLICT (template_key) DO NOTHING;
        """
        ),
        {
            "template_key": "cpa_lead_capture",
            "template_name": "CPA Lead Capture",
            "template_category": "cpa",
            "minimum_plan_tier_id": 3,  # enterprise tier
            "workflow_type": "conversational",
            "workflow_config": json.dumps(workflow_config),
            "output_template": json.dumps(output_template),
            "description": "A conversational workflow for qualifying potential CPA clients. Captures basic contact information and service needs. Customize to add fields specific to your practice.",
            "workflow_objective": "Qualify potential CPA clients by naturally gathering their contact information and understanding their accounting or tax service needs. Ask conversational questions to capture required fields (name, email, phone, service needed) and optional context (state, timeline, referral source). Confirm all information before completing the lead capture.",
            "tags": "cpa,tax,accounting,lead-capture",
            "version": 1,
            "is_active": True,
        },
    )


def downgrade() -> None:
    """Remove base CPA Lead Capture template."""
    op.execute(
        sa.text("DELETE FROM workflow_templates WHERE template_key = 'cpa_lead_capture';")
    )
