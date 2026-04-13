"""
CPA Lead Capture Workflow Fixtures

Based on actual workflow configuration from database:
- persona_workflows table, id: 368d263a-3ec1-49bb-b6d2-8825ddf61330
"""

# Required fields for CPA lead capture
CPA_REQUIRED_FIELDS = [
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
        "field_id": "service_need",
        "label": "Service needed",
        "field_type": "text",
        "description": "What accounting or tax services are you looking for?",
    },
]

# Optional fields for additional context
CPA_OPTIONAL_FIELDS = [
    {
        "field_id": "state",
        "label": "State",
        "field_type": "text",
        "description": "State where you or your business is located",
    },
    {
        "field_id": "timeline",
        "label": "Timeline",
        "field_type": "choice",
        "options": ["Immediate", "This month", "This quarter", "Just exploring"],
    },
    {
        "field_id": "referral_source",
        "label": "How did you hear about us?",
        "field_type": "text",
    },
]

# Inference rules for field extraction
CPA_INFERENCE_RULES = {
    "state": "Extract from location mentions. If city mentioned, infer state.",
    "timeline": "Infer from urgency cues: 'ASAP', 'before deadline' → Immediate",
    "contact_name": "Extract full name from introduction or signature",
}

# CPA-specific advice redirect patterns
# These patterns detect when users ask for tax/accounting advice
# that should be redirected to the CPA rather than answered by the AI
CPA_ADVICE_PATTERNS = [
    # Entity/filing questions
    "should i file as",
    "should i be an",
    "should i form an",
    "llc or s-corp",
    "s-corp or llc",
    "s-corp or c-corp",
    "sole proprietor or llc",
    "which entity",
    "what entity should",
    "best entity for",
    # Deadline questions
    "what's the deadline",
    "when is the deadline",
    "when do i need to file",
    "when should i file",
    "is it too late to",
    # Tax liability questions
    "how much will i owe",
    "how much tax",
    "what will my tax be",
    "estimate my tax",
    "calculate my tax",
    # Deduction questions
    "can i deduct",
    "is this deductible",
    "deductible?",
    "can i write off",
    "should i deduct",
    "what can i deduct",
    "what deductions",
    # FBAR/Foreign questions
    "do i need to file fbar",
    "do i need fbar",
    "should i file fbar",
    "am i required to",
    # Compliance questions
    "do i need to",
    "am i supposed to",
    "is it required",
    "do i have to report",
    "should i report",
    # Strategy questions
    "is it better to",
    "would it be better",
    "what's the best way to",
    "how can i reduce",
    "how do i minimize",
    "tax strategy",
    "tax planning",
]

# Extraction strategy configuration
CPA_EXTRACTION_STRATEGY = {
    "opening_question": "Thanks for reaching out! I'd love to learn more about what you're looking for. What brings you here today?",
    "confidence_threshold": 0.8,
    "confirmation_required": True,
    "max_clarifying_questions": 5,
    # Advice redirect configuration (liability protection)
    "advice_redirect": {
        "enabled": True,
        "domain": "cpa",
        "patterns": CPA_ADVICE_PATTERNS,
        "redirect_message": (
            "That's a great question for {persona_name} to discuss with you directly. "
            "Let me make sure they have your contact info so they can give you "
            "personalized guidance on that."
        ),
    },
}

# Output template with scoring rules
CPA_OUTPUT_TEMPLATE = {
    "format": "lead_summary",
    "sections": ["profile", "need", "score", "follow_up_questions"],
    "scoring_rules": {
        "base_score": 50,
        "field_completeness_weight": 20,
        "quality_signals": [
            {
                "signal_id": "urgent_timeline",
                "points": 10,
                "condition": {
                    "field": "timeline",
                    "operator": "equals",
                    "value": "Immediate",
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
            }
        ],
    },
    "max_follow_up_questions": 4,
}

# Complete workflow data (as passed to agent)
CPA_WORKFLOW_DATA = {
    "workflow_id": "368d263a-3ec1-49bb-b6d2-8825ddf61330",
    "title": "CPA Lead Capture",
    "workflow_type": "conversational",
    "opening_message": None,
    "workflow_objective": (
        "Qualify potential CPA clients by naturally gathering their contact information "
        "and understanding their accounting or tax service needs. Ask conversational questions "
        "to capture required fields (name, email, phone, service needed) and optional context "
        "(state, timeline, referral source). Confirm all information before completing the lead capture."
    ),
    "trigger_config": {
        "promotion_mode": "proactive",
        "max_attempts": 3,
        "cooldown_turns": 5,
    },
    "required_fields": CPA_REQUIRED_FIELDS,
    "optional_fields": CPA_OPTIONAL_FIELDS,
    "extraction_strategy": CPA_EXTRACTION_STRATEGY,
    "output_template": CPA_OUTPUT_TEMPLATE,
    "result_config": {},
}

# Fake persona info for testing
FAKE_PERSONA_INFO = {
    "id": "e99721c3-c2cd-434f-a00b-fd1aa98a9e6f",
    "name": "Test CPA Expert",
    "role": "Certified Public Accountant",
    "persona_name": "test-cpa-expert",
    "voice_id": None,
    "calendar_url": None,
    "email_capture_enabled": False,
}

# Fake persona prompt for testing
FAKE_PERSONA_PROMPT = {
    "example_prompt": (
        "You are Test CPA Expert, a Certified Public Accountant. "
        "You help clients with tax preparation, bookkeeping, and financial planning. "
        "Be friendly, professional, and helpful."
    ),
    "introduction": "I'm a CPA with expertise in small business taxes.",
    "thinking_style": "analytical",
    "communication_style": "professional but approachable",
}


# Alternative workflow configurations for testing variations
# These can be used to test different CPA scenarios

CPA_WORKFLOW_MINIMAL = {
    **CPA_WORKFLOW_DATA,
    "workflow_id": "minimal-cpa-workflow",
    "title": "Minimal CPA Lead",
    "required_fields": [
        {"field_id": "contact_name", "label": "Name", "field_type": "text"},
        {"field_id": "contact_email", "label": "Email", "field_type": "email"},
    ],
    "optional_fields": [],
}

CPA_WORKFLOW_EXTENDED = {
    **CPA_WORKFLOW_DATA,
    "workflow_id": "extended-cpa-workflow",
    "title": "Extended CPA Lead",
    "required_fields": [
        *CPA_REQUIRED_FIELDS,
        {
            "field_id": "business_name",
            "label": "Business name",
            "field_type": "text",
        },
        {
            "field_id": "entity_type",
            "label": "Entity type",
            "field_type": "choice",
            "options": ["Sole Proprietor", "LLC", "S-Corp", "C-Corp", "Partnership"],
        },
    ],
    "optional_fields": [
        *CPA_OPTIONAL_FIELDS,
        {
            "field_id": "annual_revenue",
            "label": "Annual revenue range",
            "field_type": "choice",
            "options": ["Under $100K", "$100K-$500K", "$500K-$1M", "$1M-$5M", "Over $5M"],
        },
    ],
}
