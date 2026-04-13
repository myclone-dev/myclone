"""
Pydantic schemas for Knowledge Library management

This module defines request/response models for knowledge library operations,
including knowledge source management and persona-knowledge relationships.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shared.utils.validators import slugify_persona_name

# ============================================================================
# Knowledge Source Base Models
# ============================================================================


class KnowledgeSourceBase(BaseModel):
    """Base model for all knowledge sources"""

    id: UUID = Field(..., description="Unique identifier for the knowledge source")
    type: str = Field(..., description="Source type: linkedin, twitter, website, document, youtube")
    display_name: str = Field(..., description="Human-readable name for the source")
    embeddings_count: int = Field(
        default=0, description="Number of embeddings/chunks for this source"
    )
    created_at: datetime = Field(..., description="When the source was created")
    updated_at: datetime = Field(..., description="When the source was last updated")
    used_by_personas_count: int = Field(
        default=0, description="Number of personas using this source"
    )


# ============================================================================
# Platform-Specific Knowledge Source Models
# ============================================================================


class LinkedInKnowledgeSource(KnowledgeSourceBase):
    """LinkedIn profile knowledge source"""

    type: str = Field(default="linkedin", description="Source type")
    headline: Optional[str] = Field(None, description="LinkedIn headline")
    summary: Optional[str] = Field(None, description="LinkedIn summary/about section")
    location: Optional[str] = Field(None, description="User location")
    posts_count: int = Field(default=0, description="Number of LinkedIn posts")
    experiences_count: int = Field(default=0, description="Number of work experiences")
    skills_count: int = Field(default=0, description="Number of skills")
    latest_experience_title: Optional[str] = Field(
        None, description="Title from most recent work experience"
    )
    last_synced_at: Optional[datetime] = Field(None, description="Last time data was synced")

    model_config = ConfigDict(from_attributes=True)


class TwitterKnowledgeSource(KnowledgeSourceBase):
    """Twitter profile knowledge source"""

    type: str = Field(default="twitter", description="Source type")
    username: str = Field(..., description="Twitter username (without @)")
    display_name_twitter: Optional[str] = Field(None, description="Twitter display name")
    bio: Optional[str] = Field(None, description="Twitter bio")
    verified: bool = Field(default=False, description="Whether account is verified")
    tweets_count: int = Field(default=0, description="Number of tweets scraped")
    followers_count: int = Field(default=0, description="Number of followers")
    following_count: int = Field(default=0, description="Number of accounts following")
    last_scraped_at: Optional[datetime] = Field(None, description="Last time data was scraped")

    model_config = ConfigDict(from_attributes=True)


class WebsiteKnowledgeSource(KnowledgeSourceBase):
    """Website scrape knowledge source"""

    type: str = Field(default="website", description="Source type")
    website_url: str = Field(..., description="Root URL that was scraped")
    title: Optional[str] = Field(None, description="Website title")
    description: Optional[str] = Field(None, description="Website description/meta description")
    scraper: str = Field(default="firecrawl", description="Scraper used (firecrawl, etc.)")
    pages_crawled: int = Field(default=0, description="Number of pages crawled")
    max_pages_crawled: int = Field(default=1, description="Maximum pages configured to crawl")
    scraping_status: str = Field(
        default="completed", description="Status: pending, in_progress, completed, failed"
    )
    scraped_at: datetime = Field(..., description="When the scrape was performed")

    model_config = ConfigDict(from_attributes=True)


class DocumentKnowledgeSource(KnowledgeSourceBase):
    """Document knowledge source (PDF, DOCX, etc.)"""

    type: str = Field(default="document", description="Source type")
    filename: str = Field(..., description="Original filename")
    document_type: str = Field(..., description="File type: pdf, xlsx, pptx, docx, csv, txt, md")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    page_count: Optional[int] = Field(None, description="Number of pages (for PDFs)")
    sheet_count: Optional[int] = Field(None, description="Number of sheets (for Excel)")
    slide_count: Optional[int] = Field(None, description="Number of slides (for PowerPoint)")
    uploaded_at: datetime = Field(..., description="When the document was uploaded")

    model_config = ConfigDict(from_attributes=True)


class YouTubeKnowledgeSource(KnowledgeSourceBase):
    """YouTube video knowledge source"""

    type: str = Field(default="youtube", description="Source type")
    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., description="Video title")
    description: Optional[str] = Field(None, description="Video description")
    channel_name: Optional[str] = Field(None, description="Channel name")
    duration_seconds: Optional[int] = Field(None, description="Video duration in seconds")
    has_transcript: bool = Field(default=False, description="Whether transcript is available")
    published_at: Optional[datetime] = Field(None, description="When video was published")

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Knowledge Library Response Models
# ============================================================================


class KnowledgeLibraryResponse(BaseModel):
    """Response containing user's complete knowledge library"""

    linkedin: List[LinkedInKnowledgeSource] = Field(
        default_factory=list, description="LinkedIn profiles"
    )
    twitter: List[TwitterKnowledgeSource] = Field(
        default_factory=list, description="Twitter profiles"
    )
    websites: List[WebsiteKnowledgeSource] = Field(
        default_factory=list, description="Website scrapes"
    )
    documents: List[DocumentKnowledgeSource] = Field(
        default_factory=list, description="Uploaded documents"
    )
    youtube: List[YouTubeKnowledgeSource] = Field(
        default_factory=list, description="YouTube videos"
    )
    total_sources: int = Field(..., description="Total number of knowledge sources")
    total_embeddings: int = Field(..., description="Total number of embeddings across all sources")


