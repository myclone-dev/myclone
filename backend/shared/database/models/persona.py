from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PersonaBase(BaseModel):
    persona_name: str = Field(
        default="default", description="Persona name (unique per user, default='default')"
    )
    name: str = Field(..., description="Display name of the persona")
    role: Optional[str] = Field(None, description="Professional role/title")
    expertise: Optional[str] = Field(None, description="Areas of expertise")
    company: Optional[str] = Field(None, description="Company affiliation")
    description: Optional[str] = Field(None, description="Brief description of the persona")
    voice_id: Optional[str] = Field(None, description="ElevenLabs voice ID for this persona")
    voice_enabled: bool = Field(
        default=True,
        description="Whether voice chat is enabled for this persona",
    )
    language: Optional[str] = Field(
        default="auto",
        description="Language code for persona responses (auto, en, hi, es, fr, zh, de, ar, it, sv). Default: auto",
    )
    greeting_message: Optional[str] = Field(
        None, description="Custom greeting message for voice chat"
    )
    suggested_questions: Optional[List[str]] = Field(
        None, description="Suggested starter questions for chat UI"
    )
    # Persona-specific avatar
    persona_avatar_url: Optional[str] = Field(
        None, description="Persona-specific avatar URL (S3). Overrides user avatar when set."
    )
    # Default Lead Capture Settings
    default_lead_capture_enabled: bool = Field(
        default=False,
        description="Whether agent captures visitor contact info via conversation",
    )
    # Content Mode Settings
    content_mode_enabled: bool = Field(
        default=False,
        description="Whether content creation mode is enabled for this persona",
    )
    # Email Capture Settings (popup - legacy)
    email_capture_enabled: bool = Field(
        default=False, description="Whether to prompt visitors for email"
    )
    email_capture_message_threshold: int = Field(
        default=5, ge=1, le=20, description="Number of messages before prompting for email"
    )
    email_capture_require_fullname: bool = Field(
        default=True, description="Whether full name is required when capturing email"
    )
    email_capture_require_phone: bool = Field(
        default=False, description="Whether phone number is required when capturing email"
    )
    # Session Time Limit Settings
    session_time_limit_enabled: bool = Field(
        default=False, description="Whether session time limits are enforced for visitors"
    )
    session_time_limit_minutes: float = Field(
        default=30.0,
        ge=0.5,
        le=120,
        description="Maximum session duration in minutes (supports fractions like 2.5 for 2m 30s)",
    )
    session_time_limit_warning_minutes: float = Field(
        default=2.0,
        ge=0.25,
        le=30,
        description="Minutes before limit to show warning (supports fractions)",
    )

    @field_validator("suggested_questions", mode="before")
    @classmethod
    def extract_questions_from_dict(cls, v):
        """
        Extract questions list from database JSONB format.

        Database stores: {"questions": ["Q1", "Q2"], "generated_at": "...", ...}
        API returns: ["Q1", "Q2"]
        """
        if v is None:
            return None
        if isinstance(v, dict):
            return v.get("questions", [])
        if isinstance(v, list):
            return v
        return None

    @field_validator("language", mode="before")
    @classmethod
    def normalize_language(cls, v):
        """
        Normalize language field: NULL values are treated as 'auto'.

        This ensures consistent handling across the system where NULL from
        database is always represented as 'auto' in the API.
        """
        return v if v is not None else "auto"


class PersonaCreate(PersonaBase):
    pass


class PersonaUpdate(BaseModel):
    persona_name: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    expertise: Optional[str] = None
    company: Optional[str] = None
    description: Optional[str] = None
    voice_id: Optional[str] = None
    voice_enabled: Optional[bool] = None
    language: Optional[str] = Field(
        None,
        description="Language code for persona responses (auto, en, hi, es, fr, zh, de, ar, it, sv)",
    )
    # Default Lead Capture Settings
    default_lead_capture_enabled: Optional[bool] = None
    # Content Mode Settings
    content_mode_enabled: Optional[bool] = None
    # Email Capture Settings (popup - legacy)
    email_capture_enabled: Optional[bool] = None
    email_capture_message_threshold: Optional[int] = Field(None, ge=1, le=20)
    email_capture_require_fullname: Optional[bool] = None
    email_capture_require_phone: Optional[bool] = None
    greeting_message: Optional[str] = None
    # Session Time Limit Settings
    session_time_limit_enabled: Optional[bool] = None
    session_time_limit_minutes: Optional[float] = Field(None, ge=0.5, le=120)
    session_time_limit_warning_minutes: Optional[float] = Field(None, ge=0.25, le=30)
    # Persona-specific avatar (not directly settable via update - use avatar endpoints)
    # persona_avatar_url is managed via dedicated upload/delete endpoints


