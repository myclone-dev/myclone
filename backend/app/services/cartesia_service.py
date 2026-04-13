# Updated CartesiaService (async-friendly, safer headers, correct multipart types)

import asyncio
import hashlib
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

FileLike = Tuple[str, bytes]  # (filename, content)
FileParam = Union[str, FileLike]


class CartesiaVoiceCreationError(Exception):
    """Raised when voice clone creation fails in Cartesia."""

    def __init__(
        self,
        message: str,
        voice_id: Optional[str] = None,
        stage: str = "unknown",
        raw_response: Optional[Dict] = None,
        user_message: Optional[str] = None,
    ):
        super().__init__(message)
        self.voice_id = voice_id
        self.stage = stage
        self.raw_response = raw_response
        # User-friendly message for frontend display
        self.user_message = user_message or message


def parse_cartesia_error(status_code: int, response_body: str) -> str:
    """
    Parse Cartesia API error response and return a user-friendly message.

    Args:
        status_code: HTTP status code from Cartesia
        response_body: Raw response body text

    Returns:
        User-friendly error message
    """
    import json

    # Common error messages mapping
    error_messages = {
        400: "Invalid audio file format. Please upload a valid audio file (WAV, MP3, M4A, or FLAC).",
        401: "Voice cloning service authentication failed. Please try again later.",
        403: "Voice cloning service access denied. Please contact support.",
        404: "Voice cloning service endpoint not found. Please try again later.",
        413: "Audio file is too large. Please upload a file smaller than 10MB.",
        415: "Unsupported audio format. Please use WAV, MP3, M4A, or FLAC format.",
        429: "Too many requests. Please wait a moment and try again.",
        500: "Voice cloning service is temporarily unavailable. Please try again later.",
        502: "Voice cloning service is temporarily unavailable. Please try again later.",
        503: "Voice cloning service is temporarily unavailable. Please try again later.",
    }

    # Try to parse JSON error response for more specific message
    try:
        error_data = json.loads(response_body)

        # Check for specific Cartesia error patterns
        detail = error_data.get("detail", "")
        message = error_data.get("message", "")
        error = error_data.get("error", "")

        error_text = str(detail or message or error).lower()

        # Audio duration issues
        if "duration" in error_text or "too short" in error_text or "too long" in error_text:
            if "short" in error_text:
                return "Audio is too short. Please provide at least 10 seconds of clear speech."
            elif "long" in error_text:
                return "Audio is too long. Please keep your recording under 30 seconds."
            else:
                return "Audio duration issue. Please provide 10-30 seconds of clear speech."

        # Audio quality issues
        if "quality" in error_text or "noise" in error_text or "unclear" in error_text:
            return (
                "Audio quality is too low. Please record in a quiet environment with clear speech."
            )

        # Format issues
        if "format" in error_text or "codec" in error_text or "unsupported" in error_text:
            return "Unsupported audio format. Please use WAV, MP3, M4A, or FLAC format."

        # Sample rate issues
        if "sample rate" in error_text or "sample_rate" in error_text:
            return "Audio sample rate is not supported. Please use a standard audio format."

        # Empty or silent audio
        if "empty" in error_text or "silent" in error_text or "no audio" in error_text:
            return "No audio detected in the file. Please ensure your recording contains audible speech."

        # Speech detection issues
        if "speech" in error_text or "voice" in error_text:
            return "Could not detect clear speech in the audio. Please record yourself speaking clearly."

        # 422 Unprocessable Entity - general validation error
        if status_code == 422:
            if detail or message or error:
                # Return the actual error if it's informative
                actual_error = str(detail or message or error)
                if len(actual_error) < 200:  # Reasonable length for user display
                    return f"Voice cloning failed: {actual_error}"
            return "Could not process the audio file. Please ensure it contains 10-30 seconds of clear speech in a quiet environment."

    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    # Fallback to status code based message
    return error_messages.get(
        status_code,
        "Voice cloning failed. Please try again with a different audio recording.",
    )


class CartesiaVoiceVerificationError(Exception):
    """Raised when voice verification fails after creation."""

    def __init__(self, message: str, voice_id: str, verification_error: Optional[str] = None):
        super().__init__(message)
        self.voice_id = voice_id
        self.verification_error = verification_error


# Cartesia supported languages for voice cloning
CARTESIA_LANGUAGES = [
    "en",
    "fr",
    "de",
    "es",
    "pt",
    "zh",
    "ja",
    "hi",
    "it",
    "ko",
    "nl",
    "pl",
    "ru",
    "sv",
    "tr",
]

