"""PDF processing handler for voice processing worker."""

import os
import tempfile
from pathlib import Path
from typing import Dict, Optional
from uuid import UUID

from loguru import logger
from utils.config import config
from utils.progress import ProgressTracker

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.services.s3_service import get_s3_service
from shared.voice_processing.errors import ErrorCode, VoiceProcessingError
from shared.voice_processing.models import JobRequest, JobResult, ProcessingStage

from .pdf_parser import MarkdownPDFParser
from .rag_ingestion import (
    create_persona_data_source_link,
    ensure_persona_exists,
    ingest_chunked_content_to_rag,
)


async def process_pdf_parsing(request: JobRequest, progress_tracker: ProgressTracker) -> JobResult:
    """Process document parsing job (supports PDF and Office formats).

    Supported formats: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX
    All formats are processed through the Datalab.io Marker API which converts
    them to markdown and then chunks them for RAG ingestion.

    Args:
        request: Job request
        progress_tracker: Progress tracking callback

    Returns:
        Job result with parsed document chunks
    """
    import time

    start_time = time.time()

    # Get API keys from settings
    marker_api_key = settings.datalab_api_key
    openai_api_key = settings.openai_api_key

    if not marker_api_key:
        raise VoiceProcessingError(
            message="DATALAB_API_KEY not configured in settings",
            error_code=ErrorCode.CONFIGURATION_ERROR,
        )

    if not openai_api_key:
        raise VoiceProcessingError(
            message="OPENAI_API_KEY not configured in settings",
            error_code=ErrorCode.CONFIGURATION_ERROR,
        )

    pdf_chunks = []
    input_info = {}
    pdf_path = None
    temp_file = None

    try:
        progress_tracker.start_stage(ProcessingStage.VALIDATION, "Validating document source")

        # Create output directory for document processing
        output_dir = config.get_output_dir("pdf_processing")
        output_dir.mkdir(parents=True, exist_ok=True)

        parser = MarkdownPDFParser(
            marker_api_key=marker_api_key,
            openai_api_key=openai_api_key,
            progress_tracker=progress_tracker,
        )

        # Handle document source (S3 path, URL, or local file) - supports PDF and Office formats
        if request.input_source.startswith("s3://"):
            pdf_path, input_info, temp_file = await _download_pdf_from_s3(
                request.input_source, progress_tracker
            )
        elif request.input_source.startswith(("http://", "https://")):
            pdf_path, input_info, temp_file = await _download_pdf_from_url(
                request.input_source, request.metadata, progress_tracker
            )
        else:
            pdf_path, input_info = _validate_local_pdf(request.input_source)

        progress_tracker.update_progress(10, "Document validation completed")

        # Process document to chunks (supports PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX)
        file_ext = Path(pdf_path).suffix.lower()
        logger.info(f"Processing document: {pdf_path} (format: {file_ext})")

        # Get document_id from metadata to pass to parser
        document_id = request.metadata.get("document_id") if request.metadata else None

        # Determine S3 URI for metadata (use original source if it's S3, otherwise None)
        s3_uri = (
            request.input_source
            if request.input_source.startswith("s3://")
            else input_info.get("s3_path")
        )

        # Determine content type from file extension for Marker API
        file_ext = Path(pdf_path).suffix.lower()
        content_type_map = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xls": "application/vnd.ms-excel",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".ppt": "application/vnd.ms-powerpoint",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        }
        content_type = content_type_map.get(file_ext, "application/pdf")
        logger.info(
            f"Processing document with extension '{file_ext}' and content type: {content_type}"
        )

        pdf_chunks = await parser.process_pdf_to_chunks(
            pdf_path=pdf_path,
            output_dir=str(output_dir),
            chunk_size=request.chunk_size,
            overlap=request.overlap,
            force=False,  # Use cache if available
            enhance_images=request.enhance_images,
            document_id=str(document_id) if document_id else None,
            s3_uri=s3_uri,  # Pass S3 URI for metadata
            content_type=content_type,  # Pass content type for Marker API
        )

        logger.info(f"✅ Generated {len(pdf_chunks)} chunks from document (format: {file_ext})")
        logger.info(
            f"📊 Sample chunk keys: {list(pdf_chunks[0].keys()) if pdf_chunks else 'No chunks'}"
        )

        # Ingest document chunks into RAG
        logger.info("🔄 Starting RAG ingestion stage...")

        if request.user_id and pdf_chunks:
            progress_tracker.start_stage(
                ProcessingStage.CHUNK_ENRICHMENT, "Ingesting chunks into RAG"
            )

            logger.info(
                f"📚 Ingesting {len(pdf_chunks)} chunks to RAG for user {request.user_id} (format: {file_ext})"
            )
            logger.info(f"📝 Metadata: {request.metadata}")
            logger.info(
                f"🔑 Document ID: {request.metadata.get('document_id') if request.metadata else 'None'}"
            )
            logger.info(f"👤 Persona ID: {request.persona_id or 'Using default persona'}")

            await _ingest_pdf_chunks_to_rag(
                chunks=pdf_chunks,
                user_id=request.user_id,
                document_id=request.metadata.get("document_id") if request.metadata else None,
                persona_id=request.persona_id,
            )
            logger.info("✅ RAG ingestion completed successfully")
        else:
            progress_tracker.start_stage(ProcessingStage.CLEANUP, "Finalizing document processing")

            if not request.user_id:
                logger.warning("⚠️ Skipping RAG ingestion: No user_id provided")
            if not pdf_chunks:
                logger.warning("⚠️ Skipping RAG ingestion: No document chunks generated")

        processing_time = time.time() - start_time

        # Calculate statistics
        # Note: PDF chunks use 'content' field and 'token_count', not 'word_count'
        total_tokens = sum(chunk.get("token_count", 0) for chunk in pdf_chunks)
        total_chars = sum(len(chunk.get("content", "")) for chunk in pdf_chunks)
        # Approximate words from characters (avg 5 chars per word)
        total_words = total_chars // 5 if total_chars > 0 else 0
        avg_chunk_size = total_words / len(pdf_chunks) if pdf_chunks else 0

        logger.info(
            f"📈 Processing complete: {len(pdf_chunks)} chunks, ~{total_words} words ({total_tokens} tokens), {processing_time:.2f}s (format: {file_ext})"
        )

        progress_tracker.complete_stage(
            f"Document processing completed successfully (format: {file_ext})"
        )

        # ===== REFRESH USAGE CACHE AFTER SUCCESSFUL INGESTION =====
        # Recalculate usage from Documents table to ensure accurate limits
        if request.user_id:
            try:
                logger.info(f"🔄 Refreshing usage cache for user {request.user_id}")
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
                    logger.info(f"✅ Usage cache refreshed for user {request.user_id}")
            except Exception as cache_error:
                # Non-critical error - log warning but don't fail the job
                logger.warning(f"⚠️ Failed to refresh usage cache: {cache_error}")
        # ===== END USAGE CACHE REFRESH =====

        return JobResult(
            success=True,
            processing_time_seconds=processing_time,
            input_info=input_info,
            pdf_chunks=pdf_chunks,
            pdf_stats={
                "total_chunks": len(pdf_chunks),
                "total_words": total_words,
                "total_characters": total_chars,
                "average_chunk_size": avg_chunk_size,
                "persona_id": str(request.persona_id) if request.persona_id else None,
                "user_id": str(request.user_id) if request.user_id else None,
            },
        )

    except VoiceProcessingError:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Document parsing failed: {e}")

        # Capture exception in Sentry with full context
        capture_exception_with_context(
            e,
            extra={
                "input_source": request.input_source,
                "document_id": request.metadata.get("document_id") if request.metadata else None,
                "persona_id": str(request.persona_id) if request.persona_id else None,
                "user_id": str(request.user_id) if request.user_id else None,
                "file_path": pdf_path,
                "input_info": input_info,
                "chunk_size": request.chunk_size,
                "overlap": request.overlap,
            },
            tags={
                "component": "voice_worker",
                "operation": "pdf_parsing",
                "severity": "high",
                "parser_type": "pdf_handler",
            },
        )

        return JobResult(
            success=False,
            processing_time_seconds=processing_time,
            input_info=input_info,
            error_code="document_processing_error",
            error_message=str(e),
            error_suggestions=[
                "Check if document is valid and not corrupted",
                "Ensure DATALAB_API_KEY and OPENAI_API_KEY are set",
                "Try again with a different document",
                "Supported formats: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX",
            ],
        )
    finally:
        # Clean up temporary file if created
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_file.name}: {e}")


