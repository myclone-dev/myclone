"""
Audio conversion utilities using ffmpeg via pydub

Handles conversion of various audio formats (WebM, MP3, M4A, etc.) to WAV format
suitable for ElevenLabs voice cloning API.
"""

import asyncio
import io
import logging
from pathlib import Path

from pydub import AudioSegment

logger = logging.getLogger(__name__)


async def convert_to_wav(
    file_content: bytes,
    filename: str,
    target_sample_rate: int = 44100,
    target_channels: int = 1,
) -> tuple[bytes, str]:
    """
    Convert audio file to WAV format asynchronously.

    Uses ffmpeg via pydub to convert various audio formats (WebM, MP3, M4A, FLAC, etc.)
    to WAV format suitable for ElevenLabs voice cloning.

    Args:
        file_content: Audio file content as bytes
        filename: Original filename (used to detect format)
        target_sample_rate: Target sample rate in Hz (default: 44100)
        target_channels: Target number of channels (default: 1 for mono)

    Returns:
        Tuple of (wav_bytes, wav_filename)

    Raises:
        ValueError: If audio format is unsupported or conversion fails

    Example:
        >>> webm_content = await file.read()
        >>> wav_content, wav_name = await convert_to_wav(webm_content, "recording.webm")
        >>> # wav_content is now WAV format, wav_name is "recording.wav"
    """

    def _convert() -> bytes:
        """Synchronous conversion function (runs in thread pool)"""
        try:
            # Detect format from filename extension
            ext = Path(filename).suffix.lstrip(".").lower()

            if not ext:
                raise ValueError(f"Cannot detect audio format: {filename} has no extension")

            logger.info(f"Converting {filename} ({ext}) to WAV format")

            # Load audio file from bytes
            # pydub auto-detects format if 'format' param is correct
            audio = AudioSegment.from_file(io.BytesIO(file_content), format=ext)

            # Apply audio processing for optimal quality
            # Set sample rate
            if audio.frame_rate != target_sample_rate:
                audio = audio.set_frame_rate(target_sample_rate)
                logger.debug(f"Resampled to {target_sample_rate} Hz")

            # Set channels (mono/stereo)
            if audio.channels != target_channels:
                audio = audio.set_channels(target_channels)
                logger.debug(f"Converted to {target_channels} channel(s)")

            # Export as WAV
            wav_buffer = io.BytesIO()
            audio.export(
                wav_buffer,
                format="wav",
                parameters=[
                    "-acodec",
                    "pcm_s16le",  # 16-bit PCM (standard WAV)
                ],
            )

            wav_bytes = wav_buffer.getvalue()

            logger.info(
                f"Conversion successful: {filename} → WAV "
                f"({len(file_content)} bytes → {len(wav_bytes)} bytes, "
                f"{audio.duration_seconds:.1f}s, {target_sample_rate}Hz, "
                f"{target_channels}ch)"
            )

            return wav_bytes

        except Exception as e:
            logger.error(f"Audio conversion failed for {filename}: {e}", exc_info=True)
            raise ValueError(f"Failed to convert {filename} to WAV: {str(e)}")

    # Run conversion in thread pool to avoid blocking event loop
    wav_bytes = await asyncio.to_thread(_convert)

    # Generate new filename with .wav extension
    wav_filename = Path(filename).stem + ".wav"

    return wav_bytes, wav_filename


def is_supported_audio_format(filename: str) -> bool:
    """
    Check if audio format is supported by ffmpeg/pydub.

    Args:
        filename: Filename to check

    Returns:
        True if format is supported, False otherwise

    Example:
        >>> is_supported_audio_format("audio.webm")
        True
        >>> is_supported_audio_format("audio.txt")
        False
    """
    supported_formats = {
        # Formats supported by ElevenLabs natively
        "wav",
        "mp3",
        "m4a",
        "flac",
        # Formats that need conversion
        "webm",
        "ogg",
        "opus",
        "aac",
        "wma",
        "aiff",
        "au",
    }

    ext = Path(filename).suffix.lstrip(".").lower()
    return ext in supported_formats


def needs_conversion(filename: str) -> bool:
    """
    Check if audio file needs conversion to WAV for ElevenLabs.

    ElevenLabs supports: .wav, .mp3, .m4a, .flac

    Args:
        filename: Filename to check

    Returns:
        True if conversion needed, False if format is already supported

    Example:
        >>> needs_conversion("audio.webm")
        True
        >>> needs_conversion("audio.wav")
        False
    """
    elevenlabs_supported = {"wav", "mp3", "m4a", "flac"}
    ext = Path(filename).suffix.lstrip(".").lower()

    return ext not in elevenlabs_supported and is_supported_audio_format(filename)
