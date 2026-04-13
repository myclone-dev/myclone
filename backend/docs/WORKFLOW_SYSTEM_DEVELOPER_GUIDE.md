# Workflow System - Developer Guide

> **Production implementation guide for the voice-based workflow system**
>
> Last Updated: January 28, 2026

---

## Overview

The Workflow System enables personas to conduct **structured questionnaires and assessments via voice conversation**. Instead of traditional forms, users answer questions through natural dialogue with AI agents.

**Current Status**: ✅ **Fully Implemented** (Database, API, LiveKit voice integration)

**Not Implemented**: ❌ Actions system (email, CRM, calendar automation) - planned for future

---

## Architecture

### System Flow

```
1. User connects to LiveKit room
   ↓
2. Agent loads active workflow (if persona has one)
   ↓
3. Agent promotes workflow during conversation
   ↓
4. User says "start assessment" → start_assessment() called
   ↓
5. Agent asks questions one by one via TTS
   ↓
6. User answers via voice → LLM extracts answer
   ↓
7. submit_workflow_answer() saves to database
   ↓
8. Repeat 5-7 until all questions answered
   ↓
9. Calculate score (for scored workflows)
   ↓
10. Announce results to user
```

### Components

| Component | File | Purpose |
|-----------|------|---------|
| **Database Models** | `shared/database/models/workflow.py` | PersonaWorkflow, WorkflowSession tables |
| **Repository** | `shared/database/repositories/workflow_repository.py` | CRUD + analytics operations |
| **API Routes** | `app/api/workflow_routes.py` | REST endpoints for workflow management |
| **API Models** | `app/api/models/workflow_models.py` | Pydantic schemas (includes TriggerConfig) |
| **Modular Agent** | `livekit/livekit_agent.py` | Voice/text agent with thin tool wrappers |
| **Workflow Factory** | `livekit/handlers/workflow/__init__.py` | Creates Linear or Conversational handler |
| **Base Handler** | `livekit/handlers/workflow/base.py` | Shared workflow session management |
| **Linear Handler** | `livekit/handlers/workflow/linear_handler.py` | Step-by-step Q&A assessments |
| **Conversational Handler** | `livekit/handlers/workflow/conversational_handler.py` | Lead capture field extraction |
| **Prompt Manager** | `livekit/managers/prompt_manager.py` | System prompt with workflow promotion |
| **Data Loader** | `livekit/helpers/persona_data_extractor.py` | Loads workflow with persona data |
| **Objective Generator** | `shared/generation/workflow_objective_generator.py` | LLM-based objective generation (database storage) |
| **Promotion Prompts** | `shared/generation/workflow_promotion_prompts.py` | Runtime prompt injection (system prompt) |
| **Restaurant Workflow Config** | `docs/workflows/RESTAURANT_ORDER_WORKFLOW.md` | Menu, rules, fields — all in config JSON |
| **Migration** | `alembic/versions/132600cde686_*.py` | Database schema creation |

**Note:** The legacy monolithic agent (`livekit/livekit_agent_retrieval.py`) still exists but the modular agent (`livekit/livekit_agent.py`) is the primary production implementation.

---

## Database Schema

### persona_workflows

Stores workflow definitions (questions, scoring, categories).

```python
# shared/database/models/workflow.py
class PersonaWorkflow(Base):
    id: UUID
    persona_id: UUID  # Persona that owns this workflow

    workflow_type: str  # 'simple' or 'scored'
    title: str  # "Business Readiness Assessment"
    description: str  # Internal description
    opening_message: str  # "Let's understand where you're at"
    workflow_objective: str  # LLM-generated text to guide chat_objective

    workflow_config: dict  # JSONB: {steps: [{step_id, question_text, options}]}
    result_config: dict  # JSONB: {categories: [{name, min_score, max_score, message}]}
    trigger_config: dict  # JSONB: {promotion_mode, max_attempts, cooldown_turns}

    is_active: bool  # Only one active workflow per persona
    published_at: datetime  # When published (null = draft)
```

**workflow_config structure**:
```json
{
  "steps": [
    {
      "step_id": "q1",
      "step_type": "multiple_choice",
      "question_text": "Can you explain your business in one sentence?",
      "options": [
        {"label": "A", "text": "No", "score": 1},
        {"label": "B", "text": "Somewhat", "score": 2},
        {"label": "C", "text": "Yes", "score": 4}
      ]
    }
  ]
}
```

**result_config structure** (scored workflows only):
```json
{
  "categories": [
    {
      "name": "Beginner",
      "min_score": 14,
      "max_score": 26,
      "message": "You're at the foundation stage..."
    },
    {
      "name": "Intermediate",
      "min_score": 27,
      "max_score": 40,
      "message": "You've got traction but..."
    }
  ]
}
```

