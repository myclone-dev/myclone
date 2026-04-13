"""
Pydantic models for the workflow system API.

These models define the request/response schemas for workflow endpoints.

Created: 2025-12-08
"""

from __future__ import annotations  # Enables forward references for type hints

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ===== Workflow Step Configuration Models =====


class WorkflowOption(BaseModel):
    """
    A single option for a multiple choice question.

    Used in both simple and scored workflows.
    For scored workflows, 'score' is required.
    """

    label: str = Field(..., description="Option label (e.g., 'A', 'B', 'C', 'D')")
    text: str = Field(..., description="Option text shown to user")
    value: Optional[str] = Field(
        None, description="Machine-readable value for non-scored workflows"
    )
    score: Optional[int] = Field(None, description="Points for this option (scored workflows only)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "label": "A",
                "text": "Not really — we tend to use long or vague descriptions",
                "score": 1,
            }
        }
    )


class WorkflowStep(BaseModel):
    """
    A single step (question) in a workflow.

    Supports multiple question types:
    - text_input: Single line text
    - text_area: Multi-line text
    - number_input: Numeric value
    - multiple_choice: Options with optional scoring
    - yes_no: Boolean
    """

    step_id: str = Field(..., description="Unique identifier for this step (e.g., 'q1', 'q2')")
    step_type: Literal["text_input", "text_area", "number_input", "multiple_choice", "yes_no"] = (
        Field(..., description="Type of question")
    )
    question_text: str = Field(..., description="Question text shown to user")
    required: bool = Field(default=True, description="Whether this question is required")

    # Only for multiple_choice
    options: Optional[List[WorkflowOption]] = Field(
        None, description="Options for multiple choice questions"
    )

    # Validation rules for text/number inputs
    validation: Optional[Dict[str, Any]] = Field(
        None,
        description="Validation rules (e.g., min_length, max_length, min, max)",
    )

    @field_validator("step_type")
    @classmethod
    def validate_step_type(cls, v):
        """
        Ensure step_type is one of the allowed values.

        Defense-in-depth validation to catch invalid values from database reads
        or manual SQL inserts that bypass Pydantic's Literal validation.
        """
        valid_types = {"text_input", "text_area", "number_input", "multiple_choice", "yes_no"}
        if v not in valid_types:
            raise ValueError(
                f"step_type must be one of {valid_types}, got '{v}'. "
                f"This prevents runtime errors in step rendering and validation."
            )
        return v

    @field_validator("options")
    @classmethod
    def validate_options(cls, v, info):
        """Ensure options are provided for multiple_choice questions."""
        if info.data.get("step_type") == "multiple_choice":
            if not v or len(v) < 2:
                raise ValueError("Multiple choice questions must have at least 2 options")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "step_id": "q1",
                "step_type": "multiple_choice",
                "question_text": "Can you explain your business in one sentence?",
                "required": True,
                "options": [
                    {"label": "A", "text": "Not really", "score": 1},
                    {"label": "B", "text": "We can describe it", "score": 2},
                    {"label": "C", "text": "Yes but complex", "score": 3},
                    {"label": "D", "text": "Absolutely clear", "score": 4},
                ],
            }
        }
    )


# ===== Scoring Configuration Models (for scored workflows only) =====


class ResultCategory(BaseModel):
    """
    A result category for scored workflows.

    Defines a score range and the message to show users who fall in that range.
    """

    name: str = Field(..., description="Category name (e.g., 'Not Ready', 'Emerging', 'Scaling')")
    min_score: int = Field(..., description="Minimum score for this category (inclusive)")
    max_score: int = Field(..., description="Maximum score for this category (inclusive)")
    message: str = Field(..., description="Message shown to users who score in this category")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Emerging",
                "min_score": 27,
                "max_score": 40,
                "message": "You've got traction, but scaling is still fragile. Focus on freeing yourself from bottlenecks...",
            }
        }
    )


class ScoringConfig(BaseModel):
    """
    Scoring configuration for scored workflows.

    Defines how to calculate scores and what result categories to use.
    """

    scoring_type: Literal["sum"] = Field(
        default="sum", description="How to calculate total score (currently only 'sum' supported)"
    )
    categories: List[ResultCategory] = Field(
        ..., description="Result categories based on score ranges", min_length=1
    )

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, v):
        """Ensure categories cover all scores without gaps or overlaps."""
        if not v:
            raise ValueError("At least one category is required")

        # Sort by min_score
        sorted_cats = sorted(v, key=lambda c: c.min_score)

        # Check for gaps and overlaps
        for i in range(len(sorted_cats) - 1):
            current = sorted_cats[i]
            next_cat = sorted_cats[i + 1]

            if current.max_score >= next_cat.min_score:
                raise ValueError(
                    f"Overlapping categories: {current.name} ({current.max_score}) and {next_cat.name} ({next_cat.min_score})"
                )
            if current.max_score + 1 < next_cat.min_score:
                raise ValueError(
                    f"Gap in categories: {current.name} ({current.max_score}) to {next_cat.name} ({next_cat.min_score})"
                )

        return v


