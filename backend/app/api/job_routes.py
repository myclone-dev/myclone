"""
Unified Job Status API Routes

This module provides a generic, unified interface for tracking job status
across ALL job types in the system (scraping, document processing, etc.)

Endpoints:
- GET /api/v1/jobs/{user_id} - Get all jobs for a user
- GET /api/v1/jobs/{user_id}/{job_id} - Get specific job by ID
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.auth.optimized_middleware import require_jwt_or_api_key
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["Job Status"])


# =============================================================================
# Response Models
# =============================================================================


class JobStatusResponse(BaseModel):
    """Unified job status response for all job types"""

    job_id: UUID
    user_id: UUID
    source_type: str  # linkedin, twitter, website, pdf, document, youtube
    status: str  # queued, pending, processing, completed, failed
    provider: Optional[str] = None  # scrapingdog, firecrawl, etc.
    error_message: Optional[str] = None

    # Progress metrics
    records_imported: int = 0
    posts_imported: int = 0
    experiences_imported: int = 0
    pages_imported: int = 0

    # Timestamps
    started_at: str
    completed_at: Optional[str] = None

    # Reference IDs (for fetching related data)
    linkedin_profile_id: Optional[UUID] = None
    twitter_profile_id: Optional[UUID] = None
    website_metadata_id: Optional[UUID] = None
    document_id: Optional[UUID] = None
    youtube_video_id: Optional[UUID] = None

    # Metadata (for displaying source details)
    source_name: Optional[str] = None  # Filename, URL, profile name, etc.
    file_type: Optional[str] = None  # audio, video, pdf for document uploads

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "source_type": "linkedin",
                "status": "completed",
                "provider": "scrapingdog",
                "error_message": None,
                "records_imported": 1,
                "posts_imported": 25,
                "experiences_imported": 5,
                "pages_imported": 0,
                "started_at": "2025-10-20T12:34:56.789Z",
                "completed_at": "2025-10-20T12:35:30.123Z",
                "linkedin_profile_id": "456e7890-e89b-12d3-a456-426614174000",
            }
        }


class JobListResponse(BaseModel):
    """Response with list of jobs and summary"""

    user_id: UUID
    total_jobs: int
    active_jobs: int  # queued, pending, or processing
    completed_jobs: int
    failed_jobs: int
    jobs: List[JobStatusResponse]


# =============================================================================
# API Endpoints
# =============================================================================


@router.get("/{user_id}", response_model=JobListResponse)
async def get_all_user_jobs(
    user_id: UUID,
    source_type: Optional[str] = Query(
        None,
        description="Filter by source type (linkedin, twitter, website, pdf, document, youtube)",
    ),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by status (queued, pending, processing, completed, failed)",
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of jobs to return"),
    auth_result: dict = Depends(require_jwt_or_api_key),
):
    """
    Get all jobs for a user with optional filtering

    This is the **unified endpoint** for tracking all job types:
    - LinkedIn scraping
    - Twitter scraping
    - Website scraping
    - PDF/Document processing
    - YouTube ingestion
    - Auto-onboarding (multiple jobs)

    **Authentication:**
    Supports multiple authentication methods:
    - JWT token (via myclone_token cookie) - for authenticated users
    - Widget token (via Bearer token starting with wgt_)
    - API key (via Bearer token or X-API-Key header)

    **Authorization:**
    - JWT users can only access their own jobs (user_id must match authenticated user)
    - API key/Widget token users can access any user's jobs

    **Use Cases:**
    - Dashboard view (all jobs)
    - Monitoring active jobs
    - Job history

    **Query Parameters:**
    - `source_type`: Filter by job type (optional)
    - `status`: Filter by status (optional)
    - `limit`: Max jobs to return (default: 50, max: 100)

    **Response:**
    - Summary: total_jobs, active_jobs, completed_jobs, failed_jobs
    - List: All jobs matching filters

    **Example:**
    ```bash
    # With JWT token (cookie automatically sent by browser)
    curl "http://localhost:8000/api/v1/jobs/USER_ID" \
      --cookie "myclone_token=YOUR_JWT_TOKEN"

    # With API key
    curl "http://localhost:8000/api/v1/jobs/USER_ID" \
      -H "Authorization: Bearer YOUR_API_KEY"

    # Filter by type
    curl "http://localhost:8000/api/v1/jobs/USER_ID?source_type=linkedin" \
      -H "Authorization: Bearer YOUR_API_KEY"
    ```
    """
    try:
        # Authorization: If JWT authenticated, ensure user can only access their own jobs
        auth_type = auth_result.get("type")
        if auth_type == "jwt":
            authenticated_user = auth_result.get("data", {}).get("user")
            if authenticated_user and str(authenticated_user.id) != str(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only access your own jobs",
                )
        # Scraping infrastructure has been removed; return empty job list
        return JobListResponse(
            user_id=user_id,
            total_jobs=0,
            active_jobs=0,
            completed_jobs=0,
            failed_jobs=0,
            jobs=[],
        )

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user_id),
                "source_type_filter": source_type,
                "status_filter": status_filter,
            },
            tags={
                "component": "job_routes",
                "operation": "get_all_user_jobs",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"Failed to get jobs for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve jobs: {str(e)}",
        )


@router.get("/{user_id}/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    user_id: UUID,
    job_id: UUID,
    auth_result: dict = Depends(require_jwt_or_api_key),
):
    """
    Get specific job status by ID

    This endpoint returns detailed status for a single job.
    It verifies that the job belongs to the specified user for security.

    **Authentication:**
    Supports multiple authentication methods:
    - JWT token (via myclone_token cookie) - for authenticated users
    - Widget token (via Bearer token starting with wgt_)
    - API key (via Bearer token or X-API-Key header)

    **Authorization:**
    - JWT users can only access their own jobs (user_id must match authenticated user)
    - API key/Widget token users can access any user's jobs
    - All users: job must belong to the specified user_id

    **Use Cases:**
    - Track specific job progress
    - Poll for job completion
    - Get job results after completion

    **Example:**
    ```bash
    # With JWT token (cookie automatically sent by browser)
    curl "http://localhost:8000/api/v1/jobs/USER_ID/JOB_ID" \
      --cookie "myclone_token=YOUR_JWT_TOKEN"

    # With API key
    curl "http://localhost:8000/api/v1/jobs/USER_ID/JOB_ID" \
      -H "Authorization: Bearer YOUR_API_KEY"
    ```

    **Polling Pattern:**
    ```javascript
    async function pollJob(userId, jobId) {
      while (true) {
        const res = await fetch(`/api/v1/jobs/${userId}/${jobId}`, {
          credentials: 'include' // Send cookies for JWT auth
        });
        const job = await res.json();

        console.log('Status:', job.status);

        if (job.status === 'completed' || job.status === 'failed') {
          return job; // Done!
        }

        await new Promise(r => setTimeout(r, 2000)); // Wait 2s
      }
    }
    ```
    """
    try:
        # Authorization: If JWT authenticated, ensure user can only access their own jobs
        auth_type = auth_result.get("type")
        if auth_type == "jwt":
            authenticated_user = auth_result.get("data", {}).get("user")
            if authenticated_user and str(authenticated_user.id) != str(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only access your own jobs",
                )
        # Scraping infrastructure has been removed; job tracking is no longer available
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "job_id": str(job_id),
                "user_id": str(user_id),
            },
            tags={
                "component": "job_routes",
                "operation": "get_job_status",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"Failed to get job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve job: {str(e)}",
        )
