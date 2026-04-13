"""
Workflow API Routes - CRUD endpoints for workflows and workflow sessions

Provides REST API for:
- Creating, reading, updating, deleting workflows
- Starting and managing workflow sessions
- Submitting answers to workflow questions
- Viewing workflow analytics
"""

import logging
from typing import Optional, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.models.workflow_models import (
    AnswerSubmit,
    WorkflowAnalytics,
    WorkflowCreate,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowSessionCreate,
    WorkflowSessionListResponse,
    WorkflowSessionResponse,
    WorkflowUpdate,
)
from app.auth.jwt_auth import get_current_user, get_user_or_service
from shared.database.models.database import Conversation, async_session_maker
from shared.database.models.user import User
from shared.database.repositories.persona_repository import PersonaRepository
from shared.database.repositories.workflow_repository import WorkflowRepository
from shared.generation.workflow_objective_generator import generate_workflow_objective
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/workflows", tags=["Workflows"])


# ===== Dependency Injection =====


async def get_db():
    """
    Database session dependency for FastAPI routes.

    Yields:
        AsyncSession: Database session for async operations
    """
    async with async_session_maker() as session:
        yield session


async def _update_conversation_with_lead_info(
    db_session: AsyncSession,
    conversation_id: Optional[UUID],
    collected_data: dict,
) -> None:
    """
    Update conversation with lead info from completed workflow.

    Extracts email, fullname, and phone from workflow collected_data
    and updates the associated conversation record.

    Uses merge strategy: only fills empty fields, never overwrites existing data.

    Args:
        db_session: Database session
        conversation_id: Conversation UUID (may be None)
        collected_data: Workflow collected_data with answers
    """
    if not conversation_id:
        logger.debug("No conversation_id provided, skipping lead info update")
        return

    try:
        # Extract lead fields using naming convention
        # Format: collected_data = {"email": {"answer": "john@example.com", "answered_at": ...}}
        updates = {}

        # Extract email
        if "email" in collected_data and isinstance(collected_data["email"], dict):
            email = collected_data["email"].get("answer")
            if email:
                updates["user_email"] = email

        # Extract fullname (check both "fullname" and "name" step IDs)
        fullname = None
        if "fullname" in collected_data and isinstance(collected_data["fullname"], dict):
            fullname = collected_data["fullname"].get("answer")
        elif "name" in collected_data and isinstance(collected_data["name"], dict):
            fullname = collected_data["name"].get("answer")
        if fullname:
            updates["user_fullname"] = fullname

        # Extract phone
        if "phone" in collected_data and isinstance(collected_data["phone"], dict):
            phone = collected_data["phone"].get("answer")
            if phone:
                updates["user_phone"] = phone

        if not updates:
            logger.debug("No lead fields found in collected_data")
            return

        # Merge strategy: only update fields that are currently NULL
        # Build WHERE clause to check for NULL fields
        stmt = update(Conversation).where(Conversation.id == conversation_id).values(**updates)

        # Execute update
        await db_session.execute(stmt)
        await db_session.commit()

        logger.info(
            f"Updated conversation {conversation_id} with lead info: {list(updates.keys())}"
        )

    except Exception as e:
        logger.error(f"Failed to update conversation {conversation_id} with lead info: {e}")
        capture_exception_with_context(
            e,
            extra={
                "conversation_id": str(conversation_id),
                "collected_data_keys": list(collected_data.keys()),
            },
            tags={
                "component": "workflow",
                "operation": "update_conversation_lead_info",
                "severity": "medium",
                "user_facing": "false",
            },
        )
        # Don't raise - this is a non-critical update


