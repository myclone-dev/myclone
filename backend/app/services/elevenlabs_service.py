"""
ElevenLabs Service - Business logic for ElevenLabs voice cloning API

This service handles:
- ElevenLabs API integration
- File validation
- Voice clone creation
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from elevenlabs.client import ElevenLabs

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context


class ElevenLabsService:
    """Service for ElevenLabs voice cloning API operations"""

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize ElevenLabs service

        Args:
            api_key: ElevenLabs API key (defaults to settings.elevenlabs_api_key)
        """
        self.client = ElevenLabs(api_key=api_key or settings.elevenlabs_api_key)
        self.logger = logging.getLogger(__name__)

    def _validate_files(self, files: Union[List[str], List[Tuple[str, bytes]]]) -> bool:
        """
        Validate files meet ElevenLabs requirements

        Args:
            files: Either list of file paths (str) or list of (filename, content) tuples

        Returns:
            True if all files are valid

        Raises:
            ValueError: If any file fails validation
            FileNotFoundError: If file path doesn't exist
        """
        for file_item in files:
            # Check if it's a tuple (filename, content) or a string (file path)
            if isinstance(file_item, tuple):
                file_name, file_content = file_item
                file_size = len(file_content)

                # Check file size (10MB limit)
                if file_size > self.MAX_FILE_SIZE:
                    raise ValueError(
                        f"File too large: {file_name} (max {self.MAX_FILE_SIZE // (1024*1024)}MB)"
                    )

                # Check if file is empty
                if file_size == 0:
                    raise ValueError(f"File is empty: {file_name}")

                # Check file format by extension
                allowed_extensions = [".wav", ".mp3", ".m4a", ".flac"]
                if not any(file_name.lower().endswith(ext) for ext in allowed_extensions):
                    raise ValueError(
                        f"Unsupported file format: {file_name}. Allowed: {allowed_extensions}"
                    )

                # Basic WAV file validation by checking header
                if file_name.lower().endswith(".wav"):
                    try:
                        if len(file_content) < 12:
                            raise ValueError(f"Invalid WAV file (too small): {file_name}")

                        # Check RIFF header
                        if file_content[:4] != b"RIFF":
                            raise ValueError(f"Invalid WAV file (missing RIFF header): {file_name}")

                        # Check WAVE format
                        if file_content[8:12] != b"WAVE":
                            raise ValueError(f"Invalid WAV file (missing WAVE format): {file_name}")

                        self.logger.info(
                            f"Validated file from memory: {file_name} ({file_size} bytes)"
                        )
                    except Exception as e:
                        raise ValueError(f"Failed to validate WAV file {file_name}: {str(e)}")
            else:
                # Original file path validation
                file_path = file_item
                path = Path(file_path)
                if not path.exists():
                    raise FileNotFoundError(f"File not found: {file_path}")

                # Check file size (10MB limit)
                file_size = path.stat().st_size
                if file_size > self.MAX_FILE_SIZE:
                    raise ValueError(
                        f"File too large: {file_path} (max {self.MAX_FILE_SIZE // (1024*1024)}MB)"
                    )

                # Check if file is empty
                if file_size == 0:
                    raise ValueError(f"File is empty: {file_path}")

                # Check file format by extension
                allowed_extensions = [".wav", ".mp3", ".m4a", ".flac"]
                if not any(file_path.lower().endswith(ext) for ext in allowed_extensions):
                    raise ValueError(
                        f"Unsupported file format: {file_path}. Allowed: {allowed_extensions}"
                    )

                # Basic WAV file validation by checking header
                if file_path.lower().endswith(".wav"):
                    try:
                        with open(file_path, "rb") as f:
                            header = f.read(12)
                            if len(header) < 12:
                                raise ValueError(f"Invalid WAV file (too small): {file_path}")

                            # Check RIFF header
                            if header[:4] != b"RIFF":
                                raise ValueError(
                                    f"Invalid WAV file (missing RIFF header): {file_path}"
                                )

                            # Check WAVE format
                            if header[8:12] != b"WAVE":
                                raise ValueError(
                                    f"Invalid WAV file (missing WAVE format): {file_path}"
                                )

                            # Try to get basic audio info
                            f.seek(0)
                            # Look for 'fmt ' chunk to get sample rate
                            while True:
                                chunk_header = f.read(8)
                                if len(chunk_header) < 8:
                                    break
                                chunk_id = chunk_header[:4]
                                chunk_size = int.from_bytes(chunk_header[4:8], "little")

                                if chunk_id == b"fmt ":
                                    fmt_data = f.read(16)  # Read minimum fmt chunk
                                    if len(fmt_data) >= 8:
                                        sample_rate = int.from_bytes(fmt_data[4:8], "little")
                                        # Estimate duration
                                        duration = file_size / (
                                            sample_rate * 2
                                        )  # Rough estimate for 16-bit mono
                                        self.logger.info(
                                            f"Validated WAV file: {file_path} ({file_size} bytes, ~{duration:.1f}s)"
                                        )

                                        # Check duration requirements (30s to 5min)
                                        if duration < 30:
                                            self.logger.warning(
                                                f"Audio file may be too short: {file_path} (~{duration:.1f}s, minimum 30s recommended)"
                                            )
                                        elif duration > 300:
                                            self.logger.warning(
                                                f"Audio file may be too long: {file_path} (~{duration:.1f}s, maximum 5min recommended)"
                                            )
                                    else:
                                        self.logger.info(
                                            f"Validated WAV file: {file_path} ({file_size} bytes)"
                                        )
                                    break
                                else:
                                    # Skip this chunk
                                    f.seek(chunk_size, 1)

                    except Exception as e:
                        raise ValueError(f"Failed to validate WAV file {file_path}: {str(e)}")

        return True

    def create_voice_clone(
        self,
        name: str,
        files: Union[List[str], List[Tuple[str, bytes]]],
        description: Optional[str] = None,
        remove_background_noise: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a voice clone using ElevenLabs IVC API

        Args:
            name: Voice clone name
            files: List of file paths or (filename, content) tuples
            description: Optional description
            remove_background_noise: Whether to remove background noise

        Returns:
            Dictionary with voice_id, name, and status

        Raises:
            ValueError: If validation fails
            Exception: If ElevenLabs API call fails
        """
        try:
            # Validate inputs
            if not name or not name.strip():
                raise ValueError("Voice name is required")

            if not files or len(files) == 0:
                raise ValueError("At least one audio file is required")

            self._validate_files(files)

            # Log request details
            self.logger.info("Creating voice clone with:")
            self.logger.info(f"  Name: {name.strip()}")
            self.logger.info(f"  Files: {len(files)} file(s)")
            self.logger.info(f"  Description: {description}")
            self.logger.info(f"  Remove background noise: {remove_background_noise}")

            # Convert files to file objects format expected by ElevenLabs API
            file_objects = []
            for file_item in files:
                if isinstance(file_item, tuple):
                    # Already have content as tuple (filename, bytes)
                    file_name, file_content = file_item
                    file_objects.append((file_name, file_content))
                    self.logger.info(
                        f"Using provided content for: {file_name} ({len(file_content)} bytes)"
                    )
                else:
                    # File path - need to read from disk
                    file_path = file_item
                    try:
                        with open(file_path, "rb") as f:
                            file_content = f.read()
                            file_objects.append((file_path, file_content))
                            self.logger.info(
                                f"Loaded file from disk: {file_path} ({len(file_content)} bytes)"
                            )
                    except Exception as e:
                        raise ValueError(f"Failed to read file {file_path}: {str(e)}")

            # Create voice clone via ElevenLabs API
            response = self.client.voices.ivc.create(
                name=name.strip(),
                files=file_objects,
                description=description,
                remove_background_noise=remove_background_noise,
            )

            voice_id = getattr(response, "voice_id", "unknown")
            self.logger.info(f"Voice clone created successfully: {name} (voice_id: {voice_id})")

            # Convert response object to dictionary for consistent API
            return {
                "voice_id": voice_id,
                "name": name.strip(),
                "status": "success",
            }

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"voice_name": name, "files_count": len(files)},
                tags={
                    "component": "elevenlabs_service",
                    "operation": "create_voice_clone",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"Failed to create voice clone '{name}': {str(e)}")
            raise

    def delete_voice(self, voice_id: str) -> Dict[str, Any]:
        """
        Delete a voice clone from ElevenLabs

        Args:
            voice_id: ElevenLabs voice ID to delete

        Returns:
            Dictionary with status and message

        Raises:
            ValueError: If voice_id is invalid
            Exception: If ElevenLabs API call fails (except voice_does_not_exist)
        """
        try:
            if not voice_id or not voice_id.strip():
                raise ValueError("Voice ID is required")

            self.logger.info(f"Deleting voice from ElevenLabs: {voice_id}")

            # Delete voice via ElevenLabs API
            self.client.voices.delete(voice_id=voice_id)

            self.logger.info(f"Voice deleted successfully from ElevenLabs: {voice_id}")

            return {
                "voice_id": voice_id,
                "status": "success",
                "message": f"Voice {voice_id} deleted successfully",
            }

        except Exception as e:
            error_str = str(e).lower()
            # Handle "voice_does_not_exist" as success - voice was already deleted
            # (e.g., user deleted directly via ElevenLabs dashboard)
            if "voice_does_not_exist" in error_str or "does not exist" in error_str:
                self.logger.info(
                    f"Voice {voice_id} does not exist on ElevenLabs (already deleted), "
                    "treating as success"
                )
                return {
                    "voice_id": voice_id,
                    "status": "success",
                    "message": f"Voice {voice_id} already deleted from ElevenLabs",
                    "already_deleted": True,
                }
            # For other errors, capture in Sentry, log and re-raise
            capture_exception_with_context(
                e,
                extra={"voice_id": voice_id},
                tags={
                    "component": "elevenlabs_service",
                    "operation": "delete_voice",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"Failed to delete voice '{voice_id}': {str(e)}")
            raise