# ===== Workflow Configuration Models =====


class WorkflowConfig(BaseModel):
    """
    Complete workflow configuration.

    Contains all steps (questions) and optional sections.
    """

    steps: List[WorkflowStep] = Field(
        ..., description="List of workflow steps (questions)", min_length=1
    )

    @field_validator("steps")
    @classmethod
    def validate_step_ids_unique(cls, v):
        """Ensure all step IDs are unique."""
        step_ids = [step.step_id for step in v]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("All step IDs must be unique")
        return v


# ===== Trigger Configuration Model =====


class TriggerConfig(BaseModel):
    """
    Trigger configuration for workflow promotion.

    Controls how and when the AI should promote the workflow to users.
    """

    promotion_mode: Literal["proactive", "contextual", "reactive"] = Field(
        default="contextual",
        description=(
            "Promotion strategy:\n"
            "- 'proactive': Push immediately within 1-2 turns (for assessments/quizzes)\n"
            "- 'contextual': Suggest when conversation naturally aligns (default)\n"
            "- 'reactive': Only mention if user explicitly asks (for booking/scheduling tools)"
        ),
    )
    max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of times to re-suggest workflow if user declines",
    )
    cooldown_turns: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of conversation turns to wait before re-suggesting after decline",
    )

    @field_validator("promotion_mode")
    @classmethod
    def validate_promotion_mode(cls, v):
        """
        Ensure promotion_mode is one of the allowed values.

        Defense-in-depth validation to catch invalid values from database reads
        or manual SQL inserts that bypass Pydantic's Literal validation.
        """
        valid_modes = {"proactive", "contextual", "reactive"}
        if v not in valid_modes:
            raise ValueError(
                f"promotion_mode must be one of {valid_modes}, got '{v}'. "
                f"This prevents runtime errors in prompt generation."
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "promotion_mode": "proactive",
                "max_attempts": 3,
                "cooldown_turns": 5,
            }
        }
    )


# ===== API Request Models =====


class WorkflowCreate(BaseModel):
    """
    Request body for creating a new workflow.
    """

    workflow_type: Literal["simple", "scored", "conversational"] = Field(
        ...,
        description="Workflow type: 'simple' (linear Q&A), 'scored' (Q&A + scoring), or 'conversational' (intelligent field extraction)",
    )
    title: str = Field(..., description="Workflow title", min_length=1, max_length=500)
    description: Optional[str] = Field(
        None, description="Internal description (not shown to users)"
    )
    opening_message: Optional[str] = Field(
        None,
        description="Message shown before first question (optional, not used for conversational)",
    )
    workflow_objective: Optional[str] = Field(
        None,
        description="LLM-generated objective for guiding user toward workflow (auto-generated if not provided)",
    )

    # Simple/Scored workflows use WorkflowConfig (steps array)
    # Conversational workflows use ConversationalWorkflowConfig (fields array)
    workflow_config: Dict[str, Any] = Field(
        ..., description="Workflow configuration (structure depends on workflow_type)"
    )
    result_config: Optional[ScoringConfig] = Field(
        None,
        description="Result configuration (required for scored workflows, not used for conversational)",
    )

    # NEW: Output template for conversational workflows
    output_template: Optional[OutputTemplate] = Field(
        None,
        description="Output template for conversational workflows (required for conversational type)",
    )

    trigger_config: Optional[TriggerConfig] = Field(
        None,
        description="Trigger settings (how and when to promote workflow)",
    )
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

    @field_validator("workflow_type")
    @classmethod
    def validate_workflow_type(cls, v):
        """
        Ensure workflow_type is one of the allowed values.

        Defense-in-depth validation to catch invalid values from database reads
        or manual SQL inserts that bypass Pydantic's Literal validation.
        """
        valid_types = {"simple", "scored", "conversational"}
        if v not in valid_types:
            raise ValueError(
                f"workflow_type must be one of {valid_types}, got '{v}'. "
                f"This prevents runtime errors in result configuration validation."
            )
        return v

    @field_validator("result_config")
    @classmethod
    def validate_result_config(cls, v, info):
        """Ensure result_config is provided for scored workflows only."""
        workflow_type = info.data.get("workflow_type")
        if workflow_type == "scored" and not v:
            raise ValueError("result_config is required for scored workflows")
        if workflow_type in ("simple", "conversational") and v:
            raise ValueError(f"result_config should not be provided for {workflow_type} workflows")
        return v

    @field_validator("output_template")
    @classmethod
    def validate_output_template(cls, v, info):
        """Ensure output_template is provided for conversational workflows only."""
        workflow_type = info.data.get("workflow_type")
        if workflow_type == "conversational" and not v:
            raise ValueError("output_template is required for conversational workflows")
        if workflow_type in ("simple", "scored") and v:
            raise ValueError(
                f"output_template should not be provided for {workflow_type} workflows"
            )
        return v

    @model_validator(mode="after")
    def validate_workflow_config_schema(self):
        """
        Validate workflow_config structure based on workflow_type.

        This ensures the JSONB workflow_config matches the expected schema:
        - simple/scored: Must have 'steps' array with WorkflowStep structure
        - conversational: Must have required_fields, optional_fields, inference_rules, extraction_strategy

        Note: Uses validate_workflow_config_by_type() which is defined at the end of this file
        to avoid forward reference issues with ConversationalWorkflowConfig.
        """
        # Import here to avoid circular dependency / forward reference issues
        # The actual validation function is defined at the end of this file
        from app.api.models.workflow_models import validate_workflow_config_by_type

        validate_workflow_config_by_type(self.workflow_type, self.workflow_config)
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "workflow_type": "scored",
                "title": "Business Scale & Growth Predictor Quiz",
                "description": "Helps founders understand their readiness to scale",
                "opening_message": "Discover how ready you and your business are to scale to the next level...",
                "workflow_config": {
                    "steps": [
                        {
                            "step_id": "q1",
                            "step_type": "multiple_choice",
                            "question_text": "Can you explain your business in one sentence?",
                            "required": True,
                            "options": [
                                {"label": "A", "text": "Not really", "score": 1},
                                {"label": "B", "text": "We can describe it", "score": 2},
                                {"label": "C", "text": "Yes but complex", "score": 3},
                                {"label": "D", "text": "Absolutely clear", "score": 4},
                            ],
                        }
                    ]
                },
                "result_config": {
                    "scoring_type": "sum",
                    "categories": [
                        {
                            "name": "Not Ready",
                            "min_score": 14,
                            "max_score": 26,
                            "message": "Both you and your business need strengthening before scaling...",
                        },
                        {
                            "name": "Emerging",
                            "min_score": 27,
                            "max_score": 40,
                            "message": "You've got traction but scaling is fragile...",
                        },
                    ],
                },
            }
        }
    )


