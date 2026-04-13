"""Video utilities for basic duration checks and manual time extraction."""

from pathlib import Path
from typing import List, Optional

import ffmpeg
from loguru import logger

from .config import config


class VideoChunker:
    """Basic video utilities for duration checks and manual time extraction."""

    def __init__(self):
        """Initialize video utilities."""
        self.temp_dir = config.get_temp_dir()

    def get_video_duration(self, video_path: str) -> float:
        """Get duration of video file in seconds.

        Args:
            video_path: Path to video file

        Returns:
            Duration in seconds

        Raises:
            RuntimeError: If unable to get duration
        """
        try:
            probe = ffmpeg.probe(video_path)
            duration = float(probe["format"]["duration"])
            logger.info(f"Video duration: {duration/60:.1f} minutes")
            return duration
        except Exception as e:
            raise RuntimeError(f"Failed to get video duration: {e}")

    def is_long_video(self, video_path: str, threshold_minutes: float = 30.0) -> bool:
        """Check if video is longer than specified threshold.

        Args:
            video_path: Path to video file
            threshold_minutes: Duration threshold in minutes

        Returns:
            True if video exceeds threshold
        """
        duration = self.get_video_duration(video_path)
        return duration > (threshold_minutes * 60)

    def extract_time_segment(
        self, video_path: str, start_time: float, duration: float, output_path: Optional[str] = None
    ) -> str:
        """Extract a specific time segment from video.

        Args:
            video_path: Path to input video
            start_time: Start time in seconds
            duration: Duration in seconds
            output_path: Optional output path for extracted segment

        Returns:
            Path to extracted segment
        """
        if output_path is None:
            video_name = Path(video_path).stem
            output_path = self.temp_dir / f"{video_name}_segment_{start_time}s.mp4"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        return self._extract_segment(video_path, str(output_path), start_time, duration)

    def _extract_segment(
        self, input_path: str, output_path: str, start_time: float, duration: float
    ) -> str:
        """Extract a specific segment from video.

        Args:
            input_path: Path to input video
            output_path: Path for output segment
            start_time: Start time in seconds
            duration: Duration in seconds

        Returns:
            Path to extracted segment
        """
        try:
            logger.info(
                f"Extracting segment: {start_time:.1f}s - {start_time + duration:.1f}s "
                f"({duration/60:.1f} minutes)"
            )

            stream = ffmpeg.input(input_path, ss=start_time, t=duration)
            stream = ffmpeg.output(
                stream, output_path, c="copy"
            )  # Copy streams without re-encoding
            ffmpeg.run(stream, overwrite_output=True, quiet=True)

            logger.success(f"Segment extracted: {output_path}")
            return output_path

        except ffmpeg.Error as e:
            error_msg = f"Failed to extract segment: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def cleanup_segments(self, segment_paths: List[str]):
        """Clean up temporary segment files.

        Args:
            segment_paths: List of segment file paths to remove
        """
        for segment_path in segment_paths:
            try:
                Path(segment_path).unlink(missing_ok=True)
                logger.debug(f"Cleaned up segment: {segment_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup segment {segment_path}: {e}")
