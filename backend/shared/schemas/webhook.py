"""
Webhook schemas for API requests and responses
"""

from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class WebhookCreateRequest(BaseModel):
    """Request schema for creating/updating a webhook"""

    url: HttpUrl = Field(..., description="HTTPS webhook URL (Zapier, Make, n8n, Slack, etc.)")
    events: List[str] = Field(
        default=["conversation.finished"],
        description="List of event types to send to this webhook",
    )
    secret: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional secret for webhook signature verification (unused in MVP)",
    )


class WebhookUpdateRequest(BaseModel):
    """Request schema for updating a webhook (all fields optional)"""

    url: Optional[HttpUrl] = Field(None, description="HTTPS webhook URL")
    events: Optional[List[str]] = Field(None, description="List of event types")
    secret: Optional[str] = Field(None, max_length=255, description="Optional secret")
    enabled: Optional[bool] = Field(None, description="Enable or disable webhook")


class WebhookResponse(BaseModel):
    """Response schema for webhook configuration"""

    enabled: bool = Field(..., description="Whether webhook is enabled")
    url: Optional[str] = Field(None, description="Webhook URL (null if not configured)")
    events: Optional[List[str]] = Field(None, description="Event types sent to webhook")
    has_secret: bool = Field(
        ..., description="Whether a secret is configured (secret value is never exposed)"
    )
    personas_count: int = Field(..., description="Number of personas this webhook applies to")

    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "url": "https://hooks.zapier.com/hooks/catch/123456/abcdef/",
                "events": ["conversation.finished"],
                "has_secret": False,
                "personas_count": 3,
            }
        }
