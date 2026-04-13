"""Background worker for processing voice extraction jobs."""

import asyncio
import json
import os
import signal
import time
from pathlib import Path
from typing import Any, Dict, Optional

from extractors.audio_extractor import AudioExtractor
from extractors.youtube_extractor import YouTubeExtractor
from loguru import logger
from nats.aio.msg import Msg
from processors.audio_video_handlers import process_audio_transcription, process_video_transcription
from processors.pdf_handler import process_pdf_parsing
from processors.segment_selector import SegmentSelector
from processors.text_handler import process_text_document
from processors.youtube_handler import process_youtube_ingestion
from utils.config import config
from utils.progress import ProgressTracker

from shared.database.voice_job_model import async_session_maker
from shared.s3_utils import get_s3_client
from shared.voice_processing.errors import ErrorCode, VoiceProcessingError
from shared.voice_processing.job_repository import JobRepository
from shared.voice_processing.job_service import JobService
from shared.voice_processing.models import (
    JobRequest,
    JobResult,
    JobStatus,
    JobType,
    ProcessingStage,
)

# Optional Sentry monitoring - gracefully handle if not installed
try:
    import sentry_sdk

    from shared.monitoring.sentry_utils import (
        add_breadcrumb,
        capture_exception_with_context,
        init_sentry,
        set_job_context,
    )

    SENTRY_AVAILABLE = True
except ImportError:
    logger.warning("Sentry SDK not available - error monitoring disabled")
    SENTRY_AVAILABLE = False

    # Define no-op functions when Sentry is not available
    def add_breadcrumb(*args, **kwargs):
        pass

    def capture_exception_with_context(*args, **kwargs):
        pass

    def init_sentry(*args, **kwargs):
        pass

    def set_job_context(*args, **kwargs):
        pass