class WorkflowUpdate(BaseModel):
    """
    Request body for updating an existing workflow.

    All fields are optional - only provided fields will be updated.
    """

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    opening_message: Optional[str] = None
    workflow_objective: Optional[str] = None
    workflow_config: Optional[Dict[str, Any]] = None  # Dict for partial updates (deep merge)
    result_config: Optional[Dict[str, Any]] = None  # Dict for partial updates (deep merge)
    output_template: Optional[Dict[str, Any]] = None  # Dict for partial updates (deep merge)
    trigger_config: Optional[Dict[str, Any]] = None  # Dict for partial updates (deep merge)
    extra_metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


# ===== API Response Models =====


class WorkflowResponse(BaseModel):
    """
    Response model for a workflow.
    """

    id: UUID
    persona_id: UUID
    workflow_type: str
    title: str
    description: Optional[str] = None
    opening_message: Optional[str] = None
    workflow_objective: Optional[str] = None
    workflow_config: Dict[str, Any]  # JSONB from database
    result_config: Optional[Dict[str, Any]] = None  # JSONB from database (for scored workflows)
    output_template: Optional[Dict[str, Any]] = (
        None  # NEW: JSONB from database (for conversational workflows)
    )
    is_active: bool
    version: int
    published_at: Optional[datetime] = None
    trigger_config: Optional[Dict[str, Any]] = None
    extra_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    # Optional statistics (populated when include_stats=true)
    total_sessions: Optional[int] = Field(None, description="Total number of sessions started")
    completed_sessions: Optional[int] = Field(None, description="Number of completed sessions")
    completion_rate: Optional[float] = Field(None, description="Completion rate percentage")
    avg_score: Optional[float] = Field(None, description="Average score (for scored workflows)")

    model_config = ConfigDict(from_attributes=True)


class WorkflowListResponse(BaseModel):
    """
    Response model for listing workflows.
    """

    workflows: List[WorkflowResponse]
    total: int


# ===== Session Models =====


class WorkflowSessionCreate(BaseModel):
    """
    Request body for starting a new workflow session.
    """

    workflow_id: UUID = Field(..., description="Workflow to execute")
    conversation_id: Optional[UUID] = Field(None, description="Associated conversation (if any)")
    user_id: Optional[UUID] = Field(None, description="User taking the workflow (if authenticated)")
    session_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional session metadata"
    )


class AnswerSubmit(BaseModel):
    """
    Request body for submitting an answer to a workflow step.
    """

    step_id: str = Field(..., description="Step ID being answered")
    answer: Any = Field(..., description="User's answer (type depends on question type)")
    raw_answer: Optional[str] = Field(
        None, description="Original user input (for natural language extraction)"
    )


