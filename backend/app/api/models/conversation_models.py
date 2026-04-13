"""
Pydantic models for conversation API endpoints
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ConversationDetail(BaseModel):
    """Detailed conversation information"""

    id: str = Field(..., description="Conversation UUID")
    persona_id: str = Field(..., description="Persona UUID")
    session_id: Optional[str] = Field(
        None, description="Session identifier (LiveKit room/voice session)"
    )
    workflow_session_id: Optional[str] = Field(
        None, description="Workflow session UUID (if a lead capture workflow was completed)"
    )
    extracted_fields: Optional[Dict[str, Any]] = Field(
        None, description="Extracted lead capture fields (contact info, service needs, etc.)"
    )
    result_data: Optional[Dict[str, Any]] = Field(
        None, description="Workflow result data (lead scoring, quality rating, follow-up questions)"
    )
    user_email: Optional[str] = Field(None, description="User email address")
    user_fullname: Optional[str] = Field(None, description="User full name")
    user_phone: Optional[str] = Field(None, description="User phone number")
    conversation_type: str = Field(..., description="Type of conversation ('text' or 'voice')")
    messages: List[Dict[str, Any]] = Field(
        default_factory=list, description="Conversation messages"
    )
    conversation_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_at: datetime = Field(..., description="Conversation creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(..., description="Total number of messages in conversation")

    # Recording fields (voice conversations only)
    recording_url: Optional[str] = Field(
        None, description="Presigned S3 URL for voice recording playback"
    )
    recording_status: Optional[str] = Field(
        None,
        description="Recording status: disabled, pending, active, completed, failed",
    )
    recording_duration_seconds: Optional[int] = Field(
        None, description="Duration of recording in seconds"
    )

    class Config:
        from_attributes = True


class ConversationSummary(BaseModel):
    """Summary of a conversation for list views"""

    id: str = Field(..., description="Conversation UUID")
    persona_id: str = Field(..., description="Persona UUID")
    session_id: Optional[str] = Field(
        None, description="Session identifier (LiveKit room/voice session)"
    )
    workflow_session_id: Optional[str] = Field(
        None, description="Workflow session UUID (if a lead capture workflow was completed)"
    )
    extracted_fields: Optional[Dict[str, Any]] = Field(
        None, description="Extracted lead capture fields (contact info, service needs, etc.)"
    )
    result_data: Optional[Dict[str, Any]] = Field(
        None, description="Workflow result data (lead scoring, quality rating, follow-up questions)"
    )
    user_email: Optional[str] = Field(None, description="User email address")
    user_fullname: Optional[str] = Field(None, description="User full name")
    user_phone: Optional[str] = Field(None, description="User phone number")
    conversation_type: str = Field(..., description="Type of conversation ('text' or 'voice')")
    message_count: int = Field(..., description="Number of messages in conversation")
    last_message_preview: Optional[str] = Field(
        None, description="Preview of the last message (first 100 chars)"
    )
    created_at: datetime = Field(..., description="Conversation creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    """Response for conversation list endpoints"""

    conversations: List[ConversationSummary] = Field(
        default_factory=list, description="List of conversations"
    )
    total: int = Field(..., description="Total number of conversations")
    limit: int = Field(..., description="Limit applied to the query")
    offset: int = Field(..., description="Offset applied to the query")
    has_more: bool = Field(..., description="Whether there are more conversations available")
    text_conversations: int = Field(
        default=0, description="Total number of text conversations (aggregate count)"
    )
    voice_conversations: int = Field(
        default=0, description="Total number of voice conversations (aggregate count)"
    )


class ConversationQueryParams(BaseModel):
    """Query parameters for conversation listing"""

    limit: int = Field(default=100, ge=1, le=500, description="Maximum number of results")
    offset: int = Field(default=0, ge=0, description="Number of results to skip")
    conversation_type: Optional[str] = Field(
        None, description="Filter by conversation type ('text' or 'voice')"
    )

    class Config:
        from_attributes = True


class ConversationSummaryResult(BaseModel):
    """AI-generated summary of a conversation"""

    conversation_id: str = Field(..., description="Conversation UUID")
    summary: str = Field(..., description="AI-generated summary of the conversation")
    key_topics: str = Field(..., description="Main topics discussed in the conversation")
    sentiment: str = Field(
        ..., description="Overall sentiment of the conversation (positive/neutral/negative/mixed)"
    )
    message_count: int = Field(..., description="Total number of messages in the conversation")
    conversation_type: str = Field(..., description="Type of conversation ('text' or 'voice')")
    generated_at: datetime = Field(..., description="When this summary was generated")

    class Config:
        from_attributes = True


class ConversationPostProcessRequest(BaseModel):
    """Request model for internal post-processing endpoint.

    Called by the LiveKit agent during shutdown to hand off slow operations
    (AI summary, email, webhook, lead scoring) to the FastAPI backend.
    """

    persona_id: UUID
    session_token: str
    conversation_id: UUID
    conversation_type: str = Field(..., description="'voice' or 'text'")
    conversation_history: List[Dict[str, Any]]
    persona_name: str = ""
    # Optional workflow data
    workflow_session_id: Optional[UUID] = None
    workflow_extracted_fields: Optional[Dict[str, Any]] = None
    workflow_context: Optional[Dict[str, Any]] = None
    workflow_is_active: bool = False
    captured_lead_data: Optional[Dict[str, Any]] = None
