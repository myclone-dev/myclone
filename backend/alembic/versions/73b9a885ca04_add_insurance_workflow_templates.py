"""add_insurance_workflow_templates

Revision ID: 73b9a885ca04
Revises: d4097a233702
Create Date: 2026-01-31 01:51:00.979027

Adds 4 new Insurance workflow templates:
1. Auto Insurance - Capture driver and vehicle info for auto insurance quotes
2. Home Insurance - Capture property details for homeowners/renters insurance
3. Business Insurance - Capture business details for commercial insurance
4. Pet Insurance - Capture pet details for pet insurance coverage

"""

import json
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "73b9a885ca04"
down_revision: Union[str, Sequence[str], None] = "d4097a233702"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# =============================================================================
# Template 1: Auto Insurance
# =============================================================================
AUTO_INSURANCE_TEMPLATE = {
    "template_key": "auto_insurance",
    "template_name": "Auto Insurance",
    "template_category": "insurance",
    "minimum_plan_tier_id": 3,  # Enterprise
    "workflow_type": "conversational",
    "description": "Capture driver information and vehicle details for auto insurance quotes. "
    "Gather driving history, coverage needs, and timeline to qualify leads.",
    "workflow_objective": "Qualify potential auto insurance clients by gathering their contact "
    "information, vehicle details, and coverage needs. Ask conversational questions to capture "
    "required fields (name, email, phone, vehicle year/make/model, current coverage status) and "
    "optional context (driving history, multi-car discount, timeline). Confirm all information before completing.",
    "workflow_config": json.dumps(
        {
            "required_fields": [
                {
                    "field_id": "contact_name",
                    "label": "Full name",
                    "field_type": "text",
                    "clarifying_question": "What is your name?",
                },
                {
                    "field_id": "contact_email",
                    "label": "Email address",
                    "field_type": "email",
                    "clarifying_question": "What is the best email to reach you at?",
                },
                {
                    "field_id": "contact_phone",
                    "label": "Phone number",
                    "field_type": "phone",
                    "clarifying_question": "And a phone number in case we need to call?",
                },
                {
                    "field_id": "vehicle_info",
                    "label": "Vehicle information",
                    "field_type": "text",
                    "description": "Year, make, and model of the vehicle",
                    "clarifying_question": "What vehicle do you need insured? Year, make, and model?",
                },
                {
                    "field_id": "current_coverage",
                    "label": "Current coverage status",
                    "field_type": "choice",
                    "options": [
                        "Currently insured - looking to switch",
                        "Coverage lapsing soon",
                        "No current coverage",
                        "Adding a new vehicle",
                    ],
                    "clarifying_question": "Do you currently have auto insurance or are you looking for new coverage?",
                },
            ],
            "optional_fields": [
                {
                    "field_id": "num_vehicles",
                    "label": "Number of vehicles",
                    "field_type": "choice",
                    "options": ["1", "2", "3", "4+"],
                },
                {
                    "field_id": "num_drivers",
                    "label": "Number of drivers",
                    "field_type": "choice",
                    "options": ["1", "2", "3", "4+"],
                },
                {
                    "field_id": "driving_history",
                    "label": "Driving history",
                    "field_type": "choice",
                    "options": [
                        "Clean record",
                        "Minor violations",
                        "At-fault accident in past 3 years",
                        "Multiple incidents",
                    ],
                },
                {
                    "field_id": "zip_code",
                    "label": "ZIP code",
                    "field_type": "text",
                    "description": "ZIP code for rate calculation",
                },
                {
                    "field_id": "timeline",
                    "label": "Timeline",
                    "field_type": "choice",
                    "options": [
                        "Immediately",
                        "Within a week",
                        "Within 30 days",
                        "Just comparing rates",
                    ],
                },
                {
                    "field_id": "referral_source",
                    "label": "How did you hear about us?",
                    "field_type": "text",
                },
            ],
            "extraction_strategy": {
                "tone": "professional",
                "confirmation_required": True,
                "max_clarifying_questions": 5,
            },
            "inference_rules": {
                "contact_name": "Extract full name from introduction or signature",
                "zip_code": "Extract from location or address mentions",
                "timeline": "Infer from urgency cues: expiring soon -> Immediately",
                "current_coverage": "Infer from context about their situation",
            },
        }
    ),
    "output_template": json.dumps(
        {
            "format": "lead_summary",
            "sections": ["profile", "vehicle_details", "coverage_needs", "follow_up_questions"],
            "scoring_rules": {
                "base_score": 50,
                "field_completeness_weight": 20,
                "quality_signals": [
                    {
                        "signal_id": "multiple_vehicles",
                        "points": 15,
                        "condition": {
                            "field": "num_vehicles",
                            "operator": "in",
                            "value": ["2", "3", "4+"],
                        },
                    },
                    {
                        "signal_id": "clean_driving",
                        "points": 10,
                        "condition": {
                            "field": "driving_history",
                            "operator": "equals",
                            "value": "Clean record",
                        },
                    },
                    {
                        "signal_id": "urgent_timeline",
                        "points": 10,
                        "condition": {
                            "field": "timeline",
                            "operator": "in",
                            "value": ["Immediately", "Within a week"],
                        },
                    },
                    {
                        "signal_id": "switching_coverage",
                        "points": 5,
                        "condition": {
                            "field": "current_coverage",
                            "operator": "equals",
                            "value": "Currently insured - looking to switch",
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
                        "penalty_id": "poor_driving_history",
                        "points": -10,
                        "condition": {
                            "field": "driving_history",
                            "operator": "in",
                            "value": ["At-fault accident in past 3 years", "Multiple incidents"],
                        },
                    },
                ],
            },
            "follow_up_rules": [],
            "max_follow_up_questions": 4,
        }
    ),
    "tags": ["insurance", "auto", "car", "vehicle", "quote"],
}


# =============================================================================
# Template 2: Home Insurance
# =============================================================================
HOME_INSURANCE_TEMPLATE = {
    "template_key": "home_insurance",
    "template_name": "Home Insurance",
    "template_category": "insurance",
    "minimum_plan_tier_id": 3,  # Enterprise
    "workflow_type": "conversational",
    "description": "Capture property details and coverage needs for homeowners or renters insurance. "
    "Gather property type, value, and current coverage status to qualify leads.",
    "workflow_objective": "Qualify potential home insurance clients by gathering their contact "
    "information, property details, and coverage needs. Ask conversational questions to capture "
    "required fields (name, email, phone, property type, ownership status) and optional context "
    "(property value, current coverage, move-in date, timeline). Confirm all information before completing.",
    "workflow_config": json.dumps(
        {
            "required_fields": [
                {
                    "field_id": "contact_name",
                    "label": "Full name",
                    "field_type": "text",
                    "clarifying_question": "What is your name?",
                },
                {
                    "field_id": "contact_email",
                    "label": "Email address",
                    "field_type": "email",
                    "clarifying_question": "What is the best email to reach you at?",
                },
                {
                    "field_id": "contact_phone",
                    "label": "Phone number",
                    "field_type": "phone",
                    "clarifying_question": "And a phone number in case we need to call?",
                },
                {
                    "field_id": "property_type",
                    "label": "Property type",
                    "field_type": "choice",
                    "options": [
                        "Single-family home",
                        "Condo/Townhouse",
                        "Apartment (renter)",
                        "Multi-family property",
                        "Mobile home",
                    ],
                    "clarifying_question": "What type of property do you need to insure?",
                },
                {
                    "field_id": "ownership_status",
                    "label": "Ownership status",
                    "field_type": "choice",
                    "options": [
                        "Own - with mortgage",
                        "Own - paid off",
                        "Renting",
                        "Buying soon",
                    ],
                    "clarifying_question": "Do you own or rent this property?",
                },
            ],
            "optional_fields": [
                {
                    "field_id": "property_value",
                    "label": "Estimated property value",
                    "field_type": "choice",
                    "options": [
                        "Under $200K",
                        "$200K - $400K",
                        "$400K - $600K",
                        "$600K - $1M",
                        "Over $1M",
                    ],
                },
                {
                    "field_id": "zip_code",
                    "label": "Property ZIP code",
                    "field_type": "text",
                    "description": "ZIP code of the property",
                },
                {
                    "field_id": "current_coverage",
                    "label": "Current coverage status",
                    "field_type": "choice",
                    "options": [
                        "Currently insured - looking to switch",
                        "Coverage expiring soon",
                        "No current coverage",
                        "New purchase - need coverage",
                    ],
                },
                {
                    "field_id": "year_built",
                    "label": "Year built",
                    "field_type": "text",
                    "description": "Approximate year the property was built",
                },
                {
                    "field_id": "timeline",
                    "label": "Timeline",
                    "field_type": "choice",
                    "options": [
                        "Immediately - closing soon",
                        "Within 30 days",
                        "Within 60 days",
                        "Just exploring options",
                    ],
                },
                {
                    "field_id": "referral_source",
                    "label": "How did you hear about us?",
                    "field_type": "text",
                },
            ],
            "extraction_strategy": {
                "tone": "professional",
                "confirmation_required": True,
                "max_clarifying_questions": 5,
            },
            "inference_rules": {
                "contact_name": "Extract full name from introduction or signature",
                "zip_code": "Extract from address or location mentions",
                "property_type": "Infer from mentions of house, apartment, condo, etc.",
                "ownership_status": "Infer from context about buying, renting, owning",
            },
        }
    ),
    "output_template": json.dumps(
        {
            "format": "lead_summary",
            "sections": ["profile", "property_details", "coverage_needs", "follow_up_questions"],
            "scoring_rules": {
                "base_score": 50,
                "field_completeness_weight": 20,
                "quality_signals": [
                    {
                        "signal_id": "high_value_property",
                        "points": 15,
                        "condition": {
                            "field": "property_value",
                            "operator": "in",
                            "value": ["$400K - $600K", "$600K - $1M", "Over $1M"],
                        },
                    },
                    {
                        "signal_id": "homeowner",
                        "points": 10,
                        "condition": {
                            "field": "ownership_status",
                            "operator": "in",
                            "value": ["Own - with mortgage", "Own - paid off", "Buying soon"],
                        },
                    },
                    {
                        "signal_id": "urgent_timeline",
                        "points": 10,
                        "condition": {
                            "field": "timeline",
                            "operator": "in",
                            "value": ["Immediately - closing soon", "Within 30 days"],
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
    "tags": ["insurance", "home", "homeowners", "renters", "property"],
}


# =============================================================================
# Template 3: Business Insurance
# =============================================================================
BUSINESS_INSURANCE_TEMPLATE = {
    "template_key": "business_insurance",
    "template_name": "Business Insurance",
    "template_category": "insurance",
    "minimum_plan_tier_id": 3,  # Enterprise
    "workflow_type": "conversational",
    "description": "Capture business details and coverage needs for commercial insurance. "
    "Gather business type, size, and specific coverage requirements to qualify leads.",
    "workflow_objective": "Qualify potential business insurance clients by gathering their contact "
    "information, business details, and coverage needs. Ask conversational questions to capture "
    "required fields (name, email, phone, business type, number of employees) and optional context "
    "(annual revenue, current coverage, specific needs, timeline). Confirm all information before completing.",
    "workflow_config": json.dumps(
        {
            "required_fields": [
                {
                    "field_id": "contact_name",
                    "label": "Full name",
                    "field_type": "text",
                    "clarifying_question": "What is your name?",
                },
                {
                    "field_id": "contact_email",
                    "label": "Email address",
                    "field_type": "email",
                    "clarifying_question": "What is the best email to reach you at?",
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
                    "description": "Industry or type of business",
                    "clarifying_question": "What type of business do you operate?",
                },
                {
                    "field_id": "employee_count",
                    "label": "Number of employees",
                    "field_type": "choice",
                    "options": [
                        "Just me (sole proprietor)",
                        "2-10 employees",
                        "11-50 employees",
                        "51-100 employees",
                        "100+ employees",
                    ],
                    "clarifying_question": "How many employees does your business have?",
                },
            ],
            "optional_fields": [
                {
                    "field_id": "annual_revenue",
                    "label": "Annual revenue",
                    "field_type": "choice",
                    "options": [
                        "Under $100K",
                        "$100K - $500K",
                        "$500K - $1M",
                        "$1M - $5M",
                        "Over $5M",
                    ],
                },
                {
                    "field_id": "coverage_types",
                    "label": "Coverage types needed",
                    "field_type": "multi_choice",
                    "options": [
                        "General Liability",
                        "Professional Liability (E&O)",
                        "Workers Compensation",
                        "Commercial Property",
                        "Business Interruption",
                        "Cyber Liability",
                        "Commercial Auto",
                        "Not sure - need guidance",
                    ],
                },
                {
                    "field_id": "current_coverage",
                    "label": "Current coverage status",
                    "field_type": "choice",
                    "options": [
                        "Currently insured - looking to switch",
                        "Some coverage - need more",
                        "No current coverage",
                        "New business - first time",
                    ],
                },
                {
                    "field_id": "state",
                    "label": "Business state",
                    "field_type": "text",
                    "description": "Primary state of operation",
                },
                {
                    "field_id": "timeline",
                    "label": "Timeline",
                    "field_type": "choice",
                    "options": [
                        "Immediately",
                        "Within 30 days",
                        "Within 60 days",
                        "Just exploring options",
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
                "state": "Extract from location or address mentions",
                "employee_count": "Infer from mentions of team size or scale",
                "business_type": "Extract from description of what they do",
            },
        }
    ),
    "output_template": json.dumps(
        {
            "format": "lead_summary",
            "sections": ["profile", "business_details", "coverage_needs", "follow_up_questions"],
            "scoring_rules": {
                "base_score": 50,
                "field_completeness_weight": 20,
                "quality_signals": [
                    {
                        "signal_id": "larger_business",
                        "points": 15,
                        "condition": {
                            "field": "employee_count",
                            "operator": "in",
                            "value": ["11-50 employees", "51-100 employees", "100+ employees"],
                        },
                    },
                    {
                        "signal_id": "high_revenue",
                        "points": 15,
                        "condition": {
                            "field": "annual_revenue",
                            "operator": "in",
                            "value": ["$1M - $5M", "Over $5M"],
                        },
                    },
                    {
                        "signal_id": "urgent_timeline",
                        "points": 10,
                        "condition": {
                            "field": "timeline",
                            "operator": "in",
                            "value": ["Immediately", "Within 30 days"],
                        },
                    },
                    {
                        "signal_id": "multiple_coverage_needs",
                        "points": 10,
                        "condition": {
                            "field": "coverage_types",
                            "operator": "exists",
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
    "tags": ["insurance", "business", "commercial", "liability", "workers-comp"],
}


# =============================================================================
# Template 4: Pet Insurance
# =============================================================================
PET_INSURANCE_TEMPLATE = {
    "template_key": "pet_insurance",
    "template_name": "Pet Insurance",
    "template_category": "insurance",
    "minimum_plan_tier_id": 3,  # Enterprise
    "workflow_type": "conversational",
    "description": "Capture pet details and coverage needs for pet insurance quotes. "
    "Gather pet type, breed, age, and health history to qualify leads.",
    "workflow_objective": "Qualify potential pet insurance clients by gathering their contact "
    "information and pet details. Ask conversational questions to capture required fields "
    "(name, email, phone, pet type, pet name, pet age) and optional context (breed, health history, "
    "current coverage, timeline). Confirm all information before completing.",
    "workflow_config": json.dumps(
        {
            "required_fields": [
                {
                    "field_id": "contact_name",
                    "label": "Full name",
                    "field_type": "text",
                    "clarifying_question": "What is your name?",
                },
                {
                    "field_id": "contact_email",
                    "label": "Email address",
                    "field_type": "email",
                    "clarifying_question": "What is the best email to reach you at?",
                },
                {
                    "field_id": "contact_phone",
                    "label": "Phone number",
                    "field_type": "phone",
                    "clarifying_question": "And a phone number in case we need to call?",
                },
                {
                    "field_id": "pet_type",
                    "label": "Type of pet",
                    "field_type": "choice",
                    "options": ["Dog", "Cat", "Other"],
                    "clarifying_question": "What type of pet do you want to insure?",
                },
                {
                    "field_id": "pet_name",
                    "label": "Pet name",
                    "field_type": "text",
                    "clarifying_question": "What is your pet's name?",
                },
                {
                    "field_id": "pet_age",
                    "label": "Pet age",
                    "field_type": "choice",
                    "options": [
                        "Under 1 year",
                        "1-3 years",
                        "4-7 years",
                        "8-10 years",
                        "Over 10 years",
                    ],
                    "clarifying_question": "How old is your pet?",
                },
            ],
            "optional_fields": [
                {
                    "field_id": "breed",
                    "label": "Breed",
                    "field_type": "text",
                    "description": "Breed or mix of the pet",
                },
                {
                    "field_id": "health_status",
                    "label": "Current health status",
                    "field_type": "choice",
                    "options": [
                        "Healthy - no known issues",
                        "Minor conditions",
                        "Pre-existing conditions",
                        "Senior pet - age-related concerns",
                    ],
                },
                {
                    "field_id": "current_coverage",
                    "label": "Current coverage status",
                    "field_type": "choice",
                    "options": [
                        "Currently insured - looking to switch",
                        "No current coverage",
                        "New pet - first time",
                    ],
                },
                {
                    "field_id": "coverage_priority",
                    "label": "Coverage priority",
                    "field_type": "choice",
                    "options": [
                        "Accidents only",
                        "Accidents and illness",
                        "Comprehensive (including wellness)",
                        "Not sure - need guidance",
                    ],
                },
                {
                    "field_id": "zip_code",
                    "label": "ZIP code",
                    "field_type": "text",
                    "description": "ZIP code for rate calculation",
                },
                {
                    "field_id": "referral_source",
                    "label": "How did you hear about us?",
                    "field_type": "text",
                },
            ],
            "extraction_strategy": {
                "tone": "friendly",
                "confirmation_required": True,
                "max_clarifying_questions": 5,
            },
            "inference_rules": {
                "contact_name": "Extract full name from introduction or signature",
                "pet_type": "Infer from mentions of dog, cat, puppy, kitten, etc.",
                "pet_age": "Infer from mentions of puppy/kitten (under 1) or senior (8+)",
                "breed": "Extract from mentions of specific breeds",
            },
        }
    ),
    "output_template": json.dumps(
        {
            "format": "lead_summary",
            "sections": ["profile", "pet_details", "coverage_needs", "follow_up_questions"],
            "scoring_rules": {
                "base_score": 50,
                "field_completeness_weight": 20,
                "quality_signals": [
                    {
                        "signal_id": "young_pet",
                        "points": 15,
                        "condition": {
                            "field": "pet_age",
                            "operator": "in",
                            "value": ["Under 1 year", "1-3 years"],
                        },
                    },
                    {
                        "signal_id": "healthy_pet",
                        "points": 10,
                        "condition": {
                            "field": "health_status",
                            "operator": "equals",
                            "value": "Healthy - no known issues",
                        },
                    },
                    {
                        "signal_id": "comprehensive_coverage",
                        "points": 10,
                        "condition": {
                            "field": "coverage_priority",
                            "operator": "in",
                            "value": [
                                "Accidents and illness",
                                "Comprehensive (including wellness)",
                            ],
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
                        "penalty_id": "senior_pet",
                        "points": -5,
                        "condition": {
                            "field": "pet_age",
                            "operator": "equals",
                            "value": "Over 10 years",
                        },
                    },
                    {
                        "penalty_id": "pre_existing",
                        "points": -10,
                        "condition": {
                            "field": "health_status",
                            "operator": "equals",
                            "value": "Pre-existing conditions",
                        },
                    },
                ],
            },
            "follow_up_rules": [],
            "max_follow_up_questions": 4,
        }
    ),
    "tags": ["insurance", "pet", "dog", "cat", "veterinary"],
}


def escape_sql_string(s: str) -> str:
    """Escape single quotes for SQL by doubling them."""
    return s.replace("'", "''")


def upgrade() -> None:
    """Add 4 new Insurance workflow templates."""

    templates = [
        AUTO_INSURANCE_TEMPLATE,
        HOME_INSURANCE_TEMPLATE,
        BUSINESS_INSURANCE_TEMPLATE,
        PET_INSURANCE_TEMPLATE,
    ]

    for template in templates:
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
    """Remove the 4 Insurance workflow templates."""

    op.execute(
        """
        DELETE FROM workflow_templates
        WHERE template_key IN (
            'auto_insurance',
            'home_insurance',
            'business_insurance',
            'pet_insurance'
        );
        """
    )