# Voice clone modes: similarity vs stability tradeoff
CARTESIA_CLONE_MODES = ["similarity", "stability"]


class CartesiaService:
    """Service for Cartesia voice cloning API operations (async)."""

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    MAX_FILE_DURATION_SECONDS = 90  # Cartesia limit per clip
    MIN_FILE_DURATION_SECONDS = 1  # avoid zero-length clips
    MAX_TOTAL_DURATION_SECONDS = 300  # Cartesia accepts up to ~5 minutes combined
    API_BASE_URL = os.getenv("CARTESIA_BASE_URL", "https://api.cartesia.ai")
    API_VERSION = "2025-04-16"
    # Cartesia supports: .wav, .mp3, .flac, .ogg, .oga, .ogx, .aac, .wma, .m4a, .opus, .ac3, .webm
    # https://docs.cartesia.ai/build-with-cartesia/capability-guides/clone-voices-pro/playground
    ALLOWED_EXTENSIONS = [".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".aac", ".opus"]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "cartesia_api_key", None)
        if not self.api_key:
            raise ValueError("Cartesia API key is required")

        self.logger = logging.getLogger(__name__)
        self.default_headers = {"X-API-Key": self.api_key, "Cartesia-Version": self.API_VERSION}

    def _auth_headers(self) -> Dict[str, str]:
        return dict(self.default_headers)

    @staticmethod
    def _guess_mime_type(filename: str) -> str:
        mime, _ = mimetypes.guess_type(filename)
        return mime or "application/octet-stream"

    @staticmethod
    def _is_wav_file(filename: str) -> bool:
        return filename.lower().endswith(".wav")

    def _validate_file_tuple(self, file_name: str, file_content: bytes) -> None:
        if not isinstance(file_name, str):
            raise ValueError("filename must be a string")

        size = len(file_content)
        if size == 0:
            raise ValueError(f"File is empty: {file_name}")
        if size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File too large: {file_name} (max {self.MAX_FILE_SIZE // (1024 * 1024)} MB)"
            )

        if not any(file_name.lower().endswith(ext) for ext in self.ALLOWED_EXTENSIONS):
            raise ValueError(
                f"Unsupported file format: {file_name}. Allowed: {self.ALLOWED_EXTENSIONS}"
            )

        # WAV-specific validation
        if self._is_wav_file(file_name):
            self._validate_wav_header(file_name, file_content)
            self._validate_wav_duration(file_name, file_content)

    def _validate_file_path(self, file_path: str) -> None:
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        size = p.stat().st_size
        if size == 0:
            raise ValueError(f"File is empty: {file_path}")
        if size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File too large: {file_path} (max {self.MAX_FILE_SIZE // (1024 * 1024)} MB)"
            )

        if not any(file_path.lower().endswith(ext) for ext in self.ALLOWED_EXTENSIONS):
            raise ValueError(
                f"Unsupported file format: {file_path}. Allowed: {self.ALLOWED_EXTENSIONS}"
            )

        # WAV-specific validation
        if self._is_wav_file(file_path):
            file_content = p.read_bytes()
            self._validate_wav_header(file_path, file_content)
            self._validate_wav_duration(file_path, file_content)

    def _validate_wav_header(self, file_name: str, file_content: bytes) -> None:
        """Validate WAV file header."""
        if len(file_content) < 12:
            raise ValueError(f"Invalid WAV file (too small): {file_name}")
        if file_content[:4] != b"RIFF" or file_content[8:12] != b"WAVE":
            raise ValueError(f"Invalid WAV file (bad header): {file_name}")

    def _validate_wav_duration(self, file_name: str, file_content: bytes) -> None:
        """Ensure WAV audio duration matches Cartesia requirements."""
        import contextlib
        import wave
        from io import BytesIO

        try:
            with contextlib.closing(wave.open(BytesIO(file_content), "rb")) as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                if rate == 0:
                    raise ValueError(f"Sample rate is zero for {file_name}")
                duration = frames / float(rate)

                if duration < self.MIN_FILE_DURATION_SECONDS:
                    raise ValueError(f"Audio clip too short ({duration:.2f}s) for {file_name}")
                if duration > self.MAX_FILE_DURATION_SECONDS:
                    raise ValueError(
                        f"Audio clip exceeds {self.MAX_FILE_DURATION_SECONDS}s: {file_name}"
                    )

        except wave.Error as err:
            raise ValueError(f"Invalid WAV structure for {file_name}: {err}")

    def _validate_files_sync(self, files: List[FileParam]) -> bool:
        """Synchronous validation helper. Run in thread from async contexts."""
        for item in files:
            if isinstance(item, tuple):
                name, content = item
                self._validate_file_tuple(name, content)
            else:
                self._validate_file_path(item)
        return True

    def _extract_duration_seconds(self, filename: str, file_content: bytes) -> float:
        """Extract duration from audio file. Only reliable for WAV files."""
        import contextlib
        import wave
        from io import BytesIO

        # Only attempt duration extraction for WAV files
        if not self._is_wav_file(filename):
            # For non-WAV files, return 0 and let Cartesia handle validation
            # Alternatively, you could use pydub/mutagen for other formats
            self.logger.debug(f"Skipping duration extraction for non-WAV file: {filename}")
            return 0.0

        try:
            with contextlib.closing(wave.open(BytesIO(file_content), "rb")) as wav_file:
                frames = wav_file.getnframes()
                rate = wav_file.getframerate()
                return frames / float(rate) if rate else 0.0
        except wave.Error as e:
            self.logger.warning(f"Could not extract duration from {filename}: {e}")
            return 0.0

    async def create_voice_clone(
        self,
        name: str,
        files: List[FileParam],
        description: Optional[str] = None,
        language: str = "en",
        enhance: bool = True,
        mode: str = "similarity",
        timeout: float = 120.0,
        verify_creation: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a voice clone using Cartesia's instant voice cloning API.

        Args:
            name: Name for the voice clone
            files: List of audio files (paths or (filename, bytes) tuples)
            description: Optional description
            language: Language code (default: "en")
            enhance: Apply AI enhancement to reduce background noise (default: True)
            mode: Clone mode - 'similarity' or 'stability' (default: "similarity")
            timeout: Request timeout in seconds (default: 120.0)
            verify_creation: If True, verify voice exists in Cartesia after creation (default: True)

        Returns:
            Dictionary with voice_id, name, embedding, and status

        Raises:
            ValueError: For invalid input parameters
            CartesiaVoiceCreationError: If voice creation fails
            CartesiaVoiceVerificationError: If verification fails after creation
        """
        # Input validation
        if not name or not name.strip():
            raise ValueError("Voice name is required")
        if not files:
            raise ValueError("At least one audio file is required")
        if language not in CARTESIA_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}. Supported: {CARTESIA_LANGUAGES}")
        if mode not in CARTESIA_CLONE_MODES:
            raise ValueError(f"Invalid mode: {mode}. Must be 'similarity' or 'stability'")

        self.logger.info(
            f"[VOICE_CLONE_START] Starting voice clone creation: name={name}, "
            f"files={len(files)}, language={language}, enhance={enhance}, mode={mode}"
        )

        # Run validation in thread to avoid blocking event loop
        await asyncio.to_thread(self._validate_files_sync, files)
        self.logger.info(f"[VOICE_CLONE_VALIDATION] File validation passed for {len(files)} files")

        # Prepare multipart files list
        # Cartesia API expects 'clip' field name for each audio file
        multipart_files = []
        total_duration = 0.0
        total_size_bytes = 0

        for idx, item in enumerate(files):
            if isinstance(item, tuple):
                filename, content = item
                if not isinstance(content, (bytes, bytearray)):
                    raise ValueError(f"File content must be bytes for {filename}")
                content_type = self._guess_mime_type(filename)
                # Use 'clip' as the field name per Cartesia API
                multipart_files.append(("clip", (filename, content, content_type)))
                file_size = len(content)
                total_size_bytes += file_size
                duration = self._extract_duration_seconds(filename, content)
                total_duration += duration
                self.logger.info(
                    f"[VOICE_CLONE_FILE] Prepared file {idx + 1}/{len(files)}: "
                    f"{filename} ({file_size} bytes, {duration:.2f}s)"
                )
            else:
                path = Path(item)
                file_bytes = await asyncio.to_thread(path.read_bytes)
                filename = path.name
                content_type = self._guess_mime_type(filename)
                # Use 'clip' as the field name per Cartesia API
                multipart_files.append(("clip", (filename, file_bytes, content_type)))
                file_size = len(file_bytes)
                total_size_bytes += file_size
                duration = self._extract_duration_seconds(filename, file_bytes)
                total_duration += duration
                self.logger.info(
                    f"[VOICE_CLONE_FILE] Prepared file {idx + 1}/{len(files)}: "
                    f"{str(path)} ({file_size} bytes, {duration:.2f}s)"
                )

        # Only enforce total duration if we could measure it (WAV files)
        if total_duration > self.MAX_TOTAL_DURATION_SECONDS:
            raise ValueError(
                f"Combined audio exceeds {self.MAX_TOTAL_DURATION_SECONDS}s (currently {total_duration:.1f}s)"
            )

        self.logger.info(
            f"[VOICE_CLONE_PREPARED] Total: {len(multipart_files)} files, "
            f"{total_size_bytes} bytes, {total_duration:.2f}s duration"
        )

        data = {
            "name": name.strip(),
            "language": language,
            "enhance": enhance,
            "mode": mode,
        }
        if description:
            data["description"] = description

        headers = self._auth_headers()

        try:
            self.logger.info(
                f"[VOICE_CLONE_API_CALL] Sending request to Cartesia API: "
                f"POST {self.API_BASE_URL}/voices/clone"
            )

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.API_BASE_URL}/voices/clone",
                    headers=headers,
                    data=data,
                    files=multipart_files,
                )

                self.logger.info(
                    f"[VOICE_CLONE_API_RESPONSE] Cartesia API response: "
                    f"status={response.status_code}, content_length={len(response.content)}"
                )

                # Handle non-200 responses with detailed error logging
                if response.status_code != 200:
                    body_preview = response.text[:1000]
                    error_msg = (
                        f"Cartesia API returned non-200 status: {response.status_code}. "
                        f"Response: {body_preview}"
                    )
                    self.logger.error(f"[VOICE_CLONE_API_ERROR] {error_msg}")

                    # Parse error for user-friendly message
                    user_message = parse_cartesia_error(response.status_code, response.text)
                    self.logger.info(f"[VOICE_CLONE_USER_ERROR] User message: {user_message}")

                    # Capture in Sentry for monitoring
                    capture_exception_with_context(
                        Exception(error_msg),
                        extra={
                            "voice_name": name,
                            "status_code": response.status_code,
                            "response_body": body_preview,
                            "files_count": len(files),
                            "total_size_bytes": total_size_bytes,
                            "user_message": user_message,
                        },
                        tags={
                            "component": "cartesia_service",
                            "operation": "create_voice_clone",
                            "failure_type": "api_error",
                            "status_code": str(response.status_code),
                        },
                    )

                    raise CartesiaVoiceCreationError(
                        message=f"Cartesia API error: {response.status_code}",
                        stage="api_call",
                        raw_response={"status_code": response.status_code, "body": body_preview},
                        user_message=user_message,
                    )

                # Parse response JSON
                try:
                    resp_json = response.json()
                except Exception as json_error:
                    error_msg = f"Failed to parse Cartesia API response as JSON: {json_error}"
                    self.logger.error(f"[VOICE_CLONE_PARSE_ERROR] {error_msg}")
                    raise CartesiaVoiceCreationError(
                        message=error_msg,
                        stage="response_parsing",
                        raw_response={"raw_text": response.text[:500]},
                    )

                # Log response (truncate embedding for readability)
                log_resp = dict(resp_json) if isinstance(resp_json, dict) else {"raw": resp_json}
                if "embedding" in log_resp and isinstance(log_resp.get("embedding"), list):
                    embedding_len = len(log_resp["embedding"])
                    log_resp["embedding"] = f"<{embedding_len} floats>"
                self.logger.info(f"[VOICE_CLONE_API_PARSED] Cartesia response: {log_resp}")

                # Validate response structure
                if not isinstance(resp_json, dict):
                    error_msg = (
                        f"Unexpected Cartesia API response type: {type(resp_json).__name__}. "
                        f"Expected dict. Response: {str(resp_json)[:200]}"
                    )
                    self.logger.error(f"[VOICE_CLONE_RESPONSE_ERROR] {error_msg}")
                    raise CartesiaVoiceCreationError(
                        message=error_msg,
                        stage="response_validation",
                        raw_response=resp_json,
                    )

                # Extract voice_id - check multiple possible field names
                voice_id = (
                    resp_json.get("id")
                    or resp_json.get("voice_id")
                    or resp_json.get("embedding_id")
                )

                # Get embedding
                embedding = resp_json.get("embedding")

                # Validate embedding if present
                if embedding is not None:
                    if not isinstance(embedding, list):
                        self.logger.warning(
                            f"[VOICE_CLONE_EMBEDDING_WARNING] Unexpected embedding type: "
                            f"{type(embedding).__name__}. Expected list."
                        )
                        embedding = None
                    elif len(embedding) == 0:
                        self.logger.warning(
                            "[VOICE_CLONE_EMBEDDING_WARNING] Empty embedding returned by Cartesia"
                        )
                        embedding = None
                    else:
                        self.logger.info(
                            f"[VOICE_CLONE_EMBEDDING] Received embedding with {len(embedding)} dimensions"
                        )

                # If no voice_id provided but we have a valid embedding, generate deterministic ID
                if not voice_id and embedding:
                    embedding_str = str(embedding)
                    hash_obj = hashlib.sha256(embedding_str.encode())
                    voice_id = f"cartesia_{hash_obj.hexdigest()[:16]}"
                    self.logger.info(
                        f"[VOICE_CLONE_ID_GENERATED] Generated voice_id from embedding hash: {voice_id}"
                    )

                # Final validation - we must have a voice_id
                if not voice_id:
                    error_msg = (
                        f"Could not extract or generate voice_id from Cartesia response. "
                        f"Response keys: {list(resp_json.keys())}. "
                        f"Has embedding: {embedding is not None}"
                    )
                    self.logger.error(f"[VOICE_CLONE_ID_ERROR] {error_msg}")

                    capture_exception_with_context(
                        CartesiaVoiceCreationError(error_msg, stage="id_extraction"),
                        extra={
                            "voice_name": name,
                            "response_keys": list(resp_json.keys()),
                            "has_embedding": embedding is not None,
                            "response_preview": str(resp_json)[:500],
                        },
                        tags={
                            "component": "cartesia_service",
                            "operation": "create_voice_clone",
                            "failure_type": "no_voice_id",
                        },
                    )

                    raise CartesiaVoiceCreationError(
                        message=error_msg,
                        stage="id_extraction",
                        raw_response=resp_json,
                    )

                # Verify embedding is present (required for TTS)
                if not embedding:
                    self.logger.warning(
                        f"[VOICE_CLONE_NO_EMBEDDING] Voice {voice_id} created but no embedding returned. "
                        "TTS may not work correctly."
                    )

                self.logger.info(
                    f"[VOICE_CLONE_CREATED] Successfully created voice clone in Cartesia: "
                    f"name={name}, voice_id={voice_id}, has_embedding={embedding is not None}"
                )

                # Optional: Verify the voice actually exists in Cartesia
                if verify_creation:
                    await self._verify_voice_exists(voice_id, name)

                return {
                    "voice_id": voice_id,
                    "name": name.strip(),
                    "description": description,
                    "language": language,
                    "status": "success",
                    "embedding": embedding,
                    "embedding_dimensions": len(embedding) if embedding else 0,
                    "verified": verify_creation,
                    "raw": resp_json,
                }

        except CartesiaVoiceCreationError:
            raise
        except CartesiaVoiceVerificationError:
            raise
        except httpx.TimeoutException as e:
            error_msg = f"Cartesia API request timed out after {timeout}s"
            self.logger.error(f"[VOICE_CLONE_TIMEOUT] {error_msg}: {e}")
            capture_exception_with_context(
                e,
                extra={"voice_name": name, "timeout": timeout},
                tags={
                    "component": "cartesia_service",
                    "operation": "create_voice_clone",
                    "failure_type": "timeout",
                },
            )
            raise CartesiaVoiceCreationError(message=error_msg, stage="api_call")
        except httpx.HTTPStatusError as e:
            error_msg = (
                f"HTTP status error creating Cartesia voice clone: "
                f"{e.response.status_code} - {e.response.text[:500]}"
            )
            self.logger.error(f"[VOICE_CLONE_HTTP_ERROR] {error_msg}")
            raise CartesiaVoiceCreationError(
                message=error_msg,
                stage="api_call",
                raw_response={"status_code": e.response.status_code, "body": e.response.text[:500]},
            )
        except httpx.HTTPError as e:
            error_msg = f"HTTP error creating Cartesia voice clone: {str(e)}"
            self.logger.error(f"[VOICE_CLONE_HTTP_ERROR] {error_msg}")
            raise CartesiaVoiceCreationError(message=error_msg, stage="api_call")

    async def _verify_voice_exists(
        self,
        voice_id: str,
        voice_name: str,
        max_retries: int = 2,
        retry_delay: float = 1.0,
    ) -> bool:
        """
        Verify that a voice clone actually exists in Cartesia after creation.

        For embedding-based voices (generated IDs starting with 'cartesia_'),
        we cannot verify via GET /voices/{id} since the ID is not real.
        Instead, we verify the embedding was returned and is valid.

        Args:
            voice_id: The voice ID to verify
            voice_name: Voice name for logging
            max_retries: Number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            True if verification passed

        Raises:
            CartesiaVoiceVerificationError: If verification fails
        """
        # For generated IDs (embedding-based), we can't verify via API
        # The embedding itself is the "voice" - it's used directly for TTS
        if voice_id.startswith("cartesia_"):
            self.logger.info(
                f"[VOICE_CLONE_VERIFY] Voice {voice_id} uses embedding-based ID. "
                "Verification skipped (embedding is stored locally for TTS)."
            )
            return True

        # For real Cartesia voice IDs, verify via API
        self.logger.info(f"[VOICE_CLONE_VERIFY] Verifying voice exists in Cartesia: {voice_id}")

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                voice_data = await self.get_voice(voice_id)

                if voice_data:
                    self.logger.info(
                        f"[VOICE_CLONE_VERIFIED] Voice {voice_id} verified in Cartesia. "
                        f"Response keys: {list(voice_data.keys()) if isinstance(voice_data, dict) else 'N/A'}"
                    )
                    return True

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    last_error = "Voice not found in Cartesia (404)"
                else:
                    last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"

                self.logger.warning(
                    f"[VOICE_CLONE_VERIFY_RETRY] Attempt {attempt + 1}/{max_retries + 1} failed: {last_error}"
                )

            except Exception as e:
                last_error = str(e)
                self.logger.warning(
                    f"[VOICE_CLONE_VERIFY_RETRY] Attempt {attempt + 1}/{max_retries + 1} failed: {last_error}"
                )

            if attempt < max_retries:
                await asyncio.sleep(retry_delay)

        # All retries exhausted
        error_msg = (
            f"Voice verification failed after {max_retries + 1} attempts. "
            f"Voice ID: {voice_id}, Name: {voice_name}. Last error: {last_error}"
        )
        self.logger.error(f"[VOICE_CLONE_VERIFY_FAILED] {error_msg}")

        capture_exception_with_context(
            CartesiaVoiceVerificationError(error_msg, voice_id, last_error),
            extra={
                "voice_id": voice_id,
                "voice_name": voice_name,
                "retries": max_retries,
                "last_error": last_error,
            },
            tags={
                "component": "cartesia_service",
                "operation": "verify_voice",
                "failure_type": "verification_failed",
            },
        )

        raise CartesiaVoiceVerificationError(
            message=error_msg,
            voice_id=voice_id,
            verification_error=last_error,
        )

    async def get_voice(self, voice_id: str) -> Dict[str, Any]:
        headers = self._auth_headers()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.API_BASE_URL}/voices/{voice_id}", headers=headers)
            response.raise_for_status()
            return response.json()

    async def list_voices(self) -> List[Dict[str, Any]]:
        headers = self._auth_headers()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.API_BASE_URL}/voices", headers=headers)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                return payload
            return payload.get("voices", []) or payload.get("data", {}).get("voices", [])

    async def delete_voice(self, voice_id: str) -> Dict[str, Any]:
        """
        Delete a voice clone from Cartesia.

        Args:
            voice_id: Cartesia voice ID to delete

        Returns:
            Dictionary with status and message

        Raises:
            ValueError: If voice_id is invalid
            httpx.HTTPStatusError: If Cartesia API call fails
        """
        if not voice_id or not voice_id.strip():
            raise ValueError("Voice ID is required")

        self.logger.info(f"Deleting voice from Cartesia: {voice_id}")

        headers = self._auth_headers()

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.API_BASE_URL}/voices/{voice_id}",
                    headers=headers,
                )

                if response.status_code == 404:
                    self.logger.warning(f"Voice not found in Cartesia: {voice_id}")
                    # Still return success since the voice doesn't exist
                    return {
                        "voice_id": voice_id,
                        "status": "success",
                        "message": f"Voice {voice_id} not found (may have been already deleted)",
                    }

                response.raise_for_status()

                self.logger.info(f"Voice deleted successfully from Cartesia: {voice_id}")

                return {
                    "voice_id": voice_id,
                    "status": "success",
                    "message": f"Voice {voice_id} deleted successfully",
                }

        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"HTTP status error deleting Cartesia voice: {e.response.status_code} - {e.response.text[:500]}"
            )
            raise
        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error deleting Cartesia voice: {str(e)}")
            raise
