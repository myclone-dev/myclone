"""
Workflow Template API Routes - Endpoints for template library management

Provides REST API for:
- Listing available templates (filtered by user tier)
- Enabling templates for personas (copy-on-enable pattern)
- Customizing template-based workflows
- Checking for template updates and syncing

Created: 2026-01-25
"""

import logging
from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.template_models import (
    CustomizeWorkflowRequest,
    EnableTemplateRequest,
    SyncTemplateRequest,
    TemplateListResponse,
    TemplateResponse,
    TemplateSyncStatus,
)
from app.api.models.workflow_models import WorkflowResponse
from app.auth.jwt_auth import get_current_user, get_user_or_service
from shared.database.models.database import async_session_maker
from shared.database.models.user import User
from shared.database.repositories.persona_repository import PersonaRepository
from shared.database.repositories.workflow_repository import WorkflowRepository
from shared.database.repositories.workflow_template_repository import WorkflowTemplateRepository
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.services.tier_service import TierService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workflow-templates", tags=["Workflow Templates"])


# ===== Dependency Injection =====


async def get_db():
    """
    Database session dependency for FastAPI routes.

    Yields:
        AsyncSession: Database session for async operations
    """
    async with async_session_maker() as session:
        yield session


async def get_user_tier_id(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> int:
    """
    Get the current user's subscription tier ID.

    Args:
        current_user: Authenticated user (from JWT)
        session: Database session

    Returns:
        User's subscription tier_id (FK to tier_plans.id)
    """
    try:
        tier_service = TierService(session)
        tier_limits = await tier_service.get_user_tier_limits(current_user.id)
        return tier_limits.get("tier_id", 0)  # Default to free (id=0)

    except Exception as e:
        logger.error(f"Error getting user tier for {current_user.id}: {e}")
        return 0  # Default to free tier on error


# ===== Helper Functions =====


def can_access_templates(tier_id: int) -> bool:
    """
    Check if a user's tier can access templates.

    Templates are available for standard tiers (free, pro, business, enterprise).

    Args:
        tier_id: User's tier_id from tier_plans

    Returns:
        True if user can access templates, False otherwise
    """
    return tier_id in [0, 1, 2, 3]


def get_accessible_tier_ids(user_tier_id: int) -> list[int]:
    """
    Get list of tier IDs the user can access based on hierarchy.

    Tier hierarchy:
    - 0: free (lowest)
    - 1: pro
    - 2: business
    - 3: enterprise (HIGHEST - can access everything)

    Args:
        user_tier_id: User's tier_id

    Returns:
        List of tier IDs user can access (user's tier and below)
    """
    # Standard hierarchy: user can access their tier and all tiers below
    # enterprise (3) can access all: [0, 1, 2, 3]
    # business (2) can access: [0, 1, 2]
    # pro (1) can access: [0, 1]
    # free (0) can access: [0]
    return list(range(user_tier_id + 1))


# ===== Template Library Endpoints =====


@router.get("", response_model=TemplateListResponse)
async def list_templates(
    category: Optional[str] = Query(
        None, description="Filter by template category (e.g., 'cpa', 'tax')"
    ),
    include_stats: bool = Query(False, description="Include usage statistics for each template"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Maximum number of templates"),
    offset: int = Query(0, ge=0, description="Number of templates to skip"),
    user_tier_id: int = Depends(get_user_tier_id),
    session: AsyncSession = Depends(get_db),
):
    """
    List available workflow templates for the authenticated user.

    Templates are filtered by:
    - User's subscription tier (free=0, pro=1, business=2, enterprise=3)
    - Active status (only active templates shown)
    - Optional category filter
    - Only standard tier users can access templates

    Args:
        category: Filter by template category (optional)
        include_stats: Include usage statistics (default: False)
        limit: Maximum number of templates to return
        offset: Number of templates to skip
        user_tier_id: User's subscription tier ID (auto-injected)
        session: Database session

    Returns:
        List of templates accessible to user and total count

    Raises:
        HTTPException: If operation fails or user has no template access
    """
    try:
        # Check if user can access templates
        if not can_access_templates(user_tier_id):
            raise HTTPException(
                status_code=403,
                detail="Templates are not available for your subscription tier. Please upgrade to a standard plan.",
            )

        template_repo = WorkflowTemplateRepository(session)

        # Get list of tier IDs user can access
        accessible_tier_ids = get_accessible_tier_ids(user_tier_id)

        # Get templates accessible to user's tier
        templates = await template_repo.get_templates_by_tier_ids(
            tier_ids=accessible_tier_ids,
            category=category,
            active_only=True,
        )

        # Apply pagination
        total = len(templates)
        if limit:
            templates = templates[offset : offset + limit]
        else:
            templates = templates[offset:]

        # Build response with optional statistics
        template_responses = []
        for template in templates:
            template_dict = TemplateResponse.model_validate(template).model_dump()

            # Fetch and add statistics if requested
            if include_stats:
                usage_count = await template_repo.get_template_usage_count(template.id)
                customization_rate = await template_repo.get_customization_rate(template.id)
                template_dict.update(
                    {
                        "usage_count": usage_count,
                        "customization_rate": customization_rate,
                    }
                )

            template_responses.append(TemplateResponse(**template_dict))

        logger.info(
            f"Listed {len(template_responses)} templates for tier_id={user_tier_id} (category={category})"
        )
        return TemplateListResponse(
            templates=template_responses,
            total=total,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing templates for tier_id={user_tier_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"user_tier_id": user_tier_id, "category": category},
            tags={
                "component": "template",
                "operation": "list_templates",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {str(e)}")


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    include_stats: bool = Query(False, description="Include usage statistics"),
    user_tier_id: int = Depends(get_user_tier_id),
    session: AsyncSession = Depends(get_db),
):
    """
    Get a specific template by ID.

    Verifies user has access based on their subscription tier.

    Args:
        template_id: Template UUID
        include_stats: Include usage statistics (default: False)
        user_tier_id: User's subscription tier ID (auto-injected)
        session: Database session

    Returns:
        Template details

    Raises:
        HTTPException: If template not found or user lacks access
    """
    try:
        # Check if user can access templates
        if not can_access_templates(user_tier_id):
            raise HTTPException(
                status_code=403,
                detail="Templates are not available for your subscription tier.",
            )

        template_repo = WorkflowTemplateRepository(session)
        template = await template_repo.get_template_by_id(template_id)

        if not template:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

        # Check if user's tier can access this template
        # User must have tier_id >= template's minimum_plan_tier_id
        accessible_tier_ids = get_accessible_tier_ids(user_tier_id)

        if template.minimum_plan_tier_id not in accessible_tier_ids:
            raise HTTPException(
                status_code=403,
                detail=f"This template requires a higher subscription tier (tier_id={template.minimum_plan_tier_id}). Your tier: {user_tier_id}",
            )

        # Build response with optional statistics
        template_dict = TemplateResponse.model_validate(template).model_dump()
        if include_stats:
            usage_count = await template_repo.get_template_usage_count(template.id)
            customization_rate = await template_repo.get_customization_rate(template.id)
            template_dict.update(
                {
                    "usage_count": usage_count,
                    "customization_rate": customization_rate,
                }
            )

        return TemplateResponse(**template_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template {template_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"template_id": str(template_id)},
            tags={
                "component": "template",
                "operation": "get_template",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to get template: {str(e)}")


# ===== Template Enablement Endpoints =====


@router.post("/enable", response_model=WorkflowResponse, status_code=201)
async def enable_template(
    enable_request: EnableTemplateRequest,
    persona_id: UUID = Query(..., description="Persona ID to enable template for"),
    auth: Union[User, str] = Depends(get_user_or_service),
    session: AsyncSession = Depends(get_db),
):
    """
    Enable a template for a persona (copy-on-enable pattern).

    Creates a new PersonaWorkflow by copying the template's configuration.
    User can customize the workflow after creation.

    **Authentication:**
    - JWT (user): Must own the persona, tier restrictions apply
    - API Key (admin/service): Can enable for any persona, no tier restrictions

    Args:
        enable_request: Enable template request (template_id, auto_publish)
        persona_id: Persona UUID to enable template for
        auth: User object (JWT) or "service" string (API key)
        session: Database session

    Returns:
        Created workflow with template reference

    Raises:
        HTTPException: If template not found, user lacks access, or persona doesn't belong to user
    """
    try:
        is_service_auth = auth == "service"

        # Verify persona exists
        persona_repo = PersonaRepository(session)
        persona = await persona_repo.get_by_id(persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

        # For user auth: verify ownership and tier access
        user_tier_id = 0  # Default for service auth (not used)
        if not is_service_auth:
            current_user = auth  # auth is User object

            # Get user tier
            tier_service = TierService(session)
            tier_limits = await tier_service.get_user_tier_limits(current_user.id)
            user_tier_id = tier_limits.get("tier_id", 0)

            # Check if user can access templates
            if not can_access_templates(user_tier_id):
                raise HTTPException(
                    status_code=403,
                    detail="Templates are not available for your subscription tier.",
                )

            # Verify persona belongs to current user
            if persona.user_id != current_user.id:
                raise HTTPException(
                    status_code=403, detail="You don't have permission to modify this persona"
                )

        # Get template
        template_repo = WorkflowTemplateRepository(session)
        template = await template_repo.get_template_by_id(enable_request.template_id)
        if not template:
            raise HTTPException(
                status_code=404, detail=f"Template {enable_request.template_id} not found"
            )

        # Check tier access (only for user auth, admins/service can access any template)
        if not is_service_auth:
            accessible_tier_ids = get_accessible_tier_ids(user_tier_id)
            if template.minimum_plan_tier_id not in accessible_tier_ids:
                raise HTTPException(
                    status_code=403,
                    detail=f"This template requires a higher subscription tier (tier_id={template.minimum_plan_tier_id}). Your tier: {user_tier_id}",
                )

        # Create workflow from template (copy-on-enable)
        workflow_repo = WorkflowRepository(session)
        workflow = await workflow_repo.create_workflow(
            persona_id=persona_id,
            workflow_type=template.workflow_type,
            title=template.template_name,
            description=template.description,
            opening_message=None,  # Conversational workflows don't use opening_message
            workflow_objective=template.workflow_objective,  # COPY suggested objective from template
            workflow_config=template.workflow_config,  # COPY template config
            result_config=None,  # Not used for conversational workflows
            output_template=template.output_template,  # COPY output template
            trigger_config=None,  # User can configure later
            extra_metadata=None,
            template_id=template.id,  # Link to template
            template_version=template.version,  # Snapshot version
            is_template_customized=False,  # Not customized yet
        )

        # Auto-publish if requested
        if enable_request.auto_publish:
            workflow = await workflow_repo.publish_workflow(workflow.id)

        logger.info(
            f"Enabled template {template.template_key} for persona {persona_id} (workflow_id={workflow.id})"
        )
        return WorkflowResponse.model_validate(workflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error enabling template {enable_request.template_id} for persona {persona_id}: {e}"
        )
        capture_exception_with_context(
            e,
            extra={"template_id": str(enable_request.template_id), "persona_id": str(persona_id)},
            tags={
                "component": "template",
                "operation": "enable_template",
                "severity": "high",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to enable template: {str(e)}")


# ===== Workflow Customization Endpoints =====


@router.put("/workflows/{workflow_id}/customize", response_model=WorkflowResponse)
async def customize_workflow(
    workflow_id: UUID,
    customize_request: CustomizeWorkflowRequest,
    auth: Union[User, str] = Depends(get_user_or_service),
    session: AsyncSession = Depends(get_db),
):
    """
    Customize a template-based workflow.

    Marks the workflow as customized, disabling automatic syncing with template updates.

    **Authentication:**
    - JWT (user): Must own the workflow's persona
    - API Key (admin/service): Can customize any workflow

    Args:
        workflow_id: Workflow UUID
        customize_request: Customization updates
        auth: User object (JWT) or "service" string (API key)
        session: Database session

    Returns:
        Updated workflow

    Raises:
        HTTPException: If workflow not found or user lacks access
    """
    try:
        is_service_auth = auth == "service"

        workflow_repo = WorkflowRepository(session)
        workflow = await workflow_repo.get_workflow_by_id(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        # For user auth: verify ownership
        if not is_service_auth:
            current_user = auth  # auth is User object
            persona_repo = PersonaRepository(session)
            persona = await persona_repo.get_by_id(workflow.persona_id)
            if not persona or persona.user_id != current_user.id:
                raise HTTPException(
                    status_code=403, detail="You don't have permission to modify this workflow"
                )

        # Prepare updates (exclude None values)
        updates = customize_request.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Mark as customized
        updates["is_template_customized"] = True

        # Update workflow
        updated_workflow = await workflow_repo.update_workflow(workflow_id, **updates)
        if not updated_workflow:
            raise HTTPException(status_code=500, detail="Failed to update workflow")

        logger.info(f"Customized template-based workflow {workflow_id}")
        return WorkflowResponse.model_validate(updated_workflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error customizing workflow {workflow_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"workflow_id": str(workflow_id)},
            tags={
                "component": "template",
                "operation": "customize_workflow",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to customize workflow: {str(e)}")


# ===== Template Sync Endpoints =====


@router.get("/workflows/{workflow_id}/sync-status", response_model=TemplateSyncStatus)
async def get_sync_status(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Check if a workflow can be synced with its template's latest version.

    Args:
        workflow_id: Workflow UUID
        current_user: Authenticated user (from JWT)
        session: Database session

    Returns:
        Sync status information

    Raises:
        HTTPException: If workflow not found, not template-based, or user lacks access
    """
    try:
        workflow_repo = WorkflowRepository(session)
        workflow = await workflow_repo.get_workflow_by_id(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        # Verify workflow belongs to user's persona
        persona_repo = PersonaRepository(session)
        persona = await persona_repo.get_by_id(workflow.persona_id)
        if not persona or persona.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You don't have permission to access this workflow"
            )

        # Check if workflow is template-based
        if not workflow.template_id:
            raise HTTPException(status_code=400, detail="This workflow is not based on a template")

        # Get template
        template_repo = WorkflowTemplateRepository(session)
        template = await template_repo.get_template_by_id(workflow.template_id)
        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"Template {workflow.template_id} not found (may have been deleted)",
            )

        # Check sync status
        has_updates = template.version > (workflow.template_version or 0)
        can_sync = has_updates and not workflow.is_template_customized

        return TemplateSyncStatus(
            template_id=template.id,
            workflow_template_version=template.version,
            workflow_synced_version=workflow.template_version or 0,
            is_customized=workflow.is_template_customized,
            has_updates=has_updates,
            can_sync=can_sync,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync status for workflow {workflow_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"workflow_id": str(workflow_id)},
            tags={
                "component": "template",
                "operation": "get_sync_status",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")


@router.post("/workflows/{workflow_id}/sync", response_model=WorkflowResponse)
async def sync_workflow(
    workflow_id: UUID,
    sync_request: SyncTemplateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    Sync a workflow with its template's latest version.

    Only works if workflow is not customized, unless force=true.

    Args:
        workflow_id: Workflow UUID
        sync_request: Sync options (force)
        current_user: Authenticated user (from JWT)
        session: Database session

    Returns:
        Updated workflow

    Raises:
        HTTPException: If workflow not found, customized, or user lacks access
    """
    try:
        workflow_repo = WorkflowRepository(session)
        workflow = await workflow_repo.get_workflow_by_id(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        # Verify workflow belongs to user's persona
        persona_repo = PersonaRepository(session)
        persona = await persona_repo.get_by_id(workflow.persona_id)
        if not persona or persona.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You don't have permission to modify this workflow"
            )

        # Check if workflow is template-based
        if not workflow.template_id:
            raise HTTPException(status_code=400, detail="This workflow is not based on a template")

        # Get template
        template_repo = WorkflowTemplateRepository(session)
        template = await template_repo.get_template_by_id(workflow.template_id)
        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"Template {workflow.template_id} not found (may have been deleted)",
            )

        # Check if workflow is customized
        if workflow.is_template_customized and not sync_request.force:
            raise HTTPException(
                status_code=400,
                detail="This workflow has been customized. Use force=true to overwrite customizations.",
            )

        # Check if template has updates
        if template.version <= (workflow.template_version or 0):
            raise HTTPException(
                status_code=400, detail="Template has no updates (workflow is already up to date)"
            )

        # Sync workflow with template
        updated_workflow = await workflow_repo.update_workflow(
            workflow_id,
            workflow_config=template.workflow_config,  # COPY latest config
            output_template=template.output_template,  # COPY latest output template
            template_version=template.version,  # Update version snapshot
            is_template_customized=False,  # Reset customization flag
        )

        if not updated_workflow:
            raise HTTPException(status_code=500, detail="Failed to sync workflow")

        logger.info(
            f"Synced workflow {workflow_id} with template {template.template_key} v{template.version}"
        )
        return WorkflowResponse.model_validate(updated_workflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing workflow {workflow_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"workflow_id": str(workflow_id), "force": sync_request.force},
            tags={
                "component": "template",
                "operation": "sync_workflow",
                "severity": "high",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to sync workflow: {str(e)}")
