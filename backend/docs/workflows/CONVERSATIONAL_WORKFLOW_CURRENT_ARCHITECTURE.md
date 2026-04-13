# Conversational Workflow System - Current Architecture Documentation

**Status:** ✅ Implemented and Working (Phase 1-4 Complete + Batch Tool Enhancement)
**Last Updated:** 2026-02-24
**Migration Applied:** `7ac6c5e769e2_add_conversational_workflow_support.py`

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Database Schema](#database-schema)
3. [Core Components](#core-components)
4. **[Phase 1: Config-Driven Multi-Vertical Architecture](#phase-1-config-driven-multi-vertical-architecture)** ⭐ NEW
5. **[Phase 2: UX Improvements](#phase-2-ux-improvements)** ⭐ NEW
6. **[Phase 3: Confirmation Flow](#phase-3-confirmation-flow)** ⭐ NEW
7. [Data Flow Architecture](#data-flow-architecture)
8. [Field Extraction Engine](#field-extraction-engine)
9. [Lead Scoring System](#lead-scoring-system)
10. [Summary Generation](#summary-generation)
11. [API Layer](#api-layer)
12. [Configuration Structure](#configuration-structure)
13. [What This System IS](#what-this-system-is)
14. [What This System IS NOT](#what-this-system-is-not)
15. [Implementation Files](#implementation-files)

---

## System Overview

### What is the Conversational Workflow System?

The **Conversational Workflow** is the third workflow type (after `simple` and `scored`) that enables **intelligent field extraction from natural language conversations**. Instead of asking structured questions in sequence, it:

1. **Starts with an open-ended question** (e.g., "What's going on with your business?")
2. **Extracts structured fields** (contact_name, entity_type, revenue_range, etc.) from free-form responses using LLM
3. **Asks clarifying questions** only for missing required fields
4. **Scores the lead** based on field completeness, quality signals, and risk penalties
5. **Generates a formatted summary** with profile, situation, needs, score, and follow-up questions

### Use Cases

- **CPA Lead Capture**: Extract business details, entity type, revenue, compliance issues
- **Insurance Sales**: Extract policy needs, coverage amounts, risk factors, timeline
- **Real Estate**: Extract property details, budget, location preferences, timeline
- **Healthcare**: Extract symptoms, medical history, insurance coverage, urgency

### Workflow Type Comparison

| Feature | Simple | Scored | **Conversational** |
|---------|--------|--------|-------------------|
| Question Flow | Linear | Linear | **Dynamic** |
| Field Extraction | Structured | Structured | **Natural Language** |
| Scoring | ❌ No | ✅ Fixed Rules | **✅ Multi-Factor** |
| Clarifying Questions | ❌ No | ❌ No | **✅ Intelligent** |
| Confidence Scoring | ❌ No | ❌ No | **✅ Per-Field** |
| Industry Agnostic | ✅ Yes | ✅ Yes | **✅ Config-Driven** |

---

## Database Schema

### Migration: `7ac6c5e769e2_add_conversational_workflow_support`

**Tables Modified:**

#### 1. `persona_workflows` Table

**New Column:**
```sql
output_template JSONB  -- Nullable
```

**Purpose:** Stores lead summary formatting configuration and scoring rules for conversational workflows.

**Structure (New Config-Driven Format):**
```json
{
  "format": "lead_summary",
  "sections": ["profile", "situation", "need", "score", "key_context", "follow_up_questions"],
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
        "signal_id": "multi_state",
        "points": 10,
        "condition": {
          "field": "state",
          "operator": "contains",
          "value": "multi-state"
        }
      }
    ],
    "risk_penalties": [
      {
        "penalty_id": "red_flag_unfiled_returns",
        "points": -20,
        "condition": {
          "field": "red_flags",
          "operator": "contains",
          "value": "unfiled"
        }
      }
    ]
  },
  "export_destinations": ["email", "internal_dashboard"]
}
```

**Note:** Legacy dict format still supported for backward compatibility. See complete example in Configuration Structure section.

**Index Added:**
```sql
CREATE INDEX idx_persona_workflows_output_template ON persona_workflows USING GIN (output_template);
```

#### 2. `workflow_sessions` Table

**New Column:**
```sql
extracted_fields JSONB  -- Nullable
```

**Purpose:** Stores incrementally extracted fields with confidence scores and metadata during conversational workflow sessions.

**Structure:**
```json
{
  "contact_name": {
    "value": "John Smith",
    "confidence": 1.0,
    "extraction_method": "direct_statement",
    "raw_input": "My name is John Smith",
    "extracted_at": "2026-01-24T10:05:00Z"
  },
  "entity_type": {
    "value": "LLC",
    "confidence": 0.85,
    "extraction_method": "natural_language",
    "raw_input": "We're an LLC operating in California",
    "extracted_at": "2026-01-24T10:06:00Z"
  }
}
```

**Index Added:**
```sql
CREATE INDEX idx_workflow_sessions_extracted_fields ON workflow_sessions USING GIN (extracted_fields);
```

**Backward Compatibility:** Both columns are `nullable=True`, so existing `simple` and `scored` workflows continue working without changes.

---

## Core Components

### High-Level Architecture

**Note:** See "LiveKit Voice Agent Integration" section below for detailed architecture diagrams.

```
┌─────────────────────────────────────────────────────────────────┐
│                   LiveKit Voice/Text Agent                       │
│                  livekit/livekit_agent.py                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Workflow Handler                              │
│              livekit/handlers/workflow_handler.py                │
│                                                                   │
│  - start_workflow()                                              │
│  - process_conversational_message()                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│           Conversational Workflow Coordinator                    │
│     livekit/services/conversational_workflow_coordinator.py      │
└──┬────────────────┬────────────────┬─────────────────────────────┘
   │                │                │
   ▼                ▼                ▼
┌─────────┐  ┌──────────┐  ┌────────────────┐
│ Field   │  │ Scoring  │  │   Workflow     │
│Extract- │  │ Engine   │  │   Repository   │
│ or      │  │          │  │   (Database)   │
└─────────┘  └──────────┘  └────────────────┘
   │
   │ Uses OpenAI Structured Outputs
   ▼
┌──────────────────────┐
│  OpenAI GPT-4o-mini  │
│  (Extraction LLM)    │
└──────────────────────┘
```

### Component Files (PRODUCTION)

**Note:** As of Jan 2026, conversational workflow logic is split between modular handlers and shared services.

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| **Workflow Factory** | `livekit/handlers/workflow/__init__.py` | ~75 | Factory to create appropriate handler |
| **Base Handler** | `livekit/handlers/workflow/base.py` | ~230 | Shared workflow logic (session management) |
| **Linear Handler** | `livekit/handlers/workflow/linear_handler.py` | ~310 | Step-by-step Q&A assessments |
| **Conversational Handler** | `livekit/handlers/workflow/conversational_handler.py` | ~360 | Lead capture field extraction |
| **Field Extractor** | `livekit/services/workflow_field_extractor.py` | ~130 | Pydantic model for extracted fields |
| **Condition Evaluator** | `livekit/services/workflow_condition_evaluator.py` | 315 | Generic rule engine (16 operators) |
| **API Models** | `app/api/models/workflow_models.py` | 841 | Pydantic validation schemas |
| **DB Models** | `shared/database/models/workflow.py` | 369 | SQLAlchemy ORM models |
| **Repository** | `shared/database/repositories/workflow_repository.py` | - | Database operations |

**Deleted in Jan 2026 Cleanup:**
- `livekit/services/conversational_workflow_coordinator.py` (stale dual-LLM approach)
- `livekit/services/workflow_scoring_engine.py` (unused)

---

## ⭐ LiveKit Voice Agent Integration (NEW - Jan 2026)

### Overview

Conversational workflows are now **fully integrated** with the LiveKit voice agent through a new modular handler architecture.

### Architecture (Jan 2026 - Modular Handlers)

```
┌─────────────────────────────────────────────────────────────────┐
│                   LiveKit Modular Agent                          │
│                  livekit/livekit_agent.py (~650 lines)           │
│                                                                   │
│  - Main LLM pipeline (voice/text conversation)                   │
│  - Thin @function_tool wrappers delegate to handlers             │
│  - Uses create_workflow_handler() factory                        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Workflow Handler Factory                      │
│              livekit/handlers/workflow/__init__.py               │
│                                                                   │
│  create_workflow_handler(workflow_data, persona_id, ...)         │
│  Returns: LinearWorkflowHandler | ConversationalWorkflowHandler  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
┌─────────────────────┐    ┌─────────────────────────┐
│  LinearWorkflow     │    │  ConversationalWorkflow │
│     Handler         │    │        Handler          │
│ (simple/scored)     │    │    (lead capture)       │
│                     │    │                         │
│ - submit_answer()   │    │ - store_extracted_field()│
│ - _complete_workflow│    │ - complete_workflow()    │
└─────────┬───────────┘    └───────────┬─────────────┘
          │                            │
          │                            │
          ▼                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BaseWorkflowHandler                           │
│              livekit/handlers/workflow/base.py                   │
│                                                                   │
│  Shared Logic:                                                   │
│  - start_workflow() - Creates DB session, sends opening message  │
│  - _create_workflow_session() - Database operations              │
│  - is_active, workflow_type properties                           │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────┐
│  Workflow Repository │
│  (Database CRUD)     │
└──────────────────────┘
```

### LiveKit Components (Production Implementation)

**Note:** These are the ONLY implementations of workflows. The handlers use a factory pattern to create the appropriate handler type.

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| **Modular Agent** | `livekit/livekit_agent.py` | ~650 | Main LiveKit agent (thin wrappers delegate to handlers) |
| **Workflow Factory** | `livekit/handlers/workflow/__init__.py` | ~75 | Creates Linear or Conversational handler |
| **Base Handler** | `livekit/handlers/workflow/base.py` | ~230 | Shared session management and validation |
| **Linear Handler** | `livekit/handlers/workflow/linear_handler.py` | ~310 | Step-by-step Q&A assessments |
| **Conversational Handler** | `livekit/handlers/workflow/conversational_handler.py` | ~360 | Natural language lead capture |
| **Field Extractor** | `livekit/services/workflow_field_extractor.py` | ~130 | ExtractedFieldValue Pydantic model |
| **Condition Evaluator** | `livekit/services/workflow_condition_evaluator.py` | 315 | Generic rule engine (config-driven, zero industry knowledge) |

### Implementation Notes

**Modular Handler Pattern:** As of Jan 2026, workflow logic uses a factory + inheritance pattern:

- ✅ **Factory Function**: `create_workflow_handler()` returns appropriate handler type
- ✅ **Base Class**: `BaseWorkflowHandler` contains shared session management
- ✅ **Type-Specific Handlers**: `LinearWorkflowHandler` and `ConversationalWorkflowHandler`
- ✅ **Sentry Monitoring**: Production error tracking throughout all handlers
- ✅ **Voice + Text**: Works in both LiveKit voice calls and text conversations

**Key Simplification (Jan 2026):**
- Deleted stale dual-LLM services (`conversational_workflow_coordinator.py`, `workflow_scoring_engine.py`)
- Conversational workflows now use batch field extraction via `update_lead_fields()` tool
- LLM extracts ALL fields from each message in ONE call (JSON string parameter)
- Batch approach eliminates race conditions when multiple fields extracted from single utterance

### How Workflow Handlers Work

#### 1. Factory Pattern

```python
# livekit/handlers/workflow/__init__.py

def create_workflow_handler(workflow_data, persona_id, output_callback, ...):
    """Factory creates the right handler based on workflow type."""
    if not workflow_data:
        return None  # No workflow configured
    
    workflow_type = workflow_data.get("workflow_type", "simple")
    
    if workflow_type == "conversational":
        return ConversationalWorkflowHandler(...)
    else:
        return LinearWorkflowHandler(...)  # simple, scored
```

#### 2. Conversational Workflow Tools

The agent uses two tools for conversational workflows:

```python
# livekit/livekit_agent.py

@function_tool
async def update_lead_fields(self, fields_json: str) -> str:
    """
    Store one or more lead capture fields extracted from user's message.
    
    LLM extracts ALL fields from user's message and passes them as a JSON string.
    This batch approach prevents race conditions when multiple fields are
    extracted from a single utterance.
    
    Args:
        fields_json: JSON string mapping field_id to value
                     Example: '{"contact_name": "John", "contact_email": "john@email.com"}'
    
    Returns:
        Status message with remaining fields or "AWAITING_CONFIRMATION"
    """
    fields = json.loads(fields_json)
    
    # Auto-starts workflow if not active
    if not self.workflow_handler.is_active:
        await self.workflow_handler.start_workflow(send_opening_message=False)
    
    # Store ALL extracted fields in single atomic operation
    return await self.workflow_handler.store_extracted_fields(fields)

@function_tool
async def confirm_lead_capture(self) -> str:
    """Called after user confirms all fields are correct."""
    return await self.workflow_handler.complete_workflow(extracted_fields)
```

**Why Batch Tool (JSON string)?**

The previous `update_lead_field(field_id, value)` approach had a race condition:
- When LLM extracted 4 fields from one message, it made 4 parallel tool calls
- Each call read stale DB state, causing conflicting progress reports
- Result: Agent would re-ask for already-captured information

The new `update_lead_fields(fields_json)` approach:
- Extracts ALL fields in ONE call as a JSON string
- Single DB transaction ensures accurate progress
- OpenAI function calling doesn't support `dict` type, so we use JSON string

#### 3. ConversationalWorkflowHandler Methods

```python
# livekit/handlers/workflow/conversational_handler.py

class ConversationalWorkflowHandler(BaseWorkflowHandler):
    async def store_extracted_fields(self, fields: dict[str, str]) -> str:
        """
        Store multiple extracted fields in a single atomic operation.
        
        Args:
            fields: Dictionary of field_id -> value pairs
        
        Returns:
            Status message with remaining fields or AWAITING_CONFIRMATION
        """
        # 1. Filter out empty values
        # 2. Validate all field_ids against workflow config
        # 3. Save ALL fields to database in single transaction
        # 4. Calculate progress AFTER all fields stored
        # 5. Return accurate status message
    
    async def complete_workflow(self, extracted_fields: dict) -> str:
        """Mark workflow complete after user confirmation."""
        # 1. Update session status to 'completed'
        # 2. Update progress_percentage to 100
        # 3. Return success message
```

#### 4. Output Callback Pattern

All handlers use a **callback function** to send messages (voice or text):

```python
# Initialization (in livekit_agent.py)
workflow_handler = create_workflow_handler(
    workflow_data=workflow_data,
    persona_id=persona_id,
    output_callback=self._output_message,  # Agent's output method
    text_only_mode=self.text_only_mode
)

# The callback handles voice vs text automatically
async def _output_message(self, message: str):
    if self.text_only_mode:
        await self.room.local_participant.send_text(message, topic="lk.chat")
    else:
        await self.session.say(message, allow_interruptions=True)
```

### Architecture Evolution

**Jan 2026 Migration (Phase 1):** The codebase previously had two separate implementations (API-based in `shared/workflows/` and voice-based in `livekit/services/`), causing code duplication and maintenance burden.

**Jan 2026 Cleanup (Phase 2):** Deleted stale dual-LLM services:
- `livekit/services/conversational_workflow_coordinator.py` - Complex orchestration replaced by simple handler
- `livekit/services/workflow_scoring_engine.py` - Unused scoring logic
- `livekit/tasks/` folder - Stale background tasks

**Jan 2026 Modularization (Phase 3):** Split monolithic `workflow_handler.py` into:
- `livekit/handlers/workflow/__init__.py` - Factory function
- `livekit/handlers/workflow/base.py` - Shared logic
- `livekit/handlers/workflow/linear_handler.py` - Assessments
- `livekit/handlers/workflow/conversational_handler.py` - Lead capture

**Current State:** Modular handler pattern that:
- Shares database schema (`persona_workflows`, `workflow_sessions`)
- Uses factory to create appropriate handler type
- Simplified conversational workflow (field-by-field extraction via LLM tools)
- Works in both voice (LiveKit) and text modes

### Benefits of LiveKit Integration

1. **Voice-First UX**: Natural conversational workflow over voice calls
2. **Modular Architecture**: Clean separation via WorkflowHandler (81% code reduction in main agent)
3. **Stateful Sessions**: Maintains context throughout voice conversation
4. **Dual Mode**: Supports both voice and text via same handler
5. **Shared Logic**: Reuses core services (field extraction, scoring) across API and voice

### Example Voice Workflow Flow

```
1. User connects to LiveKit room
   ↓
2. Agent loads active conversational workflow from database
   ↓
3. Agent greets user, workflow starts when user shows interest
   ↓
4. User responds (voice): "I'm John from Acme Corp, we're an LLC in California..."
   ↓
5. LLM extracts ALL fields and calls update_lead_fields() ONCE with JSON:
   update_lead_fields('{"contact_name": "John", "business_name": "Acme Corp", "entity_type": "LLC", "state": "California"}')
   ↓
6. Handler stores all 4 fields atomically, returns accurate progress:
   "Saved 4 fields. Progress: 60% (3/5 required). Still need: contact_email, service_need"
   ↓
7. Agent asks naturally (TTS): "Great John! What's your email and what service do you need?"
   ↓
8. User responds: "john@acme.com, we need tax filing help"
   ↓
9. LLM extracts both fields in ONE call:
   update_lead_fields('{"contact_email": "john@acme.com", "service_need": "tax filing"}')
   ↓
10. Handler returns: "AWAITING_CONFIRMATION" (all required fields collected)
    ↓
11. Agent says confirmation (TTS):
    "Perfect! I have: John from Acme Corp, LLC in California,
     email john@acme.com, needing tax filing help. Is that correct?"
    ↓
12. User confirms: "Yes, that's correct"
    ↓
13. LLM calls: confirm_lead_capture()
    ↓
14. Handler marks workflow complete, stores in database
    ↓
15. Agent: "Awesome! How can I help you with your tax filing today?"
```

**Key Improvement (Jan 2026):** The batch tool approach ensures that when a user provides
multiple pieces of information in one utterance, ALL fields are extracted and stored in a
single atomic operation. This eliminates race conditions and ensures accurate progress tracking.

---

## Phase 1: Config-Driven Multi-Vertical Architecture

### Problem Addressed

The initial implementation had **hardcoded CPA-specific logic** in two critical areas:
1. **Lead Scoring** - Pattern matching for CPA-specific signals (revenue_1m_plus, foreign_accounts_fbar, S-Corp, FBAR)
2. **Follow-Up Questions** - Hardcoded CPA terminology (FBAR forms, sales tax, payroll questions)

This broke the **industry-agnostic design principle** - workflows for insurance, real estate, or healthcare would get CPA questions.

### Solution: Generic Condition Evaluator

**Core Concept:** Replace all hardcoded pattern matching with a **universal rule engine** that has zero industry knowledge.

**`ConditionEvaluator` Utility:**
- 16 generic operators: `exists`, `not_exists`, `equals`, `not_equals`, `contains`, `not_contains`, `contains_any`, `greater_than`, `less_than`, `greater_than_or_equal`, `less_than_or_equal`, `in_list`, `not_in_list`, `regex_match`, `word_count_gte`, `word_count_lte`
- Compound logic support: `any_of` (OR), `all_of` (AND) for complex conditions
- Works for **any** industry by evaluating field conditions from config

**Example Condition:**
```json
{
  "field": "revenue_range",
  "operator": "contains_any",
  "value": ["$1M", "$5M"]
}
```

This condition means: "If revenue_range contains $1M or $5M, award points" - no CPA knowledge needed.

### Impact

**Before Phase 1:**
- Adding insurance workflows → need to modify `lead_scorer.py` and `summary_formatter.py` code
- Hardcoded checks like `if "$1M" in revenue_value` scattered throughout
- CPA follow-up questions show up for all industries

**After Phase 1:**
- Adding insurance workflows → just configure conditions in JSON (no code changes)
- All pattern matching delegated to `ConditionEvaluator`
- **True multi-vertical support** - CPA, insurance, real estate, healthcare all use same codebase

### Backward Compatibility

Both `lead_scorer.py` and `summary_formatter.py` support **dual formats**:
- **Legacy format** (dict): Existing CPA workflows continue working unchanged
- **New format** (list with conditions): New workflows use config-driven approach
- Format auto-detected at runtime

### Files Modified

- `shared/workflows/condition_evaluator.py` - NEW (generic rule engine)
- `shared/workflows/lead_scorer.py` - Added config-driven quality signals and risk penalties
- `shared/workflows/summary_formatter.py` - Added config-driven follow-up question generation
- `app/api/models/workflow_models.py` - Added `Condition`, `FollowUpRule`, `QualitySignal`, `RiskPenalty` models

---

## Phase 2: UX Improvements

### Problem Addressed

Conversational workflows felt **robotic and generic** in two ways:
1. **Generic clarifying questions** - "What's your email address?" instead of "Got it! What's the best email to reach you at?"
2. **No correction support** - If user says "actually, my email is different...", system ignores it (field already extracted)

### Solution 1: Custom Clarifying Questions

**Core Concept:** Allow workflow creators to define **natural, conversational questions** per field instead of relying on generic templates.

**Added to `ConversationalField` model:**
```json
{
  "field_id": "contact_email",
  "field_type": "email",
  "label": "Email address",
  "clarifying_question": "Got it! What's the best email to reach you at?"  ← NEW
}
```

**Behavior:**
- If `clarifying_question` provided → use it (conversational)
- If not provided → fall back to generic template (backward compatible)

### Solution 2: Correction Detection

**Core Concept:** Detect when user wants to **correct previously extracted data** using natural language patterns.

**13 Correction Patterns Detected:**
- "actually", "sorry", "I meant", "correction", "wrong", "that's not right", "let me correct", "my bad", "no that's", "wait", "change that", "not quite", "incorrect"

**Behavior:**
- User says: "Actually, my email is john@different.com"
- System detects "actually" → sets `allow_overwrite=True`
- Field extractor **re-extracts all fields** from the message (including corrections)
- Updated field replaces old value

**Without correction detection:**
- System would ignore the correction (email already extracted)
- User stuck with wrong data

**With correction detection:**
- System automatically updates the field
- Natural conversation flow maintained

### Impact

**Before Phase 2:**
- Questions feel robotic: "What's your email address?"
- Cannot fix mistakes without starting over

**After Phase 2:**
- Questions feel natural: "Got it! What's the best email to reach you at?"
- Users can naturally correct: "Actually, it's john@new.com" → field updated

### Files Modified

- `livekit/services/workflow_field_extractor.py` - Added custom question support, `allow_overwrite` parameter
- `livekit/services/conversational_workflow_coordinator.py` - Added correction intent detection
- `app/api/models/workflow_models.py` - Added `clarifying_question` to `ConversationalField`

---

## Phase 3: Confirmation Flow

### Problem Addressed

Workflows **completed immediately** when all required fields were captured - no chance for user to review or correct before submission.

**User Experience Issue:**
- System: "Got your email as john@acme.com"
- User: (doesn't notice typo)
- System: **[WORKFLOW COMPLETED]** → Lead submitted with wrong email
- User: "Wait, I meant john@acmecorp.com" → Too late, workflow already completed

### Solution: Review Before Completion

**Core Concept:** Add a **confirmation state** between field capture and workflow completion.

**New Flow:**
1. All required fields captured
2. System enters **confirmation mode** (if `extraction_strategy.confirmation_required = true`)
3. System shows **formatted summary** of all captured fields
4. User can:
   - **Confirm** ("yes", "looks good", "correct") → Complete workflow
   - **Correct** ("no", "change email", "actually...") → Stay in confirmation, allow edits
   - **Unclear** → Ask again

**Confirmation Summary Example:**
```
Great! Here's what I've captured:

• Full name: John Smith
• Email: john@acme.com
• Entity type: LLC
• Revenue range: $1M+

Is this information correct? (You can say 'yes' to confirm, or let me know what needs to be changed)
```

### Response Detection

**17 Affirmative Patterns:** "yes", "yeah", "yep", "yup", "correct", "that's right", "looks good", "perfect", "all good", "confirmed", "ok", "sure", etc.

**8 Negative Patterns:** "no", "nope", "not quite", "not right", "incorrect", "wrong", "need to change", "let me fix"

**Correction Patterns (from Phase 2):** "actually", "sorry", "I meant", etc. also trigger correction mode

### State Machine

**Session Metadata:** `awaiting_confirmation` flag tracks confirmation state

**States:**
1. **Normal extraction** → `awaiting_confirmation = false`
2. **All required fields captured + confirmation required** → `awaiting_confirmation = true`, show summary
3. **User confirms** → Complete workflow
4. **User wants corrections** → Re-extract fields, show updated summary, stay in confirmation mode
5. **Unclear response** → Ask again

### Configurability

Confirmation flow is **optional** via `extraction_strategy.confirmation_required`:
- `true` (default) → Show confirmation summary before completion
- `false` → Complete immediately when all required fields captured (original behavior)

### Impact

**Before Phase 3:**
- No review opportunity
- Mistakes discovered after workflow completed
- Poor user experience for critical data

**After Phase 3:**
- User reviews all data before submission
- Can make corrections during confirmation
- Professional, trustworthy experience
- Configurable per workflow (some workflows may not need confirmation)

### Files Modified

- `livekit/services/conversational_workflow_coordinator.py` - Added confirmation state machine, response detection, summary formatting
- `shared/database/repositories/workflow_repository.py` - Added `update_session_metadata()` method

---

## Data Flow Architecture

### End-to-End Message Processing Flow

```
USER MESSAGE: "Hi, I'm John from Acme Corp. We're an LLC in California
               and looking for help with our taxes."

                           ↓

┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: API Receives Message                                    │
│ POST /api/workflows/sessions/{session_id}/message               │
│ Body: {"message": "Hi, I'm John..."}                            │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: ConversationalWorkflowExecutor.process_user_message()   │
│                                                                   │
│ 1. Load session from DB                                          │
│ 2. Get existing extracted_fields (from previous messages)       │
│ 3. Load workflow_config (required_fields, optional_fields)      │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: ConversationalFieldExtractor.update_extracted_fields()  │
│                                                                   │
│ Input:                                                           │
│ - existing_fields: {}  (empty for first message)                │
│ - new_message: "Hi, I'm John from Acme Corp..."                 │
│ - required_fields: [contact_name, entity_type, state, ...]      │
│ - inference_rules: {...}                                         │
│ - confidence_threshold: 0.8                                      │
│                                                                   │
│ Process:                                                         │
│ 1. Build extraction prompt with field definitions               │
│ 2. Call OpenAI with structured outputs (MultiFieldExtraction)   │
│ 3. LLM returns extractions with confidence scores                │
│                                                                   │
│ Output:                                                          │
│ extracted_fields = {                                             │
│   "contact_name": {                                              │
│     "value": "John",                                             │
│     "confidence": 1.0,                                           │
│     "extraction_method": "direct_statement"                      │
│   },                                                             │
│   "business_name": {                                             │
│     "value": "Acme Corp",                                        │
│     "confidence": 1.0,                                           │
│     "extraction_method": "direct_statement"                      │
│   },                                                             │
│   "entity_type": {                                               │
│     "value": "LLC",                                              │
│     "confidence": 1.0,                                           │
│     "extraction_method": "direct_statement"                      │
│   },                                                             │
│   "state": {                                                     │
│     "value": "California",                                       │
│     "confidence": 0.95,                                          │
│     "extraction_method": "natural_language"                      │
│   }                                                              │
│ }                                                                │
│ missing_required_fields = ["contact_email", "service_need"]     │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Update Session Progress                                 │
│                                                                   │
│ - Calculate progress: 4/6 required fields = 67%                 │
│ - Update workflow_sessions.extracted_fields (JSONB)             │
│ - Update workflow_sessions.progress_percentage = 67             │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Check Completion                                        │
│                                                                   │
│ Are all required fields captured?                               │
│ ❌ NO → missing_required_fields = ["contact_email", "service_need"]│
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Generate Clarifying Question                            │
│                                                                   │
│ FieldExtractor._generate_clarifying_question()                  │
│                                                                   │
│ Output: "What's your email address?"                            │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: Return Response (IN_PROGRESS)                           │
│                                                                   │
│ {                                                                │
│   "status": "in_progress",                                       │
│   "next_question": "What's your email address?",                │
│   "progress_percentage": 67,                                     │
│   "missing_required_fields": ["contact_email", "service_need"]  │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘


USER MESSAGE: "It's john@acmecorp.com and we need tax filing help"

                           ↓

[Repeat Steps 1-7 with updated extracted_fields]

                           ▼

┌─────────────────────────────────────────────────────────────────┐
│ ALL REQUIRED FIELDS CAPTURED!                                   │
│ extracted_fields now has all 6 required fields                  │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: Complete Workflow (Executor._complete_workflow)         │
│                                                                   │
│ 1. Calculate Lead Score (LeadScorer.calculate_score)            │
│ 2. Generate Summary (SummaryFormatter.format_summary)           │
│ 3. Mark session as completed (WorkflowRepository)               │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 9: Lead Scoring                                            │
│                                                                   │
│ LeadScorer.calculate_score()                                    │
│                                                                   │
│ Calculation:                                                     │
│ - base_score: 50                                                 │
│ - field_completeness: 20 (100% optional fields captured)        │
│ - quality_signals: +15 (revenue_1m_plus detected)               │
│ - risk_penalties: 0 (no red flags)                              │
│                                                                   │
│ Total Score: 85/100 → HIGH PRIORITY                             │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 10: Summary Generation                                     │
│                                                                   │
│ SummaryFormatter.format_summary()                               │
│                                                                   │
│ Generates sections:                                              │
│ - PROFILE: Contact info, business details                       │
│ - CURRENT SITUATION: Current state, bookkeeping status          │
│ - SERVICE NEED: What they're looking for                        │
│ - LEAD SCORE: 85/100 - HIGH PRIORITY                            │
│ - KEY CONTEXT: Foreign accounts, complexity, red flags          │
│ - FOLLOW-UP QUESTIONS: Contextual questions (4 max)             │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 11: Database Update                                        │
│                                                                   │
│ WorkflowRepository.complete_conversational_session()            │
│                                                                   │
│ UPDATE workflow_sessions SET                                     │
│   status = 'completed',                                          │
│   progress_percentage = 100,                                     │
│   result_data = {                                                │
│     "final_summary": "...",                                      │
│     "lead_score": 85,                                            │
│     "priority_level": "high"                                     │
│   },                                                             │
│   completed_at = NOW()                                           │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 12: Return Response (COMPLETED)                            │
│                                                                   │
│ {                                                                │
│   "status": "completed",                                         │
│   "final_summary": "LEAD: John - Acme Corp\n...",               │
│   "lead_score": 85.0,                                            │
│   "priority_level": "high",                                      │
│   "progress_percentage": 100                                     │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Field Extraction Engine

**File:** `livekit/services/workflow_field_extractor.py`

### How It Works

The field extractor uses **OpenAI Structured Outputs** (beta API) with `gpt-4o-mini` to extract fields from natural language.

#### Extraction Methods

| Method | Confidence Range | Example |
|--------|------------------|---------|
| **direct_statement** | 1.0 | "My name is John" → contact_name = "John" |
| **natural_language** | 0.85-0.95 | "I'm in San Jose" → state = "California" |
| **inference** | 0.7-0.85 | "Small team" → revenue_range = "$100K-$500K" |
| **clarifying_question** | 1.0 | After asking "What's your email?" → contact_email |

#### Confidence Scoring Logic

```python
def _determine_extraction_method(self, confidence: float) -> str:
    if confidence >= 0.95:
        return "direct_statement"
    elif confidence >= 0.85:
        return "natural_language"
    else:
        return "inference"
```

**Default Threshold:** 0.8 (configurable via `extraction_strategy.confidence_threshold`)

Fields with `confidence < threshold` are **NOT extracted** and remain in `missing_required_fields`.

#### Inference Rules

**Purpose:** Natural language instructions that guide LLM extraction for each field.

**Example:**
```json
{
  "inference_rules": {
    "entity_type": "Extract if user mentions 'LLC', 'S-Corp', 'C-Corp', etc. If unclear, ask: 'What's your business structure?'",
    "revenue_range": "Infer from cues: 'small team' → $100K-$500K, '10+ employees' → $500K+",
    "state": "Extract from location mentions. If user says city, infer state (e.g., 'San Jose' → California)"
  }
}
```

**How They're Used:** Injected into the OpenAI system prompt as extraction guidelines.

#### Clarifying Question Generation

**Template-Based (Current Implementation):**

```python
def _generate_clarifying_question(self, field_id: str, required_fields: List[Dict]) -> str:
    field = next((f for f in required_fields if f["field_id"] == field_id), None)

    if field_type == "choice" and options:
        return f"What's your {label}? ({', '.join(options)})"
    elif field_type == "email":
        return f"What's your email address?"
    elif field_type == "phone":
        return f"What's your phone number?"
    else:
        return f"What's your {label}?"
```

**Limitation:** Generic templates, not context-aware.

**Example Output:**
- "What's your email address?"
- "What's your Business entity type? (Sole Proprietor, LLC, S-Corp, C-Corp)"

---

## Lead Scoring System

**File:** `livekit/services/lead_scoring_service.py`

**⚠️ UPDATED (2026-01-31):** Lead scoring is now **LLM-only** via `LeadScoringService`. The old rule-based `WorkflowScoringEngine` and `WorkflowSummaryService` have been removed.

### Why LLM-Only Scoring?

Rule-based scoring is brittle - it requires exact string matches (e.g., "Immediate" vs "immediately" vs "ASAP"). The LLM understands intent and nuance in free-form text, making it more accurate and maintainable.

### Architecture

```
complete_workflow()
        ↓
Mark session as completed (instant response to user)
        ↓
_fire_background_scoring() → Fire-and-forget async task
        ↓
LeadScoringService.evaluate_lead() → OpenAI GPT-4o-mini
        ↓
Returns LeadEvaluationResult (Pydantic validated)
        ↓
repo.update_session_lead_evaluation() → Stores in result_data
```

### LeadEvaluationResult Schema

The LLM returns a structured JSON that is validated by Pydantic:

```python
class LeadEvaluationResult(BaseModel):
    lead_score: int                    # 0-100
    priority_level: Literal["high", "medium", "low"]
    lead_quality: Literal["hot", "warm", "cold"]
    urgency_level: Literal["high", "medium", "low"]
    lead_summary: LeadSummary          # Structured contact + service info
    scoring: LeadScoring               # Breakdown with signals/penalties
    confidence: float                  # 0.0-1.0
    evaluated_at: str                  # ISO timestamp

class LeadSummary(BaseModel):
    contact: LeadContact               # name, email, phone
    service_need: str                  # What they're looking for
    additional_info: Dict[str, str]    # Extra context (state, timeline, etc.)
    follow_up_questions: List[str]     # LLM-generated suggestions

class LeadScoring(BaseModel):
    score: int
    priority: str
    signals_matched: List[SignalMatched]    # [{signal_id, points, reason}]
    penalties_applied: List[PenaltyApplied] # [{penalty_id, points, reason}]
    reasoning: str                          # LLM explanation
```

### Database Storage

The complete `LeadEvaluationResult` is stored in `workflow_sessions.result_data` (JSONB):

```json
{
  "lead_score": 85,
  "priority_level": "high",
  "lead_quality": "hot",
  "urgency_level": "high",
  "lead_summary": {
    "contact": {"name": "John Smith", "email": "john@acme.com", "phone": "555-1234"},
    "service_need": "S-Corp election and tax planning",
    "additional_info": {"timeline": "Immediate", "state": "California"},
    "follow_up_questions": [
      "What is your current business structure?",
      "Have you consulted with a tax professional before?"
    ]
  },
  "scoring": {
    "score": 85,
    "priority": "high",
    "signals_matched": [
      {"signal_id": "urgent_timeline", "points": 15, "reason": "Immediate need indicated"}
    ],
    "penalties_applied": [],
    "reasoning": "Hot lead with urgent need and complete contact info."
  },
  "confidence": 0.92,
  "evaluated_at": "2026-01-30T22:32:09.560706+00:00"
}
```

### Workflow Context

The LLM receives `scoring_rules` from the workflow template to evaluate against workflow-specific quality signals:

```python
workflow_context = {
    "template_name": "CPA Lead Capture",
    "workflow_type": "conversational",
    "scoring_rules": {
        "quality_signals": [...],   # From output_template
        "risk_penalties": [...]     # From output_template
    },
    "output_config": {
        "max_follow_up_questions": 4
    }
}
```

### Priority Classification

The LLM determines priority based on the overall evaluation, but generally follows:

| Score Range | Priority | Lead Quality |
|-------------|----------|--------------|
| 80-100 | high | hot |
| 60-79 | medium | warm |
| 0-59 | low | cold |

---

## Summary Generation

**File:** `livekit/services/lead_scoring_service.py` (integrated into LeadScoringService)

**⚠️ UPDATED (2026-01-31):** Summary generation is now part of the LLM scoring - the `lead_summary` field contains structured data suitable for frontend rendering.

### Summary Sections

The formatter generates **6 configurable sections** based on `output_template.sections`:

#### 1. PROFILE Section
```
LEAD: John Smith - Acme Corp
CONTACT: john@acme.com | +1-555-0100

BUSINESS PROFILE
Entity: LLC
State(s): California
Revenue: $1M+
Employees: 10-25
```

**Fields Used:** contact_name, business_name, contact_email, contact_phone, entity_type, state, revenue_range, employee_count

#### 2. CURRENT SITUATION Section
```
CURRENT SITUATION
Currently using QuickBooks but falling behind. No CPA yet.
Bookkeeping: Behind by 2 months
Income Sources: Business revenue, 1099 contract work
```

**Fields Used:** current_situation, bookkeeping_status, income_sources

#### 3. SERVICE NEED Section
```
SERVICE NEED
Primary: Tax filing and bookkeeping catch-up
Timeline: Before tax deadline (4 months)
```

**Fields Used:** service_need, timeline

#### 4. LEAD SCORE Section
```
LEAD SCORE: 85/100 - HIGH PRIORITY
Breakdown: Base: 50 | Completeness: +20 | Revenue 1M Plus: +15
```

**Fields Used:** score_breakdown (from LeadScorer)

#### 5. KEY CONTEXT Section
```
KEY CONTEXT
⚠️ Foreign Accounts: Yes, UK bank accounts
Complexity: Multi-state operations (CA, NY)
⚠️ RED FLAGS: Unfiled 2023 return
Referral: Existing client recommendation
```

**Fields Used:** foreign_accounts, complexity_signals, red_flags, referral_source

#### 6. FOLLOW-UP QUESTIONS Section

**✅ Phase 1 Update:** Follow-up questions now support config-driven conditions.

```
SUGGESTED FOLLOW-UP QUESTIONS
1. Have you been filing FBAR (FinCEN Form 114) annually?
2. Are you reporting foreign income on your US tax return?
3. Do you have economic nexus in all states you're operating in?
4. Are you current on sales tax filings for all states?
```

**New Config-Driven Format (Recommended):**
```json
{
  "follow_up_rules": [
    {
      "question": "Have you been filing FBAR (FinCEN Form 114) annually?",
      "priority": 1,
      "condition": {
        "field": "foreign_accounts",
        "operator": "exists"
      }
    },
    {
      "question": "Do you have economic nexus in all states you're operating in?",
      "priority": 2,
      "condition": {
        "field": "state",
        "operator": "contains",
        "value": "multi-state"
      }
    }
  ],
  "max_follow_up_questions": 4
}
```

**How It Works:**
1. System evaluates each follow-up rule's condition against extracted fields
2. Questions with matching conditions are collected
3. Questions sorted by priority (lower number = higher priority)
4. Top N questions returned (configurable via `max_follow_up_questions`)

**Supported Operators:** All 16 operators from `ConditionEvaluator` (exists, not_exists, equals, not_equals, contains, not_contains, contains_any, greater_than, less_than, greater_than_or_equal, less_than_or_equal, in_list, not_in_list, regex_match, word_count_gte, word_count_lte, plus compound logic: any_of, all_of)

**Industry Examples:**

**CPA Vertical:**
- "Have you been filing FBAR annually?" (if foreign_accounts exists)
- "Are you taking a reasonable salary?" (if entity_type = "S-Corp")

**Insurance Vertical:**
- "Do you have any pre-existing conditions?" (if health_history exists)
- "What's your current deductible?" (if has_existing_policy = true)

**Real Estate Vertical:**
- "Are you pre-qualified for financing?" (if budget > $500K)
- "Do you have a preferred school district?" (if has_children = true)

**Legacy Format (Still Supported):** Workflows can still use hardcoded pattern matching for backward compatibility.

---

## API Endpoints for Lead Evaluation

**⚠️ UPDATED (2026-01-31):** Conversation endpoints now include `workflow_session_id` for linking to lead evaluations.

### Conversation Endpoints

#### GET /api/personas/{persona_id}/conversations

Returns list of conversations with `workflow_session_id` for each (if a workflow was completed).

```typescript
interface ConversationSummary {
  id: string;                          // Conversation UUID
  persona_id: string;
  session_id: string | null;           // LiveKit session token
  workflow_session_id: string | null;  // NEW: For fetching lead evaluation
  user_email: string | null;
  user_fullname: string | null;
  user_phone: string | null;
  conversation_type: "text" | "voice";
  message_count: number;
  last_message_preview: string | null;
  created_at: string;
  updated_at: string;
}
```

#### GET /api/conversations/{conversation_id}

Returns full conversation details with `workflow_session_id`.

```typescript
interface ConversationDetail extends ConversationSummary {
  messages: Message[];
  conversation_metadata: Record<string, any> | null;
}
```

### Workflow Session Endpoints

#### GET /api/workflows/sessions/{workflow_session_id}

Returns workflow session with `result_data` containing lead evaluation.

```typescript
interface WorkflowSessionResponse {
  id: string;
  workflow_id: string;
  persona_id: string;
  conversation_id: string | null;
  status: "in_progress" | "completed" | "abandoned";
  progress_percentage: number;
  extracted_fields: Record<string, ExtractedField> | null;
  result_data: LeadEvaluationResult | null;  // Contains scoring
  completed_at: string | null;
  updated_at: string;
}
```

### Frontend Flow

```
1. GET /api/personas/{id}/conversations
   └─> Returns list with workflow_session_id for each

2. If workflow_session_id exists:
   └─> GET /api/workflows/sessions/{workflow_session_id}
       └─> result_data contains:
           - lead_score (0-100)
           - lead_quality ("hot" | "warm" | "cold")
           - priority_level ("high" | "medium" | "low")
           - lead_summary (contact, service_need, follow_up_questions)
           - scoring (signals_matched, penalties_applied, reasoning)
```

### Linking Logic

Conversations and workflow sessions are linked via session token:
- `conversations.session_id` = `workflow_sessions.session_token`

The `get_workflow_data_for_conversations()` method in `ConversationRepository` handles this join.

---

## API Layer

**File:** `app/api/models/workflow_models.py`

### Pydantic Models for Conversational Workflows

#### ConversationalField
```python
class ConversationalField(BaseModel):
    field_id: str  # e.g., "contact_name", "entity_type"
    field_type: Literal["text", "email", "phone", "number", "choice", "date"]
    label: str  # Human-readable name
    description: Optional[str]  # Helps LLM extraction
    options: Optional[List[str]]  # For choice fields
    clarifying_question: Optional[str]  # Custom question for UX (Phase 2)
    relevant_when: Optional[Condition]  # Conditional relevance (Phase 4 - Branching)
    validation: Optional[Dict[str, Any]]  # min_length, pattern, etc.
```

**`relevant_when`** — When set, this field is only asked/tracked when the condition evaluates to `True` against currently extracted fields. Uses the same `Condition` model and `ConditionEvaluator` (16 operators + compound logic) used by scoring and follow-up rules. If `None`, field is always relevant.

Example: Only ask about business structure when client type is "Business":
```json
{
  "field_id": "business_structure",
  "field_type": "choice",
  "label": "Business structure",
  "options": ["LLC", "S-Corp", "C-Corp", "Sole Prop", "Partnership"],
  "relevant_when": {
    "field": "client_type",
    "operator": "equals",
    "value": "Business"
  }
}
```

#### ExtractionStrategy
```python
class ExtractionStrategy(BaseModel):
    opening_question: str  # First question to ask user
    max_clarifying_questions: int = 5  # Max follow-ups
    confirmation_required: bool = True  # Show summary before completing
    confirmation_style: Literal["summary", "none"] = "summary"
    extraction_model: str = "gpt-4o-mini"  # LLM model
    confidence_threshold: float = 0.8  # Min confidence (0-1)
    allow_partial_extraction: bool = False  # Complete without optionals?
```

#### OutputTemplate
```python
class OutputTemplate(BaseModel):
    format: Literal["lead_summary"] = "lead_summary"
    sections: List[str]  # Sections to include in summary
    scoring_rules: Dict[str, Any]  # Lead scoring configuration
    export_destinations: List[str] = ["email", "internal_dashboard"]
```

#### Condition (Phase 1 - Config-Driven Rules)
```python
class Condition(BaseModel):
    """Generic condition for quality signals, risk penalties, and follow-up rules."""
    field: Optional[str]  # Field to evaluate (e.g., "revenue_range")
    operator: Optional[str]  # One of 16 operators (exists, contains, equals, etc.)
    value: Optional[Union[str, int, List[str]]]  # Value(s) to compare against
    values: Optional[List[str]]  # For operators like contains_any, in_list
    pattern: Optional[str]  # Regex pattern for regex_match operator

    # Compound conditions
    any_of: Optional[List['Condition']]  # OR logic
    all_of: Optional[List['Condition']]  # AND logic
```

**Supported Operators:** exists, not_exists, equals, not_equals, contains, not_contains, contains_any, greater_than, less_than, greater_than_or_equal, less_than_or_equal, in_list, not_in_list, regex_match, word_count_gte, word_count_lte

#### QualitySignal (Phase 1)
```python
class QualitySignal(BaseModel):
    """Positive scoring signal with config-driven condition."""
    signal_id: str  # Unique identifier (e.g., "revenue_1m_plus")
    points: int  # Points to add if condition matches
    condition: Condition  # Condition to evaluate
```

#### RiskPenalty (Phase 1)
```python
class RiskPenalty(BaseModel):
    """Negative scoring penalty with config-driven condition."""
    penalty_id: str  # Unique identifier (e.g., "red_flag_unfiled_returns")
    points: int  # Negative points to apply if condition matches
    condition: Condition  # Condition to evaluate
```

#### FollowUpRule (Phase 1)
```python
class FollowUpRule(BaseModel):
    """Conditional follow-up question rule."""
    question: str  # Question to ask
    priority: int  # Lower number = higher priority
    condition: Condition  # When to ask this question
```

#### ConversationalWorkflowConfig
```python
class ConversationalWorkflowConfig(BaseModel):
    required_fields: List[ConversationalField]  # MUST be captured
    optional_fields: List[ConversationalField]  # Nice to have
    inference_rules: Dict[str, str]  # field_id → extraction instruction
    extraction_strategy: ExtractionStrategy
```

### Validation Rules

1. **workflow_type = "conversational"** → `output_template` is **REQUIRED**
2. **workflow_type = "conversational"** → `result_config` is **NOT ALLOWED**
3. All `field_id` values must be unique within required_fields and optional_fields
4. Choice fields must have at least 2 options
5. `scoring_rules` must have keys: `base_score`, `field_completeness_weight`, `quality_signals`, `risk_penalties`

---

## Configuration Structure

### Complete Example: CPA Lead Capture Workflow

```json
{
  "workflow_type": "conversational",
  "title": "CPA Lead Qualification",
  "workflow_config": {
    "required_fields": [
      {
        "field_id": "contact_name",
        "field_type": "text",
        "label": "Full name",
        "description": "Contact person's full name"
      },
      {
        "field_id": "contact_email",
        "field_type": "email",
        "label": "Email address"
      },
      {
        "field_id": "contact_phone",
        "field_type": "phone",
        "label": "Phone number"
      },
      {
        "field_id": "entity_type",
        "field_type": "choice",
        "label": "Business entity type",
        "description": "Legal structure of the business",
        "options": ["Sole Proprietor", "LLC", "S-Corp", "C-Corp", "Partnership"],
        "relevant_when": {
          "field": "client_type",
          "operator": "equals",
          "value": "Business"
        }
      },
      {
        "field_id": "service_need",
        "field_type": "text",
        "label": "Service needed",
        "description": "What accounting/tax services are you looking for?"
      }
    ],
    "optional_fields": [
      {
        "field_id": "revenue_range",
        "field_type": "choice",
        "label": "Annual revenue range",
        "options": ["<$100K", "$100K-$500K", "$500K-$1M", "$1M-$5M", "$5M+"]
      },
      {
        "field_id": "state",
        "field_type": "text",
        "label": "State(s) of operation"
      },
      {
        "field_id": "foreign_accounts",
        "field_type": "text",
        "label": "Foreign bank accounts or assets"
      },
      {
        "field_id": "red_flags",
        "field_type": "text",
        "label": "Compliance issues or red flags"
      },
      {
        "field_id": "timeline",
        "field_type": "text",
        "label": "Timeline or urgency"
      },
      {
        "field_id": "bookkeeping_status",
        "field_type": "text",
        "label": "Current bookkeeping status"
      }
    ],
    "inference_rules": {
      "entity_type": "Extract if user mentions 'LLC', 'S-Corp', 'C-Corp', etc. If unclear, ask: 'What's your business structure?'",
      "revenue_range": "Infer from cues: 'small team' → $100K-$500K, '10+ employees' → $500K+, explicit amounts",
      "state": "Extract from location mentions. If user says city, infer state (e.g., 'San Jose' → California)",
      "foreign_accounts": "Extract if user mentions foreign bank accounts, FBAR, offshore assets, international income",
      "red_flags": "Extract mentions of: unfiled returns, IRS notices, audit, messy books, payroll issues"
    },
    "extraction_strategy": {
      "opening_question": "Thanks for reaching out! What's going on with your business that made you look for a CPA?",
      "max_clarifying_questions": 5,
      "confirmation_required": true,
      "confirmation_style": "summary",
      "extraction_model": "gpt-4o-mini",
      "confidence_threshold": 0.8,
      "allow_partial_extraction": false
    }
  },
  "output_template": {
    "format": "lead_summary",
    "sections": ["profile", "situation", "need", "score", "key_context", "follow_up_questions"],
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
          "signal_id": "revenue_500k_plus",
          "points": 10,
          "condition": {
            "field": "revenue_range",
            "operator": "contains_any",
            "values": ["$500K", "$1M", "$5M"]
          }
        },
        {
          "signal_id": "multi_state",
          "points": 10,
          "condition": {
            "field": "state",
            "operator": "contains",
            "value": "multi-state"
          }
        },
        {
          "signal_id": "foreign_accounts_fbar",
          "points": 15,
          "condition": {
            "field": "foreign_accounts",
            "operator": "exists"
          }
        },
        {
          "signal_id": "urgent_timeline",
          "points": 10,
          "condition": {
            "field": "timeline",
            "operator": "contains_any",
            "values": ["Immediate", "ASAP"]
          }
        }
      ],
      "risk_penalties": [
        {
          "penalty_id": "red_flag_unfiled_returns",
          "points": -20,
          "condition": {
            "field": "red_flags",
            "operator": "contains",
            "value": "unfiled"
          }
        },
        {
          "penalty_id": "red_flag_irs_notice",
          "points": -15,
          "condition": {
            "field": "red_flags",
            "operator": "contains_any",
            "values": ["irs notice", "irs letter"]
          }
        },
        {
          "penalty_id": "red_flag_messy_books",
          "points": -10,
          "condition": {
            "any_of": [
              {"field": "red_flags", "operator": "contains", "value": "mess"},
              {"field": "bookkeeping_status", "operator": "contains", "value": "behind"}
            ]
          }
        },
        {
          "penalty_id": "incomplete_contact",
          "points": -5,
          "condition": {
            "any_of": [
              {"field": "contact_email", "operator": "not_exists"},
              {"field": "contact_phone", "operator": "not_exists"}
            ]
          }
        }
      ]
    },
    "follow_up_rules": [
      {
        "question": "Have you been filing FBAR (FinCEN Form 114) annually for your foreign accounts?",
        "priority": 1,
        "condition": {
          "field": "foreign_accounts",
          "operator": "exists"
        }
      },
      {
        "question": "Are you taking a reasonable salary as required for S-Corps?",
        "priority": 2,
        "condition": {
          "field": "entity_type",
          "operator": "equals",
          "value": "S-Corp"
        }
      },
      {
        "question": "Do you have economic nexus established in all states you're operating in?",
        "priority": 3,
        "condition": {
          "field": "state",
          "operator": "contains",
          "value": "multi-state"
        }
      },
      {
        "question": "Are you current on all payroll tax filings?",
        "priority": 4,
        "condition": {
          "field": "service_need",
          "operator": "contains",
          "value": "payroll"
        }
      }
    ],
    "max_follow_up_questions": 4,
    "export_destinations": ["email", "internal_dashboard"]
  }
}
```

---

## What This System IS

### ✅ 1. LLM-Powered Field Extraction Engine
- Uses OpenAI structured outputs (gpt-4o-mini) to extract fields from natural language
- Confidence scoring for each field (0.0-1.0)
- Incremental extraction across multiple messages
- Merges new extractions with existing fields

### ✅ 2. Intelligent Clarifying Question System
- Automatically detects missing required fields
- Supports custom clarifying questions per field (Phase 2)
- Falls back to template-based questions if custom not provided
- **Enhancement Available:** LLM-generated context-aware questions

### ✅ 3. Multi-Factor Lead Scoring Algorithm
- Base score + field completeness bonus
- Quality signals (revenue, multi-state, foreign accounts, etc.)
- Risk penalties (unfiled returns, IRS notice, messy books)
- Priority classification (low/medium/high)

### ✅ 4. Configurable Inference Rules
- Natural language extraction instructions per field
- Guides LLM on how to extract each field
- Example: "Infer revenue_range from cues like 'small team' → $100K-$500K"

### ✅ 5. Industry-Agnostic Configuration (Phase 1 - Fully Multi-Vertical)
- All business logic in JSONB (workflow_config, output_template)
- Generic `ConditionEvaluator` with 16 operators - zero industry knowledge
- Config-driven quality signals and risk penalties
- Config-driven follow-up questions with condition-based evaluation
- Backward compatible with legacy CPA-specific format
- **Works for:** CPA, insurance, real estate, healthcare, any industry

### ✅ 6. Incremental Session Progress Tracking
- `extracted_fields` updated after each message
- `progress_percentage` calculated as `(captured / total) × 100`
- `missing_required_fields` list shrinks as fields are captured

### ✅ 7. Formatted Lead Summary Generation
- 6 configurable sections (profile, situation, need, score, key_context, follow_up_questions)
- Professional formatting with headers, bullets, emojis
- Exportable to email, dashboard, CRM

### ✅ 8. Database-Backed Session Management
- Sessions stored in `workflow_sessions` table
- JSONB columns for flexible schema (extracted_fields, result_data)
- GIN indexes for efficient JSONB queries

### ✅ 9. Sentry Monitoring Integration
- All exception paths have `capture_exception_with_context()`
- Proper tagging (component, operation, severity, user_facing)
- PII in `extra` (redactable), no PII in tags

### ✅ 10. Pydantic Validation & Type Safety
- Comprehensive Pydantic models for all API requests/responses
- Field validation (unique field IDs, choice options, scoring rules)
- Type hints throughout codebase

### ✅ 11. Correction Detection & Field Re-Extraction (Phase 2)
- Detects 13 correction patterns ("actually", "sorry", "I meant", etc.)
- Automatically re-extracts fields when corrections detected
- `allow_overwrite` parameter enables field updates
- Natural conversation flow for mistake correction

### ✅ 12. Confirmation Flow Before Completion (Phase 3)
- Optional confirmation mode (configurable per workflow)
- Shows formatted summary of all captured fields before completion
- Detects affirmative responses (17 patterns) for confirmation
- Detects negative responses (8 patterns) for corrections
- State machine with `awaiting_confirmation` flag
- Allows corrections during confirmation mode
- Professional, trustworthy user experience

### ✅ 13. LiveKit Voice Agent Integration (NEW - Jan 2026)
- **Modular handler architecture**: WorkflowHandler delegates to ConversationalWorkflowCoordinator
- **Voice-first UX**: TTS clarifying questions, voice responses
- **Dual mode support**: Same handler for voice and text conversations
- **Stateful sessions**: Maintains workflow context during voice calls
- **Callback pattern**: Output method handles voice/text automatically
- **Linear + Conversational**: Supports both workflow types in LiveKit
- **81% code reduction**: New modular agent (561 lines vs 2,921 legacy)
- **Shared services**: Reuses field extraction & scoring across API and voice

---

## What This System IS NOT

### ❌ 1. NOT Using LLM for Clarifying Questions (During Extraction)
**Current:** Template-based or custom questions like "What's your email address?" or "Got it! What's the best email to reach you at?"
**Potential Enhancement:** Fully context-aware questions generated by LLM based on conversation flow

### ❌ 2. NOT Supporting Conditional Field Logic
**Current:** All required fields must be captured
**Potential Enhancement:** "If entity_type = S-Corp, then payroll_status is required"

### ❌ 3. NOT Supporting Multi-Language Extraction
**Current:** English only
**Potential Enhancement:** Extract from Spanish, French, etc. conversations

### ❌ 4. NOT Supporting Real-Time Validation
**Current:** Validation happens at completion
**Potential Enhancement:** Validate fields as they're extracted (e.g., email format, phone number)

### ✅ 5. NOW INTEGRATED with LiveKit Voice Agent (NEW - Jan 2026)
**Status:** ✅ COMPLETE - Fully integrated via WorkflowHandler
**Implementation:** Voice-to-text → extract fields → text-to-speech clarifying questions
**Files:** `livekit/handlers/workflow_handler.py`, `livekit/services/conversational_workflow_coordinator.py`

### ❌ 6. NOT Supporting CRM Export
**Current:** summary stored in database only
**Potential Enhancement:** Auto-export to HubSpot, Salesforce, etc.

### ❌ 7. NOT Supporting Analytics Dashboard
**Current:** Raw data in database
**Potential Enhancement:** Lead conversion rates, field capture success rates, average session length

---

## Implementation Files

### Created/Modified Files

#### Production Implementation (Current - Jan 2026)

**Note:** The `shared/workflows/` directory was **deleted** in Jan 2026 migration. All functionality consolidated into `livekit/services/`.

**⚠️ UPDATED (2026-01-31):** Scoring is now LLM-only via `LeadScoringService`. Rule-based `workflow_scoring_engine.py` and `workflow_summary_service.py` have been deleted.

| File | Status | Lines | Description |
|------|--------|-------|-------------|
| `livekit/livekit_agent.py` | ✅ Active | 561 | Modular LiveKit agent (81% smaller than legacy) |
| `livekit/handlers/__init__.py` | ✅ Active | 16 | Handler exports |
| `livekit/handlers/workflow/conversational_handler.py` | ✅ Active | ~400 | **PRODUCTION:** Conversational workflow orchestration |
| `livekit/handlers/workflow/linear_handler.py` | ✅ Active | ~300 | **PRODUCTION:** Linear/scored workflow handler |
| `livekit/handlers/tool_handler.py` | ✅ Active | 173 | Function tools (search, calendar) |
| `livekit/handlers/session_context.py` | ✅ Active | 42 | Session state tracking |
| `livekit/services/__init__.py` | ✅ Active | - | LiveKit services exports (LeadScoringService, etc.) |
| `livekit/services/lead_scoring_service.py` | ✅ Active | 566 | **NEW:** LLM-only lead scoring with Pydantic models |
| `livekit/services/workflow_field_extractor.py` | ✅ Active | 429 | **PRODUCTION:** Field extraction with Pydantic & Sentry |
| `livekit/services/workflow_condition_evaluator.py` | ✅ Active | 315 | **PRODUCTION:** Generic rule engine (16+ operators) |
| `livekit/services/workflow_tone_service.py` | ✅ Active | - | Conversation tone/style management |
| `app/api/models/workflow_models.py` | ✅ Active | 841 | Pydantic models (Condition, FollowUpRule, QualitySignal, etc.) |
| `app/services/livekit_orchestrator.py` | ✅ Active | - | Agent version switching (modular vs legacy) |

#### Database & Infrastructure

| File | Status | Lines | Description |
|------|--------|-------|-------------|
| `alembic/versions/7ac6c5e769e2_add_conversational_workflow_support.py` | ✅ Applied | 95 | Database migration (output_template, extracted_fields) |
| `shared/database/models/workflow.py` | ✅ Active | 369 | SQLAlchemy ORM models |
| `shared/database/repositories/workflow_repository.py` | ✅ Active | - | Database operations (including `update_session_lead_evaluation`) |
| `shared/database/repositories/conversation_repository.py` | ✅ Active | - | Conversation queries with workflow session linking |

#### Deleted Files (Jan 2026 Migration)

| File | Status | Reason |
|------|--------|--------|
| `shared/workflows/*` | ❌ **DELETED** | Code duplication eliminated - functionality moved to `livekit/services/` |
| `livekit/services/workflow_scoring_engine.py` | ❌ **DELETED** | Replaced by LLM-only `LeadScoringService` |
| `livekit/services/workflow_summary_service.py` | ❌ **DELETED** | Replaced by LLM-generated summaries in `LeadScoringService` |
| `livekit/services/lead_enrichment_service.py` | ❌ **DELETED** | Merged into `LeadScoringService` |

### Key Methods Added to Repository

```python
# shared/database/repositories/workflow_repository.py

async def update_extracted_fields(
    session_id: UUID,
    extracted_fields: Dict[str, Any],
    progress_percentage: int
) -> None:
    """Update session with incrementally extracted fields."""

async def update_session_lead_evaluation(
    session_id: UUID,
    evaluation_data: Dict[str, Any]
) -> Optional[WorkflowSession]:
    """
    Store complete LLM lead evaluation in result_data.
    Called by background task after LeadScoringService completes.
    
    Schema stored:
    {
        "lead_score": int,
        "priority_level": "high" | "medium" | "low",
        "lead_quality": "hot" | "warm" | "cold",
        "urgency_level": "high" | "medium" | "low",
        "lead_summary": {...},
        "scoring": {...},
        "confidence": float,
        "evaluated_at": str
    }
    """

async def update_session_metadata(
    session_id: UUID,
    session_metadata: Dict[str, Any]
) -> None:
    """Update session metadata (Phase 3: used for awaiting_confirmation flag)."""
```

---

## Error Handling & Monitoring

### Sentry Integration

All production services include comprehensive Sentry monitoring:

**Coverage:**
- Field extraction failures (OpenAI API errors, malformed responses)
- Scoring calculation errors
- Database operation failures
- Session state errors

**Example from WorkflowFieldExtractor:**
```python
except Exception as e:
    self.logger.error(f"Field extraction failed: {e}", exc_info=True)
    capture_exception_with_context(
        e,
        extra={
            "user_message": user_message[:200],
            "required_fields_count": len(required_fields),
            "optional_fields_count": len(optional_fields),
        },
        tags={
            "component": "workflow_field_extractor",
            "operation": "extract_fields",
            "severity": "high",
            "user_facing": "true",
        },
    )
    # Return empty result on error
    return FieldExtractionResult(
        extracted_fields={},
        missing_required_fields=[f["field_id"] for f in required_fields],
        missing_optional_fields=[f["field_id"] for f in optional_fields],
    )
```

### OpenAI API Failure Handling

**Field Extraction:**
- If OpenAI API fails → returns empty `FieldExtractionResult` with all fields marked as missing
- User experience: Workflow continues, system asks clarifying questions for all required fields
- Error logged to Sentry with full context

**No Retry Logic (Current):**
- Single attempt per message (no automatic retries)
- Rationale: Failures are rare, retries add latency
- Future enhancement: Could add retry with exponential backoff

### Malformed Data Handling

**Pydantic Validation:**
- All extracted fields validated with Pydantic models
- Invalid confidence scores (< 0 or > 1) → validation error
- Missing required model fields → validation error
- Type mismatches → validation error

**Fallback Behavior:**
- Validation errors treated as extraction failures
- System falls back to empty extraction result
- Next clarifying question is asked

### Session Timeout Handling

**Current Behavior:**
- No explicit timeout mechanism
- Sessions persist until explicitly completed or abandoned
- Database tracks `created_at`, `updated_at`, `completed_at`

**Future Enhancement:**
- Could implement auto-expiry for abandoned sessions (e.g., 24 hours)
- Could send reminder notifications for incomplete sessions

### Database Error Handling

**Repository Pattern:**
- All database operations wrapped in try/except blocks
- Errors captured to Sentry with context
- Failed database operations logged with session details

**Transaction Management:**
- Uses SQLAlchemy async sessions with context managers
- Automatic rollback on exceptions
- Connection pooling for reliability

---

## Testing Framework (Jan 2026)

### Overview

A comprehensive testing framework for conversational workflows using LiveKit's `AgentSession` testing capabilities.

### Test Files

| File | Type | Tests | Description |
|------|------|-------|-------------|
| `livekit/tests/unit/test_conversational_handler.py` | Unit | 34 | Tone, summary templates, no-redundant-questions |
| `livekit/tests/unit/test_scoring_engine.py` | Unit | 27 | Config-driven scoring engine |
| `livekit/tests/integration/test_cpa_lead_capture.py` | Integration | 24 | End-to-end tests with real LLM |
| `livekit/tests/integration/test_confirmation_flow.py` | Integration | 6 | Confirmation handling |
| `livekit/tests/TEST_SCENARIOS.md` | Documentation | - | All test scenarios with results |
| `livekit/tests/fixtures/cpa_workflow.py` | Fixtures | - | CPA workflow configurations |
| `livekit/tests/fixtures/mock_repositories.py` | Mocks | - | Mock database repositories |

### Test Categories

#### Unit Tests (No API Key Required)
- **Tone Controls**: All 4 presets (concierge, professional, casual, efficient)
- **Summary Templates**: All 4 formats (structured, synopsis, minimal, detailed)
- **No Redundant Questions**: Asked field tracking, update intent detection
- **Scoring Engine**: Base score, quality signals, risk penalties, field completeness

#### Integration Tests (Requires OPENAI_API_KEY)
- **Basic Lead Capture**: Name extraction, multi-field extraction, full conversation flow
- **Field Correction**: User corrects previously provided information
- **Confirmation Flow**: Yes/yep/correct confirmations, rejection handling
- **Inference Rules**: City-to-state inference, name extraction from intro
- **Hallucination Controls**: Don't fabricate revenue, entity type when not mentioned

### Running Tests

```bash
# Run all tests (unit + integration)
poetry run pytest livekit/tests/ -v

# Run only unit tests (no API key needed)
poetry run pytest livekit/tests/unit/ -v

# Run integration tests with verbose output
LIVEKIT_EVALS_VERBOSE=1 poetry run pytest livekit/tests/integration/ -v -s
```

### Test Results Summary

```
======================== 91 passed ========================
- 61 unit tests
- 30 integration tests
```

---

## Summary

### Current State (Phase 1-3 Complete)
✅ **Production-ready conversational workflow system** with:
- LLM-powered field extraction (OpenAI structured outputs)
- Confidence scoring and incremental capture
- Multi-factor lead scoring with config-driven rules
- Professional summary generation
- Database-backed session management
- Production-ready Sentry monitoring
- **Phase 1:** Config-driven multi-vertical architecture (ConditionEvaluator)
- **Phase 2:** UX improvements (custom questions, correction detection)
- **Phase 3:** Confirmation flow before completion

### Phase 1: Multi-Vertical Architecture ✅ COMPLETE
**Problem Solved:** Hardcoded CPA-specific logic in scoring and follow-up questions

**Implementation:**
- Generic `ConditionEvaluator` with 16 operators
- Config-driven quality signals and risk penalties
- Config-driven follow-up questions with condition evaluation
- Backward compatible with legacy CPA format

**Impact:** System now supports **any industry** (CPA, insurance, real estate, healthcare) without code changes

### Phase 2: UX Improvements ✅ COMPLETE
**Problem Solved:** Robotic questions and inability to correct extracted fields

**Implementation:**
- Custom `clarifying_question` field for conversational questions
- 13 correction patterns detected ("actually", "sorry", "I meant", etc.)
- `allow_overwrite` parameter for field re-extraction

**Impact:** Natural conversation flow, users can correct mistakes mid-conversation

### Phase 3: Confirmation Flow ✅ COMPLETE
**Problem Solved:** No review opportunity before workflow completion

**Implementation:**
- State machine with `awaiting_confirmation` flag
- Formatted confirmation summary
- 17 affirmative patterns, 8 negative patterns detected
- Correction support during confirmation mode
- Configurable per workflow (`confirmation_required`)

**Impact:** Professional, trustworthy experience - users review before submission

### LiveKit Integration ✅ COMPLETE (Jan 2026)
**Problem Solved:** Conversational workflows only worked via REST API

**Implementation:**
- New modular LiveKit agent (`livekit_agent.py` - 561 lines, 81% smaller)
- WorkflowHandler for both linear and conversational workflows
- ConversationalWorkflowCoordinator for field extraction & scoring
- Voice-first UX with TTS clarifying questions
- Stateful session management during voice conversations

**Impact:** Conversational workflows now work seamlessly in voice calls via LiveKit

### Testing Framework ✅ COMPLETE (Jan 2026)
**Problem Solved:** No automated testing for conversational workflow behavior

**Implementation:**
- Unit tests for tone controls, summary templates, scoring engine (61 tests)
- Integration tests using LiveKit's AgentSession framework (30 tests)
- Simplified TestLeadCaptureAgent for isolated testing
- CPA workflow fixtures and mock repositories
- Comprehensive test scenarios documentation

**Impact:** Reliable, repeatable testing of agent behavior including edge cases

### Workflow Enhancements ✅ COMPLETE (Jan 2026)
**Problem Solved:** Rigid conversation style, hardcoded scoring, repetitive questions

**Implementation:**
- **Tone Controls**: 4 presets (concierge, professional, casual, efficient)
- **Summary Templates**: 4 formats (structured, synopsis, minimal, detailed)
- **No Redundant Questions**: Track asked fields, detect update intent
- **Config-Driven Scoring**: All rules from workflow config, no hardcoded patterns
- **Admin API Access**: Service auth for template/workflow management

**Documentation:** See `docs/workflows/WORKFLOW_ENHANCEMENTS.md` for full details

**Impact:** Customizable conversation style per client, maintainable scoring rules

### Phase 4: Conditional Field Branching (`relevant_when`) ✅ COMPLETE (Feb 2026)
**Problem Solved:** All fields were flat — no way to branch based on client type (e.g., Individual vs Business vs Foreign Disclosure)

**Implementation:**
- Added `relevant_when: Optional[Condition]` to `ConversationalField` model
- Reuses existing `Condition` model and `ConditionEvaluator` (16 operators + compound logic)
- `_get_relevant_fields()` in `ConversationalWorkflowHandler` filters fields at runtime
- Only relevant required fields count toward progress percentage
- LLM prompt displays conditions inline so the agent knows which fields to pursue per client type
- No migration needed — `relevant_when` lives inside JSONB `workflow_config`

**Key Files:**
- `app/api/models/workflow_models.py` — `ConversationalField.relevant_when`
- `livekit/handlers/workflow/conversational_handler.py` — `_get_relevant_fields()`, filtered progress in `store_extracted_fields()`
- `shared/generation/workflow_promotion_prompts.py` — conditional display in LLM execution instructions

**Impact:** Single workflow config can handle multiple client types (CPA example: Individual asks about AGI/income sources, Business asks about entity type/bookkeeping, Foreign Disclosure asks about visa/account balance)

### Bug Fix: Workflow Session ↔ Conversation Linking (Feb 2026)
**Problem Solved:** `workflow_sessions.conversation_id` was always NULL, so conversation API couldn't join to show extracted fields and lead scores

**Root Cause:** `WorkflowSession` is created when workflow starts (before conversation exists). `Conversation` record is created during shutdown callback. Nothing linked them afterward.

**Fix:**
- Shutdown callback (`livekit/entrypoint.py`) now updates `WorkflowSession.conversation_id` after saving the conversation
- Added `WorkflowRepository.update_session_conversation_id()` method
- Conversation query uses `OR` fallback: joins on `conversation_id` or `session_token` (covers existing records)
- Conversation API responses now include `extracted_fields` and `result_data` from workflow session

### Next Steps
1. ✅ ~~Integrate with LiveKit voice agent~~ - COMPLETE (Jan 2026)
2. ✅ ~~Add automated testing framework~~ - COMPLETE (Jan 2026)
3. ✅ ~~Add tone controls and summary templates~~ - COMPLETE (Jan 2026)
4. Test with insurance/real estate workflows using new config-driven approach
5. ✅ ~~Add conditional field logic ("if entity_type = S-Corp, then...")~~ - COMPLETE (Feb 2026)
6. Add CRM export capabilities

---

**Last Updated:** 2026-02-24
**Author:** Claude Code (AI Assistant)
**Review Status:** ✅ Phase 1-4 Complete + Enhancements
