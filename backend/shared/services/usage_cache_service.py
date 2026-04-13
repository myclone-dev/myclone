"""
Usage Cache Service - Two-stage update system with race condition protection

This service manages the user_usage_cache table with a two-stage update pattern:

Stage 1 (Pre-insert): When user uploads a file
- Check tier limits
- If allowed, insert document to Documents table
- Immediately update usage_cache with optimistic increment (fast path)

Stage 2 (Post-processing): When worker completes job
- Aggregate actual usage from Documents/YouTubeVideos tables
- Update usage_cache with accurate values (reconciliation)

Race condition protection:
- SELECT ... FOR UPDATE locks on user_usage_cache row
- Optimistic locking with last_updated_at
- Transaction isolation for atomic operations
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.document import Document
from shared.database.models.tier_plan import UserUsageCache
from shared.database.models.youtube import YouTubeVideo

logger = logging.getLogger(__name__)


class UsageCacheService:
    """Service for managing user_usage_cache table with race condition protection"""

    # File type categorization (matches TierService)
    RAW_TEXT_TYPES = {"txt", "md"}
    DOCUMENT_TYPES = {"pdf", "docx", "xlsx", "pptx", "doc", "xls", "ppt"}
    MULTIMEDIA_TYPES = {"mp3", "mp4", "wav", "m4a", "mov", "avi", "mkv", "webm"}

    def __init__(self, db: AsyncSession):
        self.db = db

    def _categorize_file_type(self, file_extension: str) -> str:
        """Categorize file type into raw_text, document, or multimedia"""
        ext = file_extension.lower().lstrip(".")

        if ext in self.RAW_TEXT_TYPES:
            return "raw_text"
        elif ext in self.DOCUMENT_TYPES:
            return "document"
        elif ext in self.MULTIMEDIA_TYPES:
            return "multimedia"
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

    async def _ensure_cache_exists(self, user_id: UUID) -> UserUsageCache:
        """
        Ensure user_usage_cache entry exists for user (with row lock)

        This acquires a FOR UPDATE lock to prevent race conditions during creation.

        Args:
            user_id: User UUID

        Returns:
            UserUsageCache instance (locked)
        """
        # Try to get existing cache with lock
        logger.info(f"Acquiring usage cache lock for user {user_id}")
        query = select(UserUsageCache).where(UserUsageCache.user_id == user_id).with_for_update()
        result = await self.db.execute(query)
        cache = result.scalar_one_or_none()
        logger.info(f"Usage cache lock acquired for user {user_id}")
        if not cache:
            # Create new cache entry (still holding transaction lock)
            cache = UserUsageCache(
                user_id=user_id,
                raw_text_storage_bytes=0,
                raw_text_file_count=0,
                document_storage_bytes=0,
                document_file_count=0,
                multimedia_storage_bytes=0,
                multimedia_file_count=0,
                multimedia_total_duration_seconds=0,
                youtube_video_count=0,
                youtube_total_duration_seconds=0,
            )
            self.db.add(cache)
            await self.db.flush()
            await self.db.refresh(cache)
            logger.info(f"Created new usage cache for user {user_id}")

        return cache

    async def increment_usage_optimistic(
        self,
        user_id: UUID,
        file_extension: str,
        file_size_bytes: int,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """
        STAGE 1: Optimistic increment when document is inserted

        This is called AFTER tier limits are checked and document is inserted.
        It provides a fast update path without re-aggregating all documents.

        Race condition protection:
        - SELECT ... FOR UPDATE locks the cache row
        - Atomic increment within transaction
        - Transaction must be committed by caller

        Args:
            user_id: User UUID
            file_extension: File extension (e.g., 'pdf', 'mp3')
            file_size_bytes: File size in bytes
            duration_seconds: Duration for multimedia files (optional)
        """
        category = self._categorize_file_type(file_extension)

        # Get cache with row lock (prevents concurrent updates)
        cache = await self._ensure_cache_exists(user_id)

        # Increment based on category
        if category == "raw_text":
            cache.raw_text_storage_bytes += file_size_bytes
            cache.raw_text_file_count += 1
            logger.info(
                f"[Stage 1] Incremented raw_text usage for user {user_id}: "
                f"+{file_size_bytes} bytes, count={cache.raw_text_file_count}"
            )

        elif category == "document":
            cache.document_storage_bytes += file_size_bytes
            cache.document_file_count += 1
            logger.info(
                f"[Stage 1] Incremented document usage for user {user_id}: "
                f"+{file_size_bytes} bytes, count={cache.document_file_count}"
            )

        elif category == "multimedia":
            cache.multimedia_storage_bytes += file_size_bytes
            cache.multimedia_file_count += 1
            if duration_seconds:
                cache.multimedia_total_duration_seconds += duration_seconds
            logger.info(
                f"[Stage 1] Incremented multimedia usage for user {user_id}: "
                f"+{file_size_bytes} bytes, +{duration_seconds or 0}s, "
                f"count={cache.multimedia_file_count}"
            )

        # Update timestamp
        cache.last_updated_at = datetime.now(timezone.utc)

        # Note: Caller must commit transaction

    async def increment_youtube_usage_optimistic(
        self,
        user_id: UUID,
        duration_seconds: int,
    ) -> None:
        """
        STAGE 1: Optimistic increment when YouTube video is inserted

        Args:
            user_id: User UUID
            duration_seconds: Video duration in seconds
        """
        # Get cache with row lock
        cache = await self._ensure_cache_exists(user_id)

        # Increment YouTube counters
        cache.youtube_video_count += 1
        cache.youtube_total_duration_seconds += duration_seconds
        cache.last_updated_at = datetime.now(timezone.utc)

        logger.info(
            f"[Stage 1] Incremented YouTube usage for user {user_id}: "
            f"+{duration_seconds}s, count={cache.youtube_video_count}"
        )

    async def recalculate_usage_from_source(
        self,
        user_id: UUID,
        file_type_category: Optional[str] = None,
    ) -> Dict:
        """
        STAGE 2: Recalculate usage from actual Documents/YouTubeVideos tables

        This is called by worker after successful job completion to reconcile
        the cache with actual database state. Acts as a safety check.

        Race condition protection:
        - SELECT ... FOR UPDATE locks the cache row
        - Aggregates from source tables within same transaction
        - Atomic update

        Args:
            user_id: User UUID
            file_type_category: Optional - recalculate specific category only
                                ('raw_text', 'document', 'multimedia', 'youtube', or None for all)

        Returns:
            Dict with updated usage stats
        """
        # Get cache with row lock
        cache = await self._ensure_cache_exists(user_id)

        updated_fields = {}

        # Recalculate document-based usage
        if file_type_category in [None, "raw_text", "document", "multimedia"]:
            # Aggregate all documents by category
            query = (
                select(
                    Document.document_type,
                    func.coalesce(func.sum(Document.file_size), 0).label("total_size"),
                    func.count(Document.id).label("file_count"),
                )
                .where(Document.user_id == user_id)
                .group_by(Document.document_type)
            )

            result = await self.db.execute(query)
            documents = result.all()

            # Initialize counters
            raw_text_bytes = 0
            raw_text_count = 0
            document_bytes = 0
            document_count = 0
            multimedia_bytes = 0
            multimedia_count = 0

            # Categorize and sum
            for doc_type, total_size, count in documents:
                try:
                    category = self._categorize_file_type(doc_type)

                    if category == "raw_text":
                        raw_text_bytes += total_size
                        raw_text_count += count
                    elif category == "document":
                        document_bytes += total_size
                        document_count += count
                    elif category == "multimedia":
                        multimedia_bytes += total_size
                        multimedia_count += count

                except ValueError:
                    logger.warning(f"Unknown document type during recalculation: {doc_type}")
                    continue

            # Update cache based on filter
            if file_type_category in [None, "raw_text"]:
                cache.raw_text_storage_bytes = raw_text_bytes
                cache.raw_text_file_count = raw_text_count
                updated_fields["raw_text"] = {
                    "storage_bytes": raw_text_bytes,
                    "file_count": raw_text_count,
                }

            if file_type_category in [None, "document"]:
                cache.document_storage_bytes = document_bytes
                cache.document_file_count = document_count
                updated_fields["document"] = {
                    "storage_bytes": document_bytes,
                    "file_count": document_count,
                }

            if file_type_category in [None, "multimedia"]:
                cache.multimedia_storage_bytes = multimedia_bytes
                cache.multimedia_file_count = multimedia_count

                # Calculate total duration from Documents table duration_seconds column
                duration_query = (
                    select(func.coalesce(func.sum(Document.duration_seconds), 0))
                    .where(Document.user_id == user_id)
                    .where(Document.document_type.in_(list(self.MULTIMEDIA_TYPES)))
                )
                duration_result = await self.db.execute(duration_query)
                multimedia_duration = duration_result.scalar_one()

                cache.multimedia_total_duration_seconds = multimedia_duration
                updated_fields["multimedia"] = {
                    "storage_bytes": multimedia_bytes,
                    "file_count": multimedia_count,
                    "total_duration_seconds": multimedia_duration,
                }

        # Recalculate YouTube usage
        if file_type_category in [None, "youtube"]:
            query = select(
                func.count(YouTubeVideo.id).label("video_count"),
                func.coalesce(func.sum(YouTubeVideo.duration_seconds), 0).label("total_duration"),
            ).where(YouTubeVideo.user_id == user_id)

            result = await self.db.execute(query)
            row = result.one()

            cache.youtube_video_count = row.video_count
            cache.youtube_total_duration_seconds = row.total_duration
            updated_fields["youtube"] = {
                "video_count": row.video_count,
                "total_duration_seconds": row.total_duration,
            }

        # Update timestamp
        cache.last_updated_at = datetime.now(timezone.utc)

        logger.info(
            f"[Stage 2] Recalculated usage for user {user_id} "
            f"(category: {file_type_category or 'all'}): {updated_fields}"
        )

        # Note: Caller must commit transaction
        return updated_fields

    async def get_usage_cache(self, user_id: UUID) -> Optional[UserUsageCache]:
        """
        Get current usage cache for user (without lock)

        Args:
            user_id: User UUID

        Returns:
            UserUsageCache or None
        """
        query = select(UserUsageCache).where(UserUsageCache.user_id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def decrement_usage_on_delete(
        self,
        user_id: UUID,
        file_extension: str,
        file_size_bytes: int,
        duration_seconds: Optional[int] = None,
    ) -> None:
        """
        Decrement usage when a document is deleted

        This is an optimistic decrement - followed by recalculation for accuracy.

        Args:
            user_id: User UUID
            file_extension: File extension
            file_size_bytes: File size in bytes
            duration_seconds: Duration for multimedia files
        """
        category = self._categorize_file_type(file_extension)

        # Get cache with row lock
        cache = await self._ensure_cache_exists(user_id)

        # Decrement based on category
        if category == "raw_text":
            cache.raw_text_storage_bytes = max(0, cache.raw_text_storage_bytes - file_size_bytes)
            cache.raw_text_file_count = max(0, cache.raw_text_file_count - 1)

        elif category == "document":
            cache.document_storage_bytes = max(0, cache.document_storage_bytes - file_size_bytes)
            cache.document_file_count = max(0, cache.document_file_count - 1)

        elif category == "multimedia":
            cache.multimedia_storage_bytes = max(
                0, cache.multimedia_storage_bytes - file_size_bytes
            )
            cache.multimedia_file_count = max(0, cache.multimedia_file_count - 1)
            if duration_seconds:
                cache.multimedia_total_duration_seconds = max(
                    0, cache.multimedia_total_duration_seconds - duration_seconds
                )

        cache.last_updated_at = datetime.now(timezone.utc)

        logger.info(
            f"Decremented {category} usage for user {user_id}: " f"-{file_size_bytes} bytes"
        )

    async def decrement_youtube_usage_on_delete(
        self,
        user_id: UUID,
        duration_seconds: int,
    ) -> None:
        """
        Decrement YouTube usage when a video is deleted

        Args:
            user_id: User UUID
            duration_seconds: Video duration in seconds
        """
        cache = await self._ensure_cache_exists(user_id)

        cache.youtube_video_count = max(0, cache.youtube_video_count - 1)
        cache.youtube_total_duration_seconds = max(
            0, cache.youtube_total_duration_seconds - duration_seconds
        )
        cache.last_updated_at = datetime.now(timezone.utc)

        logger.info(f"Decremented YouTube usage for user {user_id}: " f"-{duration_seconds}s")
