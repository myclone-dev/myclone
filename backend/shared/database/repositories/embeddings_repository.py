"""
Embeddings Repository - Database operations for embeddings

This repository provides ORM-based queries for the embeddings table.
Uses VoyageLiteEmbedding (data_llamalite_embeddings) for all queries.
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.database import async_session_maker
from shared.database.models.embeddings import VoyageLiteEmbedding

# NOTE: Using VoyageLiteEmbedding (data_llamalite_embeddings table, 512 dims, Voyage AI)

logger = logging.getLogger(__name__)


class EmbeddingsRepository:
    """Repository for embeddings database operations using ORM"""

    async def get_user_embeddings_count(self, user_id: UUID) -> int:
        """
        Get count of embeddings for a user

        Args:
            user_id: User UUID

        Returns:
            Total count of embeddings for this user
        """
        async with async_session_maker() as session:
            return await self.get_user_embeddings_count_with_session(session, user_id)

    async def get_user_embeddings_count_with_session(
        self, session: AsyncSession, user_id: UUID
    ) -> int:
        """
        Get count of embeddings for a user using provided session

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            Total count of embeddings for this user
        """
        try:
            stmt = (
                select(func.count())
                .select_from(VoyageLiteEmbedding)
                .where(VoyageLiteEmbedding.user_id == user_id)
            )
            result = await session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error getting embeddings count for user {user_id}: {e}")
            return 0

    async def get_source_embeddings_count(self, source_record_id: UUID) -> int:
        """
        Get count of embeddings for a specific source record

        Args:
            source_record_id: Source record UUID

        Returns:
            Total count of embeddings for this source
        """
        async with async_session_maker() as session:
            try:
                stmt = (
                    select(func.count())
                    .select_from(VoyageLiteEmbedding)
                    .where(VoyageLiteEmbedding.source_record_id == source_record_id)
                )
                result = await session.execute(stmt)
                return result.scalar() or 0
            except Exception as e:
                logger.error(f"Error getting embeddings count for source {source_record_id}: {e}")
                return 0

    async def get_user_source_embeddings_count(self, user_id: UUID, source: str) -> int:
        """
        Get count of embeddings for a user from a specific source platform

        Args:
            user_id: User UUID
            source: Source platform (linkedin, twitter, website, document)

        Returns:
            Total count of embeddings for this user + source combination
        """
        async with async_session_maker() as session:
            try:
                stmt = (
                    select(func.count())
                    .select_from(VoyageLiteEmbedding)
                    .where(
                        VoyageLiteEmbedding.user_id == user_id,
                        VoyageLiteEmbedding.source == source,
                    )
                )
                result = await session.execute(stmt)
                return result.scalar() or 0
            except Exception as e:
                logger.error(
                    f"Error getting embeddings count for user {user_id}, source {source}: {e}"
                )
                return 0


# Singleton instance
_embeddings_repository: Optional[EmbeddingsRepository] = None


def get_embeddings_repository() -> EmbeddingsRepository:
    """Get singleton embeddings repository instance"""
    global _embeddings_repository
    if _embeddings_repository is None:
        _embeddings_repository = EmbeddingsRepository()
    return _embeddings_repository