class WorkflowSessionResponse(BaseModel):
    """
    Response model for a workflow session.
    """

    id: UUID
    workflow_id: UUID
    persona_id: UUID
    conversation_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    status: str  # 'in_progress', 'completed', 'abandoned'
    current_step_id: Optional[str] = None
    progress_percentage: int
    collected_data: Dict[str, Any]  # JSONB from database
    result_data: Optional[Dict[str, Any]] = None  # JSONB from database (for scored workflows)
    extracted_fields: Optional[Dict[str, Any]] = (
        None  # NEW: JSONB from database (for conversational workflows)
    )
    session_metadata: Optional[Dict[str, Any]] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkflowSessionListResponse(BaseModel):
    """
    Response model for listing workflow sessions.
    """

    sessions: List[WorkflowSessionResponse]
    total: int


# ===== Analytics Models =====


class WorkflowAnalytics(BaseModel):
    """
    Analytics data for a workflow.
    """

    workflow_id: UUID
    total_sessions: int
    completed_sessions: int
    abandoned_sessions: int
    completion_rate: float  # Percentage
    avg_completion_time_seconds: Optional[float] = None

    # For scored workflows
    avg_score: Optional[float] = None
    score_distribution: Optional[Dict[str, int]] = None  # {category_name: count}

    # Drop-off analysis
    drop_off_by_step: Optional[Dict[str, int]] = None  # {step_id: abandoned_count}


class WorkflowSessionDetail(BaseModel):
    """
    Detailed view of a completed workflow session.

    Includes all questions, answers, and results.
    """

    session: WorkflowSessionResponse
    workflow: WorkflowResponse
    questions_and_answers: List[Dict[str, Any]]  # Enriched collected_data with question text


# ===== Bulk Import Model =====


class BulkQuestionsImport(BaseModel):
    """
    Request body for bulk importing questions.

    Accepts a list of question texts and automatically creates WorkflowStep objects.
    """

    questions: List[str] = Field(..., description="List of question texts", min_length=1)
    default_type: Literal["text_input", "text_area", "multiple_choice", "number_input"] = Field(
        default="multiple_choice", description="Default question type for all questions"
    )
    default_options: Optional[List[WorkflowOption]] = Field(
        None, description="Default options for multiple choice questions"
    )


# ===== Conversational Workflow Models (NEW) =====


class ConversationalField(BaseModel):
    """
    A field to extract from natural language in conversational workflows.

    Used for both required_fields and optional_fields.
    """

    field_id: str = Field(
        ..., description="Unique identifier for this field (e.g., 'contact_name', 'entity_type')"
    )
    field_type: Literal["text", "email", "phone", "number", "choice", "date"] = Field(
        ..., description="Data type of the field"
    )
    label: str = Field(..., description="Human-readable field name")
    description: Optional[str] = Field(
        None, description="What this field represents (helps AI extraction)"
    )

    # Only for choice fields
    options: Optional[List[str]] = Field(
        None,
        description="Allowed values for choice fields (e.g., ['Sole Proprietor', 'LLC', 'S-Corp'])",
    )

    # NEW: Custom clarifying question (Phase 2 UX improvement)
    clarifying_question: Optional[str] = Field(
        None,
        description="Custom conversational question to ask if this field is missing. If not provided, uses generic template based on field_type.",
    )

    # Conditional relevance (only ask this field when condition is met)
    relevant_when: Optional["Condition"] = Field(
        None,
        description="Condition that must be true for this field to be relevant. "
        "Uses same operators as scoring conditions (exists, equals, in_list, etc.). "
        "If null, field is always relevant.",
    )

    # Validation rules
    validation: Optional[Dict[str, Any]] = Field(
        None,
        description="Validation rules (e.g., min_length, max_length, pattern, min, max)",
    )

    @model_validator(mode="after")
    def validate_choice_options(self):
        """Ensure options are provided for choice fields."""
        if self.field_type == "choice":
            if not self.options or len(self.options) < 2:
                raise ValueError(f"Choice field '{self.field_id}' must have at least 2 options")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Choice Field with Custom Question",
                    "value": {
                        "field_id": "entity_type",
                        "field_type": "choice",
                        "label": "Business entity type",
                        "description": "Legal structure of the business",
                        "options": ["Sole Proprietor", "LLC", "S-Corp", "C-Corp", "Partnership"],
                        "clarifying_question": "What's your business structure — LLC, S-Corp, or something else?",
                    },
                },
                {
                    "title": "Email Field with Custom Question",
                    "value": {
                        "field_id": "contact_email",
                        "field_type": "email",
                        "label": "Email address",
                        "description": "Best email to reach the contact",
                        "clarifying_question": "Got it! What's the best email to reach you at?",
                    },
                },
            ]
        }
    )


