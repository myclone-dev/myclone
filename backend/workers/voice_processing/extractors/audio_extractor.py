"""Audio extraction from video files using FFmpeg."""

from pathlib import Path
from typing import Optional

import ffmpeg
from loguru import logger
from pydub import AudioSegment
from utils.config import config
from utils.filename_utils import FilenameGenerator
from utils.progress import ProgressTracker
from utils.video_chunker import VideoChunker

from shared.voice_processing.errors import (
    ErrorCode,
    ErrorContext,
    ErrorHandler,
    VoiceProcessingError,
)


class AudioExtractor:
    """Extract audio from video files with format validation."""

    def __init__(self, progress_tracker: Optional[ProgressTracker] = None):
        """Initialize audio extractor.

        Args:
            progress_tracker: Optional progress tracker for monitoring operations
        """
        self.validation_config = config.get_validation_config()
        self.temp_dir = config.get_temp_dir()
        self.video_chunker = VideoChunker()
        self.progress_tracker = progress_tracker

    def extract_from_video(
        self,
        video_path: str,
        output_path: str = None,
        target_format: str = "wav",
        start_time: int = None,
        end_time: int = None,
    ) -> str:
        """Extract audio from video file using FFmpeg.

        Args:
            video_path: Path to input video file
            output_path: Path for output audio file (optional)
            target_format: Output audio format ('wav', 'mp3', etc.)
            start_time: Start time in seconds (for manual time range extraction)
            end_time: End time in seconds (for manual time range extraction)

        Returns:
            Path to extracted audio file

        Raises:
            FileNotFoundError: If video file doesn't exist
            ValueError: If video format not supported
            RuntimeError: If extraction fails
        """
        video_path = Path(video_path)

        # Validate input file
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if not self._is_supported_video_format(video_path.suffix.lower().lstrip(".")):
            supported = self.validation_config.get("supported_video_formats", [])
            raise ValueError(
                f"Unsupported video format: {video_path.suffix}. " f"Supported: {supported}"
            )

        # Generate output path if not provided
        if output_path is None:
            output_dir = config.get_output_dir("raw")
            # Generate clean base name from file path
            base_name = FilenameGenerator.from_file_path(str(video_path))
            output_path = output_dir / f"{base_name}.{target_format}"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if start_time is not None and end_time is not None:
            logger.info(
                f"Extracting audio from {video_path} (time range: {start_time}s-{end_time}s) to {output_path}"
            )
        else:
            logger.info(f"Extracting audio from {video_path} to {output_path}")

        try:
            # Use FFmpeg to extract audio with optional time range
            input_params = {}
            if start_time is not None:
                input_params["ss"] = start_time
            if end_time is not None:
                input_params["to"] = end_time

            stream = ffmpeg.input(str(video_path), **input_params)

            # Configure audio extraction parameters
            audio_params = {
                "acodec": self._get_codec_for_format(target_format),
                "ar": 44100,  # Sample rate
                "ac": 1,  # Mono audio
            }

            # Add format-specific parameters
            if target_format == "mp3":
                audio_params["audio_bitrate"] = "192k"
            elif target_format == "wav":
                audio_params["acodec"] = "pcm_s16le"  # 16-bit PCM

            stream = ffmpeg.output(stream, str(output_path), **audio_params)

            # Run extraction
            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            logger.success(f"Audio extracted successfully: {output_path}")
            return str(output_path)

        except ffmpeg.Error as e:
            error_msg = f"FFmpeg extraction failed: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during extraction: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def convert_audio_format(
        self,
        input_path: str,
        output_path: str = None,
        target_format: str = "mp3",
        start_time: int = None,
        end_time: int = None,
    ) -> str:
        """Convert audio file to different format with optional time range extraction.

        Args:
            input_path: Path to input audio file
            output_path: Path for output file (optional)
            target_format: Target audio format
            start_time: Start time in seconds (for manual time range extraction)
            end_time: End time in seconds (for manual time range extraction)

        Returns:
            Path to converted audio file

        Raises:
            VoiceProcessingError: If conversion fails with structured error information
        """
        input_path = Path(input_path)

        # Validation
        if not input_path.exists():
            raise VoiceProcessingError(
                message=f"Input audio file not found: {input_path}",
                error_code=ErrorCode.FILE_NOT_FOUND,
                context=ErrorContext(operation="audio_conversion", file_path=str(input_path)),
            )

        # Generate output path if not provided
        if output_path is None:
            output_dir = config.get_output_dir("raw")
            # Generate clean base name from file path
            base_name = FilenameGenerator.from_file_path(str(input_path))
            output_path = output_dir / f"{base_name}_converted.{target_format}"

        output_path = Path(output_path)

        if start_time is not None and end_time is not None:
            logger.info(
                f"Converting {input_path} to {target_format} (time range: {start_time}s-{end_time}s)"
            )
        else:
            logger.info(f"Converting {input_path} to {target_format}")

        # Report progress if tracker available
        if self.progress_tracker:
            self.progress_tracker.update_progress(10.0, f"Loading {target_format} conversion")

        try:
            # Load audio with pydub
            audio = AudioSegment.from_file(str(input_path))

            if self.progress_tracker:
                self.progress_tracker.update_progress(
                    30.0, "Audio loaded, applying format settings"
                )

            # Apply time range extraction if specified
            if start_time is not None and end_time is not None:
                start_ms = start_time * 1000  # Convert to milliseconds
                end_ms = end_time * 1000
                audio = audio[start_ms:end_ms]
                logger.info(
                    f"Extracted time range: {start_time}s-{end_time}s (duration: {(end_ms - start_ms) / 1000}s)"
                )

            # Convert to mono if needed
            if audio.channels > 1:
                audio = audio.set_channels(1)

            # Set sample rate to 44.1kHz
            audio = audio.set_frame_rate(44100)

            if self.progress_tracker:
                self.progress_tracker.update_progress(60.0, f"Exporting to {target_format} format")

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Export in target format
            export_params = {}
            if target_format == "mp3":
                export_params["bitrate"] = "192k"
            elif target_format == "wav":
                export_params["parameters"] = ["-acodec", "pcm_s16le"]

            audio.export(str(output_path), format=target_format, **export_params)

            if self.progress_tracker:
                file_size = output_path.stat().st_size if output_path.exists() else 0
                self.progress_tracker.update_progress(
                    100.0,
                    f"Conversion completed: {output_path.name}",
                    details={
                        "input_path": str(input_path),
                        "output_path": str(output_path),
                        "target_format": target_format,
                        "file_size_bytes": file_size,
                    },
                )

            logger.success(f"Audio converted successfully: {output_path}")
            return str(output_path)

        except Exception as e:
            error = ErrorHandler.handle_ffmpeg_error(e, str(input_path), "audio_conversion")
            logger.error(f"Audio conversion failed: {error.message}")
            raise error

    def _is_supported_video_format(self, format_ext: str) -> bool:
        """Check if video format is supported."""
        supported = self.validation_config.get("supported_video_formats", [])
        return format_ext in supported

    def _get_codec_for_format(self, format_name: str) -> str:
        """Get appropriate codec for output format."""
        codec_map = {
            "mp3": "libmp3lame",
            "wav": "pcm_s16le",
            "aac": "aac",
            "m4a": "aac",
            "ogg": "libvorbis",
        }
        return codec_map.get(format_name, "pcm_s16le")