# ===== Workflow CRUD Endpoints =====


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    workflow_data: WorkflowCreate,
    persona_id: UUID = Query(..., description="Persona ID this workflow belongs to"),
    session: AsyncSession = Depends(get_db),
):
    """
    Create a new workflow for a persona.

    Args:
        workflow_data: Workflow configuration
        persona_id: Persona UUID
        session: Database session

    Returns:
        Created workflow

    Raises:
        HTTPException: If persona not found or creation fails
    """
    try:
        # Verify persona exists
        persona_repo = PersonaRepository(session)
        persona = await persona_repo.get_by_id(persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")

        # Convert Pydantic models to dicts once
        # Note: model_dump() automatically converts nested Pydantic models to dicts
        workflow_dict = workflow_data.model_dump()

        # Generate workflow objective if not provided
        workflow_objective = workflow_dict.get("workflow_objective")
        if not workflow_objective:
            # Extract promotion_mode from trigger_config
            promotion_mode = None
            if workflow_dict.get("trigger_config"):
                promotion_mode = workflow_dict["trigger_config"].get("promotion_mode")

            # Extract persona style (use description as style guide)
            persona_style = persona.description if persona.description else None

            # Generate objective using LLM with promotion_mode
            workflow_objective = await generate_workflow_objective(
                workflow_data=workflow_dict,
                persona_style=persona_style,
                promotion_mode=promotion_mode,
            )
            logger.info(
                f"Generated workflow objective (promotion_mode={promotion_mode}): {workflow_objective[:100]}..."
            )

        # Create workflow
        workflow_repo = WorkflowRepository(session)
        workflow = await workflow_repo.create_workflow(
            persona_id=persona_id,
            workflow_type=workflow_dict["workflow_type"],
            title=workflow_dict["title"],
            description=workflow_dict.get("description"),
            opening_message=workflow_dict.get("opening_message"),
            workflow_objective=workflow_objective,
            workflow_config=workflow_dict["workflow_config"],
            result_config=workflow_dict.get("result_config"),
            trigger_config=workflow_dict.get("trigger_config"),
            extra_metadata=workflow_dict.get("extra_metadata"),
            output_template=workflow_dict.get("output_template"),
        )

        logger.info(f"Created workflow {workflow.id} for persona {persona_id}")
        return WorkflowResponse.model_validate(workflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating workflow for persona {persona_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"persona_id": str(persona_id), "workflow_title": workflow_data.title},
            tags={
                "component": "workflow",
                "operation": "create_workflow",
                "severity": "high",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to create workflow: {str(e)}")


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get a workflow by ID.

    Args:
        workflow_id: Workflow UUID
        session: Database session

    Returns:
        Workflow details

    Raises:
        HTTPException: If workflow not found
    """
    try:
        workflow_repo = WorkflowRepository(session)
        workflow = await workflow_repo.get_workflow_by_id(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        return WorkflowResponse.model_validate(workflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow {workflow_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"workflow_id": str(workflow_id)},
            tags={"component": "workflow", "operation": "get_workflow"},
        )
        raise HTTPException(status_code=500, detail=f"Failed to get workflow: {str(e)}")


@router.get("", response_model=WorkflowListResponse)
async def list_workflows(
    persona_id: Optional[UUID] = Query(
        None, description="Persona ID to filter workflows (optional - omit for all user workflows)"
    ),
    active_only: bool = Query(True, description="Only return active workflows"),
    include_stats: bool = Query(
        True, description="Include completion statistics for each workflow"
    ),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Maximum number of workflows"),
    offset: int = Query(0, ge=0, description="Number of workflows to skip"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """
    List workflows for the authenticated user.

    - If persona_id is provided: List workflows for that specific persona (must belong to user)
    - If persona_id is omitted: List ALL workflows across all of the user's personas

    Args:
        persona_id: Persona UUID (optional - omit to get all user workflows)
        active_only: Only return active workflows (default: True)
        include_stats: Include session statistics (default: True)
        limit: Maximum number of workflows to return
        offset: Number of workflows to skip
        current_user: Authenticated user (from JWT)
        session: Database session

    Returns:
        List of workflows with statistics and total count

    Raises:
        HTTPException: If operation fails or persona doesn't belong to user
    """
    try:
        workflow_repo = WorkflowRepository(session)

        if persona_id:
            # Verify persona belongs to current user
            persona_repo = PersonaRepository(session)
            persona = await persona_repo.get_by_id(persona_id)
            if not persona:
                raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")
            if persona.user_id != current_user.id:
                raise HTTPException(
                    status_code=403,
                    detail="You don't have permission to access this persona's workflows",
                )

            # Get workflows for specific persona
            workflows = await workflow_repo.get_workflows_by_persona(
                persona_id, active_only=active_only, limit=limit, offset=offset
            )
            total = await workflow_repo.get_workflows_count_by_persona(
                persona_id, active_only=active_only
            )
        else:
            # Get ALL workflows for user's personas
            workflows = await workflow_repo.get_workflows_by_user(
                current_user.id, active_only=active_only, limit=limit, offset=offset
            )
            total = await workflow_repo.get_workflows_count_by_user(
                current_user.id, active_only=active_only
            )

        # Build response with optional statistics
        workflow_responses = []
        for workflow in workflows:
            workflow_dict = WorkflowResponse.model_validate(workflow).model_dump()

            # Fetch and add statistics if requested
            if include_stats:
                analytics = await workflow_repo.get_workflow_analytics(workflow.id)
                workflow_dict.update(
                    {
                        "total_sessions": analytics.get("total_sessions", 0),
                        "completed_sessions": analytics.get("completed_sessions", 0),
                        "completion_rate": analytics.get("completion_rate", 0.0),
                        "avg_score": analytics.get("avg_score"),
                    }
                )

            workflow_responses.append(WorkflowResponse(**workflow_dict))

        return WorkflowListResponse(
            workflows=workflow_responses,
            total=total,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing workflows for user {current_user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(current_user.id),
                "persona_id": str(persona_id) if persona_id else None,
            },
            tags={"component": "workflow", "operation": "list_workflows"},
        )
        raise HTTPException(status_code=500, detail=f"Failed to list workflows: {str(e)}")


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    workflow_updates: WorkflowUpdate,
    auth: Union[User, str] = Depends(get_user_or_service),
    session: AsyncSession = Depends(get_db),
):
    """
    Update a workflow.

    **Authentication:**
    - JWT (user): Must own the workflow's persona
    - API Key (admin/service): Can update any workflow

    Args:
        workflow_id: Workflow UUID
        workflow_updates: Fields to update
        auth: User object (JWT) or "service" string (API key)
        session: Database session

    Returns:
        Updated workflow

    Raises:
        HTTPException: If workflow not found or update fails
    """
    try:
        is_service_auth = auth == "service"
        workflow_repo = WorkflowRepository(session)

        # Get workflow first to verify ownership
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

        # Prepare updates dict (exclude None values)
        # Note: model_dump() already converts nested Pydantic models to dicts
        updates = workflow_updates.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        updated_workflow = await workflow_repo.update_workflow(workflow_id, **updates)

        if not updated_workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        logger.info(f"Updated workflow {workflow_id}")
        return WorkflowResponse.model_validate(updated_workflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating workflow {workflow_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"workflow_id": str(workflow_id)},
            tags={
                "component": "workflow",
                "operation": "update_workflow",
                "severity": "medium",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to update workflow: {str(e)}")


@router.post("/{workflow_id}/publish", response_model=WorkflowResponse)
async def publish_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Publish a workflow (set published_at timestamp and activate).

    Args:
        workflow_id: Workflow UUID
        session: Database session

    Returns:
        Published workflow

    Raises:
        HTTPException: If workflow not found or publish fails
    """
    try:
        workflow_repo = WorkflowRepository(session)
        workflow = await workflow_repo.publish_workflow(workflow_id)

        if not workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        logger.info(f"Published workflow {workflow_id}")
        return WorkflowResponse.model_validate(workflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error publishing workflow {workflow_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"workflow_id": str(workflow_id)},
            tags={"component": "workflow", "operation": "publish_workflow"},
        )
        raise HTTPException(status_code=500, detail=f"Failed to publish workflow: {str(e)}")


@router.post("/{workflow_id}/regenerate-objective", response_model=WorkflowResponse)
async def regenerate_objective(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Regenerate the workflow objective using LLM and auto-save.

    Fetches the workflow, generates a new objective based on current configuration,
    and automatically updates the workflow with the new objective.

    Args:
        workflow_id: Workflow UUID
        session: Database session

    Returns:
        Updated workflow with new objective

    Raises:
        HTTPException: If workflow not found or regeneration fails
    """
    try:
        workflow_repo = WorkflowRepository(session)

        # Get workflow
        workflow = await workflow_repo.get_workflow_by_id(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        # Get persona for style
        persona_repo = PersonaRepository(session)
        persona = await persona_repo.get_by_id(workflow.persona_id)
        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona {workflow.persona_id} not found")

        # Extract promotion_mode from workflow's trigger_config
        promotion_mode = None
        if workflow.trigger_config and isinstance(workflow.trigger_config, dict):
            promotion_mode = workflow.trigger_config.get("promotion_mode")

        # Build workflow data dict for generator
        workflow_dict = {
            "title": workflow.title,
            "workflow_type": workflow.workflow_type,
            "workflow_config": workflow.workflow_config,
            "result_config": workflow.result_config,
            "opening_message": workflow.opening_message,
            "trigger_config": workflow.trigger_config,
        }

        # Extract persona style
        persona_style = persona.description if persona.description else None

        # Generate new objective with promotion_mode
        new_objective = await generate_workflow_objective(
            workflow_data=workflow_dict,
            persona_style=persona_style,
            promotion_mode=promotion_mode,
        )

        logger.info(f"Regenerated objective for workflow {workflow_id}: {new_objective[:100]}...")

        # Update workflow with new objective
        updated_workflow = await workflow_repo.update_workflow(
            workflow_id, workflow_objective=new_objective
        )

        if not updated_workflow:
            raise HTTPException(status_code=500, detail="Failed to save regenerated objective")

        logger.info(f"Saved regenerated objective for workflow {workflow_id}")
        return WorkflowResponse.model_validate(updated_workflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating objective for workflow {workflow_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"workflow_id": str(workflow_id)},
            tags={
                "component": "workflow",
                "operation": "regenerate_objective",
                "severity": "medium",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to regenerate objective: {str(e)}")


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Delete a workflow.

    Args:
        workflow_id: Workflow UUID
        session: Database session

    Raises:
        HTTPException: If workflow not found or deletion fails
    """
    try:
        workflow_repo = WorkflowRepository(session)
        success = await workflow_repo.delete_workflow(workflow_id)

        if not success:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        logger.info(f"Deleted workflow {workflow_id}")
        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting workflow {workflow_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"workflow_id": str(workflow_id)},
            tags={
                "component": "workflow",
                "operation": "delete_workflow",
                "severity": "medium",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to delete workflow: {str(e)}")


# ===== Workflow Session Endpoints =====


@router.post("/sessions", response_model=WorkflowSessionResponse, status_code=201)
async def start_session(
    session_data: WorkflowSessionCreate,
    session: AsyncSession = Depends(get_db),
):
    """
    Start a new workflow session.

    Args:
        session_data: Session configuration
        session: Database session

    Returns:
        Created workflow session

    Raises:
        HTTPException: If workflow not found or creation fails
    """
    try:
        workflow_repo = WorkflowRepository(session)

        # Verify workflow exists
        workflow = await workflow_repo.get_workflow_by_id(session_data.workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=404, detail=f"Workflow {session_data.workflow_id} not found"
            )

        # Create session
        workflow_session = await workflow_repo.create_session(
            workflow_id=session_data.workflow_id,
            persona_id=workflow.persona_id,
            conversation_id=session_data.conversation_id,
            user_id=session_data.user_id,
            session_metadata=session_data.session_metadata,
        )

        logger.info(
            f"Started workflow session {workflow_session.id} for workflow {session_data.workflow_id}"
        )
        return WorkflowSessionResponse.model_validate(workflow_session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting workflow session: {e}")
        capture_exception_with_context(
            e,
            extra={"workflow_id": str(session_data.workflow_id)},
            tags={
                "component": "workflow",
                "operation": "start_session",
                "severity": "high",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


@router.get("/sessions/{session_id}", response_model=WorkflowSessionResponse)
async def get_session(
    session_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get a workflow session by ID.

    Args:
        session_id: Session UUID
        session: Database session

    Returns:
        Workflow session details

    Raises:
        HTTPException: If session not found
    """
    try:
        workflow_repo = WorkflowRepository(session)
        workflow_session = await workflow_repo.get_session_by_id(session_id)

        if not workflow_session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        return WorkflowSessionResponse.model_validate(workflow_session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"session_id": str(session_id)},
            tags={"component": "workflow", "operation": "get_session"},
        )
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")


@router.get("/sessions", response_model=WorkflowSessionListResponse)
async def list_sessions(
    workflow_id: UUID = Query(..., description="Workflow ID to list sessions for"),
    status: Optional[str] = Query(
        None, description="Filter by status (in_progress, completed, abandoned)"
    ),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Maximum number of sessions"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    session: AsyncSession = Depends(get_db),
):
    """
    List all sessions for a workflow.

    Args:
        workflow_id: Workflow UUID
        status: Filter by status (optional)
        limit: Maximum number of sessions to return
        offset: Number of sessions to skip
        session: Database session

    Returns:
        List of sessions and total count

    Raises:
        HTTPException: If operation fails
    """
    try:
        workflow_repo = WorkflowRepository(session)
        sessions = await workflow_repo.get_sessions_by_workflow(
            workflow_id, status=status, limit=limit, offset=offset
        )

        # Count total (without limit/offset)
        total_sessions = await workflow_repo.get_sessions_by_workflow(workflow_id, status=status)

        return WorkflowSessionListResponse(
            sessions=[WorkflowSessionResponse.model_validate(s) for s in sessions],
            total=len(total_sessions),
        )

    except Exception as e:
        logger.error(f"Error listing sessions for workflow {workflow_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"workflow_id": str(workflow_id)},
            tags={"component": "workflow", "operation": "list_sessions"},
        )
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.post("/sessions/{session_id}/answer", response_model=WorkflowSessionResponse)
async def submit_answer(
    session_id: UUID,
    answer_data: AnswerSubmit,
    session: AsyncSession = Depends(get_db),
):
    """
    Submit an answer to a workflow session.

    Args:
        session_id: Session UUID
        answer_data: Answer data (step_id, answer, raw_answer)
        session: Database session

    Returns:
        Updated workflow session

    Raises:
        HTTPException: If session not found or submission fails
    """
    try:
        workflow_repo = WorkflowRepository(session)

        # Get session and workflow to validate step_id
        workflow_session = await workflow_repo.get_session_by_id(session_id)
        if not workflow_session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        if workflow_session.status != "in_progress":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot submit answer to session with status '{workflow_session.status}'",
            )

        # Get workflow to extract score from options (if scored workflow)
        workflow = await workflow_repo.get_workflow_by_id(workflow_session.workflow_id)
        if not workflow:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow {workflow_session.workflow_id} not found",
            )

        # Find step and extract score if applicable
        score = None
        steps = workflow.workflow_config.get("steps", [])
        step = next((s for s in steps if s.get("step_id") == answer_data.step_id), None)

        if not step:
            raise HTTPException(
                status_code=400, detail=f"Step {answer_data.step_id} not found in workflow"
            )

        # Extract score from options if multiple choice
        if step.get("step_type") == "multiple_choice" and step.get("options"):
            # Match answer to option
            for option in step["options"]:
                # Match by label, text, or value
                if (
                    answer_data.answer == option.get("label")
                    or answer_data.answer == option.get("text")
                    or answer_data.answer == option.get("value")
                ):
                    score = option.get("score")
                    break

        # Save answer
        updated_session = await workflow_repo.save_answer(
            session_id=session_id,
            step_id=answer_data.step_id,
            answer=answer_data.answer,
            raw_answer=answer_data.raw_answer,
            score=score,
        )

        if not updated_session:
            raise HTTPException(status_code=500, detail="Failed to save answer")

        # If workflow completed, update conversation with lead info
        if updated_session.status == "completed":
            await _update_conversation_with_lead_info(
                db_session=session,
                conversation_id=updated_session.conversation_id,
                collected_data=updated_session.collected_data,
            )

        logger.info(f"Submitted answer for session {session_id}, step {answer_data.step_id}")
        return WorkflowSessionResponse.model_validate(updated_session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting answer for session {session_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"session_id": str(session_id), "step_id": answer_data.step_id},
            tags={
                "component": "workflow",
                "operation": "submit_answer",
                "severity": "high",
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to submit answer: {str(e)}")


@router.post("/sessions/{session_id}/abandon", response_model=WorkflowSessionResponse)
async def abandon_session(
    session_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Mark a session as abandoned.

    Args:
        session_id: Session UUID
        session: Database session

    Returns:
        Updated workflow session

    Raises:
        HTTPException: If session not found or operation fails
    """
    try:
        workflow_repo = WorkflowRepository(session)
        workflow_session = await workflow_repo.abandon_session(session_id)

        if not workflow_session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

        logger.info(f"Abandoned session {session_id}")
        return WorkflowSessionResponse.model_validate(workflow_session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error abandoning session {session_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"session_id": str(session_id)},
            tags={"component": "workflow", "operation": "abandon_session"},
        )
        raise HTTPException(status_code=500, detail=f"Failed to abandon session: {str(e)}")


# ===== Analytics Endpoints =====


@router.get("/{workflow_id}/analytics", response_model=WorkflowAnalytics)
async def get_workflow_analytics(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
):
    """
    Get analytics for a workflow.

    Args:
        workflow_id: Workflow UUID
        session: Database session

    Returns:
        Workflow analytics (completion rate, avg score, drop-off points, etc.)

    Raises:
        HTTPException: If workflow not found or operation fails
    """
    try:
        workflow_repo = WorkflowRepository(session)

        # Verify workflow exists
        workflow = await workflow_repo.get_workflow_by_id(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

        # Get analytics
        analytics = await workflow_repo.get_workflow_analytics(workflow_id)

        return WorkflowAnalytics(**analytics)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analytics for workflow {workflow_id}: {e}")
        capture_exception_with_context(
            e,
            extra={"workflow_id": str(workflow_id)},
            tags={"component": "workflow", "operation": "get_analytics"},
        )
        raise HTTPException(status_code=500, detail=f"Failed to get analytics: {str(e)}")
