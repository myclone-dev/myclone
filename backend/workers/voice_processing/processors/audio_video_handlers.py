"""Audio and video transcription handlers for worker."""

import os
import tempfile
from pathlib import Path

from loguru import logger
from utils.progress import ProgressTracker

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.services.s3_service import get_s3_service
from shared.voice_processing.errors import ErrorCode, VoiceProcessingError
from shared.voice_processing.models import JobRequest, JobResult

from .audio_video_transcription import AudioVideoTranscriptionProcessor
from .rag_ingestion import ingest_chunked_content_to_rag, update_document_content


async def process_audio_transcription(
    request: JobRequest, progress_tracker: ProgressTracker
) -> JobResult:
    """Process audio transcription job using AssemblyAI with timestamp-based chunking.

    Args:
        request: Job request
        progress_tracker: Progress tracking callback

    Returns:
        Job result with timestamped transcript chunks
    """
    import time

    from shared.voice_processing.models import ProcessingStage

    start_time = time.time()

    # Get AssemblyAI API key from settings
    assemblyai_api_key = settings.assemblyai_api_key
    openai_api_key = settings.openai_api_key

    if not assemblyai_api_key:
        logger.error("AssemblyAI API key not configured")
        raise VoiceProcessingError(
            message="ASSEMBLYAI_API_KEY not configured in settings",
            error_code=ErrorCode.CONFIGURATION_ERROR,
        )

    if not openai_api_key:
        logger.warning("⚠️ OpenAI API key not configured - chunk enrichment will be skipped")

    transcript_chunks = []
    input_info = {}
    temp_audio_file = None
    s3_uri = None  # Track S3 URI for metadata

    try:
        logger.info(f"🎙️ Starting audio transcription job for source: {request.input_source}")
        progress_tracker.start_stage(ProcessingStage.VALIDATION, "Validating audio source")

        # Create output directory for transcription processing
        from utils.config import config

        output_dir = config.get_output_dir("transcription")
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created output directory: {output_dir}")

        # Initialize transcription processor with OpenAI support
        processor = AudioVideoTranscriptionProcessor(
            assemblyai_api_key=assemblyai_api_key,
            openai_api_key=openai_api_key,
            progress_tracker=progress_tracker,
        )
        logger.debug("Initialized AudioVideoTranscriptionProcessor")

        # Handle audio source (S3 or URL)
        audio_source = None
        if request.input_source.startswith("s3://"):
            # Download audio from S3
            s3_uri = request.input_source  # Store S3 URI for metadata
            logger.info(f"Downloading audio from S3: {request.input_source}")
            progress_tracker.update_progress(5, "Downloading audio from S3")

            from urllib.parse import urlparse

            # Parse S3 path to get file extension
            parsed_url = urlparse(request.input_source)
            file_extension = Path(parsed_url.path).suffix or ".mp3"
            temp_audio_file = tempfile.NamedTemporaryFile(suffix=file_extension, delete=False)
            temp_audio_file.close()

            # Download from S3
            s3_service = get_s3_service()
            await s3_service.download_file(
                s3_path=request.input_source, local_path=temp_audio_file.name
            )

            input_info = {
                "source": "s3",
                "s3_path": request.input_source,
                "file_size": os.path.getsize(temp_audio_file.name),
                "content_type": "audio",
            }
            audio_source = temp_audio_file.name
            logger.info(
                f"✅ Downloaded audio from S3: {request.input_source} -> {audio_source} ({input_info['file_size']} bytes)"
            )

        elif request.input_source.startswith(("http://", "https://")):
            # Download audio from URL
            logger.info(f"Downloading audio from URL: {request.input_source}")
            progress_tracker.update_progress(5, "Downloading audio from URL")

            from urllib.parse import urlparse

            parsed_url = urlparse(request.input_source)
            file_extension = Path(parsed_url.path).suffix or ".mp3"
            temp_audio_file = tempfile.NamedTemporaryFile(suffix=file_extension, delete=False)
            temp_audio_file.close()

            await processor._download_file(request.input_source, temp_audio_file.name)

            input_info = {
                "source": "url",
                "url": request.input_source,
                "file_size": os.path.getsize(temp_audio_file.name),
                "content_type": "audio",
            }
            audio_source = temp_audio_file.name
            logger.info(
                f"✅ Downloaded audio from URL: {audio_source} ({input_info['file_size']} bytes)"
            )
        else:
            logger.error(f"Invalid audio source format: {request.input_source}")
            raise VoiceProcessingError(
                message=f"Invalid audio source: {request.input_source}",
                error_code=ErrorCode.INVALID_FORMAT,
            )

        progress_tracker.update_progress(10, "Audio validation completed")

        # Process audio transcription with chunking
        logger.info(f"🔄 Processing audio file: {audio_source}")

        # Get full transcript with timestamps and chunks - pass S3 URI for metadata
        result = await processor.process_audio_video(
            input_source=audio_source,
            output_dir=str(output_dir),
            min_chunk_tokens=400,
            max_chunk_tokens=800,
            target_chunk_duration=45.0,
            s3_uri=s3_uri,  # Pass S3 URI for metadata consistency
        )

        # process_audio_video now returns a dict with 'chunks' and 'full_transcript'
        transcript_chunks = result.get("chunks", [])
        full_transcript = result.get("full_transcript", "")
        duration_seconds = result.get("duration_seconds", 0)

        logger.info(
            f"✅ Generated {len(transcript_chunks)} transcript chunks, total transcript length: {len(full_transcript)} chars, duration: {duration_seconds}s"
        )

        # Log the exact value we're about to pass
        logger.info(
            f"📊 Audio transcription result: duration_seconds={duration_seconds} (type: {type(duration_seconds)})"
        )

        progress_tracker.update_progress(
            85, f"Generated {len(transcript_chunks)} transcript chunks"
        )

        # Update Document table with content_text (unchunked transcript) and duration
        if request.metadata and request.metadata.get("document_id"):
            document_id = request.metadata["document_id"]
            logger.info(
                f"📝 Updating document {document_id} with transcript content (length={len(full_transcript)}) and duration ({duration_seconds}s)"
            )
            await update_document_content(document_id, full_transcript, duration_seconds)
            logger.info(
                f"✅ Updated document {document_id} with {len(full_transcript)} characters of transcript and {duration_seconds}s duration"
            )

        # Ingest chunks into RAG if persona_id and user_id are provided
        if request.persona_id and request.user_id and transcript_chunks:
            # Validate document_id exists before RAG ingestion
            if not request.metadata or not request.metadata.get("document_id"):
                logger.error("document_id missing from metadata - cannot link embeddings to source")
                raise VoiceProcessingError(
                    message="document_id required in metadata for audio ingestion",
                    error_code=ErrorCode.INVALID_FORMAT,
                )

            document_id = request.metadata["document_id"]
            logger.info(
                f"📚 Ingesting {len(transcript_chunks)} chunks into RAG (user={request.user_id}, persona={request.persona_id}, source={document_id})"
            )

            from uuid import UUID

            await ingest_chunked_content_to_rag(
                chunks=transcript_chunks,
                user_id=request.user_id,
                persona_id=request.persona_id,
                source_type="audio",
                source_record_id=UUID(document_id),
                document_id=document_id,
            )
            progress_tracker.update_progress(95, "Ingested chunks into RAG")
            logger.info("✅ RAG ingestion completed")

        processing_time = time.time() - start_time

        # Calculate statistics
        total_tokens = sum(chunk.get("token_count", 0) for chunk in transcript_chunks)
        total_duration = sum(chunk.get("duration", 0) for chunk in transcript_chunks)
        avg_chunk_tokens = total_tokens / len(transcript_chunks) if transcript_chunks else 0
        avg_chunk_duration = total_duration / len(transcript_chunks) if transcript_chunks else 0

        logger.info(
            f"✅ Audio transcription completed successfully in {processing_time:.2f}s: "
            f"{len(transcript_chunks)} chunks, {total_tokens} tokens, {total_duration:.1f}s duration"
        )
        progress_tracker.complete_stage("Audio transcription completed successfully")

        # ===== REFRESH USAGE CACHE AFTER SUCCESSFUL AUDIO INGESTION =====
        # Recalculate usage from Documents table to ensure accurate limits
        if request.user_id:
            try:
                logger.info(
                    f"🔄 Refreshing usage cache for user {request.user_id} after audio ingestion"
                )
                from uuid import UUID

                from shared.database.voice_job_model import async_session_maker
                from shared.services.usage_cache_service import UsageCacheService

                async with async_session_maker() as session:
                    usage_cache_service = UsageCacheService(session)
                    await usage_cache_service.recalculate_usage_from_source(
                        user_id=(
                            UUID(request.user_id)
                            if isinstance(request.user_id, str)
                            else request.user_id
                        )
                    )
                    await session.commit()
                    logger.info(f"✅ Usage cache refreshed for user {request.user_id} (audio)")
            except Exception as cache_error:
                # Non-critical error - log warning but don't fail the job
                logger.warning(f"⚠️ Failed to refresh usage cache: {cache_error}")
        # ===== END USAGE CACHE REFRESH =====

        return JobResult(
            success=True,
            processing_time_seconds=processing_time,
            input_info=input_info,
            transcript_chunks=transcript_chunks,
            transcript_stats={
                "total_chunks": len(transcript_chunks),
                "total_tokens": total_tokens,
                "total_duration": total_duration,
                "average_chunk_tokens": avg_chunk_tokens,
                "average_chunk_duration": avg_chunk_duration,
                "persona_id": str(request.persona_id) if request.persona_id else None,
                "user_id": str(request.user_id) if request.user_id else None,
            },
        )

    except VoiceProcessingError:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(
            f"❌ Audio transcription failed after {processing_time:.2f}s: {e}", exc_info=True
        )

        # Capture exception in Sentry with full context
        capture_exception_with_context(
            e,
            extra={
                "input_source": request.input_source,
                "document_id": request.metadata.get("document_id") if request.metadata else None,
                "persona_id": str(request.persona_id) if request.persona_id else None,
                "user_id": str(request.user_id) if request.user_id else None,
                "input_info": input_info,
                "temp_audio_file": temp_audio_file.name if temp_audio_file else None,
            },
            tags={
                "component": "voice_worker",
                "operation": "audio_transcription",
                "parser_type": "assemblyai",
                "severity": "high",
            },
        )

        return JobResult(
            success=False,
            processing_time_seconds=processing_time,
            input_info=input_info,
            error_code="audio_transcription_error",
            error_message=str(e),
            error_suggestions=[
                "Check if audio file is valid and not corrupted",
                "Ensure ASSEMBLYAI_API_KEY is configured",
                "Try again with a different audio file",
            ],
        )
    finally:
        # Clean up temporary audio file
        if temp_audio_file and os.path.exists(temp_audio_file.name):
            try:
                os.unlink(temp_audio_file.name)
                logger.debug(f"🧹 Cleaned up temporary audio file: {temp_audio_file.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_audio_file.name}: {e}")


