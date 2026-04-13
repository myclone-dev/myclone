"""
Pydantic models for the workflow template system API.

These models define the request/response schemas for template endpoints.

Created: 2026-01-25
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ===== API Response Models =====


class TemplateResponse(BaseModel):
    """
    Response model for a workflow template.
    """

    id: UUID
    template_key: str
    template_name: str
    template_category: str
    minimum_plan_tier_id: int  # FK to tier_plans.id
    workflow_type: str
    workflow_config: Dict[str, Any]  # JSONB from database
    output_template: Dict[str, Any]  # JSONB from database
    description: Optional[str] = None
    workflow_objective: Optional[str] = None
    preview_image_url: Optional[str] = None
    tags: Optional[List[str]] = None
    version: int
    is_active: bool
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None

    # Optional statistics (populated when include_stats=true)
    usage_count: Optional[int] = Field(None, description="Number of workflows using this template")
    customization_rate: Optional[float] = Field(
        None, description="Percentage of workflows that customized the template"
    )

    model_config = ConfigDict(from_attributes=True)


class TemplateListResponse(BaseModel):
    """
    Response model for listing templates.
    """

    templates: List[TemplateResponse]
    total: int


class TemplateSyncStatus(BaseModel):
    """
    Response model for template sync status check.
    """

    template_id: UUID
    workflow_template_version: int  # Current template version
    workflow_synced_version: int  # Version workflow was created from
    is_customized: bool  # Whether workflow has been customized
    has_updates: bool  # Whether template has newer version
    can_sync: bool  # Whether workflow can be synced (not customized and has updates)


# ===== API Request Models =====


class EnableTemplateRequest(BaseModel):
    """
    Request body for enabling a template for a persona.
    """

    template_id: UUID = Field(..., description="Template UUID to enable")
    auto_publish: bool = Field(
        default=False, description="Whether to publish the workflow immediately after creation"
    )


class CustomizeWorkflowRequest(BaseModel):
    """
    Request body for customizing a template-based workflow.

    Marking a workflow as customized disables automatic syncing with template updates.
    """

    workflow_config: Optional[Dict[str, Any]] = Field(
        None, description="Updated workflow configuration"
    )
    output_template: Optional[Dict[str, Any]] = Field(
        None, description="Updated output template configuration"
    )
    title: Optional[str] = Field(None, description="Updated workflow title")
    description: Optional[str] = Field(None, description="Updated workflow description")
    opening_message: Optional[str] = Field(None, description="Updated opening message")
    workflow_objective: Optional[str] = Field(None, description="Updated workflow objective")


class SyncTemplateRequest(BaseModel):
    """
    Request body for syncing a workflow with its template's latest version.

    Only works if workflow is not customized.
    """

    force: bool = Field(
        default=False,
        description="Force sync even if workflow is customized (overwrites customizations)",
    )