class ExtractionStrategy(BaseModel):
    """
    Configuration for how to extract fields from natural language.

    Controls the conversational behavior and extraction parameters.
    """

    opening_question: Optional[str] = Field(
        default=None,
        description="Initial open-ended question to start the conversation. If not provided, a default is used.",
    )
    max_clarifying_questions: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of clarifying questions to ask for missing required fields",
    )
    confirmation_required: bool = Field(
        default=True,
        description="Whether to confirm ALL extracted data in ONE summary before completing",
    )
    confirmation_style: Literal["summary", "none"] = Field(
        default="summary",
        description="How to confirm extracted data: 'summary' (one confirmation) or 'none'",
    )
    extraction_model: str = Field(
        default="gpt-4o-mini",
        description="LLM model to use for field extraction",
    )
    confidence_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score (0-1) to accept extracted field without clarification",
    )
    allow_partial_extraction: bool = Field(
        default=False,
        description="Whether to complete workflow if only required fields are captured (optional fields missing)",
    )

    # Conversation tone (controls phrasing of acknowledgments, questions, etc.)
    tone: Literal["concierge", "professional", "casual", "efficient"] = Field(
        default="professional",
        description=(
            "Conversation tone preset:\n"
            "- 'concierge': White-glove premium service (warm, appreciative)\n"
            "- 'professional': Friendly but efficient (default)\n"
            "- 'casual': Relaxed, conversational\n"
            "- 'efficient': Minimal, fast-paced"
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "opening_question": "Thanks for reaching out! What's going on with your business that made you look for a CPA?",
                "max_clarifying_questions": 5,
                "confirmation_required": True,
                "confirmation_style": "summary",
                "extraction_model": "gpt-4o-mini",
                "confidence_threshold": 0.8,
                "allow_partial_extraction": False,
                "tone": "professional",
            }
        }
    )


# ===== Condition Models (NEW - Config-Driven Rules) =====


class Condition(BaseModel):
    """
    Generic condition for evaluating extracted fields.

    Used by:
    - Follow-up question rules (when to ask a question)
    - Quality signals (when to add positive points)
    - Risk penalties (when to subtract points)

    Supports operators:
    - exists, not_exists
    - equals, not_equals
    - contains, contains_any, not_contains
    - greater_than, less_than, greater_than_or_equal, less_than_or_equal
    - in_list, not_in_list
    - regex_match
    - word_count_gte, word_count_lte

    Supports compound logic:
    - any_of (OR): Returns True if ANY sub-condition matches
    - all_of (AND): Returns True if ALL sub-conditions match
    """

    # Single field condition
    field: Optional[str] = Field(None, description="Field ID to evaluate")
    operator: Optional[str] = Field(
        None,
        description="Operator: exists, not_exists, equals, not_equals, contains, contains_any, greater_than, etc.",
    )
    value: Optional[Any] = Field(
        None, description="Value to compare against (for equals, contains, etc.)"
    )
    values: Optional[List[Any]] = Field(
        None, description="List of values (for contains_any, in_list, etc.)"
    )
    pattern: Optional[str] = Field(None, description="Regex pattern (for regex_match operator)")

    # Compound conditions
    any_of: Optional[List[Condition]] = Field(
        None, description="OR logic - True if ANY condition matches"
    )
    all_of: Optional[List[Condition]] = Field(
        None, description="AND logic - True if ALL conditions match"
    )

    @field_validator("operator")
    @classmethod
    def validate_operator(cls, v):
        """Ensure operator is valid if provided."""
        if v is None:
            return v

        valid_operators = {
            "exists",
            "not_exists",
            "equals",
            "not_equals",
            "contains",
            "not_contains",
            "contains_any",
            "greater_than",
            "less_than",
            "greater_than_or_equal",
            "less_than_or_equal",
            "in_list",
            "not_in_list",
            "regex_match",
            "word_count_gte",
            "word_count_lte",
        }

        if v not in valid_operators:
            raise ValueError(
                f"Invalid operator '{v}'. Must be one of: {', '.join(sorted(valid_operators))}"
            )

        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"field": "foreign_accounts", "operator": "exists"},
                {"field": "entity_type", "operator": "contains", "value": "S-Corp"},
                {"field": "revenue_range", "operator": "contains_any", "values": ["$1M", "$5M"]},
                {
                    "any_of": [
                        {"field": "state", "operator": "contains", "value": "multi-state"},
                        {
                            "field": "complexity_signals",
                            "operator": "contains",
                            "value": "multi-state",
                        },
                    ]
                },
            ]
        }
    )


# Resolve forward reference for ConversationalField.relevant_when
ConversationalField.model_rebuild()


class FollowUpRule(BaseModel):
    """
    Rule for generating follow-up questions in lead summary.

    When condition matches, the question is added to the summary.
    """

    rule_id: str = Field(
        ..., description="Unique identifier for this rule (e.g., 'fbar_check', 'scorp_salary')"
    )
    condition: Condition = Field(..., description="When to ask this question")
    question: str = Field(..., description="Question to ask")
    priority: int = Field(
        default=0, description="Priority for ordering questions (higher = shown first). Default: 0"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rule_id": "fbar_check",
                "condition": {"field": "foreign_accounts", "operator": "exists"},
                "question": "Have you been filing FBAR (FinCEN Form 114) annually?",
                "priority": 1,
            }
        }
    )


