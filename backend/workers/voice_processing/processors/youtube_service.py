"""
YouTube video extraction and transcript processing for voice processing worker.
"""

import asyncio
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from loguru import logger
from openai import AsyncOpenAI

from shared.config import settings

try:
    import assemblyai as aai
    import yt_dlp
    from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi
    from youtube_transcript_api.proxies import WebshareProxyConfig
except ImportError as e:
    logger.error(f"Missing required package for YouTube processing: {e}")
    logger.error("Install: pip install yt-dlp youtube-transcript-api assemblyai")
    raise


class YouTubeService:
    """
    Extract and chunk YouTube video transcripts for vector DB ingestion.
    Integrates with existing voice processing pipeline.
    """

    def __init__(self):
        """Initialize with API keys from shared.config.Settings."""
        # AssemblyAI API key from settings
        self.aai_api_key = settings.assemblyai_api_key
        if self.aai_api_key:
            aai.settings.api_key = self.aai_api_key
            logger.info("✓ AssemblyAI API key configured")
        else:
            logger.warning("⚠ ASSEMBLYAI_API_KEY not found - transcription will be disabled")

        # YouTube Data API key from settings
        self.youtube_api_key = settings.youtube_api_key
        if self.youtube_api_key:
            logger.info("✓ YouTube Data API key found - will use for metadata")
        else:
            logger.info("⚠ No YOUTUBE_API_KEY found - will use yt-dlp fallback for metadata")

        # OpenAI for summary and keyword generation from settings
        self.openai_api_key = settings.openai_api_key
        if self.openai_api_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
            logger.info("✓ OpenAI API key configured - will use for summary and keywords")
        else:
            self.openai_client = None
            logger.warning(
                "⚠ OPENAI_API_KEY not found - will use simple extraction for summary and keywords"
            )

        # YouTube proxy configuration - used for bypassing IP-based bot detection
        self.proxy = settings.youtube_proxy if settings.youtube_proxy else None
        if self.proxy:
            logger.info("✓ YouTube residential proxy configured")
        else:
            logger.warning("⚠ No YouTube proxy configured - may encounter bot detection on AWS IPs")
            logger.info("   Recommended: Set YOUTUBE_PROXY env var (e.g., ScraperAPI, BrightData)")

        # Webshare proxy credentials for youtube_transcript_api
        self.webshare_proxy_username = settings.webshare_proxy_username
        self.webshare_proxy_password = settings.webshare_proxy_password

        if self.webshare_proxy_username and self.webshare_proxy_password:
            logger.info("✓ Webshare proxy credentials configured for transcript API")
        else:
            logger.info("⚠ No Webshare proxy credentials - transcript API may encounter IP blocks")

    def extract_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL."""
        patterns = [
            r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)",
            r"youtube\.com\/watch\?.*v=([^&\n?#]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError(f"Could not extract video ID from URL: {url}")

    def get_video_metadata_from_api(self, video_id: str) -> Optional[Dict]:
        """
        Get video metadata using YouTube Data API v3.
        Returns None if API key not available or request fails.
        """
        if not self.youtube_api_key:
            return None

        try:
            url = "https://www.googleapis.com/youtube/v3/videos"
            params = {
                "part": "snippet,contentDetails,statistics",
                "id": video_id,
                "key": self.youtube_api_key,
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if not data.get("items"):
                logger.warning(f"✗ No video found with ID: {video_id}")
                return None

            item = data["items"][0]
            snippet = item.get("snippet", {})
            statistics = item.get("statistics", {})
            content_details = item.get("contentDetails", {})

            # Parse ISO 8601 duration (PT1H2M3S format)
            duration_str = content_details.get("duration", "PT0S")
            duration = self._parse_iso8601_duration(duration_str)

            # Parse published date
            published_at = snippet.get("publishedAt", "")

            # Only essential metadata for YouTube table
            metadata = {
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "published_at": published_at,
                "duration": duration,
                "view_count": int(statistics.get("viewCount", 0)),
                "thumbnail": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "tags": snippet.get("tags", []),
                "source": "youtube_api",
            }

            logger.info("✓ Metadata fetched from YouTube Data API")
            return metadata

        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Error fetching from YouTube API: {e}")
            return None
        except Exception as e:
            logger.error(f"✗ Unexpected error with YouTube API: {e}")
            return None

    def _parse_iso8601_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration to seconds."""
        pattern = r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?"
        match = re.match(pattern, duration_str)
        if not match:
            return 0

        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)

        return hours * 3600 + minutes * 60 + seconds

    def get_video_metadata_from_ytdlp(self, video_id: str) -> Dict:
        """
        Fallback: Get video metadata using yt-dlp.
        Uses proxy if configured to bypass IP-based bot detection.
        """
        url = f"https://www.youtube.com/watch?v={video_id}"

        # Try without proxy first (faster, free)
        try:
            logger.debug("Attempting metadata fetch without proxy...")
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "cachedir": os.environ.get("YT_DLP_CACHE_DIR", "/tmp/yt-dlp-cache"),
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                metadata = self._parse_yt_dlp_info(info, video_id)
                logger.info("✓ Metadata fetched from yt-dlp (direct)")
                return metadata

        except Exception as e:
            # Check if it's bot detection
            error_msg = str(e).lower()
            if "bot" in error_msg or "captcha" in error_msg or "sign in" in error_msg:
                logger.warning(f"⚠ Bot detection encountered: {e}")

                # Retry with proxy if available
                if self.proxy:
                    logger.info("🔄 Retrying with residential proxy...")
                    return self._get_metadata_with_proxy(video_id, url)
                else:
                    logger.error("✗ No proxy configured - cannot bypass bot detection")
                    return self._minimal_metadata(video_id)
            else:
                logger.error(f"✗ Error fetching metadata: {e}")
                return self._minimal_metadata(video_id)

    def _get_metadata_with_proxy(self, video_id: str, url: str) -> Dict:
        """Fetch metadata using residential proxy."""
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "cachedir": os.environ.get("YT_DLP_CACHE_DIR", "/tmp/yt-dlp-cache"),
                "proxy": self.proxy,
                # Disable SSL verification when using proxy (required for HTTP proxies with HTTPS)
                "nocheckcertificate": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                metadata = self._parse_yt_dlp_info(info, video_id)
                logger.info("✓ Metadata fetched from yt-dlp (via proxy)")
                return metadata

        except Exception as e:
            logger.error(f"✗ Error fetching metadata with proxy: {e}")
            return self._minimal_metadata(video_id)

    def _parse_yt_dlp_info(self, info: Dict, video_id: str) -> Dict:
        """Parse yt-dlp info dict into standardized metadata format."""
        return {
            "video_id": video_id,
            "title": info.get("title", ""),
            "description": info.get("description", ""),
            "channel": info.get("channel", ""),
            "channel_id": info.get("channel_id", ""),
            "published_at": info.get("upload_date", ""),  # yt-dlp format: YYYYMMDD
            "duration": info.get("duration", 0),
            "view_count": info.get("view_count", 0),
            "thumbnail": info.get("thumbnail", ""),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "tags": info.get("tags", []),
            "source": "yt_dlp",
        }

    def _minimal_metadata(self, video_id: str) -> Dict:
        """Return minimal metadata when all fetching methods fail."""
        return {
            "video_id": video_id,
            "title": "",
            "description": "",
            "channel": "",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "tags": [],
            "source": "minimal",
        }

    def get_video_metadata(self, video_id: str) -> Dict:
        """
        Get video metadata, preferring YouTube Data API, falling back to yt-dlp.
        """
        # Try YouTube Data API first
        metadata = self.get_video_metadata_from_api(video_id)

        # Fallback to yt-dlp
        if metadata is None:
            metadata = self.get_video_metadata_from_ytdlp(video_id)

        return metadata

    def get_youtube_transcript(
        self, video_id: str, retry_attempts: int = 2
    ) -> Optional[List[Dict]]:
        """
        Robust transcript fetcher for youtube-transcript-api >= 1.x (instance API).
        Uses Webshare proxy to bypass IP blocks on AWS/cloud IPs.
        Returns standardized list of {'text','start','duration'} or None.
        """
        preferred_langs = ["en", "en-US", "en-GB", "en-CA", "en-AU"]

        # Try without proxy first (faster for non-blocked IPs)
        ytt = self._create_transcript_api_instance(use_proxy=False)
        if ytt is None:
            logger.error("✗ Could not create YouTubeTranscriptApi instance")
            return None

        # Attempt to fetch with standard instance
        result = self._fetch_transcript_with_instance(
            ytt, video_id, preferred_langs, retry_attempts
        )

        # If we got blocked (RequestBlocked/IpBlocked), retry with Webshare proxy
        if result is None and self.webshare_proxy_username and self.webshare_proxy_password:
            logger.warning("⚠ Transcript fetch failed, retrying with Webshare proxy...")
            ytt_proxy = self._create_transcript_api_instance(use_proxy=True)
            if ytt_proxy:
                result = self._fetch_transcript_with_instance(
                    ytt_proxy, video_id, preferred_langs, retry_attempts
                )

        return result

    def _create_transcript_api_instance(
        self, use_proxy: bool = False
    ) -> Optional[YouTubeTranscriptApi]:
        """Create YouTubeTranscriptApi instance with or without Webshare proxy."""
        try:
            if use_proxy and self.webshare_proxy_username and self.webshare_proxy_password:
                logger.info("✓ Creating YouTubeTranscriptApi with Webshare proxy")
                proxy_config = WebshareProxyConfig(
                    proxy_username=self.webshare_proxy_username,
                    proxy_password=self.webshare_proxy_password,
                )
                return YouTubeTranscriptApi(proxy_config=proxy_config)
            else:
                return YouTubeTranscriptApi()
        except Exception as e:
            logger.error(f"✗ Could not create YouTubeTranscriptApi instance: {e}")
            return None

    def _fetch_transcript_with_instance(
        self,
        ytt: YouTubeTranscriptApi,
        video_id: str,
        preferred_langs: List[str],
        retry_attempts: int,
    ) -> Optional[List[Dict]]:
        """Fetch transcript using provided YouTubeTranscriptApi instance."""
        # Fast path: fetch preferred languages directly
        try:
            for attempt in range(1, retry_attempts + 1):
                try:
                    fetched = ytt.fetch(video_id, languages=preferred_langs)
                    # Use .to_raw_data() if available; otherwise iterate
                    if hasattr(fetched, "to_raw_data"):
                        raw = fetched.to_raw_data()
                    else:
                        # fallback: build raw list from iteration
                        raw = []
                        for snippet in fetched:
                            raw.append(
                                {
                                    "text": getattr(snippet, "text", str(snippet)),
                                    "start": getattr(snippet, "start", 0.0),
                                    "duration": getattr(snippet, "duration", 0.0),
                                }
                            )
                    logger.info(f"✓ Found English transcript (fetch) ({len(raw)} segments)")
                    return self._standardize_transcript_format(raw)
                except (NoTranscriptFound, TranscriptsDisabled):
                    # no transcript by fetch -> break to try list() path
                    raise
                except Exception as e:
                    error_msg = str(e).lower()
                    # Check if it's an IP block - don't retry, return None to trigger proxy fallback
                    if (
                        "requestblocked" in error_msg
                        or "ipblocked" in error_msg
                        or "blocked" in error_msg
                    ):
                        logger.warning(f"⚠ IP blocked by YouTube: {e}")
                        return None
                    # transient error -> retry a couple times then fallback
                    if attempt < retry_attempts:
                        wait = 1.0 * (2 ** (attempt - 1))
                        logger.warning(
                            f"⚠ fetch() attempt {attempt} failed: {e}. retrying in {wait}s..."
                        )
                        time.sleep(wait)
                        continue
                    else:
                        logger.warning(
                            f"⚠ fetch() failed after {retry_attempts} attempts: {e}. Falling back to list()"
                        )
                        break
        except TranscriptsDisabled:
            logger.error(f"✗ Transcripts are disabled for video {video_id}")
            return None
        except NoTranscriptFound:
            # fetch did not find transcripts; continue to list() fallback
            pass
        except Exception as e:
            error_msg = str(e).lower()
            if "requestblocked" in error_msg or "ipblocked" in error_msg or "blocked" in error_msg:
                logger.warning(f"⚠ IP blocked by YouTube: {e}")
                return None
            logger.warning(f"⚠ Unexpected error during fetch(): {e}")

        # Fallback: list all transcripts and try prioritized strategies
        try:
            transcript_list = ytt.list(video_id)
        except TranscriptsDisabled:
            logger.error(f"✗ Transcripts are disabled for video {video_id}")
            return None
        except NoTranscriptFound:
            logger.error(f"✗ No transcript found for video {video_id}")
            return None
        except Exception as e:
            error_msg = str(e).lower()
            if "requestblocked" in error_msg or "ipblocked" in error_msg or "blocked" in error_msg:
                logger.warning(f"⚠ IP blocked by YouTube during list(): {e}")
                return None
            logger.error(f"✗ Error listing transcripts for {video_id}: {e}")
            return None

        # 1) Manual English captions
        try:
            logger.info("Searching for manually created English captions...")
            transcript = transcript_list.find_manually_created_transcript(preferred_langs)
            fetched = transcript.fetch()
            raw = fetched.to_raw_data() if hasattr(fetched, "to_raw_data") else list(fetched)
            logger.info(f"✓ Found manual English captions ({len(raw)} segments)")
            return self._standardize_transcript_format(raw)
        except NoTranscriptFound:
            logger.info("No manually created English captions found.")
        except Exception as e:
            logger.warning(f"⚠ Error fetching manual captions: {e}")

        # 2) Auto-generated English captions
        try:
            logger.info("Searching for auto-generated English captions...")
            transcript = transcript_list.find_generated_transcript(preferred_langs)
            fetched = transcript.fetch()
            raw = fetched.to_raw_data() if hasattr(fetched, "to_raw_data") else list(fetched)
            logger.info(f"✓ Found auto-generated English captions ({len(raw)} segments)")
            return self._standardize_transcript_format(raw)
        except NoTranscriptFound:
            logger.info("No auto-generated English captions found.")
        except Exception as e:
            logger.warning(f"⚠ Error fetching generated captions: {e}")

        # 3) Try translating any translatable transcripts to English
        try:
            logger.info("No English captions found. Checking for translatable captions...")
            for transcript in transcript_list:
                try:
                    if getattr(transcript, "is_translatable", False):
                        lang = getattr(transcript, "language", "unknown")
                        logger.info(f"Found {lang} captions - attempting translation to English...")
                        translated = transcript.translate("en")
                        fetched = translated.fetch()
                        raw = (
                            fetched.to_raw_data()
                            if hasattr(fetched, "to_raw_data")
                            else list(fetched)
                        )
                        logger.info(
                            f"✓ Translated {lang} captions to English ({len(raw)} segments)"
                        )
                        return self._standardize_transcript_format(raw)
                except Exception as e:
                    logger.warning(
                        f"⚠ Could not translate/fetch from transcript {getattr(transcript,'language','unknown')}: {e}"
                    )
            logger.info("No translatable captions succeeded.")
        except Exception as e:
            logger.warning(f"⚠ Error while checking translatable captions: {e}")

        # Nothing worked
        logger.error(f"✗ No English transcript available for video {video_id}")
        return None

    def _standardize_transcript_format(self, segments: List[Dict]) -> List[Dict]:
        """
        Standardize transcript format to have consistent keys.
        YouTube Transcript API returns: text, start, duration
        """
        standardized = []
        for segment in segments:
            standardized.append(
                {
                    "text": segment.get("text", "").strip(),
                    "start": segment.get("start", 0),
                    "duration": segment.get("duration", 0),
                }
            )
        return standardized

    async def download_audio(self, video_id: str, output_path: str = "temp_audio.mp3") -> str:
        """
        Download audio from YouTube video using yt-dlp (async wrapper).
        Uses proxy if configured to bypass IP-based bot detection.
        Implements fallback: try without proxy first, then with proxy if bot detection occurs.
        """

        async def _download_with_options(use_proxy: bool = False):
            ydl_opts = {
                "format": "bestaudio/best",
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "outtmpl": output_path.replace(".mp3", ""),
                "quiet": False,
                "cachedir": os.environ.get("YT_DLP_CACHE_DIR", "/tmp/yt-dlp-cache"),
            }

            # Add proxy if requested
            if use_proxy and self.proxy:
                ydl_opts["proxy"] = self.proxy
                # Disable SSL verification when using proxy (required for HTTP proxies with HTTPS)
                ydl_opts["nocheckcertificate"] = True
                logger.info("✓ Using residential proxy for audio download")

            def _sync_download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
                return output_path

            return await asyncio.to_thread(_sync_download)

        # Try without proxy first (faster, free)
        try:
            logger.info(f"Downloading audio for video {video_id}...")
            result = await _download_with_options(use_proxy=False)
            logger.info("✓ Audio downloaded successfully (direct)")
            return result

        except Exception as e:
            # Check if it's bot detection
            error_msg = str(e).lower()
            if "bot" in error_msg or "captcha" in error_msg or "sign in" in error_msg:
                logger.warning(f"⚠ Bot detection encountered during download: {e}")

                # Retry with proxy if available
                if self.proxy:
                    logger.info("🔄 Retrying audio download with residential proxy...")
                    try:
                        result = await _download_with_options(use_proxy=True)
                        logger.info("✓ Audio downloaded successfully (via proxy)")
                        return result
                    except Exception as proxy_error:
                        logger.error(f"✗ Error downloading with proxy: {proxy_error}")
                        raise
                else:
                    logger.error("✗ No proxy configured - cannot bypass bot detection")
                    raise
            else:
                logger.error(f"✗ Error downloading audio: {e}")
                raise

    async def transcribe_with_assemblyai(self, audio_path: str) -> List[Dict]:
        """
        Transcribe audio using AssemblyAI with timestamps and speaker diarization (async wrapper).
        Forces English language detection.
        """
        if not self.aai_api_key:
            raise RuntimeError("AssemblyAI API key not configured")

        def _transcribe():
            logger.info("Transcribing with AssemblyAI (English)...")

            config = aai.TranscriptionConfig(
                speaker_labels=True,  # Enable diarization
                punctuate=True,
                format_text=True,
                language_code="en",  # Force English
            )

            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(audio_path, config=config)

            if transcript.status == aai.TranscriptStatus.error:
                raise Exception(f"Transcription failed: {transcript.error}")

            # Convert to standardized format
            segments = []
            for utterance in transcript.utterances:
                segments.append(
                    {
                        "text": utterance.text,
                        "start": utterance.start / 1000.0,  # Convert ms to seconds
                        "duration": (utterance.end - utterance.start) / 1000.0,
                        "speaker": utterance.speaker if hasattr(utterance, "speaker") else None,
                        "confidence": (
                            utterance.confidence if hasattr(utterance, "confidence") else None
                        ),
                    }
                )

            logger.info(f"✓ Transcription complete: {len(segments)} segments")
            return segments

        # Run in thread pool to avoid blocking the event loop
        return await asyncio.to_thread(_transcribe)

    def count_tokens(self, text: str) -> int:
        """
        Rough token count estimation (1 token ≈ 4 characters for English).
        For production, use tiktoken or similar.
        """
        return len(text) // 4

    def chunk_transcript(
        self,
        segments: List[Dict],
        min_chunk_size: int = 400,
        max_chunk_size: int = 800,
        target_duration: float = 45.0,
    ) -> List[Dict]:
        """
        Chunk transcript into semantic segments based on timestamps and token counts.
        Simplified version without speaker tracking.

        Args:
            segments: List of transcript segments with text, start, duration
            min_chunk_size: Minimum tokens per chunk (default: 400)
            max_chunk_size: Maximum tokens per chunk (default: 800)
            target_duration: Target duration in seconds (default: 45, range: 15-60)
        """
        chunks = []
        current_chunk = {"text": "", "start_time": 0, "end_time": 0, "segments": []}

        for i, segment in enumerate(segments):
            segment_text = segment["text"].strip()
            if not segment_text:
                continue

            # Initialize first chunk
            if not current_chunk["text"]:
                current_chunk["start_time"] = segment["start"]
                current_chunk["text"] = segment_text
                current_chunk["end_time"] = segment["start"] + segment.get("duration", 0)
                current_chunk["segments"].append(segment)
                continue

            # Calculate potential new chunk stats
            potential_text = current_chunk["text"] + " " + segment_text
            potential_tokens = self.count_tokens(potential_text)
            potential_duration = (
                segment["start"] + segment.get("duration", 0) - current_chunk["start_time"]
            )

            # Decide whether to continue current chunk or start new one
            should_split = False

            # Split if we exceed max tokens
            if potential_tokens > max_chunk_size:
                should_split = True

            # Split if we exceed target duration and have minimum tokens
            elif (
                potential_duration > target_duration
                and self.count_tokens(current_chunk["text"]) >= min_chunk_size
            ):
                should_split = True

            # Split at sentence boundaries when reasonable
            elif potential_tokens >= min_chunk_size and segment_text.endswith(
                (".", "!", "?", ".\n", "!\n", "?\n")
            ):
                if potential_duration > target_duration * 0.7:
                    should_split = True

            if should_split:
                # Finalize current chunk
                chunks.append(current_chunk.copy())

                # Start new chunk
                current_chunk = {
                    "text": segment_text,
                    "start_time": segment["start"],
                    "end_time": segment["start"] + segment.get("duration", 0),
                    "segments": [segment],
                }
            else:
                # Continue current chunk
                current_chunk["text"] = potential_text
                current_chunk["end_time"] = segment["start"] + segment.get("duration", 0)
                current_chunk["segments"].append(segment)

        # Add final chunk
        if current_chunk["text"]:
            chunks.append(current_chunk)

        logger.info(f"✓ Created {len(chunks)} chunks from {len(segments)} segments")
        return chunks

    def format_timestamp(self, seconds: float) -> str:
        """Format seconds to HH:MM:SS or MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    async def generate_chunk_summary_and_keywords_with_openai(
        self, chunk_text: str, metadata: Dict
    ) -> tuple[str, List[str]]:
        """
        Generate a brief summary and extract key topics/keywords using OpenAI.
        This creates additional context for better vectorization.

        Args:
            chunk_text: The transcript text of the chunk
            metadata: Video metadata for context

        Returns:
            Tuple of (summary, keywords_list)
        """
        if not self.openai_client:
            # Fallback to simple extraction if OpenAI not available
            return self._generate_simple_summary_and_keywords(chunk_text)

        try:
            # Use OpenAI to generate concise summary and keywords
            prompt = f"""Analyze this YouTube video transcript segment and provide:
