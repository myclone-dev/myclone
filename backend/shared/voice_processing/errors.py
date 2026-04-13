"""Structured error handling for voice processing operations."""

import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ErrorCategory(Enum):
    """High-level error categories for API responses."""

    VALIDATION = "validation"
    NETWORK = "network"
    PROCESSING = "processing"
    RESOURCE = "resource"
    SYSTEM = "system"
    EXTERNAL = "external"


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCode(Enum):
    """Specific error codes for detailed error handling."""

    # Validation errors
    INVALID_URL = "invalid_url"
    INVALID_FORMAT = "invalid_format"
    FILE_NOT_FOUND = "file_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    DURATION_TOO_LONG = "duration_too_long"
    FILE_TOO_LARGE = "file_too_large"

    # Network errors
    DOWNLOAD_FAILED = "download_failed"
    CONNECTION_TIMEOUT = "connection_timeout"
    NETWORK_UNREACHABLE = "network_unreachable"
    RATE_LIMITED = "rate_limited"
    FORBIDDEN_ACCESS = "forbidden_access"
    VIDEO_UNAVAILABLE = "video_unavailable"

    # Processing errors
    AUDIO_EXTRACTION_FAILED = "audio_extraction_failed"
    FORMAT_CONVERSION_FAILED = "format_conversion_failed"
    QUALITY_CHECK_FAILED = "quality_check_failed"
    SEGMENTATION_FAILED = "segmentation_failed"
    CODEC_ERROR = "codec_error"

    # Resource errors
    DISK_SPACE_FULL = "disk_space_full"
    MEMORY_EXHAUSTED = "memory_exhausted"
    TEMP_DIR_UNAVAILABLE = "temp_dir_unavailable"
    PERMISSION_DENIED = "permission_denied"

    # System errors
    FFMPEG_NOT_AVAILABLE = "ffmpeg_not_available"
    DEPENDENCY_ERROR = "dependency_error"
    CONFIGURATION_ERROR = "configuration_error"

    # External service errors
    YOUTUBE_API_ERROR = "youtube_api_error"
    THIRD_PARTY_SERVICE_ERROR = "third_party_service_error"

    # System
    SYSTEM = "system"


@dataclass
class ErrorContext:
    """Additional context information for errors."""

    operation: str
    input_data: Optional[Dict[str, Any]] = None
    stage: Optional[str] = None
    file_path: Optional[str] = None
    url: Optional[str] = None
    duration: Optional[float] = None
    file_size: Optional[int] = None
    system_info: Optional[Dict[str, Any]] = None


