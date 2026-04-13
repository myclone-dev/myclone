"""Data models for voice processing API."""

import time
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID


class JobType(Enum):
    """Types of processing jobs."""

    VOICE_EXTRACTION = "voice_extraction"
    TRANSCRIPT_EXTRACTION = "transcript_extraction"
    COMBINED_PROCESSING = "combined_processing"  # Both voice + transcript
    PDF_PARSING = "pdf_parsing"  # PDF parsing and chunking
    AUDIO_TRANSCRIPTION = "audio_transcription"  # Audio transcription and chunking
    VIDEO_TRANSCRIPTION = "video_transcription"  # Video transcription and chunking
    YOUTUBE_INGESTION = "youtube_ingestion"  # YouTube video transcript ingestion
    TEXT_PROCESSING = "text_processing"  # Text document (.txt, .md) processing


class JobStatus(Enum):
    """Job processing status."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Job priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ProcessingStage(Enum):
    """Current processing stage for detailed progress."""

    VALIDATION = "validation"
    DOWNLOAD = "download"
    CONVERSION = "conversion"
    VOICE_EXTRACTION = "voice_extraction"
    TRANSCRIPT_EXTRACTION = "transcript_extraction"
    SEGMENTATION = "segmentation"
    QUALITY_CHECK = "quality_check"
    PDF_PARSING = "pdf_parsing"
    CHUNK_CREATION = "chunk_creation"
    CHUNK_ENRICHMENT = "chunk_enrichment"
    CLEANUP = "cleanup"
    COMPLETED = "completed"


@dataclass
class JobRequest:
    """Request payload for creating a new processing job."""

    job_type: JobType
    input_source: str  # YouTube URL or file path
    user_id: Optional[UUID] = None
    priority: JobPriority = JobPriority.NORMAL

    # Voice extraction options
    output_format: str = "wav"
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

    # PDF parsing options
    persona_id: Optional[UUID] = None  # For PDF parsing jobs
    chunk_size: int = 1000  # Words per chunk
    overlap: int = 200  # Word overlap between chunks
    enhance_images: bool = False  # Use AI to enhance image descriptions

    # Processing options
    max_duration_seconds: Optional[int] = None  # Limit processing time
    webhook_url: Optional[str] = None  # Callback URL for completion
    metadata: Optional[Dict[str, Any]] = (
        None  # Additional metadata for processing (document_id, enable_vector_creation, etc.)
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert enums to strings for JSON serialization
        data["job_type"] = self.job_type.value
        data["priority"] = self.priority.value
        # Convert UUID to string for JSON serialization
        if self.user_id is not None:
            data["user_id"] = str(self.user_id)
        if self.persona_id is not None:
            data["persona_id"] = str(self.persona_id)
        return data


@dataclass
class JobProgress:
    """Current job progress information."""

    job_id: str
    stage: ProcessingStage
    percentage: float  # 0.0 to 100.0
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from datetime import datetime

        def serialize_value(obj):
            """Custom serializer for datetime and other non-JSON types."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, Enum):  # Handle Enum types
                return obj.value
            elif hasattr(obj, "isoformat"):  # Handle other datetime-like objects
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: serialize_value(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_value(item) for item in obj]
            else:
                return obj

        # Convert to dict and serialize datetime objects
        data = asdict(self)
        data["stage"] = self.stage.value
        return serialize_value(data)


