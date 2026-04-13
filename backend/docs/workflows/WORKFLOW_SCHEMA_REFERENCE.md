# Workflow System - Complete Schema Reference

**Last Updated**: January 24, 2025
**Purpose**: Technical schema reference for UI/frontend development

This document provides the complete database and API schema for the workflow system, designed to help frontend developers understand data structures and design appropriate UIs.

**Related Documentation**:
- [WORKFLOW_TYPES_REFERENCE.md](./WORKFLOW_TYPES_REFERENCE.md) - Field definitions, use cases, examples
- [WORKFLOW_SYSTEM_DEVELOPER_GUIDE.md](../WORKFLOW_SYSTEM_DEVELOPER_GUIDE.md) - Backend implementation guide

---

## Table of Contents

1. [Core Workflow Model](#core-workflow-model)
2. [Workflow Config by Type](#workflow-config-by-type)
3. [Workflow Session Model](#workflow-session-model)
4. [API Request/Response Models](#api-requestresponse-models)
5. [Analytics Schema](#analytics-schema)
6. [Database Relationships](#database-relationships)
7. [UI Design Guide](#ui-design-guide)

---

## Core Workflow Model

**Database Table**: `persona_workflows`
**TypeScript Interface**:

```typescript
interface PersonaWorkflow {
  // ===== Identity =====
  id: UUID
  persona_id: UUID

  // ===== Type & Metadata =====
  workflow_type: "simple" | "scored" | "conversational"
  title: string                      // Max 500 chars, e.g., "Business Readiness Quiz"
  description: string | null         // Internal notes (not shown to users)
  opening_message: string | null     // Message before first question
  workflow_objective: string | null  // LLM-generated AI guidance (overrides chat_objective)

  // ===== Configuration (JSONB) =====
  // Structure varies by workflow_type - see "Workflow Config by Type" section
  workflow_config: WorkflowConfig

  // ===== Scoring (scored type only) =====
  result_config: {
    scoring_type: "sum"
    categories: Array<{
      name: string                   // "Not Ready", "Emerging", "Scaling"
      min_score: number              // Inclusive
      max_score: number              // Inclusive
      message: string                // Result message shown to user
    }>
  } | null

  // ===== Promotion Settings (JSONB) =====
  trigger_config: {
    promotion_mode: "proactive" | "contextual" | "reactive"
    max_attempts: number             // 1-10, default: 3
    cooldown_turns: number           // 1-20, default: 5
  } | null

  // ===== Output Template (conversational type only - PROPOSED) =====
  output_template: {
    format: "lead_summary"
    sections: Array<"profile" | "situation" | "need" | "score" | "key_context" | "follow_up_questions">
    scoring_rules: {
      base_score: number
      field_completeness_weight: number
      quality_signals: Record<string, number>   // Signal name → points
      risk_penalties: Record<string, number>    // Risk name → points
    }
    export_destinations: Array<"email" | "crm_webhook" | "internal_dashboard">
  } | null

  // ===== Lifecycle =====
  is_active: boolean                 // Only one active workflow per persona
  version: number                    // Increments on updates
  published_at: datetime | null      // null = draft
  extra_metadata: object | null      // Extensible metadata (tags, notes, etc.)
  created_at: datetime
  updated_at: datetime

  // ===== Relationships (not in DB, loaded via joins) =====
  persona?: Persona
  sessions?: WorkflowSession[]
}
```

---

## Workflow Config by Type

### Type 1: Simple Workflow

**Purpose**: Basic information collection (no scoring)
**Use Cases**: Contact forms, feedback surveys, registration

```typescript
interface SimpleWorkflowConfig {
  steps: Array<{
    // ===== Step Identity =====
    step_id: string                  // Unique identifier, e.g., "q1", "email", "company_name"
    step_type: "text_input" | "text_area" | "number_input" | "multiple_choice" | "yes_no" | "email_input" | "phone_input"
    question_text: string            // Question shown to user
    required: boolean                // Whether user must answer (default: true)

    // ===== Options (multiple_choice only) =====
    options?: Array<{
      label: string                  // "A", "B", "C"
      text: string                   // Option text shown to user
      value?: string                 // Machine-readable value (optional)
    }>

    // ===== Validation Rules (optional) =====
    validation?: {
      min_length?: number            // Text minimum length
      max_length?: number            // Text maximum length
      pattern?: string               // Regex pattern (e.g., email validation)
      min?: number                   // Number minimum value
      max?: number                   // Number maximum value
      integer_only?: boolean         // Number must be integer
    }
  }>
}

// Result config is null for simple workflows
result_config: null
```

**Example**:
```json
{
  "steps": [
    {
      "step_id": "name",
      "step_type": "text_input",
      "question_text": "What's your name?",
      "required": true,
      "validation": {"min_length": 2}
    },
    {
      "step_id": "email",
      "step_type": "email_input",
      "question_text": "What's your email?",
      "required": true,
      "validation": {"pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"}
    },
    {
      "step_id": "message",
      "step_type": "text_area",
      "question_text": "How can we help?",
      "required": true,
      "validation": {"min_length": 10}
    }
  ]
}
```

---

### Type 2: Scored Workflow

**Purpose**: Assessments with scoring and categorized results
**Use Cases**: Quizzes, readiness assessments, diagnostic tools

```typescript
interface ScoredWorkflowConfig {
  steps: Array<{
    // ===== Step Identity (same as Simple) =====
    step_id: string
    step_type: "multiple_choice"     // Usually multiple choice for scoring
    question_text: string
    required: boolean

    // ===== Options (MUST include scores) =====
    options: Array<{
      label: string                  // "A", "B", "C", "D"
      text: string                   // Option text shown to user
      score: number                  // Point value (e.g., 1-4)
      value?: string                 // Optional machine-readable value
    }>

    // ===== Validation (optional) =====
    validation?: {
      // Same as Simple workflow
    }
  }>
}

// Result config is REQUIRED for scored workflows
result_config: {
  scoring_type: "sum"                // Only "sum" supported currently
  categories: Array<{
    name: string                     // Category name (e.g., "Not Ready", "Emerging")
    min_score: number                // Minimum score (inclusive)
    max_score: number                // Maximum score (inclusive)
    message: string                  // Result message shown to user
  }>
}
```

**Example**:
```json
{
  "steps": [
    {
      "step_id": "q1",
      "step_type": "multiple_choice",
      "question_text": "Can you explain your business in one sentence?",
      "required": true,
      "options": [
        {"label": "A", "text": "Not really — we use long descriptions", "score": 1},
        {"label": "B", "text": "We can describe it, but it takes explaining", "score": 2},
        {"label": "C", "text": "Yes, but it's a bit complex", "score": 3},
        {"label": "D", "text": "Absolutely — it's clear and simple", "score": 4}
      ]
    }
  ]
}
```

**Result Config Example**:
```json
{
  "scoring_type": "sum",
  "categories": [
    {
      "name": "Not Ready",
      "min_score": 14,
      "max_score": 26,
      "message": "Both you and your business need strengthening before scaling..."
    },
    {
      "name": "Emerging",
      "min_score": 27,
      "max_score": 40,
      "message": "You've got traction, but scaling is still fragile..."
    },
    {
      "name": "Scaling",
      "min_score": 41,
      "max_score": 56,
      "message": "You're ready to scale. Now execute with discipline..."
    }
  ]
}
```

---

### Type 3: Conversational Workflow (PROPOSED - Not Implemented)

**Purpose**: Natural dialogue with intelligent field extraction
**Use Cases**: Lead capture, qualification, discovery calls

```typescript
interface ConversationalWorkflowConfig {
  // ===== Required Fields (must capture) =====
  required_fields: Array<{
    field_id: string                 // "contact_name", "contact_email", "entity_type"
    field_type: "text" | "email" | "phone" | "number" | "choice" | "date"
    label: string                    // Human-readable field name
    description?: string             // What this field represents (helps AI extraction)

    // ===== Options (for choice fields) =====
    options?: string[]               // ["Sole Proprietor", "LLC", "S-Corp", "C-Corp"]

    // ===== Conditional Relevance (branching) =====
    relevant_when?: Condition        // Only ask when condition is true (null = always ask)
                                     // Uses same Condition model as scoring/follow-up rules

    // ===== Validation =====
    validation?: {
      min_length?: number
      max_length?: number
      pattern?: "email" | "phone" | string  // Predefined or custom regex
      min?: number
      max?: number
      required_format?: string       // Free-form format hint for AI
    }
  }>

  // ===== Optional Fields (nice to have) =====
  optional_fields: Array<{
    // Same schema as required_fields (including relevant_when)
  }>

  // ===== Inference Rules (field extraction guidance) =====
  inference_rules: Record<string, string>  // field_id → extraction instruction

  // Example:
  // {
  //   "entity_type": "Extract if user mentions 'LLC', 'S-Corp', 'C-Corp'...",
  //   "revenue_range": "Infer from business size cues: 'small team' → $100K-$500K..."
  // }

  // ===== Extraction Strategy =====
  extraction_strategy: {
    opening_question: string         // "What's going on that made you reach out?"
    max_clarifying_questions: number // Default: 5
    confirmation_required: boolean   // Confirm ALL extracted data in ONE summary
    confirmation_style: "summary" | "none"
    extraction_model: string         // "gpt-4o-mini"
    confidence_threshold: number     // 0-1, default: 0.8
    allow_partial_extraction: boolean // Can complete with only required fields?
  }
}

// Result config is null for conversational
result_config: null

// Output template is REQUIRED for conversational
output_template: {
  format: "lead_summary"
  sections: Array<"profile" | "situation" | "need" | "score" | "key_context" | "follow_up_questions">

  scoring_rules: {
    base_score: number
    field_completeness_weight: number
    quality_signals: Record<string, number>   // "revenue_1m_plus" → 15
    risk_penalties: Record<string, number>    // "red_flag_unfiled" → -20
  }

  export_destinations: Array<"email" | "crm_webhook" | "internal_dashboard">
}
```

**Example**:
```json
{
  "required_fields": [
    {
      "field_id": "contact_name",
      "field_type": "text",
      "label": "Full name",
      "description": "Primary contact at the business",
      "validation": {"min_length": 2}
    },
    {
      "field_id": "contact_email",
      "field_type": "email",
      "label": "Email address",
      "validation": {"pattern": "email"}
    },
    {
      "field_id": "entity_type",
      "field_type": "choice",
      "label": "Business entity type",
      "options": ["Sole Proprietor", "LLC", "S-Corp", "C-Corp", "Partnership"]
    }
  ],

  "optional_fields": [
    {
      "field_id": "revenue_range",
      "field_type": "choice",
      "label": "Annual revenue range",
      "options": ["<$100K", "$100K-$500K", "$500K-$1M", "$1M-$5M", "$5M+"]
    }
  ],

  "inference_rules": {
    "entity_type": "Extract if user mentions 'LLC', 'S-Corp', 'C-Corp', 'sole proprietor', or 'partnership'. Common phrases: 'we're an LLC', 'elected S-Corp status'.",
    "revenue_range": "Infer from business size cues: 'just started' → <$100K, 'small team (2-5)' → $100K-$500K, 'growing fast' → $500K-$1M."
  },

  "extraction_strategy": {
    "opening_question": "What's going on that made you reach out to us?",
    "max_clarifying_questions": 5,
    "confirmation_required": true,
    "confirmation_style": "summary",
    "extraction_model": "gpt-4o-mini",
    "confidence_threshold": 0.8,
    "allow_partial_extraction": false
  }
}
```

---

## Workflow Session Model

**Database Table**: `workflow_sessions`
**Purpose**: Tracks individual workflow executions

```typescript
interface WorkflowSession {
  // ===== Identity =====
  id: UUID
  workflow_id: UUID
  persona_id: UUID
  conversation_id: UUID | null       // Links to chat conversation (optional)
  user_id: UUID | null               // Authenticated user (optional)

  // ===== Status =====
  status: "in_progress" | "completed" | "abandoned"
  started_at: datetime
  completed_at: datetime | null
  updated_at: datetime

  // ===== Progress Tracking =====
  current_step_id: string | null     // For simple/scored: "q5" | For conversational: N/A
  progress_percentage: number        // 0-100

  // ===== Collected Data (JSONB) =====
  // Structure varies by workflow type
  collected_data: SimpleCollectedData | ScoredCollectedData | ConversationalCollectedData

  // ===== Result Data (JSONB) =====
  // Set on completion, structure varies by type
  result_data: SimpleResultData | ScoredResultData | ConversationalResultData | null

  // ===== Conversational-Specific (PROPOSED) =====
  extracted_fields?: Record<string, {
    value: any
    confidence: number
    source: string
  }>

  // ===== Metadata =====
  session_metadata: object | null    // User agent, IP, custom data
}
```

### Collected Data Schemas

#### Simple/Scored Workflows

```typescript
interface SimpleCollectedData {
  [step_id: string]: {
    question: string                 // Question text
    answer: string                   // User's answer
    raw_answer?: string              // Original voice/text input (if different)
    score?: number                   // Only for scored workflows
    answered_at: datetime
  }
}

// Example:
{
  "q1": {
    "question": "Can you explain your business in one sentence?",
    "answer": "B",
    "raw_answer": "We can describe it but not consistently",
    "score": 2,
    "answered_at": "2025-01-15T10:32:00Z"
  },
  "q2": {
    "question": "Do you have a clear target customer?",
    "answer": "C",
    "raw_answer": "Yes but we're still refining it",
    "score": 3,
    "answered_at": "2025-01-15T10:33:00Z"
  }
}
```

#### Conversational Workflows (PROPOSED)

```typescript
interface ConversationalCollectedData {
  [field_id: string]: {
    value: any                       // Extracted value
    extracted_at: datetime
    extraction_method: "natural_language" | "inference" | "clarifying_question"
    confidence: number               // 0-1
    raw_input: string                // Original user input
  }
}

// Example:
{
  "contact_name": {
    "value": "John Smith",
    "extracted_at": "2025-01-15T10:32:00Z",
    "extraction_method": "natural_language",
    "confidence": 0.95,
    "raw_input": "I'm John Smith, owner of Acme Corp"
  },
  "entity_type": {
    "value": "S-Corp",
    "extracted_at": "2025-01-15T10:32:00Z",
    "extraction_method": "inference",
    "confidence": 0.92,
    "raw_input": "we elected S-Corp status last year"
  },
  "revenue_range": {
    "value": "$500K-$1M",
    "extracted_at": "2025-01-15T10:33:00Z",
    "extraction_method": "clarifying_question",
    "confidence": 1.0,
    "raw_input": "about $800K in revenue"
  }
}
```

### Result Data Schemas

#### Simple Workflows

```typescript
interface SimpleResultData {
  // No scoring, just completion confirmation
  completed: true
  completion_message?: string
}

// Example:
{
  "completed": true,
  "completion_message": "Thank you for your submission!"
}
```

#### Scored Workflows

```typescript
interface ScoredResultData {
  total_score: number
  max_possible_score: number
  percentage: number                 // (total_score / max_possible_score) * 100
  category: string                   // Matched category name
  category_message: string           // Result message from category
}

// Example:
{
  "total_score": 38,
  "max_possible_score": 56,
  "percentage": 67.8,
  "category": "Emerging",
  "category_message": "You've got traction, but scaling is still fragile. Focus on: freeing yourself from bottlenecks..."
}
```

#### Conversational Workflows (PROPOSED)

```typescript
interface ConversationalResultData {
  lead_score: number                 // 0-100
  max_score: number                  // 100
  score_breakdown: {
    base_score: number
    field_completeness: number
    quality_signals: Record<string, number>
    risk_penalties: Record<string, number>
  }
  priority_level: "low" | "medium" | "high"
  formatted_summary: string          // Generated lead summary text
  follow_up_questions: string[]
}

// Example:
{
  "lead_score": 82,
  "max_score": 100,
  "score_breakdown": {
    "base_score": 50,
    "field_completeness": 20,
    "quality_signals": {
      "multi_state": 10,
      "urgent_timeline": 10,
      "established_business": 5
    },
    "risk_penalties": {
      "incomplete_contact": -13
    }
  },
  "priority_level": "high",
  "formatted_summary": "LEAD: John Smith - Acme Corp\nCONTACT: john@acme.com | (555) 123-4567\n\nPROFILE: S-Corp, $800K revenue, TX + CA (multi-state)...",
  "follow_up_questions": [
    "Sales tax compliance status in TX and CA?",
    "Is owner taking reasonable salary for S-Corp?"
  ]
}
```

---

## API Request/Response Models

### Create Workflow

**Endpoint**: `POST /api/v1/workflows?persona_id={uuid}`

```typescript
interface WorkflowCreateRequest {
  // ===== Basic Info =====
  workflow_type: "simple" | "scored" | "conversational"
  title: string
  description?: string
  opening_message?: string
  workflow_objective?: string        // Optional, LLM generates if missing

  // ===== Configuration =====
  workflow_config: SimpleWorkflowConfig | ScoredWorkflowConfig | ConversationalWorkflowConfig

  // ===== Scoring (scored only) =====
  result_config?: {
    scoring_type: "sum"
    categories: Array<{
      name: string
      min_score: number
      max_score: number
      message: string
    }>
  }

  // ===== Promotion =====
  trigger_config?: {
    promotion_mode: "proactive" | "contextual" | "reactive"
    max_attempts: number             // 1-10
    cooldown_turns: number           // 1-20
  }

  // ===== Output (conversational only) =====
  output_template?: {
    format: "lead_summary"
    sections: string[]
    scoring_rules: object
    export_destinations: string[]
  }

  // ===== Metadata =====
  extra_metadata?: object
}
```

### Workflow Response

```typescript
interface WorkflowResponse {
  // ===== Identity =====
  id: UUID
  persona_id: UUID

  // ===== Basic Info =====
  workflow_type: "simple" | "scored" | "conversational"
  title: string
  description: string | null
  opening_message: string | null
  workflow_objective: string | null

  // ===== Configuration =====
  workflow_config: object
  result_config: object | null
  trigger_config: object | null
  output_template: object | null

  // ===== Lifecycle =====
  is_active: boolean
  version: number
  published_at: datetime | null
  extra_metadata: object | null
  created_at: datetime
  updated_at: datetime

  // ===== Optional Stats (if include_stats=true) =====
  total_sessions?: number
  completed_sessions?: number
  completion_rate?: number           // Percentage
  avg_score?: number                 // For scored workflows
}
```

### List Workflows

**Endpoint**: `GET /api/v1/workflows?persona_id={uuid}&active_only=true&include_stats=true`

```typescript
interface WorkflowListResponse {
  workflows: WorkflowResponse[]
  total: number                      // Total count (without pagination)
}
```

### Update Workflow

**Endpoint**: `PATCH /api/v1/workflows/{workflow_id}`

```typescript
interface WorkflowUpdateRequest {
  // All fields optional (only include what you want to update)
  title?: string
  description?: string
  opening_message?: string
  workflow_objective?: string
  workflow_config?: object
  result_config?: object
  trigger_config?: object
  output_template?: object
  extra_metadata?: object
}
```

### Start Session

**Endpoint**: `POST /api/v1/workflows/sessions`

```typescript
interface WorkflowSessionCreateRequest {
  workflow_id: UUID
  conversation_id?: UUID             // Optional
  user_id?: UUID                     // Optional
  session_metadata?: object          // Optional custom data
}
```

### Session Response

```typescript
interface WorkflowSessionResponse {
  id: UUID
  workflow_id: UUID
  persona_id: UUID
  conversation_id: UUID | null
  user_id: UUID | null
  status: "in_progress" | "completed" | "abandoned"
  current_step_id: string | null
  progress_percentage: number
  collected_data: object
  result_data: object | null
  extracted_fields?: object          // Conversational only
  session_metadata: object | null
  started_at: datetime
  completed_at: datetime | null
  updated_at: datetime
}
```

### List Sessions

**Endpoint**: `GET /api/v1/workflows/sessions?workflow_id={uuid}&status=completed`

```typescript
interface WorkflowSessionListResponse {
  sessions: WorkflowSessionResponse[]
  total: number
}
```

### Submit Answer

**Endpoint**: `POST /api/v1/workflows/sessions/{session_id}/answer`

```typescript
interface AnswerSubmitRequest {
  step_id: string                    // Step being answered
  answer: string                     // User's answer (e.g., "A", "john@example.com")
  raw_answer?: string                // Original input (if different)
}
```

---

## Analytics Schema

**Endpoint**: `GET /api/v1/workflows/{workflow_id}/analytics`

```typescript
interface WorkflowAnalytics {
  // ===== Overview Metrics =====
  total_sessions: number
  completed_sessions: number
  in_progress_sessions: number
  abandoned_sessions: number
  completion_rate: number            // Percentage (0-100)

  // ===== Time Metrics =====
  avg_completion_time_seconds: number
  median_completion_time_seconds: number

  // ===== Scoring Metrics (scored workflows only) =====
  avg_score: number | null
  median_score: number | null
  max_score: number
  score_distribution: Record<string, number>  // Category name → count

  // ===== Lead Metrics (conversational workflows only - PROPOSED) =====
  avg_lead_score?: number | null
  priority_distribution?: {
    high: number
    medium: number
    low: number
  }

  // ===== Drop-off Analysis =====
  drop_off_by_step: Record<string, number>  // step_id → abandon count

  // ===== Field Extraction Stats (conversational only - PROPOSED) =====
  field_extraction_stats?: Record<string, {
    extracted_count: number
    avg_confidence: number
    clarification_needed_count: number
  }>
}
```

**Example Response**:
```json
{
  "total_sessions": 247,
  "completed_sessions": 168,
  "in_progress_sessions": 12,
  "abandoned_sessions": 67,
  "completion_rate": 68.0,

  "avg_completion_time_seconds": 552,
  "median_completion_time_seconds": 480,

  "avg_score": 34.5,
  "median_score": 36,
  "max_score": 56,
  "score_distribution": {
    "Not Ready": 42,
    "Emerging": 98,
    "Scaling": 28
  },

  "drop_off_by_step": {
    "q5": 8,
    "q9": 12,
    "q12": 5
  }
}
```

---

## Database Relationships

### Entity Relationship Diagram

```
┌─────────────┐
│    User     │
│  (users)    │
└──────┬──────┘
       │ 1
       │
       │ N
┌──────▼──────┐
│   Persona   │
│  (personas) │
└──────┬──────┘
       │ 1
       │
       │ N
┌──────▼─────────────────┐
│  PersonaWorkflow       │
│  (persona_workflows)   │
│                        │
│  - workflow_config     │
│  - result_config       │
│  - trigger_config      │
│  - output_template     │
└──────┬─────────────────┘
       │ 1
       │
       │ N
┌──────▼─────────────────┐
│  WorkflowSession       │
│  (workflow_sessions)   │
│                        │
│  - collected_data      │
│  - result_data         │
│  - extracted_fields    │
└──────┬─────────────────┘
       │ 1 (optional)
       │
       │ N
┌──────▼─────────────────┐
│  Conversation          │
│  (conversations)       │
└────────────────────────┘
```

### Key Constraints

1. **One Active Workflow Per Persona**: Only one `PersonaWorkflow` can have `is_active=true` per persona
2. **Session Belongs to One Workflow**: Each `WorkflowSession` links to exactly one workflow
3. **Optional User/Conversation**: Sessions can be anonymous (no user_id) or standalone (no conversation_id)
4. **Cascade Deletes**:
   - Delete persona → deletes all workflows
   - Delete workflow → deletes all sessions
   - Delete conversation → sets `conversation_id=null` in sessions

---

## UI Design Guide

### 1. Workflow Builder (Create/Edit)

#### **Page Structure**

```
┌─────────────────────────────────────────┐
│  Workflow Builder                       │
├─────────────────────────────────────────┤
│                                         │
│  [Step 1: Basic Info]  ← Active        │
│  [Step 2: Questions/Fields]             │
│  [Step 3: Results/Output]               │
│  [Step 4: Promotion Settings]           │
│  [Step 5: Preview & Test]               │
│                                         │
├─────────────────────────────────────────┤
│  [Back]              [Save] [Continue] │
└─────────────────────────────────────────┘
```

#### **Step 1: Basic Info**

```typescript
interface BasicInfoForm {
  workflow_type: "simple" | "scored" | "conversational"  // Radio buttons
  title: string                                          // Text input (max 500)
  description: string                                    // Textarea (optional)
  opening_message: string                                // Textarea (optional)
}
```

**UI Components**:
- Workflow type selector: Radio cards with icons and descriptions
- Title input: Text field with character counter
- Description: Rich text editor or textarea
- Opening message: Textarea with preview

#### **Step 2: Questions/Fields Configuration**

**For Simple/Scored Workflows**:

```typescript
interface StepEditor {
  steps: Array<{
    step_id: string                  // Auto-generated or editable
    step_type: StepType              // Dropdown
    question_text: string            // Textarea
    required: boolean                // Checkbox
    options?: OptionEditor[]         // For multiple_choice
    validation?: ValidationEditor    // Collapsible panel
  }>
}
```

**UI Components**:
- Drag-and-drop step list (sortable)
- Step type dropdown with icons
- Question text editor (rich text or plain)
- Options editor (for multiple choice):
  - Add/remove option buttons
  - Label input (A, B, C auto-populated)
  - Text input
  - Score input (scored workflows only)
- Validation rules panel (collapsible)

**For Conversational Workflows** (PROPOSED):

```typescript
interface FieldEditor {
  required_fields: Field[]
  optional_fields: Field[]
  inference_rules: Record<string, string>
  extraction_strategy: ExtractionStrategyForm
}
```

**UI Components**:
- Two-column layout: Required fields | Optional fields
- Field editor modal:
  - Field ID, type, label, description
  - Options editor (for choice type)
  - Validation rules
- Inference rules editor:
  - Field selector dropdown
  - Natural language instruction textarea
  - AI suggestion button
- Extraction strategy form:
  - Opening question input
  - Sliders: max clarifying questions, confidence threshold
  - Checkboxes: confirmation required, allow partial extraction

#### **Step 3: Results/Output Configuration**

**For Scored Workflows**:

```typescript
interface ResultConfigEditor {
  scoring_type: "sum"              // Fixed (only option)
  categories: Array<{
    name: string
    min_score: number
    max_score: number
    message: string                // Rich text editor
  }>
}
```

**UI Components**:
- Score range visualizer (bar chart showing category ranges)
- Category list editor:
  - Add/remove category buttons
  - Name input
  - Score range inputs (with validation to prevent gaps/overlaps)
  - Message editor (rich text)
- Validation warnings: "Gap detected between 26-27" or "Overlap at 40-41"

**For Conversational Workflows** (PROPOSED):

```typescript
interface OutputTemplateEditor {
  format: "lead_summary"           // Fixed
  sections: string[]               // Checkbox list
  scoring_rules: ScoringRulesEditor
  export_destinations: string[]    // Checkbox list
}
```

**UI Components**:
- Sections checklist (profile, situation, need, etc.)
- Scoring rules editor:
  - Base score input
  - Quality signals: Key-value editor (signal name → points)
  - Risk penalties: Key-value editor (risk name → penalty points)
- Export destinations: Checkbox list with integration status

#### **Step 4: Promotion Settings**

```typescript
interface PromotionSettingsForm {
  trigger_config: {
    promotion_mode: "proactive" | "contextual" | "reactive"
    max_attempts: number           // Slider (1-10)
    cooldown_turns: number         // Slider (1-20)
  }
  workflow_objective?: string      // Textarea (optional, LLM-generated if empty)
}
```

**UI Components**:
- Promotion mode: Radio cards with descriptions
- Max attempts slider with value display
- Cooldown turns slider with value display
- Workflow objective:
  - Textarea (optional manual entry)
  - "Generate with AI" button (calls LLM)
  - "Regenerate" button if already generated

#### **Step 5: Preview & Test**

**UI Components**:
- Workflow preview (read-only display of all config)
- Test execution panel:
  - Mock conversation UI (voice or text mode)
  - Answer submission form
  - Live progress tracker
  - Result display on completion
- Action buttons:
  - "Save as Draft"
  - "Publish Workflow"
  - "Back to Edit"

---

### 2. Workflow List View

```typescript
interface WorkflowListItem {
  id: UUID
  persona_id: UUID
  persona_name: string              // From join
  workflow_type: "simple" | "scored" | "conversational"
  title: string
  is_active: boolean
  published_at: datetime | null

  // Stats (optional)
  total_sessions?: number
  completed_sessions?: number
  completion_rate?: number          // Percentage
  avg_score?: number                // Scored only

  // Actions
  actions: ["edit", "duplicate", "delete", "publish", "unpublish", "view_analytics"]
}
```

**UI Components**:

```
┌───────────────────────────────────────────────────────────────┐
│  Workflows                                    [+ New Workflow] │
├───────────────────────────────────────────────────────────────┤
│  Filters:  [Persona ▼]  [Type ▼]  [Status ▼]   🔍 Search...  │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  📝 Business Readiness Quiz                          [Active] │
│  Persona: Sarah Coach • Scored • 168/247 completed (68%)      │
│  Avg Score: 34.5/56 • Published: Jan 15, 2025                 │
│  [Edit] [Duplicate] [Analytics] [•••]                         │
│                                                                │
│  ─────────────────────────────────────────────────────────    │
│                                                                │
│  📋 Contact Form                                      [Draft] │
│  Persona: Sarah Coach • Simple • 42 sessions                  │
│  Last edited: Jan 20, 2025                                    │
│  [Edit] [Publish] [Delete] [•••]                              │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

**Table Columns**:
1. Workflow icon + title
2. Persona name
3. Type badge (Simple/Scored/Conversational)
4. Status badge (Active/Draft)
5. Stats (sessions, completion rate)
6. Published date
7. Actions menu

---

### 3. Session Viewer (Analytics)

#### **Session List**

```typescript
interface SessionListItem {
  id: UUID
  workflow_title: string
  status: "in_progress" | "completed" | "abandoned"
  progress_percentage: number
  started_at: datetime
  completed_at: datetime | null

  // Preview
  result_score?: number             // Scored workflows
  result_category?: string          // Scored workflows
  lead_score?: number               // Conversational workflows

  // Actions
  actions: ["view_details", "export", "delete"]
}
```

**UI Components**:

```
┌───────────────────────────────────────────────────────────────┐
│  Sessions - Business Readiness Quiz                           │
├───────────────────────────────────────────────────────────────┤
│  Filters:  [Status ▼]  [Date Range ▼]        🔍 Search...    │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  ✅ Completed • Jan 24, 2025 10:32 AM                         │
│  Score: 38/56 (68%) • Category: Emerging                      │
│  Duration: 9m 12s                                              │
│  [View Details] [Export]                                       │
│                                                                │
│  ─────────────────────────────────────────────────────────    │
│                                                                │
│  ⏳ In Progress • Jan 24, 2025 11:45 AM                       │
│  Progress: 64% (9/14 questions)                               │
│  Last active: 2 minutes ago                                   │
│  [View Details]                                                │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

#### **Session Detail View**

```
┌───────────────────────────────────────────────────────────────┐
│  ← Back to Sessions                                           │
├───────────────────────────────────────────────────────────────┤
│  Session #abc123                                              │
│  Status: Completed ✅ • Score: 38/56 (68%)                    │
│  Started: Jan 24, 10:32 AM • Completed: Jan 24, 10:41 AM      │
│  Duration: 9m 12s                                              │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  📊 Results                                                    │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Category: Emerging                                   │    │
│  │  Total Score: 38/56 (67.8%)                           │    │
│  │                                                        │    │
│  │  You've got traction, but scaling is still fragile.   │    │
│  │  Focus on: freeing yourself from bottlenecks...       │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
│  📝 Answers (14)                                               │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Q1: Can you explain your business in one sentence?   │    │
│  │  A:  B - We can describe it, but it takes explaining  │    │
│  │  Score: 2/4 • Answered: 10:33 AM                      │    │
│  │                                                        │    │
│  │  Q2: Do you have a clear target customer?             │    │
│  │  A:  C - Yes, but we're still refining it             │    │
│  │  Score: 3/4 • Answered: 10:34 AM                      │    │
│  │  ...                                                   │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
│  🔧 Raw Data (JSON)                                            │
│  [Expand to view raw collected_data and result_data]          │
│                                                                │
│  [Export as PDF] [Export as CSV] [Delete Session]             │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

---

### 4. Analytics Dashboard

```
┌───────────────────────────────────────────────────────────────┐
│  Analytics - Business Readiness Quiz                          │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  📊 Overview                                                   │
│  ┌────────────┬────────────┬────────────┬────────────┐       │
│  │ Sessions   │ Completed  │ Completion │ Avg Score  │       │
│  │    247     │    168     │    68%     │   34.5     │       │
│  └────────────┴────────────┴────────────┴────────────┘       │
│                                                                │
│  📈 Score Distribution                                         │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Not Ready    ████████████ 42 sessions               │    │
│  │  Emerging     ████████████████████████ 98 sessions   │    │
│  │  Scaling      ██████ 28 sessions                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
│  ⏱️ Completion Time                                            │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Average: 9m 12s                                      │    │
│  │  Median:  8m 0s                                       │    │
│  │  [Time distribution chart]                            │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
│  📉 Drop-off Analysis                                          │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Q5:  8 abandonments                                  │    │
│  │  Q9:  12 abandonments (⚠️ High drop-off)             │    │
│  │  Q12: 5 abandonments                                  │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

**Chart Types Recommended**:
1. **Score Distribution**: Horizontal bar chart or pie chart
2. **Completion Rate**: Progress ring or percentage bar
3. **Time Distribution**: Histogram or box plot
4. **Drop-off Analysis**: Funnel chart showing abandonment at each step
5. **Sessions Over Time**: Line chart (daily/weekly)

---

### 5. Mobile Considerations

**Responsive Design Priorities**:

1. **Workflow List**: Card-based layout (stacked vertically)
2. **Workflow Builder**:
   - Single-column step editor
   - Bottom sheet for option/validation editors
   - Sticky action buttons
3. **Session Viewer**:
   - Accordion-style Q&A list
   - Swipeable session cards
4. **Analytics**:
   - Simplified charts (single metric per viewport)
   - Tabbed metrics navigation

---

### 6. Component Library Recommendations

**Suggested Components**:

1. **Forms**:
   - Rich text editor (TipTap, Quill, or Slate)
   - Drag-and-drop list (React DnD, dnd-kit)
   - Multi-step form wizard
   - Validation error displays

2. **Data Display**:
   - Table with sorting/filtering (TanStack Table)
   - Charts (Recharts, Chart.js, or Tremor)
   - Progress indicators (circular, linear)
   - Badge components (status, type)

3. **Interactive**:
   - Modal dialogs
   - Dropdown menus
   - Tooltips (help text)
   - Confirmation dialogs (delete, publish)

4. **Workflow-Specific**:
   - Step progress indicator (stepper)
   - Score range validator (visual)
   - Field extraction confidence meter
   - Lead summary previewer

---

## Summary

This schema reference provides:

✅ **Complete TypeScript interfaces** for all workflow types
✅ **Database schema** with JSONB field structures
✅ **API request/response models** for all endpoints
✅ **Analytics data structures** for reporting
✅ **UI design recommendations** for each view
✅ **Component suggestions** for implementation

**Next Steps**:
1. Use these schemas to design your UI mockups
2. Implement API client using the request/response models
3. Build form validation using the schema constraints
4. Create reusable components based on the UI guide

**Questions?** Refer to:
- [WORKFLOW_TYPES_REFERENCE.md](./WORKFLOW_TYPES_REFERENCE.md) for detailed field definitions
- [WORKFLOW_SYSTEM_DEVELOPER_GUIDE.md](../WORKFLOW_SYSTEM_DEVELOPER_GUIDE.md) for backend implementation

---

**Last Updated**: January 24, 2025
