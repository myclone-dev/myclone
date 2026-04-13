"""
PersonaPrompt History and Versioning Service

Handles versioning, archiving, and history management for PersonaPrompt records.
Implements the strategy where:
- Main table contains only current active versions
- History table contains all previous versions
- Updates/deletes archive old versions before making changes
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.database import PersonaPrompt, PersonaPromptHistory

logger = logging.getLogger(__name__)


class PersonaPromptHistoryService:
    """Service for managing PersonaPrompt versioning and history"""

    @staticmethod
    async def _get_next_version(db: AsyncSession, persona_id: UUID) -> int:
        """Calculate the next version number for a persona"""
        result = await db.execute(
            select(func.max(PersonaPromptHistory.version)).where(
                PersonaPromptHistory.persona_id == persona_id
            )
        )
        max_version = result.scalar()
        return (max_version or 0) + 1

    @staticmethod
    async def _archive_current_version(
        db: AsyncSession, current_record: PersonaPrompt, operation: str
    ) -> PersonaPromptHistory:
        """Archive current version to history table before update/delete"""
        next_version = await PersonaPromptHistoryService._get_next_version(
            db, current_record.persona_id
        )

        history_entry = PersonaPromptHistory(
            original_id=current_record.id,
            persona_id=current_record.persona_id,
            introduction=current_record.introduction,
            thinking_style=current_record.thinking_style,
            area_of_expertise=current_record.area_of_expertise,
            chat_objective=current_record.chat_objective,
            objective_response=current_record.objective_response,
            example_responses=current_record.example_responses,
            target_audience=current_record.target_audience,
            prompt_template_id=current_record.prompt_template_id,
            example_prompt=current_record.example_prompt,
            is_dynamic=current_record.is_dynamic,
            is_active=current_record.is_active,
            response_structure=current_record.response_structure,
            conversation_flow=current_record.conversation_flow,
            strict_guideline=current_record.strict_guideline,
            updated_at=current_record.updated_at,
            version=next_version,
            operation=operation,
            # created_at will be automatically set to NOW() by default
        )

        db.add(history_entry)
        await db.flush()

        logger.info(
            f"Archived persona prompt for persona_id '{current_record.persona_id}' version {next_version} with operation '{operation}'"
        )
        return history_entry

    @staticmethod
    async def update_persona_prompt_with_versioning(
        db: AsyncSession, persona_id: UUID, update_data: Dict[str, Any]
    ) -> Tuple[PersonaPrompt, PersonaPromptHistory]:
        """Update persona prompt with automatic versioning"""
        # Get current record
        result = await db.execute(
            select(PersonaPrompt).where(
                and_(PersonaPrompt.persona_id == persona_id, PersonaPrompt.is_active == True)
            )
        )
        current_record = result.scalar_one_or_none()

        if not current_record:
            raise ValueError(f"Active PersonaPrompt not found for persona_id: {persona_id}")

        # Archive current version before updating
        history_entry = await PersonaPromptHistoryService._archive_current_version(
            db, current_record, "UPDATE"
        )

        # Update current record
        for key, value in update_data.items():
            if hasattr(current_record, key):
                setattr(current_record, key, value)

        current_record.updated_at = datetime.now(timezone.utc)
        await db.flush()

        logger.info(f"Updated persona prompt for persona_id '{persona_id}' to new version")
        return current_record, history_entry

    @staticmethod
    async def delete_persona_prompt_with_versioning(
        db: AsyncSession, persona_id: UUID, soft_delete: bool = True
    ) -> PersonaPromptHistory:
        """Delete persona prompt with versioning (soft or hard delete)"""
        # Get current record
        result = await db.execute(
            select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id)
        )
        current_record = result.scalar_one_or_none()

        if not current_record:
            raise ValueError(f"PersonaPrompt not found for persona_id: {persona_id}")

        # Determine operation type
        operation = "DEACTIVATE" if soft_delete else "DELETE"

        # Archive current version before deletion
        history_entry = await PersonaPromptHistoryService._archive_current_version(
            db, current_record, operation
        )

        if soft_delete:
            # Soft delete: just deactivate
            current_record.is_active = False
            current_record.updated_at = datetime.now(timezone.utc)
            logger.info(f"Soft deleted (deactivated) persona prompt for persona_id '{persona_id}'")
        else:
            # Hard delete: remove from main table
            await db.delete(current_record)
            logger.info(f"Hard deleted persona prompt for persona_id '{persona_id}'")

        await db.flush()
        return history_entry

    @staticmethod
    async def get_persona_prompt_history(
        db: AsyncSession, persona_id: UUID, limit: Optional[int] = None
    ) -> List[PersonaPromptHistory]:
        """Get all historical versions (excluding current version)"""
        query = (
            select(PersonaPromptHistory)
            .where(PersonaPromptHistory.persona_id == persona_id)
            .order_by(desc(PersonaPromptHistory.version))
        )

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_complete_timeline(db: AsyncSession, persona_id: UUID) -> List[Dict[str, Any]]:
        """Get complete timeline: history + current version"""
        # Get historical versions
        history_records = await PersonaPromptHistoryService.get_persona_prompt_history(
            db, persona_id
        )

        # Get current version
        result = await db.execute(
            select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id)
        )
        current_record = result.scalar_one_or_none()

        timeline = []

        # Add historical versions
        for history in history_records:
            timeline.append(
                {
                    "version": history.version,
                    "operation": history.operation,
                    "changed_at": history.created_at,  # created_at represents when this version was archived
                    "is_current": False,
                    "data": {
                        "id": history.original_id,
                        "persona_id": str(history.persona_id),
                        "introduction": history.introduction,
                        "thinking_style": history.thinking_style,
                        "area_of_expertise": history.area_of_expertise,
                        "chat_objective": history.chat_objective,
                        "objective_response": history.objective_response,
                        "example_responses": history.example_responses,
                        "target_audience": history.target_audience,
                        "prompt_template_id": history.prompt_template_id,
                        "example_prompt": history.example_prompt,
                        "is_dynamic": history.is_dynamic,
                        "is_active": history.is_active,
                        "response_structure": history.response_structure,
                        "conversation_flow": history.conversation_flow,
                        "created_at": history.created_at,
                        "updated_at": history.updated_at,
                    },
                }
            )

        # Add current version if exists
        if current_record:
            current_version = await PersonaPromptHistoryService._get_next_version(db, persona_id)
            timeline.append(
                {
                    "version": current_version,
                    "operation": "CURRENT",
                    "changed_at": current_record.updated_at,
                    "is_current": True,
                    "data": {
                        "id": current_record.id,
                        "persona_id": str(current_record.persona_id),
                        "introduction": current_record.introduction,
                        "thinking_style": current_record.thinking_style,
                        "area_of_expertise": current_record.area_of_expertise,
                        "chat_objective": current_record.chat_objective,
                        "objective_response": current_record.objective_response,
                        "example_responses": current_record.example_responses,
                        "target_audience": current_record.target_audience,
                        "prompt_template_id": current_record.prompt_template_id,
                        "example_prompt": current_record.example_prompt,
                        "is_dynamic": current_record.is_dynamic,
                        "is_active": current_record.is_active,
                        "response_structure": current_record.response_structure,
                        "conversation_flow": current_record.conversation_flow,
                        "strict_guideline": current_record.strict_guideline,
                        "created_at": current_record.created_at,
                        "updated_at": current_record.updated_at,
                    },
                }
            )

        # Sort by version descending (newest first)
        timeline.sort(key=lambda x: x["version"], reverse=True)
        return timeline

    @staticmethod
    async def get_specific_version(
        db: AsyncSession, persona_id: UUID, version: int
    ) -> Optional[PersonaPromptHistory]:
        """Get a specific historical version"""
        result = await db.execute(
            select(PersonaPromptHistory).where(
                and_(
                    PersonaPromptHistory.persona_id == persona_id,
                    PersonaPromptHistory.version == version,
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def restore_version(
        db: AsyncSession, persona_id: UUID, restore_version: int
    ) -> Tuple[PersonaPrompt, PersonaPromptHistory]:
        """Restore a previous version as current"""
        # Get the version to restore
        historical_version = await PersonaPromptHistoryService.get_specific_version(
            db, persona_id, restore_version
        )

        if not historical_version:
            raise ValueError(f"Version {restore_version} not found for persona_id '{persona_id}'")

        # Get current record (to archive before restore)
        result = await db.execute(
            select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id)
        )
        current_record = result.scalar_one_or_none()

        if not current_record:
            raise ValueError(f"Current PersonaPrompt not found for persona_id: {persona_id}")

        # Archive current version before restoring
        archive_entry = await PersonaPromptHistoryService._archive_current_version(
            db, current_record, "UPDATE"
        )

        # Restore the historical version data to current record
        restore_data = {
            "introduction": historical_version.introduction,
            "thinking_style": historical_version.thinking_style,
            "area_of_expertise": historical_version.area_of_expertise,
            "chat_objective": historical_version.chat_objective,
            "objective_response": historical_version.objective_response,
            "example_responses": historical_version.example_responses,
            "target_audience": historical_version.target_audience,
            "prompt_template_id": historical_version.prompt_template_id,
            "example_prompt": historical_version.example_prompt,
            "is_dynamic": historical_version.is_dynamic,
            "is_active": True,  # Always activate when restoring
            "response_structure": historical_version.response_structure,
            "conversation_flow": historical_version.conversation_flow,
            "strict_guideline": historical_version.strict_guideline,
            "updated_at": datetime.now(timezone.utc),
        }

        for key, value in restore_data.items():
            setattr(current_record, key, value)

        await db.flush()

        logger.info(
            f"Restored persona prompt for persona_id '{persona_id}' to version {restore_version}"
        )
        return current_record, archive_entry

    @staticmethod
    async def compare_versions(
        db: AsyncSession, persona_id: UUID, version1: int, version2: int
    ) -> Dict[str, Any]:
        """Compare two versions and return differences"""
        # Get version data
        if version1 == 0:  # 0 represents current version
            result = await db.execute(
                select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id)
            )
            v1_record = result.scalar_one_or_none()
            if not v1_record:
                raise ValueError("Current version not found")
            v1_data = {
                "introduction": v1_record.introduction,
                "thinking_style": v1_record.thinking_style,
                "area_of_expertise": v1_record.area_of_expertise,
                "chat_objective": v1_record.chat_objective,
                "objective_response": v1_record.objective_response,
                "example_responses": v1_record.example_responses,
                "target_audience": v1_record.target_audience,
                "prompt_template_id": v1_record.prompt_template_id,
                "example_prompt": v1_record.example_prompt,
                "is_dynamic": v1_record.is_dynamic,
                "is_active": v1_record.is_active,
                "response_structure": v1_record.response_structure,
                "conversation_flow": v1_record.conversation_flow,
                "updated_at": v1_record.updated_at,
            }
        else:
            v1_record = await PersonaPromptHistoryService.get_specific_version(
                db, persona_id, version1
            )
            if not v1_record:
                raise ValueError(f"Version {version1} not found")
            v1_data = {
                "introduction": v1_record.introduction,
                "thinking_style": v1_record.thinking_style,
                "area_of_expertise": v1_record.area_of_expertise,
                "chat_objective": v1_record.chat_objective,
                "objective_response": v1_record.objective_response,
                "example_responses": v1_record.example_responses,
                "target_audience": v1_record.target_audience,
                "prompt_template_id": v1_record.prompt_template_id,
                "example_prompt": v1_record.example_prompt,
                "is_dynamic": v1_record.is_dynamic,
                "is_active": v1_record.is_active,
                "response_structure": v1_record.response_structure,
                "conversation_flow": v1_record.conversation_flow,
                "updated_at": v1_record.updated_at,
            }

        if version2 == 0:  # 0 represents current version
            result = await db.execute(
                select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id)
            )
            v2_record = result.scalar_one_or_none()
            if not v2_record:
                raise ValueError("Current version not found")
            v2_data = {
                "introduction": v2_record.introduction,
                "thinking_style": v2_record.thinking_style,
                "area_of_expertise": v2_record.area_of_expertise,
                "chat_objective": v2_record.chat_objective,
                "objective_response": v2_record.objective_response,
                "example_responses": v2_record.example_responses,
                "target_audience": v2_record.target_audience,
                "prompt_template_id": v2_record.prompt_template_id,
                "example_prompt": v2_record.example_prompt,
                "is_dynamic": v2_record.is_dynamic,
                "is_active": v2_record.is_active,
                "response_structure": v2_record.response_structure,
                "conversation_flow": v2_record.conversation_flow,
                "strict_guideline": v2_record.strict_guideline,
                "updated_at": v2_record.updated_at,
            }
        else:
            v2_record = await PersonaPromptHistoryService.get_specific_version(
                db, persona_id, version2
            )
            if not v2_record:
                raise ValueError(f"Version {version2} not found")
            v2_data = {
                "introduction": v2_record.introduction,
                "thinking_style": v2_record.thinking_style,
                "area_of_expertise": v2_record.area_of_expertise,
                "chat_objective": v2_record.chat_objective,
                "objective_response": v2_record.objective_response,
                "example_responses": v2_record.example_responses,
                "target_audience": v2_record.target_audience,
                "prompt_template_id": v2_record.prompt_template_id,
                "example_prompt": v2_record.example_prompt,
                "is_dynamic": v2_record.is_dynamic,
                "is_active": v2_record.is_active,
                "response_structure": v2_record.response_structure,
                "conversation_flow": v2_record.conversation_flow,
                "strict_guideline": v2_record.strict_guideline,
                "updated_at": v2_record.updated_at,
            }

        # Compare and find differences
        differences = {}
        for key in v1_data.keys():
            if v1_data[key] != v2_data[key]:
                differences[key] = {
                    f"version_{version1}": v1_data[key],
                    f"version_{version2}": v2_data[key],
                }

        return {
            "persona_id": str(persona_id),
            "version_1": version1,
            "version_2": version2,
            "differences": differences,
            "identical": len(differences) == 0,
        }

    @staticmethod
    async def get_version_metadata(db: AsyncSession, persona_id: UUID) -> List[Dict[str, Any]]:
        """Get version metadata (version numbers, operations, timestamps)"""
        # Get historical metadata
        result = await db.execute(
            select(
                PersonaPromptHistory.version,
                PersonaPromptHistory.operation,
                PersonaPromptHistory.created_at,
            )
            .where(PersonaPromptHistory.persona_id == persona_id)
            .order_by(desc(PersonaPromptHistory.version))
        )

        metadata = []
        for version, operation, created_at in result.fetchall():
            metadata.append(
                {
                    "version": version,
                    "operation": operation,
                    "changed_at": created_at,  # created_at represents when this version was archived
                    "is_current": False,
                }
            )

        # Add current version metadata
        result = await db.execute(
            select(PersonaPrompt.updated_at).where(PersonaPrompt.persona_id == persona_id)
        )
        current_updated_at = result.scalar_one_or_none()

        if current_updated_at:
            current_version = await PersonaPromptHistoryService._get_next_version(db, persona_id)
            metadata.append(
                {
                    "version": current_version,
                    "operation": "CURRENT",
                    "changed_at": current_updated_at,
                    "is_current": True,
                }
            )

        # Sort by version descending
        metadata.sort(key=lambda x: x["version"], reverse=True)
        return metadata

    @staticmethod
    async def get_history_count(db: AsyncSession, persona_id: UUID) -> int:
        """Get count of historical versions"""
        result = await db.execute(
            select(func.count(PersonaPromptHistory.id)).where(
                PersonaPromptHistory.persona_id == persona_id
            )
        )
        return result.scalar() or 0
