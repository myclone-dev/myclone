"""YouTube video processing and audio extraction."""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

import yt_dlp
from extractors.audio_extractor import AudioExtractor
from loguru import logger
from utils.config import config
from utils.filename_utils import FilenameGenerator
from utils.progress import DownloadProgressHook, ProgressStage, ProgressTracker

from shared.voice_processing.errors import (
    ErrorCode,
    ErrorContext,
    ErrorHandler,
    VoiceProcessingError,
)


class YouTubeExtractor:
    """Download and extract audio from YouTube videos."""

    def __init__(self, progress_tracker: Optional[ProgressTracker] = None):
        """Initialize YouTube extractor.

        Args:
            progress_tracker: Optional progress tracker for monitoring operations
        """
        self.youtube_config = config.get_youtube_config()
        self.temp_dir = config.get_temp_dir()
        self.audio_extractor = AudioExtractor(progress_tracker)
        self.progress_tracker = progress_tracker

        # Setup YouTube proxy configuration - used for bypassing IP-based bot detection
        from shared.config import settings

        self.proxy = settings.youtube_proxy if settings.youtube_proxy else None
        if self.proxy:
            logger.info("✓ YouTube residential proxy configured")
        else:
            logger.warning("⚠ No YouTube proxy configured - may encounter bot detection on AWS IPs")

    def extract_audio_from_url(self, url: str, output_path: str = None) -> str:
        """Download YouTube video and extract audio.

        Args:
            url: YouTube video URL
            output_path: Path for output audio file (optional)

        Returns:
            Path to extracted audio file

        Raises:
            VoiceProcessingError: If any step fails with structured error information
        """
        # Start validation stage
        if self.progress_tracker:
            self.progress_tracker.start_stage(ProgressStage.VALIDATION, "Validating YouTube URL")

        try:
            # Validate URL
            if not self._is_valid_youtube_url(url):
                # Provide specific error message for Apple Podcasts
                if "podcasts.apple.com" in url:
                    raise ErrorHandler.handle_validation_error(
                        f"Invalid Apple Podcasts URL: {url}. Episode URLs must include ?i=<episode_id> parameter.",
                        ErrorCode.INVALID_URL,
                        {
                            "url": url,
                            "hint": "Navigate to a specific episode and copy the URL with ?i= parameter",
                        },
                    )
                else:
                    raise ErrorHandler.handle_validation_error(
                        f"Invalid media URL format: {url}. URL must start with http:// or https://",
                        ErrorCode.INVALID_URL,
                        {"url": url},
                    )

            logger.info(f"Processing media URL: {url}")

            # Get video info first
            video_info = self.get_video_info(url)

            # Generate clean base name from URL (not title)
            base_name = FilenameGenerator.from_youtube_url(url, video_info)

            # Check video length
            duration = video_info.get("duration", 0)
            max_length = self.youtube_config.get("max_length", 7200)
            if duration > max_length:
                raise ErrorHandler.handle_validation_error(
                    f"Video too long: {duration}s (max: {max_length}s)",
                    ErrorCode.DURATION_TOO_LONG,
                    {"duration": duration, "max_length": max_length, "url": url},
                )

            # Generate output path if not provided
            if output_path is None:
                output_dir = config.get_output_dir("raw")
                output_path = output_dir / f"{base_name}.wav"

            output_path = Path(output_path)

            if self.progress_tracker:
                self.progress_tracker.complete_stage("URL validation completed")

            # Download audio-only stream
            temp_audio_path = self._download_audio(url, base_name)

            # Start conversion stage
            if self.progress_tracker:
                self.progress_tracker.start_stage(
                    ProgressStage.CONVERSION, "Processing audio format"
                )

            # Check if format conversion is needed for standardization
            downloaded_format = temp_audio_path.suffix.lower().lstrip(".")
            target_format = output_path.suffix.lower().lstrip(".")

            if downloaded_format != target_format or downloaded_format not in ["wav", "mp3", "m4a"]:
                logger.info(f"Converting audio from {downloaded_format} to {target_format} format")
                final_audio_path = self.audio_extractor.convert_audio_format(
                    str(temp_audio_path), str(output_path), target_format
                )
                # Clean up temporary file
                temp_audio_path.unlink(missing_ok=True)
            else:
                # Audio is already in acceptable format, just move to final location
                logger.info(
                    f"Audio already in {downloaded_format} format, moving to final location"
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                temp_audio_path.rename(output_path)
                final_audio_path = str(output_path)

            if self.progress_tracker:
                self.progress_tracker.complete_stage("Audio extraction completed")

            logger.success(f"YouTube audio-only extraction completed: {final_audio_path}")
            return final_audio_path

        except VoiceProcessingError:
            # Re-raise structured errors
            if self.progress_tracker and self.progress_tracker.current_stage:
                self.progress_tracker.fail_stage("Operation failed")
            raise
        except Exception as e:
            # Convert unexpected errors to structured errors
            error = ErrorHandler.handle_youtube_error(e, url)
            if self.progress_tracker and self.progress_tracker.current_stage:
                self.progress_tracker.fail_stage(f"Unexpected error: {str(e)}")
            logger.error(f"YouTube extraction failed: {error.message}")
            raise error

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get information about YouTube video without downloading.

        Args:
            url: YouTube video URL

        Returns:
            Dictionary with video metadata
        """
        # Try without proxy first
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "cachedir": os.environ.get("YT_DLP_CACHE_DIR", "/tmp/yt-dlp-cache"),
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return self._parse_video_info(info, url)

        except Exception as e:
            # Check if it's bot detection
            error_msg = str(e).lower()
            if (
                "bot" in error_msg or "captcha" in error_msg or "sign in" in error_msg
            ) and self.proxy:
                logger.warning("⚠ Bot detection encountered, retrying with proxy...")
                return self._get_video_info_with_proxy(url)
            else:
                logger.error(f"Failed to get video info: {e}")
                raise RuntimeError(f"Cannot access video information: {e}")

    def _get_video_info_with_proxy(self, url: str) -> Dict[str, Any]:
        """Get video info using residential proxy."""
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "cachedir": os.environ.get("YT_DLP_CACHE_DIR", "/tmp/yt-dlp-cache"),
                "proxy": self.proxy,
                # Disable SSL verification when using proxy (required for HTTP proxies with HTTPS)
                "nocheckcertificate": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return self._parse_video_info(info, url)

        except Exception as e:
            logger.error(f"Failed to get video info with proxy: {e}")
            raise RuntimeError(f"Cannot access video information: {e}")

    def _parse_video_info(self, info: Dict, url: str) -> Dict[str, Any]:
        """Parse yt-dlp info dict into standardized format."""
        return {
            "title": info.get("title", "Unknown"),
            "duration": info.get("duration", 0),
            "uploader": info.get("uploader", "Unknown"),
            "upload_date": info.get("upload_date", "Unknown"),
            "view_count": info.get("view_count", 0),
            "description": info.get("description", ""),
            "video_id": info.get("id", ""),
            "webpage_url": info.get("webpage_url", url),
        }

    def _download_audio(self, url: str, base_name: str) -> Path:
        """Download audio-only stream from YouTube video.

        Args:
            url: YouTube video URL
            base_name: Clean base name for filename

        Returns:
            Path to downloaded audio file

        Raises:
            VoiceProcessingError: If download fails with structured error information
        """
        # Start download stage
        if self.progress_tracker:
            self.progress_tracker.start_stage(ProgressStage.DOWNLOAD, "Starting audio download")

        # Create temporary filename for direct audio download
        temp_filename = self.temp_dir / f"{base_name}_temp.%(ext)s"

        # Set up progress hook if tracker is available
        progress_hook = None
        if self.progress_tracker:
            progress_hook = DownloadProgressHook(self.progress_tracker)

        # Try without proxy first (faster, free)
        try:
            logger.info("Attempting audio download without proxy...")
            downloaded_file = self._download_with_ydl(
                url, temp_filename, progress_hook, use_proxy=False
            )
            logger.info("✓ Audio downloaded successfully (direct)")
            return downloaded_file

        except Exception as e:
            # Check if it's bot detection
            error_msg = str(e).lower()
            if "bot" in error_msg or "captcha" in error_msg or "sign in" in error_msg:
                if self.proxy:
                    logger.warning("⚠ Bot detection encountered, retrying with proxy...")
                    try:
                        downloaded_file = self._download_with_ydl(
                            url, temp_filename, progress_hook, use_proxy=True
                        )
                        logger.info("✓ Audio downloaded successfully (via proxy)")
                        return downloaded_file
                    except Exception as proxy_error:
                        logger.error(f"Audio download failed with proxy: {str(proxy_error)}")
                        raise VoiceProcessingError(
                            message=f"No suitable audio format available for video: {url}",
                            code=ErrorCode.UNSUPPORTED_FORMAT,
                            context=ErrorContext(
                                operation="youtube_audio_download",
                                details={"url": url, "error": str(proxy_error)},
                            ),
                        )
                else:
                    logger.error(f"Bot detection encountered but no proxy configured: {e}")
                    raise VoiceProcessingError(
                        message=f"YouTube bot detection - no proxy configured: {url}",
                        code=ErrorCode.UNSUPPORTED_FORMAT,
                        context=ErrorContext(
                            operation="youtube_audio_download",
                            details={"url": url, "error": str(e)},
                        ),
                    )
            else:
                logger.error(f"Audio download failed: {str(e)}")
                raise VoiceProcessingError(
                    message=f"No suitable audio format available for video: {url}",
                    code=ErrorCode.UNSUPPORTED_FORMAT,
                    context=ErrorContext(
                        operation="youtube_audio_download",
                        details={"url": url, "error": str(e)},
                    ),
                )

    def _download_with_ydl(
        self, url: str, temp_filename: Path, progress_hook, use_proxy: bool = False
    ) -> Path:
        """Download audio using yt-dlp with optional proxy."""
        # Configure yt-dlp options for direct audio-only download
        ydl_opts = {
            # Select best quality audio-only stream (accepts all codecs including opus)
            # FFmpeg will handle codec conversion if needed during post-processing
            "format": "bestaudio/best",
            "outtmpl": str(temp_filename),
            # Do NOT use extractaudio - we want direct audio streams
            "noplaylist": True,
            "retries": self.youtube_config.get("retry_attempts", 3),
            "ignoreerrors": False,
            "quiet": True,
            "no_warnings": True,
            "cachedir": os.environ.get("YT_DLP_CACHE_DIR", "/tmp/yt-dlp-cache"),
            # Prefer ffmpeg for any needed minor processing
            "prefer_ffmpeg": True,
        }

        # Add proxy if requested
        if use_proxy and self.proxy:
            ydl_opts["proxy"] = self.proxy
            # Disable SSL verification when using proxy (required for HTTP proxies with HTTPS)
            ydl_opts["nocheckcertificate"] = True
            logger.info("✓ Using residential proxy for audio download")

        # Add progress hook if available
        if progress_hook:
            ydl_opts["progress_hooks"] = [progress_hook]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Download the audio-only stream directly
                ydl.download([url])

            # Find the downloaded file (yt-dlp replaces %(ext)s with actual extension)
            # Extract base name from temp_filename path
            base_name = temp_filename.stem.replace("_temp", "")
            pattern = f"{base_name}_temp.*"
            downloaded_files = list(self.temp_dir.glob(pattern))

            if not downloaded_files:
                raise VoiceProcessingError(
                    message="Downloaded audio file not found after successful download",
                    error_code=ErrorCode.DOWNLOAD_FAILED,
                    context=ErrorContext(operation="audio_download", url=url),
                    suggestions=["Check temporary directory permissions", "Try downloading again"],
                )

            downloaded_file = downloaded_files[0]
            logger.debug(f"Downloaded audio-only file: {downloaded_file}")

            # Complete download stage if not already completed by progress hook
            if (
                self.progress_tracker
                and self.progress_tracker.current_stage == ProgressStage.DOWNLOAD
            ):
                file_size = downloaded_file.stat().st_size
                self.progress_tracker.complete_stage(
                    f"Download completed: {downloaded_file.name}",
                    details={"file_path": str(downloaded_file), "file_size_bytes": file_size},
                )

            return downloaded_file

        except VoiceProcessingError:
            # Re-raise structured errors
            raise
        except Exception as e:
            # Convert to structured error
            error = ErrorHandler.handle_youtube_error(e, url)
            logger.error(f"yt-dlp audio-only download failed: {error.message}")
            raise error

    def _is_valid_youtube_url(self, url: str) -> bool:
        """Validate media URL format (YouTube, Apple Podcasts, and other yt-dlp supported sites).

        Supports 1800+ extractors including:
        - YouTube (youtube.com, youtu.be)
        - Apple Podcasts (podcasts.apple.com)
        - Spotify Podcasts
        - SoundCloud
        - Vimeo
        - And many more

        For Apple Podcasts: Episode URLs must include the ?i=<episode_id> parameter.
        """
        # Basic URL validation
        if not url or not url.startswith(("http://", "https://")):
            return False

        # Must have a domain after protocol
        if url in ("http://", "https://"):
            return False

        # Specific validation for Apple Podcasts URLs
        if "podcasts.apple.com" in url:
            # Apple Podcasts URLs must have episode ID parameter (?i=...)
            if "?i=" not in url and "&i=" not in url:
                logger.warning(
                    f"Apple Podcasts URL missing episode ID: {url}. "
                    "URL must point to a specific episode with ?i=<episode_id> parameter."
                )
                return False

        return True

    def _sanitize_filename(self, filename: str, max_length: int = 100) -> str:
        """Sanitize filename for safe file system usage.

        Args:
            filename: Original filename
            max_length: Maximum length for filename

        Returns:
            Sanitized filename
        """
        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', "", filename)

        # Replace spaces with underscores
        filename = re.sub(r"\s+", "_", filename)

        # Remove non-ASCII characters
        filename = filename.encode("ascii", "ignore").decode("ascii")

        # Limit length
        if len(filename) > max_length:
            filename = filename[:max_length]

        # Ensure filename is not empty
        if not filename:
            filename = "youtube_video"

        return filename
