"""
Pydantic models for LiveKit metadata and communication

These models ensure type-safe serialization/deserialization of data
passed between the backend and LiveKit agents.
"""

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class PersonaMetadata(BaseModel):
    """Persona information to be passed to LiveKit agent

    This model is compatible with both:
    - SQLAlchemy ORM Persona objects (from database)
    - JSON data (from LiveKit metadata)
    """

    # TODO: Figure out whether we need these optional fields or not
    id: str = Field(..., description="Persona UUID as string")
    name: str = Field(..., description="Persona display name")
    username: str = Field(
        ...,
        validation_alias="persona_name",
        serialization_alias="persona_name",
        description="Unique Persona name for identification",
    )
    user_fullname: Optional[str] = Field(None, description="User's full name from users table")
    role: Optional[str] = Field(default="Expert", description="Professional role")
    company: Optional[str] = Field(default="Independent", description="Company affiliation")
    description: Optional[str] = Field(
        default="A knowledgeable expert", description="Brief description"
    )
    voice_id: Optional[str] = Field(None, description="ElevenLabs voice ID")
    language: Optional[str] = Field(
        default="auto",
        description="Language code for persona responses (auto, en, hi, es, fr, zh, de, ar, it, sv)",
    )
    greeting_message: Optional[str] = Field(
        None, description="Custom greeting message for voice chat"
    )

    @field_validator("id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID objects to strings for compatibility with ORM"""
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        from_attributes = True  # Allows creating from ORM objects (Pydantic v2)
        populate_by_name = True  # Allow both field name and alias for deserialization


class PatternMetadata(BaseModel):
    """Behavior pattern data for persona"""

    pattern_type: str = Field(..., description="Type of pattern (e.g., 'communication_style')")
    pattern_data: Dict[str, Any] = Field(default_factory=dict, description="Pattern configuration")


class PersonaPromptMetadata(BaseModel):
    """Persona prompt configuration

    This model is compatible with both:
    - SQLAlchemy ORM PersonaPrompt objects (from database)
    - JSON data (from LiveKit metadata)
    """

    id: Optional[str] = None  # UUID as string - prompt ID
    persona_id: Optional[str] = None  # UUID as string
    introduction: Optional[str] = None  # Made optional to handle edge cases
    thinking_style: Optional[str] = None
    area_of_expertise: Optional[str] = None
    chat_objective: Optional[str] = None
    objective_response: Optional[str] = None
    example_responses: Optional[str] = None
    target_audience: Optional[str] = None
    prompt_template_id: Optional[str] = None  # UUID as string - FK to prompt_templates
    example_prompt: Optional[str] = None
    is_dynamic: bool = False
    is_active: bool = True
    response_structure: Optional[str] = None
    conversation_flow: Optional[str] = None
    strict_guideline: Optional[str] = None
    created_at: Optional[str] = None  # ISO format datetime string
    updated_at: Optional[str] = None  # ISO format datetime string

    class Config:
        from_attributes = True  # Allows creating from ORM objects (Pydantic v2)

    @field_validator("id", "persona_id", "prompt_template_id", mode="before")
    @classmethod
    def convert_uuid_to_str(cls, v):
        """Convert UUID objects to strings"""
        if v is not None and not isinstance(v, str):
            return str(v)
        return v

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def convert_datetime_to_str(cls, v):
        """Convert datetime objects to ISO format strings"""
        if v is not None and not isinstance(v, str):
            if hasattr(v, "isoformat"):
                return v.isoformat()
            return str(v)
        return v


class LiveKitDispatchMetadata(BaseModel):
    """Complete metadata payload for LiveKit dispatch

    This is serialized to JSON and included in the LiveKit dispatch request.
    The agent deserializes it to access persona data without hitting the database.
    """

    persona_id: str = Field(..., description="Persona UUID as string for backward compatibility")
    persona_data: PersonaMetadata = Field(..., description="Full persona information")
    patterns: Dict[str, Any] = Field(default_factory=dict, description="Behavior patterns by type")
    persona_prompt: Optional[PersonaPromptMetadata] = Field(
        None, description="Persona prompt configuration"
    )
    session_token: Optional[str] = Field(None, description="Optional session identifier")
    # Email capture settings
    email_capture_enabled: bool = Field(default=False, description="Whether to prompt for email")
    email_capture_message_threshold: int = Field(
        default=5, description="Number of messages before prompting"
    )
    email_capture_require_fullname: bool = Field(
        default=True, description="Whether full name is required"
    )
    email_capture_require_phone: bool = Field(
        default=False, description="Whether phone number is required"
    )
    email_capture_completed: bool = Field(
        default=False,
        description="Whether user has already completed email capture for this session",
    )
    # Calendar settings
    calendar_enabled: bool = Field(
        default=False, description="Whether calendar link sharing is enabled"
    )
    calendar_url: Optional[str] = Field(None, description="Calendly/Cal.com URL for booking")
    calendar_display_name: Optional[str] = Field(
        None, description='Display name for calendar link (e.g., "30-min intro call")'
    )
    # Workflow settings
    workflow_id: Optional[str] = Field(None, description="Active workflow UUID as string")
    workflow_title: Optional[str] = Field(None, description="Workflow title")
    workflow_type: Optional[str] = Field(
        None, description="Workflow type (simple, scored, conversational)"
    )
    workflow_opening_message: Optional[str] = Field(
        None, description="Opening message for workflow"
    )
    workflow_objective: Optional[str] = Field(
        None, description="LLM-generated objective for guiding user toward workflow"
    )
    workflow_trigger_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Trigger config for workflow promotion (promotion_mode, max_attempts, cooldown_turns)",
    )
    # Linear workflow fields
    workflow_steps: Optional[list] = Field(
        None, description="Workflow question steps (for linear workflows)"
    )
    workflow_result_config: Optional[Dict[str, Any]] = Field(
        None, description="Result configuration for scored workflows"
    )
    # Conversational workflow fields
    workflow_required_fields: Optional[List[Dict[str, Any]]] = Field(
        None, description="Required fields for conversational workflows"
    )
    workflow_optional_fields: Optional[List[Dict[str, Any]]] = Field(
        None, description="Optional fields for conversational workflows"
    )
    workflow_extraction_strategy: Optional[Dict[str, Any]] = Field(
        None, description="Extraction strategy configuration for conversational workflows"
    )
    workflow_inference_rules: Optional[Dict[str, Any]] = Field(
        None, description="Field inference rules for conversational workflows"
    )
    workflow_output_template: Optional[Dict[str, Any]] = Field(
        None, description="Output template for workflow results"
    )
    workflow_agent_instructions: Optional[str] = Field(
        None,
        description="Free-text behavioral rules injected into the system prompt. "
        "Allows workflow-specific agent behavior without code changes.",
    )
    workflow_reference_data: Optional[str] = Field(
        None,
        description="Free-text reference data injected into the system prompt (e.g., menu, "
        "product catalog, pricing table). The agent can look up facts from this data.",
    )
    workflow_response_mode: Optional[Literal["strict", "flexible"]] = Field(
        None,
        description="Controls how strictly the agent follows brevity rules. "
        "'strict' (default/None): standard brevity rules apply. "
        "'flexible': relaxes word-count limits and 'answer only what is asked' rules "
        "so the agent can upsell, show price breakdowns, and follow workflow-specific instructions.",
    )
    # Default lead capture (always-on basic name/email/phone capture)
    default_capture_enabled: bool = Field(
        default=True,
        description="Whether default lead capture (name/email/phone) is active. "
        "Automatically disabled when a conversational workflow handles capture.",
    )
    # Content mode (dogfooding - off by default)
    content_mode_enabled: bool = Field(
        default=False,
        description="Whether content creation mode is enabled for this persona",
    )
    # Suggested questions for chat UI
    suggested_questions: Optional[List[str]] = Field(
        None, description="Suggested starter questions for chat UI"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "persona_id": "550e8400-e29b-41d4-a716-446655440000",
                "persona_data": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Dr. Jane Smith",
                    "username": "janesmith",
                    "role": "AI Researcher",
                    "company": "Tech Corp",
                    "description": "Expert in machine learning",
                    "voice_id": "abc123",
                },
                "patterns": {
                    "communication_style": {
                        "tone": "professional",
                        "formality": "semi-formal",
                    }
                },
                "persona_prompt": {
                    "persona_id": "550e8400-e29b-41d4-a716-446655440000",
                    "introduction": "You are Dr. Jane Smith...",
                },
                "session_token": "session_xyz",
            }
        }
