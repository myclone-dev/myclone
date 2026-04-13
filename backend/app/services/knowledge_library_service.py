"""
Knowledge Library Service - Business logic for knowledge library management

This service handles:
- Fetching user's knowledge sources
- Aggregating metadata and statistics
- Managing persona-knowledge relationships
- CRUD operations for knowledge sources
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.database import Persona, async_session_maker
from shared.database.models.document import Document
from shared.database.models.embeddings import VoyageLiteEmbedding

# NOTE: Using VoyageLiteEmbedding (data_llamalite_embeddings table, 512 dims, Voyage AI)
from shared.database.models.persona_data_source import PersonaDataSource
from shared.database.models.youtube import YouTubeVideo
from shared.schemas.knowledge_library import (
    AvailableKnowledgeSource,
    AvailableKnowledgeSourcesResponse,
    DocumentKnowledgeSource,
    KnowledgeLibraryResponse,
    KnowledgeSourceAttachment,
    LinkedInKnowledgeSource,
    PersonaKnowledgeSource,
    TwitterKnowledgeSource,
    WebsiteKnowledgeSource,
    YouTubeKnowledgeSource,
)

logger = logging.getLogger(__name__)


class KnowledgeLibraryService:
    """Service for knowledge library operations"""

    # ========================================================================
    # Get User's Knowledge Library
    # ========================================================================

    async def get_user_knowledge_library(self, user_id: UUID) -> KnowledgeLibraryResponse:
        """
        Get all knowledge sources for a user, grouped by type.

        Args:
            user_id: User UUID

        Returns:
            KnowledgeLibraryResponse with all sources grouped by type
        """
        async with async_session_maker() as session:
            # Fetch all source types in parallel
            linkedin_sources = await self._get_linkedin_sources(session, user_id)
            twitter_sources = await self._get_twitter_sources(session, user_id)
            website_sources = await self._get_website_sources(session, user_id)
            document_sources = await self._get_document_sources(session, user_id)
            youtube_sources = await self._get_youtube_sources(session, user_id)

            # Calculate totals
            total_sources = (
                len(linkedin_sources)
                + len(twitter_sources)
                + len(website_sources)
                + len(document_sources)
                + len(youtube_sources)
            )

            total_embeddings = sum(
                s.embeddings_count
                for sources_list in [
                    linkedin_sources,
                    twitter_sources,
                    website_sources,
                    document_sources,
                    youtube_sources,
                ]
                for s in sources_list
            )

            return KnowledgeLibraryResponse(
                linkedin=linkedin_sources,
                twitter=twitter_sources,
                websites=website_sources,
                documents=document_sources,
                youtube=youtube_sources,
                total_sources=total_sources,
                total_embeddings=total_embeddings,
            )

    # ========================================================================
    # Platform-Specific Fetchers
    # ========================================================================

    async def _get_linkedin_sources(
        self, session: AsyncSession, user_id: UUID
    ) -> List[LinkedInKnowledgeSource]:
        """LinkedIn scraping infrastructure has been removed; always returns empty list."""
        return []

    async def _get_twitter_sources(
        self, session: AsyncSession, user_id: UUID
    ) -> List[TwitterKnowledgeSource]:
        """Twitter scraping infrastructure has been removed; always returns empty list."""
        return []

    async def _get_website_sources(
        self, session: AsyncSession, user_id: UUID
    ) -> List[WebsiteKnowledgeSource]:
        """Website scraping infrastructure has been removed; always returns empty list."""
        return []

    async def _get_document_sources(
        self, session: AsyncSession, user_id: UUID
    ) -> List[DocumentKnowledgeSource]:
        """Get documents for user with metadata"""
        stmt = select(Document).where(Document.user_id == user_id)
        result = await session.execute(stmt)
        documents = result.scalars().all()

        sources = []
        for doc in documents:
            # Count embeddings
            embeddings_count = await self._get_source_embeddings_count(session, doc.id)

            # Count personas using this source
            personas_count = await self._get_personas_using_source_count(session, doc.id)

            sources.append(
                DocumentKnowledgeSource(
                    id=doc.id,
                    display_name=doc.filename,
                    filename=doc.filename,
                    document_type=doc.document_type,
                    file_size=doc.file_size,
                    page_count=doc.page_count,
                    sheet_count=doc.sheet_count,
                    slide_count=doc.slide_count,
                    embeddings_count=embeddings_count,
                    used_by_personas_count=personas_count,
                    uploaded_at=doc.uploaded_at,
                    created_at=doc.created_at,
                    updated_at=doc.updated_at,
                )
            )

        return sources

    async def _get_youtube_sources(
        self, session: AsyncSession, user_id: UUID
    ) -> List[YouTubeKnowledgeSource]:
        """Get YouTube videos for user with metadata"""
        stmt = select(YouTubeVideo).where(YouTubeVideo.user_id == user_id)
        result = await session.execute(stmt)
        videos = result.scalars().all()

        sources = []
        for video in videos:
            # Count embeddings
            embeddings_count = await self._get_source_embeddings_count(session, video.id)

            # Count personas using this source
            personas_count = await self._get_personas_using_source_count(session, video.id)

            # Check if transcript exists by checking if embeddings were created
            # Transcripts are stored as embeddings in data_llamalite_embeddings, not in youtube_videos table
            has_transcript = embeddings_count > 0

            sources.append(
                YouTubeKnowledgeSource(
                    id=video.id,
                    display_name=video.title,
                    video_id=video.video_id,
                    title=video.title,
                    description=video.description,
                    channel_name=video.channel_name,
                    duration_seconds=video.duration_seconds,
                    has_transcript=has_transcript,
                    embeddings_count=embeddings_count,
                    used_by_personas_count=personas_count,
                    published_at=video.published_at,
                    created_at=video.created_at,
                    updated_at=video.updated_at,
                )
            )

        return sources

    # ========================================================================
    # Helper Methods
    # ========================================================================

    # NOTE: Using VoyageLiteEmbedding directly instead of dynamic provider selection.
    # The _get_embedding_model() method is deprecated.
    # def _get_embedding_model(self):
    #     settings = get_settings()
    #     if settings.embedding_provider == "voyage":
    #         return VoyageLiteEmbedding
    #     return VoyageLiteEmbedding

    async def _get_source_embeddings_count(
        self, session: AsyncSession, source_record_id: UUID
    ) -> int:
        """Get count of embeddings for a specific source"""
        stmt = (
            select(func.count())
            .select_from(VoyageLiteEmbedding)
            .where(VoyageLiteEmbedding.source_record_id == source_record_id)
        )
        return (await session.execute(stmt)).scalar() or 0

    async def _get_linkedin_embeddings_count(self, session: AsyncSession, user_id: UUID) -> int:
        """
        Get count of ALL LinkedIn embeddings for a user.

        LinkedIn embeddings include:
        - Profile info (source='linkedin_profile')
        - Posts (source='linkedin_post')
        - Experiences (source='linkedin_experience')
        - Skills, etc.

        All have source starting with 'linkedin_' prefix.
        """
        stmt = (
            select(func.count())
            .select_from(VoyageLiteEmbedding)
            .where(
                VoyageLiteEmbedding.user_id == user_id,
                VoyageLiteEmbedding.source.like("linkedin_%"),
            )
        )
        return (await session.execute(stmt)).scalar() or 0

    async def _get_twitter_embeddings_count(self, session: AsyncSession, user_id: UUID) -> int:
        """
        Get count of ALL Twitter embeddings for a user.

        Twitter embeddings include:
        - Profile bio (source='twitter_profile')
        - Tweets (source='twitter_tweet')

        All have source starting with 'twitter_' prefix.
        """
        stmt = (
            select(func.count())
            .select_from(VoyageLiteEmbedding)
            .where(
                VoyageLiteEmbedding.user_id == user_id,
                VoyageLiteEmbedding.source.like("twitter_%"),
            )
        )
        return (await session.execute(stmt)).scalar() or 0

    async def _get_personas_using_source_count(
        self, session: AsyncSession, source_record_id: UUID
    ) -> int:
        """Get count of personas using this source"""
        stmt = (
            select(func.count())
            .select_from(PersonaDataSource)
            .where(PersonaDataSource.source_record_id == source_record_id)
        )
        return (await session.execute(stmt)).scalar() or 0

    async def get_personas_using_source(self, source_record_id: UUID) -> List[Dict[str, Any]]:
        """Get list of personas using a specific source"""
        async with async_session_maker() as session:
            stmt = (
                select(Persona, PersonaDataSource)
                .join(PersonaDataSource, Persona.id == PersonaDataSource.persona_id)
                .where(PersonaDataSource.source_record_id == source_record_id)
            )
            result = await session.execute(stmt)
            rows = result.all()

            personas = []
            for persona, pds in rows:
                personas.append(
                    {
                        "id": str(persona.id),
                        "persona_name": persona.persona_name,
                        "name": persona.name,
                        "enabled": pds.enabled,
                        "attached_at": pds.created_at,
                    }
                )

            return personas

    # ========================================================================
    # Persona Knowledge Management
    # ========================================================================

    async def get_persona_knowledge_sources(self, persona_id: UUID) -> List[PersonaKnowledgeSource]:
        """
        Get all knowledge sources attached to a persona.

        Delegates to PersonaKnowledgeRepository for data access.
        """
        from shared.database.repositories.persona_knowledge_repository import (
            PersonaKnowledgeRepository,
        )

        async with async_session_maker() as session:
            return await PersonaKnowledgeRepository.get_persona_knowledge_sources(
                session, persona_id
            )

    async def attach_sources_to_persona(
        self, persona_id: UUID, sources: List[KnowledgeSourceAttachment]
    ) -> List[PersonaDataSource]:
        """Attach multiple knowledge sources to a persona"""
        async with async_session_maker() as session:
            created_sources = []

            for source in sources:
                # Check if already attached
                check_stmt = select(PersonaDataSource).where(
                    PersonaDataSource.persona_id == persona_id,
                    PersonaDataSource.source_type == source.source_type,
                    PersonaDataSource.source_record_id == source.source_record_id,
                )
                existing = (await session.execute(check_stmt)).scalar_one_or_none()

                if existing:
                    # Already attached, just enable it if disabled
                    if not existing.enabled:
                        existing.enabled = True
                        existing.enabled_at = datetime.now(timezone.utc)
                        existing.disabled_at = None
                        created_sources.append(existing)
                else:
                    # Create new attachment
                    new_source = PersonaDataSource(
                        persona_id=persona_id,
                        source_type=source.source_type,
                        source_record_id=source.source_record_id,
                        enabled=True,
                        enabled_at=datetime.now(timezone.utc),
                    )
                    session.add(new_source)
                    created_sources.append(new_source)

            await session.commit()
            return created_sources

    async def detach_source_from_persona(self, persona_id: UUID, source_record_id: UUID) -> bool:
        """Remove a knowledge source from persona"""
        async with async_session_maker() as session:
            stmt = delete(PersonaDataSource).where(
                PersonaDataSource.persona_id == persona_id,
                PersonaDataSource.source_record_id == source_record_id,
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def toggle_source(self, persona_id: UUID, source_record_id: UUID) -> bool:
        """Toggle enabled state of a knowledge source"""
        async with async_session_maker() as session:
            stmt = select(PersonaDataSource).where(
                PersonaDataSource.persona_id == persona_id,
                PersonaDataSource.source_record_id == source_record_id,
            )
            source = (await session.execute(stmt)).scalar_one_or_none()

            if not source:
                return False

            # Toggle enabled state
            source.enabled = not source.enabled
            if source.enabled:
                source.enabled_at = datetime.now(timezone.utc)
                source.disabled_at = None
            else:
                source.disabled_at = datetime.now(timezone.utc)

            await session.commit()
            return True

    # ========================================================================
    # Available Sources for Persona
    # ========================================================================

    async def get_available_knowledge_sources(
        self, persona_id: UUID
    ) -> AvailableKnowledgeSourcesResponse:
        """Get all available knowledge sources for a persona (user's library)"""
        async with async_session_maker() as session:
            # Get persona to find user_id
            persona_stmt = select(Persona).where(Persona.id == persona_id)
            persona = (await session.execute(persona_stmt)).scalar_one_or_none()

            if not persona:
                raise ValueError(f"Persona {persona_id} not found")

            user_id = persona.user_id

            # Get all user's knowledge sources
            library = await self.get_user_knowledge_library(user_id)

            # Get currently attached sources
            attached_stmt = select(PersonaDataSource).where(
                PersonaDataSource.persona_id == persona_id
            )
            attached_result = await session.execute(attached_stmt)
            attached_sources = attached_result.scalars().all()

            # Create lookup dict for attached sources
            attached_lookup = {
                (pds.source_type, pds.source_record_id): pds for pds in attached_sources
            }

            # Build available sources list
            available = []

            # LinkedIn
            for source in library.linkedin:
                key = ("linkedin", source.id)
                pds = attached_lookup.get(key)
                available.append(
                    AvailableKnowledgeSource(
                        source_type="linkedin",
                        source_record_id=source.id,
                        display_name=source.display_name,
                        embeddings_count=source.embeddings_count,
                        is_attached=pds is not None,
                        is_enabled=pds.enabled if pds else False,
                        metadata={
                            "headline": source.headline,
                            "posts_count": source.posts_count,
                            "experiences_count": source.experiences_count,
                        },
                    )
                )

            # Twitter
            for source in library.twitter:
                key = ("twitter", source.id)
                pds = attached_lookup.get(key)
                available.append(
                    AvailableKnowledgeSource(
                        source_type="twitter",
                        source_record_id=source.id,
                        display_name=source.display_name,
                        embeddings_count=source.embeddings_count,
                        is_attached=pds is not None,
                        is_enabled=pds.enabled if pds else False,
                        metadata={
                            "username": source.username,
                            "tweets_count": source.tweets_count,
                        },
                    )
                )

            # Websites
            for source in library.websites:
                key = ("website", source.id)
                pds = attached_lookup.get(key)
                available.append(
                    AvailableKnowledgeSource(
                        source_type="website",
                        source_record_id=source.id,
                        display_name=source.display_name,
                        embeddings_count=source.embeddings_count,
                        is_attached=pds is not None,
                        is_enabled=pds.enabled if pds else False,
                        metadata={
                            "website_url": source.website_url,
                            "pages_crawled": source.pages_crawled,
                        },
                    )
                )

            # Documents
            for source in library.documents:
                key = ("document", source.id)
                pds = attached_lookup.get(key)
                available.append(
                    AvailableKnowledgeSource(
                        source_type="document",
                        source_record_id=source.id,
                        display_name=source.display_name,
                        embeddings_count=source.embeddings_count,
                        is_attached=pds is not None,
                        is_enabled=pds.enabled if pds else False,
                        metadata={
                            "filename": source.filename,
                            "document_type": source.document_type,
                            "page_count": source.page_count,
                        },
                    )
                )

            # YouTube
            for source in library.youtube:
                key = ("youtube", source.id)
                pds = attached_lookup.get(key)
                available.append(
                    AvailableKnowledgeSource(
                        source_type="youtube",
                        source_record_id=source.id,
                        display_name=source.display_name,
                        embeddings_count=source.embeddings_count,
                        is_attached=pds is not None,
                        is_enabled=pds.enabled if pds else False,
                        metadata={
                            "video_id": source.video_id,
                            "channel_name": source.channel_name,
                        },
                    )
                )

            already_attached = sum(1 for s in available if s.is_attached)

            return AvailableKnowledgeSourcesResponse(
                persona_id=persona_id,
                user_id=user_id,
                available_sources=available,
                total_available=len(available),
                already_attached=already_attached,
            )

    # ========================================================================
    # Ownership Verification
    # ========================================================================

    async def get_source_owner_id(self, source_type: str, source_record_id: UUID) -> Optional[UUID]:
        """
        Get the user_id who owns a knowledge source.

        Args:
            source_type: Type of source (linkedin, twitter, website, document, youtube)
            source_record_id: Source record UUID

        Returns:
            User ID if source exists, None otherwise
        """
        async with async_session_maker() as session:
            if source_type in ("linkedin", "twitter", "website"):
                # These tables have been removed along with scraping infrastructure
                return None
            elif source_type == "document":
                stmt = select(Document.user_id).where(Document.id == source_record_id)
            elif source_type == "youtube":
                stmt = select(YouTubeVideo.user_id).where(YouTubeVideo.id == source_record_id)
            else:
                return None

            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    # ========================================================================
    # Delete Knowledge Source
    # ========================================================================

    async def delete_knowledge_source(
        self, source_type: str, source_record_id: UUID, user_id: UUID
    ) -> Tuple[int, int]:
        """
        Delete a knowledge source and all its embeddings.

        Args:
            source_type: Type of source (linkedin, twitter, website, document, youtube)
            source_record_id: Source record UUID
            user_id: User ID (for multi-persona safety - only delete user's own data)

        Returns:
            Tuple of (embeddings_deleted, personas_affected)
        """
        async with async_session_maker() as session:
            # Count personas using this source before deletion
            personas_stmt = (
                select(func.count())
                .select_from(PersonaDataSource)
                .where(
                    PersonaDataSource.source_record_id == source_record_id,
                    PersonaDataSource.source_type == source_type,  # Add source_type filtering
                )
            )
            personas_affected = (await session.execute(personas_stmt)).scalar() or 0

            # Delete from persona_data_sources (with source_type filter)
            delete_pds_stmt = delete(PersonaDataSource).where(
                PersonaDataSource.source_record_id == source_record_id,
                PersonaDataSource.source_type == source_type,  # Add source_type filtering
            )
            await session.execute(delete_pds_stmt)

            # Count embeddings before deletion (filter by user_id for safety)
            count_stmt = (
                select(func.count())
                .select_from(VoyageLiteEmbedding)
                .where(
                    VoyageLiteEmbedding.source_record_id == source_record_id,
                    VoyageLiteEmbedding.user_id == user_id,  # Only delete user's own embeddings
                )
            )
            embeddings_count = (await session.execute(count_stmt)).scalar() or 0

            # Delete embeddings (filter by user_id for multi-persona safety)
            delete_emb_stmt = delete(VoyageLiteEmbedding).where(
                VoyageLiteEmbedding.source_record_id == source_record_id,
                VoyageLiteEmbedding.user_id == user_id,  # Only delete user's own embeddings
            )
            await session.execute(delete_emb_stmt)

            # Delete the source record itself
            if source_type in ("linkedin", "twitter", "website"):
                # These tables have been removed along with scraping infrastructure; nothing to delete
                pass
            elif source_type == "document":
                await session.execute(delete(Document).where(Document.id == source_record_id))
            elif source_type == "youtube":
                await session.execute(
                    delete(YouTubeVideo).where(YouTubeVideo.id == source_record_id)
                )

            await session.commit()

            return embeddings_count, personas_affected


# ============================================================================
# Singleton Instance
# ============================================================================

_knowledge_library_service: Optional[KnowledgeLibraryService] = None


def get_knowledge_library_service() -> KnowledgeLibraryService:
    """Get singleton knowledge library service instance"""
    global _knowledge_library_service
    if _knowledge_library_service is None:
        _knowledge_library_service = KnowledgeLibraryService()
    return _knowledge_library_service
