"""Job management service for voice processing operations."""

import json
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

import nats
from loguru import logger
from nats.aio.client import Client as NATSClient
from nats.js import JetStreamContext
from nats.js.api import RetentionPolicy, StorageType, StreamConfig

from shared.database.voice_job_model import async_session_maker

from .errors import ErrorCode, VoiceProcessingError
from .job_repository import JobRepository
from .models import Job, JobProgress, JobRequest, JobResult, JobStatus, ProcessingStage


class JobService:
    """Service for managing voice processing jobs with NATS and PostgreSQL.

    This service uses PostgreSQL for shared job state between backend and workers.
    """

    def __init__(self, nats_url: str = "nats://localhost:4222"):
        """Initialize job service.

        Args:
            nats_url: NATS server URL
        """
        self.nats_url = nats_url
        self.nats_client: Optional[NATSClient] = None
        self.jetstream: Optional[JetStreamContext] = None

        # NATS subjects
        self.job_queue_subject = "voice.jobs"
        self.progress_subject = "voice.progress"
        self.results_subject = "voice.results"

    async def initialize(self):
        """Initialize NATS connection and streams."""
        try:
            # Connect to NATS
            self.nats_client = await nats.connect(self.nats_url)
            self.jetstream = self.nats_client.jetstream()

            # Create streams if they don't exist
            await self._create_streams()

            logger.info(f"Job service initialized with NATS at {self.nats_url}")

        except Exception as e:
            logger.error(f"Failed to initialize job service: {e}")
            raise VoiceProcessingError(
                message=f"Job service initialization failed: {e}",
                error_code=ErrorCode.SYSTEM,
                suggestions=["Check NATS server is running", "Verify NATS URL is correct"],
            )

    async def _create_streams(self):
        """Create NATS JetStream streams for job processing."""
        try:
            # Job queue stream - persistent job storage
            await self.jetstream.add_stream(
                config=StreamConfig(
                    name="VOICE_JOBS",
                    subjects=[self.job_queue_subject],
                    retention=RetentionPolicy.WORK_QUEUE,  # Jobs removed after acknowledgment
                    max_age=24 * 60 * 60,  # 24 hours (in seconds)
                    storage=StorageType.FILE,  # Persistent storage
                )
            )

            # Progress updates stream - temporary progress notifications
            await self.jetstream.add_stream(
                config=StreamConfig(
                    name="VOICE_PROGRESS",
                    subjects=[self.progress_subject],
                    retention=RetentionPolicy.LIMITS,
                    max_age=60 * 60,  # 1 hour (in seconds)
                    max_msgs=10000,
                    storage=StorageType.MEMORY,  # Fast access for real-time updates
                )
            )

            # Results stream - completed job results
            await self.jetstream.add_stream(
                config=StreamConfig(
                    name="VOICE_RESULTS",
                    subjects=[self.results_subject],
                    retention=RetentionPolicy.LIMITS,
                    max_age=7 * 24 * 60 * 60,  # 7 days (in seconds)
                    max_msgs=1000,
                    storage=StorageType.FILE,  # Persistent results
                )
            )

            logger.info("NATS streams created successfully")

        except nats.errors.Error as e:
            # Only ignore "stream already exists" error - let real problems surface
            error_msg = str(e).lower()
            if "stream name already in use" in error_msg or "already exists" in error_msg:
                logger.debug("NATS streams already exist")
            else:
                logger.error(f"Failed to create NATS streams: {e}")
                raise

    async def create_job(self, request: JobRequest, user_id: Optional[UUID] = None) -> str:
        """Create a new job in the database without publishing to queue.

        Use this when you need to create a job first, then update it (e.g., S3 upload),
        and finally publish to queue using publish_job_to_queue().

        Args:
            request: Job request with processing parameters
            user_id: Optional user identifier (UUID)

        Returns:
            Job ID for tracking

        Raises:
            VoiceProcessingError: If job creation fails
        """
        try:
            # Create new job in memory to get job_id
            job = Job.create_new(request, user_id)

            # Store job in PostgreSQL
            async with async_session_maker() as session:
                repo = JobRepository(session)
                await repo.create_job(
                    job_id=job.job_id,
                    job_type=request.job_type,
                    request_data=request.to_dict(),
                    user_id=user_id,
                    priority=request.priority,
                )

            logger.info(f"Job {job.job_id} created in database ({job.job_type.value})")
            return job.job_id

        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            raise VoiceProcessingError(
                message=f"Job creation failed: {e}",
                error_code=ErrorCode.SYSTEM,
                suggestions=["Check database connection", "Try creating the job again"],
            )

    async def publish_job_to_queue(
        self, job_id: str, request: JobRequest, user_id: Optional[UUID] = None
    ) -> None:
        """Publish an existing job to NATS queue for processing.

        Args:
            job_id: Job identifier
            request: Job request with processing parameters
            user_id: Optional user identifier (UUID)

        Raises:
            VoiceProcessingError: If publishing fails
        """
        try:
            # Publish job to NATS queue
            job_data = {
                "job_id": job_id,
                "job_type": request.job_type.value,
                "request": request.to_dict(),
                "user_id": str(user_id) if user_id else None,
                "priority": request.priority.value,
                "created_at": time.time(),
                "persona_id": (
                    str(request.persona_id) if request.persona_id else None
                ),  # Pass persona_id for worker
            }

            await self.jetstream.publish(
                subject=self.job_queue_subject,
                payload=json.dumps(job_data).encode(),
                headers={"priority": str(request.priority.value)},
            )

            logger.info(f"Job {job_id} published to queue ({request.job_type.value})")

        except Exception as e:
            logger.error(f"Failed to publish job to queue: {e}")
            raise VoiceProcessingError(
                message=f"Job queue publishing failed: {e}",
                error_code=ErrorCode.SYSTEM,
                suggestions=["Check NATS connection", "Try publishing the job again"],
            )

    async def submit_job(self, request: JobRequest, user_id: Optional[UUID] = None) -> str:
        """Submit a new processing job (create in DB + publish to queue).

        This is a convenience method that combines create_job() and publish_job_to_queue().
        For workflows requiring intermediate steps (e.g., S3 upload), use create_job()
        and publish_job_to_queue() separately.

        Args:
            request: Job request with processing parameters
            user_id: Optional user identifier (UUID)

        Returns:
            Job ID for tracking

        Raises:
            VoiceProcessingError: If job submission fails
        """
        try:
            # Create job in database
            job_id = await self.create_job(request, user_id)

            # Publish to queue
            await self.publish_job_to_queue(job_id, request, user_id)

            logger.info(f"Job {job_id} submitted successfully ({request.job_type.value})")
            return job_id

        except Exception as e:
            logger.error(f"Failed to submit job: {e}")
            raise VoiceProcessingError(
                message=f"Job submission failed: {e}",
                error_code=ErrorCode.SYSTEM,
                suggestions=["Check NATS connection", "Try submitting the job again"],
            )

    async def update_job_input_source(self, job_id: str, input_source: str) -> None:
        """Update job's input_source in request_data (e.g., after S3 upload).

        Args:
            job_id: Job identifier
            input_source: New input source (S3 URI)
        """
        async with async_session_maker() as session:
            repo = JobRepository(session)
            db_job = await repo.get_job_by_id(job_id)

            if not db_job:
                logger.warning(f"Attempted to update input_source for unknown job: {job_id}")
                return

            # Update request_data with new input_source
            updated_request = db_job.request_data.copy()
            updated_request["input_source"] = input_source

            await repo.update_job_request_data(job_id, updated_request)
            logger.info(f"Updated job {job_id} input_source to: {input_source}")

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current job status and progress.

        Args:
            job_id: Job identifier

        Returns:
            Job status dictionary or None if not found
        """
        async with async_session_maker() as session:
            repo = JobRepository(session)
            db_job = await repo.get_job_by_id(job_id)

            if not db_job:
                return None

            return {
                "job_id": db_job.job_id,
                "status": db_job.status,
                "job_type": db_job.job_type,
                "priority": db_job.priority,
                "current_stage": db_job.current_stage,
                "progress_percentage": db_job.progress_percentage,
                "error_message": db_job.error_message,
                "error_code": db_job.error_code,
                "result": db_job.result,
                "created_at": db_job.created_at.timestamp() if db_job.created_at else None,
                "started_at": db_job.started_at.timestamp() if db_job.started_at else None,
                "completed_at": db_job.completed_at.timestamp() if db_job.completed_at else None,
                "retry_count": db_job.retry_count,
            }

    async def get_job_progress(self, job_id: str) -> Optional[JobProgress]:
        """Get detailed job progress information.

        Args:
            job_id: Job identifier

        Returns:
            Job progress or None if not found
        """
        async with async_session_maker() as session:
            repo = JobRepository(session)
            db_job = await repo.get_job_by_id(job_id)

            if not db_job:
                return None

            return JobProgress(
                job_id=job_id,
                stage=(
                    ProcessingStage(db_job.current_stage)
                    if db_job.current_stage
                    else ProcessingStage.VALIDATION
                ),
                percentage=db_job.progress_percentage or 0,
                message=db_job.current_stage or "Processing...",
                details=db_job.stage_details,
                timestamp=db_job.updated_at.timestamp() if db_job.updated_at else time.time(),
            )

    async def update_job_progress(
        self,
        job_id: str,
        stage: ProcessingStage,
        percentage: float,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Update job progress and publish to NATS.

        Args:
            job_id: Job identifier
            stage: Current processing stage
            percentage: Progress percentage (0-100)
            message: Progress message
            details: Optional additional details
        """
        # Update job progress in PostgreSQL
        async with async_session_maker() as session:
            repo = JobRepository(session)

            # Handle both ProcessingStage enum and string values
            stage_value = stage.value if isinstance(stage, ProcessingStage) else stage

            success = await repo.update_job_progress(
                job_id=job_id,
                current_stage=stage_value,
                progress_percentage=int(percentage),
                stage_details=details,
            )

            if not success:
                logger.warning(f"Attempted to update progress for unknown job: {job_id}")
                return

        # Publish progress update to NATS
        progress = JobProgress(
            job_id=job_id, stage=stage, percentage=percentage, message=message, details=details
        )

        try:
            await self.jetstream.publish(
                subject=f"{self.progress_subject}.{job_id}",
                payload=json.dumps(progress.to_dict()).encode(),
            )
        except Exception as e:
            logger.warning(f"Failed to publish progress update: {e}")

    async def complete_job(self, job_id: str, result: JobResult):
        """Mark job as completed with results.

        Args:
            job_id: Job identifier
            result: Job processing results
        """
        # Update job in PostgreSQL
        async with async_session_maker() as session:
            repo = JobRepository(session)

            # Set status based on result success
            final_status = JobStatus.COMPLETED if result.success else JobStatus.FAILED
            await repo.update_job_status(job_id, final_status)

            # Store result data
            await repo.update_job_result(job_id, result.to_dict())

            # Get updated job for completion data
            db_job = await repo.get_job_by_id(job_id)
            if not db_job:
                logger.warning(f"Attempted to complete unknown job: {job_id}")
                return

        # Calculate processing time
        processing_time = 0
        if db_job.started_at and db_job.completed_at:
            processing_time = (db_job.completed_at - db_job.started_at).total_seconds()

        # Publish completion notification
        completion_data = {
            "job_id": job_id,
            "status": "completed",
            "result": result.to_dict(),
            "completed_at": db_job.completed_at.timestamp() if db_job.completed_at else None,
            "processing_time": processing_time,
        }

        try:
            await self.jetstream.publish(
                subject=f"{self.results_subject}.{job_id}",
                payload=json.dumps(completion_data).encode(),
            )

            logger.info(f"Job {job_id} completed successfully in {processing_time:.1f}s")

        except Exception as e:
            logger.warning(f"Failed to publish completion notification: {e}")

    async def fail_job(
        self,
        job_id: str,
        error_code: str,
        error_message: str,
        suggestions: Optional[List[str]] = None,
    ):
        """Mark job as failed.

        Args:
            job_id: Job identifier
            error_code: Error code
            error_message: Error description
            suggestions: Optional suggestions for resolution
        """
        # Update job in PostgreSQL
        async with async_session_maker() as session:
            repo = JobRepository(session)

            success = await repo.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=error_message,
                error_code=error_code,
            )

            if not success:
                logger.warning(f"Attempted to fail unknown job: {job_id}")
                return

            # Get updated job
            db_job = await repo.get_job_by_id(job_id)

        # Determine if retry is possible (max 3 retries)
        can_retry = db_job and db_job.retry_count < 3

        # Publish failure notification
        failure_data = {
            "job_id": job_id,
            "status": "failed",
            "error_code": error_code,
            "error_message": error_message,
            "suggestions": suggestions or [],
            "failed_at": (
                db_job.completed_at.timestamp() if db_job and db_job.completed_at else None
            ),
            "can_retry": can_retry,
        }

        try:
            await self.jetstream.publish(
                subject=f"{self.results_subject}.{job_id}",
                payload=json.dumps(failure_data).encode(),
            )

            logger.error(f"Job {job_id} failed: {error_message}")

        except Exception as e:
            logger.warning(f"Failed to publish failure notification: {e}")

    async def retry_job(self, job_id: str) -> bool:
        """Retry a failed job.

        Args:
            job_id: Job identifier

        Returns:
            True if job was retried, False if cannot retry
        """
        async with async_session_maker() as session:
            repo = JobRepository(session)
            db_job = await repo.get_job_by_id(job_id)

            if not db_job or db_job.status != JobStatus.FAILED.value or db_job.retry_count >= 3:
                return False

            try:
                # Increment retry count
                await repo.increment_retry_count(job_id)

                # Reset status to pending
                await repo.update_job_status(job_id, JobStatus.PENDING)

                # Resubmit to queue
                job_data = {
                    "job_id": db_job.job_id,
                    "job_type": db_job.job_type,
                    "request": db_job.request_data,
                    "user_id": db_job.user_id,
                    "priority": db_job.priority,
                    "retry_count": db_job.retry_count + 1,
                    "created_at": (
                        db_job.created_at.timestamp() if db_job.created_at else time.time()
                    ),
                }

                await self.jetstream.publish(
                    subject=self.job_queue_subject,
                    payload=json.dumps(job_data).encode(),
                    headers={"priority": str(db_job.priority), "retry": "true"},
                )

                logger.info(f"Job {job_id} retried (attempt {db_job.retry_count + 1})")
                return True

            except Exception as e:
                logger.error(f"Failed to retry job {job_id}: {e}")
                return False

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or processing job.

        Args:
            job_id: Job identifier

        Returns:
            True if job was cancelled, False if cannot cancel
        """
        async with async_session_maker() as session:
            repo = JobRepository(session)
            db_job = await repo.get_job_by_id(job_id)

            if not db_job or db_job.status in [
                JobStatus.COMPLETED.value,
                JobStatus.FAILED.value,
                JobStatus.CANCELLED.value,
            ]:
                return False

            await repo.update_job_status(job_id, JobStatus.CANCELLED)

            logger.info(f"Job {job_id} cancelled")
            return True

    async def list_jobs(
        self, user_id: Optional[UUID] = None, status: Optional[JobStatus] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List jobs with optional filtering.

        Args:
            user_id: Filter by user ID (UUID)
            status: Filter by job status
            limit: Maximum number of jobs to return

        Returns:
            List of job dictionaries
        """
        async with async_session_maker() as session:
            repo = JobRepository(session)
            db_jobs = await repo.list_jobs(user_id=user_id, status=status, limit=limit)

            return [
                {
                    "job_id": job.job_id,
                    "status": job.status,
                    "job_type": job.job_type,
                    "priority": job.priority,
                    "current_stage": job.current_stage,
                    "progress_percentage": job.progress_percentage,
                    "error_message": job.error_message,
                    "created_at": job.created_at.timestamp() if job.created_at else None,
                    "completed_at": job.completed_at.timestamp() if job.completed_at else None,
                }
                for job in db_jobs
            ]

    async def close(self):
        """Close NATS connection."""
        if self.nats_client:
            await self.nats_client.close()
            logger.info("Job service connection closed")

    # Document processing job methods
    async def publish_pdf_job(
        self,
        user_id: str,
        document_id: str,
        input_source: str,
        job_id: str,
        persona_id: Optional[str] = None,  # Add persona_id parameter
    ) -> bool:
        """Publish PDF processing job for document enrichment"""
        try:
            from uuid import UUID

            from .models import JobPriority, JobType

            # Convert user_id string to UUID if needed
            user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

            # Convert persona_id string to UUID if provided
            persona_uuid = (
                UUID(persona_id) if persona_id and isinstance(persona_id, str) else persona_id
            )

            request = JobRequest(
                job_type=JobType.PDF_PARSING,
                input_source=input_source,
                user_id=user_uuid,  # Add user_id to the request
                persona_id=persona_uuid,  # Add persona_id to the request
                priority=JobPriority.NORMAL,
                metadata={
                    "document_id": document_id,
                    "scraping_job_id": job_id,  # Changed from job_id to scraping_job_id
                    "enable_vector_creation": True,
                },
            )

            submitted_job_id = await self.submit_job(
                request, user_uuid
            )  # FIX: Pass user_uuid instead of user_id
            logger.info(
                f"PDF processing job submitted: {submitted_job_id} for user {user_id}, persona {persona_id or 'default'}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish PDF job: {e}")
            return False

    async def publish_audio_job(
        self,
        user_id: str,
        document_id: str,
        input_source: str,
        job_id: str,
        persona_id: Optional[str] = None,  # Add persona_id parameter
    ) -> bool:
        """Publish audio transcription job for document enrichment"""
        try:
            from uuid import UUID

            from .models import JobPriority, JobType

            # Convert user_id string to UUID if needed
            user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

            # Convert persona_id string to UUID if provided
            persona_uuid = (
                UUID(persona_id) if persona_id and isinstance(persona_id, str) else persona_id
            )

            request = JobRequest(
                job_type=JobType.AUDIO_TRANSCRIPTION,
                input_source=input_source,
                user_id=user_uuid,  # Add user_id to the request
                persona_id=persona_uuid,  # Add persona_id to the request
                priority=JobPriority.NORMAL,
                metadata={
                    "document_id": document_id,
                    "scraping_job_id": job_id,  # Changed from job_id to scraping_job_id
                    "enable_vector_creation": True,
                },
            )

            submitted_job_id = await self.submit_job(
                request, user_uuid
            )  # FIX: Pass user_uuid instead of user_id
            logger.info(
                f"Audio processing job submitted: {submitted_job_id} for user {user_id}, persona {persona_id or 'default'}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish audio job: {e}")
            return False

    async def publish_video_job(
        self,
        user_id: str,
        document_id: str,
        input_source: str,
        job_id: str,
        persona_id: Optional[str] = None,  # Add persona_id parameter
    ) -> bool:
        """Publish video transcription job for document enrichment"""
        try:
            from uuid import UUID

            from .models import JobPriority, JobType

            # Convert user_id string to UUID if needed
            user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

            # Convert persona_id string to UUID if provided
            persona_uuid = (
                UUID(persona_id) if persona_id and isinstance(persona_id, str) else persona_id
            )

            request = JobRequest(
                job_type=JobType.VIDEO_TRANSCRIPTION,
                input_source=input_source,
                user_id=user_uuid,  # Add user_id to the request
                persona_id=persona_uuid,  # Add persona_id to the request
                priority=JobPriority.NORMAL,
                metadata={
                    "document_id": document_id,
                    "scraping_job_id": job_id,  # Changed from job_id to scraping_job_id
                    "enable_vector_creation": True,
                },
            )

            submitted_job_id = await self.submit_job(
                request, user_uuid
            )  # FIX: Pass user_uuid instead of user_id
            logger.info(
                f"Video processing job submitted: {submitted_job_id} for user {user_id}, persona {persona_id or 'default'}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish video job: {e}")
            return False

    async def publish_text_job(
        self,
        user_id: str,
        document_id: str,
        input_source: str,
        job_id: str,
        persona_id: Optional[str] = None,
    ) -> bool:
        """Publish text document processing job (.txt, .md) for enrichment.

        Args:
            user_id: User UUID string
            document_id: Document UUID string
            input_source: S3 path to text file
            job_id: Scraping job UUID string
            persona_id: Optional persona UUID string

        Returns:
            True if job was successfully published, False otherwise
        """
        try:
            from uuid import UUID

            from .models import JobPriority, JobType

            # Convert user_id string to UUID if needed
            user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

            # Convert persona_id string to UUID if provided
            persona_uuid = (
                UUID(persona_id) if persona_id and isinstance(persona_id, str) else persona_id
            )

            request = JobRequest(
                job_type=JobType.TEXT_PROCESSING,
                input_source=input_source,
                user_id=user_uuid,
                persona_id=persona_uuid,
                priority=JobPriority.NORMAL,
                chunk_size=1000,  # Characters per chunk for text
                overlap=200,  # Character overlap between chunks
                metadata={
                    "document_id": document_id,
                    "scraping_job_id": job_id,
                    "enable_vector_creation": True,
                },
            )

            submitted_job_id = await self.submit_job(
                request, user_uuid
            )  # FIX: Pass user_uuid instead of user_id
            logger.info(
                f"Text processing job submitted: {submitted_job_id} for user {user_id}, persona {persona_id or 'default'}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish text job: {e}")
            return False


# Singleton instance
_job_service: Optional[JobService] = None


def get_queue_service() -> JobService:
    """Get singleton job service instance."""
    import os

    global _job_service
    if _job_service is None:
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        _job_service = JobService(nats_url=nats_url)
    return _job_service
