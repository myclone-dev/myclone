"""
Workflow Template Repository - Database operations for workflow templates

Provides CRUD operations for:
- WorkflowTemplate: Master template library for conversational workflows

Added: 2026-01-25
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.workflow import WorkflowTemplate

logger = logging.getLogger(__name__)


class WorkflowTemplateRepository:
    """
    Repository for workflow template database operations.

    Handles CRUD operations for the master template library used in
    the Copy-on-Enable template system.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session

        Args:
            session: Database session
        """
        self.session = session

    # ===== Template CRUD Operations =====

    async def create_template(
        self,
        template_key: str,
        template_name: str,
        template_category: str,
        workflow_type: str,
        workflow_config: Dict[str, Any],
        output_template: Dict[str, Any],
        minimum_plan_tier_id: int = 3,
        description: Optional[str] = None,
        preview_image_url: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by: Optional[UUID] = None,
    ) -> WorkflowTemplate:
        """
        Create a new workflow template

        Args:
            template_key: Unique key for code references (e.g., 'cpa_lead_capture')
            template_name: Display name (e.g., 'CPA Lead Capture')
            template_category: Category for filtering (e.g., 'cpa', 'tax')
            workflow_type: Type of workflow (typically 'conversational')
            workflow_config: Base field definitions and extraction strategy
            output_template: Base scoring rules and output configuration
            minimum_plan_tier_id: Minimum tier required (default: 3 = enterprise)
            description: Template description for UI (optional)
            preview_image_url: Screenshot for gallery (optional)
            tags: Tags for search/filtering (optional)
            created_by: User who created template (optional, NULL = admin)

        Returns:
            Created WorkflowTemplate
        """
        try:
            template = WorkflowTemplate(
                template_key=template_key,
                template_name=template_name,
                template_category=template_category,
                workflow_type=workflow_type,
                workflow_config=workflow_config,
                output_template=output_template,
                minimum_plan_tier_id=minimum_plan_tier_id,
                description=description,
                preview_image_url=preview_image_url,
                tags=tags,
                created_by=created_by,
            )
            self.session.add(template)
            await self.session.commit()
            await self.session.refresh(template)
            logger.info(f"Created workflow template '{template_key}' (id={template.id})")
            return template
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating workflow template '{template_key}': {e}")
            raise

    async def get_template_by_id(self, template_id: UUID) -> Optional[WorkflowTemplate]:
        """
        Get template by ID

        Args:
            template_id: Template UUID

        Returns:
            WorkflowTemplate if found, None otherwise
        """
        try:
            stmt = select(WorkflowTemplate).where(WorkflowTemplate.id == template_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting template {template_id}: {e}")
            return None

    async def get_template_by_key(self, template_key: str) -> Optional[WorkflowTemplate]:
        """
        Get template by unique key

        Args:
            template_key: Template key (e.g., 'cpa_lead_capture')

        Returns:
            WorkflowTemplate if found, None otherwise
        """
        try:
            stmt = select(WorkflowTemplate).where(WorkflowTemplate.template_key == template_key)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting template by key '{template_key}': {e}")
            return None

    async def list_templates(
        self,
        category: Optional[str] = None,
        minimum_plan_tier_id: Optional[int] = None,
        active_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[WorkflowTemplate]:
        """
        List workflow templates with optional filtering

        Args:
            category: Filter by category (optional)
            minimum_plan_tier_id: Filter by specific tier ID (optional)
            active_only: Only return active templates (default: True)
            limit: Maximum number of templates to return
            offset: Number of templates to skip

        Returns:
            List of WorkflowTemplate
        """
        try:
            stmt = select(WorkflowTemplate)

            if active_only:
                stmt = stmt.where(WorkflowTemplate.is_active == True)

            if category:
                stmt = stmt.where(WorkflowTemplate.template_category == category)

            if minimum_plan_tier_id is not None:
                stmt = stmt.where(WorkflowTemplate.minimum_plan_tier_id == minimum_plan_tier_id)

            stmt = stmt.order_by(WorkflowTemplate.created_at.desc())

            if limit:
                stmt = stmt.limit(limit)
            if offset:
                stmt = stmt.offset(offset)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error listing templates: {e}")
            return []

    async def get_templates_by_tier_ids(
        self,
        tier_ids: List[int],
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> List[WorkflowTemplate]:
        """
        Get templates available for a list of accessible tier IDs

        Tier hierarchy:
        - 0: free (lowest)
        - 1: pro
        - 2: business
        - 3: enterprise (HIGHEST - can access everything)

        Args:
            tier_ids: List of tier IDs the user can access (e.g., [0, 1, 2] for business tier)
            category: Filter by category (optional)
            active_only: Only return active templates (default: True)

        Returns:
            List of WorkflowTemplate the user can access
        """
        try:
            stmt = select(WorkflowTemplate)

            if active_only:
                stmt = stmt.where(WorkflowTemplate.is_active == True)

            if category:
                stmt = stmt.where(WorkflowTemplate.template_category == category)

            # Filter by accessible tiers
            if tier_ids:
                stmt = stmt.where(WorkflowTemplate.minimum_plan_tier_id.in_(tier_ids))
            else:
                # Empty tier list means no access
                stmt = stmt.where(False)

            stmt = stmt.order_by(WorkflowTemplate.created_at.desc())

            result = await self.session.execute(stmt)
            templates = list(result.scalars().all())
            logger.info(f"Found {len(templates)} templates for tier_ids {tier_ids}")
            return templates
        except Exception as e:
            logger.error(f"Error getting templates for tier_ids {tier_ids}: {e}")
            return []

    async def update_template(
        self,
        template_id: UUID,
        **updates: Any,
    ) -> Optional[WorkflowTemplate]:
        """
        Update template fields

        Note: Updating workflow_config or output_template will increment version

        Args:
            template_id: Template UUID
            **updates: Fields to update

        Returns:
            Updated WorkflowTemplate if successful, None otherwise
        """
        try:
            template = await self.get_template_by_id(template_id)
            if not template:
                logger.warning(f"Template {template_id} not found for update")
                return None

            # Check if config changed (increment version if so)
            if "workflow_config" in updates or "output_template" in updates:
                template.version += 1
                logger.info(f"Incremented template version to {template.version}")

            for key, value in updates.items():
                if hasattr(template, key):
                    setattr(template, key, value)

            template.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            await self.session.refresh(template)
            logger.info(f"Updated template {template_id}")
            return template
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating template {template_id}: {e}")
            return None

    async def publish_template(self, template_id: UUID) -> Optional[WorkflowTemplate]:
        """
        Publish a template (set published_at timestamp and activate)

        Args:
            template_id: Template UUID

        Returns:
            Updated WorkflowTemplate if successful, None otherwise
        """
        return await self.update_template(
            template_id,
            published_at=datetime.now(timezone.utc),
            is_active=True,
        )

    async def deactivate_template(self, template_id: UUID) -> Optional[WorkflowTemplate]:
        """
        Deactivate a template (hide from library, existing workflows unaffected)

        Args:
            template_id: Template UUID

        Returns:
            Updated WorkflowTemplate if successful, None otherwise
        """
        return await self.update_template(template_id, is_active=False)

    async def activate_template(self, template_id: UUID) -> Optional[WorkflowTemplate]:
        """
        Activate a template (show in library)

        Args:
            template_id: Template UUID

        Returns:
            Updated WorkflowTemplate if successful, None otherwise
        """
        return await self.update_template(template_id, is_active=True)

    async def delete_template(self, template_id: UUID) -> bool:
        """
        Delete a template (hard delete)

        Note: If personas reference this template, their template_id will be set to NULL
        (ON DELETE SET NULL in foreign key constraint). They keep their copied config.

        Args:
            template_id: Template UUID

        Returns:
            True if deleted, False otherwise
        """
        try:
            template = await self.get_template_by_id(template_id)
            if not template:
                logger.warning(f"Template {template_id} not found for deletion")
                return False

            await self.session.delete(template)
            await self.session.commit()
            logger.info(f"Deleted template {template_id}")
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting template {template_id}: {e}")
            return False

    # ===== Template Analytics =====

    async def get_template_usage_count(self, template_id: UUID) -> int:
        """
        Count how many personas are using this template

        Args:
            template_id: Template UUID

        Returns:
            Number of persona_workflows referencing this template
        """
        try:
            from sqlalchemy import func

            from shared.database.models.workflow import PersonaWorkflow

            stmt = select(func.count(PersonaWorkflow.id)).where(
                PersonaWorkflow.template_id == template_id
            )
            result = await self.session.execute(stmt)
            count = result.scalar_one()
            logger.debug(f"Template {template_id} used by {count} workflows")
            return count
        except Exception as e:
            logger.error(f"Error counting template usage for {template_id}: {e}")
            return 0

    async def get_customization_rate(self, template_id: UUID) -> float:
        """
        Calculate what percentage of workflows using this template have customized it

        Args:
            template_id: Template UUID

        Returns:
            Percentage of workflows with is_template_customized=True (0-100)
        """
        try:
            from sqlalchemy import func

            from shared.database.models.workflow import PersonaWorkflow

            total_stmt = select(func.count(PersonaWorkflow.id)).where(
                PersonaWorkflow.template_id == template_id
            )
            customized_stmt = select(func.count(PersonaWorkflow.id)).where(
                PersonaWorkflow.template_id == template_id,
                PersonaWorkflow.is_template_customized == True,
            )

            total_result = await self.session.execute(total_stmt)
            customized_result = await self.session.execute(customized_stmt)

            total = total_result.scalar_one()
            customized = customized_result.scalar_one()

            rate = (customized / total * 100) if total > 0 else 0
            logger.debug(f"Template {template_id}: {customized}/{total} customized ({rate:.1f}%)")
            return rate
        except Exception as e:
            logger.error(f"Error calculating customization rate for {template_id}: {e}")
            return 0.0