class PersonaResponse(PersonaBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PersonaWithStats(PersonaResponse):
    total_chunks: int = 0
    total_patterns: int = 0
    total_conversations: int = 0


class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to the persona")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    context_window: int = Field(default=5, description="Number of previous messages to include")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Response temperature")
    stream: bool = Field(default=False, description="Whether to stream the response")
    max_tokens: Optional[int] = Field(default=1000, description="Maximum tokens in response")


class ChatResponse(BaseModel):
    response: str = Field(..., description="Persona's response")
    session_id: Optional[str] = Field(None, description="Session ID for conversation tracking")
    thinking_pattern: Optional[str] = Field(None, description="Applied thinking pattern")
    sources: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list, description="Source chunks used"
    )


class ContentUpload(BaseModel):
    content: str = Field(..., description="Text content to add")
    source: str = Field(..., description="Source identifier")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )


class PatternAnalysisResponse(BaseModel):
    persona_id: UUID = Field(..., description="Persona ID")
    patterns: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=dict, description="Extracted patterns by type"
    )
    confidence_scores: Dict[str, float] = Field(
        default_factory=dict, description="Confidence scores for each pattern type"
    )
    last_updated: Optional[datetime] = Field(None, description="Last pattern analysis timestamp")
    sample_count: int = Field(default=0, description="Number of samples analyzed")


# Enhanced session tracking models
class SessionModel(BaseModel):
    session_token: str = Field(..., description="Unique session identifier")
    persona_id: str = Field(..., description="Associated persona ID")
    user_email: str = Field(..., description="User email (anonymous or real)")
    message_count: int = Field(default=0, description="Number of messages in session")
    email_prompted: bool = Field(
        default=False, description="Whether user has been prompted for email"
    )
    email_provided: bool = Field(default=False, description="Whether user has provided real email")
    is_anonymous: bool = Field(default=True, description="Whether session is anonymous")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional session metadata"
    )


class SessionInitResponse(BaseModel):
    session_token: str = Field(..., description="Generated chat session token")
    auth_token: Optional[str] = Field(
        None, description="Generated auth session token for API calls"
    )
    persona_id: str = Field(..., description="Persona ID")
    persona_name: str = Field(..., description="Persona name")
    is_anonymous: bool = Field(default=True, description="Whether session is anonymous")
    auth_expires_at: Optional[str] = Field(None, description="When auth token expires")


class EmailRequest(BaseModel):
    email: str = Field(..., description="User's email address")
    fullname: Optional[str] = Field(None, max_length=255, description="User's full name")
    phone: Optional[str] = Field(None, max_length=50, description="User's phone number")


class EmailProvisionResponse(BaseModel):
    success: bool = Field(..., description="Whether email was successfully provided")
    email: str = Field(..., description="Provided email address")
    previous_conversations: bool = Field(..., description="Whether user has previous conversations")
    merged_sessions: int = Field(default=0, description="Number of anonymous sessions merged")


class LeadCaptureRequest(BaseModel):
    email: str = Field(..., description="Captured email address")
    fullname: str | None = Field(None, max_length=255, description="Captured full name")
    phone: str | None = Field(None, max_length=50, description="Captured phone number")


class LeadCaptureResponse(BaseModel):
    success: bool = Field(..., description="Whether lead capture was successful")
    email: str = Field(..., description="Captured email address")
    user_id: str = Field(..., description="User ID (new or existing)")
    is_new_user: bool = Field(..., description="Whether a new visitor user was created")
    previous_conversations: bool = Field(
        default=False, description="Whether user has previous conversations with this persona"
    )
    token: str | None = Field(None, description="JWT token (also set in HTTP-only cookie)")


class TrackedChatRequest(BaseModel):
    message: str = Field(..., description="User message to the persona")
    session_token: str = Field(..., description="Session token for tracking")
    context_window: int = Field(default=5, description="Number of previous messages to include")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Response temperature")
    attachment_ids: list[str] | None = Field(
        default=None,
        description="Optional list of attachment UUIDs to include in message context (max 5)",
    )


class SpecialChatRequest(BaseModel):
    message: str = Field(default="", description="Optional user message with the PDF")
    session_token: str = Field(..., description="Session token for tracking")
    pdf_url: str | None = Field(default=None, description="Optional URL or S3 path to the PDF file")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Response temperature")
