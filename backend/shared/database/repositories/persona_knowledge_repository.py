"""
Persona Knowledge Repository

Data access layer for persona-knowledge relationships.
Handles fetching knowledge sources attached to personas with optimized bulk operations.
"""

import logging
from typing import Dict, List, Sequence, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.document import Document
from shared.database.models.embeddings import VoyageLiteEmbedding

# NOTE: Using VoyageLiteEmbedding (data_llamalite_embeddings table, 512 dims, Voyage AI)
from shared.database.models.persona_data_source import PersonaDataSource
from shared.database.models.youtube import YouTubeVideo
from shared.schemas.knowledge_library import PersonaKnowledgeSource

logger = logging.getLogger(__name__)


class PersonaKnowledgeRepository:
    """Repository for persona-knowledge source operations"""

    @staticmethod
    async def get_persona_knowledge_sources(
        session: AsyncSession, persona_id: UUID
    ) -> List[PersonaKnowledgeSource]:
        """
        Get all knowledge sources attached to a single persona.

        Args:
            session: Database session
            persona_id: Persona UUID

        Returns:
            List of PersonaKnowledgeSource objects
        """
        stmt = select(PersonaDataSource).where(PersonaDataSource.persona_id == persona_id)
        result = await session.execute(stmt)
        persona_sources = result.scalars().all()

        if not persona_sources:
            return []

        sources = []
        for pds in persona_sources:
            # Skip sources with null source_record_id
            if pds.source_record_id is None:
                logger.warning(f"Skipping PersonaDataSource {pds.id} with null source_record_id")
                continue

            # Get embeddings count for this source
            embeddings_count = await PersonaKnowledgeRepository._get_source_embeddings_count(
                session, pds.source_record_id
            )

            # Get display name based on source type
            display_name = await PersonaKnowledgeRepository._get_source_display_name(
                session, pds.source_type, pds.source_record_id
            )

            sources.append(
                PersonaKnowledgeSource(
                    id=pds.id,
                    source_type=pds.source_type,
                    source_record_id=pds.source_record_id,
                    display_name=display_name,
                    enabled=pds.enabled,
                    enabled_at=pds.enabled_at,
                    disabled_at=pds.disabled_at,
                    embeddings_count=embeddings_count,
                    created_at=pds.created_at,
                )
            )

        return sources

    @staticmethod
    async def get_personas_knowledge_sources_bulk(
        session: AsyncSession, persona_ids: List[UUID]
    ) -> Dict[UUID, List[PersonaKnowledgeSource]]:
        """
        Optimized bulk fetch of knowledge sources for multiple personas.

        Fixes N+1 query problem by:
        1. Fetching all PersonaDataSource rows for all personas at once
        2. Bulk counting embeddings grouped by source_record_id
        3. Bulk fetching display names grouped by source_type

        Args:
            session: Database session
            persona_ids: List of persona UUIDs

        Returns:
            Dict mapping persona_id to list of PersonaKnowledgeSource

        Performance:
            Before: 1 + N + M*N + M*N queries (where N=personas, M=sources per persona)
            After: 1 + 1 + 5 queries (max 7 queries regardless of personas/sources count)
        """
        if not persona_ids:
            return {}

        # Step 1: Fetch all PersonaDataSource rows for all personas (1 query)
        stmt = select(PersonaDataSource).where(PersonaDataSource.persona_id.in_(persona_ids))
        result = await session.execute(stmt)
        persona_sources = result.scalars().all()

        if not persona_sources:
            # Return empty dict for all personas
            return {pid: [] for pid in persona_ids}

        # Filter out sources with null source_record_id
        valid_sources = [pds for pds in persona_sources if pds.source_record_id is not None]

        if not valid_sources:
            # All sources have null source_record_id
            logger.warning("All PersonaDataSource entries have null source_record_id")
            return {pid: [] for pid in persona_ids}

        # Step 2: Bulk count embeddings for all source_record_ids (1 query)
        source_record_ids = list({pds.source_record_id for pds in valid_sources})
        embeddings_stmt = (
            select(
                VoyageLiteEmbedding.source_record_id,
                func.count().label("count"),
            )
            .where(VoyageLiteEmbedding.source_record_id.in_(source_record_ids))
            .group_by(VoyageLiteEmbedding.source_record_id)
        )
        embeddings_result = await session.execute(embeddings_stmt)
        embeddings_counts = {row[0]: row[1] for row in embeddings_result}

        # Step 3: Bulk fetch display names grouped by source_type (max 5 queries for 5 source types)
        display_names = await PersonaKnowledgeRepository._bulk_get_display_names(
            session, valid_sources
        )

        # Step 4: Build result dict grouped by persona_id
        result_dict: Dict[UUID, List[PersonaKnowledgeSource]] = {pid: [] for pid in persona_ids}

        for pds in valid_sources:
            # source_record_id is guaranteed to be non-None here due to filtering
            source_record_id = pds.source_record_id

            # Explicit validation for production safety (assert removed with -O flag)
            if source_record_id is None:
                logger.error(
                    f"PersonaDataSource {pds.id} has null source_record_id after filtering. "
                    "This should not happen - check filtering logic."
                )
                continue

            embeddings_count = embeddings_counts.get(source_record_id, 0)
            display_name = display_names.get(
                (pds.source_type, source_record_id),
                f"{pds.source_type.capitalize()} Source",
            )

            result_dict[pds.persona_id].append(
                PersonaKnowledgeSource(
                    id=pds.id,
                    source_type=pds.source_type,
                    source_record_id=source_record_id,
                    display_name=display_name,
                    enabled=pds.enabled,
                    enabled_at=pds.enabled_at,
                    disabled_at=pds.disabled_at,
                    embeddings_count=embeddings_count,
                    created_at=pds.created_at,
                )
            )

        return result_dict

    @staticmethod
    async def _bulk_get_display_names(
        session: AsyncSession, persona_sources: Sequence[PersonaDataSource]
    ) -> Dict[Tuple[str, UUID], str]:
        """
        Bulk fetch display names for all sources grouped by source_type.

        Args:
            session: Database session
            persona_sources: Sequence of PersonaDataSource objects (must have non-None source_record_id)

        Returns:
            Dict mapping (source_type, source_record_id) to display_name
        """
        display_names = {}

        # Group sources by type
        sources_by_type: Dict[str, List[UUID]] = {}
        for pds in persona_sources:
            # source_record_id should be non-None (filtered by caller)
            if pds.source_record_id is None:
                logger.warning(f"Skipping PersonaDataSource {pds.id} with null source_record_id")
                continue

            if pds.source_type not in sources_by_type:
                sources_by_type[pds.source_type] = []
            sources_by_type[pds.source_type].append(pds.source_record_id)

        # LinkedIn, Twitter, Website tables have been removed; use default display names
        for source_id in sources_by_type.get("linkedin", []):
            display_names[("linkedin", source_id)] = "LinkedIn Profile"
        for source_id in sources_by_type.get("twitter", []):
            display_names[("twitter", source_id)] = "Twitter Profile"
        for source_id in sources_by_type.get("website", []):
            display_names[("website", source_id)] = "Website"

        # Bulk fetch Document
        if "document" in sources_by_type:
            stmt = select(Document.id, Document.filename).where(
                Document.id.in_(sources_by_type["document"])
            )
            result = await session.execute(stmt)
            for source_id, filename in result:
                display_names[("document", source_id)] = filename or "Document"

        # Bulk fetch YouTube
        if "youtube" in sources_by_type:
            stmt = select(YouTubeVideo.id, YouTubeVideo.title).where(
                YouTubeVideo.id.in_(sources_by_type["youtube"])
            )
            result = await session.execute(stmt)
            for source_id, title in result:
                display_names[("youtube", source_id)] = title or "YouTube Video"

        return display_names

    @staticmethod
    async def _get_source_embeddings_count(session: AsyncSession, source_record_id: UUID) -> int:
        """
        Get count of embeddings for a specific source.

        Args:
            session: Database session
            source_record_id: Source record UUID

        Returns:
            Count of embeddings
        """
        stmt = (
            select(func.count())
            .select_from(VoyageLiteEmbedding)
            .where(VoyageLiteEmbedding.source_record_id == source_record_id)
        )
        return (await session.execute(stmt)).scalar() or 0

    @staticmethod
    async def _get_source_display_name(
        session: AsyncSession, source_type: str, source_record_id: UUID
    ) -> str:
        """
        Get display name for a source based on type.

        Args:
            session: Database session
            source_type: Type of source (linkedin, twitter, website, document, youtube)
            source_record_id: Source record UUID

        Returns:
            Display name for the source
        """
        if source_type == "linkedin":
            # LinkedIn tables have been removed
            return "LinkedIn Profile"

        elif source_type == "twitter":
            # Twitter tables have been removed
            return "Twitter Profile"

        elif source_type == "website":
            # Website tables have been removed
            return "Website"

        elif source_type == "document":
            stmt = select(Document.filename).where(Document.id == source_record_id)
            filename = (await session.execute(stmt)).scalar_one_or_none()
            return filename or "Document"

        elif source_type == "youtube":
            stmt = select(YouTubeVideo.title).where(YouTubeVideo.id == source_record_id)
            title = (await session.execute(stmt)).scalar_one_or_none()
            return title or "YouTube Video"

        return f"{source_type.capitalize()} Source"
