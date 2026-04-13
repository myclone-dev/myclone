# Workflow Enhancements

This document describes the conversational workflow enhancements implemented for lead capture workflows.

**Last Updated:** January 29, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Tone Controls](#1-tone-controls)
3. [Summary Templates](#2-summary-templates)
4. [No Redundant Questions](#3-no-redundant-questions)
5. [Config-Driven Scoring](#4-config-driven-scoring)
6. [Advice Redirect](#5-advice-redirect)
7. [Admin API Access](#6-admin-api-access)
8. [Schema Reference](#7-schema-reference)

---

## Overview

These enhancements improve the conversational lead capture workflow with:

- **Tone Controls** - Configurable conversation style (concierge, professional, casual, efficient)
- **Summary Templates** - Flexible lead summary formats (structured, synopsis, minimal, detailed)
- **No Redundant Questions** - Tracks asked fields to prevent repetitive questions
- **Config-Driven Scoring** - All scoring rules defined in workflow config (no hardcoded patterns)
- **Advice Redirect** - LLM-native handling of professional advice questions

### Architecture Note

These features use a **single-LLM architecture** where the main agent handles all interactions:
- Field extraction via `update_lead_field()` tool
- Confirmation/rejection detection via natural language understanding
- Advice redirect via system prompt instructions

This is simpler and more maintainable than a dual-LLM approach with separate extractor.

---

## 1. Tone Controls

### Overview

Configurable conversation tone affects how the bot phrases questions, acknowledgments, and confirmations.

### Available Tones

| Tone | Description | Use Case |
|------|-------------|----------|
| `concierge` | Warm, white-glove service | High-value clients, luxury services |
| `professional` | Friendly but efficient (default) | Most B2B services |
| `casual` | Relaxed, conversational | Startups, creative industries |
| `efficient` | Minimal, fast-paced | High-volume lead capture |

### Example Phrasing by Tone

| Component | Concierge | Professional | Efficient |
|-----------|-----------|--------------|-----------|
| Acknowledgment | "Wonderful, thank you so much!" | "Got it, thank you." | "Noted." |
| Question prefix | "May I ask" | "Could you tell me" | (direct) |
| Confirmation intro | "I just want to make sure I have everything correct —" | "Perfect! Just to confirm —" | "Confirming:" |

### Configuration

```json
{
  "extraction_strategy": {
    "tone": "concierge"
  }
}
```

### Implementation

**Service:** `livekit/services/workflow_tone_service.py` (~300 lines)

**Methods:**
- `get_acknowledgment()` - Returns tone-appropriate acknowledgment
- `format_question()` - Formats clarifying questions with tone prefix
- `get_confirmation_intro()` - Returns confirmation summary intro
- `get_completion_message()` - Returns workflow completion message

**Tests:** 12 unit tests in `TestToneControls`

---

## 2. Summary Templates

### Overview

The lead summary is what the **CPA/business owner** sees (in email, dashboard, CRM). Different clients want different formats.

### Available Templates

| Template | Description | Best For |
|----------|-------------|----------|
| `structured` | Key-value pairs with headers (default) | Most use cases |
| `synopsis` | Narrative paragraph format | Quick reading |
| `minimal` | Compact one-liner | Dashboard widgets |
| `detailed` | Structured + full score breakdown | Analysis/debugging |

### Example Outputs

**Structured (Default):**
```
LEAD SUMMARY
==================================================

CONTACT: Raj Patel
EMAIL: raj@email.com  
PHONE: 555-987-6543

SERVICE NEEDED: FBAR filing and 1040

==================================================
LEAD SCORE: 85/100 - HIGH PRIORITY
```

**Synopsis:**
```
Raj Patel (raj@email.com, 555-987-6543) is looking for FBAR filing and 1040.
Lead Score: 85/100 (High Priority)
```

**Minimal:**
```
Raj Patel - raj@email.com - 555-987-6543 - 85/100 High
```

**Detailed:**
```
LEAD SUMMARY
==================================================
[... structured content ...]

SCORE BREAKDOWN
==================================================
Base Score: 50
Field Completeness: +15
Quality Signals: +25 (foreign_accounts, urgent_timeline)
Risk Penalties: -5 (first_time_filer)
--------------------------------------------------
TOTAL: 85/100 - HIGH PRIORITY
```

### Configuration

```json
{
  "output_template": {
    "summary_template": "detailed",
    "include_score_breakdown": true
  }
}
```

### Implementation

**Service:** `livekit/services/workflow_summary_service.py` (~330 lines)

**Methods:**
- `format_summary()` - Main entry point, routes to appropriate template
- `_format_structured()` - Default format with headers
- `_format_synopsis()` - Narrative paragraph
- `_format_minimal()` - Compact one-liner
- `_format_detailed()` - Includes score breakdown

**Tests:** 11 unit tests in `TestLeadSummaryTemplates`

---

## 3. No Redundant Questions

### Problem

Without tracking, the bot might ask for information already provided:

```
User: "Hi, I'm John Smith, my email is john@test.com"
Bot: "Nice to meet you John! What's your email address?"  <- WRONG!
```

### Solution

Track `asked_fields` in session metadata. When generating the next question:
1. Check which fields are already captured
2. Check which fields have been asked
3. Only ask for fields that are both missing AND not yet asked

### Override Scenarios

The bot WILL re-ask when:
- **User explicitly wants to update**: "I want to change my email"
- **Correction flow**: User rejects confirmation, `asked_fields` is cleared

### Update Intent Detection

Patterns detected as update intent:
- "change my", "update my", "correct my", "fix my"
- "let me change", "let me update"
- "actually,", "actually my"

### Implementation

**Location:** `livekit/handlers/workflow/conversational_handler.py`

**Methods:**
- `_get_next_clarifying_question()` - Skips already-asked fields
- `_detect_update_intent()` - Detects correction requests
- `_add_to_asked_fields()` - Tracks asked fields
- `_clear_asked_fields_for_correction()` - Resets on rejection

**Tests:** 11 unit tests in `TestNoRedundantQuestions`

---

## 4. Config-Driven Scoring

### Overview

All lead scoring is now config-driven. No hardcoded patterns - everything comes from `output_template.scoring_rules`.

### Scoring Components

| Component | Description | Config Key |
|-----------|-------------|------------|
| Base Score | Starting score for all leads | `base_score` (default: 50) |
| Field Completeness | Bonus for capturing optional fields | `field_completeness_weight` (default: 20) |
| Quality Signals | Positive indicators (high revenue, urgent timeline) | `quality_signals` |
| Risk Penalties | Negative indicators (unfiled returns, IRS notice) | `risk_penalties` |

### Configuration Example

```json
{
  "output_template": {
    "scoring_rules": {
      "base_score": 50,
      "field_completeness_weight": 20,
      "quality_signals": [
        {
          "signal_id": "revenue_1m_plus",
          "points": 15,
          "condition": {
            "field": "revenue_range",
            "operator": "contains_any",
            "values": ["$1M", "$5M"]
          }
        },
        {
          "signal_id": "urgent_timeline",
          "points": 10,
          "condition": {
            "field": "timeline",
            "operator": "equals",
            "value": "Immediate"
          }
        }
      ],
      "risk_penalties": [
        {
          "penalty_id": "unfiled_returns",
          "points": -20,
          "condition": {
            "field": "red_flags",
            "operator": "contains",
            "value": "unfiled"
          }
        }
      ]
    }
  }
}
```

### Condition Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `exists` | Field has a value | `{"field": "foreign_accounts", "operator": "exists"}` |
| `not_exists` | Field is empty | `{"field": "referral", "operator": "not_exists"}` |
| `equals` | Exact match | `{"field": "timeline", "operator": "equals", "value": "Immediate"}` |
| `contains` | Substring match | `{"field": "service_need", "operator": "contains", "value": "S-Corp"}` |
| `contains_any` | Any of values | `{"field": "revenue", "operator": "contains_any", "values": ["$1M", "$5M"]}` |
| `any_of` | OR logic | `{"any_of": [condition1, condition2]}` |
| `all_of` | AND logic | `{"all_of": [condition1, condition2]}` |

### Implementation

**Service:** `livekit/services/workflow_scoring_engine.py` (~320 lines)

**Methods:**
- `calculate_score()` - Main entry point
- `_calculate_field_completeness_bonus()` - Bonus for optional fields
- `_calculate_quality_signals()` - Positive score adjustments
- `_calculate_risk_penalties()` - Negative score adjustments
- `_evaluate_condition()` - Recursive condition evaluation

**Tests:** 27 unit tests in `TestScoringEngine`

---

## 5. Advice Redirect

### Overview

Advice redirect protects against liability by detecting when users ask for professional advice and redirecting them to speak with the expert directly.

### LLM-Native Approach

We use an **LLM-native approach** where the main agent handles advice redirect via system prompt instructions:

```
When users ask for professional advice (e.g., "Should I file as S-Corp?", 
"Can I deduct this?"), redirect them to speak with the expert directly:

"That's a great question for [Expert Name] to discuss with you directly. 
Let me make sure they have your contact info so they can give you 
personalized guidance on that."
```

### Why LLM-Native?

| Approach | Pros | Cons |
|----------|------|------|
| **Pattern-based** | Predictable, auditable | Maintenance burden, misses edge cases |
| **LLM-native** (chosen) | Adaptive, handles nuance | Less predictable |

The LLM naturally understands context and can handle variations like:
- "What entity should I choose?"
- "Is it better to file as LLC or S-Corp?"
- "Can I write off my home office?"

### No Separate Config Needed

Unlike pattern-based approaches, LLM-native advice redirect doesn't require config:
- No `advice_redirect.patterns` array to maintain
- No pattern generation endpoint needed
- LLM handles it contextually based on system prompt

---

## 6. Admin API Access

### Overview

Template and workflow management endpoints support both JWT (user) and API key (admin/service) authentication.

### Authentication Modes

| Auth Type | Method | Permissions |
|-----------|--------|-------------|
| **JWT** | `myclone_token` cookie | User can only modify their own personas/workflows |
| **API Key** | `X-API-Key` header | Admin can modify any persona/workflow |

### Endpoints with Dual Auth

| Endpoint | JWT Behavior | API Key Behavior |
|----------|--------------|------------------|
| `POST /workflow-templates/enable` | Own persona, tier restrictions | Any persona, no tier restrictions |
| `PUT /workflow-templates/workflows/{id}/customize` | Own workflow only | Any workflow |
| `PATCH /workflows/{id}` | Own workflow only | Any workflow |

### Example: Admin Updating Workflow Config

```bash
curl -X PATCH "https://api.example.com/api/v1/workflows/<workflow-id>" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_config": {
      "extraction_strategy": {
        "tone": "concierge"
      }
    },
    "output_template": {
      "summary_template": "detailed",
      "include_score_breakdown": true
    }
  }'
```

---

## 7. Schema Reference

### ExtractionStrategy Schema

```python
class ExtractionStrategy(BaseModel):
    opening_question: str
    max_clarifying_questions: int = 5
    confirmation_required: bool = True
    confirmation_style: Literal["summary", "none"] = "summary"
    extraction_model: str = "gpt-4o-mini"
    confidence_threshold: float = 0.8
    allow_partial_extraction: bool = False
    tone: Literal["concierge", "professional", "casual", "efficient"] = "professional"
```

### OutputTemplate Schema

```python
class OutputTemplate(BaseModel):
    format: Literal["lead_summary"] = "lead_summary"
    sections: List[str]
    scoring_rules: Dict[str, Any]
    follow_up_rules: Optional[List[FollowUpRule]] = None
    max_follow_up_questions: int = 4
    export_destinations: List[str] = ["email", "internal_dashboard"]
    summary_template: Literal["structured", "synopsis", "minimal", "detailed"] = "structured"
    include_score_breakdown: bool = False
```

### Full Workflow Config Example

```json
{
  "required_fields": [
    {"field_id": "contact_name", "field_type": "text", "label": "Full name"},
    {"field_id": "contact_email", "field_type": "email", "label": "Email"},
    {"field_id": "contact_phone", "field_type": "phone", "label": "Phone"},
    {"field_id": "service_need", "field_type": "text", "label": "Service needed"}
  ],
  "optional_fields": [
    {"field_id": "timeline", "field_type": "choice", "label": "Timeline", 
     "options": ["Immediate", "This month", "This quarter", "Just exploring"]}
  ],
  "inference_rules": {
    "state": "Extract from location mentions. If city mentioned, infer state.",
    "timeline": "Infer from urgency cues: 'ASAP' -> Immediate"
  },
  "extraction_strategy": {
    "opening_question": "Thanks for reaching out! What brings you here today?",
    "confidence_threshold": 0.8,
    "confirmation_required": true,
    "tone": "professional"
  },
  "output_template": {
    "format": "lead_summary",
    "sections": ["profile", "need", "score", "follow_up_questions"],
    "scoring_rules": {
      "base_score": 50,
      "field_completeness_weight": 20,
      "quality_signals": [],
      "risk_penalties": []
    },
    "summary_template": "structured",
    "include_score_breakdown": false
  }
}
```

---

## Test Coverage

| Feature | Unit Tests | Integration Tests |
|---------|------------|-------------------|
| Tone Controls | 12 | - |
| Summary Templates | 11 | - |
| No Redundant Questions | 11 | - |
| Scoring Engine | 27 | 2 |
| Full Lead Capture | - | 24 |
| Confirmation Flow | - | 6 |
| **Total** | **61** | **30** |

Run tests:
```bash
# Unit tests (fast)
poetry run pytest livekit/tests/unit/ -v

# Integration tests (requires OPENAI_API_KEY)
poetry run pytest livekit/tests/integration/ -v
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-29 | Initial implementation of tone controls, summary templates, no-redundant-questions |
| 2026-01-29 | Config-driven scoring engine (replaces hardcoded patterns) |
| 2026-01-29 | Admin API access with service auth |
| 2026-01-29 | Documentation created |