async def process_video_transcription(
    request: JobRequest, progress_tracker: ProgressTracker
) -> JobResult:
    """Process video transcription job using AssemblyAI (extracts audio first with FFmpeg).

    Args:
        request: Job request
        progress_tracker: Progress tracking callback

    Returns:
        Job result with timestamped transcript chunks
    """
    import time

    from shared.voice_processing.models import ProcessingStage

    start_time = time.time()

    # Get AssemblyAI API key from settings
    assemblyai_api_key = settings.assemblyai_api_key
    openai_api_key = settings.openai_api_key

    if not assemblyai_api_key:
        logger.error("AssemblyAI API key not configured")
        raise VoiceProcessingError(
            message="ASSEMBLYAI_API_KEY not configured in settings",
            error_code=ErrorCode.CONFIGURATION_ERROR,
        )

    if not openai_api_key:
        logger.warning("⚠️ OpenAI API key not configured - chunk enrichment will be skipped")

    transcript_chunks = []
    input_info = {}
    temp_video_file = None
    temp_audio_file = None
    s3_uri = None  # Track S3 URI for metadata

    try:
        logger.info(f"🎬 Starting video transcription job for source: {request.input_source}")
        progress_tracker.start_stage(ProcessingStage.VALIDATION, "Validating video source")

        # Create output directory for transcription processing
        from utils.config import config

        output_dir = config.get_output_dir("transcription")
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created output directory: {output_dir}")

        # Initialize transcription processor with OpenAI support
        processor = AudioVideoTranscriptionProcessor(
            assemblyai_api_key=assemblyai_api_key,
            openai_api_key=openai_api_key,
            progress_tracker=progress_tracker,
        )
        logger.debug("Initialized AudioVideoTranscriptionProcessor")

        # Handle video source (S3 or URL)
        video_source = None
        if request.input_source.startswith("s3://"):
            # Download video from S3
            s3_uri = request.input_source  # Store S3 URI for metadata
            logger.info(f"Downloading video from S3: {request.input_source}")
            progress_tracker.update_progress(5, "Downloading video from S3")

            from urllib.parse import urlparse

            # Parse S3 path to get file extension
            parsed_url = urlparse(request.input_source)
            file_extension = Path(parsed_url.path).suffix or ".mp4"
            temp_video_file = tempfile.NamedTemporaryFile(suffix=file_extension, delete=False)
            temp_video_file.close()

            # Download from S3
            s3_service = get_s3_service()
            await s3_service.download_file(
                s3_path=request.input_source, local_path=temp_video_file.name
            )

            input_info = {
                "source": "s3",
                "s3_path": request.input_source,
                "file_size": os.path.getsize(temp_video_file.name),
                "content_type": "video",
            }
            video_source = temp_video_file.name
            logger.info(
                f"✅ Downloaded video from S3: {request.input_source} -> {video_source} ({input_info['file_size']} bytes)"
            )

        elif request.input_source.startswith(("http://", "https://")):
            # Download video from URL
            logger.info(f"Downloading video from URL: {request.input_source}")
            progress_tracker.update_progress(5, "Downloading video from URL")

            from urllib.parse import urlparse

            parsed_url = urlparse(request.input_source)
            file_extension = Path(parsed_url.path).suffix or ".mp4"
            temp_video_file = tempfile.NamedTemporaryFile(suffix=file_extension, delete=False)
            temp_video_file.close()

            await processor._download_file(request.input_source, temp_video_file.name)

            input_info = {
                "source": "url",
                "url": request.input_source,
                "file_size": os.path.getsize(temp_video_file.name),
                "content_type": "video",
            }
            video_source = temp_video_file.name
            logger.info(
                f"✅ Downloaded video from URL: {video_source} ({input_info['file_size']} bytes)"
            )
        else:
            logger.error(f"Invalid video source format: {request.input_source}")
            raise VoiceProcessingError(
                message=f"Invalid video source: {request.input_source}",
                error_code=ErrorCode.INVALID_FORMAT,
            )

        progress_tracker.update_progress(10, "Video validation completed")

        # Extract audio from video using FFmpeg
        logger.info(f"🎵 Extracting audio from video: {video_source}")
        progress_tracker.update_progress(15, "Extracting audio from video")

        temp_audio_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp_audio_file.close()

        await processor._extract_audio_from_video(video_source, temp_audio_file.name)
        logger.info(f"✅ Extracted audio from video: {video_source} -> {temp_audio_file.name}")

        # Process audio transcription with chunking
        logger.info(f"🔄 Processing extracted audio: {temp_audio_file.name}")

        # Get full transcript with timestamps and chunks - pass S3 URI for metadata
        result = await processor.process_audio_video(
            input_source=temp_audio_file.name,
            output_dir=str(output_dir),
            min_chunk_tokens=400,
            max_chunk_tokens=800,
            target_chunk_duration=45.0,
            s3_uri=s3_uri,  # Pass S3 URI for metadata consistency
            content_type="video",  # Explicitly mark as video since audio was already extracted
        )

        # process_audio_video now returns a dict with 'chunks' and 'full_transcript'
        transcript_chunks = result.get("chunks", [])
        full_transcript = result.get("full_transcript", "")
        duration_seconds = result.get("duration_seconds", 0)

        logger.info(
            f"✅ Generated {len(transcript_chunks)} transcript chunks, total transcript length: {len(full_transcript)} chars, duration: {duration_seconds}s"
        )

        # Log the exact value we're about to pass
        logger.info(
            f"📊 Video transcription result: duration_seconds={duration_seconds} (type: {type(duration_seconds)})"
        )

        progress_tracker.update_progress(
            85, f"Generated {len(transcript_chunks)} transcript chunks"
        )

        # Update Document table with content_text (unchunked transcript) and duration
        if request.metadata and request.metadata.get("document_id"):
            document_id = request.metadata["document_id"]
            logger.info(
                f"📝 Updating document {document_id} with transcript content (length={len(full_transcript)}) and duration ({duration_seconds}s)"
            )
            await update_document_content(document_id, full_transcript, duration_seconds)
            logger.info(
                f"✅ Updated document {document_id} with {len(full_transcript)} characters of transcript and {duration_seconds}s duration"
            )

        # Ingest chunks into RAG if persona_id and user_id are provided
        if request.persona_id and request.user_id and transcript_chunks:
            # Validate document_id exists before RAG ingestion
            if not request.metadata or not request.metadata.get("document_id"):
                logger.error("document_id missing from metadata - cannot link embeddings to source")
                raise VoiceProcessingError(
                    message="document_id required in metadata for video ingestion",
                    error_code=ErrorCode.INVALID_FORMAT,
                )

            document_id = request.metadata["document_id"]
            logger.info(
                f"📚 Ingesting {len(transcript_chunks)} chunks into RAG (user={request.user_id}, persona={request.persona_id}, source={document_id})"
            )

            from uuid import UUID

            await ingest_chunked_content_to_rag(
                chunks=transcript_chunks,
                user_id=request.user_id,
                persona_id=request.persona_id,
                source_type="video",
                source_record_id=UUID(document_id),
                document_id=document_id,
            )
            progress_tracker.update_progress(95, "Ingested chunks into RAG")
            logger.info("✅ RAG ingestion completed")

        processing_time = time.time() - start_time

        # Calculate statistics
        total_tokens = sum(chunk.get("token_count", 0) for chunk in transcript_chunks)
        total_duration = sum(chunk.get("duration", 0) for chunk in transcript_chunks)
        avg_chunk_tokens = total_tokens / len(transcript_chunks) if transcript_chunks else 0
        avg_chunk_duration = total_duration / len(transcript_chunks) if transcript_chunks else 0

        logger.info(
            f"✅ Video transcription completed successfully in {processing_time:.2f}s: "
            f"{len(transcript_chunks)} chunks, {total_tokens} tokens, {total_duration:.1f}s duration"
        )
        progress_tracker.complete_stage("Video transcription completed successfully")

        # ===== REFRESH USAGE CACHE AFTER SUCCESSFUL VIDEO INGESTION =====
        # Recalculate usage from Documents table to ensure accurate limits
        if request.user_id:
            try:
                logger.info(
                    f"🔄 Refreshing usage cache for user {request.user_id} after video ingestion"
                )
                from uuid import UUID

                from shared.database.voice_job_model import async_session_maker
                from shared.services.usage_cache_service import UsageCacheService

                async with async_session_maker() as session:
                    usage_cache_service = UsageCacheService(session)
                    await usage_cache_service.recalculate_usage_from_source(
                        user_id=(
                            UUID(request.user_id)
                            if isinstance(request.user_id, str)
                            else request.user_id
                        )
                    )
                    await session.commit()
                    logger.info(f"✅ Usage cache refreshed for user {request.user_id} (video)")
            except Exception as cache_error:
                # Non-critical error - log warning but don't fail the job
                logger.warning(f"⚠️ Failed to refresh usage cache: {cache_error}")
        # ===== END USAGE CACHE REFRESH =====

        return JobResult(
            success=True,
            processing_time_seconds=processing_time,
            input_info=input_info,
            transcript_chunks=transcript_chunks,
            transcript_stats={
                "total_chunks": len(transcript_chunks),
                "total_tokens": total_tokens,
                "total_duration": total_duration,
                "average_chunk_tokens": avg_chunk_tokens,
                "average_chunk_duration": avg_chunk_duration,
                "persona_id": str(request.persona_id) if request.persona_id else None,
                "user_id": str(request.user_id) if request.user_id else None,
            },
        )

    except VoiceProcessingError:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(
            f"❌ Video transcription failed after {processing_time:.2f}s: {e}", exc_info=True
        )

        # Capture exception in Sentry with full context
        capture_exception_with_context(
            e,
            extra={
                "input_source": request.input_source,
                "document_id": request.metadata.get("document_id") if request.metadata else None,
                "persona_id": str(request.persona_id) if request.persona_id else None,
                "user_id": str(request.user_id) if request.user_id else None,
                "input_info": input_info,
                "temp_video_file": temp_video_file.name if temp_video_file else None,
                "temp_audio_file": temp_audio_file.name if temp_audio_file else None,
            },
            tags={
                "component": "voice_worker",
                "operation": "video_transcription",
                "parser_type": "assemblyai",
                "severity": "high",
            },
        )

        return JobResult(
            success=False,
            processing_time_seconds=processing_time,
            input_info=input_info,
            error_code="video_transcription_error",
            error_message=str(e),
            error_suggestions=[
                "Check if video file is valid and not corrupted",
                "Ensure ASSEMBLYAI_API_KEY is configured",
                "Ensure FFmpeg is installed for audio extraction",
                "Try again with a different video file",
            ],
        )
    finally:
        # Clean up temporary video file
        if temp_video_file and os.path.exists(temp_video_file.name):
            try:
                os.unlink(temp_video_file.name)
                logger.debug(f"🧹 Cleaned up temporary video file: {temp_video_file.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_video_file.name}: {e}")

        # Clean up temporary audio file
        if temp_audio_file and os.path.exists(temp_audio_file.name):
            try:
                os.unlink(temp_audio_file.name)
                logger.debug(f"🧹 Cleaned up temporary audio file: {temp_audio_file.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_audio_file.name}: {e}")