**trigger_config structure** (optional):
```json
{
  "promotion_mode": "proactive",
  "max_attempts": 3,
  "cooldown_turns": 5
}
```

**promotion_mode options**:
- `"proactive"`: Push immediately within 1-2 turns (default for scored workflows)
- `"contextual"`: Suggest when conversation naturally aligns (default for simple workflows)
- `"reactive"`: Wait for user to explicitly ask (for booking/scheduling tools)

**Smart defaults**: If `trigger_config` is not provided:
- Scored workflows → `proactive` mode (assessments should be offered early)
- Simple workflows → `contextual` mode (forms suggested when relevant)

### workflow_sessions

Tracks individual workflow executions.

```python
class WorkflowSession(Base):
    id: UUID
    workflow_id: UUID
    persona_id: UUID
    conversation_id: UUID  # Optional: links to chat conversation
    user_id: UUID  # Optional: authenticated user

    status: str  # 'in_progress', 'completed', 'abandoned'
    current_step_id: str  # "q3"
    progress_percentage: int  # 0-100

    collected_data: dict  # JSONB: all user answers
    result_data: dict  # JSONB: final score, category, message

    started_at: datetime
    completed_at: datetime
```

**collected_data structure**:
```json
{
  "q1": {
    "answer": "B",
    "raw_answer": "We can describe it but not consistently",
    "score": 2,
    "answered_at": "2025-12-10T10:05:00Z"
  },
  "q2": {
    "answer": "A",
    "score": 1,
    "answered_at": "2025-12-10T10:06:00Z"
  }
}
```

**result_data structure** (after completion):
```json
{
  "total_score": 38,
  "max_possible_score": 56,
  "percentage": 67.8,
  "category": "Intermediate",
  "category_message": "You've got traction but scaling is still fragile..."
}
```

**See**: `shared/database/models/workflow.py:1-369`

---

## Repository Layer

### Key Methods

**Creating a workflow**:
```python
# shared/database/repositories/workflow_repository.py:36

workflow_repo = WorkflowRepository(session)

workflow = await workflow_repo.create_workflow(
    persona_id=persona.id,
    workflow_type="scored",  # or "simple"
    title="Business Readiness Assessment",
    workflow_config={
        "steps": [...]  # Question definitions
    },
    result_config={
        "categories": [...]  # Score ranges
    },
    workflow_objective="Your goal is to guide users to take the assessment...",
)
```

**Starting a session**:
```python
# shared/database/repositories/workflow_repository.py:338

session = await workflow_repo.create_session(
    workflow_id=workflow.id,
    persona_id=persona.id,
    conversation_id=None,  # Optional
    user_id=None,  # Optional
)
# Returns: WorkflowSession with status='in_progress'
```

**Saving answers**:
```python
# shared/database/repositories/workflow_repository.py:471

await workflow_repo.save_answer(
    session_id=session.id,
    step_id="q1",
    answer="B",
    raw_answer="We can describe it but...",
    score=2,
)
# Auto-increments progress, moves to next step
# Auto-completes if last question
```

**Score calculation** (automatic on last answer):
```python
# shared/database/repositories/workflow_repository.py:554

# Called automatically by save_answer() for scored workflows
result_data = await workflow_repo._calculate_score(session, workflow)

# Returns:
{
    "total_score": 38,
    "max_possible_score": 56,
    "percentage": 67.8,
    "category": "Intermediate",
    "category_message": "..."
}
```

**Analytics**:
```python
# shared/database/repositories/workflow_repository.py:648

analytics = await workflow_repo.get_workflow_analytics(workflow.id)

# Returns:
{
    "total_sessions": 247,
    "completed_sessions": 168,
    "completion_rate": 68.0,
    "avg_score": 34.5,
    "avg_completion_time_seconds": 552,
    "score_distribution": {
        "Beginner": 42,
        "Intermediate": 128
    },
    "drop_off_by_step": {
        "q5": 8,
        "q9": 12
    }
}
```

**See**: `shared/database/repositories/workflow_repository.py:1-733`

---

## API Layer

### Endpoints

