"""YouTube ingestion handler for voice processing worker."""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from utils.progress import ProgressTracker

from shared.database.models.database import Persona
from shared.database.models.persona_data_source import PersonaDataSource
from shared.database.models.youtube import YouTubeVideo
from shared.database.voice_job_model import async_session_maker
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.rag.rag_singleton import get_rag_system
from shared.voice_processing.errors import ErrorCode, VoiceProcessingError
from shared.voice_processing.models import JobRequest, JobResult, ProcessingStage

from .youtube_service import YouTubeService


async def process_youtube_ingestion(
    request: JobRequest, progress_tracker: ProgressTracker, persona_id: Optional[str]
) -> JobResult:
    """Process YouTube video ingestion for transcript extraction and persona training.

    This method:
    1. Extracts video metadata and transcript from YouTube
    2. Chunks the transcript into semantic segments with OpenAI-generated summaries and keywords
    3. Stores video metadata in YouTubeVideo table
    4. Uses RAG system to create embeddings (same pattern as ScrapingWorker)
    5. Links video to persona via PersonaDataSource

    Args:
        request: Job request with YouTube URL
        progress_tracker: Progress tracking callback
        persona_id: Optional persona ID (if None, uses 'default' persona)

    Returns:
        Job result with processing information
    """
    start_time = time.time()
    video_id = None

    try:
        # Validate user_id early
        user_id = request.user_id
        if not user_id:
            raise VoiceProcessingError(
                message="user_id is required for YouTube ingestion",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        logger.info(f"🎬 Starting YouTube video ingestion: {request.input_source}")
        logger.info("👤 Job started for User ID")
        logger.info(f"🎭 Persona ID: {persona_id or 'Using default persona'}")

        # Step 1: Initialize YouTube extractor
        progress_tracker.start_stage(ProcessingStage.VALIDATION, "Initializing YouTube processing")
        youtube_service = YouTubeService()

        # Step 2: Extract video metadata and transcript with OpenAI enrichment
        progress_tracker.update_progress(10, "Extracting video metadata and transcript")
        logger.info("📥 Extracting video metadata and transcript...")

        enriched_chunks, metadata = await youtube_service.process_video(
            youtube_url=request.input_source,
            keep_audio=False,
            min_chunk_tokens=400,
            max_chunk_tokens=800,
            target_chunk_duration=45.0,
        )

        if not enriched_chunks:
            raise VoiceProcessingError(
                message="No transcript content could be extracted from the YouTube video",
                error_code=ErrorCode.PROCESSING_ERROR,
            )

        video_id = metadata.get("video_id")
        logger.info(
            f"✅ Extracted {len(enriched_chunks)} chunks from video: {metadata.get('title', 'Unknown')}"
        )
        logger.info(
            f"📹 Video ID: {video_id}, Channel: {metadata.get('channel', 'Unknown')}, Duration: {metadata.get('duration', 0)}s"
        )

        progress_tracker.update_progress(30, f"Extracted {len(enriched_chunks)} chunks from video")

        # Step 3: Store video metadata and create persona links
        # Extract youtube_video_id from request metadata (created by API endpoint)
        youtube_video_id_from_request = (
            UUID(request.metadata.get("youtube_video_id"))
            if request.metadata and request.metadata.get("youtube_video_id")
            else None
        )

        resolved_persona_id, youtube_video_id = await _store_youtube_metadata(
            user_id=user_id,
            persona_id=persona_id,
            metadata=metadata,
            video_id=video_id,
            request_input_source=request.input_source,
            progress_tracker=progress_tracker,
            youtube_video_id_from_request=youtube_video_id_from_request,
        )

        # Step 4: Prepare content sources for RAG ingestion
        content_sources = _prepare_youtube_content_sources(
            enriched_chunks=enriched_chunks,
            metadata=metadata,
            youtube_video_id=youtube_video_id,
            video_id=video_id,
        )

        progress_tracker.update_progress(
            80, f"Ingesting {len(content_sources)} chunks to RAG system"
        )

        # Step 5: Ingest to RAG using the same pattern as ScrapingWorker
        result = await _ingest_youtube_to_rag(
            user_id=user_id,
            persona_id=resolved_persona_id,
            content_sources=content_sources,
        )

        chunks_added = result.get("chunks_added", 0)
        logger.info(
            f"✅ RAG ingestion completed for YouTube video: "
            f"persona_id={resolved_persona_id}, "
            f"chunks_added={chunks_added}, "
            f"status={result.get('status', 'unknown')}"
        )

        progress_tracker.update_progress(95, "Ingested chunks into RAG")
        logger.info("✅ RAG ingestion completed")

        processing_time = time.time() - start_time
        logger.info(
            f"✅ YouTube video ingestion completed successfully in {processing_time:.2f}s: "
            f"{len(enriched_chunks)} chunks, {chunks_added} embeddings created"
        )

        progress_tracker.update_progress(100, "YouTube video ingestion completed successfully")

        # ===== REFRESH USAGE CACHE AFTER SUCCESSFUL YOUTUBE INGESTION =====
        # Recalculate usage from YouTubeVideo table to ensure accurate limits
        try:
            logger.info(f"🔄 Refreshing usage cache for user {user_id} after YouTube ingestion")
            from shared.database.voice_job_model import async_session_maker
            from shared.services.usage_cache_service import UsageCacheService

            async with async_session_maker() as session:
                usage_cache_service = UsageCacheService(session)
                # Refresh specifically YouTube usage
                await usage_cache_service.recalculate_usage_from_source(
                    user_id=user_id, file_type_category="youtube"
                )
                await session.commit()
                logger.info(f"✅ Usage cache refreshed for user {user_id} (YouTube)")
        except Exception as cache_error:
            # Non-critical error - log warning but don't fail the job
            logger.warning(f"⚠️ Failed to refresh usage cache: {cache_error}")
        # ===== END USAGE CACHE REFRESH =====

        return JobResult(
            success=True,
            processing_time_seconds=processing_time,
            input_info={
                "source": "youtube",
                "video_id": video_id,
                "title": metadata.get("title", ""),
                "channel": metadata.get("channel", ""),
                "duration": metadata.get("duration", 0),
                "view_count": metadata.get("view_count", 0),
                "url": metadata.get("url", request.input_source),
            },
            transcript_text=f"Processed {len(enriched_chunks)} chunks with {chunks_added} embeddings created",
            transcript_segments=[
                {
                    "chunk_index": i,
                    "start_time": chunk["start_time"],
                    "end_time": chunk["end_time"],
                    "text_preview": (
                        chunk["text"][:100] + "..." if len(chunk["text"]) > 100 else chunk["text"]
                    ),
                    "token_count": chunk["token_count"],
                    "summary": chunk["summary"],
                    "keywords": chunk["keywords"][:3],  # Show first 3 keywords
                }
                for i, chunk in enumerate(enriched_chunks[:5])
            ],  # First 5 chunks as preview
        )

    except Exception as e:
        processing_time = time.time() - start_time

        logger.error(f"YouTube ingestion failed: {e}")

        # Capture exception in Sentry with full context
        capture_exception_with_context(
            e,
            extra={
                "input_source": request.input_source,
                "video_id": video_id,
                "persona_id": str(persona_id) if persona_id else None,
                "user_id": str(request.user_id) if request.user_id else None,
            },
            tags={
                "component": "voice_worker",
                "operation": "youtube_ingestion",
                "parser_type": "youtube_handler",
                "severity": "high",
            },
        )

        if isinstance(e, VoiceProcessingError):
            return JobResult(
                success=False,
                processing_time_seconds=processing_time,
                input_info={"source": "youtube", "url": request.input_source},
                error_code=e.error_code.value,
                error_message=e.message,
                error_suggestions=e.suggestions,
            )
        else:
            return JobResult(
                success=False,
                processing_time_seconds=processing_time,
                input_info={"source": "youtube", "url": request.input_source},
                error_code="youtube_ingestion_error",
                error_message=str(e),
                error_suggestions=[
                    "Check YouTube URL is valid and accessible",
                    "Ensure video has English transcripts or captions",
                    "Verify OpenAI API key is configured for summary generation",
                    "Verify AssemblyAI API key is configured if no transcript available",
                    "Try again later",
                ],
            )


async def _store_youtube_metadata(
    user_id: UUID,
    persona_id: Optional[str],
    metadata: Dict,
    video_id: str,
    request_input_source: str,
    progress_tracker: ProgressTracker,
    youtube_video_id_from_request: Optional[UUID] = None,
) -> tuple[UUID, UUID]:
    """Store YouTube video metadata and create persona links.

    Args:
        user_id: User UUID
        persona_id: Optional persona ID
        metadata: Video metadata
        video_id: YouTube video ID
        request_input_source: Original request URL
        progress_tracker: Progress tracker
        youtube_video_id_from_request: Optional YouTubeVideo UUID created by API endpoint

    Returns:
        Tuple of (resolved_persona_id, youtube_video_id)
    """
    resolved_persona_id = persona_id
    youtube_video_id = None

    async with async_session_maker() as session:
        # ===== TIER LIMIT CHECK =====
        # Check tier limits before updating video metadata
        from shared.services.tier_service import TierLimitExceeded, TierService

        video_duration_seconds = metadata.get("duration", 0)

        tier_service = TierService(session)
        try:
            await tier_service.check_youtube_ingest_allowed(
                user_id=user_id, video_duration_seconds=video_duration_seconds
            )
            logger.info(
                f"✅ Tier limit check passed for user {user_id}: "
                f"duration={video_duration_seconds}s ({video_duration_seconds/60:.1f} min)"
            )
        except TierLimitExceeded as e:
            logger.error(f"❌ Tier limit exceeded for user {user_id}: {e}")
            raise VoiceProcessingError(
                message=str(e),
                error_code=ErrorCode.VALIDATION_ERROR,
            )
        # ===== END TIER LIMIT CHECK =====

        progress_tracker.update_progress(40, "Updating video metadata in database")

        # Find or create persona
        if resolved_persona_id:
            # Use provided persona_id
            persona_query = select(Persona).where(
                Persona.id == UUID(resolved_persona_id), Persona.user_id == user_id
            )
            persona = (await session.execute(persona_query)).scalar_one_or_none()
            if not persona:
                raise VoiceProcessingError(
                    message=f"Persona with ID {resolved_persona_id} not found for user {user_id}",
                    error_code=ErrorCode.NOT_FOUND,
                )
        else:
            # Find or create 'default' persona
            persona_query = select(Persona).where(
                Persona.user_id == user_id,
                Persona.persona_name == "default",
                Persona.is_active == True,
            )
            persona = (await session.execute(persona_query)).scalar_one_or_none()

            if not persona:
                # Create default persona
                persona = Persona(
                    user_id=user_id,
                    persona_name="default",
                    name="Default Persona",
                    description="Auto-created default persona for YouTube ingestion",
                )
                session.add(persona)
                await session.flush()

        resolved_persona_id = persona.id
        progress_tracker.update_progress(50, f"Using persona: {persona.name}")

        # Find existing video (should have been created by API endpoint)
        existing_video = None

        if youtube_video_id_from_request:
            # Use the UUID provided by the API endpoint (preferred)
            existing_video_query = select(YouTubeVideo).where(
                YouTubeVideo.id == youtube_video_id_from_request
            )
            existing_video = (await session.execute(existing_video_query)).scalar_one_or_none()
            if existing_video:
                logger.info(
                    f"Found YouTubeVideo by ID from request: {youtube_video_id_from_request}"
                )

        if not existing_video:
            # Fallback: lookup by video_id and user_id
            existing_video_query = select(YouTubeVideo).where(
                YouTubeVideo.video_id == video_id, YouTubeVideo.user_id == user_id
            )
            existing_video = (await session.execute(existing_video_query)).scalar_one_or_none()
            if existing_video:
                logger.info(f"Found YouTubeVideo by video_id and user_id: {video_id}")

        if existing_video:
            # Update existing video with full metadata
            youtube_video = existing_video
            logger.info(f"Updating existing YouTubeVideo {youtube_video.id} with full metadata")

            # Parse published_at
            published_at = None
            if metadata.get("published_at"):
                try:
                    published_at = datetime.fromisoformat(
                        metadata["published_at"].replace("Z", "+00:00")
                    )
                except:
                    pass

            # Update all fields
            youtube_video.title = metadata.get("title", "")
            youtube_video.description = metadata.get("description", "")
            youtube_video.video_url = metadata.get("url", request_input_source)
            youtube_video.thumbnail_url = metadata.get("thumbnail", "")
            youtube_video.duration_seconds = metadata.get("duration", 0)
            youtube_video.view_count = metadata.get("view_count", 0)
            youtube_video.channel_name = metadata.get("channel", "")
            youtube_video.channel_url = (
                f"https://www.youtube.com/channel/{metadata.get('channel_id', '')}"
                if metadata.get("channel_id")
                else None
            )
            youtube_video.published_at = published_at

            await session.flush()
        else:
            # Fallback: Create new video if it doesn't exist (shouldn't happen normally)
            logger.warning(
                f"YouTubeVideo not found for video_id={video_id}, user_id={user_id}. "
                "Creating new entry (this should have been created by API endpoint)."
            )

            published_at = None
            if metadata.get("published_at"):
                try:
                    published_at = datetime.fromisoformat(
                        metadata["published_at"].replace("Z", "+00:00")
                    )
                except:
                    pass

            youtube_video = YouTubeVideo(
                user_id=user_id,
                video_id=video_id,
                title=metadata.get("title", ""),
                description=metadata.get("description", ""),
                video_url=metadata.get("url", request_input_source),
                thumbnail_url=metadata.get("thumbnail", ""),
                duration_seconds=metadata.get("duration", 0),
                view_count=metadata.get("view_count", 0),
                channel_name=metadata.get("channel", ""),
                channel_url=(
                    f"https://www.youtube.com/channel/{metadata.get('channel_id', '')}"
                    if metadata.get("channel_id")
                    else None
                ),
                published_at=published_at,
            )
            session.add(youtube_video)
            await session.flush()

        youtube_video_id = youtube_video.id
        progress_tracker.update_progress(60, "Creating PersonaDataSource link")

        # Create PersonaDataSource link
        existing_link_query = select(PersonaDataSource).where(
            PersonaDataSource.persona_id == resolved_persona_id,
            PersonaDataSource.source_type == "youtube",
            PersonaDataSource.source_record_id == youtube_video_id,
        )
        existing_link = (await session.execute(existing_link_query)).scalar_one_or_none()

        if not existing_link:
            persona_data_source = PersonaDataSource(
                persona_id=resolved_persona_id,
                source_type="youtube",
                source_record_id=youtube_video_id,
                enabled=True,
                source_filters={},
                enabled_at=datetime.now(timezone.utc),
            )
            session.add(persona_data_source)
            logger.info(f"🔗 Created PersonaDataSource link for persona {resolved_persona_id}")
        else:
            logger.info("♻️  PersonaDataSource link already exists")

        await session.commit()
        logger.info("✅ Database operations completed successfully")

        # ===== STAGE 1: USAGE CACHE UPDATE =====
        # Optimistically update usage cache after YouTube video is committed
        try:
            from shared.services.usage_cache_service import UsageCacheService

            usage_cache_service = UsageCacheService(session)
            await usage_cache_service.increment_youtube_usage_optimistic(
                user_id=user_id,
                duration_seconds=metadata.get("duration", 0),
            )
            await session.commit()
            logger.info(
                f"[Stage 1] Updated usage cache for user {user_id}: "
                f"YouTube video={video_id}, duration={metadata.get('duration', 0)}s"
            )
        except Exception as cache_error:
            # Non-critical error - log and continue
            # Stage 2 will reconcile in worker
            logger.warning(f"Failed to update usage cache (Stage 1) for YouTube: {cache_error}")
            await session.rollback()
        # ===== END STAGE 1 =====

    return resolved_persona_id, youtube_video_id


def _prepare_youtube_content_sources(
    enriched_chunks: List[Dict],
    metadata: Dict,
    youtube_video_id: UUID,
    video_id: str,
) -> List[Dict]:
    """Prepare content sources for RAG ingestion.

    Args:
        enriched_chunks: Enriched transcript chunks
        metadata: Video metadata
        youtube_video_id: UUID of YouTubeVideo record
        video_id: YouTube video ID

    Returns:
        List of content sources ready for RAG ingestion
    """
    content_sources = []
    posted_at = None

    if metadata.get("published_at"):
        try:
            posted_at = datetime.fromisoformat(metadata["published_at"].replace("Z", "+00:00"))
        except:
            pass

    for chunk in enriched_chunks:
        # Use the optimized vectorized text with format: transcript | Summary: ... | Keywords: ...
        vectorized_text = chunk["vectorized_text"]

        # Create metadata for this chunk
        chunk_metadata = {
            # Core identifiers
            "source_record_id": str(youtube_video_id),
            "source": "youtube",
            "source_type": "transcript",
            # Video information
            "video_id": video_id,
            "video_title": metadata.get("title", ""),
            "channel": metadata.get("channel", ""),
            # Chunk timing information
            "chunk_index": chunk["chunk_index"],
            "start_time": chunk["start_time"],
            "end_time": chunk["end_time"],
            "duration": chunk["duration"],
            "timestamp_url": chunk["timestamp_url"],
            # Tags from video metadata
            "tags": metadata.get("tags", []),
            # Posted date for sorting/filtering
            "posted_at": posted_at.isoformat() if posted_at else None,
        }

        content_sources.append(
            {
                "content": vectorized_text,
                "source": "youtube",
                "source_type": "transcript",
                "source_record_id": youtube_video_id,
                "metadata": chunk_metadata,
            }
        )

    return content_sources


async def _ingest_youtube_to_rag(
    user_id: UUID, persona_id: UUID, content_sources: List[Dict]
) -> Dict:
    """Ingest YouTube content to RAG system.

    Args:
        user_id: User UUID
        persona_id: Persona UUID
        content_sources: Prepared content sources

    Returns:
        RAG ingestion result

    Raises:
        VoiceProcessingError: If RAG ingestion fails
    """
    rag = await get_rag_system()

    result = await rag.ingest_persona_data(
        user_id=user_id,
        persona_id=persona_id,
        content_sources=content_sources,
    )

    # Add safety check for None result
    if result is None:
        raise VoiceProcessingError(
            message="RAG ingestion returned None - this may indicate a configuration issue or database problem",
            error_code=ErrorCode.PROCESSING_ERROR,
        )

    return result
