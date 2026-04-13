"""Centralized filename generation utilities for voice processing system."""

import hashlib
import re
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse


class FilenameGenerator:
    """Generate clean, consistent filenames for voice processing."""

    # Configuration
    MAX_BASE_LENGTH = 30

    @classmethod
    def from_youtube_url(cls, url: str, video_info: dict = None) -> str:
        """Generate clean base filename from YouTube URL.

        Args:
            url: YouTube video URL
            video_info: Optional video metadata dict

        Returns:
            Clean base filename (without extension)
        """
        # Extract video ID from URL
        video_id = cls._extract_youtube_id(url)

        if not video_id:
            # Fallback to hash of URL
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            return f"youtube_{url_hash}"

        # Use video ID as base
        return f"youtube_{video_id}"

    @classmethod
    def from_file_path(cls, file_path: str) -> str:
        """Generate clean base filename from file path.

        Args:
            file_path: Path to file

        Returns:
            Clean base filename (without extension)
        """
        path = Path(file_path)
        original_name = path.stem

        # Sanitize the original filename
        clean_name = cls._sanitize_name(original_name, max_length=cls.MAX_BASE_LENGTH)

        return f"upload_{clean_name}"

    @classmethod
    def _extract_youtube_id(cls, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL.

        Args:
            url: YouTube URL

        Returns:
            Video ID or None if not found
        """
        # Handle different YouTube URL formats
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        # Try parsing as query parameter
        try:
            parsed = urlparse(url)
            if parsed.hostname in ("www.youtube.com", "youtube.com"):
                query_params = parse_qs(parsed.query)
                if "v" in query_params:
                    return query_params["v"][0]
        except Exception:
            pass

        return None

    @classmethod
    def _sanitize_name(cls, name: str, max_length: int = MAX_BASE_LENGTH) -> str:
        """Sanitize name for filesystem safety.

        Args:
            name: Original name
            max_length: Maximum length

        Returns:
            Sanitized name
        """
        # Remove invalid filesystem characters
        name = re.sub(r'[<>:"/\\|?*$]', "", name)

        # Replace spaces and special chars with underscores
        name = re.sub(r"[\s\-\.]+", "_", name)

        # Remove non-ASCII characters
        name = name.encode("ascii", "ignore").decode("ascii")

        # Remove multiple underscores
        name = re.sub(r"_+", "_", name)

        # Trim underscores from edges
        name = name.strip("_")

        # Limit length
        if len(name) > max_length:
            name = name[:max_length].rstrip("_")

        # Ensure not empty
        if not name:
            name = "unknown"

        return name.lower()


# Convenience functions for backward compatibility
def get_youtube_base_name(url: str, video_info: dict = None) -> str:
    """Get clean base name for YouTube video."""
    return FilenameGenerator.from_youtube_url(url, video_info)


def get_file_base_name(file_path: str) -> str:
    """Get clean base name for uploaded file."""
    return FilenameGenerator.from_file_path(file_path)