async def _download_pdf_from_s3(
    s3_path: str, progress_tracker: ProgressTracker
) -> tuple[str, Dict, tempfile._TemporaryFileWrapper]:
    """Download document from S3 (supports PDF and Office formats).

    Args:
        s3_path: S3 URI
        progress_tracker: Progress tracker

    Returns:
        Tuple of (document_path, input_info, temp_file)
    """
    progress_tracker.update_progress(5, "Downloading document from S3")

    # Extract file extension from S3 path to preserve format
    file_ext = Path(s3_path).suffix.lower() or ".pdf"

    temp_file = tempfile.NamedTemporaryFile(suffix=file_ext, delete=False)
    temp_file.close()

    s3_service = get_s3_service()
    pdf_path = await s3_service.download_file(s3_path=s3_path, local_path=temp_file.name)

    input_info = {
        "source": "s3",
        "s3_path": s3_path,
        "file_size": os.path.getsize(pdf_path),
        "file_extension": file_ext,
    }

    logger.info(f"Downloaded document from S3: {s3_path} -> {pdf_path} (format: {file_ext})")
    return pdf_path, input_info, temp_file


async def _download_pdf_from_url(
    url: str, metadata: Optional[Dict], progress_tracker: ProgressTracker
) -> tuple[str, Dict, tempfile._TemporaryFileWrapper]:
    """Download document from HTTP/HTTPS URL (supports PDF and Office formats).

    Args:
        url: Document URL
        metadata: Request metadata
        progress_tracker: Progress tracker

    Returns:
        Tuple of (document_path, input_info, temp_file)
    """
    progress_tracker.update_progress(5, "Downloading document from URL")

    # Extract file extension from URL to preserve format
    file_ext = Path(url).suffix.lower() or ".pdf"

    temp_file = tempfile.NamedTemporaryFile(suffix=file_ext, delete=False)
    temp_file.close()

    document_id = metadata.get("document_id") if metadata else None

    # Import download helper
    from utils.download_utils import download_document_from_url

    pdf_path = await download_document_from_url(url, temp_file.name, document_id)

    input_info = {
        "source": "url",
        "url": url,
        "file_size": os.path.getsize(pdf_path),
        "file_extension": file_ext,
    }

    return pdf_path, input_info, temp_file