```python
# app/api/workflow_routes.py

# Workflow CRUD
POST   /api/v1/workflows              # Create workflow
GET    /api/v1/workflows/{id}         # Get workflow
GET    /api/v1/workflows              # List workflows (by persona or user)
PATCH  /api/v1/workflows/{id}         # Update workflow
DELETE /api/v1/workflows/{id}         # Delete workflow
POST   /api/v1/workflows/{id}/publish # Publish workflow

# Workflow objectives
POST   /api/v1/workflows/{id}/regenerate-objective  # Regenerate LLM objective

# Sessions
POST   /api/v1/workflows/sessions                   # Start session
GET    /api/v1/workflows/sessions/{id}              # Get session
GET    /api/v1/workflows/sessions                   # List sessions
POST   /api/v1/workflows/sessions/{id}/answer       # Submit answer
POST   /api/v1/workflows/sessions/{id}/abandon      # Abandon session

# Analytics
GET    /api/v1/workflows/{id}/analytics             # Get workflow analytics
```

### Creating a Workflow

```bash
POST /api/v1/workflows?persona_id={uuid}
Content-Type: application/json

{
  "workflow_type": "scored",
  "title": "Business Readiness Assessment",
  "opening_message": "Before we dive in, let's understand where you're at.",
  "workflow_config": {
    "steps": [
      {
        "step_id": "q1",
        "step_type": "multiple_choice",
        "question_text": "Can you explain your business in one sentence?",
        "options": [
          {"label": "A", "text": "No", "score": 1},
          {"label": "B", "text": "Somewhat", "score": 2}
        ]
      }
    ]
  },
  "result_config": {
    "categories": [
      {
        "name": "Beginner",
        "min_score": 0,
        "max_score": 10,
        "message": "You're at the foundation stage..."
      }
    ]
  },
  "trigger_config": {
    "promotion_mode": "proactive",
    "max_attempts": 3,
    "cooldown_turns": 5
  }
}
```

**Auto-generates workflow_objective**: If not provided, the API uses an LLM to generate `workflow_objective` based on the workflow structure, persona style, **and promotion_mode**.

```python
# app/api/workflow_routes.py:106-119

# Extract promotion_mode from trigger_config
promotion_mode = None
if workflow_data.trigger_config:
    promotion_mode = workflow_data.trigger_config.promotion_mode

# Generate objective using LLM with promotion_mode
if not workflow_data.workflow_objective:
    workflow_objective = await generate_workflow_objective(
        workflow_data=workflow_dict,
        persona_style=persona.description,
        promotion_mode=promotion_mode,  # Passed to LLM for mode-specific objective
    )
```

**Smart Defaults**: If `trigger_config` is not provided:
- Scored workflows → `promotion_mode="proactive"` (assessments should be offered early)
- Simple workflows → `promotion_mode="contextual"` (forms suggested when relevant)
- `max_attempts=3`, `cooldown_turns=5` used as fallback defaults

**See**:
- API endpoint: `app/api/workflow_routes.py:59-141`
- Objective generator: `shared/generation/workflow_objective_generator.py`

---

## LiveKit Integration

### Loading Workflow Data

When a user connects to LiveKit, the agent loads the active workflow:

```python
# livekit/helpers/persona_data_extractor.py:236

async def _load_active_workflow(persona_id: str) -> Optional[Dict]:
    """Load active (published) workflow for a persona"""
    workflow_repo = WorkflowRepository(session)

    workflows = await workflow_repo.get_workflows_by_persona(
        persona_id=UUID(persona_id),
        active_only=True,
        limit=1
    )

    if not workflows:
        return None

    workflow = workflows[0]
    return {
        "workflow_id": str(workflow.id),
        "title": workflow.title,
        "workflow_type": workflow.workflow_type,
        "opening_message": workflow.opening_message,
        "workflow_objective": workflow.workflow_objective,
        "steps": workflow.workflow_config.get("steps", []),
        "result_config": workflow.result_config or {},
    }
```

**See**: `livekit/helpers/persona_data_extractor.py:236-280`

### Agent Initialization

```python
# livekit/livekit_agent_retrieval.py:120

def __init__(
    self,
    workflow_data: Optional[Dict[str, Any]] = None,
    ...
):
    self.workflow_data = workflow_data
    self._workflow_available = bool(workflow_data)
    self._workflow_session_id = None  # Set when workflow starts
    self._workflow_current_step = None  # Current question index
    self._workflow_answers = {}  # Collected answers
```

**See**: `livekit/livekit_agent_retrieval.py:109-148`

### Workflow Objective Override

If a workflow has `workflow_objective`, it **completely replaces** the persona's `chat_objective`:

```python
# livekit/livekit_agent_retrieval.py:464

if (
    self._workflow_available
    and self.workflow_data
    and self.workflow_data.get("workflow_objective")
):
    # Clone persona_prompt_info
    modified_prompt_info = copy(self.persona_prompt_info)

    # OVERRIDE chat_objective with workflow_objective
    modified_prompt_info.chat_objective = self.workflow_data["workflow_objective"]

    logger.info("🎯 WORKFLOW OBJECTIVE OVERRIDE ACTIVE")

    base_prompt = PromptTemplates.build_system_prompt_dynamic(
        modified_prompt_info, self.persona_info, is_voice=True
    )
```