class VoiceProcessingError(Exception):
    """Base exception for voice processing operations with structured error information."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        category: ErrorCategory = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: ErrorContext = None,
        original_error: Exception = None,
        suggestions: List[str] = None,
    ):
        """Initialize structured error.

        Args:
            message: Human-readable error message
            error_code: Specific error code for programmatic handling
            category: High-level error category
            severity: Error severity level
            context: Additional context information
            original_error: Original exception that caused this error
            suggestions: List of suggested solutions
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.category = category or self._get_default_category(error_code)
        self.severity = severity
        self.context = context
        self.original_error = original_error
        self.suggestions = suggestions or []
        self.traceback_str = traceback.format_exc() if original_error else None

    def _get_default_category(self, error_code: ErrorCode) -> ErrorCategory:
        """Get default category based on error code."""
        validation_codes = {
            ErrorCode.INVALID_URL,
            ErrorCode.INVALID_FORMAT,
            ErrorCode.FILE_NOT_FOUND,
            ErrorCode.UNSUPPORTED_FORMAT,
            ErrorCode.DURATION_TOO_LONG,
            ErrorCode.FILE_TOO_LARGE,
        }

        network_codes = {
            ErrorCode.DOWNLOAD_FAILED,
            ErrorCode.CONNECTION_TIMEOUT,
            ErrorCode.NETWORK_UNREACHABLE,
            ErrorCode.RATE_LIMITED,
            ErrorCode.FORBIDDEN_ACCESS,
            ErrorCode.VIDEO_UNAVAILABLE,
        }

        processing_codes = {
            ErrorCode.AUDIO_EXTRACTION_FAILED,
            ErrorCode.FORMAT_CONVERSION_FAILED,
            ErrorCode.QUALITY_CHECK_FAILED,
            ErrorCode.SEGMENTATION_FAILED,
            ErrorCode.CODEC_ERROR,
        }

        resource_codes = {
            ErrorCode.DISK_SPACE_FULL,
            ErrorCode.MEMORY_EXHAUSTED,
            ErrorCode.TEMP_DIR_UNAVAILABLE,
            ErrorCode.PERMISSION_DENIED,
        }

        system_codes = {
            ErrorCode.FFMPEG_NOT_AVAILABLE,
            ErrorCode.DEPENDENCY_ERROR,
            ErrorCode.CONFIGURATION_ERROR,
        }

        external_codes = {ErrorCode.YOUTUBE_API_ERROR, ErrorCode.THIRD_PARTY_SERVICE_ERROR}

        if error_code in validation_codes:
            return ErrorCategory.VALIDATION
        elif error_code in network_codes:
            return ErrorCategory.NETWORK
        elif error_code in processing_codes:
            return ErrorCategory.PROCESSING
        elif error_code in resource_codes:
            return ErrorCategory.RESOURCE
        elif error_code in system_codes:
            return ErrorCategory.SYSTEM
        elif error_code in external_codes:
            return ErrorCategory.EXTERNAL
        else:
            return ErrorCategory.SYSTEM

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for API responses."""
        return {
            "error": True,
            "message": self.message,
            "error_code": self.error_code.value,
            "category": self.category.value,
            "severity": self.severity.value,
            "suggestions": self.suggestions,
            "context": self._serialize_context(),
            "original_error": str(self.original_error) if self.original_error else None,
        }

    def _serialize_context(self) -> Optional[Dict[str, Any]]:
        """Serialize context for JSON responses."""
        if not self.context:
            return None

        return {
            "operation": self.context.operation,
            "input_data": self.context.input_data,
            "stage": self.context.stage,
            "file_path": self.context.file_path,
            "url": self.context.url,
            "duration": self.context.duration,
            "file_size": self.context.file_size,
            "system_info": self.context.system_info,
        }

    def is_retryable(self) -> bool:
        """Check if this error indicates a retryable operation."""
        retryable_codes = {
            ErrorCode.CONNECTION_TIMEOUT,
            ErrorCode.NETWORK_UNREACHABLE,
            ErrorCode.RATE_LIMITED,
            ErrorCode.DOWNLOAD_FAILED,
            ErrorCode.MEMORY_EXHAUSTED,
        }
        return self.error_code in retryable_codes


class ErrorHandler:
    """Centralized error handling and classification."""

    @staticmethod
    def handle_youtube_error(original_error: Exception, url: str) -> VoiceProcessingError:
        """Convert yt-dlp errors to structured errors."""
        error_msg = str(original_error).lower()

        if "private video" in error_msg or "video unavailable" in error_msg:
            return VoiceProcessingError(
                message=f"Video is unavailable or private: {url}",
                error_code=ErrorCode.VIDEO_UNAVAILABLE,
                context=ErrorContext(operation="youtube_download", url=url),
                original_error=original_error,
                suggestions=["Check if the video is public and accessible"],
            )

        elif "network" in error_msg or "connection" in error_msg:
            return VoiceProcessingError(
                message=f"Network error while downloading video: {str(original_error)}",
                error_code=ErrorCode.CONNECTION_TIMEOUT,
                context=ErrorContext(operation="youtube_download", url=url),
                original_error=original_error,
                suggestions=["Check internet connection", "Try again in a few minutes"],
            )

        elif "format" in error_msg:
            return VoiceProcessingError(
                message=f"No suitable audio format available for video: {url}",
                error_code=ErrorCode.UNSUPPORTED_FORMAT,
                context=ErrorContext(operation="youtube_download", url=url),
                original_error=original_error,
                suggestions=["Try a different video", "Video may have restricted audio formats"],
            )

        else:
            return VoiceProcessingError(
                message=f"YouTube download failed: {str(original_error)}",
                error_code=ErrorCode.DOWNLOAD_FAILED,
                context=ErrorContext(operation="youtube_download", url=url),
                original_error=original_error,
                suggestions=["Check video URL", "Try again later"],
            )

    @staticmethod
    def handle_ffmpeg_error(
        original_error: Exception, input_path: str, operation: str
    ) -> VoiceProcessingError:
        """Convert FFmpeg errors to structured errors."""
        error_msg = str(original_error).lower()

        if "no such file" in error_msg or "file not found" in error_msg:
            return VoiceProcessingError(
                message=f"Input file not found: {input_path}",
                error_code=ErrorCode.FILE_NOT_FOUND,
                context=ErrorContext(operation=operation, file_path=input_path),
                original_error=original_error,
                suggestions=["Check file path", "Ensure file exists"],
            )

        elif "permission denied" in error_msg:
            return VoiceProcessingError(
                message=f"Permission denied accessing file: {input_path}",
                error_code=ErrorCode.PERMISSION_DENIED,
                context=ErrorContext(operation=operation, file_path=input_path),
                original_error=original_error,
                suggestions=["Check file permissions", "Ensure write access to output directory"],
            )

        elif "codec" in error_msg or "format" in error_msg:
            return VoiceProcessingError(
                message=f"Audio codec or format error: {str(original_error)}",
                error_code=ErrorCode.CODEC_ERROR,
                context=ErrorContext(operation=operation, file_path=input_path),
                original_error=original_error,
                suggestions=["File may be corrupted", "Try converting to a different format"],
            )

        else:
            return VoiceProcessingError(
                message=f"Audio processing failed: {str(original_error)}",
                error_code=ErrorCode.AUDIO_EXTRACTION_FAILED,
                context=ErrorContext(operation=operation, file_path=input_path),
                original_error=original_error,
                suggestions=["Check input file integrity", "Try with a different audio file"],
            )

    @staticmethod
    def handle_validation_error(
        message: str, error_code: ErrorCode, context_data: Dict[str, Any] = None
    ) -> VoiceProcessingError:
        """Create validation error with appropriate suggestions."""
        suggestions = []

        if error_code == ErrorCode.INVALID_URL:
            suggestions = [
                "Ensure URL is a valid YouTube link",
                "Check for typos in the URL",
                "Try copying the URL directly from YouTube",
            ]
        elif error_code == ErrorCode.DURATION_TOO_LONG:
            suggestions = [
                "Use a shorter video (under 2 hours)",
                "Consider using time-based segmentation",
            ]
        elif error_code == ErrorCode.FILE_TOO_LARGE:
            suggestions = ["Use a smaller file", "Compress the audio file before processing"]

        return VoiceProcessingError(
            message=message,
            error_code=error_code,
            context=ErrorContext(operation="validation", input_data=context_data),
            suggestions=suggestions,
        )
