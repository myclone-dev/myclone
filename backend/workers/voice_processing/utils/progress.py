"""Progress tracking system for voice processing operations."""

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional


class ProgressStatus(Enum):
    """Progress status types."""

    STARTING = "starting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProgressStage(Enum):
    """Processing stages for voice extraction."""

    VALIDATION = "validation"
    DOWNLOAD = "download"
    CONVERSION = "conversion"
    SEGMENTATION = "segmentation"
    QUALITY_CHECK = "quality_check"
    CLEANUP = "cleanup"


@dataclass
class ProgressUpdate:
    """Structured progress update information."""

    stage: ProgressStage
    status: ProgressStatus
    percentage: float  # 0.0 to 100.0
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class ProgressTracker:
    """Track and report progress for voice processing operations."""

    def __init__(self, callback: Optional[Callable[[ProgressUpdate], None]] = None):
        """Initialize progress tracker.

        Args:
            callback: Optional callback function to receive progress updates
        """
        self.callback = callback
        self.current_stage = None
        self.start_time = time.time()
        self.stage_start_time = None

    def start_stage(self, stage: ProgressStage, message: str = None):
        """Start a new processing stage.

        Args:
            stage: The processing stage being started
            message: Optional message describing the stage
        """
        self.current_stage = stage
        self.stage_start_time = time.time()

        if message is None:
            message = f"Starting {stage.value}"

        self._send_update(stage, ProgressStatus.STARTING, 0.0, message)

    def update_progress(
        self, percentage: float, message: str = None, details: Dict[str, Any] = None
    ):
        """Update progress within the current stage.

        Args:
            percentage: Progress percentage (0.0 to 100.0)
            message: Optional progress message
            details: Optional additional details
        """
        if self.current_stage is None:
            raise ValueError("No stage started. Call start_stage() first.")

        if message is None:
            message = f"Processing {self.current_stage.value}: {percentage:.1f}%"

        self._send_update(
            self.current_stage, ProgressStatus.IN_PROGRESS, percentage, message, details
        )

    def complete_stage(self, message: str = None, details: Dict[str, Any] = None):
        """Complete the current stage.

        Args:
            message: Optional completion message
            details: Optional completion details
        """
        if self.current_stage is None:
            raise ValueError("No stage started. Call start_stage() first.")

        if message is None:
            elapsed = time.time() - self.stage_start_time if self.stage_start_time else 0
            message = f"Completed {self.current_stage.value} in {elapsed:.1f}s"

        self._send_update(self.current_stage, ProgressStatus.COMPLETED, 100.0, message, details)

        self.current_stage = None
        self.stage_start_time = None

    def fail_stage(self, message: str, details: Dict[str, Any] = None):
        """Mark the current stage as failed.

        Args:
            message: Failure message
            details: Optional failure details
        """
        if self.current_stage is None:
            raise ValueError("No stage started. Call start_stage() first.")

        self._send_update(self.current_stage, ProgressStatus.FAILED, 0.0, message, details)

        self.current_stage = None
        self.stage_start_time = None

    def _send_update(
        self,
        stage: ProgressStage,
        status: ProgressStatus,
        percentage: float,
        message: str,
        details: Dict[str, Any] = None,
    ):
        """Send progress update to callback if configured.

        Args:
            stage: Current processing stage
            status: Progress status
            percentage: Progress percentage
            message: Progress message
            details: Optional additional details
        """
        if self.callback:
            update = ProgressUpdate(
                stage=stage, status=status, percentage=percentage, message=message, details=details
            )

            try:
                self.callback(update)
            except Exception:
                # Don't let callback failures break the main process
                pass


class DownloadProgressHook:
    """Progress hook for yt-dlp downloads."""

    def __init__(self, progress_tracker: ProgressTracker):
        """Initialize download progress hook.

        Args:
            progress_tracker: Progress tracker to report to
        """
        self.progress_tracker = progress_tracker

    def __call__(self, d: Dict[str, Any]):
        """yt-dlp progress hook callback.

        Args:
            d: yt-dlp progress dictionary
        """
        try:
            status = d.get("status")

            if status == "downloading":
                # Calculate percentage
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)

                if total > 0:
                    percentage = (downloaded / total) * 100.0
                else:
                    percentage = 0.0

                # Format download details
                speed = d.get("speed", 0)
                eta = d.get("eta", 0)

                details = {
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "speed_bps": speed,
                    "eta_seconds": eta,
                }

                # Create human-readable message
                if speed and speed > 0:
                    speed_mb = speed / (1024 * 1024)
                    message = f"Downloading: {percentage:.1f}% at {speed_mb:.1f} MB/s"
                else:
                    message = f"Downloading: {percentage:.1f}%"

                self.progress_tracker.update_progress(percentage, message, details)

            elif status == "finished":
                file_path = d.get("filename", "audio file")
                total_bytes = d.get("total_bytes", 0)
                details = {"file_path": file_path, "total_bytes": total_bytes}

                message = f"Download completed: {file_path}"
                self.progress_tracker.complete_stage(message, details)

        except Exception:
            # Don't let progress tracking break downloads
            pass
