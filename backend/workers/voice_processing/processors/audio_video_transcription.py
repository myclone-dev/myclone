"""Audio/Video transcription processor using AssemblyAI with timestamp-based chunking."""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import aiohttp
from loguru import logger
from utils.progress import ProgressTracker

from shared.voice_processing.errors import ErrorCode, VoiceProcessingError


class AudioVideoTranscriptionProcessor:
    """
    Process audio/video files for transcription using AssemblyAI with timestamp-based chunking.
    Supports both local files and URL downloads, with automatic audio extraction from video files.
    """

    def __init__(
        self,
        assemblyai_api_key: str,
        openai_api_key: Optional[str] = None,
        progress_tracker: Optional[ProgressTracker] = None,
    ):
        self.assemblyai_api_key = assemblyai_api_key
        self.openai_api_key = openai_api_key
        self.progress_tracker = progress_tracker
        self.base_url = "https://api.assemblyai.com/v2"

        # Initialize OpenAI client for chunk enrichment (if API key provided)
        self.openai_client = None
        if openai_api_key:
            try:
                from openai import AsyncOpenAI

                self.openai_client = AsyncOpenAI(api_key=openai_api_key)
                logger.info("✅ OpenAI client initialized for chunk enrichment")
            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to initialize OpenAI client: {e}. Chunk enrichment will be skipped."
                )
                self.openai_client = None

    async def _download_file(self, file_url: str, output_path: str) -> str:
        """Download file from URL to local path"""
        if self.progress_tracker:
            self.progress_tracker.update_progress(5, "Downloading audio/video file")

        try:
            logger.info(f"Downloading file from {file_url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    response.raise_for_status()

                    # Get total size for progress tracking
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded = 0

                    with open(output_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                            downloaded += len(chunk)

                            if total_size > 0 and self.progress_tracker:
                                progress = (
                                    5 + (downloaded / total_size) * 10
                                )  # 5-15% of total progress
                                self.progress_tracker.update_progress(
                                    progress, f"Downloaded {downloaded}/{total_size} bytes"
                                )

            if self.progress_tracker:
                self.progress_tracker.update_progress(15, "File download completed")

            logger.info(
                f"Successfully downloaded file to {output_path} ({os.path.getsize(output_path)} bytes)"
            )
            return output_path

        except Exception as e:
            logger.error(f"Failed to download file from {file_url}: {e}")
            raise VoiceProcessingError(
                message=f"Failed to download file: {str(e)}",
                error_code=ErrorCode.DOWNLOAD_FAILED,
            )

    def _is_video_file(self, file_path: str) -> bool:
        """Check if file is a video format that needs audio extraction"""
        video_extensions = {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".3gp"}
        return Path(file_path).suffix.lower() in video_extensions

    async def _extract_audio_from_video(self, video_path: str, output_audio_path: str) -> str:
        """Extract audio from video file using FFmpeg"""
        if self.progress_tracker:
            self.progress_tracker.update_progress(20, "Extracting audio from video")

        try:
            logger.info(f"Extracting audio from video: {video_path}")

            # Build FFmpeg command
            cmd = [
                "ffmpeg",
                "-i",
                video_path,
                "-vn",  # No video
                "-acodec",
                "libmp3lame",  # MP3 codec
                "-ab",
                "192k",  # Audio bitrate
                "-ar",
                "44100",  # Sample rate
                "-y",  # Overwrite output file
                output_audio_path,
            ]

            # Run FFmpeg
            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
                logger.error(f"FFmpeg failed: {error_msg}")
                raise VoiceProcessingError(
                    message=f"FFmpeg failed: {error_msg}",
                    error_code=ErrorCode.AUDIO_EXTRACTION_FAILED,
                )

            if self.progress_tracker:
                self.progress_tracker.update_progress(30, "Audio extraction completed")

            logger.info(
                f"Successfully extracted audio to {output_audio_path} ({os.path.getsize(output_audio_path)} bytes)"
            )
            return output_audio_path

        except VoiceProcessingError:
            raise
        except Exception as e:
            logger.error(f"Failed to extract audio from {video_path}: {e}")
            raise VoiceProcessingError(
                message=f"Failed to extract audio: {str(e)}",
                error_code=ErrorCode.AUDIO_EXTRACTION_FAILED,
            )

    async def _upload_to_assemblyai(self, file_path: str) -> str:
        """Upload audio file to AssemblyAI and return upload URL"""
        if self.progress_tracker:
            self.progress_tracker.update_progress(35, "Uploading audio to AssemblyAI")

        try:
            headers = {"authorization": self.assemblyai_api_key}

            async with aiohttp.ClientSession() as session:
                with open(file_path, "rb") as f:
                    async with session.post(
                        f"{self.base_url}/upload", headers=headers, data=f
                    ) as response:
                        response.raise_for_status()
                        result = await response.json()

                        if "upload_url" not in result:
                            raise VoiceProcessingError(
                                message="Failed to get upload URL from AssemblyAI",
                                error_code=ErrorCode.THIRD_PARTY_SERVICE_ERROR,
                            )

                        if self.progress_tracker:
                            self.progress_tracker.update_progress(45, "Audio uploaded successfully")

                        return result["upload_url"]

        except aiohttp.ClientError as e:
            raise VoiceProcessingError(
                message=f"Network error uploading to AssemblyAI: {str(e)}",
                error_code=ErrorCode.NETWORK_UNREACHABLE,
            )
        except Exception as e:
            raise VoiceProcessingError(
                message=f"Failed to upload audio: {str(e)}",
                error_code=ErrorCode.THIRD_PARTY_SERVICE_ERROR,
            )

    async def _transcribe_with_assemblyai(self, upload_url: str) -> Dict:
        """Submit transcription job to AssemblyAI and wait for completion"""
        # Don't start a new stage - let the caller manage stages
        if self.progress_tracker:
            self.progress_tracker.update_progress(45, "Starting transcription")

        headers = {"authorization": self.assemblyai_api_key, "content-type": "application/json"}

        # Submit transcription job
        data = {
            "audio_url": upload_url,
            "speaker_labels": True,  # Enable speaker diarization
            "punctuate": True,
            "format_text": True,
            "language_code": "en",  # Force English
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Submit job
                async with session.post(
                    f"{self.base_url}/transcript", headers=headers, json=data
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

                    transcript_id = result.get("id")
                    if not transcript_id:
                        raise VoiceProcessingError(
                            message="Failed to get transcript ID from AssemblyAI",
                            error_code=ErrorCode.THIRD_PARTY_SERVICE_ERROR,
                        )

                if self.progress_tracker:
                    self.progress_tracker.update_progress(50, "Transcription job submitted")

                # Poll for completion
                poll_url = f"{self.base_url}/transcript/{transcript_id}"
                timeout = 1800  # 30 minutes
                poll_interval = 5
                elapsed = 0

                while elapsed < timeout:
                    async with session.get(poll_url, headers=headers) as response:
                        response.raise_for_status()
                        result = await response.json()

                    status = result.get("status")

                    if status == "completed":
                        if self.progress_tracker:
                            self.progress_tracker.update_progress(80, "Transcription completed")
                        return result
                    elif status == "error":
                        error_msg = result.get("error", "Unknown transcription error")
                        raise VoiceProcessingError(
                            message=f"AssemblyAI transcription failed: {error_msg}",
                            error_code=ErrorCode.THIRD_PARTY_SERVICE_ERROR,
                        )
                    elif status in ["queued", "processing"]:
                        if self.progress_tracker:
                            progress = 50 + (elapsed / timeout) * 30  # 50-80% of total progress
                            self.progress_tracker.update_progress(
                                progress, f"Transcribing... ({elapsed}s)"
                            )

                        await asyncio.sleep(poll_interval)
                        elapsed += poll_interval
                    else:
                        logger.warning(f"Unknown transcription status: {status}")
                        await asyncio.sleep(poll_interval)
                        elapsed += poll_interval

                raise VoiceProcessingError(
                    message=f"AssemblyAI transcription timed out after {timeout} seconds",
                    error_code=ErrorCode.CONNECTION_TIMEOUT,
                )

        except aiohttp.ClientError as e:
            raise VoiceProcessingError(
                message=f"Network error during transcription: {str(e)}",
                error_code=ErrorCode.NETWORK_UNREACHABLE,
            )

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds to HH:MM:SS or MM:SS format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _count_tokens(self, text: str) -> int:
        """Rough token count estimation (1 token ≈ 4 characters for English)"""
        return len(text) // 4

    def _create_chunks_from_transcript(
        self,
        transcript_result: Dict,
        min_chunk_tokens: int = 400,
        max_chunk_tokens: int = 1000,  # Changed from 800 to 1000 as per user request
        target_duration: float = 45.0,
        source_info: Dict = None,
    ) -> List[Dict]:
        """Create semantic chunks from AssemblyAI transcript with timestamps"""
        if self.progress_tracker:
            self.progress_tracker.update_progress(82, "Creating timestamped chunks")

        logger.info("🔪 Starting chunking process from transcript")
        logger.info(
            f"📊 Chunking parameters: min_tokens={min_chunk_tokens}, max_tokens={max_chunk_tokens}, target_duration={target_duration}s"
        )

        # Extract utterances (speaker-segmented text with timestamps)
        utterances = transcript_result.get("utterances", [])

        # Log what we received from AssemblyAI
        logger.info(
            f"📥 AssemblyAI response: utterances={len(utterances)}, has_text={'text' in transcript_result}"
        )

        if not utterances:
            logger.warning("⚠️ No utterances found in transcript, falling back to words")
            # Fallback to words if no utterances
            words = transcript_result.get("words", [])
            logger.info(f"📥 Found {len(words)} words in transcript")

            if not words:
                # Last resort: chunk the raw text if no utterances or words
                full_text = transcript_result.get("text", "")
                if not full_text:
                    raise VoiceProcessingError(
                        message="No transcript data found in AssemblyAI response",
                        error_code=ErrorCode.THIRD_PARTY_SERVICE_ERROR,
                    )

                logger.warning(
                    f"⚠️ No words found either, chunking raw text ({len(full_text)} chars)"
                )
                return self._chunk_raw_text(
                    full_text, min_chunk_tokens, max_chunk_tokens, source_info
                )

            logger.info(f"📝 Converting {len(words)} words into utterance-like format")
            # Convert words to utterance-like format with better sentence detection
            utterances = []
            current_text = []
            current_start = None
            current_end = None
            current_speaker = "Speaker A"

            # Track sentence boundaries more carefully
            sentence_word_count = 0

            for word_idx, word in enumerate(words):
                word_text = word.get("text", "")
                if current_start is None:
                    current_start = word.get("start", 0)

                current_text.append(word_text)
                current_end = word.get("end", current_start)
                sentence_word_count += 1

                # Better sentence boundary detection
                is_sentence_end = word_text.endswith((".", "!", "?"))
                is_long_enough = sentence_word_count >= 8  # Minimum words per sentence
                is_very_long = sentence_word_count >= 30  # Force split after 30 words

                # Split on sentence boundaries or when we've accumulated enough words
                if (is_sentence_end and is_long_enough) or is_very_long:
                    utterances.append(
                        {
                            "text": " ".join(current_text),
                            "start": current_start,
                            "end": current_end,
                            "speaker": current_speaker,
                        }
                    )
                    current_text = []
                    current_start = None
                    sentence_word_count = 0

            # Add remaining text
            if current_text:
                utterances.append(
                    {
                        "text": " ".join(current_text),
                        "start": current_start or 0,
                        "end": current_end or 0,
                        "speaker": current_speaker,
                    }
                )
            logger.info(f"✅ Created {len(utterances)} utterances from words")
        else:
            logger.info(f"✅ Found {len(utterances)} utterances in transcript")

        # Convert utterances to standardized segments format
        segments = []
        for utterance in utterances:
            segment_text = utterance.get("text", "").strip()
            if not segment_text:
                continue

            segments.append(
                {
                    "text": segment_text,
                    "start": utterance.get("start", 0) / 1000.0,  # Convert ms to seconds
                    "duration": (utterance.get("end", 0) - utterance.get("start", 0)) / 1000.0,
                    "speaker": utterance.get("speaker"),
                    "confidence": utterance.get("confidence"),
                }
            )

        logger.info(f"📋 Converted {len(segments)} segments for chunking")

        # If we still only have 1 segment, it means the entire transcript is one block
        # We need to split it further by sentences
        if len(segments) == 1 and self._count_tokens(segments[0]["text"]) > max_chunk_tokens:
            logger.warning(
                f"⚠️ Single segment with {self._count_tokens(segments[0]['text'])} tokens detected, performing sentence-based splitting"
            )
            segments = self._split_large_segment(segments[0], max_chunk_tokens)
            logger.info(f"✅ Split into {len(segments)} smaller segments")

        # Log first few segments for debugging
        for i, seg in enumerate(segments[:3]):
            logger.debug(
                f"🔍 Segment {i}: text_len={len(seg['text'])}, tokens={self._count_tokens(seg['text'])}, start={seg['start']:.2f}s, duration={seg['duration']:.2f}s"
            )

        # Create semantic chunks
        chunks = []
        current_chunk = {
            "text": "",
            "start_time": 0,
            "end_time": 0,
            "segments": [],
            "speakers": set(),
        }

        chunks_split_reasons = []  # Track why chunks were split for logging
        skipped_segments = 0  # Track segments that failed to process

        for i, segment in enumerate(segments):
            try:
                segment_text = segment.get("text", "").strip()
                if not segment_text:
                    logger.debug(f"⚠️ Skipping empty segment at index {i}")
                    continue

                # Validate segment has required fields
                segment_start = segment.get("start")
                segment_duration = segment.get("duration", 0)

                if segment_start is None:
                    logger.warning(f"⚠️ Segment {i} missing 'start' timestamp, skipping")
                    skipped_segments += 1
                    continue

                # Track speakers if available
                speaker = segment.get("speaker")

                # Initialize first chunk
                if not current_chunk["text"]:
                    current_chunk["start_time"] = segment_start
                    current_chunk["text"] = segment_text
                    current_chunk["end_time"] = segment_start + segment_duration
                    current_chunk["segments"].append(segment)
                    if speaker:
                        current_chunk["speakers"].add(speaker)
                    logger.debug(f"🆕 Initialized first chunk with segment {i}")
                    continue

                # Calculate potential new chunk stats
                potential_text = current_chunk["text"] + " " + segment_text
                potential_tokens = self._count_tokens(potential_text)
                potential_duration = segment_start + segment_duration - current_chunk["start_time"]
                current_tokens = self._count_tokens(current_chunk["text"])

                # Decide whether to continue current chunk or start new one
                should_split = False
                split_reason = ""

                # Split if we exceed max tokens
                if potential_tokens > max_chunk_tokens:
                    should_split = True
                    split_reason = f"max_tokens_exceeded (potential={potential_tokens}, max={max_chunk_tokens})"

                # Split if we exceed target duration and have minimum tokens
                elif potential_duration > target_duration and current_tokens >= min_chunk_tokens:
                    should_split = True
                    split_reason = f"target_duration_exceeded (duration={potential_duration:.1f}s, target={target_duration}s, tokens={current_tokens})"

                # Split at sentence boundaries when reasonable
                elif current_tokens >= min_chunk_tokens and segment_text.endswith(
                    (".", "!", "?", ".\n", "!\n", "?\n")
                ):
                    if potential_duration > target_duration * 0.7:
                        should_split = True
                        split_reason = f"sentence_boundary (tokens={current_tokens}, duration={potential_duration:.1f}s)"

                if should_split:
                    # Log chunk creation
                    logger.debug(
                        f"✂️ Splitting chunk {len(chunks)}: "
                        f"tokens={current_tokens}, "
                        f"duration={current_chunk['end_time'] - current_chunk['start_time']:.1f}s, "
                        f"reason={split_reason}"
                    )
                    chunks_split_reasons.append(split_reason)

                    # Finalize current chunk
                    current_chunk["speakers"] = (
                        list(current_chunk["speakers"]) if current_chunk["speakers"] else None
                    )
                    chunks.append(current_chunk.copy())

                    # Start new chunk
                    current_chunk = {
                        "text": segment_text,
                        "start_time": segment_start,
                        "end_time": segment_start + segment_duration,
                        "segments": [segment],
                        "speakers": {speaker} if speaker else set(),
                    }
                    logger.debug(f"🆕 Started new chunk {len(chunks)} with segment {i}")
                else:
                    # Continue current chunk
                    current_chunk["text"] = potential_text
                    current_chunk["end_time"] = segment_start + segment_duration
                    current_chunk["segments"].append(segment)
                    if speaker:
                        current_chunk["speakers"].add(speaker)

            except Exception as e:
                # Log error but continue processing remaining segments
                logger.error(
                    f"❌ Error processing segment {i}: {e}. Segment data: {segment}", exc_info=True
                )
                skipped_segments += 1
                continue

        # Log if we skipped any segments
        if skipped_segments > 0:
            logger.warning(f"⚠️ Skipped {skipped_segments} malformed segments during chunking")

        # Add final chunk
        if current_chunk["text"]:
            final_tokens = self._count_tokens(current_chunk["text"])
            final_duration = current_chunk["end_time"] - current_chunk["start_time"]
            logger.debug(
                f"✅ Finalizing last chunk: tokens={final_tokens}, duration={final_duration:.1f}s"
            )
            current_chunk["speakers"] = (
                list(current_chunk["speakers"]) if current_chunk["speakers"] else None
            )
            chunks.append(current_chunk)

        logger.info(f"✅ Created {len(chunks)} chunks from {len(segments)} segments")

        # Log chunk statistics
        if chunks:
            total_tokens = sum(self._count_tokens(c["text"]) for c in chunks)
            total_duration = sum(c["end_time"] - c["start_time"] for c in chunks)
            avg_tokens = total_tokens / len(chunks)
            avg_duration = total_duration / len(chunks)
            logger.info(
                f"📊 Chunk statistics: "
                f"total_tokens={total_tokens}, "
                f"avg_tokens={avg_tokens:.0f}, "
                f"total_duration={total_duration:.1f}s, "
                f"avg_duration={avg_duration:.1f}s"
            )

            # Log first few chunks for verification
            for i, chunk in enumerate(chunks[:3]):
                chunk_tokens = self._count_tokens(chunk["text"])
                chunk_duration = chunk["end_time"] - chunk["start_time"]
                logger.info(
                    f"🔍 Chunk {i}: "
                    f"tokens={chunk_tokens}, "
                    f"duration={chunk_duration:.1f}s, "
                    f"text_preview={chunk['text'][:100]}..."
                )

        # Enrich chunks with metadata
        enriched_chunks = []
        for i, chunk in enumerate(chunks):
            enriched = {
                # Chunk identification
                "chunk_id": i,
                "chunk_index": i,
                # Chunk content (vectorized)
                "content": chunk["text"],  # Changed from "text" to "content" for consistency
                "token_count": self._count_tokens(chunk["text"]),
                # Temporal information
                "start_time": round(chunk["start_time"], 2),
                "end_time": round(chunk["end_time"], 2),
                "duration": round(chunk["end_time"] - chunk["start_time"], 2),
                "start_time_formatted": self._format_timestamp(chunk["start_time"]),
                "end_time_formatted": self._format_timestamp(chunk["end_time"]),
                # Speaker information (if available)
                "speakers": chunk.get("speakers"),
                "speaker_count": len(chunk.get("speakers", [])) if chunk.get("speakers") else None,
                # Source metadata - use content_type (audio/video) as source for proper RAG categorization
                "source": source_info.get("content_type", "audio") if source_info else "audio",
                "file_path": source_info.get("file_path") if source_info else None,
                "file_url": source_info.get("url") if source_info else None,
                "file_size": source_info.get("file_size") if source_info else None,
                # Context for LLM
                "context": f"Audio/Video transcript from {self._format_timestamp(chunk['start_time'])} to {self._format_timestamp(chunk['end_time'])}",
                "full_context": f"Source: {source_info.get('source', 'Unknown')}\nTimestamp: {self._format_timestamp(chunk['start_time'])} - {self._format_timestamp(chunk['end_time'])}\nDuration: {round(chunk['end_time'] - chunk['start_time'], 1)}s",
                # Metadata
                "extracted_at": datetime.now().isoformat(),
                "segment_count": len(chunk.get("segments", [])),
                "content_type": "audio_transcript",
            }

            enriched_chunks.append(enriched)

        if self.progress_tracker:
            self.progress_tracker.update_progress(90, f"Created {len(enriched_chunks)} chunks")

        logger.info(
            f"✅ Chunking complete: Created {len(enriched_chunks)} enriched transcript chunks from {len(segments)} segments"
        )

        return enriched_chunks

    def _split_large_segment(self, segment: Dict, max_tokens: int) -> List[Dict]:
        """Split a large segment into smaller segments based on sentences and token limits"""
        text = segment["text"]
        start_time = segment["start"]
        duration = segment["duration"]
        speaker = segment.get("speaker")

        logger.info(
            f"🔪 Splitting large segment: {self._count_tokens(text)} tokens, {len(text)} chars"
        )

        # Split by sentences first
        import re

        # Split on sentence boundaries (., !, ?) followed by space or end of string
        sentence_pattern = r"([.!?]+[\s\n]+|[.!?]+$)"
        parts = re.split(sentence_pattern, text)

        # Reconstruct sentences (combine text with punctuation)
        sentences = []
        for i in range(0, len(parts) - 1, 2):
            if i + 1 < len(parts):
                sentences.append(parts[i] + parts[i + 1])
            else:
                sentences.append(parts[i])
        if len(parts) % 2 == 1 and parts[-1].strip():
            sentences.append(parts[-1])

        logger.info(f"📝 Split into {len(sentences)} sentences")

        # If no sentence splits, split by word count
        if len(sentences) <= 1:
            words = text.split()
            words_per_chunk = int(
                max_tokens * 3.5
            )  # Rough estimate: 4 chars per token, avg word length
            sentences = [
                " ".join(words[i : i + words_per_chunk])
                for i in range(0, len(words), words_per_chunk)
            ]
            logger.info(f"📝 No sentences found, split into {len(sentences)} word-based segments")

        # Calculate time per character for timestamp distribution
        time_per_char = duration / len(text) if len(text) > 0 else 0

        # Create segments from sentences, grouping if needed to respect token limits
        segments = []
        current_segment_text = ""
        current_segment_start = start_time
        chars_processed = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            potential_text = (
                current_segment_text + " " + sentence if current_segment_text else sentence
            )
            potential_tokens = self._count_tokens(potential_text)

            if potential_tokens > max_tokens and current_segment_text:
                # Save current segment
                segment_duration = len(current_segment_text) * time_per_char
                segments.append(
                    {
                        "text": current_segment_text,
                        "start": current_segment_start,
                        "duration": segment_duration,
                        "speaker": speaker,
                        "confidence": segment.get("confidence"),
                    }
                )

                # Start new segment
                current_segment_text = sentence
                chars_processed += len(current_segment_text)
                current_segment_start = start_time + (chars_processed * time_per_char)
            else:
                current_segment_text = potential_text

        # Add final segment
        if current_segment_text:
            segment_duration = len(current_segment_text) * time_per_char
            segments.append(
                {
                    "text": current_segment_text,
                    "start": current_segment_start,
                    "duration": segment_duration,
                    "speaker": speaker,
                    "confidence": segment.get("confidence"),
                }
            )

        logger.info(f"✅ Created {len(segments)} segments from large segment")
        return segments

    def _chunk_raw_text(
        self, text: str, min_tokens: int, max_tokens: int, source_info: Dict = None
    ) -> List[Dict]:
        """Chunk raw text when no utterances or words are available"""
        logger.warning("⚠️ Using raw text chunking - no timestamp information available")

        # Split by sentences
        import re

        sentence_pattern = r"([.!?]+[\s\n]+|[.!?]+$)"
        parts = re.split(sentence_pattern, text)

        sentences = []
        for i in range(0, len(parts) - 1, 2):
            if i + 1 < len(parts):
                sentences.append((parts[i] + parts[i + 1]).strip())
            else:
                sentences.append(parts[i].strip())
        if len(parts) % 2 == 1 and parts[-1].strip():
            sentences.append(parts[-1].strip())

        # Group sentences into chunks
        chunks = []
        current_chunk_text = ""

        for sentence in sentences:
            if not sentence:
                continue

            potential_text = current_chunk_text + " " + sentence if current_chunk_text else sentence
            potential_tokens = self._count_tokens(potential_text)

            if potential_tokens > max_tokens and current_chunk_text:
                chunks.append({"text": current_chunk_text})
                current_chunk_text = sentence
            else:
                current_chunk_text = potential_text

        if current_chunk_text:
            chunks.append({"text": current_chunk_text})

        # Enrich with minimal metadata
        enriched_chunks = []
        for i, chunk in enumerate(chunks):
            enriched = {
                "chunk_id": i,
                "chunk_index": i,
                "content": chunk["text"],
                "token_count": self._count_tokens(chunk["text"]),
                "start_time": 0,
                "end_time": 0,
                "duration": 0,
                "start_time_formatted": "00:00",
                "end_time_formatted": "00:00",
                "speakers": None,
                "speaker_count": None,
                "source": source_info.get("content_type", "audio") if source_info else "audio",
                "file_path": source_info.get("file_path") if source_info else None,
                "file_url": source_info.get("url") if source_info else None,
                "file_size": source_info.get("file_size") if source_info else None,
                "context": f"Transcript chunk {i+1} of {len(chunks)}",
                "full_context": f"Source: {source_info.get('source', 'Unknown')}\nChunk: {i+1}/{len(chunks)}",
                "extracted_at": datetime.now().isoformat(),
                "segment_count": 0,
                "content_type": "audio_transcript",
            }
            enriched_chunks.append(enriched)

        logger.info(f"✅ Created {len(enriched_chunks)} chunks from raw text")
        return enriched_chunks

    async def _enrich_chunk_with_openai(self, chunk_text: str) -> Dict:
        """
        Use OpenAI to generate summary and keywords for a given chunk.
        Matches PDF enrichment format.
        """
        if not self.openai_client:
            return {"summary": "", "keywords": []}

        prompt = f"""
        You are enriching transcript text for knowledge-base vectorization.
        Return a 1-sentence summary and 5 keywords in JSON format.

        Example output:
        {{
          "summary": "...",
          "keywords": ["...", "...", "..."]
        }}

        Text:
        {chunk_text[:4000]}
        """

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates structured summaries.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=150,
                temperature=0.3,
            )

            content = response.choices[0].message.content
            import json

            enriched = json.loads(content)
            logger.debug(f"✅ Generated summary and {len(enriched.get('keywords', []))} keywords")
        except Exception as e:
            logger.warning(f"OpenAI enrichment failed: {e}")
            enriched = {"summary": "", "keywords": []}

        return enriched

    async def process_audio_video(
        self,
        input_source: str,
        output_dir: str,
        min_chunk_tokens: int = 400,
        max_chunk_tokens: int = 800,
        target_chunk_duration: float = 45.0,
        s3_uri: Optional[str] = None,  # Add S3 URI parameter
        content_type: Optional[str] = None,  # Explicit content type (audio/video)
    ) -> Dict:
        """
        Main processing pipeline for audio/video transcription with chunking.

        Args:
            input_source: Local file path or URL to audio/video file
            output_dir: Directory to store temporary files
            min_chunk_tokens: Minimum tokens per chunk
            max_chunk_tokens: Maximum tokens per chunk
            target_chunk_duration: Target duration per chunk in seconds
            s3_uri: Optional S3 URI where the file is stored (for metadata)
            content_type: Optional explicit content type ('audio' or 'video') to override detection

        Returns:
            Dict with 'chunks' (list of enriched transcript chunks) and 'full_transcript' (complete text from AssemblyAI)
        """
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Determine if input is URL or local file
        is_url = input_source.startswith(("http://", "https://"))
        temp_files = []

        try:
            # Don't start a new stage - let the caller manage stages
            logger.info(f"Processing audio/video source: {input_source}")

            # Handle input source
            if is_url:
                # Download file from URL
                parsed_url = urlparse(input_source)
                file_extension = Path(parsed_url.path).suffix or ".mp3"  # Default to mp3
                temp_input_path = os.path.join(output_dir, f"downloaded_file{file_extension}")

                await self._download_file(input_source, temp_input_path)
                temp_files.append(temp_input_path)

                # Use S3 URI if available, otherwise fall back to URL
                file_ref = s3_uri if s3_uri else input_source

                source_info = {
                    "source": "url",
                    "url": input_source,
                    "file_path": file_ref,  # Both file_path and file_url point to same location
                    "file_url": file_ref,
                    "file_size": os.path.getsize(temp_input_path),
                }
                audio_path = temp_input_path
            else:
                # Local file
                if not os.path.exists(input_source):
                    raise VoiceProcessingError(
                        message=f"Input file not found: {input_source}",
                        error_code=ErrorCode.FILE_NOT_FOUND,
                    )

                # Use S3 URI if available, otherwise use local path
                file_ref = s3_uri if s3_uri else input_source

                source_info = {
                    "source": "local_file",
                    "file_path": file_ref,  # Both file_path and file_url point to same location
                    "file_url": file_ref,
                    "file_size": os.path.getsize(input_source),
                }
                audio_path = input_source

            # Determine content type: use explicit parameter if provided, otherwise detect from file
            if content_type:
                # Use explicit content type (e.g., when video handler already extracted audio)
                source_info["content_type"] = content_type
                logger.info(f"Using explicit content_type: {content_type}")
            elif self._is_video_file(audio_path):
                # Detect video file and extract audio
                temp_audio_path = os.path.join(output_dir, "extracted_audio.mp3")
                await self._extract_audio_from_video(audio_path, temp_audio_path)
                temp_files.append(temp_audio_path)
                audio_path = temp_audio_path
                source_info["content_type"] = "video"
                logger.info("Detected video file, extracted audio")
            else:
                # Default to audio
                source_info["content_type"] = "audio"
                logger.info("Using content_type: audio")

            # Upload to AssemblyAI
            upload_url = await self._upload_to_assemblyai(audio_path)

            # Transcribe with AssemblyAI
            transcript_result = await self._transcribe_with_assemblyai(upload_url)

            # Debug: Log the transcript_result structure
            logger.info(f"📋 AssemblyAI transcript_result type: {type(transcript_result)}")
            logger.info(
                f"📋 AssemblyAI transcript_result keys: {transcript_result.keys() if isinstance(transcript_result, dict) else 'Not a dict'}"
            )

            # Extract full transcript text from AssemblyAI
            if not isinstance(transcript_result, dict):
                logger.error(f"❌ transcript_result is not a dict: {type(transcript_result)}")
                raise VoiceProcessingError(
                    message=f"Invalid transcript result type from AssemblyAI: {type(transcript_result)}",
                    error_code=ErrorCode.THIRD_PARTY_SERVICE_ERROR,
                )

            full_transcript = transcript_result.get("text", "")
            logger.info(f"Extracted full transcript: {len(full_transcript)} characters")

            # Extract audio duration from AssemblyAI response (already in seconds)
            audio_duration_seconds = transcript_result.get("audio_duration", 0)

            # Log the raw value for debugging
            logger.info(f"📊 Raw audio_duration from AssemblyAI: {audio_duration_seconds} seconds")

            # Convert to integer (handle both int and float)
            if audio_duration_seconds:
                audio_duration_seconds = int(audio_duration_seconds)
            else:
                audio_duration_seconds = 0
                logger.warning(
                    f"⚠️ No audio_duration in AssemblyAI response! Available keys: {list(transcript_result.keys())}"
                )

            logger.info(f"Extracted audio duration: {audio_duration_seconds} seconds")

            # Create chunks from transcript
            chunks = self._create_chunks_from_transcript(
                transcript_result,
                min_chunk_tokens=min_chunk_tokens,
                max_chunk_tokens=max_chunk_tokens,
                target_duration=target_chunk_duration,
                source_info=source_info,
            )

            logger.info(f"Audio/video processing completed: {len(chunks)} chunks created")

            # Enrich chunks with OpenAI (summary, keywords) and update metadata
            if self.progress_tracker:
                self.progress_tracker.update_progress(85, "Enriching chunks with AI summaries")

            enriched_chunks = []
            for i, chunk in enumerate(chunks):
                # Generate summary and keywords using the "content" field
                chunk_text = chunk.get("content", chunk.get("text", ""))
                enrichment = await self._enrich_chunk_with_openai(chunk_text)

                # Update chunk with enrichment data and standardized metadata
                chunk["summary"] = enrichment.get("summary", "")
                chunk["keywords"] = enrichment.get("keywords", [])

                # Update context and full_context to match PDF format (summary|keywords)
                chunk["context"] = enrichment.get("summary", "")
                chunk["full_context"] = (
                    f"{enrichment.get('summary', '')}|{', '.join(enrichment.get('keywords', []))}"
                )

                # Ensure file_path and file_url are both set (already done in source_info)
                enriched_chunks.append(chunk)

                if (i + 1) % 10 == 0:
                    logger.info(f"✅ Enriched {i + 1}/{len(chunks)} chunks")

            logger.info(
                f"✅ Enriched all {len(enriched_chunks)} chunks with AI summaries and keywords"
            )

            # Return both chunks, full transcript, and duration
            return {
                "chunks": enriched_chunks,
                "full_transcript": full_transcript,
                "duration_seconds": audio_duration_seconds,
            }

        except VoiceProcessingError:
            raise
        except Exception as e:
            logger.error(f"Failed to process audio/video: {e}", exc_info=True)
            raise VoiceProcessingError(
                message=f"Failed to process audio/video: {str(e)}",
                error_code=ErrorCode.CODEC_ERROR,
            )
        finally:
            # Clean up temporary files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"Cleaned up temporary file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")
