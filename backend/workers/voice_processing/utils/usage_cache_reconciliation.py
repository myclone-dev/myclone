"""
Usage Cache Reconciliation Module for Voice Processing Worker

This module provides Stage 2 usage cache reconciliation after successful job completion.
It should be called by the worker after marking a job as completed.
"""

import logging

logger = logging.getLogger(__name__)


async def reconcile_usage_cache_after_job(
    user_id: str,
    job_type: str,
    job_id: str,
) -> None:
    """
    STAGE 2: Reconcile usage cache after successful job completion

    This function recalculates actual usage from the database and updates
    the user_usage_cache table. This acts as a reconciliation/safety check
    against the optimistic Stage 1 update that happened during upload.

    Args:
        user_id: User UUID string
        job_type: Job type (e.g., 'pdf_parsing', 'audio_transcription', 'youtube_ingestion')
        job_id: Job identifier for logging

    Race condition protection:
    - Uses SELECT ... FOR UPDATE locks inside UsageCacheService
    - Atomic recalculation within transaction
    """
    try:
        from uuid import UUID

        from shared.database.voice_job_model import async_session_maker
        from shared.services.usage_cache_service import UsageCacheService

        # Convert user_id string to UUID
        try:
            user_uuid = UUID(user_id)
        except (ValueError, TypeError):
            logger.warning(f"Invalid user_id format: {user_id}, skipping cache reconciliation")
            return

        async with async_session_maker() as session:
            usage_cache_service = UsageCacheService(session)

            # Map job type to file category for targeted reconciliation
            file_type_category = None

            if job_type == "pdf_parsing":
                file_type_category = "document"
            elif job_type == "audio_transcription":
                file_type_category = "multimedia"
            elif job_type == "video_transcription":
                file_type_category = "multimedia"
            elif job_type == "youtube_ingestion":
                file_type_category = "youtube"
            elif job_type == "text_processing":
                file_type_category = "raw_text"
            else:
                # Unknown job type - recalculate all categories to be safe
                logger.info(f"Unknown job type '{job_type}', recalculating all categories")
                file_type_category = None

            # Recalculate usage from source tables
            updated = await usage_cache_service.recalculate_usage_from_source(
                user_id=user_uuid,
                file_type_category=file_type_category,
            )

            await session.commit()

            logger.info(
                f"[Stage 2] ✅ Reconciled usage cache for user {user_id}, "
                f"category: {file_type_category or 'all'}, job: {job_id}, "
                f"updated: {updated}"
            )

    except Exception as cache_error:
        # Non-critical error - log but don't fail the job
        logger.warning(
            f"[Stage 2] ⚠️ Failed to reconcile usage cache for job {job_id}: {cache_error}",
            exc_info=True,
        )
