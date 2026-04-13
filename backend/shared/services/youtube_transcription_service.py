"""
Simplified YouTube Transcription Service for processing YouTube videos.

This service handles:
1. YouTube video download and audio extraction using yt-dlp
2. Audio transcription using AssemblyAI
3. Content chunking for storage in ContentChunk table
"""

import asyncio
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import yt_dlp


class YouTubeTranscriptionService:
    """Service for processing YouTube videos and extracting transcripts."""

    def __init__(self):
        self.assemblyai_api_key = os.getenv("ASSEMBLYAI_API_KEY")
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))  # Characters per chunk
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))  # Overlap between chunks

        if not self.assemblyai_api_key:
            raise ValueError("ASSEMBLYAI_API_KEY environment variable is required")

    async def _download_video_audio(
        self, youtube_url: str, temp_path: Path
    ) -> tuple[Dict[str, Any], Path]:
        """
        Download YouTube video audio and extract metadata using MP3 format

        Args:
            youtube_url: YouTube video URL
            temp_path: Temporary directory path

        Returns:
            Tuple of (video_info, audio_file_path)
        """
        try:
            # First get video info
            video_info = await self._get_video_info(youtube_url)

            # Generate clean base name
            base_name = self._sanitize_filename(video_info.get("title", "youtube_audio"))
            output_filename = temp_path / f"{base_name}.%(ext)s"

            # Configure yt-dlp options for MP3 download
            ydl_opts = {
                # Select best audio and convert to MP3
                "format": "bestaudio/best",
                "outtmpl": str(output_filename),
                "noplaylist": True,
                "retries": 3,
                "ignoreerrors": False,
                "quiet": True,
                "no_warnings": True,
                "cachedir": "/tmp/yt-dlp-cache",
                "prefer_ffmpeg": True,
                # Post-processing to convert to MP3
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }

            # Download and convert to MP3
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])

            # Find the downloaded MP3 file
            pattern = f"{base_name}.mp3"
            mp3_file = temp_path / pattern

            if not mp3_file.exists():
                # Fallback: look for any file with the base name
                pattern = f"{base_name}.*"
                downloaded_files = list(temp_path.glob(pattern))
                if downloaded_files:
                    mp3_file = downloaded_files[0]
                else:
                    raise RuntimeError("Downloaded audio file not found after successful download")

            return video_info, mp3_file

        except Exception as e:
            raise RuntimeError(f"Failed to download YouTube audio: {str(e)}")

    async def _get_video_info(self, url: str) -> Dict[str, Any]:
        """Get information about YouTube video without downloading"""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "cachedir": "/tmp/yt-dlp-cache",
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                return {
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration", 0),
                    "uploader": info.get("uploader", "Unknown"),
                    "upload_date": info.get("upload_date", "Unknown"),
                    "view_count": info.get("view_count", 0),
                    "description": info.get("description", ""),
                    "video_id": info.get("id", ""),
                    "webpage_url": info.get("webpage_url", url),
                    "channel": info.get("uploader", "Unknown Channel"),
                    "like_count": info.get("like_count", 0),
                    "thumbnail": info.get("thumbnail", ""),
                    "tags": info.get("tags", []),
                    "categories": info.get("categories", []),
                }

        except Exception as e:
            raise RuntimeError(f"Cannot access video information: {e}")

    def _sanitize_filename(self, filename: str, max_length: int = 100) -> str:
        """Sanitize filename for safe file system usage"""
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

    def _parse_upload_date(self, upload_date_str: Optional[str]) -> Optional[datetime]:
        """Parse upload date string to datetime object."""
        if not upload_date_str:
            return None

        try:
            # yt-dlp provides dates in YYYYMMDD format
            if len(upload_date_str) == 8:
                year = int(upload_date_str[:4])
                month = int(upload_date_str[4:6])
                day = int(upload_date_str[6:8])
                return datetime(year, month, day, tzinfo=timezone.utc)
        except (ValueError, IndexError):
            pass

        return None

    async def _transcribe_audio(self, audio_file: Path) -> str:
        """
        Transcribe audio file using AssemblyAI API.

        Args:
            audio_file: Path to audio file

        Returns:
            Transcript text
        """
        try:
            # AssemblyAI API endpoints
            upload_url = "https://api.assemblyai.com/v2/upload"
            transcript_url = "https://api.assemblyai.com/v2/transcript"

            headers = {"authorization": self.assemblyai_api_key, "content-type": "application/json"}

            # Use longer timeout for large file uploads and transcription requests
            timeout = httpx.Timeout(120.0, connect=60.0)

            async with httpx.AsyncClient(timeout=timeout) as client:
                # Step 1: Upload audio file
                upload_headers = {"authorization": self.assemblyai_api_key}

                # Read file content and upload
                with open(audio_file, "rb") as f:
                    file_content = f.read()

                upload_response = await client.post(
                    upload_url, headers=upload_headers, content=file_content
                )

                if upload_response.status_code != 200:
                    error_text = (
                        upload_response.text
                        if hasattr(upload_response, "text")
                        else str(upload_response.content)
                    )
                    raise RuntimeError(
                        f"Failed to upload audio: {upload_response.status_code} - {error_text}"
                    )

                try:
                    upload_result = upload_response.json()
                    audio_url = upload_result["upload_url"]
                except (KeyError, ValueError) as e:
                    raise RuntimeError(f"Invalid upload response format: {e}")

                # Step 2: Request transcription
                transcript_request = {
                    "audio_url": audio_url,
                    "language_detection": True,
                    "punctuate": True,
                    "format_text": True,
                    "speaker_labels": False,  # Disable speaker diarization for simplicity
                }

                transcript_response = await client.post(
                    transcript_url, json=transcript_request, headers=headers
                )

                if transcript_response.status_code != 200:
                    error_text = (
                        transcript_response.text
                        if hasattr(transcript_response, "text")
                        else str(transcript_response.content)
                    )
                    raise RuntimeError(
                        f"Failed to request transcription: {transcript_response.status_code} - {error_text}"
                    )

                try:
                    transcript_result = transcript_response.json()
                    transcript_id = transcript_result["id"]
                except (KeyError, ValueError) as e:
                    raise RuntimeError(f"Invalid transcription response format: {e}")

                # Step 3: Poll for completion
                polling_url = f"{transcript_url}/{transcript_id}"
                max_polls = 240  # Maximum 20 minutes of polling (240 * 5 seconds)
                poll_count = 0

                while poll_count < max_polls:
                    try:
                        polling_response = await client.get(polling_url, headers=headers)

                        if polling_response.status_code != 200:
                            error_text = (
                                polling_response.text
                                if hasattr(polling_response, "text")
                                else str(polling_response.content)
                            )
                            raise RuntimeError(
                                f"Failed to poll transcription: {polling_response.status_code} - {error_text}"
                            )

                        result = polling_response.json()
                        status = result.get("status")

                        if status == "completed":
                            transcript_text = result.get("text", "")
                            if not transcript_text:
                                raise RuntimeError("No transcript text returned from AssemblyAI")

                            # Clean and return transcript
                            cleaned_transcript = self._clean_transcript(transcript_text)
                            return cleaned_transcript

                        elif status == "error":
                            error_msg = result.get("error", "Unknown error")
                            raise RuntimeError(f"AssemblyAI transcription failed: {error_msg}")

                        elif status in ["queued", "processing"]:
                            # Wait before polling again - this is now non-blocking
                            await asyncio.sleep(5)
                            poll_count += 1
                            continue

                        else:
                            raise RuntimeError(f"Unknown transcription status: {status}")

                    except httpx.TimeoutException as e:
                        raise RuntimeError(f"Timeout during transcription polling: {e}")
                    except Exception as e:
                        raise RuntimeError(f"Error during transcription polling: {e}")

                # If we've exceeded max polls
                raise RuntimeError(f"Transcription timed out after {max_polls * 5} seconds")

        except httpx.TimeoutException as e:
            raise RuntimeError(f"HTTP timeout during transcription: {e}")
        except httpx.RequestError as e:
            raise RuntimeError(f"HTTP request error during transcription: {e}")
        except Exception as e:
            raise RuntimeError(f"AssemblyAI transcription failed: {str(e)}")

    def _clean_transcript(self, transcript: str) -> str:
        """
        Clean and normalize transcript text.

        Args:
            transcript: Raw transcript text

        Returns:
            Cleaned transcript text
        """
        # Remove excessive whitespace
        transcript = re.sub(r"\s+", " ", transcript)

        # Fix common transcription issues
        transcript = transcript.replace(" um ", " ")
        transcript = transcript.replace(" uh ", " ")
        transcript = transcript.replace(" ah ", " ")

        # Remove repeated words (simple case)
        transcript = re.sub(r"\b(\w+)\s+\1\b", r"\1", transcript)

        # Ensure proper sentence spacing
        transcript = re.sub(r"([.!?])\s*", r"\1 ", transcript)

        # Clean up and strip
        transcript = transcript.strip()

        return transcript

    def _enhance_transcript_with_metadata(self, transcript: str, metadata: Dict[str, Any]) -> str:
        """
        Enhance transcript with video metadata for better context.

        Args:
            transcript: Original transcript
            metadata: Video metadata

        Returns:
            Enhanced transcript with metadata context
        """
        enhanced_parts = []

        # Add video title and description as context
        if metadata.get("title"):
            enhanced_parts.append(f"Video Title: {metadata['title']}")

        if metadata.get("description"):
            # Truncate description to avoid too much noise
            description = metadata["description"][:500]
            enhanced_parts.append(f"Video Description: {description}")

        if metadata.get("channel"):
            enhanced_parts.append(f"Channel: {metadata['channel']}")

        if metadata.get("duration"):
            enhanced_parts.append(f"Duration: {metadata['duration']} seconds")

        # Add publication date if available
        if metadata.get("upload_date"):
            enhanced_parts.append(f"Published: {metadata['upload_date']}")

        # Add the actual transcript
        enhanced_parts.append("Transcript:")
        enhanced_parts.append(transcript)

        return "\n\n".join(enhanced_parts)

    def _chunk_text(self, text: str) -> List[str]:
        """
        Chunk text into overlapping segments.

        Args:
            text: Text to chunk

        Returns:
            List of text chunks
        """
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # If this is not the last chunk, try to find a good break point
            if end < len(text):
                # Look for sentence endings near the end
                break_point = self._find_good_break_point(text, start, end)
                if break_point > start:
                    end = break_point

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position with overlap
            start = end - self.chunk_overlap

        return chunks

    def _find_good_break_point(self, text: str, start: int, end: int) -> int:
        """
        Find a good break point for chunking (sentence boundary).

        Args:
            text: Full text
            start: Start index
            end: Proposed end index

        Returns:
            Better end index if found, otherwise original end
        """
        # Look for sentence endings in the last 200 characters
        search_start = max(start, end - 200)
        search_text = text[search_start:end]

        # Find sentence endings (., !, ?)
        sentence_endings = []
        for match in re.finditer(r"[.!?]\s+", search_text):
            sentence_endings.append(search_start + match.end())

        if sentence_endings:
            return sentence_endings[-1]  # Return the last sentence ending

        # If no sentence endings, look for paragraph breaks
        paragraph_breaks = []
        for match in re.finditer(r"\n\s*\n", search_text):
            paragraph_breaks.append(search_start + match.start())

        if paragraph_breaks:
            return paragraph_breaks[-1]

        # If no good break point found, return original end
        return end

    async def process_youtube_video(
        self, youtube_url: str, save_audio: bool = False, uploads_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Complete YouTube video processing pipeline.

        Args:
            youtube_url: YouTube video URL
            save_audio: Whether to save the MP3 file after processing
            uploads_path: Directory to save MP3 file (if save_audio=True)

        Returns:
            Dictionary containing video info, transcript, and chunks
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            try:
                # Step 1: Download audio and get video info
                video_info, audio_file = await self._download_video_audio(youtube_url, temp_path)

                # Step 2: Transcribe audio
                transcript = await self._transcribe_audio(audio_file)

                # Step 3: Enhance transcript with metadata
                enhanced_transcript = self._enhance_transcript_with_metadata(transcript, video_info)

                # Step 4: Chunk text
                chunks = self._chunk_text(enhanced_transcript)

                # Step 5: Save audio file if requested
                saved_audio_path = None
                if save_audio and uploads_path:
                    uploads_path.mkdir(exist_ok=True)
                    saved_audio_path = uploads_path / audio_file.name
                    import shutil

                    shutil.copy2(audio_file, saved_audio_path)

                return {
                    "video_info": video_info,
                    "transcript": transcript,
                    "enhanced_transcript": enhanced_transcript,
                    "chunks": chunks,
                    "audio_file_path": str(saved_audio_path) if saved_audio_path else None,
                    "chunk_count": len(chunks),
                    "transcript_length": len(transcript),
                }

            except Exception as e:
                raise RuntimeError(f"YouTube processing failed: {str(e)}")
