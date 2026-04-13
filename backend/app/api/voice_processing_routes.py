"""Voice processing API routes"""

import logging
from io import BytesIO
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, field_validator
from sqlalchemy import delete, select

from shared.config import settings
from shared.s3_utils import get_s3_client

# Import from shared voice_processing package
from shared.voice_processing.errors import VoiceProcessingError
from shared.voice_processing.job_service import JobService
from shared.voice_processing.models import JobPriority, JobStatus, JobType

logger = logging.getLogger(__name__)

# Router for voice processing endpoints
router = APIRouter(prefix="/api/v1/voice-processing", tags=["voice-processing"])

# Global job service instance (initialized on startup)
_job_service: Optional[JobService] = None


async def get_job_service() -> JobService:
    """Dependency to get job service instance."""
    if not _job_service:
        raise HTTPException(
            status_code=503,
            detail="Voice processing service not initialized. Check NATS connection.",
        )
    return _job_service


async def initialize_voice_processing():
    """Initialize voice processing service (called from main.py lifespan)."""
    global _job_service

    from shared.config import settings

    _job_service = JobService(settings.nats_url)
    await _job_service.initialize()


async def shutdown_voice_processing():
    """Shutdown voice processing service (called from main.py lifespan)."""
    global _job_service

    if _job_service:
        await _job_service.close()


# Pydantic models for API requests/responses
class CreateJobRequest(BaseModel):
    """Request model for creating a new job."""

    job_type: JobType
    input_source: str
    user_id: Optional[UUID] = None
    priority: JobPriority = JobPriority.NORMAL

    # Voice extraction options
    output_format: str = "wav"  # Always WAV for ElevenLabs (locked to ensure 9MB size prediction)
    profile: str = "elevenlabs"
    multiple_segments: bool = False
    max_segments: int = 3
    normalize_audio: bool = False

    # Manual time range extraction (for multi-speaker videos)
    start_time: Optional[int] = None  # Start time in seconds
    end_time: Optional[int] = None  # End time in seconds

    # Transcript extraction options (for future)
    transcript_language: Optional[str] = None
    include_timestamps: bool = True

    # Processing options
    max_duration_seconds: Optional[int] = None
    webhook_url: Optional[str] = None

    @field_validator("input_source")
    @classmethod
    def validate_input_source(cls, v):
        if not v or not v.strip():
            raise ValueError("input_source cannot be empty")
        return v.strip()

    @field_validator("output_format")
    @classmethod
    def validate_output_format(cls, v):
        # Only WAV is supported for ElevenLabs (9MB size limit requirement)
        if v.lower() != "wav":
            raise ValueError("output_format must be 'wav' (required for ElevenLabs compatibility)")
        return "wav"

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, v, values):
        """Validate that end_time > start_time if both provided."""
        start_time = (
            values.data.get("start_time") if hasattr(values, "data") else values.get("start_time")
        )
        if start_time is not None and v is not None:
            if v <= start_time:
                raise ValueError("end_time must be greater than start_time")
        return v


class JobResponse(BaseModel):
    """Response model for job operations."""

    job_id: str
    status: str
    message: str


class YouTubeIngestRequest(BaseModel):
    """Request model for YouTube video ingestion."""

    youtube_url: str
    user_id: UUID
    persona_id: Optional[UUID] = None
    force: bool = False

    @field_validator("youtube_url")
    @classmethod
    def validate_youtube_url(cls, v):
        if not v or not v.strip():
            raise ValueError("youtube_url cannot be empty")

        # Basic YouTube URL validation
        import re

        youtube_patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([^&\n?#]+)",
            r"youtube\.com\/watch\?.*v=([^&\n?#]+)",
        ]

        if not any(re.search(pattern, v) for pattern in youtube_patterns):
            raise ValueError("Invalid YouTube URL format")

        return v.strip()


@router.get("/health")
async def voice_processing_health():
    """Health check for voice processing service."""
    nats_connected = _job_service is not None and _job_service.nats_client is not None

    return {
        "status": "healthy" if nats_connected else "degraded",
        "nats_connected": nats_connected,
        "service": "voice-processing",
    }


@router.post("/jobs", response_model=JobResponse)
async def create_voice_processing_job(
    request: CreateJobRequest, job_svc: JobService = Depends(get_job_service)
):
    """Create a new voice processing job.

    Supports:
    - Voice extraction from media URLs (YouTube, Apple Podcasts, Spotify, SoundCloud, Vimeo, etc.) or uploaded files
    - Transcript extraction (future)
    - Combined voice + transcript processing (future)

    Note: Apple Podcasts URLs must point to specific episodes (include ?i=<episode_id> parameter)

    Returns immediately with a job ID for async tracking.
    """
    try:
        from shared.voice_processing.models import JobRequest

        # Convert to internal job request
        job_request = JobRequest(
            job_type=request.job_type,
            input_source=request.input_source,
            user_id=request.user_id,
            priority=request.priority,
            output_format=request.output_format,
            profile=request.profile,
            multiple_segments=request.multiple_segments,
            max_segments=request.max_segments,
            normalize_audio=request.normalize_audio,
            start_time=request.start_time,
            end_time=request.end_time,
            transcript_language=request.transcript_language,
            include_timestamps=request.include_timestamps,
            max_duration_seconds=request.max_duration_seconds,
            webhook_url=request.webhook_url,
        )

        # Submit job
        job_id = await job_svc.submit_job(job_request, request.user_id)

        return JobResponse(
            job_id=job_id, status="queued", message="Job created and queued for processing"
        )

    except VoiceProcessingError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": e.message,
                "error_code": e.error_code.value,
                "category": e.category.value,
                "suggestions": e.suggestions,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, job_svc: JobService = Depends(get_job_service)):
    """Get status and progress of a specific voice processing job."""
    try:
        job_data = await job_svc.get_job_status(job_id)

        if not job_data:
            raise HTTPException(status_code=404, detail="Job not found")

        return job_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/jobs/{job_id}/progress")