def _validate_local_pdf(file_path: str) -> tuple[str, Dict]:
    """Validate local document file (supports PDF and Office formats).

    Args:
        file_path: Local file path

    Returns:
        Tuple of (document_path, input_info)

    Raises:
        VoiceProcessingError: If file not found or unsupported format
    """
    pdf_path = Path(file_path)

    if not pdf_path.exists():
        raise VoiceProcessingError(
            message=f"Document file not found: {file_path}",
            error_code=ErrorCode.FILE_NOT_FOUND,
        )

    # Check if file extension is supported
    file_ext = pdf_path.suffix.lower()
    supported_formats = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}

    if file_ext not in supported_formats:
        raise VoiceProcessingError(
            message=f"Unsupported file format: {file_ext}. Supported formats: {', '.join(supported_formats)}",
            error_code=ErrorCode.INVALID_FORMAT,
        )

    input_info = {
        "source": "local_file",
        "file_path": str(pdf_path),
        "file_size": os.path.getsize(str(pdf_path)),
        "file_extension": file_ext,
    }

    return str(pdf_path), input_info


async def _ingest_pdf_chunks_to_rag(
    chunks: list[Dict],
    user_id: UUID,
    document_id: Optional[str],
    persona_id: Optional[str],
) -> None:
    """Ingest document chunks into RAG system using centralized ingestion module.

    Args:
        chunks: List of processed document chunks (PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX)
        user_id: ID of the user who owns the document
        document_id: ID of the document
        persona_id: ID of the persona (optional, for direct ingestion)
    """
    try:
        # Extract source type from chunks (dynamic based on file extension)
        # All chunks should have the same source type, so we get it from the first chunk
        source_type = chunks[0].get("source", "pdf") if chunks else "pdf"

        logger.info(f"🔍 Detected source type from chunks: {source_type}")

        # Ensure persona exists (get existing or create default)
        final_persona_id = await ensure_persona_exists(
            user_id=user_id,
            persona_id=UUID(persona_id) if persona_id else None,
        )

        # Create PersonaDataSource link if document_id is provided
        if document_id:
            doc_uuid = UUID(document_id) if isinstance(document_id, str) else document_id

            # Map document formats to 'document' or 'pdf' for PersonaDataSource CheckConstraint
            # The constraint only allows: linkedin, twitter, website, pdf, github, medium, youtube, document
            persona_source_type_map = {
                "pdf": "pdf",
                "doc": "document",
                "docx": "document",
                "xls": "document",
                "xlsx": "document",
                "ppt": "document",
                "pptx": "document",
            }
            persona_source_type = persona_source_type_map.get(source_type, "document")

            await create_persona_data_source_link(
                persona_id=final_persona_id,
                source_type=persona_source_type,  # Use mapped source_type for PersonaDataSource
                source_record_id=doc_uuid,
            )

        # Use centralized RAG ingestion with dynamic source_type
        result = await ingest_chunked_content_to_rag(
            chunks=chunks,
            user_id=user_id,
            persona_id=final_persona_id,
            source_type=source_type,  # Use dynamic source_type instead of hardcoded "pdf"
            document_id=document_id,
        )

        logger.info(
            f"✅ {source_type.upper()} RAG ingestion completed: "
            f"persona_id={final_persona_id}, "
            f"chunks_added={result.get('chunks_added', 0)}, "
            f"source_type={source_type}"
        )

    except Exception as e:
        logger.error(f"❌ RAG ingestion failed for PDF (user={user_id}): {e}", exc_info=True)
        # Don't fail the entire job if ingestion fails - just log the warning