class KnowledgeSourceDetail(BaseModel):
    """Detailed view of a specific knowledge source"""

    source: KnowledgeSourceBase = Field(..., description="The knowledge source details")
    embeddings_count: int = Field(..., description="Number of embeddings for this source")
    chunks_preview: List[Dict[str, Any]] = Field(
        default_factory=list, description="Preview of first few chunks"
    )
    used_by_personas: List[Dict[str, Any]] = Field(
        default_factory=list, description="Personas using this source"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# ============================================================================
# Persona Knowledge Models
# ============================================================================


class PersonaKnowledgeSource(BaseModel):
    """Knowledge source attached to a persona"""

    id: UUID = Field(..., description="persona_data_sources.id")
    source_type: str = Field(..., description="Type: linkedin, twitter, website, document, youtube")
    source_record_id: UUID = Field(..., description="ID of the actual source record")
    display_name: str = Field(..., description="Human-readable name")
    enabled: bool = Field(..., description="Whether this source is currently enabled")
    enabled_at: Optional[datetime] = Field(None, description="When source was enabled")
    disabled_at: Optional[datetime] = Field(None, description="When source was disabled")
    embeddings_count: int = Field(default=0, description="Number of embeddings for this source")
    created_at: datetime = Field(..., description="When source was attached to persona")

    model_config = ConfigDict(from_attributes=True)


class PersonaKnowledgeResponse(BaseModel):
    """Response for persona's knowledge sources"""

    persona_id: UUID = Field(..., description="Persona ID")
    persona_name: str = Field(..., description="Persona name (e.g., 'default', 'professional')")
    name: str = Field(..., description="Display name of the persona")
    sources: List[PersonaKnowledgeSource] = Field(
        default_factory=list, description="All knowledge sources for this persona"
    )
    total_sources: int = Field(..., description="Total number of sources")
    enabled_sources: int = Field(..., description="Number of enabled sources")
    total_embeddings: int = Field(..., description="Total embeddings across all enabled sources")


# ============================================================================
# Available Sources for Persona (User's Library)
# ============================================================================


class AvailableKnowledgeSource(BaseModel):
    """Knowledge source available to attach to a persona"""

    source_type: str = Field(..., description="Type: linkedin, twitter, website, document, youtube")
    source_record_id: UUID = Field(..., description="ID of the source record")
    display_name: str = Field(..., description="Human-readable name")
    embeddings_count: int = Field(default=0, description="Number of embeddings")
    is_attached: bool = Field(
        default=False, description="Whether this source is already attached to the persona"
    )
    is_enabled: bool = Field(
        default=False, description="Whether this source is enabled (only relevant if attached)"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Platform-specific metadata")

    model_config = ConfigDict(from_attributes=True)


class AvailableKnowledgeSourcesResponse(BaseModel):
    """Response for available knowledge sources to attach to persona"""

    persona_id: UUID = Field(..., description="Persona ID")
    user_id: UUID = Field(..., description="User ID (owner of knowledge)")
    available_sources: List[AvailableKnowledgeSource] = Field(
        default_factory=list, description="All available knowledge sources"
    )
    total_available: int = Field(..., description="Total number of available sources")
    already_attached: int = Field(..., description="Number of sources already attached")


# ============================================================================
# Request Models
# ============================================================================


class KnowledgeSourceAttachment(BaseModel):
    """Request to attach a single knowledge source"""

    source_type: str = Field(..., description="Type: linkedin, twitter, website, document, youtube")
    source_record_id: UUID = Field(..., description="ID of the source record to attach")


class AttachKnowledgeRequest(BaseModel):
    """Request to attach multiple knowledge sources to a persona"""

    sources: List[KnowledgeSourceAttachment] = Field(..., description="List of sources to attach")


class PersonaCreateWithKnowledge(BaseModel):
    """Create persona with knowledge sources in one request"""

    persona_name: str = Field(
        default="default", description="Persona name (unique per user, default='default')"
    )
    name: str = Field(..., description="Display name of the persona")
    role: Optional[str] = Field(None, description="Professional role")
    expertise: Optional[str] = Field(None, description="Areas of expertise")
    company: Optional[str] = Field(None, description="Company affiliation")
    description: Optional[str] = Field(None, description="Brief description of the persona")
    voice_id: Optional[str] = Field(None, description="ElevenLabs voice ID for this persona")
    language: Optional[str] = Field(
        default="auto",
        description="Language code for persona responses (auto, en, hi, es, fr, zh, de, ar, it, sv). Default: auto",
    )
    knowledge_sources: List[KnowledgeSourceAttachment] = Field(
        default_factory=list, description="Knowledge sources to attach"
    )

    @field_validator("persona_name")
    @classmethod
    def validate_persona_name(cls, v: str) -> str:
        """
        Validate and slugify persona name for URL safety

        Transforms user input into URL-friendly slug:
        - "Engineer Persona" → "engineer-persona"
        - "Sales & Marketing!" → "sales-marketing"
        - "Tech Advisor 2024" → "tech-advisor-2024"

        Validation rules:
        - 3-60 characters
        - Lowercase alphanumeric + hyphens
        - No leading/trailing/consecutive hyphens
        - Cannot be reserved name (default, new, edit, etc.)
        """
        return slugify_persona_name(v)


class PersonaUpdateWithKnowledge(BaseModel):
    """Update persona and optionally update knowledge sources"""

    persona_name: Optional[str] = Field(None, description="Persona name")
    name: Optional[str] = Field(None, description="Display name")
    role: Optional[str] = Field(None, description="Professional role")
    expertise: Optional[str] = Field(None, description="Areas of expertise")
    company: Optional[str] = Field(None, description="Company affiliation")
    description: Optional[str] = Field(None, description="Brief description")
    voice_id: Optional[str] = Field(None, description="ElevenLabs voice ID")
    voice_enabled: Optional[bool] = Field(
        None, description="Whether voice chat is enabled for this persona"
    )
    language: Optional[str] = Field(
        None,
        description="Language code for persona responses (auto, en, hi, es, fr, zh, de, ar, it, sv)",
    )
    greeting_message: Optional[str] = Field(
        None, description="Custom greeting message for voice chat"
    )
    suggested_questions: Optional[List[str]] = Field(
        None, description="Suggested starter questions for chat UI"
    )
    knowledge_sources: Optional[List[KnowledgeSourceAttachment]] = Field(
        None, description="If provided, REPLACES all current knowledge sources"
    )
    # Default Lead Capture Settings
    default_lead_capture_enabled: Optional[bool] = Field(
        None, description="Whether agent captures visitor contact info via conversation"
    )
    # Content Mode Settings
    content_mode_enabled: Optional[bool] = Field(
        None, description="Whether content creation mode is enabled for this persona"
    )
    # Email Capture Settings (popup - legacy)
    email_capture_enabled: Optional[bool] = Field(
        None, description="Whether to prompt visitors for email"
    )
    email_capture_message_threshold: Optional[int] = Field(
        None, ge=1, le=20, description="Number of messages before prompting for email"
    )
    email_capture_require_fullname: Optional[bool] = Field(
        None, description="Whether full name is required when capturing email"
    )
    email_capture_require_phone: Optional[bool] = Field(
        None, description="Whether phone number is required when capturing email"
    )
    # Calendar Integration Settings
    calendar_enabled: Optional[bool] = Field(
        None, description="Whether calendar integration is enabled for this persona"
    )
    calendar_url: Optional[str] = Field(
        None, max_length=500, description="Calendly/Cal.com URL for booking calls"
    )
    calendar_display_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Display name for calendar link (e.g., '30-min intro call')",
    )
    # Conversation Summary Email Settings
    send_summary_email_enabled: Optional[bool] = Field(
        None,
        description="Whether to send conversation summary emails to persona owner after conversations end",
    )
    # Webhook Integration Settings
    webhook_enabled: Optional[bool] = Field(
        None, description="Whether webhook integration is enabled for this persona"
    )
    webhook_url: Optional[str] = Field(
        None, max_length=500, description="HTTPS webhook URL for receiving events"
    )
    webhook_events: Optional[List[str]] = Field(
        None, description="List of event types to send (e.g., ['conversation.finished'])"
    )
    webhook_secret: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional secret for webhook signature verification",
    )
    # Session Time Limit Settings
    session_time_limit_enabled: Optional[bool] = Field(
        None, description="Whether session time limits are enforced for visitors"
    )
    session_time_limit_minutes: Optional[float] = Field(
        None,
        ge=0.5,
        le=120,
        description="Maximum session duration in minutes (0.5-120, supports fractions like 2.5 for 2m 30s)",
    )
    session_time_limit_warning_minutes: Optional[float] = Field(
        None,
        ge=0.25,
        le=30,
        description="Minutes before limit to show warning (0.25-30, supports fractions)",
    )

    @field_validator("persona_name")
    @classmethod
    def validate_persona_name(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate and slugify persona name if provided

        Only validates if a value is provided (since field is Optional for updates).
        Same validation rules as PersonaCreateWithKnowledge.
        """
        if v is None:
            return None
        return slugify_persona_name(v)

    @model_validator(mode="after")
    def validate_session_time_limits(self) -> "PersonaUpdateWithKnowledge":
        """
        Validate that warning time is less than session duration.

        Only validates if both values are provided (since fields are Optional for updates).
        """
        if (
            self.session_time_limit_warning_minutes is not None
            and self.session_time_limit_minutes is not None
        ):
            if self.session_time_limit_warning_minutes >= self.session_time_limit_minutes:
                raise ValueError("Warning time must be less than session duration")
        return self


class PersonaWithKnowledgeResponse(BaseModel):
    """Response for persona with knowledge information"""

    id: UUID = Field(..., description="Persona ID")
    user_id: UUID = Field(..., description="Owner user ID")
    persona_name: str = Field(..., description="Persona name")
    name: str = Field(..., description="Display name")
    role: Optional[str] = Field(None, description="Professional role")
    expertise: Optional[str] = Field(None, description="Areas of expertise")
    company: Optional[str] = Field(None, description="Company affiliation")
    description: Optional[str] = Field(None, description="Brief description")
    voice_id: Optional[str] = Field(None, description="ElevenLabs voice ID")
    voice_enabled: bool = Field(
        default=True, description="Whether voice chat is enabled for this persona"
    )
    language: Optional[str] = Field(
        default="auto",
        description="Language code for persona responses (auto, en, hi, es, fr, zh, de, ar, it, sv)",
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
    knowledge_sources_count: int = Field(
        default=0, description="Number of attached knowledge sources"
    )
    enabled_sources_count: int = Field(default=0, description="Number of enabled sources")
    total_embeddings: int = Field(default=0, description="Total embeddings across all sources")
    is_private: bool = Field(default=False, description="Whether persona requires access control")
    access_control_enabled_at: Optional[datetime] = Field(
        None, description="When access control was enabled"
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
        default=5, description="Number of messages before prompting for email"
    )
    email_capture_require_fullname: bool = Field(
        default=True, description="Whether full name is required when capturing email"
    )
    email_capture_require_phone: bool = Field(
        default=False, description="Whether phone number is required when capturing email"
    )
    # # Calendar Integration Settings
    calendar_enabled: bool = Field(
        default=False, description="Whether calendar integration is enabled for this persona"
    )
    calendar_url: Optional[str] = Field(
        default=None, description="Calendly/Cal.com URL for booking calls"
    )
    calendar_display_name: Optional[str] = Field(
        default=None, description="Display name for calendar link (e.g., '30-min intro call')"
    )
    # Conversation Summary Email Settings
    send_summary_email_enabled: bool = Field(
        default=True,
        description="Whether to send conversation summary emails to persona owner after conversations end",
    )
    # Webhook Integration Settings
    webhook_enabled: bool = Field(
        default=False, description="Whether webhook integration is enabled"
    )
    webhook_url: Optional[str] = Field(default=None, description="Webhook URL")
    webhook_events: Optional[List[str]] = Field(
        default=None, description="Events to send to webhook"
    )
    # Session Time Limit Settings
    session_time_limit_enabled: bool = Field(
        default=False, description="Whether session time limits are enforced for visitors"
    )
    session_time_limit_minutes: float = Field(
        default=30.0,
        description="Maximum session duration in minutes (supports fractions like 2.5 for 2m 30s)",
    )
    session_time_limit_warning_minutes: float = Field(
        default=2.0, description="Minutes before limit to show warning (supports fractions)"
    )
    created_at: datetime = Field(..., description="When persona was created")
    updated_at: datetime = Field(..., description="When persona was last updated")

    model_config = ConfigDict(from_attributes=True)


class UserPersonasResponse(BaseModel):
    """Response for user's personas list"""

    user_id: UUID = Field(..., description="User ID")
    personas: List[PersonaWithKnowledgeResponse] = Field(
        default_factory=list, description="List of user's personas"
    )
    total_personas: int = Field(..., description="Total number of personas")


# ============================================================================
# Operation Response Models
# ============================================================================


class DeleteKnowledgeSourceResponse(BaseModel):
    """Response for knowledge source deletion"""

    success: bool = Field(..., description="Whether deletion was successful")
    source_type: str = Field(..., description="Type of source deleted")
    source_record_id: UUID = Field(..., description="ID of deleted source")
    embeddings_deleted: int = Field(..., description="Number of embeddings deleted")
    personas_affected: int = Field(
        ..., description="Number of personas that were using this source"
    )
    message: str = Field(..., description="Human-readable message")


class ReIngestKnowledgeSourceResponse(BaseModel):
    """Response for knowledge source re-ingestion"""

    success: bool = Field(..., description="Whether re-ingestion was successful")
    source_type: str = Field(..., description="Type of source re-ingested")
    source_record_id: UUID = Field(..., description="ID of source re-ingested")
    old_embeddings_deleted: int = Field(..., description="Number of old embeddings deleted")
    new_embeddings_created: int = Field(..., description="Number of new embeddings created")
    message: str = Field(..., description="Human-readable message")