async def get_job_progress(job_id: str, job_svc: JobService = Depends(get_job_service)):
    """Get real-time progress updates for a job."""
    try:
        progress = await job_svc.get_job_progress(job_id)

        if not progress:
            raise HTTPException(status_code=404, detail="Job not found")

        return progress.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: str, job_svc: JobService = Depends(get_job_service)):
    """Retry a failed voice processing job."""
    try:
        success = await job_svc.retry_job(job_id)

        if not success:
            raise HTTPException(
                status_code=400,
                detail="Job cannot be retried (not found, not failed, or max retries exceeded)",
            )

        return JobResponse(job_id=job_id, status="queued", message="Job queued for retry")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/jobs/{job_id}", response_model=JobResponse)
async def cancel_job(job_id: str, job_svc: JobService = Depends(get_job_service)):
    """Cancel a pending or processing voice job."""
    try:
        success = await job_svc.cancel_job(job_id)

        if not success:
            raise HTTPException(
                status_code=400, detail="Job cannot be cancelled (not found or already completed)"
            )

        return JobResponse(job_id=job_id, status="cancelled", message="Job cancelled successfully")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/jobs")
async def list_jobs(
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Jobs per page"),
    job_svc: JobService = Depends(get_job_service),
):
    """List voice processing jobs with optional filtering and pagination."""
    try:
        # Calculate offset
        offset = (page - 1) * limit

        # Get jobs
        jobs_data = await job_svc.list_jobs(user_id=user_id, status=status, limit=limit * 2)

        # Apply pagination
        total_count = len(jobs_data)
        paginated_jobs = jobs_data[offset : offset + limit]

        return {"jobs": paginated_jobs, "total_count": total_count, "page": page, "limit": limit}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/stats")
async def get_voice_processing_stats(job_svc: JobService = Depends(get_job_service)):
    """Get voice processing system statistics."""
    try:
        all_jobs = await job_svc.list_jobs(limit=1000)

        stats = {
            "total_jobs": len(all_jobs),
            "pending_jobs": len([j for j in all_jobs if j["status"] == "pending"]),
            "processing_jobs": len([j for j in all_jobs if j["status"] == "processing"]),
            "completed_jobs": len([j for j in all_jobs if j["status"] == "completed"]),
            "failed_jobs": len([j for j in all_jobs if j["status"] == "failed"]),
            "nats_connected": job_svc.nats_client is not None,
        }

        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/upload", response_model=JobResponse)