class VoiceProcessingWorker:
    """Background worker for processing voice extraction jobs."""

    def __init__(self, worker_id: str, nats_url: str = "nats://localhost:4222"):
        """Initialize worker.

        Args:
            worker_id: Unique identifier for this worker
            nats_url: NATS server URL
        """
        self.worker_id = worker_id
        self.nats_url = nats_url
        self.job_service: Optional[JobService] = None
        self.running = False

        # Graceful shutdown state
        self.accepting_jobs = True  # Whether to accept new jobs from NATS
        self.current_job_id: Optional[str] = None  # Currently processing job ID
        self.shutdown_requested = False  # SIGTERM received flag
        self.shutdown_start_time: Optional[float] = None  # When shutdown started

        # Processing components
        self.youtube_extractor: Optional[YouTubeExtractor] = None
        self.audio_extractor: Optional[AudioExtractor] = None
        self.segment_selector: Optional[SegmentSelector] = None

        # Stats
        self.jobs_processed = 0
        self.jobs_succeeded = 0
        self.jobs_failed = 0
        self.start_time = time.time()

        # Initialize Sentry for this worker
        init_sentry(
            component="worker_voice",
            worker_id=worker_id,
            custom_tags={"worker_type": "voice_processing"},
        )

    async def initialize(self):
        """Initialize worker components."""
        try:
            # Initialize job service
            self.job_service = JobService(self.nats_url)
            await self.job_service.initialize()

            logger.info(f"Worker {self.worker_id} initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize worker {self.worker_id}: {e}")
            raise

    async def _update_scraping_job_status(
        self, job_data: Dict[str, Any], status: str, error_message: Optional[str] = None
    ):
        """Update the corresponding scraping_jobs table entry.

        Args:
            job_data: Job metadata containing scraping_job_id
            status: New status ('completed' or 'failed')
            error_message: Optional error message for failed jobs
        """
        # Extract scraping_job_id from nested request.metadata structure
        request_data = job_data.get("request") or {}
        metadata = request_data.get("metadata") or {}
        scraping_job_id = metadata.get("scraping_job_id")

        if not scraping_job_id:
            logger.warning(
                f"No scraping_job_id found in job metadata. job_data keys: {job_data.keys()}, request keys: {request_data.keys()}, metadata keys: {metadata.keys()}"
            )
            return

        # Scraping repository has been removed; job status tracking is a no-op
        logger.debug(f"Skipping scraping job status update for job {scraping_job_id} (scraping infrastructure removed)")

    async def start(self):
        """Start processing jobs from the queue."""
        if not self.job_service:
            raise RuntimeError("Worker not initialized")

        self.running = True
        self.accepting_jobs = True  # Start accepting jobs
        logger.info(f"Worker {self.worker_id} starting job processing...")

        try:
            # Subscribe to job queue using pull consumer with retry configuration
            # This creates a durable consumer that can be shared across workers
            from nats.js.api import ConsumerConfig

            consumer_config = ConsumerConfig(
                durable_name="voice_workers",
                max_deliver=3,  # Maximum 3 delivery attempts before giving up
                ack_wait=300,  # Wait 5 minutes for ack before considering message failed
                max_ack_pending=10,  # Allow up to 10 unacknowledged messages per worker
            )

            subscription = await self.job_service.jetstream.pull_subscribe(
                subject=self.job_service.job_queue_subject,
                durable="voice_workers",  # Durable consumer name (shared across workers)
                stream="VOICE_JOBS",  # Stream name
                config=consumer_config,
            )

            # Process messages
            while self.running:
                try:
                    # Check if we should accept new jobs (graceful shutdown support)
                    if not self.accepting_jobs:
                        logger.info("🛑 Not accepting new jobs (shutdown in progress)")
                        await asyncio.sleep(1)  # Prevent tight loop
                        continue

                    # Fetch messages with timeout
                    messages = await subscription.fetch(batch=1, timeout=1)

                    for msg in messages:
                        # Double-check before processing (shutdown may have happened during fetch)
                        if not self.accepting_jobs:
                            logger.warning(
                                "⏭️  Skipping message during shutdown - NAKing for quick redelivery to healthy worker"
                            )
                            try:
                                # NAK with short delay so another worker can pick it up immediately
                                # Without this, NATS waits ack_wait timeout (300s) before redelivery
                                await msg.nak(delay=5)
                            except Exception as nak_error:
                                logger.warning(
                                    f"Failed to NAK message during shutdown: {nak_error}. "
                                    f"Will timeout and redeliver after 300s."
                                )
                            break

                        await self._process_job_message(msg)

                except asyncio.TimeoutError:
                    # No messages available, continue loop
                    continue
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await asyncio.sleep(1)  # Brief pause on error

        except Exception as e:
            logger.error(f"Worker {self.worker_id} error: {e}")
            raise
        finally:
            logger.info(f"Worker {self.worker_id} stopping...")

    async def graceful_shutdown(self):
        """Gracefully shutdown worker - wait for current job to complete.

        This method is called when SIGTERM is received (during ECS deployment).
        It will:
        1. Stop accepting new jobs (already done in signal handler)
        2. Wait for current job to complete (up to stopTimeout - 30s buffer)
        3. Close NATS connection
        4. Exit cleanly
        """
        shutdown_timeout = 570  # 9.5 minutes (stopTimeout=600s - 30s buffer for cleanup)
        check_interval = 5  # Check every 5 seconds
        elapsed = 0

        logger.info(f"🔄 Graceful shutdown initiated for worker {self.worker_id}")
        logger.info(f"   Current job: {self.current_job_id or 'None'}")
        logger.info(f"   Max wait time: {shutdown_timeout}s")

        # Stop the worker loop (will finish current message processing)
        self.running = False

        # Wait for current job to complete
        while self.current_job_id and elapsed < shutdown_timeout:
            remaining = shutdown_timeout - elapsed
            logger.info(
                f"⏳ Waiting for job {self.current_job_id} to complete... "
                f"({elapsed}s elapsed, {remaining}s remaining)"
            )

            await asyncio.sleep(check_interval)
            elapsed += check_interval

        # Check if we finished in time
        if self.current_job_id:
            logger.warning(
                f"⚠️  Shutdown timeout reached with active job: {self.current_job_id}. "
                f"ECS will force-kill in ~30 seconds. Job may be redelivered by NATS."
            )
        else:
            logger.info(f"✅ All jobs completed. Clean shutdown after {elapsed}s")

        # Close connections and cleanup
        await self.stop()

    async def stop(self):
        """Stop the worker and cleanup resources.

        This is called by graceful_shutdown() after jobs are done,
        or directly if no graceful shutdown was initiated.
        """
        logger.info(f"🛑 Stopping worker {self.worker_id}...")

        self.running = False
        self.accepting_jobs = False

        # Close NATS connection
        if self.job_service:
            try:
                await self.job_service.close()
                logger.info("✅ NATS connection closed cleanly")
            except Exception as e:
                logger.warning(f"⚠️  Error closing NATS connection: {e}")

        # Log final stats
        stats = self.get_stats()
        logger.info(
            f"📊 Worker {self.worker_id} final stats: "
            f"{stats['jobs_succeeded']}/{stats['jobs_processed']} succeeded, "
            f"{stats['jobs_failed']} failed, "
            f"uptime: {stats['uptime_seconds']:.1f}s"
        )

        # Flush Sentry events before shutdown (avoid losing in-flight events)
        try:
            sentry_sdk.flush(timeout=2.0)
            logger.debug("Flushed Sentry events before shutdown")
        except Exception as e:
            logger.warning(f"Failed to flush Sentry events: {e}")

        logger.info(f"✅ Worker {self.worker_id} stopped")

    async def _process_job_message(self, msg: Msg):
        """Process a job message from NATS queue.

        Args:
            msg: NATS message containing job data
        """
        job_data = None
        job_id = None

        # Isolate Sentry scope per message to avoid tag leakage across concurrent tasks
        with sentry_sdk.push_scope():
            try:
                # Parse job data
                job_data = json.loads(msg.data.decode())
                job_id = job_data.get("job_id")
                request_data = job_data.get("request", {})
                job_type = request_data.get("type")
                user_id = request_data.get("user_id")

                if not job_id:
                    logger.error("Received job message without job_id")
                    await msg.ack()
                    return

                # Set Sentry context for this job (isolated to this scope)
                set_job_context(
                    job_id=job_id, job_type=job_type or "unknown", source="voice_processing"
                )
                if user_id:
                    sentry_sdk.set_tag("user_id", str(user_id))

                # Add breadcrumb for job start
                add_breadcrumb(
                    f"Processing voice job: {job_type}",
                    "voice.processing",
                    data={"job_id": job_id, "type": job_type},
                )

                logger.info(f"Worker {self.worker_id} processing job {job_id}")

                # Track current job for graceful shutdown
                self.current_job_id = job_id

                # Process the job - this now returns the result without calling complete_job
                result = await self._process_job(job_data)

                # Mark job as completed in NATS/JobService
                if self.job_service and result:
                    await self.job_service.complete_job(job_id, result)

                # Update scraping job status to completed
                await self._update_scraping_job_status(job_data, "completed")

                # Acknowledge successful processing
                await msg.ack()
                self.jobs_processed += 1
                self.jobs_succeeded += 1

                add_breadcrumb(f"Completed voice job: {job_type}", "voice.completed")
                logger.info(f"Worker {self.worker_id} completed job {job_id}")

            except Exception as e:
                logger.error(f"Worker {self.worker_id} failed to process job {job_id}: {e}")

                # Check if this is a connection error during shutdown
                is_connection_error = "connection closed" in str(e).lower()
                is_shutdown = self.shutdown_requested

                if is_connection_error and is_shutdown:
                    logger.warning(
                        f"🔄 Connection error during shutdown - NAKing for redelivery to healthy worker. "
                        f"Job {job_id} will be redelivered."
                    )
                    # Don't ack - let NATS redeliver to a healthy worker
                    try:
                        await msg.nak(delay=10)  # Quick redelivery to new worker
                    except Exception as nak_error:
                        logger.warning(
                            f"Failed to NAK message: {nak_error}. Will timeout and redeliver."
                        )
                        # If NAK fails, NATS will redeliver after ack_wait timeout

                    self.jobs_failed += 1
                    return

                # Capture exception with full context (within isolated scope)
                capture_exception_with_context(
                    e,
                    extra={
                        "worker_id": self.worker_id,
                        "job_data": job_data,
                        "job_id": job_id,
                        "job_type": job_data.get("request", {}).get("type") if job_data else None,
                    },
                    tags={
                        "component": "voice_worker",
                        "operation": "process_voice_job",
                        "severity": "high",
                    },
                )

                # Determine if error is retryable
                is_retryable = isinstance(e, VoiceProcessingError) and e.is_retryable()

                # Get current delivery count (how many times NATS has delivered this message)
                delivery_count = (
                    msg.metadata.num_delivered if hasattr(msg, "metadata") and msg.metadata else 1
                )
                max_retries = 3

                if job_id and self.job_service:
                    error_code = "processing_error"
                    if isinstance(e, VoiceProcessingError):
                        error_code = e.error_code.value

                    # If retryable and haven't exceeded max retries, use NATS retry
                    if is_retryable and delivery_count < max_retries:
                        logger.warning(
                            f"Job {job_id} failed with retryable error (attempt {delivery_count}/{max_retries}). "
                            f"Will retry in 60s. Error: {e}"
                        )

                        # Update job status to show it's being retried (don't mark as FAILED yet)
                        await self.job_service.update_job_progress(
                            job_id=job_id,
                            stage=ProcessingStage.VALIDATION,
                            percentage=0,
                            message=f"Retrying after transient error (attempt {delivery_count + 1}/{max_retries})",
                            details={
                                "error": str(e),
                                "error_code": error_code,
                                "retry_count": delivery_count,
                            },
                        )

                        # NAK the message to trigger NATS retry (60 second delay)
                        await msg.nak(delay=60)  # delay in seconds
                        self.jobs_failed += 1
                        return

                    # Permanent failure or retries exhausted - mark as failed
                    logger.error(
                        f"Job {job_id} permanently failed after {delivery_count} attempts. "
                        f"Error: {e}"
                    )

                    # Mark job as failed in NATS/JobService
                    await self.job_service.fail_job(
                        job_id=job_id,
                        error_code=error_code,
                        error_message=str(e),
                        suggestions=getattr(e, "suggestions", []),
                    )

                    # Update scraping job status to failed (only if job_data was successfully parsed)
                    if job_data:
                        await self._update_scraping_job_status(
                            job_data, "failed", error_message=str(e)
                        )

                # Acknowledge message to remove from queue
                await msg.ack()
                self.jobs_processed += 1
                self.jobs_failed += 1

            finally:
                # Always clear current job ID when done (success or failure)
                if self.current_job_id == job_id:
                    self.current_job_id = None

    async def _process_job(self, job_data: Dict[str, Any]) -> JobResult:
        """Process a single job.

        Args:
            job_data: Job information from NATS message

        Returns:
            JobResult with processing results
        """
        job_id = job_data["job_id"]
        job_type = JobType(job_data["job_type"])
        request_data = job_data["request"]

        # Deduplication check: Skip if job is already being processed or completed
        async with async_session_maker() as session:
            repo = JobRepository(session)
            existing_job = await repo.get_job_by_id(job_id)

            if existing_job:
                current_status = JobStatus(existing_job.status)

                # Skip if job is already in a terminal or processing state
                if current_status in [
                    JobStatus.PROCESSING,
                    JobStatus.COMPLETED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                ]:
                    logger.warning(
                        f"Job {job_id} is already in {current_status.value} state. "
                        f"Skipping duplicate processing (worker_id: {existing_job.worker_id or 'unknown'})"
                    )
                    return None

        # Create job request object
        job_request = JobRequest(
            job_type=job_type,
            input_source=request_data["input_source"],
            user_id=request_data.get("user_id"),
            output_format=request_data.get("output_format", "wav"),
            profile=request_data.get("profile", "elevenlabs"),
            multiple_segments=request_data.get("multiple_segments", False),
            max_segments=request_data.get("max_segments", 3),
            normalize_audio=request_data.get("normalize_audio", False),
            start_time=request_data.get("start_time"),
            end_time=request_data.get("end_time"),
            # PDF parsing options
            persona_id=request_data.get("persona_id"),
            chunk_size=request_data.get("chunk_size", 1000),
            overlap=request_data.get("overlap", 200),
            enhance_images=request_data.get("enhance_images", False),
            # Metadata for document_id and other context
            metadata=request_data.get("metadata"),
        )

        # Mark job as started in PostgreSQL
        async with async_session_maker() as session:
            repo = JobRepository(session)
            await repo.update_job_status(
                job_id=job_id, status=JobStatus.PROCESSING, worker_id=self.worker_id
            )

        # Create progress tracker
        progress_tracker = ProgressTracker(
            callback=lambda update: self._update_progress_sync(job_id, update)
        )

        # Process based on job type
        if job_type == JobType.VOICE_EXTRACTION:
            result = await self._process_voice_extraction(job_request, progress_tracker, job_id)
        elif job_type == JobType.TRANSCRIPT_EXTRACTION:
            result = await self._process_transcript_extraction(job_request, progress_tracker)
        elif job_type == JobType.COMBINED_PROCESSING:
            result = await self._process_combined(job_request, progress_tracker)
        elif job_type == JobType.PDF_PARSING:
            result = await self._process_pdf_parsing(job_request, progress_tracker)
        elif job_type == JobType.AUDIO_TRANSCRIPTION:
            result = await self._process_audio_transcription(job_request, progress_tracker)
        elif job_type == JobType.VIDEO_TRANSCRIPTION:
            result = await self._process_video_transcription(job_request, progress_tracker)
        elif job_type == JobType.YOUTUBE_INGESTION:
            # Get persona_id directly from job_data (can be None for default persona)
            persona_id = job_data.get("persona_id")
            result = await self._process_youtube_ingestion(
                job_request, progress_tracker, persona_id
            )
        elif job_type == JobType.TEXT_PROCESSING:
            result = await self._process_text_document(job_request, progress_tracker)
        else:
            raise VoiceProcessingError(
                message=f"Unsupported job type: {job_type}", error_code=ErrorCode.INVALID_FORMAT
            )

        # Return the result without calling complete_job
        # The caller (_process_job_message) will handle job completion
        return result

    async def _process_voice_extraction(
        self, request: JobRequest, progress_tracker: ProgressTracker, job_id: str
    ) -> JobResult:
        """Process voice extraction job.

        Args:
            request: Job request
            progress_tracker: Progress tracking callback
            job_id: Job identifier (for S3 uploads)

        Returns:
            Job result with extracted audio files
        """
        start_time = time.time()

        # Initialize extractors with progress tracking
        youtube_extractor = YouTubeExtractor(progress_tracker)
        audio_extractor = AudioExtractor(progress_tracker)

        voice_files = []
        input_info = {}

        try:
            # Extract audio from input source
            if request.input_source.startswith("s3://"):
                # S3 file - download to local temp storage
                progress_tracker.start_stage(ProcessingStage.VALIDATION, "Downloading from S3")

                s3_client = get_s3_client()
                temp_dir = config.get_output_dir("temp")
                filename = Path(request.input_source).name
                local_path = temp_dir / filename

                # Download from S3
                input_path = await s3_client.download_from_uri(request.input_source, local_path)

                progress_tracker.complete_stage("S3 download completed")

                input_info = {
                    "source": "s3",
                    "s3_uri": request.input_source,
                    "file_path": str(input_path),
                    "file_size": input_path.stat().st_size,
                }

                audio_path = str(input_path)

            elif request.input_source.startswith(("http://", "https://")):
                # YouTube URL - run blocking I/O in thread pool
                audio_path = await asyncio.to_thread(
                    youtube_extractor.extract_audio_from_url,
                    request.input_source,
                    None,  # Let it generate output path
                )

                # Get video info for metadata
                try:
                    input_info = await asyncio.to_thread(
                        youtube_extractor.get_video_info, request.input_source
                    )
                except Exception:
                    input_info = {"source": "youtube", "url": request.input_source}

            else:
                # Local file path (legacy - should not be used in production)
                progress_tracker.start_stage(ProcessingStage.VALIDATION, "Validating input file")
                input_path = Path(request.input_source)

                if not input_path.exists():
                    raise VoiceProcessingError(
                        message=f"Input file not found: {request.input_source}",
                        error_code=ErrorCode.FILE_NOT_FOUND,
                    )

                progress_tracker.complete_stage("Input validation completed")
                audio_path = str(input_path)

                # Extract audio from video or convert audio format
                # Supported audio formats: .wav, .mp3, .m4a
                if input_path.suffix.lower() in [".wav", ".mp3", ".m4a"]:
                    # Audio file - convert if needed (with optional time range)
                    output_dir = config.get_output_dir("raw")
                    output_path = (
                        output_dir / f"{input_path.stem}_processed.{request.output_format}"
                    )
                    audio_path = await asyncio.to_thread(
                        audio_extractor.convert_audio_format,
                        str(input_path),
                        str(output_path),
                        request.output_format,
                        start_time=request.start_time,
                        end_time=request.end_time,
                    )
                else:
                    # Video file - extract audio (with optional time range)
                    output_dir = config.get_output_dir("raw")
                    output_path = (
                        output_dir / f"{input_path.stem}_extracted.{request.output_format}"
                    )
                    audio_path = await asyncio.to_thread(
                        audio_extractor.extract_from_video,
                        str(input_path),
                        str(output_path),
                        request.output_format,
                        start_time=request.start_time,
                        end_time=request.end_time,
                    )

                input_info = {
                    "source": "local_file",
                    "file_path": str(input_path),
                    "file_size": input_path.stat().st_size,
                }

            # Process segments if requested
            if request.multiple_segments:
                progress_tracker.start_stage(
                    ProcessingStage.SEGMENTATION, "Extracting multiple segments"
                )

                # Initialize segment selector with 9MB limit for ElevenLabs
                # Audio specs: 44.1kHz, 16-bit, mono (matches audio_extractor.py:103-111)
                # OPTIMIZE FOR QUALITY: Don't specify target_duration, use max 9MB capacity (~107s)
                segment_selector = SegmentSelector(
                    max_file_size_mb=9.0,  # ElevenLabs max is 10MB, use 9MB for safety
                    sample_rate=44100,
                    bit_depth=16,
                    channels=1,
                )
                segments_info = await asyncio.to_thread(
                    segment_selector.select_multiple_segments,
                    audio_path,
                    config.get_output_dir("segments"),
                    max_segments=request.max_segments,
                )

                if segments_info.get("success"):
                    for segment_info in segments_info["segments"]:
                        voice_files.append(
                            {
                                "file_path": segment_info["output_path"],
                                "duration": segment_info["duration"],
                                "quality_score": segment_info["quality_score"],
                                "start_time": segment_info["start_time"],
                                "end_time": segment_info["end_time"],
                            }
                        )

                    progress_tracker.complete_stage(f"Extracted {len(voice_files)} segments")
                else:
                    # Fallback to single file
                    voice_files.append(
                        {
                            "file_path": audio_path,
                            "duration": input_info.get("duration", 0),
                            "quality_score": 0.5,
                        }
                    )
            else:
                # Single audio file - validate it's under 9 MB for ElevenLabs
                audio_file_path = Path(audio_path)
                file_size_mb = audio_file_path.stat().st_size / (1024 * 1024)

                if file_size_mb > 9.0:
                    raise VoiceProcessingError(
                        message=(
                            f"Output file exceeds ElevenLabs 9MB limit: {file_size_mb:.2f}MB. "
                            f"Try using 'multiple_segments=true' to split into smaller segments, "
                            f"or specify a shorter time range with start_time/end_time."
                        ),
                        error_code=ErrorCode.FILE_TOO_LARGE,
                    )

                voice_files.append(
                    {
                        "file_path": audio_path,
                        "duration": input_info.get("duration", 0),
                        "quality_score": 0.5,
                        "file_size_mb": file_size_mb,
                    }
                )

            # Upload processed files to S3
            s3_client = get_s3_client()
            uploaded_voice_files = []

            for voice_file in voice_files:
                local_file_path = Path(voice_file["file_path"])

                # Determine output type based on path
                output_type = "segments" if "segments" in str(local_file_path) else "raw"

                # Upload to S3
                s3_uri = await s3_client.upload_voice_output(
                    file_path=local_file_path,
                    job_id=job_id,
                    output_type=output_type,
                    user_id=request.user_id,
                )

                # Update voice_file entry with S3 URI
                uploaded_voice_files.append(
                    {
                        "file_path": s3_uri,  # S3 URI instead of local path
                        "duration": voice_file.get("duration", 0),
                        "quality_score": voice_file.get("quality_score", 0.5),
                        "start_time": voice_file.get("start_time"),
                        "end_time": voice_file.get("end_time"),
                    }
                )

            # Calculate average quality
            avg_quality = sum(vf.get("quality_score", 0) for vf in uploaded_voice_files) / len(
                uploaded_voice_files
            )

            processing_time = time.time() - start_time

            return JobResult(
                success=True,
                processing_time_seconds=processing_time,
                input_info=input_info,
                voice_files=uploaded_voice_files,  # S3 URIs
                voice_quality_score=avg_quality,
            )

        except Exception as e:
            processing_time = time.time() - start_time

            if isinstance(e, VoiceProcessingError):
                # Log structured error
                logger.error(
                    f"Voice extraction failed: {e.message} "
                    f"(code: {e.error_code.value}, category: {e.category.value})"
                )
                return JobResult(
                    success=False,
                    processing_time_seconds=processing_time,
                    input_info=input_info,
                    error_code=e.error_code.value,
                    error_message=e.message,
                    error_suggestions=e.suggestions,
                )
            else:
                # Log unexpected error with full traceback
                logger.exception(f"Unexpected error during voice extraction: {e}")
                return JobResult(
                    success=False,
                    processing_time_seconds=processing_time,
                    input_info=input_info,
                    error_code="processing_error",
                    error_message=str(e),
                    error_suggestions=["Check input file", "Try again"],
                )

    async def _process_transcript_extraction(
        self, request: JobRequest, progress_tracker: ProgressTracker
    ) -> JobResult:
        """Process transcript extraction job (placeholder for future implementation).

        Args:
            request: Job request
            progress_tracker: Progress tracking callback

        Returns:
            Job result with transcript
        """
        # TODO: Implement transcript extraction using Whisper or similar
        start_time = time.time()

        progress_tracker.start_stage(
            ProcessingStage.TRANSCRIPT_EXTRACTION, "Transcript extraction not implemented"
        )

        # Placeholder implementation
        await asyncio.sleep(1)  # Simulate processing

        processing_time = time.time() - start_time

        return JobResult(
            success=False,
            processing_time_seconds=processing_time,
            input_info={"source": request.input_source},
            error_code="not_implemented",
            error_message="Transcript extraction not yet implemented",
            error_suggestions=[
                "Use voice extraction for now",
                "Check back later for transcript support",
            ],
        )

    async def _process_combined(
        self, request: JobRequest, progress_tracker: ProgressTracker
    ) -> JobResult:
        """Process combined voice + transcript extraction (placeholder).

        Args:
            request: Job request
            progress_tracker: Progress tracking callback

        Returns:
            Combined job result
        """
        # TODO: Implement combined processing
        # For now, just do voice extraction
        return await self._process_voice_extraction(request, progress_tracker)

    async def _process_pdf_parsing(
        self, request: JobRequest, progress_tracker: ProgressTracker
    ) -> JobResult:
        """Process PDF parsing job - delegates to pdf_handler.

        Args:
            request: Job request
            progress_tracker: Progress tracking callback

        Returns:
            Job result with parsed PDF chunks
        """
        return await process_pdf_parsing(request, progress_tracker)

    async def _process_audio_transcription(
        self, request: JobRequest, progress_tracker: ProgressTracker
    ) -> JobResult:
        """Process audio transcription job using AssemblyAI with chunking.

        Args:
            request: Job request
            progress_tracker: Progress tracking callback

        Returns:
            Job result with timestamped transcript chunks
        """
        # Delegate to the imported handler function
        return await process_audio_transcription(request, progress_tracker)

    async def _process_video_transcription(self, request, progress_tracker):
        """Process video transcription job using AssemblyAI (extracts audio first)."""
        # Delegate to the imported handler function
        return await process_video_transcription(request, progress_tracker)

    async def _process_youtube_ingestion(
        self, request: JobRequest, progress_tracker: ProgressTracker, persona_id: Optional[str]
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
        return await process_youtube_ingestion(request, progress_tracker, persona_id)

    async def _process_text_document(
        self, request: JobRequest, progress_tracker: ProgressTracker
    ) -> JobResult:
        """Process text document (.txt, .md) - delegates to text_handler.

        Args:
            request: Job request
            progress_tracker: Progress tracking callback

        Returns:
            Job result with text processing information
        """
        return await process_text_document(request, progress_tracker)

    def _update_progress_sync(self, job_id: str, update):
        """Synchronous wrapper for updating job progress.

        This is called from synchronous callbacks (ProgressTracker).
        We store the update and handle it asynchronously in the main event loop.

        Args:
            job_id: Job identifier
            update: Progress update object
        """
        # Try to get the current event loop
        try:
            loop = asyncio.get_running_loop()
            # Schedule the coroutine in the current loop
            asyncio.ensure_future(self._update_progress(job_id, update), loop=loop)
        except RuntimeError:
            # No running event loop - log warning and skip update
            logger.warning(f"Cannot update progress for job {job_id}: no running event loop")

    async def _update_progress(self, job_id: str, update):
        """Update job progress via job service.

        Args:
            job_id: Job identifier
            update: Progress update object
        """
        if self.job_service:
            # Handle both string and enum stage values
            stage_value = update.stage if isinstance(update.stage, str) else update.stage.value

            await self.job_service.update_job_progress(
                job_id=job_id,
                stage=ProcessingStage(stage_value),
                percentage=update.percentage,
                message=update.message,
                details=update.details,
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics.

        Returns:
            Worker statistics dictionary
        """
        uptime = time.time() - self.start_time

        return {
            "worker_id": self.worker_id,
            "status": "running" if self.running else "stopped",
            "uptime_seconds": uptime,
            "jobs_processed": self.jobs_processed,
            "jobs_succeeded": self.jobs_succeeded,
            "jobs_failed": self.jobs_failed,
            "success_rate": self.jobs_succeeded / max(self.jobs_processed, 1),
            "jobs_per_minute": (self.jobs_processed / uptime) * 60 if uptime > 0 else 0,
        }


async def main():
    """Main worker entry point."""
    import uuid

    worker_id = f"worker_{uuid.uuid4().hex[:8]}"
    nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
    worker = VoiceProcessingWorker(worker_id, nats_url=nats_url)

    # Get the running event loop for signal handling
    loop = asyncio.get_running_loop()

    # Graceful shutdown handler
    def handle_shutdown():
        """Handle SIGTERM/SIGINT gracefully - finish current job before exiting."""
        logger.info("🛑 Received shutdown signal - initiating graceful shutdown")

        # Set shutdown flags
        worker.shutdown_requested = True
        worker.shutdown_start_time = time.time()
        worker.accepting_jobs = False  # Stop accepting new jobs immediately

        # Create graceful shutdown task (safe - running in event loop context)
        asyncio.create_task(worker.graceful_shutdown())

    # Register signal handlers with event loop (works in event loop context)
    # Note: Linux-only, but we're on ECS so this is fine
    loop.add_signal_handler(signal.SIGTERM, handle_shutdown)
    loop.add_signal_handler(signal.SIGINT, handle_shutdown)

    try:
        await worker.initialize()
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