@dataclass
class JobResult:
    """Results from completed job processing."""

    # Common results
    success: bool
    processing_time_seconds: float
    input_info: Dict[str, Any]  # Original video/audio metadata

    # Voice extraction results
    voice_files: Optional[List[Dict[str, Any]]] = None  # List of extracted audio files
    voice_quality_score: Optional[float] = None

    # Transcript extraction results (for future)
    transcript_text: Optional[str] = None
    transcript_file: Optional[str] = None
    transcript_segments: Optional[List[Dict[str, Any]]] = None

    # PDF parsing results
    pdf_chunks: Optional[List[Dict[str, Any]]] = None  # List of parsed PDF chunks
    pdf_stats: Optional[Dict[str, Any]] = None  # Statistics about PDF processing

    # Audio/Video transcription results
    transcript_chunks: Optional[List[Dict[str, Any]]] = (
        None  # List of timestamped transcript chunks
    )
    transcript_stats: Optional[Dict[str, Any]] = None  # Statistics about transcription processing

    # Error information (if failed)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_suggestions: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        from datetime import datetime

        def serialize_value(obj):
            """Custom serializer for datetime and other non-JSON types."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif hasattr(obj, "isoformat"):  # Handle other datetime-like objects
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: serialize_value(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_value(item) for item in obj]
            else:
                return obj

        # Convert to dict and serialize datetime objects
        data = asdict(self)
        return serialize_value(data)


@dataclass
class Job:
    """Complete job information including metadata and state."""

    job_id: str
    job_type: JobType
    status: JobStatus
    created_at: float
    user_id: Optional[UUID] = None
    priority: JobPriority = JobPriority.NORMAL

    # Request data
    request: Optional[JobRequest] = None

    # Progress tracking
    current_stage: Optional[ProcessingStage] = None
    progress_percentage: float = 0.0
    progress_message: Optional[str] = None
    last_updated: Optional[float] = None

    # Timing information
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    processing_time_seconds: Optional[float] = None

    # Results
    result: Optional[JobResult] = None

    # Worker information
    worker_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    def __post_init__(self):
        if self.last_updated is None:
            self.last_updated = self.created_at

    @classmethod
    def create_new(cls, request: JobRequest, user_id: Optional[UUID] = None) -> "Job":
        """Create a new job from a request."""
        job_id = str(uuid.uuid4())
        now = time.time()

        return cls(
            job_id=job_id,
            job_type=request.job_type,
            status=JobStatus.PENDING,
            created_at=now,
            user_id=user_id,
            priority=request.priority,
            request=request,
            current_stage=ProcessingStage.VALIDATION,
            progress_message="Job created, waiting to start",
        )

    def update_progress(
        self,
        stage: ProcessingStage,
        percentage: float,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Update job progress."""
        self.current_stage = stage
        self.progress_percentage = percentage
        self.progress_message = message
        self.last_updated = time.time()

        if stage == ProcessingStage.COMPLETED:
            self.status = JobStatus.COMPLETED
            self.completed_at = self.last_updated
            if self.started_at:
                self.processing_time_seconds = self.last_updated - self.started_at

    def start_processing(self, worker_id: str):
        """Mark job as started by a worker."""
        self.status = JobStatus.PROCESSING
        self.worker_id = worker_id
        self.started_at = time.time()
        self.last_updated = self.started_at

    def mark_failed(
        self, error_code: str, error_message: str, suggestions: Optional[List[str]] = None
    ):
        """Mark job as failed."""
        self.status = JobStatus.FAILED
        self.completed_at = time.time()
        self.last_updated = self.completed_at

        if self.started_at:
            self.processing_time_seconds = self.completed_at - self.started_at

        self.result = JobResult(
            success=False,
            processing_time_seconds=self.processing_time_seconds or 0,
            input_info={},
            error_code=error_code,
            error_message=error_message,
            error_suggestions=suggestions or [],
        )

    def mark_completed(self, result: JobResult):
        """Mark job as completed with results."""
        self.status = JobStatus.COMPLETED
        self.completed_at = time.time()
        self.last_updated = self.completed_at
        self.current_stage = ProcessingStage.COMPLETED
        self.progress_percentage = 100.0
        self.progress_message = "Processing completed successfully"

        if self.started_at:
            self.processing_time_seconds = self.completed_at - self.started_at
            result.processing_time_seconds = self.processing_time_seconds

        self.result = result

    def can_retry(self) -> bool:
        """Check if job can be retried."""
        return self.status == JobStatus.FAILED and self.retry_count < self.max_retries

    def retry(self):
        """Prepare job for retry."""
        if not self.can_retry():
            raise ValueError("Job cannot be retried")

        self.retry_count += 1
        self.status = JobStatus.PENDING
        self.current_stage = ProcessingStage.VALIDATION
        self.progress_percentage = 0.0
        self.progress_message = f"Retrying job (attempt {self.retry_count + 1})"
        self.worker_id = None
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.last_updated = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)

        # Convert enums to strings
        data["job_type"] = self.job_type.value
        data["status"] = self.status.value
        data["priority"] = self.priority.value

        if self.current_stage:
            data["current_stage"] = self.current_stage.value

        if self.request:
            data["request"]["job_type"] = self.request.job_type.value
            data["request"]["priority"] = self.request.priority.value

        return data

    def to_public_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for public API responses (excludes internal fields)."""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at,
            "current_stage": self.current_stage.value if self.current_stage else None,
            "progress_percentage": self.progress_percentage,
            "progress_message": self.progress_message,
            "last_updated": self.last_updated,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "processing_time_seconds": self.processing_time_seconds,
            "result": self.result.to_dict() if self.result else None,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }


@dataclass
class JobStats:
    """System-wide job statistics."""

    total_jobs: int
    pending_jobs: int
    processing_jobs: int
    completed_jobs: int
    failed_jobs: int
    average_processing_time: float
    active_workers: int
    queue_length: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
