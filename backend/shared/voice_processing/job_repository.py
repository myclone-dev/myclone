"""Repository for voice processing job database operations.

This repository provides a clean interface for CRUD operations on voice processing jobs,
abstracting the database layer from the JobService and Worker.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.voice_job_model import VoiceProcessingJob
from shared.voice_processing.models import JobPriority, JobStatus, JobType


class JobRepository:
    """Repository for managing voice processing jobs in PostgreSQL."""

    def __init__(self, session: AsyncSession):
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session for database operations
        """
        self.session = session

    async def create_job(
        self,
        job_id: str,
        job_type: JobType,
        request_data: Dict[str, Any],
        user_id: Optional[UUID] = None,
        priority: JobPriority = JobPriority.NORMAL,
    ) -> VoiceProcessingJob:
        """Create a new voice processing job.

        Args:
            job_id: Unique job identifier
            job_type: Type of job (VOICE_EXTRACTION, etc.)
            request_data: Complete job request data as dict
            user_id: Optional user identifier
            priority: Job priority level

        Returns:
            Created VoiceProcessingJob instance
        """
        job = VoiceProcessingJob(
            job_id=job_id,
            job_type=job_type.value,
            status=JobStatus.PENDING.value,
            priority=priority.value,
            request_data=request_data,
            user_id=user_id,
        )

        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)

        return job

    async def get_job_by_id(self, job_id: str) -> Optional[VoiceProcessingJob]:
        """Get job by job_id.

        Args:
            job_id: Job identifier

        Returns:
            VoiceProcessingJob if found, None otherwise
        """
        result = await self.session.execute(
            select(VoiceProcessingJob).where(VoiceProcessingJob.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        worker_id: Optional[str] = None,
    ) -> bool:
        """Update job status.

        Args:
            job_id: Job identifier
            status: New job status
            error_message: Optional error message (for failed status)
            error_code: Optional error code (for failed status)
            worker_id: Optional worker identifier

        Returns:
            True if updated, False if job not found
        """
        update_data = {"status": status.value, "updated_at": datetime.now(timezone.utc)}

        if status == JobStatus.PROCESSING and not worker_id:
            raise ValueError("worker_id required when setting status to PROCESSING")

        if status == JobStatus.PROCESSING:
            update_data["started_at"] = datetime.now(timezone.utc)
            update_data["worker_id"] = worker_id

        if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            update_data["completed_at"] = datetime.now(timezone.utc)

        if error_message:
            update_data["error_message"] = error_message
        if error_code:
            update_data["error_code"] = error_code

        result = await self.session.execute(
            update(VoiceProcessingJob)
            .where(VoiceProcessingJob.job_id == job_id)
            .values(**update_data)
        )
        await self.session.commit()

        return result.rowcount > 0

    async def update_job_progress(
        self,
        job_id: str,
        current_stage: str,
        progress_percentage: int,
        stage_details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update job progress information.

        Args:
            job_id: Job identifier
            current_stage: Current processing stage
            progress_percentage: Progress percentage (0-100)
            stage_details: Optional stage-specific details

        Returns:
            True if updated, False if job not found
        """
        update_data = {
            "current_stage": current_stage,
            "progress_percentage": progress_percentage,
            "updated_at": datetime.now(timezone.utc),
        }

        if stage_details:
            update_data["stage_details"] = stage_details

        result = await self.session.execute(
            update(VoiceProcessingJob)
            .where(VoiceProcessingJob.job_id == job_id)
            .values(**update_data)
        )
        await self.session.commit()

        return result.rowcount > 0

    async def update_job_result(self, job_id: str, result: Dict[str, Any]) -> bool:
        """Update job result data.

        Args:
            job_id: Job identifier
            result: Result data (file paths, metadata, etc.)

        Returns:
            True if updated, False if job not found
        """
        result_update = await self.session.execute(
            update(VoiceProcessingJob)
            .where(VoiceProcessingJob.job_id == job_id)
            .values(result=result, updated_at=datetime.now(timezone.utc))
        )
        await self.session.commit()

        return result_update.rowcount > 0

    async def update_job_request_data(self, job_id: str, request_data: Dict[str, Any]) -> bool:
        """Update job request data (e.g., after S3 upload).

        Args:
            job_id: Job identifier
            request_data: Updated request data

        Returns:
            True if updated, False if job not found
        """
        request_update = await self.session.execute(
            update(VoiceProcessingJob)
            .where(VoiceProcessingJob.job_id == job_id)
            .values(request_data=request_data, updated_at=datetime.now(timezone.utc))
        )
        await self.session.commit()

        return request_update.rowcount > 0

    async def increment_retry_count(self, job_id: str) -> bool:
        """Increment job retry count.

        Args:
            job_id: Job identifier

        Returns:
            True if updated, False if job not found
        """
        job = await self.get_job_by_id(job_id)
        if not job:
            return False

        result = await self.session.execute(
            update(VoiceProcessingJob)
            .where(VoiceProcessingJob.job_id == job_id)
            .values(retry_count=job.retry_count + 1, updated_at=datetime.now(timezone.utc))
        )
        await self.session.commit()

        return result.rowcount > 0

    async def list_jobs(
        self,
        user_id: Optional[UUID] = None,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[VoiceProcessingJob]:
        """List jobs with optional filtering.

        Args:
            user_id: Optional filter by user (UUID)
            status: Optional filter by status
            limit: Maximum number of jobs to return
            offset: Offset for pagination

        Returns:
            List of VoiceProcessingJob instances
        """
        query = select(VoiceProcessingJob)

        # Apply filters
        filters = []
        if user_id:
            filters.append(VoiceProcessingJob.user_id == user_id)
        if status:
            filters.append(VoiceProcessingJob.status == status.value)

        if filters:
            query = query.where(and_(*filters))

        # Order by created_at descending (newest first)
        query = query.order_by(VoiceProcessingJob.created_at.desc())

        # Apply pagination
        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_pending_jobs(self, limit: int = 10) -> List[VoiceProcessingJob]:
        """Get pending jobs ordered by priority and creation time.

        Used by workers to fetch jobs from the queue.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of pending VoiceProcessingJob instances
        """
        result = await self.session.execute(
            select(VoiceProcessingJob)
            .where(VoiceProcessingJob.status == JobStatus.PENDING.value)
            .order_by(
                # SQLAlchemy case expression for priority ordering
                VoiceProcessingJob.priority,
                VoiceProcessingJob.created_at.asc(),
            )
            .limit(limit)
        )

        return list(result.scalars().all())

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job from the database.

        Args:
            job_id: Job identifier

        Returns:
            True if deleted, False if job not found
        """
        job = await self.get_job_by_id(job_id)
        if not job:
            return False

        await self.session.delete(job)
        await self.session.commit()

        return True

    async def get_job_count_by_status(self) -> Dict[str, int]:
        """Get count of jobs grouped by status.

        Returns:
            Dictionary mapping status to count
        """
        from sqlalchemy import func

        result = await self.session.execute(
            select(VoiceProcessingJob.status, func.count(VoiceProcessingJob.id)).group_by(
                VoiceProcessingJob.status
            )
        )

        return {row[0]: row[1] for row in result.all()}