class QualitySignal(BaseModel):
    """
    Quality signal for lead scoring (positive points).

    When condition matches, points are added to lead score.
    """

    signal_id: str = Field(
        ...,
        description="Unique identifier for this signal (e.g., 'revenue_1m_plus', 'urgent_timeline')",
    )
    points: float = Field(..., description="Points to add when condition matches (positive number)")
    condition: Condition = Field(..., description="When to apply this signal")

    @field_validator("points")
    @classmethod
    def validate_points(cls, v):
        """Ensure points is positive."""
        if v < 0:
            raise ValueError(
                "Quality signal points must be positive (use RiskPenalty for negative points)"
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "signal_id": "revenue_1m_plus",
                "points": 15,
                "condition": {
                    "field": "revenue_range",
                    "operator": "contains_any",
                    "values": ["$1M", "$5M"],
                },
            }
        }
    )


class RiskPenalty(BaseModel):
    """
    Risk penalty for lead scoring (negative points).

    When condition matches, points are subtracted from lead score.
    """

    penalty_id: str = Field(
        ...,
        description="Unique identifier for this penalty (e.g., 'red_flag_unfiled_returns', 'incomplete_contact')",
    )
    points: float = Field(
        ..., description="Points to subtract when condition matches (negative number)"
    )
    condition: Condition = Field(..., description="When to apply this penalty")

    @field_validator("points")
    @classmethod
    def validate_points(cls, v):
        """Ensure points is negative."""
        if v > 0:
            raise ValueError(
                "Risk penalty points must be negative (use QualitySignal for positive points)"
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "penalty_id": "red_flag_unfiled_returns",
                "points": -20,
                "condition": {"field": "red_flags", "operator": "contains", "value": "unfiled"},
            }
        }
    )


