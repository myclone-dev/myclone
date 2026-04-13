"""
Workflow Repository - Database operations for workflows and workflow sessions

Provides CRUD operations for:
- PersonaWorkflow: Workflow definitions
- WorkflowSession: Workflow execution tracking
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes

from shared.database.models.database import Conversation
from shared.database.models.workflow import PersonaWorkflow, WorkflowSession

logger = logging.getLogger(__name__)


class WorkflowRepository:
    """Repository for workflow database operations"""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session

        Args:
            session: Database session
        """
        self.session = session

    # ===== Workflow CRUD Operations =====

    async def create_workflow(
        self,
        persona_id: UUID,
        workflow_type: str,
        title: str,
        workflow_config: Dict[str, Any],
        description: Optional[str] = None,
        opening_message: Optional[str] = None,
        workflow_objective: Optional[str] = None,
        result_config: Optional[Dict[str, Any]] = None,
        trigger_config: Optional[Dict[str, Any]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
        output_template: Optional[Dict[str, Any]] = None,
        template_id: Optional[UUID] = None,
        template_version: Optional[int] = None,
        is_template_customized: bool = False,
    ) -> PersonaWorkflow:
        """
        Create a new workflow

        Args:
            persona_id: Persona this workflow belongs to
            workflow_type: 'simple', 'scored', or 'conversational'
            title: Workflow title
            workflow_config: Workflow configuration (steps, questions, options)
            description: Internal description (optional)
            opening_message: Message shown before first question (optional)
            workflow_objective: LLM-generated objective for guiding user toward workflow (optional)
            result_config: Result configuration for scored workflows (optional)
            trigger_config: Trigger settings (optional)
            extra_metadata: Additional metadata (optional)
            output_template: Output template for conversational workflows (optional)
            template_id: Template this workflow was created from (optional)
            template_version: Version of template when workflow was created (optional)
            is_template_customized: Whether workflow has been customized from template (default: False)

        Returns:
            Created PersonaWorkflow
        """
        try:
            workflow = PersonaWorkflow(
                persona_id=persona_id,
                workflow_type=workflow_type,
                title=title,
                description=description,
                opening_message=opening_message,
                workflow_objective=workflow_objective,
                workflow_config=workflow_config,
                result_config=result_config,
                trigger_config=trigger_config,
                extra_metadata=extra_metadata,
                output_template=output_template,
                template_id=template_id,
                template_version=template_version,
                is_template_customized=is_template_customized,
            )
            self.session.add(workflow)
            await self.session.commit()
            await self.session.refresh(workflow)
            logger.info(f"Created workflow {workflow.id} for persona {persona_id}")
            return workflow
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating workflow for persona {persona_id}: {e}")
            raise

    async def get_workflow_by_id(self, workflow_id: UUID) -> Optional[PersonaWorkflow]:
        """
        Get workflow by ID

        Args:
            workflow_id: Workflow UUID

        Returns:
            PersonaWorkflow if found, None otherwise
        """
        try:
            stmt = select(PersonaWorkflow).where(PersonaWorkflow.id == workflow_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting workflow {workflow_id}: {e}")
            return None

    async def get_workflows_by_persona(
        self,
        persona_id: UUID,
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[PersonaWorkflow]:
        """
        Get all workflows for a persona

        Args:
            persona_id: Persona UUID
            active_only: Only return active workflows (default: True)
            limit: Maximum number of workflows to return
            offset: Number of workflows to skip

        Returns:
            List of PersonaWorkflow
        """
        try:
            stmt = select(PersonaWorkflow).where(PersonaWorkflow.persona_id == persona_id)

            if active_only:
                stmt = stmt.where(PersonaWorkflow.is_active == True)

            stmt = stmt.order_by(PersonaWorkflow.created_at.desc())

            if limit:
                stmt = stmt.limit(limit)
            if offset:
                stmt = stmt.offset(offset)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting workflows for persona {persona_id}: {e}")
            return []

    async def get_workflows_count_by_persona(
        self, persona_id: UUID, active_only: bool = True
    ) -> int:
        """
        Count workflows for a persona

        Args:
            persona_id: Persona UUID
            active_only: Only count active workflows (default: True)

        Returns:
            Count of workflows
        """
        try:
            stmt = select(func.count(PersonaWorkflow.id)).where(
                PersonaWorkflow.persona_id == persona_id
            )

            if active_only:
                stmt = stmt.where(PersonaWorkflow.is_active == True)

            result = await self.session.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Error counting workflows for persona {persona_id}: {e}")
            return 0

    async def get_workflows_by_user(
        self,
        user_id: UUID,
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[PersonaWorkflow]:
        """
        Get all workflows for a user's personas

        Args:
            user_id: User UUID
            active_only: Only return active workflows (default: True)
            limit: Maximum number of workflows to return
            offset: Number of workflows to skip

        Returns:
            List of PersonaWorkflow
        """
        try:
            from shared.database.models.database import Persona

            # Join with Persona to filter by user_id
            stmt = (
                select(PersonaWorkflow)
                .join(Persona, PersonaWorkflow.persona_id == Persona.id)
                .where(Persona.user_id == user_id)
            )

            if active_only:
                stmt = stmt.where(PersonaWorkflow.is_active == True)

            stmt = stmt.order_by(PersonaWorkflow.created_at.desc())

            if limit:
                stmt = stmt.limit(limit)
            if offset:
                stmt = stmt.offset(offset)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting workflows for user {user_id}: {e}")
            return []

    async def get_workflows_count_by_user(self, user_id: UUID, active_only: bool = True) -> int:
        """
        Count all workflows for a user's personas

        Args:
            user_id: User UUID
            active_only: Only count active workflows (default: True)

        Returns:
            Count of workflows
        """
        try:
            from shared.database.models.database import Persona

            # Join with Persona to filter by user_id
            stmt = (
                select(func.count(PersonaWorkflow.id))
                .join(Persona, PersonaWorkflow.persona_id == Persona.id)
                .where(Persona.user_id == user_id)
            )

            if active_only:
                stmt = stmt.where(PersonaWorkflow.is_active == True)

            result = await self.session.execute(stmt)
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Error counting workflows for user {user_id}: {e}")
            return 0

    def _deep_merge(self, base: dict, updates: dict) -> dict:
        """
        Deep merge two dictionaries.

        Updates are merged into base recursively. For nested dicts,
        values are merged rather than replaced.

        Args:
            base: Base dictionary
            updates: Updates to merge in

        Returns:
            Merged dictionary
        """
        result = base.copy()
        for key, value in updates.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    async def update_workflow(
        self,
        workflow_id: UUID,
        **updates: Any,
    ) -> Optional[PersonaWorkflow]:
        """
        Update workflow fields with deep merge for JSONB fields.

        For workflow_config, output_template, and other dict fields,
        updates are deep-merged rather than replaced entirely.

        Args:
            workflow_id: Workflow UUID
            **updates: Fields to update

        Returns:
            Updated PersonaWorkflow if successful, None otherwise

        Example:
            # This will only update tone, keeping other extraction_strategy fields
            await repo.update_workflow(
                workflow_id,
                workflow_config={"extraction_strategy": {"tone": "concierge"}}
            )
        """
        try:
            workflow = await self.get_workflow_by_id(workflow_id)
            if not workflow:
                logger.warning(f"Workflow {workflow_id} not found for update")
                return None

            # Fields that should be deep-merged (JSONB columns)
            merge_fields = {"workflow_config", "output_template", "result_config", "extra_metadata"}

            for key, value in updates.items():
                if hasattr(workflow, key):
                    # Deep merge for dict fields
                    if key in merge_fields and isinstance(value, dict):
                        existing = getattr(workflow, key) or {}
                        merged = self._deep_merge(existing, value)
                        setattr(workflow, key, merged)
                    else:
                        setattr(workflow, key, value)

            workflow.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(workflow)
            logger.info(f"Updated workflow {workflow_id}")
            return workflow
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating workflow {workflow_id}: {e}")
            return None

    async def publish_workflow(self, workflow_id: UUID) -> Optional[PersonaWorkflow]:
        """
        Publish a workflow (set published_at timestamp)

        Args:
            workflow_id: Workflow UUID

        Returns:
            Updated PersonaWorkflow if successful, None otherwise
        """
        return await self.update_workflow(
            workflow_id,
            published_at=datetime.now(timezone.utc),
            is_active=True,
        )

    async def deactivate_workflow(self, workflow_id: UUID) -> Optional[PersonaWorkflow]:
        """
        Deactivate a workflow

        Args:
            workflow_id: Workflow UUID

        Returns:
            Updated PersonaWorkflow if successful, None otherwise
        """
        return await self.update_workflow(workflow_id, is_active=False)

    async def delete_workflow(self, workflow_id: UUID) -> bool:
        """
        Delete a workflow (hard delete)

        Args:
            workflow_id: Workflow UUID

        Returns:
            True if deleted, False otherwise
        """
        try:
            workflow = await self.get_workflow_by_id(workflow_id)
            if not workflow:
                logger.warning(f"Workflow {workflow_id} not found for deletion")
                return False

            await self.session.delete(workflow)
            await self.session.commit()
            logger.info(f"Deleted workflow {workflow_id}")
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting workflow {workflow_id}: {e}")
            return False

    # ===== Workflow Session Operations =====

    async def create_session(
        self,
        workflow_id: UUID,
        persona_id: UUID,
        conversation_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        session_token: Optional[str] = None,
        session_metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowSession:
        """
        Create a new workflow session

        Args:
            workflow_id: Workflow to execute
            persona_id: Persona conducting the workflow
            conversation_id: Associated conversation (optional)
            user_id: User taking the workflow (optional)
            session_token: Session token for linking to conversations (optional)
            session_metadata: Additional metadata (optional)

        Returns:
            Created WorkflowSession
        """
        try:
            # Get workflow to determine first step
            workflow = await self.get_workflow_by_id(workflow_id)
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")

            # Get first step ID from workflow_config
            first_step_id = None
            if workflow.workflow_config and "steps" in workflow.workflow_config:
                steps = workflow.workflow_config["steps"]
                if steps:
                    first_step_id = steps[0].get("step_id")

            session = WorkflowSession(
                workflow_id=workflow_id,
                persona_id=persona_id,
                conversation_id=conversation_id,
                user_id=user_id,
                session_token=session_token,
                status="in_progress",
                current_step_id=first_step_id,
                progress_percentage=0,
                collected_data={},
                session_metadata=session_metadata,
            )
            self.session.add(session)
            await self.session.commit()
            await self.session.refresh(session)
            logger.info(f"Created workflow session {session.id} for workflow {workflow_id}")
            return session
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating workflow session for workflow {workflow_id}: {e}")
            raise

    async def get_session_by_id(self, session_id: UUID) -> Optional[WorkflowSession]:
        """
        Get workflow session by ID

        Args:
            session_id: Session UUID

        Returns:
            WorkflowSession if found, None otherwise
        """
        try:
            stmt = select(WorkflowSession).where(WorkflowSession.id == session_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting workflow session {session_id}: {e}")
            return None

    async def get_sessions_by_workflow(
        self,
        workflow_id: UUID,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[WorkflowSession]:
        """
        Get all sessions for a workflow

        Args:
            workflow_id: Workflow UUID
            status: Filter by status ('in_progress', 'completed', 'abandoned')
            limit: Maximum number of sessions to return
            offset: Number of sessions to skip

        Returns:
            List of WorkflowSession
        """
        try:
            stmt = select(WorkflowSession).where(WorkflowSession.workflow_id == workflow_id)

            if status:
                stmt = stmt.where(WorkflowSession.status == status)

            stmt = stmt.order_by(WorkflowSession.started_at.desc())

            if limit:
                stmt = stmt.limit(limit)
            if offset:
                stmt = stmt.offset(offset)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting sessions for workflow {workflow_id}: {e}")
            return []

    async def get_sessions_by_conversation(self, conversation_id: UUID) -> List[WorkflowSession]:
        """
        Get all sessions for a conversation

        Args:
            conversation_id: Conversation UUID

        Returns:
            List of WorkflowSession
        """
        try:
            stmt = (
                select(WorkflowSession)
                .where(WorkflowSession.conversation_id == conversation_id)
                .order_by(WorkflowSession.started_at.desc())
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting sessions for conversation {conversation_id}: {e}")
            return []

    async def save_answer(
        self,
        session_id: UUID,
        step_id: str,
        answer: Any,
        raw_answer: Optional[str] = None,
        score: Optional[int] = None,
    ) -> Optional[WorkflowSession]:
        """
        Save an answer to a workflow session

        Args:
            session_id: Session UUID
            step_id: Step ID being answered
            answer: User's answer (type depends on question type)
            raw_answer: Original user input (optional, for natural language extraction)
            score: Score for this answer (optional, for scored workflows)

        Returns:
            Updated WorkflowSession if successful, None otherwise
        """
        try:
            session = await self.get_session_by_id(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found for saving answer")
                return None

            # Get workflow to find next step
            workflow = await self.get_workflow_by_id(session.workflow_id)
            if not workflow:
                logger.error(f"Workflow {session.workflow_id} not found")
                return None

            # Update collected_data
            answer_data = {
                "answer": answer,
                "answered_at": datetime.now(timezone.utc).isoformat(),
            }
            if raw_answer:
                answer_data["raw_answer"] = raw_answer
            if score is not None:
                answer_data["score"] = score

            collected_data = session.collected_data.copy()
            collected_data[step_id] = answer_data
            session.collected_data = collected_data

            # Calculate progress
            total_steps = len(workflow.workflow_config.get("steps", []))
            completed_steps = len(collected_data)
            session.progress_percentage = (
                int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
            )

            # Find next step
            steps = workflow.workflow_config.get("steps", [])
            current_step_index = next(
                (i for i, step in enumerate(steps) if step.get("step_id") == step_id), -1
            )
            if current_step_index >= 0 and current_step_index < len(steps) - 1:
                # Move to next step
                next_step = steps[current_step_index + 1]
                session.current_step_id = next_step.get("step_id")
            else:
                # Last question - calculate results if scored workflow
                session.current_step_id = None
                session.status = "completed"
                session.completed_at = datetime.now(timezone.utc)

                if workflow.workflow_type == "scored" and workflow.result_config:
                    result_data = await self._calculate_score(session, workflow)
                    session.result_data = result_data

            session.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(session)
            logger.info(f"Saved answer for session {session_id}, step {step_id}")
            return session
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error saving answer for session {session_id}: {e}")
            return None

    async def _calculate_score(
        self, session: WorkflowSession, workflow: PersonaWorkflow
    ) -> Dict[str, Any]:
        """
        Calculate score and find result category for a completed session

        Args:
            session: Completed workflow session
            workflow: Workflow with result_config

        Returns:
            Result data (total_score, category, category_message, etc.)
        """
        try:
            # Sum all scores from collected_data
            total_score = sum(
                answer_data.get("score", 0)
                for answer_data in session.collected_data.values()
                if isinstance(answer_data, dict)
            )

            # Calculate max possible score
            total_steps = len(workflow.workflow_config.get("steps", []))
            max_possible_score = total_steps * 4  # Assuming max 4 points per question

            # Find matching category
            categories = workflow.result_config.get("categories", [])
            matching_category = None
            for category in categories:
                min_score = category.get("min_score", 0)
                max_score = category.get("max_score", 0)
                if min_score <= total_score <= max_score:
                    matching_category = category
                    break

            if not matching_category:
                logger.warning(
                    f"No matching category for score {total_score} in workflow {workflow.id}"
                )
                matching_category = categories[0] if categories else {}

            result_data = {
                "total_score": total_score,
                "max_possible_score": max_possible_score,
                "percentage": (
                    round((total_score / max_possible_score) * 100, 1)
                    if max_possible_score > 0
                    else 0
                ),
                "category": matching_category.get("name", "Unknown"),
                "category_message": matching_category.get("message", ""),
            }

            logger.info(
                f"Calculated score for session {session.id}: {total_score}/{max_possible_score} - {result_data['category']}"
            )
            return result_data
        except Exception as e:
            logger.error(f"Error calculating score for session {session.id}: {e}")
            return {
                "total_score": 0,
                "category": "Error",
                "category_message": "Unable to calculate results",
            }

    async def abandon_session(self, session_id: UUID) -> Optional[WorkflowSession]:
        """
        Mark a session as abandoned

        Args:
            session_id: Session UUID

        Returns:
            Updated WorkflowSession if successful, None otherwise
        """
        try:
            session = await self.get_session_by_id(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found for abandonment")
                return None

            session.status = "abandoned"
            session.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(session)
            logger.info(f"Marked session {session_id} as abandoned")
            return session
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error abandoning session {session_id}: {e}")
            return None

    async def complete_session(self, session_id: UUID) -> Optional[WorkflowSession]:
        """
        Mark a linear workflow session as completed

        For linear workflows (simple/scored), this marks the session as complete
        after all questions have been answered. The scoring is done by save_answer()
        when the last question is answered.

        Args:
            session_id: Session UUID

        Returns:
            Updated WorkflowSession if successful, None otherwise
        """
        try:
            session = await self.get_session_by_id(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found for completion")
                return None

            # Mark as completed (save_answer should have already set this,
            # but this ensures it's set and allows for post-completion updates)
            session.status = "completed"
            if not session.completed_at:
                session.completed_at = datetime.now(timezone.utc)
            session.progress_percentage = 100
            session.updated_at = datetime.now(timezone.utc)

            await self.session.commit()
            await self.session.refresh(session)
            logger.info(f"Marked linear workflow session {session_id} as completed")
            return session
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error completing session {session_id}: {e}")
            return None

    # ===== Conversational Workflow Operations =====

    async def update_extracted_fields(
        self,
        session_id: UUID,
        extracted_fields: Dict[str, Any],
        progress_percentage: Optional[int] = None,
    ) -> Optional[WorkflowSession]:
        """
        Update extracted fields for a conversational workflow session.

        Uses SELECT ... FOR UPDATE to lock the row and prevent race conditions
        when multiple parallel tool calls try to update fields simultaneously.

        Args:
            session_id: Session UUID
            extracted_fields: Dictionary of extracted field values
                             Format: {field_id: {value, confidence, extraction_method, raw_input, extracted_at}}
            progress_percentage: Optional progress percentage (0-100)

        Returns:
            Updated WorkflowSession if successful, None otherwise
        """
        try:
            # Use FOR UPDATE to lock the row - prevents race conditions
            # when LLM calls update_lead_field multiple times in parallel
            stmt = select(WorkflowSession).where(WorkflowSession.id == session_id).with_for_update()
            result = await self.session.execute(stmt)
            session = result.scalar_one_or_none()

            if not session:
                logger.warning(f"Session {session_id} not found for updating extracted fields")
                return None

            # Update extracted_fields (merge with existing)
            # IMPORTANT: Create a NEW dict to ensure SQLAlchemy detects the change
            # (mutating the same dict object may not trigger dirty detection for JSONB)
            current_fields = dict(session.extracted_fields or {})
            current_fields.update(extracted_fields)
            session.extracted_fields = current_fields
            # Explicitly mark JSONB column as modified (belt and suspenders)
            attributes.flag_modified(session, "extracted_fields")

            # Update progress if provided
            if progress_percentage is not None:
                session.progress_percentage = progress_percentage

            session.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(session)
            logger.info(
                f"Updated {len(extracted_fields)} extracted fields for session {session_id}"
            )
            return session
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating extracted fields for session {session_id}: {e}")
            return None

    async def update_session_metadata(
        self,
        session_id: UUID,
        session_metadata: Dict[str, Any],
    ) -> Optional[WorkflowSession]:
        """
        Update session metadata for a workflow session.

        Used for tracking confirmation state and other session-level flags.

        Args:
            session_id: Session UUID
            session_metadata: Dictionary of metadata to merge with existing

        Returns:
            Updated WorkflowSession if successful, None otherwise
        """
        try:
            session = await self.get_session_by_id(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found for updating metadata")
                return None

            # Update session_metadata (merge with existing)
            current_metadata = session.session_metadata or {}
            current_metadata.update(session_metadata)
            session.session_metadata = current_metadata

            session.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(session)
            logger.info(f"Updated session metadata for session {session_id}")
            return session
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating session metadata for session {session_id}: {e}")
            return None

    async def update_session_conversation_id(
        self, session_id: UUID, conversation_id: UUID
    ) -> Optional[WorkflowSession]:
        """
        Link a workflow session to its conversation record.

        Called during shutdown after the conversation is saved to DB,
        since the conversation record doesn't exist when the workflow session
        is first created.

        Args:
            session_id: Workflow session UUID
            conversation_id: Conversation UUID to link

        Returns:
            Updated WorkflowSession if successful, None otherwise
        """
        try:
            session = await self.get_session_by_id(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found for linking conversation")
                return None

            session.conversation_id = conversation_id
            session.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(session)
            logger.info(f"Linked workflow session {session_id} to conversation {conversation_id}")
            return session
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error linking conversation to workflow session {session_id}: {e}")
            return None

    async def complete_conversational_session(
        self,
        session_id: UUID,
        final_summary: str,
        lead_score: float,
        priority_level: str,
    ) -> Optional[WorkflowSession]:
        """
        Mark a conversational workflow session as completed with final results

        Args:
            session_id: Session UUID
            final_summary: Formatted lead summary text
            lead_score: Final lead score (0-100)
            priority_level: Priority classification (low, medium, high)

        Returns:
            Updated WorkflowSession if successful, None otherwise
        """
        try:
            session = await self.get_session_by_id(session_id)
            if not session:
                logger.warning(
                    f"Session {session_id} not found for completing conversational workflow"
                )
                return None

            # Store summary in result_data
            session.result_data = {
                "final_summary": final_summary,
                "lead_score": lead_score,
                "priority_level": priority_level,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

            session.status = "completed"
            session.completed_at = datetime.now(timezone.utc)
            session.progress_percentage = 100
            session.updated_at = datetime.now(timezone.utc)

            await self.session.commit()
            await self.session.refresh(session)
            logger.info(
                f"Completed conversational session {session_id} with score {lead_score} ({priority_level})"
            )
            return session
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error completing conversational session {session_id}: {e}")
            return None

    async def update_session_enrichment(
        self, session_id: UUID, enrichment_data: Dict[str, Any]
    ) -> Optional[WorkflowSession]:
        """
        Update a workflow session with LLM enrichment data.

        Called by background task after lead enrichment completes.
        Merges enrichment into existing result_data.

        Args:
            session_id: Session UUID
            enrichment_data: LLM enrichment result (urgency, quality, reasoning, etc.)

        Returns:
            Updated session or None if not found
        """
        try:
            stmt = select(WorkflowSession).where(WorkflowSession.id == session_id)
            result = await self.session.execute(stmt)
            session = result.scalar_one_or_none()

            if not session:
                logger.warning(f"Session {session_id} not found for enrichment update")
                return None

            # Merge enrichment into existing result_data
            # Use copy to ensure SQLAlchemy detects the change
            current_data = dict(session.result_data) if session.result_data else {}
            current_data["llm_enrichment"] = enrichment_data

            # If LLM has high confidence, use its priority as enriched_priority
            if enrichment_data.get("confidence", 0) >= 0.7:
                current_data["enriched_priority"] = enrichment_data.get("priority_level")

            session.result_data = current_data
            session.updated_at = datetime.now(timezone.utc)

            # Flag the JSONB column as modified to ensure SQLAlchemy persists it
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(session, "result_data")

            await self.session.commit()
            await self.session.refresh(session)

            logger.info(
                f"Updated session {session_id} with LLM enrichment: "
                f"priority={enrichment_data.get('priority_level')}"
            )
            return session

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating session enrichment for {session_id}: {e}")
            return None

    async def update_session_lead_evaluation(
        self, session_id: UUID, evaluation_data: Dict[str, Any]
    ) -> Optional[WorkflowSession]:
        """
        Update a workflow session with complete LLM lead evaluation.

        This is the NEW method that stores the full LeadEvaluationResult
        from LeadScoringService. It REPLACES the old approach of storing
        separate lead_score, priority_level, and final_summary fields.

        Called by background task after lead scoring completes.
        Stores the complete evaluation as result_data (overwrites).

        Schema stored in result_data:
        {
            "lead_score": int,
            "priority_level": "high" | "medium" | "low",
            "lead_quality": "hot" | "warm" | "cold",
            "urgency_level": "high" | "medium" | "low",
            "lead_summary": {
                "contact": {"name": str, "email": str, "phone": str},
                "service_need": str,
                "additional_info": dict,
                "follow_up_questions": list
            },
            "scoring": {
                "score": int,
                "priority": str,
                "signals_matched": list,
                "penalties_applied": list,
                "reasoning": str
            },
            "confidence": float,
            "evaluated_at": str (ISO timestamp)
        }

        Args:
            session_id: Session UUID
            evaluation_data: Complete LeadEvaluationResult.model_dump()

        Returns:
            Updated session or None if not found
        """
        try:
            stmt = select(WorkflowSession).where(WorkflowSession.id == session_id)
            result = await self.session.execute(stmt)
            session = result.scalar_one_or_none()

            if not session:
                logger.warning(f"Session {session_id} not found for lead evaluation update")
                return None

            # Store the complete evaluation as result_data
            # This overwrites any existing result_data (intentional - this is the authoritative result)
            session.result_data = evaluation_data
            session.updated_at = datetime.now(timezone.utc)

            # Flag the JSONB column as modified to ensure SQLAlchemy persists it
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(session, "result_data")

            await self.session.commit()
            await self.session.refresh(session)

            logger.info(
                f"Updated session {session_id} with lead evaluation: "
                f"score={evaluation_data.get('lead_score')}, "
                f"quality={evaluation_data.get('lead_quality')}, "
                f"priority={evaluation_data.get('priority_level')}"
            )
            return session

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating lead evaluation for session {session_id}: {e}")
            return None

    # ===== Analytics Methods =====

    async def get_workflow_analytics(self, workflow_id: UUID) -> Dict[str, Any]:
        """
        Get analytics for a workflow

        Args:
            workflow_id: Workflow UUID

        Returns:
            Analytics data (completion rate, avg score, drop-off points, etc.)
        """
        try:
            # Get all sessions
            stmt = select(WorkflowSession).where(WorkflowSession.workflow_id == workflow_id)
            result = await self.session.execute(stmt)
            sessions = list(result.scalars().all())

            if not sessions:
                return {
                    "workflow_id": str(workflow_id),
                    "total_sessions": 0,
                    "completed_sessions": 0,
                    "abandoned_sessions": 0,
                    "completion_rate": 0.0,
                }

            total_sessions = len(sessions)
            completed_sessions = len([s for s in sessions if s.status == "completed"])
            abandoned_sessions = len([s for s in sessions if s.status == "abandoned"])
            in_progress_sessions = len([s for s in sessions if s.status == "in_progress"])

            completion_rate = (
                (completed_sessions / total_sessions) * 100 if total_sessions > 0 else 0
            )

            # Calculate avg completion time for completed sessions
            completed_with_time = [
                s for s in sessions if s.status == "completed" and s.completed_at and s.started_at
            ]
            if completed_with_time:
                avg_time_seconds = sum(
                    (s.completed_at - s.started_at).total_seconds() for s in completed_with_time
                ) / len(completed_with_time)
            else:
                avg_time_seconds = None

            # Score distribution (for scored workflows)
            # Supports both old schema (total_score, category) and new schema (lead_score, lead_quality)
            avg_score = None
            score_distribution = {}
            completed_scored = [s for s in sessions if s.status == "completed" and s.result_data]
            if completed_scored:
                scores = [
                    s.result_data.get("lead_score") or s.result_data.get("total_score", 0)
                    for s in completed_scored
                ]
                avg_score = sum(scores) / len(scores) if scores else None

                # Category distribution (lead_quality for new schema, category for old)
                for session in completed_scored:
                    category = session.result_data.get("lead_quality") or session.result_data.get(
                        "category", "Unknown"
                    )
                    score_distribution[category] = score_distribution.get(category, 0) + 1

            # Drop-off analysis
            drop_off_by_step = {}
            for session in sessions:
                if session.status == "abandoned" and session.current_step_id:
                    step_id = session.current_step_id
                    drop_off_by_step[step_id] = drop_off_by_step.get(step_id, 0) + 1

            return {
                "workflow_id": str(workflow_id),
                "total_sessions": total_sessions,
                "completed_sessions": completed_sessions,
                "abandoned_sessions": abandoned_sessions,
                "in_progress_sessions": in_progress_sessions,
                "completion_rate": round(completion_rate, 1),
                "avg_completion_time_seconds": (
                    round(avg_time_seconds, 1) if avg_time_seconds else None
                ),
                "avg_score": round(avg_score, 1) if avg_score else None,
                "score_distribution": score_distribution,
                "drop_off_by_step": drop_off_by_step,
            }
        except Exception as e:
            logger.error(f"Error getting analytics for workflow {workflow_id}: {e}")
            return {
                "workflow_id": str(workflow_id),
                "total_sessions": 0,
                "error": str(e),
            }

    # ===== Lead Export Operations =====

    async def get_leads_with_conversations(
        self,
        persona_id: UUID,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get workflow sessions (leads) with their associated conversation data.

        Uses SQLAlchemy ORM to join workflow_sessions to conversations via session_token.
        This enables CRM export with full conversation context.

        Args:
            persona_id: Filter by persona
            status: Filter by session status ('in_progress', 'completed', 'abandoned')
            limit: Maximum number of results (default 100)
            offset: Number of results to skip for pagination

        Returns:
            List of dictionaries containing lead data with conversation info:
            [
                {
                    "lead_id": UUID,
                    "workflow_id": UUID,
                    "status": str,
                    "progress_percentage": int,
                    "extracted_fields": dict,  # The captured lead data
                    "started_at": datetime,
                    "completed_at": datetime | None,
                    "session_token": str | None,
                    "conversation_id": UUID | None,
                    "conversation_messages": list | None,
                    "conversation_summary": str | None,
                    "conversation_type": str | None,
                }
            ]
        """
        try:
            # Build query with outer join to conversations
            stmt = (
                select(WorkflowSession, Conversation)
                .outerjoin(
                    Conversation,
                    and_(
                        Conversation.session_id == WorkflowSession.session_token,
                        Conversation.persona_id == WorkflowSession.persona_id,
                    ),
                )
                .where(WorkflowSession.persona_id == persona_id)
            )

            # Apply status filter if provided
            if status:
                stmt = stmt.where(WorkflowSession.status == status)

            # Order by most recent first, apply pagination
            stmt = stmt.order_by(WorkflowSession.started_at.desc()).limit(limit).offset(offset)

            result = await self.session.execute(stmt)
            rows = result.all()

            # Transform to list of dicts for easy consumption
            leads = []
            for workflow_session, conversation in rows:
                lead = {
                    "lead_id": workflow_session.id,
                    "workflow_id": workflow_session.workflow_id,
                    "status": workflow_session.status,
                    "progress_percentage": workflow_session.progress_percentage,
                    "extracted_fields": workflow_session.extracted_fields,
                    "started_at": workflow_session.started_at,
                    "completed_at": workflow_session.completed_at,
                    "session_token": workflow_session.session_token,
                    # Conversation data (may be None if no conversation linked)
                    "conversation_id": conversation.id if conversation else None,
                    "conversation_messages": conversation.messages if conversation else None,
                    "conversation_summary": conversation.ai_summary if conversation else None,
                    "conversation_type": (conversation.conversation_type if conversation else None),
                }
                leads.append(lead)

            logger.info(
                f"Retrieved {len(leads)} leads for persona {persona_id} "
                f"(status={status}, limit={limit}, offset={offset})"
            )
            return leads

        except Exception as e:
            logger.error(f"Error getting leads with conversations for persona {persona_id}: {e}")
            return []

    async def count_leads(
        self,
        persona_id: UUID,
        status: Optional[str] = None,
    ) -> int:
        """
        Count workflow sessions (leads) for a persona.

        Args:
            persona_id: Filter by persona
            status: Filter by session status (optional)

        Returns:
            Total count of leads matching the criteria
        """
        try:
            stmt = select(func.count(WorkflowSession.id)).where(
                WorkflowSession.persona_id == persona_id
            )

            if status:
                stmt = stmt.where(WorkflowSession.status == status)

            result = await self.session.execute(stmt)
            return result.scalar_one()

        except Exception as e:
            logger.error(f"Error counting leads for persona {persona_id}: {e}")
            return 0