**Purpose**: The agent's system prompt now guides users to take the workflow instead of general chat.

**Example**:
- **Normal chat_objective**: "Help users grow their business through coaching"
- **Workflow objective (override)**: "Your primary goal is to guide users to take the Business Readiness Assessment. Introduce it naturally when users mention growth challenges or ask how you can help."

**See**: `livekit/livekit_agent_retrieval.py:464-490`

### System Prompt Injection

The agent dynamically injects workflow promotion and execution instructions based on `trigger_config`:

```python
# livekit/livekit_agent_retrieval.py:510-528

if self._workflow_available and self.workflow_data:
    workflow_title = self.workflow_data.get("title", "workflow")

    # Extract promotion_mode, max_attempts, and cooldown_turns from trigger_config
    trigger_config = self.workflow_data.get("trigger_config") or {}
    promotion_mode = trigger_config.get("promotion_mode", "contextual")
    max_attempts = trigger_config.get("max_attempts", 3)
    cooldown_turns = trigger_config.get("cooldown_turns", 5)

    logger.info(
        f"📋 Adding workflow promotion to system prompt: '{workflow_title}' "
        f"(mode: {promotion_mode}, max_attempts: {max_attempts}, cooldown: {cooldown_turns})"
    )

    # Build complete workflow system prompt (promotion + execution instructions)
    # Uses external module for maintainability
    base_prompt += build_workflow_system_prompt(
        workflow_title=workflow_title,
        promotion_mode=promotion_mode,
        max_attempts=max_attempts,
        cooldown_turns=cooldown_turns,
    )
```