class OutputTemplate(BaseModel):
    """
    Template for formatting the final lead summary from conversational workflows.

    Defines output structure, scoring rules, follow-up question rules, and export destinations.

    Supports BOTH formats for backward compatibility:
    - Legacy format: quality_signals and risk_penalties as dicts (signal_name → points)
    - New format: quality_signals and risk_penalties as lists with conditions
    """

    format: Literal["lead_summary"] = Field(
        default="lead_summary",
        description="Output format type (currently only 'lead_summary' supported)",
    )
    sections: List[str] = Field(
        ...,
        description="Sections to include in summary (e.g., ['profile', 'situation', 'need', 'score', 'key_context', 'follow_up_questions'])",
        min_length=1,
    )

    # Scoring rules (supports both old and new formats)
    scoring_rules: Dict[str, Any] = Field(
        ...,
        description="Lead scoring configuration (base_score, field_completeness_weight, quality_signals, risk_penalties)",
    )

    # NEW: Follow-up question rules (config-driven)
    follow_up_rules: Optional[List[FollowUpRule]] = Field(
        default=None,
        description="Rules for generating follow-up questions based on extracted fields. If not provided, uses legacy hardcoded logic.",
    )
    max_follow_up_questions: int = Field(
        default=4,
        ge=1,
        le=10,
        description="Maximum number of follow-up questions to include in summary",
    )

    export_destinations: List[str] = Field(
        default=["email", "internal_dashboard"],
        description="Where to send/display the lead summary",
    )

    # Summary formatting options
    summary_template: Literal["structured", "synopsis", "minimal", "detailed"] = Field(
        default="structured",
        description=(
            "Summary format template:\n"
            "- 'structured': Key-value pairs with clear headers (default)\n"
            "- 'synopsis': Narrative paragraph format\n"
            "- 'minimal': Compact one-liner format\n"
            "- 'detailed': Full breakdown with scoring details"
        ),
    )
    include_score_breakdown: bool = Field(
        default=False,
        description="Whether to include detailed score breakdown (base, bonuses, penalties) in summary",
    )

    @field_validator("scoring_rules")
    @classmethod
    def validate_scoring_rules(cls, v):
        """Ensure scoring_rules has required keys and valid format."""
        required_keys = {
            "base_score",
            "field_completeness_weight",
            "quality_signals",
            "risk_penalties",
        }
        if not isinstance(v, dict):
            raise ValueError("scoring_rules must be a dictionary")
        missing = required_keys - set(v.keys())
        if missing:
            raise ValueError(f"scoring_rules is missing required keys: {missing}")

        # Validate quality_signals format (can be dict or list)
        quality_signals = v.get("quality_signals")
        if quality_signals is not None:
            if not isinstance(quality_signals, (dict, list)):
                raise ValueError("quality_signals must be a dict (legacy) or list (new format)")

        # Validate risk_penalties format (can be dict or list)
        risk_penalties = v.get("risk_penalties")
        if risk_penalties is not None:
            if not isinstance(risk_penalties, (dict, list)):
                raise ValueError("risk_penalties must be a dict (legacy) or list (new format)")

        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "Legacy Format (Backward Compatible)",
                    "value": {
                        "format": "lead_summary",
                        "sections": [
                            "profile",
                            "situation",
                            "need",
                            "score",
                            "key_context",
                            "follow_up_questions",
                        ],
                        "scoring_rules": {
                            "base_score": 50,
                            "field_completeness_weight": 20,
                            "quality_signals": {
                                "revenue_1m_plus": 15,
                                "multi_state": 10,
                                "urgent_timeline": 10,
                            },
                            "risk_penalties": {
                                "red_flag_unfiled_returns": -20,
                                "red_flag_irs_notice": -15,
                            },
                        },
                        "export_destinations": ["email", "internal_dashboard"],
                        "summary_template": "structured",
                        "include_score_breakdown": False,
                    },
                },
                {
                    "title": "New Format (Config-Driven with Conditions)",
                    "value": {
                        "format": "lead_summary",
                        "sections": [
                            "profile",
                            "situation",
                            "need",
                            "score",
                            "key_context",
                            "follow_up_questions",
                        ],
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
                                        "values": ["$1M", "$5M"],
                                    },
                                },
                                {
                                    "signal_id": "multi_state",
                                    "points": 10,
                                    "condition": {
                                        "any_of": [
                                            {
                                                "field": "state",
                                                "operator": "contains",
                                                "value": "multi",
                                            },
                                            {
                                                "field": "complexity_signals",
                                                "operator": "contains",
                                                "value": "multi",
                                            },
                                        ]
                                    },
                                },
                            ],
                            "risk_penalties": [
                                {
                                    "penalty_id": "red_flag_unfiled_returns",
                                    "points": -20,
                                    "condition": {
                                        "field": "red_flags",
                                        "operator": "contains",
                                        "value": "unfiled",
                                    },
                                }
                            ],
                        },
                        "follow_up_rules": [
                            {
                                "rule_id": "fbar_check",
                                "condition": {"field": "foreign_accounts", "operator": "exists"},
                                "question": "Have you been filing FBAR (FinCEN Form 114) annually?",
                                "priority": 1,
                            },
                            {
                                "rule_id": "scorp_salary",
                                "condition": {
                                    "field": "entity_type",
                                    "operator": "contains",
                                    "value": "S-Corp",
                                },
                                "question": "Are you taking a reasonable salary from your S-Corp?",
                                "priority": 0,
                            },
                        ],
                        "max_follow_up_questions": 4,
                        "export_destinations": ["email", "internal_dashboard"],
                        "summary_template": "detailed",
                        "include_score_breakdown": True,
                    },
                },
            ]
        }
    )


class ConversationalWorkflowConfig(BaseModel):
    """
    Complete configuration for conversational workflows.

    Uses intelligent field extraction instead of linear question flow.
    """

    required_fields: List[ConversationalField] = Field(
        ...,
        description="Fields that MUST be captured for workflow to complete",
        min_length=1,
    )
    optional_fields: List[ConversationalField] = Field(
        default=[],
        description="Fields that are nice to have but not required",
    )
    inference_rules: Dict[str, str] = Field(
        ...,
        description="Natural language instructions for extracting each field (field_id -> extraction instruction)",
    )
    extraction_strategy: Optional[ExtractionStrategy] = Field(
        default=None,
        description="Configuration for how to extract fields from conversation. If not provided, defaults are used.",
    )
    output_template: Optional[OutputTemplate] = Field(
        default=None,
        description="Output template for formatting lead summary (scoring rules, follow-up rules, etc.)",
    )

    @field_validator("required_fields")
    @classmethod
    def validate_required_field_ids_unique(cls, v):
        """Ensure all required field IDs are unique."""
        field_ids = [field.field_id for field in v]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("All required field IDs must be unique")
        return v

    @field_validator("optional_fields")
    @classmethod
    def validate_optional_field_ids_unique(cls, v, info):
        """Ensure all optional field IDs are unique and don't overlap with required."""
        field_ids = [field.field_id for field in v]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("All optional field IDs must be unique")

        # Check for overlap with required fields
        required_ids = {field.field_id for field in info.data.get("required_fields", [])}
        overlap = set(field_ids) & required_ids
        if overlap:
            raise ValueError(
                f"Optional field IDs cannot overlap with required field IDs: {overlap}"
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "required_fields": [
                    {
                        "field_id": "contact_name",
                        "field_type": "text",
                        "label": "Full name",
                        "description": "Contact person's full name",
                    },
                    {
                        "field_id": "contact_email",
                        "field_type": "email",
                        "label": "Email address",
                    },
                    {
                        "field_id": "entity_type",
                        "field_type": "choice",
                        "label": "Business entity type",
                        "options": ["Sole Proprietor", "LLC", "S-Corp", "C-Corp"],
                    },
                ],
                "optional_fields": [
                    {
                        "field_id": "revenue_range",
                        "field_type": "choice",
                        "label": "Annual revenue range",
                        "options": ["<$100K", "$100K-$500K", "$500K-$1M", "$1M+"],
                    }
                ],
                "inference_rules": {
                    "entity_type": "Extract if user mentions 'LLC', 'S-Corp', 'C-Corp', etc. If unclear, ask: 'What's your business structure?'",
                    "revenue_range": "Infer from cues: 'small team' → $100K-$500K, '10+ employees' → $500K+",
                },
                "extraction_strategy": {
                    "opening_question": "Thanks for reaching out! What's going on with your business?",
                    "max_clarifying_questions": 5,
                    "confirmation_required": True,
                    "confirmation_style": "summary",
                    "extraction_model": "gpt-4o-mini",
                    "confidence_threshold": 0.8,
                    "allow_partial_extraction": False,
                    "tone": "professional",
                },
                "output_template": {
                    "format": "lead_summary",
                    "sections": ["profile", "need", "score", "follow_up_questions"],
                    "scoring_rules": {
                        "base_score": 50,
                        "field_completeness_weight": 20,
                        "quality_signals": [],
                        "risk_penalties": [],
                    },
                    "summary_template": "structured",
                    "include_score_breakdown": False,
                },
            }
        }
    )