1. A concise 1-2 sentence summary
2. 3-5 key topics/keywords (single words or short phrases, NO explanations)

Video title: {metadata.get('title', 'Unknown')}
Channel: {metadata.get('channel', 'Unknown')}

Transcript segment:
{chunk_text}

Format your response as:
Summary: [your summary]
Keywords: [keyword1, keyword2, keyword3, ...]

Keep keywords short and focused. Fewer keywords are better for vector search."""

            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cost-effective
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that extracts concise summaries and key topics from video transcripts. Keep keywords minimal (3-5 max) and highly relevant.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Lower temperature for more consistent extraction
                max_tokens=200,  # Keep response concise
            )

            content = response.choices[0].message.content.strip()

            # Parse the response
            summary = ""
            keywords = []

            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("Summary:"):
                    summary = line.replace("Summary:", "").strip()
                elif line.startswith("Keywords:"):
                    keywords_text = line.replace("Keywords:", "").strip()
                    # Parse comma-separated keywords
                    keywords = [kw.strip() for kw in keywords_text.split(",") if kw.strip()]
                    # Limit to 5 keywords max to avoid overwhelming the vector search
                    keywords = keywords[:5]

            # Fallback if parsing failed
            if not summary:
                summary = chunk_text[:150] + "..." if len(chunk_text) > 150 else chunk_text
            if not keywords:
                keywords = self._extract_simple_keywords(chunk_text)[:5]

            logger.debug(
                f"OpenAI generated summary ({len(summary)} chars) and {len(keywords)} keywords"
            )
            return summary, keywords

        except Exception as e:
            logger.warning(
                f"OpenAI summary generation failed: {e}. Falling back to simple extraction."
            )
            return self._generate_simple_summary_and_keywords(chunk_text)

    def _generate_simple_summary_and_keywords(self, chunk_text: str) -> tuple[str, List[str]]:
        """
        Fallback method for simple summary and keyword extraction without AI.

        Args:
            chunk_text: The transcript text

        Returns:
            Tuple of (summary, keywords_list)
        """
        # Simple summary generation (first 2 sentences or up to 150 chars)
        sentences = re.split(r"[.!?]+", chunk_text)
        meaningful_sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        if len(meaningful_sentences) >= 2:
            summary = ". ".join(meaningful_sentences[:2]) + "."
        elif meaningful_sentences:
            summary = meaningful_sentences[0] + "."
        else:
            summary = chunk_text[:150] + "..." if len(chunk_text) > 150 else chunk_text

        keywords = self._extract_simple_keywords(chunk_text)[:5]  # Limit to 5 keywords

        return summary, keywords

    def _extract_simple_keywords(self, chunk_text: str) -> List[str]:
        """
        Extract keywords using simple word frequency (no AI).

        Args:
            chunk_text: The transcript text

        Returns:
            List of keywords
        """
        # Remove common stop words and extract meaningful terms
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "this",
            "that",
            "these",
            "those",
            "i",
            "you",
            "he",
            "she",
            "it",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
        }

        # Extract words and filter
        words = re.findall(r"\b[a-zA-Z]{3,}\b", chunk_text.lower())
        keywords = []

        for word in words:
            if word not in stop_words and len(word) > 2:
                if word not in keywords:  # Avoid duplicates
                    keywords.append(word)
                if len(keywords) >= 5:  # Limit to 5 keywords
                    break

        return keywords

    async def enrich_chunks(self, chunks: List[Dict], metadata: Dict) -> List[Dict]:
        """
        Simplified chunk enrichment focusing only on essential data and optimized vectorized text.
        Uses OpenAI to generate summaries and keywords for better RAG retrieval.
        Format: transcript | Summary: {summary} | Keywords: {keywords}
        The first chunk includes the video title for context.
        """
        enriched_chunks = []

        logger.info(
            f"Enriching {len(chunks)} chunks with OpenAI-generated summaries and keywords..."
        )

        for i, chunk in enumerate(chunks):
            # Generate summary and keywords using OpenAI (with fallback)
            summary, keywords = await self.generate_chunk_summary_and_keywords_with_openai(
                chunk["text"], metadata
            )

            # Create optimized vectorized text with pipe separator
            # For the first chunk, include the video title for better context
            keywords_str = ", ".join(keywords)

            if i == 0:
                # First chunk: include video title for context
                video_title = metadata.get("title", "")
                vectorized_text = f"{video_title}\n\n{chunk['text']} | Summary: {summary} | Keywords: {keywords_str}"
                logger.debug(f"First chunk enriched with video title: {video_title[:50]}...")
            else:
                # Other chunks: standard format
                vectorized_text = f"{chunk['text']} | Summary: {summary} | Keywords: {keywords_str}"

            enriched = {
                # Essential chunk data
                "chunk_index": i,
                "text": chunk["text"],  # Original transcript
                "vectorized_text": vectorized_text,  # Enhanced text for embedding
                "token_count": self.count_tokens(vectorized_text),
                # Timestamps (stored in chunk metadata, not YouTube table)
                "start_time": round(chunk["start_time"], 2),
                "end_time": round(chunk["end_time"], 2),
                "duration": round(chunk["end_time"] - chunk["start_time"], 2),
                "timestamp_url": f"{metadata.get('url', '')}&t={int(chunk['start_time'])}s",
                # Summary and keywords for context
                "summary": summary,
                "keywords": keywords,
                # Source metadata for ingestion pipeline
                "source": "youtube",
                "source_type": "transcripts",
            }

            enriched_chunks.append(enriched)

            if (i + 1) % 10 == 0:
                logger.info(f"  Enriched {i + 1}/{len(chunks)} chunks...")

        logger.info("✓ Chunk enrichment complete!")
        return enriched_chunks

    async def process_video(
        self,
        youtube_url: str,
        keep_audio: bool = False,
        min_chunk_tokens: int = 400,
        max_chunk_tokens: int = 800,
        target_chunk_duration: float = 45.0,
    ) -> tuple[List[Dict], Dict]:
        """
        Main processing pipeline for YouTube video.

        Args:
            youtube_url: YouTube video URL
            keep_audio: Whether to keep downloaded audio file
            min_chunk_tokens: Minimum tokens per chunk (default: 400)
            max_chunk_tokens: Maximum tokens per chunk (default: 800)
            target_chunk_duration: Target seconds per chunk (default: 45, range: 15-60)

        Returns:
            Tuple of (enriched_chunks, metadata)
        """
        logger.info(f"Starting YouTube video extraction for: {youtube_url}")

        # Extract video ID
        video_id = self.extract_video_id(youtube_url)
        logger.info(f"Video ID: {video_id}")

        # Step 1: Get metadata
        logger.info("[1/5] Fetching video metadata...")
        metadata = self.get_video_metadata(video_id)
        logger.info(f"      Title: {metadata.get('title', 'Unknown')[:60]}...")
        logger.info(f"      Channel: {metadata.get('channel', 'Unknown')}")
        logger.info(
            f"      Duration: {metadata.get('duration', 0)}s ({self.format_timestamp(metadata.get('duration', 0))})"
        )
        logger.info(f"      Views: {metadata.get('view_count', 0):,}")

        # Step 2: Try to get existing English transcript
        logger.info("[2/5] Checking for English transcripts...")
        segments = self.get_youtube_transcript(video_id)

        # Step 3-4: If no transcript, download and transcribe
        if not segments:
            logger.info("[3/5] No English transcript found. Downloading audio...")

            # Create temp directory for audio download
            temp_dir = Path("/tmp/youtube_audio")
            temp_dir.mkdir(exist_ok=True)
            audio_path = str(temp_dir / f"{video_id}.mp3")

            await self.download_audio(video_id, audio_path)

            logger.info("[4/5] Transcribing with AssemblyAI (English)...")
            segments = await self.transcribe_with_assemblyai(audio_path)

            # Clean up audio file
            if not keep_audio and os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info("      ✓ Removed temporary audio file")
        else:
            logger.info("[3/5] ✓ Using existing English transcript (skipping download)")
            logger.info("[4/5] ✓ Skipping transcription (transcript already available)")

        # Step 5: Chunk and enrich
        logger.info("[5/5] Chunking and enriching transcript...")
        logger.info(
            f"      Target: {min_chunk_tokens}-{max_chunk_tokens} tokens, ~{target_chunk_duration}s duration"
        )
        chunks = self.chunk_transcript(
            segments,
            min_chunk_size=min_chunk_tokens,
            max_chunk_size=max_chunk_tokens,
            target_duration=target_chunk_duration,
        )

        enriched_chunks = await self.enrich_chunks(chunks, metadata)

        # Print summary
        total_tokens = sum(c["token_count"] for c in enriched_chunks)
        avg_tokens = total_tokens / len(enriched_chunks) if enriched_chunks else 0
        avg_duration = (
            sum(c["duration"] for c in enriched_chunks) / len(enriched_chunks)
            if enriched_chunks
            else 0
        )

        logger.info("✓ YouTube extraction complete!")
        logger.info(f"Total chunks: {len(enriched_chunks)}")
        logger.info(f"Total tokens: {total_tokens:,}")
        logger.info(f"Average tokens/chunk: {avg_tokens:.0f}")
        logger.info(f"Average duration/chunk: {avg_duration:.1f}s")

        return enriched_chunks, metadata