async def upload_and_process(
    file: UploadFile = File(...),
    profile: str = Form("elevenlabs"),
    output_format: str = Form("wav"),
    multiple_segments: bool = Form(False),
    max_segments: int = Form(3),
    normalize_audio: bool = Form(False),
    start_time: Optional[int] = Form(None),
    end_time: Optional[int] = Form(None),
    user_id: Optional[UUID] = Form(None),
    priority: str = Form("normal"),
    job_svc: JobService = Depends(get_job_service),
):
    """Upload audio/video file and create processing job.

    This endpoint allows users to:
    1. Upload their own voice recordings (audio files)
    2. Upload video files for voice extraction
    3. Specify manual time ranges for multi-speaker content

    Supported formats: WAV, MP3, M4A (audio), MP4, MOV (video)

    Args:
        file: Audio or video file to process
        profile: Processing profile (elevenlabs, generic)
        output_format: Output audio format (always wav for ElevenLabs compatibility)
        multiple_segments: Extract multiple segments
        max_segments: Maximum number of segments (1-10)
        normalize_audio: Normalize audio levels
        start_time: Start time in seconds (for manual extraction)
        end_time: End time in seconds (for manual extraction)
        user_id: Optional user identifier
        priority: Job priority (low, normal, high, critical)

    Returns:
        JobResponse with job_id for tracking
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        # Check file extension - only support common formats
        # Output is always WAV (required by ElevenLabs 10 MB limit)
        allowed_extensions = {
            ".wav",  # Audio - uncompressed
            ".mp3",  # Audio - compressed
            ".m4a",  # Audio - Apple
            ".mp4",  # Video - universal
            ".mov",  # Video - Apple
        }
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {file_ext}. Allowed: {', '.join(allowed_extensions)}",
            )

        # Validate time range ONLY if BOTH are provided
        # Note: start_time and end_time are completely OPTIONAL
        # They can be used with multiple_segments=true to segment a specific time range
        if start_time is not None and end_time is not None:
            if end_time <= start_time:
                raise HTTPException(
                    status_code=400, detail="end_time must be greater than start_time"
                )

        # Enforce WAV output format for ElevenLabs compatibility (9MB size limit)
        if output_format.lower() != "wav":
            raise HTTPException(
                status_code=400,
                detail="output_format must be 'wav' (required for ElevenLabs 10MB upload limit)",
            )

        # Read file content into memory for S3 upload
        file_content = await file.read()

        # Create job request with placeholder input_source (will be updated with S3 URI)
        from shared.voice_processing.models import JobRequest

        job_request = JobRequest(
            job_type=JobType.VOICE_EXTRACTION,
            input_source="pending_upload",  # Placeholder - will be updated
            user_id=user_id,
            priority=JobPriority[priority.upper()],
            output_format="wav",  # Always WAV for ElevenLabs
            profile=profile,
            multiple_segments=multiple_segments,
            max_segments=max_segments,
            normalize_audio=normalize_audio,
            start_time=start_time,
            end_time=end_time,
        )

        # Step 1: Create job in database (not published to queue yet)
        job_id = await job_svc.create_job(job_request, user_id)

        # Step 2: Upload to S3 with the generated job_id
        s3_client = get_s3_client(bucket_name=settings.user_data_bucket, region=settings.aws_region)
        file_obj = BytesIO(file_content)

        s3_uri = await s3_client.upload_voice_input(
            file_obj=file_obj,
            filename=file.filename,
            job_id=job_id,
            user_id=user_id,
        )

        # Step 3: Update job with actual S3 URI
        await job_svc.update_job_input_source(job_id, s3_uri)

        # Step 4: Update job_request with S3 URI and publish to queue
        job_request.input_source = s3_uri
        await job_svc.publish_job_to_queue(job_id, job_request, user_id)

        return JobResponse(
            job_id=job_id,
            status="queued",
            message=f"File uploaded and job created: {file.filename}",
        )

    except HTTPException:
        raise
    except VoiceProcessingError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": e.message,
                "error_code": e.error_code.value,
                "category": e.category.value,
                "suggestions": e.suggestions,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/ingest-youtube", response_model=JobResponse)
async def ingest_youtube_video(
    request: YouTubeIngestRequest, job_svc: JobService = Depends(get_job_service)
):
    """Ingest YouTube video for transcript extraction and persona training.

    This endpoint:
    1. Extracts video ID from YouTube URL
    2. Checks if video already exists for this user (duplicate detection)
    3. If exists and force=False: Returns appropriate message
    4. If force=True: Cleans up existing data and re-ingests
    5. Creates YouTubeVideo entry with basic info (video_id, user_id, video_url)
    6. Creates a job to extract transcript and enrich with metadata
    7. Worker updates the YouTubeVideo entry with full metadata after extraction
    8. Links the video to the specified persona via PersonaDataSource

    Note: Tier limits (count and duration) are checked in the worker after extracting
    video metadata, ensuring accurate validation before final database update.

    Args:
        request: YouTube ingestion request with url, user_id, optional persona_id, and force flag

    Returns:
        JobResponse with job_id for tracking the ingestion process
    """
    try:
        from app.api.youtube_utils import (
            check_youtube_video_dependency,
            cleanup_youtube_video_data,
            extract_video_id_from_url,
        )
        from shared.database.models.database import Persona, get_session
        from shared.database.models.youtube import YouTubeVideo
        from shared.services.usage_cache_service import UsageCacheService
        from shared.voice_processing.models import JobRequest

        # Extract video ID from URL
        try:
            video_id = extract_video_id_from_url(request.youtube_url)
            logger.info(
                f"[YOUTUBE INGEST] Extracted video_id: {video_id} from URL: {request.youtube_url}"
            )
        except ValueError as e:
            logger.error(
                f"[YOUTUBE INGEST] Failed to extract video_id from URL: {request.youtube_url}, Error: {e}"
            )
            raise HTTPException(status_code=400, detail=str(e))

        logger.info(
            f"[YOUTUBE INGEST] Starting ingestion - user_id={request.user_id}, video_id={video_id}, "
            f"persona_id={request.persona_id}, force={request.force}"
        )

        youtube_video_id = None  # Initialize to avoid undefined reference

        # Check for duplicate and handle force mode
        async for session in get_session():
            logger.info(
                f"[YOUTUBE INGEST] Checking for duplicate video: user_id={request.user_id}, video_id={video_id}"
            )

            # Check if video already exists for this user
            # Use with_for_update() when force=True to prevent race conditions
            existing_video, has_embeddings = await check_youtube_video_dependency(
                session, request.user_id, video_id, lock_for_update=request.force
            )

            if existing_video:
                logger.info(
                    f"[YOUTUBE INGEST] DUPLICATE DETECTED - Existing video found: "
                    f"youtube_video.id={existing_video.id}, user_id={request.user_id}, "
                    f"video_id={existing_video.video_id}, has_embeddings={has_embeddings}, "
                    f"title={existing_video.title}, force={request.force}"
                )
            else:
                logger.info(
                    f"[YOUTUBE INGEST] NO DUPLICATE - Video not found for user_id={request.user_id}, "
                    f"video_id={video_id}. Will proceed with ingestion."
                )

            if existing_video and not request.force:
                # Video exists and force=False - return success response indicating video already exists
                logger.info(
                    f"[YOUTUBE INGEST] Video already exists - Returning existing video info: "
                    f"video.id={existing_video.id}, video_id={video_id}, user_id={request.user_id}, "
                    f"has_embeddings={has_embeddings}"
                )

                return JobResponse(
                    job_id=str(existing_video.id),  # Use existing video ID as job_id
                    status="completed" if has_embeddings else "failed",
                    message=f"Video already exists. has_embeddings={has_embeddings}, video_exists=True",
                )

            # ===== HANDLE FORCE MODE =====
            # If force=True and video exists, delete it first, then refresh usage cache
            if existing_video and request.force:
                logger.info(
                    f"[YOUTUBE INGEST] FORCE MODE - Cleaning up existing video {existing_video.id}"
                )
                try:
                    # Get persona if provided
                    temp_persona = None
                    if request.persona_id:
                        stmt = select(Persona).where(Persona.id == request.persona_id)
                        result = await session.execute(stmt)
                        temp_persona = result.scalar_one_or_none()
                        logger.info(
                            f"[YOUTUBE INGEST] Found persona: {temp_persona.id if temp_persona else 'None'}"
                        )

                    # Cleanup video (deletes embeddings, persona_data_source, and video record)
                    # Handle case where another concurrent request may have already deleted the records
                    logger.info(
                        f"[YOUTUBE INGEST] Deleting existing video data for {existing_video.id}"
                    )
                    try:
                        if temp_persona:
                            await cleanup_youtube_video_data(
                                session, existing_video.id, temp_persona.id
                            )
                        else:
                            await cleanup_youtube_video_data(session, existing_video.id)
                    except Exception as cleanup_error:
                        # Check if error is due to records already being deleted (race condition)
                        error_msg = str(cleanup_error).lower()
                        if (
                            "not found" in error_msg
                            or "does not exist" in error_msg
                            or "no row was found" in error_msg
                        ):
                            logger.warning(
                                f"[YOUTUBE INGEST] Records already deleted (likely concurrent request): {cleanup_error}"
                            )
                            # Continue - this is expected in race condition scenarios
                        else:
                            # Unexpected error - re-raise
                            raise

                    # After successful deletion, refresh usage cache from YouTubeVideo table
                    logger.info(
                        f"[YOUTUBE INGEST] Refreshing usage cache for user {request.user_id}"
                    )
                    usage_cache_service = UsageCacheService(session)
                    await usage_cache_service.recalculate_usage_from_source(
                        user_id=request.user_id, file_type_category="youtube"
                    )

                    # Commit deletion and cache refresh
                    await session.commit()
                    logger.info(
                        f"[YOUTUBE INGEST] FORCE MODE SUCCESS - Deleted video {existing_video.id} "
                        f"and refreshed usage cache for user {request.user_id}"
                    )
                except Exception as cleanup_error:
                    await session.rollback()
                    logger.error(
                        f"[YOUTUBE INGEST] FORCE MODE FAILED - Error cleaning up video: {cleanup_error}",
                        exc_info=True,
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to cleanup existing YouTube video: {str(cleanup_error)}",
                    )
            # ===== END FORCE MODE HANDLING =====

            # ===== CREATE YOUTUBE VIDEO ENTRY =====
            # Only create YouTubeVideo entry if:
            # 1. Video doesn't exist for this user, OR
            # 2. Force mode was enabled and we cleaned up the existing video
            logger.info(
                f"[YOUTUBE INGEST] Checking if should create video entry: "
                f"existing_video={existing_video is not None}, force={request.force}"
            )

            if not existing_video or request.force:
                logger.info(
                    f"[YOUTUBE INGEST] CREATING NEW VIDEO ENTRY - "
                    f"user_id={request.user_id}, video_id={video_id}"
                )

                # Create YouTubeVideo entry with minimal info (full metadata added by worker)
                youtube_video = YouTubeVideo(
                    user_id=request.user_id,
                    video_id=video_id,
                    video_url=request.youtube_url,
                    title="Processing...",  # Placeholder - updated by worker
                    duration_seconds=0,  # Placeholder - updated by worker
                )
                session.add(youtube_video)
                await session.flush()
                await session.refresh(youtube_video)

                logger.info(
                    f"[YOUTUBE INGEST] YouTubeVideo entry created successfully: "
                    f"id={youtube_video.id}, video_id={video_id}, user_id={request.user_id}"
                )

                # Commit YouTubeVideo entry
                await session.commit()
                logger.info("[YOUTUBE INGEST] YouTubeVideo entry committed to database")

                youtube_video_id = youtube_video.id
            else:
                # This case should never be reached because we raise HTTPException above
                # if existing_video and not request.force
                # But adding this for safety
                logger.error(
                    f"[YOUTUBE INGEST] UNEXPECTED STATE - Should not reach here! "
                    f"existing_video={existing_video.id if existing_video else None}, "
                    f"force={request.force}"
                )
                raise HTTPException(
                    status_code=400,
                    detail="Video already exists. Use force=true to re-ingest.",
                )

            # Exit after first iteration
            break

        logger.info(
            f"[YOUTUBE INGEST] Proceeding to job creation with youtube_video_id={youtube_video_id}"
        )

        import uuid as _uuid

        scraping_job_id = _uuid.uuid4()
        logger.info(f"[YOUTUBE INGEST] Job id created: job_id={scraping_job_id}")

        # Create job request for YouTube ingestion with persona_id, youtube_video_id, and scraping_job_id
        # If persona_id is None, worker will use 'default' persona (same as scraping_consumer)
        logger.info(
            f"[YOUTUBE INGEST] Creating voice processing job request - "
            f"youtube_video_id={youtube_video_id}, scraping_job_id={scraping_job.id}, "
            f"persona_id={request.persona_id}"
        )

        job_request = JobRequest(
            job_type=JobType.YOUTUBE_INGESTION,
            input_source=request.youtube_url,
            user_id=request.user_id,
            priority=JobPriority.NORMAL,
            persona_id=request.persona_id,  # Pass persona_id directly (can be None)
            metadata={
                "scraping_job_id": str(scraping_job_id),
                "youtube_video_id": str(youtube_video_id),  # Link to YouTubeVideo record
            },
        )

        logger.info(
            f"[YOUTUBE INGEST] Job request created with metadata: "
            f"scraping_job_id={scraping_job_id}, youtube_video_id={youtube_video_id}"
        )

        # Submit job
        logger.info("[YOUTUBE INGEST] Submitting job to queue")
        job_id = await job_svc.submit_job(job_request, request.user_id)

        logger.info(
            f"[YOUTUBE INGEST] SUCCESS - Job submitted: job_id={job_id}, "
            f"video_id={video_id}, youtube_video_id={youtube_video_id}, "
            f"user_id={request.user_id}"
        )

        return JobResponse(
            job_id=job_id,
            status="queued",
            message=f"YouTube video ingestion job created and queued for processing (video_id: {video_id})",
        )

    except VoiceProcessingError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": e.message,
                "error_code": e.error_code.value,
                "category": e.category.value,
                "suggestions": e.suggestions,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in ingest_youtube_video: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ===== YOUTUBE VIDEO MANAGEMENT ENDPOINTS =====


class YouTubeVideoInfo(BaseModel):
    """YouTube video information for listing"""

    id: UUID
    video_id: str
    title: Optional[str]
    video_url: str
    thumbnail_url: Optional[str]
    duration_seconds: Optional[int]
    channel_name: Optional[str]
    created_at: str
    published_at: Optional[str]


class YouTubeVideoListResponse(BaseModel):
    """Response for YouTube video listing"""

    videos: list[YouTubeVideoInfo]
    total_count: int


class YouTubeVideoResponse(BaseModel):
    """Response for YouTube video operations"""

    success: bool
    message: str
    youtube_video_id: Optional[UUID] = None
    job_id: Optional[UUID] = None


@router.post("/youtube/refresh", response_model=YouTubeVideoResponse)
async def refresh_youtube_video_embeddings(
    user_id: UUID,
    youtube_video_id: UUID,
    job_svc: JobService = Depends(get_job_service),
):
    """
    Refresh embeddings for an existing YouTube video

    This endpoint:
    1. Verifies the YouTube video exists and belongs to the specified user
    2. Deletes existing embeddings for the video
    3. Re-queues the video for processing to regenerate embeddings
    4. If embeddings don't exist, creates them

    Parameters:
        user_id: UUID of the user who owns the video
        youtube_video_id: UUID of the YouTube video to refresh

    Returns:
        YouTubeVideoResponse with job_id for tracking
    """
    import uuid as _uuid

    from shared.database.models.database import get_session
    from shared.database.models.persona_data_source import PersonaDataSource
    from shared.database.models.youtube import YouTubeVideo
    from shared.voice_processing.models import JobRequest

    try:
        async for session in get_session():
            # Verify YouTube video exists and belongs to user
            stmt = select(YouTubeVideo).where(
                YouTubeVideo.id == youtube_video_id, YouTubeVideo.user_id == user_id
            )
            result = await session.execute(stmt)
            youtube_video = result.scalar_one_or_none()

            if not youtube_video:
                raise HTTPException(
                    status_code=404,
                    detail=f"YouTube video not found or does not belong to user {user_id}",
                )

            logger.info(
                f"Refreshing embeddings for YouTube video {youtube_video_id}: "
                f"video_id={youtube_video.video_id}, title={youtube_video.title}"
            )

            # Delete existing embeddings
            from shared.database.models.embeddings import VoyageLiteEmbedding

            stmt = delete(VoyageLiteEmbedding).where(
                VoyageLiteEmbedding.source_record_id == youtube_video_id
            )
            result = await session.execute(stmt)
            deleted_count = result.rowcount
            logger.info(
                f"Deleted {deleted_count} existing embeddings for YouTube video {youtube_video_id}"
            )

            await session.flush()

            # Find persona for this video
            stmt = select(PersonaDataSource).where(
                PersonaDataSource.source_record_id == youtube_video_id,
                PersonaDataSource.source_type == "youtube",
            )
            result = await session.execute(stmt)
            data_source = result.scalar_one_or_none()

            if not data_source:
                logger.error(f"No persona_data_source found for YouTube video {youtube_video_id}")
                raise HTTPException(
                    status_code=400,
                    detail="No persona data source found for this YouTube video",
                )

            logger.info(f"Found persona_data_source: persona_id={data_source.persona_id}")

            await session.commit()

            scraping_job_id = _uuid.uuid4()

            # Create job request for re-processing
            job_request = JobRequest(
                job_type=JobType.YOUTUBE_INGESTION,
                input_source=youtube_video.video_url,
                user_id=user_id,
                priority=JobPriority.NORMAL,
                persona_id=data_source.persona_id,
                metadata={
                    "scraping_job_id": str(scraping_job_id),
                    "youtube_video_id": str(youtube_video_id),
                },
            )

            # Submit job
            job_id = await job_svc.submit_job(job_request, user_id)

            logger.info(
                f"Successfully queued YouTube video refresh job {job_id} for video {youtube_video_id}"
            )

            return YouTubeVideoResponse(
                success=True,
                message=f"YouTube video embeddings refresh job queued successfully (deleted {deleted_count} old embeddings)",
                youtube_video_id=youtube_video_id,
                job_id=UUID(job_id),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in refresh_youtube_video_embeddings: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/youtube/{user_id}", response_model=YouTubeVideoListResponse)
async def get_youtube_videos(user_id: UUID):
    """
    Retrieve all YouTube videos for a user

    Parameters:
        user_id: UUID of the user

    Returns:
        YouTubeVideoListResponse with list of videos and total count
    """
    logger.info(f"[GET YOUTUBE VIDEOS] Starting retrieval for user_id={user_id}")

    from shared.database.models.database import get_session
    from shared.database.models.youtube import YouTubeVideo

    response_to_return = None

    async for session in get_session():
        try:
            logger.info(f"[GET YOUTUBE VIDEOS] Querying database for user {user_id}")

            stmt = (
                select(YouTubeVideo)
                .where(YouTubeVideo.user_id == user_id)
                .order_by(YouTubeVideo.created_at.desc())
            )
            result = await session.execute(stmt)
            videos = result.scalars().all()

            logger.info(f"[GET YOUTUBE VIDEOS] Found {len(videos)} videos in database")

            video_list = []
            for i, video in enumerate(videos):
                try:
                    video_info = YouTubeVideoInfo(
                        id=video.id,
                        video_id=video.video_id,
                        title=video.title,
                        video_url=video.video_url,
                        thumbnail_url=video.thumbnail_url,
                        duration_seconds=video.duration_seconds,
                        channel_name=video.channel_name,
                        created_at=video.created_at.isoformat(),
                        published_at=(
                            video.published_at.isoformat() if video.published_at else None
                        ),
                    )
                    video_list.append(video_info)
                except Exception as video_error:
                    logger.error(
                        f"[GET YOUTUBE VIDEOS] Error processing video {i+1}/{len(videos)}: "
                        f"id={video.id}, error={video_error}",
                        exc_info=True,
                    )
                    # Skip this video and continue
                    continue

            logger.info(f"[GET YOUTUBE VIDEOS] Successfully processed {len(video_list)} videos")

            try:
                response_to_return = YouTubeVideoListResponse(
                    videos=video_list,
                    total_count=len(video_list),
                )
                logger.info("[GET YOUTUBE VIDEOS] Created response object successfully")
            except Exception as response_error:
                logger.error(
                    f"[GET YOUTUBE VIDEOS] Error creating response object: {response_error}",
                    exc_info=True,
                )
                raise

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                f"[GET YOUTUBE VIDEOS] Error retrieving YouTube videos for user {user_id}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve YouTube videos: {str(e)}",
            )
        finally:
            break

    # Return the response after exiting the loop
    if response_to_return is not None:
        logger.info(
            f"[GET YOUTUBE VIDEOS] Returning response with {response_to_return.total_count} videos"
        )
        return response_to_return

    # This should never be reached
    logger.error(f"[GET YOUTUBE VIDEOS] UNEXPECTED - No response created for user {user_id}")
    raise HTTPException(status_code=500, detail="Failed to retrieve YouTube videos")


@router.delete("/youtube/{youtube_video_id}", response_model=YouTubeVideoResponse)
async def delete_youtube_video(
    youtube_video_id: UUID,
    user_id: UUID,
):
    """
    Delete a YouTube video and its associated data

    This endpoint performs a comprehensive deletion of a YouTube video and all related data:
    1. Verifies the video exists and belongs to the specified user
    2. Checks for associated PersonaDataSource entries
    3. Checks for embeddings in data_llamalite_embeddings table using source_record_id
    4. Deletes all data in a single transaction:
       - YouTube video record from youtube table
       - Related PersonaDataSource entries from persona_data_source table
       - Related embeddings from data_llamalite_embeddings table
    5. **Refreshes usage cache for accurate limits**
    6. **All operations in single transaction - rollback on any failure**

    Note: No CASCADE DELETE is configured, so all related data must be manually deleted.
    The embeddings are linked via source_record_id field.

    Parameters:
        youtube_video_id: UUID of the YouTube video to delete
        user_id: UUID of the user who owns the video

    Returns:
        YouTubeVideoResponse with success status and details about what was deleted
    """
    from shared.database.models.database import get_session
    from shared.database.models.embeddings import VoyageLiteEmbedding
    from shared.database.models.persona_data_source import PersonaDataSource
    from shared.database.models.youtube import YouTubeVideo
    from shared.services.usage_cache_service import UsageCacheService

    async for session in get_session():
        try:
            # Verify YouTube video exists and belongs to user
            stmt = select(YouTubeVideo).where(
                YouTubeVideo.id == youtube_video_id, YouTubeVideo.user_id == user_id
            )
            result = await session.execute(stmt)
            youtube_video = result.scalar_one_or_none()

            if not youtube_video:
                raise HTTPException(
                    status_code=404,
                    detail=f"YouTube video not found or does not belong to user {user_id}",
                )

            # Store video info for logging
            video_title = youtube_video.title

            # Check for associated persona_data_source entries
            stmt = select(PersonaDataSource).where(
                PersonaDataSource.source_record_id == youtube_video_id,
                PersonaDataSource.source_type == "youtube",
            )
            result = await session.execute(stmt)
            data_sources = result.scalars().all()

            # Check for embeddings in data_llamalite_embeddings table using source_record_id
            stmt = select(VoyageLiteEmbedding).where(
                VoyageLiteEmbedding.source_record_id == youtube_video_id
            )
            result = await session.execute(stmt)
            embeddings = result.scalars().all()
            embeddings_count = len(embeddings)

            logger.info(
                f"Deleting YouTube video {youtube_video_id} for user {user_id}: "
                f"Found {len(data_sources)} persona_data_source entries and {embeddings_count} data_llamalite_embeddings"
            )

            # Delete all data in a single transaction

            # 1. Delete embeddings from data_llamalite_embeddings table using source_record_id
            if embeddings_count > 0:
                for embedding in embeddings:
                    await session.delete(embedding)
                logger.info(
                    f"Deleted {embeddings_count} embeddings from data_llamalite_embeddings for YouTube video {youtube_video_id}"
                )

            # 2. Delete persona data source entries
            for data_source in data_sources:
                await session.delete(data_source)
            logger.info(
                f"Deleted {len(data_sources)} persona_data_source entries for YouTube video {youtube_video_id}"
            )

            # 3. Delete the YouTube video record
            await session.delete(youtube_video)
            logger.info(f"Deleted YouTube video {youtube_video_id}")

            await session.flush()

            # Refresh usage cache
            usage_cache_service = UsageCacheService(session)
            await usage_cache_service.recalculate_usage_from_source(
                user_id=user_id, file_type_category="youtube"
            )
            logger.info(
                f"Refreshed usage cache for user {user_id} after deleting YouTube video {youtube_video_id}"
            )

            # Commit all deletions and cache refresh
            await session.commit()

            logger.info(
                f"Successfully deleted YouTube video {youtube_video_id} ({video_title}) "
                f"with {len(data_sources)} persona_data_source entries and {embeddings_count} data_llamalite_embeddings for user {user_id}. Usage cache refreshed."
            )

            return YouTubeVideoResponse(
                success=True,
                message=f"YouTube video deleted successfully (including {len(data_sources)} data sources and {embeddings_count} embeddings)",
                youtube_video_id=youtube_video_id,
            )

        except HTTPException:
            await session.rollback()
            raise
        except Exception as e:
            await session.rollback()
            logger.error(f"Error deleting YouTube video {youtube_video_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete YouTube video: {str(e)}",
            )


@router.get("/youtube/check-embeddings/{user_id}/{youtube_video_id}")
async def check_youtube_video_embeddings(
    user_id: UUID,
    youtube_video_id: UUID,
):
    """
    Check if a YouTube video has embeddings

    This endpoint checks whether the specified YouTube video has any embeddings
    stored in the data_llamalite_embeddings table.

    Parameters:
        user_id: UUID of the user who owns the video
        youtube_video_id: UUID of the YouTube video to check

    Returns:
        {
            "has_embeddings": bool,
            "youtube_video_id": str,
            "user_id": str,
            "video_exists": bool
        }
    """
    logger.info(
        f"[CHECK EMBEDDINGS] Starting check for youtube_video_id={youtube_video_id}, user_id={user_id}"
    )

    from shared.database.models.database import get_session
    from shared.database.models.embeddings import VoyageLiteEmbedding
    from shared.database.models.youtube import YouTubeVideo

    async for session in get_session():
        try:
            logger.info(
                f"[CHECK EMBEDDINGS] Querying database for video: "
                f"youtube_video_id={youtube_video_id}, user_id={user_id}"
            )

            # Verify YouTube video exists and belongs to user
            stmt = select(YouTubeVideo).where(
                YouTubeVideo.id == youtube_video_id, YouTubeVideo.user_id == user_id
            )
            result = await session.execute(stmt)
            youtube_video = result.scalar_one_or_none()

            if not youtube_video:
                logger.warning(
                    f"[CHECK EMBEDDINGS] Video NOT FOUND - "
                    f"youtube_video_id={youtube_video_id}, user_id={user_id}"
                )
                return {
                    "has_embeddings": False,
                    "youtube_video_id": str(youtube_video_id),
                    "user_id": str(user_id),
                    "video_exists": False,
                }

            logger.info(
                f"[CHECK EMBEDDINGS] Video FOUND - id={youtube_video.id}, "
                f"video_id={youtube_video.video_id}, title={youtube_video.title}"
            )

            # Check if embeddings exist in data_llamalite_embeddings table
            logger.info(
                "[CHECK EMBEDDINGS] Checking for embeddings in data_llamalite_embeddings..."
            )
            embedding_check = await session.execute(
                select(VoyageLiteEmbedding.id)
                .where(VoyageLiteEmbedding.source_record_id == youtube_video_id)
                .limit(1)
            )
            has_embeddings = embedding_check.scalar_one_or_none() is not None

            logger.info(
                f"[CHECK EMBEDDINGS] RESULT - video_exists=True, has_embeddings={has_embeddings}, "
                f"youtube_video_id={youtube_video_id}, user_id={user_id}"
            )

            return {
                "has_embeddings": bool(has_embeddings),
                "youtube_video_id": str(youtube_video_id),
                "user_id": str(user_id),
                "video_exists": True,
            }

        except Exception as e:
            logger.error(
                f"[CHECK EMBEDDINGS] ERROR - Exception occurred: {e}, "
                f"youtube_video_id={youtube_video_id}, user_id={user_id}",
                exc_info=True,
            )
            # Return structured response instead of raising exception
            return {
                "has_embeddings": False,
                "youtube_video_id": str(youtube_video_id),
                "user_id": str(user_id),
                "video_exists": False,
                "error": str(e),
            }