# ===== Validation Utilities =====
# These are defined at the end of the file to avoid forward reference issues


class ExtractedFieldValueSchema(BaseModel):
    """
    Schema for extracted field values stored in workflow_sessions.extracted_fields.

    This model ensures consistent structure for frontend rendering.

    Example:
        {
            "contact_name": {
                "value": "John Smith",
                "confidence": 1.0,
                "extraction_method": "direct_tool_call",
                "raw_input": "John Smith",
                "extracted_at": "2026-01-27T19:52:49.354765"
            }
        }
    """

    value: Any = Field(..., description="Extracted value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    extraction_method: str = Field(
        ...,
        description="How field was extracted: natural_language, inference, clarifying_question, direct_statement, direct_tool_call",
    )
    raw_input: str = Field(..., description="Original user input that led to extraction")
    extracted_at: str = Field(..., description="ISO timestamp when field was extracted")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "value": "John Smith",
                "confidence": 1.0,
                "extraction_method": "direct_tool_call",
                "raw_input": "John Smith",
                "extracted_at": "2026-01-27T19:52:49.354765",
            }
        }
    )


def validate_extracted_fields(extracted_fields: Dict[str, Any]) -> None:
    """
    Validate extracted_fields structure from workflow_sessions.

    Args:
        extracted_fields: Dictionary of field_id -> ExtractedFieldValue

    Raises:
        ValueError: If any field doesn't match ExtractedFieldValue schema

    Usage:
        from app.api.models.workflow_models import validate_extracted_fields

        validate_extracted_fields(session.extracted_fields)
    """
    if not extracted_fields:
        return

    errors = []
    for field_id, field_data in extracted_fields.items():
        try:
            ExtractedFieldValueSchema(**field_data)
        except Exception as e:
            errors.append(f"Field '{field_id}': {e}")

    if errors:
        raise ValueError(f"Invalid extracted_fields: {'; '.join(errors)}")


def validate_workflow_config_by_type(workflow_type: str, workflow_config: Dict[str, Any]) -> None:
    """
    Validate workflow_config structure based on workflow_type.

    This function validates that the JSONB workflow_config matches the expected schema:
    - simple/scored: Must have 'steps' array with WorkflowStep structure
    - conversational: Must have required_fields, optional_fields, inference_rules, extraction_strategy

    Args:
        workflow_type: Type of workflow ('simple', 'scored', 'conversational')
        workflow_config: The workflow configuration dictionary

    Raises:
        ValueError: If workflow_config doesn't match expected schema for the workflow_type

    Usage:
        # In API endpoints or services:
        from app.api.models.workflow_models import validate_workflow_config_by_type

        validate_workflow_config_by_type("conversational", my_config)
    """
    if workflow_type == "conversational":
        # Validate against ConversationalWorkflowConfig schema
        try:
            ConversationalWorkflowConfig(**workflow_config)
        except Exception as e:
            raise ValueError(f"Invalid workflow_config for conversational workflow: {e}")
    elif workflow_type in ("simple", "scored"):
        # Validate against WorkflowConfig schema (steps array)
        try:
            WorkflowConfig(**workflow_config)
        except Exception as e:
            raise ValueError(f"Invalid workflow_config for {workflow_type} workflow: {e}")
    else:
        raise ValueError(
            f"Unknown workflow_type: {workflow_type}. Must be 'simple', 'scored', or 'conversational'"
        )