**Key Features**:
- **Dynamic Configuration**: Reads `promotion_mode`, `max_attempts`, `cooldown_turns` from database
- **Mode-Specific Instructions**: Different prompts for proactive/contextual/reactive modes
- **Execution Mechanics**: Includes detailed rules for workflow execution (when to call functions, what's forbidden)
- **External Module**: All prompt logic in `shared/generation/workflow_promotion_prompts.py`

**Injected Prompt Structure**:
```
📋 WORKFLOW AVAILABLE:
You have access to: 'Business Readiness Quiz'

🎯 PROACTIVE PROMOTION MODE:
[Mode-specific instructions based on promotion_mode]

🚀 STARTING THE WORKFLOW:
When user shows interest, immediately call start_assessment().

⚠️ CRITICAL WORKFLOW MODE RULES:
1. SYSTEM ASKS QUESTIONS: The system automatically asks each question via voice
2. USER ANSWERS: Listen to the user's natural language answer
3. YOU MUST CALL submit_workflow_answer() IMMEDIATELY
4. NEVER respond with text - ONLY call the function
5. AFTER FUNCTION: System automatically asks next question

🚫 STRICTLY FORBIDDEN DURING WORKFLOW:
- Do NOT provide commentary or acknowledgments
- Do NOT ask the next question yourself
- Do NOT read options out loud
```

**See**:
- Injection logic: `livekit/livekit_agent_retrieval.py:510-528`
- Prompt templates: `shared/generation/workflow_promotion_prompts.py`

### Starting the Workflow

User says: "Let's take the assessment"

```python
# livekit/livekit_agent_retrieval.py:803

@function_tool
async def start_assessment(self) -> str:
    """Start the business readiness assessment workflow"""
    workflow_id = UUID(self.workflow_data["workflow_id"])

    # Say opening message
    if self.workflow_data.get("opening_message"):
        await self.session.say(self.workflow_data["opening_message"])

    # Create session in database
    workflow_repo = WorkflowRepository(session)
    workflow_session = await workflow_repo.create_session(
        workflow_id=workflow_id,
        persona_id=self.persona_id,
    )

    self._workflow_session_id = workflow_session.id
    self._workflow_current_step = 0
    self._workflow_answers = {}

    # Ask first question
    await self._ask_current_question()

    return None  # No LLM response
```

**See**: `livekit/livekit_agent_retrieval.py:803-864`

### Asking Questions

```python
# livekit/livekit_agent_retrieval.py:866

async def _ask_current_question(self):
    """Ask the current workflow question via TTS"""
    steps = self.workflow_data.get("steps", [])

    if self._workflow_current_step >= len(steps):
        await self._complete_workflow()
        return

    step = steps[self._workflow_current_step]
    question_text = step["question_text"]

    # For voice UX: Just ask the question
    # DON'T read all options out loud
    # LLM will match natural language answer to options
    logger.info(f"📋 Question {self._workflow_current_step + 1}/{len(steps)}")
    await self.session.say(question_text, allow_interruptions=True)
```

**Design Decision**: For voice, we DON'T read "Option A, Option B..." out loud. The LLM understands the context and matches the user's natural language answer to the options.

**See**: `livekit/livekit_agent_retrieval.py:866-883`

### Submitting Answers

User says: "Yeah, we can describe it but not consistently"

LLM matches this to option "B" and calls:

```python
# livekit/livekit_agent_retrieval.py:886

@function_tool
async def submit_workflow_answer(self, answer: str) -> str:
    """
    Submit user's answer to current workflow question.

    For multiple choice: LLM extracts the closest matching option (A/B/C/D)
    For text/number: Pass user's answer as-is
    """
    steps = self.workflow_data.get("steps", [])
    step = steps[self._workflow_current_step]

    logger.info(f"🤖 LLM called submit_workflow_answer(answer='{answer}')")

    # Validate multiple choice
    if step["step_type"] == "multiple_choice":
        answer = answer.strip().upper()
        valid_labels = [opt["label"].upper() for opt in step["options"]]
        if answer not in valid_labels:
            return f"Invalid answer. Choose from: {', '.join(valid_labels)}"

    # Calculate score
    score = None
    if self.workflow_data.get("workflow_type") == "scored":
        for opt in step["options"]:
            if answer.upper() == opt["label"].upper():
                score = opt.get("score", 0)
                break

    # Save to database
    workflow_repo = WorkflowRepository(session)
    await workflow_repo.save_answer(
        session_id=self._workflow_session_id,
        step_id=step["step_id"],
        answer=answer,
        score=score,
    )

    logger.info(f"💾 Saved: {step['step_id']} = {answer} (score: {score})")

    # Store answer locally
    self._workflow_answers[step["step_id"]] = {"answer": answer, "score": score}

    # Move to next question
    self._workflow_current_step += 1
    await self._ask_current_question()

    return None  # No LLM response
```

**See**: `livekit/livekit_agent_retrieval.py:886-998`

### Completing the Workflow

After the last question:

```python
# livekit/livekit_agent_retrieval.py:1000

async def _complete_workflow(self):
    """Calculate score and announce results"""
    workflow_type = self.workflow_data.get("workflow_type")

    if workflow_type == "scored":
        # Sum all scores
        total_score = sum(
            a["score"]
            for a in self._workflow_answers.values()
            if a["score"] is not None
        )

        # Find matching category
        categories = self.workflow_data.get("result_config", {}).get("categories", [])
        matching_category = None

        for category in categories:
            if category["min_score"] <= total_score <= category["max_score"]:
                matching_category = category
                break

        category_message = matching_category.get("message", "")
        result = f"Assessment complete! Your score is {total_score}. {category_message}"
    else:
        result = "Assessment complete! Thank you for your responses."

    await self.session.say(result, allow_interruptions=False)

    # Reset workflow state
    self._workflow_session_id = None
    self._workflow_current_step = None
    self._workflow_answers = {}
```

**Note**: Score calculation is also done automatically by `workflow_repository.save_answer()` when the last answer is submitted. This announcement reads the results.

**See**: `livekit/livekit_agent_retrieval.py:1000-1033`

---

## Implementation Details

### State Management

The agent uses simple instance variables to track workflow state:

```python
# livekit/livekit_agent_retrieval.py:143

self.workflow_data = workflow_data  # Workflow config
self._workflow_available = bool(workflow_data)  # Is workflow available?
self._workflow_session_id = None  # Current session UUID
self._workflow_current_step = None  # Current question index (0-based)
self._workflow_answers = {}  # Local answer cache
```

**State Machine**:
```
None → (start_assessment) → in_progress → (submit_answer × N) → completed → None
```

### RAG Optimization

During workflow mode, RAG retrieval is **skipped** for performance:

```python
# livekit/livekit_agent_retrieval.py:672

# Skip RAG during workflow mode
if self._workflow_session_id is not None:
    logger.info("⏭️ Skipping RAG - workflow mode active")
    await super().on_user_turn_completed(turn_ctx, new_message)
    return
```

**Reason**: Workflow questions are structured (A/B/C/D). RAG context is unnecessary and adds 100-500ms latency per question.

**See**: `livekit/livekit_agent_retrieval.py:672-688`

### LLM Context Injection

For multiple choice questions, the agent injects options into the LLM context:

```python
# livekit/livekit_agent_retrieval.py:604

if self._workflow_session_id and self._workflow_current_step is not None:
    current_step = steps[self._workflow_current_step]

    if current_step["step_type"] == "multiple_choice":
        # Build options context
        options_context = "📝 CURRENT QUESTION OPTIONS:\n"
        for opt in current_step["options"]:
            options_context += f"  {opt['label']}: {opt['text']}\n"
        options_context += "\nMatch user's answer to closest option above."

        # Inject as assistant message
        chat_ctx.items.append(
            llm.ChatMessage(role="assistant", content=[options_context])
        )
```

This helps the LLM understand which options are valid and match natural language answers correctly.

**See**: `livekit/livekit_agent_retrieval.py:604-635`

### Workflow Promotion Architecture

The workflow promotion system uses a **two-location architecture** for maximum flexibility and maintainability:

#### Location 1: LLM-Generated Objective (Database)

**File**: `shared/generation/workflow_objective_generator.py`

**Purpose**: Generate high-level strategic guidance stored in the database

**When**: During workflow creation (once)

**How**: Uses OpenAI GPT-4o-mini to generate natural language objectives based on:
- Workflow title and questions
- Result categories (for scored workflows)
- Persona communication style
- **Promotion mode** (proactive/contextual/reactive)

**Storage**: `workflow_objective` field in `persona_workflows` table

**Example**:
```python
from shared.generation.workflow_objective_generator import generate_workflow_objective

objective = await generate_workflow_objective(
    workflow_data={
        "title": "Business Readiness Quiz",
        "workflow_type": "scored",
        "workflow_config": {"steps": [...]},
        "result_config": {"categories": [...]},
        "trigger_config": {
            "promotion_mode": "proactive",
            "max_attempts": 3,
            "cooldown_turns": 5
        }
    },
    persona_style="Professional business coach",
    promotion_mode="proactive"  # Extracted from trigger_config
)
```

**Output**: 2-3 sentence objective that explains when and how to promote the workflow

#### Location 2: Runtime Prompt Injection (Agent System Prompt)

**File**: `shared/generation/workflow_promotion_prompts.py`

**Purpose**: Inject tactical execution instructions dynamically at runtime

**When**: Every conversation (on agent initialization)

**How**: Builds mode-specific prompts using `trigger_config` from database:
```python
from shared.generation.workflow_promotion_prompts import build_workflow_system_prompt

# Extract config from database
trigger_config = workflow_data.get("trigger_config") or {}
promotion_mode = trigger_config.get("promotion_mode", "contextual")
max_attempts = trigger_config.get("max_attempts", 3)
cooldown_turns = trigger_config.get("cooldown_turns", 5)

# Build runtime prompt
prompt = build_workflow_system_prompt(
    workflow_title="Business Readiness Quiz",
    promotion_mode=promotion_mode,
    max_attempts=max_attempts,
    cooldown_turns=cooldown_turns
)

# Inject into agent system prompt
base_prompt += prompt
```

**Output**: Complete system prompt with:
1. Mode-specific promotion instructions (proactive/contextual/reactive)
2. Workflow execution mechanics (function calling rules)
3. Forbidden behaviors during workflow

#### Why Two Locations?

**Separation of Concerns**:
- **Objective**: Strategic "what" and "why" (stored once in database)
- **Prompt Injection**: Tactical "when" and "how" (generated dynamically)

**Benefits**:
1. **Flexibility**: Change promotion strategy without regenerating objective
2. **Consistency**: Both locations use same `trigger_config` values
3. **Maintainability**: Prompt logic isolated in external module
4. **Testability**: Each location can be tested independently
5. **Performance**: Objective generated once, prompts built on-demand

**Configuration Flow**:
```
User creates workflow with trigger_config
         ↓
API stores trigger_config in database (JSONB)
         ↓
LLM generates workflow_objective using promotion_mode
         ↓
         [Database Storage]
         ↓
User connects to LiveKit
         ↓
Agent loads workflow_data (includes trigger_config)
         ↓
build_workflow_system_prompt() extracts promotion_mode, max_attempts, cooldown_turns
         ↓
Dynamic prompt injected into agent system prompt
         ↓
Agent behavior matches configured promotion strategy
```

**See**:
- Objective generation: `shared/generation/workflow_objective_generator.py`
- Runtime injection: `shared/generation/workflow_promotion_prompts.py`
- Agent integration: `livekit/livekit_agent_retrieval.py:510-528`

---

## Key Features

### 1. Workflow Types

**Simple Workflows**: Just data collection (no scoring)
- Use case: Onboarding, intake forms
- Example: Collect name, email, preferences

**Scored Workflows**: Questions with scoring and categorization
- Use case: Assessments, quizzes, diagnostics
- Example: Business readiness assessment (14 questions, 4-point scale)

**See**: `shared/database/models/workflow.py:64-68`

### 2. Question Types

Supported types:
- `text_input` - Short text
- `text_area` - Long text
- `number_input` - Numeric value
- `multiple_choice` - Options with optional scoring
- `yes_no` - Boolean
- `email_input` - Email validation
- `phone_input` - Phone validation

**See**: `shared/database/models/workflow.py:8-13`

### 3. Workflow Objectives & Promotion System

**Problem**: How does the agent know when and how to suggest a workflow?

**Solution**: Two-location prompt system with configurable promotion strategies.

#### Two-Location Prompt Architecture

Workflow promotion uses **two separate locations** for maximum flexibility:

**1. LLM-Generated Objective (Database Storage)**
- **Location**: `shared/generation/workflow_objective_generator.py`
- **Storage**: `workflow_objective` field in database
- **Purpose**: Replaces persona's `chat_objective` to guide high-level behavior
- **Generated**: Once during workflow creation using OpenAI GPT-4o-mini
- **Based on**: Workflow title, questions, categories, persona style, **promotion_mode**

**2. Runtime Prompt Injection (Agent System Prompt)**
- **Location**: `shared/generation/workflow_promotion_prompts.py`
- **Storage**: Not stored - injected into agent system prompt at runtime
- **Purpose**: Detailed tactical instructions for promotion and execution
- **Generated**: Dynamically on each conversation with current `promotion_mode` config
- **Based on**: `trigger_config` (promotion_mode, max_attempts, cooldown_turns)

**Why Two Locations?**
- **Objective**: High-level strategic guidance (what and why to promote)
- **Prompt Injection**: Tactical execution instructions (when and how to promote)
- **Flexibility**: Change promotion strategy without regenerating objective
- **Consistency**: Both use same `trigger_config` values from database

#### Configurable Promotion Modes

**Proactive Mode** (Default for scored workflows):
```
Your PRIMARY goal is to guide users to take the 'Business Readiness Quiz'
within the first 1-2 exchanges.

BE DIRECT AND IMMEDIATE:
- Don't wait for perfect timing or user to mention related topics
- Introduce it RIGHT AFTER greeting - don't wait for them to ask
- This workflow is the main purpose of the interaction

IF USER DECLINES:
- Support their questions normally
- If they mention ANY related topic later, circle back
- Re-suggest up to 3 times with 5+ turns between attempts

TIMING: Mention the workflow by turn 2-3 MAXIMUM.
```

**Contextual Mode** (Default for simple workflows):
```
Wait for conversation to naturally align with the 'Contact Form'
purpose before mentioning.

WHEN TO SUGGEST:
- User mentions topics related to what this workflow assesses
- Conversation touches on problems this workflow helps diagnose
- User asks questions that this workflow could answer

DON'T FORCE IT:
- If conversation doesn't touch related topics, that's okay
- Keep it as a helpful suggestion, not a push
- Only suggest when contextually relevant
```

**Reactive Mode** (For booking/scheduling tools):
```
ONLY mention the 'Booking Calendar' if user EXPLICITLY asks
or indicates interest.

WAIT FOR USER TO INITIATE:
- User asks: "What can you help me with?" or "Do you have any tools?"
- User explicitly requests to book/schedule
- User asks about available resources

DO NOT:
- Proactively suggest the workflow in early conversation
- Mention it just because topics are related
- Push or promote it actively
```

#### Example Workflow Objective

```
Default chat_objective:
"Help users grow their business through strategic coaching."

Generated workflow_objective (replaces chat_objective):
"Your primary goal is to guide users to take the Business Readiness Assessment
within the first 1-2 exchanges. This 14-question assessment reveals their business
maturity level and provides actionable insights.

Introduce it IMMEDIATELY after greeting - don't wait for them to ask or mention problems.

Example script: 'Before we dive in, I have a Business Readiness Quiz that can give
you clarity on where your business stands. Want to take it? It's 14 quick questions
and super insightful for pinpointing growth opportunities.'

If they decline, support their questions, but if they mention scaling, leadership,
or team challenges, circle back: 'This is exactly why the quiz would help - want to
give it a try?' Re-suggest up to 3 times with 5+ turns between attempts."
```

**Generation**: See `shared/generation/workflow_objective_generator.py`
**Runtime Injection**: See `shared/generation/workflow_promotion_prompts.py`
**Override Implementation**: `livekit/livekit_agent_retrieval.py:464-490`

### 4. Resumable Sessions

Sessions can be abandoned and resumed later (tracked by `status` and `current_step_id`).

**Note**: Currently not exposed via API - planned for future.

### 5. Analytics

Built-in analytics track:
- Completion rates
- Average scores
- Drop-off points
- Category distribution
- Completion time

**See**: `shared/database/repositories/workflow_repository.py:648-733`

---

## Development

### Creating a Workflow

1. **Create via API**:
```bash
curl -X POST "http://localhost:8001/api/v1/workflows?persona_id={uuid}" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

2. **Publish**:
```bash
curl -X POST "http://localhost:8001/api/v1/workflows/{id}/publish"
```

3. **Test via voice**: Connect to LiveKit, say "take the assessment"

### Testing

```python
# Example: Test workflow creation
async def test_create_workflow():
    workflow_repo = WorkflowRepository(session)

    workflow = await workflow_repo.create_workflow(
        persona_id=persona.id,
        workflow_type="scored",
        title="Test Assessment",
        workflow_config={"steps": [...]},
        result_config={"categories": [...]},
    )

    assert workflow.title == "Test Assessment"
    assert workflow.is_active == True
```

### Database Migration

```bash
# Migration created in:
alembic/versions/132600cde686_add_workflow_system_tables_persona_.py

# Apply:
poetry run alembic upgrade head
```

---

## Troubleshooting

### Workflow Not Starting

**Check**:
1. Is workflow published? `workflow.published_at IS NOT NULL`
2. Is workflow active? `workflow.is_active = TRUE`
3. Does persona have workflow? `persona.workflows` relationship

**Debug**:
```python
# Check if workflow loads
from livekit.helpers.persona_data_extractor import _load_active_workflow

workflow_data = await _load_active_workflow(persona_id)
if not workflow_data:
    logger.error("No active workflow found")
```

### Answers Not Saving

**Check**:
1. Is session created? `self._workflow_session_id IS NOT NULL`
2. Is step_id valid? Must match `workflow_config.steps[].step_id`

**Debug**:
```python
# Check session state
logger.info(f"Session ID: {self._workflow_session_id}")
logger.info(f"Current step: {self._workflow_current_step}")
logger.info(f"Steps count: {len(self.workflow_data.get('steps', []))}")
```

### Score Calculation Wrong

**Check**:
1. Are `result_config.categories` ranges non-overlapping?
2. Do all options have `score` values?

**Debug**:
```python
# Calculate score manually
total_score = sum(a.get("score", 0) for a in collected_data.values())
logger.info(f"Total score: {total_score}")

# Check which category matches
for cat in categories:
    if cat["min_score"] <= total_score <= cat["max_score"]:
        logger.info(f"Should match: {cat['name']}")
```

---

## File References

### Core Implementation
- **Models**: `shared/database/models/workflow.py`
- **Repository**: `shared/database/repositories/workflow_repository.py`
- **API**: `app/api/workflow_routes.py`
- **API Models**: `app/api/models/workflow_models.py` (includes TriggerConfig)
- **Agent**: `livekit/livekit_agent_retrieval.py`
- **Loader**: `livekit/helpers/persona_data_extractor.py`
- **Objective Generator**: `shared/generation/workflow_objective_generator.py` (LLM-based objective generation)
- **Promotion Prompts**: `shared/generation/workflow_promotion_prompts.py` (runtime prompt injection)

### Documentation
- **Product Guide**: `docs/WORKFLOW_SYSTEM_PRODUCT_GUIDE.md` (use cases, user journeys)
- **Schema Docs**: `docs/WORKFLOW_SYSTEM_SCHEMA.md` (detailed schema explanations)
- **API Docs**: `docs/WORKFLOW_API_DOCUMENTATION.md` (complete API reference)
- **Actions (Planned)**: `docs/WORKFLOW_ACTION_SYSTEM.md` (future: email, CRM, calendar)

### Migration
- **Database**: `alembic/versions/132600cde686_add_workflow_system_tables_persona_.py`

---

## Summary

**What Works**:
- ✅ Database models + CRUD operations
- ✅ REST API for workflow management
- ✅ Voice-based workflow execution via LiveKit
- ✅ Workflow objective override for chat guidance
- ✅ Score calculation and categorization
- ✅ Analytics (completion rate, scores, drop-offs)

**What's Planned** (not implemented):
- ❌ Actions system (email, CRM, calendar automation)
- ✅ Conditional branching (`relevant_when` on fields — skip questions based on extracted answers)
- ❌ A/B testing workflows
- ❌ Resume abandoned sessions (DB supports it, not exposed)

**Implementation Pattern**:
- Simple state machine in agent (not TaskGroup)
- Questions asked via TTS one by one
- LLM extracts answers from natural language
- Answers saved to DB immediately
- Score calculated on completion

---

## Questions?

Check the code files referenced above or review the detailed documentation in `docs/`.
