"""
Document Ingestion API Routes

Endpoints:
- POST /api/v1/documents/add - Add document for processing
- POST /api/v1/documents/add-text - Add raw text content directly (meeting notes, transcripts, etc.)
- POST /api/v1/documents/process-pdf-data - Process PDF file upload for document ingestion
- POST /api/v1/documents/refresh - Refresh embeddings for existing document
- GET /api/v1/documents/{user_id} - Retrieve all documents for a user
- DELETE /api/v1/documents/{document_id} - Delete a document
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.document_utils import (
    calculate_file_checksum,
    check_document_dependency,
    cleanup_document_data,
    delete_document_embeddings,
)
from app.auth import require_api_key
from app.auth.optimized_middleware import require_jwt_or_api_key
from shared.config import settings
from shared.database.models.database import Persona, get_session
from shared.database.models.document import Document
from shared.database.models.embeddings import VoyageLiteEmbedding
from shared.database.models.persona_data_source import PersonaDataSource
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.services.s3_service import get_s3_service
from shared.services.tier_service import TierLimitExceeded, TierService
from shared.services.usage_cache_service import UsageCacheService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["Document Ingestion"])

# Supported document types and their MIME types
SUPPORTED_DOCUMENT_TYPES = {
    ".pdf": "application/pdf",
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

# Document types that support enrichment processing
ENRICHMENT_SUPPORTED_TYPES = {
    ".pdf",
    ".mp4",
    ".mp3",
    ".wav",
    ".m4a",
    ".mov",
    ".avi",
    ".mkv",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".md",
}


class DocumentAddRequest(BaseModel):
    """Request to add a document for processing"""

    url: str = Field(..., description="URL of the document to process")
    document_type: str = Field(..., description="Document file extension (e.g., .pdf, .mp4, .mp3)")
    user_id: UUID = Field(..., description="User UUID who owns this document")
    persona_id: Optional[UUID] = Field(
        None, description="Persona UUID. If None, uses 'default' persona"
    )
    force: bool = Field(False, description="Force update even if document already exists")

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        """Validate document type is supported"""
        if not v.startswith("."):
            v = f".{v}"
        v = v.lower()
        if v not in SUPPORTED_DOCUMENT_TYPES:
            supported = ", ".join(SUPPORTED_DOCUMENT_TYPES.keys())
            raise ValueError(f"Unsupported document type. Supported types: {supported}")
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format"""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/document.pdf",
                "document_type": ".pdf",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "persona_id": "456e7890-e89b-12d3-a456-426614174000",
                "force": False,
            }
        }


class DocumentResponse(BaseModel):
    """Response from document operations"""

    success: bool
    message: str
    document_id: Optional[UUID] = None
    job_id: Optional[UUID] = None
    supports_enrichment: bool = False


class DocumentInfo(BaseModel):
    """Document information for listing"""

    id: UUID
    filename: str
    document_type: str
    file_size: Optional[int]
    uploaded_at: str
    metadata: Dict[str, Any]


class DocumentListResponse(BaseModel):
    """Response for document listing"""

    documents: List[DocumentInfo]
    total_count: int


# Voice Processing Queue Service for document jobs
def get_voice_processing_queue_service():
    """Get voice processing queue service instance."""
    try:
        from shared.voice_processing.job_service import get_queue_service

        return get_queue_service()
    except ImportError:
        # Fallback if voice processing queue service is not available
        logger.warning("Voice processing queue service not available, jobs will not be queued")
        return None


async def get_or_create_default_persona(session: AsyncSession, user_id: UUID) -> Persona:
    """Get or create default persona for user"""
    stmt = select(Persona).where(
        Persona.user_id == user_id, Persona.persona_name == "default", Persona.is_active == True
    )
    result = await session.execute(stmt)
    persona = result.scalar_one_or_none()

    if not persona:
        # Create default persona
        persona = Persona(
            user_id=user_id,
            persona_name="default",
            name="Default Persona",
            description="Default persona for document ingestion",
        )
        session.add(persona)
        await session.flush()
        await session.refresh(persona)

    return persona


@router.post("/add", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def add_document(
    user_id: UUID = Form(..., description="User UUID who owns this document"),
    persona_name: str = Form("default", description="Persona name. Defaults to 'default'"),
    force: bool = Form(False, description="Force re-upload even if document exists"),
    file: UploadFile = File(..., description="Document file to process (PDF, audio, or video)"),
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(require_api_key),
):
    """
    Add document for processing (PDF, audio, or video) with duplicate detection

    This endpoint:
    1. Calculates checksum for duplicate detection
    2. Checks if document already exists by checksum
    3. If exists and force=false: Returns appropriate message
    4. If force=true: Cleans up and re-processes with usage cache refresh
    5. Validates the uploaded file (PDF, audio, or video)
    6. **Checks tier limits before processing**
    7. Classifies the file format (pdf, audio, video)
    8. Uploads the file to S3
    9. Creates a document entry in the database
    10. **Updates usage cache immediately after document creation**
    11. Creates persona_data_source entry
    12. Queues appropriate processing job based on file type
    13. **All operations in single transaction - rollback on any failure**

    Parameters:
        user_id: The UUID of the user who owns this document
        persona_name: The name of the persona (defaults to "default")
        force: Force re-upload and re-process even if document exists
        file: The document file to upload and process (PDF, MP3, MP4, WAV, etc.)

    Supported formats:
        - PDF: .pdf
        - Audio: .mp3, .wav, .m4a
        - Video: .mp4, .mov, .avi, .mkv
    """
    document = None
    job_id = None
    s3_path = None

    try:
        logger.info(
            f"Processing document upload for user {user_id}, persona: {persona_name}, "
            f"file: {file.filename}, force: {force}"
        )

        # Read file content first for validation and checksum
        content = await file.read()
        await file.seek(0)  # Reset file pointer

        # Calculate checksum for duplicate detection
        checksum = calculate_file_checksum(content)
        logger.info(
            f"Calculated file checksum: {checksum} for user {user_id}. "
            f"Checking for duplicates within this user's documents only."
        )

        # Check if document already exists by checksum FOR THIS USER
        # Note: Multiple users can upload the same file (same checksum)
        # Duplicate detection is per-user based on (user_id, checksum) combination
        existing_doc, has_embeddings = await check_document_dependency(session, user_id, checksum)

        if existing_doc and not force:
            # Document exists and force mode is not enabled
            if has_embeddings:
                # Case 1: Document and embeddings both exist
                logger.info(
                    f"Duplicate document found for user {user_id}: {existing_doc.id} with embeddings. "
                    f"File: {existing_doc.filename}, Checksum: {checksum}"
                )
                return DocumentResponse(
                    success=False,
                    message=(
                        f"You have already uploaded this file. "
                        f"Document already exists with embeddings. "
                        f"Use force=true to re-upload and re-process. "
                        f"Document ID: {existing_doc.id}"
                    ),
                    document_id=existing_doc.id,
                    supports_enrichment=True,
                )
            else:
                # Case 2: Document exists but embeddings are missing
                logger.info(
                    f"Document found for user {user_id}: {existing_doc.id} but embeddings missing. "
                    f"File: {existing_doc.filename}, Checksum: {checksum}"
                )
                return DocumentResponse(
                    success=False,
                    message=(
                        f"You have already uploaded this file but embeddings are missing. "
                        f"Use the /refresh endpoint to regenerate embeddings. "
                        f"Document ID: {existing_doc.id}"
                    ),
                    document_id=existing_doc.id,
                    supports_enrichment=True,
                )

        # ===== HANDLE FORCE MODE =====
        # If force=True and document exists, delete it first, then refresh usage cache
        if existing_doc and force:
            logger.info(f"Force mode: cleaning up existing document {existing_doc.id}")
            try:
                # Start transaction for deletion and usage cache refresh
                # Get persona first to pass to cleanup
                stmt = select(Persona).where(
                    Persona.user_id == user_id,
                    Persona.persona_name == persona_name,
                    Persona.is_active == True,
                )
                result = await session.execute(stmt)
                temp_persona = result.scalar_one_or_none()

                # Cleanup document (deletes embeddings, persona_data_source, and document)
                if temp_persona:
                    await cleanup_document_data(session, existing_doc.id, temp_persona.id)
                else:
                    await cleanup_document_data(session, existing_doc.id)

                # After successful deletion, refresh usage cache from Documents table
                usage_cache_service = UsageCacheService(session)
                await usage_cache_service.recalculate_usage_from_source(user_id=user_id)

                # Commit deletion and cache refresh
                await session.commit()
                logger.info(
                    f"Force mode: Successfully deleted document {existing_doc.id} "
                    f"and refreshed usage cache for user {user_id}"
                )
            except IntegrityError as cleanup_error:
                await session.rollback()
                logger.error(
                    f"Database integrity error during cleanup in force mode: {cleanup_error}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to upload document: Could not cleanup existing document due to database constraint.",
                )
            except SQLAlchemyError as cleanup_error:
                await session.rollback()
                logger.error(f"Database error during cleanup in force mode: {cleanup_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to upload document: Database error while cleaning up existing document.",
                )
            except Exception as cleanup_error:
                await session.rollback()
                logger.error(f"Unexpected error during cleanup in force mode: {cleanup_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to upload document: Could not cleanup existing document.",
                )
        # ===== END FORCE MODE HANDLING =====
        logger.info("LIMITS Check for user will be performed now.")
        # Validate file size (100MB limit)
        if len(content) > settings.max_file_upload_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size allowed is {settings.max_file_upload_size // (1024 * 1024)}MB",
            )

        # Determine file type and validate
        file_ext = None
        file_type_category = None  # 'pdf', 'audio', or 'video'

        # Get file extension
        if file.filename:
            file_ext = Path(file.filename).suffix.lower()

        if not file_ext:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not determine file extension from filename: {file.filename}",
            )

        # Classify file type
        if file_ext == ".pdf":
            file_type_category = "pdf"
            # Validate PDF content using magic bytes
            if not content[:5] == b"%PDF-":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid PDF file format. File '{file.filename}' does not contain valid PDF content",
                )
        elif file_ext in [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"]:
            file_type_category = "office_document"
            # Modern Office files (.docx, .xlsx, .pptx) are ZIP archives (magic bytes: PK\x03\x04)
            # Legacy Office files (.doc, .xls, .ppt) are OLE/CFB format (magic bytes: \xD0\xCF\x11\xE0)
            is_modern_office = content[:4] == b"PK\x03\x04"
            is_legacy_office = content[:4] == b"\xd0\xcf\x11\xe0"

            if not (is_modern_office or is_legacy_office):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid Office file format. File '{file.filename}' does not contain valid Office document content",
                )

            # Additional validation for legacy Office files to prevent non-Office OLE2 files
            # (MSI installers, Outlook MSG, Windows shortcuts also use OLE2/CFB format)
            if is_legacy_office and file_ext in [".doc", ".xls", ".ppt"]:
                try:
                    import io

                    import olefile

                    # Parse OLE structure
                    ole = olefile.OleFileIO(io.BytesIO(content))

                    # Check for Office-specific streams based on file type
                    office_stream_signatures = {
                        ".doc": ["WordDocument", "1Table", "0Table", "Data"],  # Word streams
                        ".xls": ["Workbook", "Book"],  # Excel streams
                        ".ppt": ["PowerPoint Document", "Current User"],  # PowerPoint streams
                    }

                    required_streams = office_stream_signatures.get(file_ext, [])
                    found_streams = ole.listdir()

                    # Flatten stream list for easier checking
                    flat_streams = ["/".join(stream) for stream in found_streams]

                    # Check if at least one required stream exists
                    has_office_stream = any(
                        any(req_stream in stream for stream in flat_streams)
                        for req_stream in required_streams
                    )

                    ole.close()

                    if not has_office_stream:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Invalid {file_ext.upper()} file. File '{file.filename}' appears to be "
                                f"an OLE2 container but does not contain valid Office document streams. "
                                f"This may be an MSI installer, Outlook MSG file, or other non-Office OLE2 file."
                            ),
                        )

                    logger.info(
                        f"✅ Validated legacy Office file {file.filename}: "
                        f"Found Office-specific streams for {file_ext}"
                    )

                except ImportError:
                    # olefile not available - log warning and continue
                    logger.warning(
                        f"⚠️ olefile library not available for legacy Office validation. "
                        f"Skipping OLE structure check for {file.filename}. "
                        f"File will be validated by Marker API during processing."
                    )
                except Exception as e:
                    # OLE parsing failed - likely not a valid Office file
                    logger.error(f"❌ Failed to validate legacy Office file {file.filename}: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Invalid {file_ext.upper()} file. File '{file.filename}' failed OLE structure validation. "
                            f"Please ensure the file is a valid Microsoft Office document."
                        ),
                    )
        elif file_ext in [".mp3", ".wav", ".m4a"]:
            file_type_category = "audio"
        elif file_ext in [".mp4", ".mov", ".avi", ".mkv"]:
            file_type_category = "video"
        elif file_ext in [".txt", ".md"]:
            file_type_category = "text"
            # Validate text content can be decoded as UTF-8
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid text file format. File '{file.filename}' is not valid UTF-8 text",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {file_ext}. Supported types: .pdf, .doc, .docx, .xls, .xlsx, .ppt, .pptx, .mp3, .wav, .m4a, .mp4, .mov, .avi, .mkv, .txt, .md",
            )

        # Validate file extension is in supported types
        if file_ext not in SUPPORTED_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension {file_ext} not in supported types",
            )

        # ===== START TRANSACTION FOR TIER CHECK + DOCUMENT CREATION + USAGE UPDATE =====
        try:
            # ===== TIER LIMIT CHECK =====
            # Check tier limits before processing the upload (with row lock to prevent race conditions)
            tier_service = TierService(session)
            try:
                # For multimedia files, we would need duration - but we can't get it before upload
                # So we'll do a basic check here and a full check after processing
                logger.info(f"Tier limit check for user {user_id}, file: {file.filename}")
                await tier_service.check_document_upload_allowed(
                    user_id=user_id,
                    file_size_bytes=len(content),
                    file_extension=file_ext,
                    duration_seconds=None,  # Duration will be checked later for multimedia
                )
                logger.info(f"Tier limit check passed for user {user_id}, file: {file.filename}")
            except TierLimitExceeded as e:
                logger.warning(f"Tier limit exceeded for user {user_id}: {e}")
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
            # ===== END TIER LIMIT CHECK =====

            # Find or create persona by user_id and persona_name
            stmt = select(Persona).where(
                Persona.user_id == user_id,
                Persona.persona_name == persona_name,
                Persona.is_active == True,
            )
            result = await session.execute(stmt)
            persona = result.scalar_one_or_none()

            if not persona:
                # Create persona if it doesn't exist
                persona = Persona(
                    user_id=user_id,
                    persona_name=persona_name,
                    name=persona_name.title() if persona_name != "default" else "Default Persona",
                    description=f"Persona '{persona_name}' for document ingestion",
                )
                session.add(persona)
                await session.flush()
                await session.refresh(persona)
                logger.info(f"Created new persona: {persona_name} for user {user_id}")

            # Upload file to S3
            s3_service = get_s3_service()

            # Ensure bucket exists
            await s3_service.ensure_bucket_exists()

            # Upload to S3: bucket-name/user-id/filename
            s3_path = await s3_service.upload_file(
                file_content=content,
                user_id=str(user_id),
                filename=file.filename,
                content_type=SUPPORTED_DOCUMENT_TYPES[file_ext],
            )
            logger.info(f"Uploaded file to S3: {s3_path}")

            # Extract metadata based on file type
            metadata = {
                "url": s3_path,
                "original_filename": file.filename,
                "content_type": SUPPORTED_DOCUMENT_TYPES[file_ext],
                "s3_path": s3_path,
                "file_type_category": file_type_category,
                "original_extension": file_ext,  # Store original file extension
                "checksum": checksum,  # Store checksum for duplicate detection
            }

            # For PDF, extract page count
            if file_type_category == "pdf":
                page_count = 1  # Default fallback
                try:
                    import io

                    from pypdf import PdfReader

                    pdf_reader = PdfReader(io.BytesIO(content))
                    page_count = len(pdf_reader.pages)
                    metadata["page_count"] = page_count
                    logger.info(f"Extracted page count from PDF: {page_count} pages")
                except ImportError:
                    logger.warning("pypdf library not available, using default page count: 1")
                except Exception as e:
                    logger.warning(f"Failed to extract page count from PDF: {e}")
            elif file_type_category == "office_document":
                # For Office documents, extract metadata counts
                # Modern formats (.docx, .pptx, .xlsx) are ZIP-based
                # Legacy formats (.doc, .xls, .ppt) are OLE/CFB-based
                try:
                    import io
                    import zipfile

                    if file_ext == ".pptx":
                        # Extract slide count from PPTX
                        slide_count = 1  # Default fallback
                        try:
                            with zipfile.ZipFile(io.BytesIO(content)) as pptx:
                                # Count slide XML files in ppt/slides/
                                slide_files = [
                                    name
                                    for name in pptx.namelist()
                                    if name.startswith("ppt/slides/slide") and name.endswith(".xml")
                                ]
                                slide_count = len(slide_files)
                                metadata["slide_count"] = slide_count
                                logger.info(
                                    f"Extracted slide count from PPTX: {slide_count} slides"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Failed to extract slide count from PPTX: {e}, using default: 1"
                            )
                            metadata["slide_count"] = 1

                    elif file_ext == ".ppt":
                        # Legacy PPT format - use default, Marker API will determine actual count
                        metadata["slide_count"] = 1
                        logger.info(
                            "PPT (legacy) file - slide count will be determined during processing"
                        )

                    elif file_ext == ".xlsx":
                        # Extract sheet count from XLSX
                        sheet_count = 1  # Default fallback
                        try:
                            with zipfile.ZipFile(io.BytesIO(content)) as xlsx:
                                # Count sheet XML files in xl/worksheets/
                                sheet_files = [
                                    name
                                    for name in xlsx.namelist()
                                    if name.startswith("xl/worksheets/sheet")
                                    and name.endswith(".xml")
                                ]
                                sheet_count = len(sheet_files)
                                metadata["sheet_count"] = sheet_count
                                logger.info(
                                    f"Extracted sheet count from XLSX: {sheet_count} sheets"
                                )
                        except Exception as e:
                            logger.warning(
                                f"Failed to extract sheet count from XLSX: {e}, using default: 1"
                            )
                            metadata["sheet_count"] = 1

                    elif file_ext == ".xls":
                        # Legacy XLS format - use default, Marker API will determine actual count
                        metadata["sheet_count"] = 1
                        logger.info(
                            "XLS (legacy) file - sheet count will be determined during processing"
                        )

                    elif file_ext == ".docx":
                        # For DOCX, we can't easily count pages without rendering
                        # Use page_count = 1 as placeholder (Marker API will determine actual count)
                        metadata["page_count"] = 1
                        logger.info("DOCX file - page count will be determined during processing")

                    elif file_ext == ".doc":
                        # Legacy DOC format - use default, Marker API will determine actual count
                        metadata["page_count"] = 1
                        logger.info(
                            "DOC (legacy) file - page count will be determined during processing"
                        )

                except Exception as e:
                    logger.warning(f"Failed to extract Office document metadata: {e}")
                    # Set default values to satisfy database constraints
                    if file_ext in [".pptx", ".ppt"]:
                        metadata["slide_count"] = 1
                    elif file_ext in [".xlsx", ".xls"]:
                        metadata["sheet_count"] = 1
                    elif file_ext in [".docx", ".doc"]:
                        metadata["page_count"] = 1

            # Determine document_type for database
            # Store the actual file extension for all file types
            # This allows proper categorization and filtering later
            db_document_type = file_ext.lstrip(".")

            logger.info(
                f"Document will be stored with type: {db_document_type} (category: {file_type_category})"
            )
            try:
                # Create document entry
                document = Document(
                    user_id=user_id,
                    document_type=db_document_type,
                    filename=file.filename,
                    file_size=len(content),
                    document_metadata=metadata,
                )

                session.add(document)
                await session.flush()
                await session.refresh(document)
                logger.info(
                    f"Created document entry: {document.id} ({file_type_category}) with document_type={db_document_type}"
                )

                # ===== END STAGE 1 =====

                # Create persona_data_source entry
                # Use 'document' as source_type for all file types (audio, video, pdf)
                # since the constraint only allows specific values
                source_type_for_db = "pdf" if file_type_category == "pdf" else "document"

                stmt = select(PersonaDataSource).where(
                    PersonaDataSource.persona_id == persona.id,
                    PersonaDataSource.source_type == source_type_for_db,
                    PersonaDataSource.source_record_id == document.id,
                )
                result = await session.execute(stmt)
                existing_data_source = result.scalar_one_or_none()

                if not existing_data_source:
                    data_source = PersonaDataSource(
                        persona_id=persona.id,
                        source_type=source_type_for_db,
                        source_record_id=document.id,
                        enabled=True,
                        source_filters={
                            "document_type": file_ext,
                            "url": s3_path,
                            "file_type_category": file_type_category,  # Keep track of actual type
                        },
                    )
                    session.add(data_source)
                    logger.info(
                        f"Created persona_data_source for uploaded {file_type_category} {document.id} with source_type={source_type_for_db}"
                    )

                    # ===== STAGE 2: USAGE CACHE UPDATE =====
                    # Update usage cache immediately after document creation (within same transaction)
                    # This provides fast usage tracking and is protected by transaction rollback on failure
                    usage_cache_service = UsageCacheService(session)
                    await usage_cache_service.increment_usage_optimistic(
                        user_id=user_id,
                        file_extension=file_ext,
                        file_size_bytes=len(content),
                        duration_seconds=None,  # Duration extracted by worker in Stage 2
                    )
                    logger.info(
                        f"[Stage 1] Updated usage cache for user {user_id}: "
                        f"file={file.filename}, size={len(content)} bytes"
                    )
            except Exception as e:
                logger.error(f"Failed to create document or persona_data_source: {e}")
                if s3_path:
                    try:
                        s3_service = get_s3_service()
                        await s3_service.delete_file(s3_path)
                        logger.info(f"Cleaned up S3 file after transaction failure: {s3_path}")
                    except Exception as s3_error:
                        logger.warning(f"Failed to cleanup S3 file {s3_path}: {s3_error}")
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to add document: {str(e)}",
                )

            # Flush to database but don't commit yet - wait for job creation
            await session.commit()

            # Get voice processing queue service and queue appropriate job
            vp_queue_service = get_voice_processing_queue_service()

            if vp_queue_service:
                try:
                    # Always initialize the queue service before use
                    logger.info("Initializing voice processing queue service...")
                    await vp_queue_service.initialize()
                    logger.info("Voice processing queue service initialized successfully")

                    import uuid as _uuid

                    job_id = _uuid.uuid4()

                    # Queue appropriate processing job based on file type
                    success = False
                    if file_type_category == "pdf":
                        success = await vp_queue_service.publish_pdf_job(
                            user_id=str(user_id),
                            document_id=str(document.id),
                            input_source=s3_path,
                            job_id=str(job_id),
                            persona_id=str(persona.id),
                        )
                    elif file_type_category == "office_document":
                        # Office documents (DOCX, PPTX, XLSX) use same Marker API pipeline as PDFs
                        success = await vp_queue_service.publish_pdf_job(
                            user_id=str(user_id),
                            document_id=str(document.id),
                            input_source=s3_path,
                            job_id=str(job_id),
                            persona_id=str(persona.id),
                        )
                    elif file_type_category == "audio":
                        success = await vp_queue_service.publish_audio_job(
                            user_id=str(user_id),
                            document_id=str(document.id),
                            input_source=s3_path,
                            job_id=str(job_id),
                            persona_id=str(persona.id),
                        )
                    elif file_type_category == "video":
                        success = await vp_queue_service.publish_video_job(
                            user_id=str(user_id),
                            document_id=str(document.id),
                            input_source=s3_path,
                            job_id=str(job_id),
                            persona_id=str(persona.id),
                        )
                    elif file_type_category == "text":
                        # For text files (.txt, .md), queue text processing job
                        # This will generate summary, keywords, and embeddings similar to transcripts
                        success = await vp_queue_service.publish_text_job(
                            user_id=str(user_id),
                            document_id=str(document.id),
                            input_source=s3_path,
                            job_id=str(job_id),
                            persona_id=str(persona.id),
                        )

                    if not success:
                        logger.error(f"Failed to queue {file_type_category} processing job")
                        raise Exception(f"Failed to queue {file_type_category} processing job")

                    logger.info(f"Queued {file_type_category} processing job: {job_id}")

                except Exception as queue_error:
                    logger.error(f"Error queueing processing job: {queue_error}")
                    raise  # Will trigger rollback
            else:
                logger.error("Voice processing queue service not available")
                raise Exception("Voice processing queue service not available")

            # ===== COMMIT TRANSACTION =====
            # Only commit if everything succeeded: tier check, document creation, usage cache update, and job queued
            # await session.commit()
            logger.info(
                f"Successfully committed transaction: document {document.id}, "
                f"job {job_id}, usage cache updated for user {user_id}"
            )
            # ===== END TRANSACTION =====

            return DocumentResponse(
                success=True,
                message=f"{file_type_category.upper()} file uploaded and processing job queued successfully",
                document_id=document.id,
                job_id=job_id,
                supports_enrichment=True,
            )

        except HTTPException:
            logger.warning("HTTPException during document add, rolled back transaction")
            raise
        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Database integrity error while adding document: {e}")
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to upload document: Database integrity constraint violated. This may indicate a duplicate or invalid reference.",
            )
        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"Database error while adding document: {e}")
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload document: Database operation failed. Please try again later.",
            )
        except Exception as e:
            await session.rollback()
            logger.error(f"Unexpected error in transaction while adding document: {e}")
            import traceback

            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload document: An unexpected error occurred during processing.",
            )

    except HTTPException:
        raise
    except TierLimitExceeded as e:
        logger.error(f"Tier limit exceeded while adding document: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"Failed to upload document: {str(e)}"
        )
    except IntegrityError as e:
        logger.error(f"Database integrity error in add_document: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to upload document: Data validation failed. Please check your input and try again.",
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error in add_document: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document: Database operation failed. Please try again later.",
        )
    except Exception as e:
        logger.error(f"Unexpected error in add_document: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {type(e).__name__}. Please contact support if this persists.",
        )


class RawTextAddRequest(BaseModel):
    """Request to add raw text content directly"""

    title: str = Field(
        ..., description="Title for the text content (e.g., 'Meeting Notes - Jan 2024')"
    )
    content: str = Field(..., description="Raw text content to process")
    user_id: UUID = Field(..., description="User UUID who owns this content")
    persona_name: str = Field("default", description="Persona name. Defaults to 'default'")
    force: bool = Field(False, description="Force re-upload even if content already exists")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is not empty and reasonable length"""
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        if len(v) > 255:
            raise ValueError("Title must be 255 characters or less")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate content is not empty"""
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
        if len(v) < 10:
            raise ValueError("Content must be at least 10 characters")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Team Meeting Notes - January 2024",
                "content": "Meeting agenda:\n1. Project updates\n2. Q1 planning\n...",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "persona_name": "default",
                "force": False,
            }
        }


@router.post("/add-text", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def add_raw_text(
    request: RawTextAddRequest,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(require_api_key),
):
    """
    Add raw text content directly as a data source (meeting notes, transcripts, etc.)

    This endpoint allows users to paste text content directly without creating a file.
    The text is saved as a .txt file in S3 and processed like any other text document.

    Use cases:
    - Meeting notes
    - Transcripts
    - Notes from calls
    - Any text content that doesn't need to be in a file

    This endpoint:
    1. Validates the text content
    2. Calculates checksum for duplicate detection
    3. Checks if content already exists by checksum
    4. **Checks tier limits before processing**
    5. Saves text as .txt file to S3
    6. Creates a document entry in the database
    7. **Updates usage cache immediately**
    8. Creates persona_data_source entry
    9. Queues text processing job for embeddings generation

    Parameters:
        title: A descriptive title for the content
        content: The raw text content to process
        user_id: The UUID of the user who owns this content
        persona_name: The name of the persona (defaults to "default")
        force: Force re-upload even if content already exists
    """
    document = None
    job_id = None
    s3_path = None
    user_id = request.user_id
    persona_name = request.persona_name
    force = request.force

    try:
        logger.info(
            f"Processing raw text upload for user {user_id}, persona: {persona_name}, "
            f"title: {request.title}, content_length: {len(request.content)}, force: {force}"
        )

        # Convert text content to bytes (UTF-8)
        content_bytes = request.content.encode("utf-8")
        content_length = len(content_bytes)

        # Calculate checksum for duplicate detection
        checksum = calculate_file_checksum(content_bytes)
        logger.info(
            f"Calculated content checksum: {checksum} for user {user_id}. "
            f"Checking for duplicates within this user's documents only."
        )

        # Check if content already exists by checksum FOR THIS USER
        existing_doc, has_embeddings = await check_document_dependency(session, user_id, checksum)

        if existing_doc and not force:
            if has_embeddings:
                logger.info(
                    f"Duplicate content found for user {user_id}: {existing_doc.id} with embeddings. "
                    f"Title: {existing_doc.filename}, Checksum: {checksum}"
                )
                return DocumentResponse(
                    success=False,
                    message=(
                        f"You have already added this content. "
                        f"Document already exists with embeddings. "
                        f"Use force=true to re-upload and re-process. "
                        f"Document ID: {existing_doc.id}"
                    ),
                    document_id=existing_doc.id,
                    supports_enrichment=True,
                )
            else:
                logger.info(
                    f"Content found for user {user_id}: {existing_doc.id} but embeddings missing. "
                    f"Title: {existing_doc.filename}, Checksum: {checksum}"
                )
                return DocumentResponse(
                    success=False,
                    message=(
                        f"You have already added this content but embeddings are missing. "
                        f"Use the /refresh endpoint to regenerate embeddings. "
                        f"Document ID: {existing_doc.id}"
                    ),
                    document_id=existing_doc.id,
                    supports_enrichment=True,
                )

        # Handle force mode: cleanup existing data
        if existing_doc and force:
            logger.info(f"Force mode: cleaning up existing content {existing_doc.id}")
            try:
                stmt = select(Persona).where(
                    Persona.user_id == user_id,
                    Persona.persona_name == persona_name,
                    Persona.is_active == True,
                )
                result = await session.execute(stmt)
                temp_persona = result.scalar_one_or_none()

                if temp_persona:
                    await cleanup_document_data(session, existing_doc.id, temp_persona.id)
                else:
                    await cleanup_document_data(session, existing_doc.id)

                # Refresh usage cache after deletion
                usage_cache_service = UsageCacheService(session)
                await usage_cache_service.recalculate_usage_from_source(user_id=user_id)

                await session.commit()
                logger.info(
                    f"Force mode: Successfully deleted content {existing_doc.id} "
                    f"and refreshed usage cache for user {user_id}"
                )
            except Exception as cleanup_error:
                capture_exception_with_context(
                    cleanup_error,
                    extra={
                        "user_id": str(user_id),
                        "title": request.title,
                        "content_length": len(request.content),
                        "existing_doc_id": str(existing_doc.id) if existing_doc else None,
                    },
                    tags={
                        "component": "document_ingestion",
                        "operation": "add_raw_text_cleanup",
                        "severity": "high",
                        "user_facing": "true",
                    },
                )
                await session.rollback()
                logger.error(f"Error during cleanup in force mode: {cleanup_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to add content: Could not cleanup existing content.",
                )

        # ===== TIER LIMIT CHECK =====
        tier_service = TierService(session)
        try:
            logger.info(f"Tier limit check for user {user_id}, content: {request.title}")
            await tier_service.check_document_upload_allowed(
                user_id=user_id,
                file_size_bytes=content_length,
                file_extension=".txt",
                duration_seconds=None,
            )
            logger.info(f"Tier limit check passed for user {user_id}")
        except TierLimitExceeded as e:
            logger.warning(f"Tier limit exceeded for user {user_id}: {e}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        # Find or create persona
        stmt = select(Persona).where(
            Persona.user_id == user_id,
            Persona.persona_name == persona_name,
            Persona.is_active == True,
        )
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            persona = Persona(
                user_id=user_id,
                persona_name=persona_name,
                name=persona_name.title() if persona_name != "default" else "Default Persona",
                description=f"Persona '{persona_name}' for document ingestion",
            )
            session.add(persona)
            await session.flush()
            await session.refresh(persona)
            logger.info(f"Created new persona: {persona_name} for user {user_id}")

        # Generate filename from title (sanitize for file system)
        import re
        import time

        safe_title = re.sub(r"[^\w\s-]", "", request.title)[:50].strip()
        safe_title = re.sub(r"[-\s]+", "-", safe_title)
        timestamp = int(time.time())
        filename = f"{safe_title}-{timestamp}.txt"

        # Upload to S3
        s3_service = get_s3_service()
        await s3_service.ensure_bucket_exists()

        s3_path = await s3_service.upload_file(
            file_content=content_bytes,
            user_id=str(user_id),
            filename=filename,
            content_type="text/plain",
        )
        logger.info(f"Uploaded raw text to S3: {s3_path}")

        # Create document entry
        metadata = {
            "url": s3_path,
            "original_title": request.title,
            "original_filename": filename,
            "content_type": "text/plain",
            "s3_path": s3_path,
            "file_type_category": "text",
            "original_extension": ".txt",
            "checksum": checksum,
            "character_count": len(request.content),
            "is_raw_text_input": True,  # Flag to identify raw text inputs
        }

        try:
            document = Document(
                user_id=user_id,
                document_type="txt",
                filename=filename,
                file_size=content_length,
                document_metadata=metadata,
            )

            session.add(document)
            await session.flush()
            await session.refresh(document)
            logger.info(f"Created document entry: {document.id} for raw text")

            # Create persona_data_source entry
            stmt = select(PersonaDataSource).where(
                PersonaDataSource.persona_id == persona.id,
                PersonaDataSource.source_type == "document",
                PersonaDataSource.source_record_id == document.id,
            )
            result = await session.execute(stmt)
            existing_data_source = result.scalar_one_or_none()

            if not existing_data_source:
                data_source = PersonaDataSource(
                    persona_id=persona.id,
                    source_type="document",  # Using 'document' for text files to match add_document() pattern
                    source_record_id=document.id,
                    enabled=True,
                    source_filters={
                        "document_type": ".txt",
                        "url": s3_path,
                        "file_type_category": "text",
                        "is_raw_text_input": True,
                    },
                )
                session.add(data_source)
                logger.info(f"Created persona_data_source for raw text {document.id}")

                # Update usage cache
                usage_cache_service = UsageCacheService(session)
                await usage_cache_service.increment_usage_optimistic(
                    user_id=user_id,
                    file_extension=".txt",
                    file_size_bytes=content_length,
                    duration_seconds=None,
                )
                logger.info(f"Updated usage cache for user {user_id}")

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "user_id": str(user_id),
                    "title": request.title,
                    "content_length": len(request.content),
                    "s3_path": s3_path,
                },
                tags={
                    "component": "document_ingestion",
                    "operation": "add_raw_text_create_document",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            logger.error(f"Failed to create document: {e}")
            if s3_path:
                try:
                    await s3_service.delete_file(s3_path)
                    logger.info(f"Cleaned up S3 file after failure: {s3_path}")
                except Exception as s3_error:
                    logger.warning(f"Failed to cleanup S3 file {s3_path}: {s3_error}")
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to add content: {str(e)}",
            )

        # Queue processing job
        vp_queue_service = get_voice_processing_queue_service()

        if vp_queue_service:
            try:
                logger.info("Initializing voice processing queue service...")
                await vp_queue_service.initialize()

                import uuid as _uuid

                job_id = _uuid.uuid4()

                success = await vp_queue_service.publish_text_job(
                    user_id=str(user_id),
                    document_id=str(document.id),
                    input_source=s3_path,
                    job_id=str(job_id),
                    persona_id=str(persona.id),
                )

                if not success:
                    logger.error("Failed to queue text processing job")
                    raise Exception("Failed to queue text processing job")

                logger.info(f"Queued text processing job: {job_id}")

                # Commit transaction only after ALL operations succeed
                # (document, data_source, usage_cache, scraping_job, and queue publish)
                await session.commit()
                logger.info(
                    f"Successfully committed transaction: document {document.id}, "
                    f"job {job_id} for user {user_id}"
                )

            except Exception as queue_error:
                capture_exception_with_context(
                    queue_error,
                    extra={
                        "user_id": str(user_id),
                        "title": request.title,
                        "document_id": str(document.id) if document else None,
                        "s3_path": s3_path,
                    },
                    tags={
                        "component": "document_ingestion",
                        "operation": "add_raw_text_queue_job",
                        "severity": "high",
                        "user_facing": "true",
                    },
                )
                logger.error(f"Error queueing processing job: {queue_error}")
                await session.rollback()
                raise
        else:
            logger.error("Voice processing queue service not available")
            raise Exception("Voice processing queue service not available")

        return DocumentResponse(
            success=True,
            message="Text content added and processing job queued successfully",
            document_id=document.id,
            job_id=job_id,
            supports_enrichment=True,
        )

    except HTTPException:
        raise
    except TierLimitExceeded as e:
        logger.error(f"Tier limit exceeded: {e}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user_id),
                "title": request.title,
                "content_length": len(request.content),
                "document_id": str(document.id) if document else None,
                "job_id": str(job_id) if job_id else None,
            },
            tags={
                "component": "document_ingestion",
                "operation": "add_raw_text",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"Unexpected error in add_raw_text: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add content: {type(e).__name__}. Please contact support if this persists.",
        )


@router.post(
    "/process-pdf-data", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
async def process_pdf_data(
    user_id: UUID = Form(..., description="User UUID who owns this document"),
    persona_name: str = Form("default", description="Persona name. Defaults to 'default'"),
    force: bool = Form(False, description="Force re-upload even if document exists"),
    file: UploadFile = File(..., description="PDF file to process"),
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_jwt_or_api_key),
):
    """
    Process PDF file upload for document ingestion with duplicate detection

    This endpoint:
    1. Calculates checksum for duplicate detection
    2. Checks if document already exists by checksum
    3. If exists and force=false: Returns appropriate message
    4. If force=true: Cleans up and re-processes
    5. Validates the uploaded PDF file
    6. Saves the file to S3
    7. Creates a document entry in the database
    8. Creates persona_data_source entry
    9. Queues a PDF processing job for the voice processing worker

    **Authentication:**
    Supports multiple authentication methods:
    - JWT token (via myclone_token cookie) - for authenticated users
    - Widget token (via Bearer token starting with wgt_)
    - API key (via Bearer token or X-API-Key header)

    **Authorization:**
    - JWT users can only upload documents for themselves (user_id must match authenticated user)
    - API key/Widget token users can upload for any user

    Parameters:
        user_id: The UUID of the user who owns this document
        persona_name: The name of the persona (defaults to "default")
        force: Force re-upload and re-process even if document exists
        file: The PDF file to upload and process
    """
    try:
        # Authorization: If JWT authenticated, ensure user can only upload for themselves
        auth_type = auth_result.get("type")
        if auth_type == "jwt":
            authenticated_user = auth_result.get("data", {}).get("user")
            if authenticated_user and str(authenticated_user.id) != str(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only upload documents for yourself",
                )

        logger.info(
            f"Processing PDF upload for user {user_id}, persona: {persona_name}, "
            f"file: {file.filename}, force: {force}"
        )

        # Read file content first for validation and checksum
        content = await file.read()
        await file.seek(0)  # Reset file pointer

        # ===== TIER LIMIT CHECK =====
        # Check tier limits BEFORE processing to fail fast
        tier_service = TierService(session)
        try:
            file_extension = Path(file.filename).suffix or ".pdf"
            await tier_service.check_document_upload_allowed(
                user_id=user_id,
                file_size_bytes=len(content),
                file_extension=file_extension,
                duration_seconds=None,  # PDFs don't have duration
            )
        except TierLimitExceeded as e:
            logger.warning(f"Tier limit exceeded for user {user_id}: {e}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        # Calculate checksum for duplicate detection
        checksum = calculate_file_checksum(content)
        logger.info(
            f"Calculated file checksum: {checksum} for user {user_id}. "
            f"Checking for duplicates within this user's documents only."
        )

        # Check if document already exists by checksum FOR THIS USER
        existing_doc, has_embeddings = await check_document_dependency(session, user_id, checksum)

        if existing_doc and not force:
            # Document exists and force mode is not enabled
            if has_embeddings:
                # Case 1: Document and embeddings both exist
                logger.info(
                    f"Duplicate PDF found for user {user_id}: {existing_doc.id} with embeddings. "
                    f"File: {existing_doc.filename}, Checksum: {checksum}"
                )
                return DocumentResponse(
                    success=False,
                    message=(
                        f"You have already uploaded this PDF file. "
                        f"Document already exists with embeddings. "
                        f"Use force=true to re-upload and re-process. "
                        f"Document ID: {existing_doc.id}"
                    ),
                    document_id=existing_doc.id,
                    supports_enrichment=True,
                )
            else:
                # Case 2: Document exists but embeddings are missing
                logger.info(
                    f"PDF document found for user {user_id}: {existing_doc.id} but embeddings missing. "
                    f"File: {existing_doc.filename}, Checksum: {checksum}"
                )
                return DocumentResponse(
                    success=False,
                    message=(
                        f"You have already uploaded this PDF file but embeddings are missing. "
                        f"Use the /refresh endpoint to regenerate embeddings. "
                        f"Document ID: {existing_doc.id}"
                    ),
                    document_id=existing_doc.id,
                    supports_enrichment=True,
                )

        # Handle force mode: cleanup existing data
        if existing_doc and force:
            logger.info(f"Force mode: cleaning up existing PDF document {existing_doc.id}")
            # Get persona first to pass to cleanup
            stmt = select(Persona).where(
                Persona.user_id == user_id,
                Persona.persona_name == persona_name,
                Persona.is_active == True,
            )
            result = await session.execute(stmt)
            temp_persona = result.scalar_one_or_none()
            if temp_persona:
                await cleanup_document_data(session, existing_doc.id, temp_persona.id)
            else:
                await cleanup_document_data(session, existing_doc.id)

        # Validate file size
        if len(content) > settings.max_pdf_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size allowed is {settings.max_pdf_file_size // (1024 * 1024)}MB",
            )

        # Validate file type using filename extension
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file extension: {file.filename}. Only PDF files are supported",
            )

        # Validate PDF content using magic bytes
        if not content[:5] == b"%PDF-":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid PDF file format. File '{file.filename}' does not contain valid PDF content",
            )

        # Find or create persona by user_id and persona_name
        stmt = select(Persona).where(
            Persona.user_id == user_id,
            Persona.persona_name == persona_name,
            Persona.is_active == True,
        )
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            # Create persona if it doesn't exist
            persona = Persona(
                user_id=user_id,
                persona_name=persona_name,
                name=persona_name.title() if persona_name != "default" else "Default Persona",
                description=f"Persona '{persona_name}' for document ingestion",
            )
            session.add(persona)
            await session.flush()
            await session.refresh(persona)
            logger.info(f"Created new persona: {persona_name} for user {user_id}")

        # Upload file to S3
        s3_service = get_s3_service()

        # Ensure bucket exists
        await s3_service.ensure_bucket_exists()

        # Upload to S3: bucket-name/user-id/filename
        s3_path = await s3_service.upload_file(
            file_content=content,
            user_id=str(user_id),
            filename=file.filename,
            content_type=SUPPORTED_DOCUMENT_TYPES[".pdf"],
        )
        logger.info(f"Uploaded PDF to S3: {s3_path}")

        # Extract PDF metadata (page count) using pypdf
        page_count = 1  # Default fallback
        try:
            import io

            from pypdf import PdfReader

            # Read PDF directly from bytes (no temp file needed)
            pdf_reader = PdfReader(io.BytesIO(content))
            page_count = len(pdf_reader.pages)

            logger.info(f"Extracted page count from PDF: {page_count} pages")

        except ImportError:
            logger.warning("pypdf library not available, using default page count: 1")
            page_count = 1
        except Exception as e:
            logger.warning(f"Failed to extract page count from PDF, using default: {e}")
            page_count = 1

        # Create document entry
        document = Document(
            user_id=user_id,
            document_type="pdf",
            filename=file.filename,
            file_size=len(content),
            document_metadata={
                "url": s3_path,
                "original_filename": file.filename,
                "content_type": SUPPORTED_DOCUMENT_TYPES[".pdf"],
                "s3_path": s3_path,
                "page_count": page_count,
                "checksum": checksum,  # Store checksum for duplicate detection
            },
        )
        session.add(document)
        await session.flush()
        await session.refresh(document)
        logger.info(f"Created document entry: {document.id} with {page_count} pages")

        # Create persona_data_source entry
        stmt = select(PersonaDataSource).where(
            PersonaDataSource.persona_id == persona.id,
            PersonaDataSource.source_type == "document",
            PersonaDataSource.source_record_id == document.id,
        )
        result = await session.execute(stmt)
        existing_data_source = result.scalar_one_or_none()

        if not existing_data_source:
            data_source = PersonaDataSource(
                persona_id=persona.id,
                source_type="pdf",
                source_record_id=document.id,
                enabled=True,
                source_filters={
                    "document_type": ".pdf",
                    "url": s3_path,
                },
            )
            session.add(data_source)
            logger.info(f"Created persona_data_source for uploaded PDF {document.id}")

        await session.commit()

        # Get voice processing queue service
        vp_queue_service = get_voice_processing_queue_service()
        job_id = None

        if vp_queue_service:
            try:
                # Always initialize the queue service before use
                logger.info("Initializing voice processing queue service...")
                await vp_queue_service.initialize()
                logger.info("Voice processing queue service initialized successfully")

                import uuid as _uuid

                job_id = _uuid.uuid4()

                # Queue PDF processing job for voice processing worker with S3 path
                success = await vp_queue_service.publish_pdf_job(
                    user_id=str(user_id),
                    document_id=str(document.id),
                    input_source=s3_path,
                    job_id=str(job_id),
                    persona_id=str(persona.id),  # ✅ FIXED: Always pass persona_id (never None)
                )

                if success:
                    logger.info(f"Queued PDF processing job for voice processing worker: {job_id}")
                else:
                    logger.error("Failed to queue PDF processing job")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to queue PDF processing job",
                    )

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error initializing voice processing queue or publishing job: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to process PDF data: {str(e)}",
                )
        else:
            logger.warning("Voice processing queue service not available, PDF job not queued")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Voice processing queue service not available",
            )

        return DocumentResponse(
            success=True,
            message="PDF file uploaded and processing job queued successfully",
            document_id=document.id,
            job_id=job_id,
            supports_enrichment=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process PDF data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process PDF data: {str(e)}",
        )


@router.post("/refresh", response_model=DocumentResponse, status_code=status.HTTP_200_OK)
async def refresh_document_embeddings(
    user_id: UUID = Form(..., description="User UUID who owns this document"),
    document_id: UUID = Form(..., description="Document UUID to refresh"),
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_jwt_or_api_key),
):
    """
    Refresh embeddings for an existing document

    This endpoint:
    1. Validates the document exists
    2. Deletes existing embeddings for the document
    3. Re-processes the document to generate new embeddings

    **Authentication:**
    Supports multiple authentication methods:
    - JWT token (via myclone_token cookie) - for authenticated users
    - Widget token (via Bearer token starting with wgt_)
    - API key (via Bearer token or X-API-Key header)

    **Authorization:**
    - JWT users can only refresh documents for themselves (user_id must match authenticated user)
    - API key/Widget token users can refresh for any user

    Parameters:
        user_id: The UUID of the user who owns this document
        document_id: The UUID of the document to refresh
    """
    try:
        # Authorization: If JWT authenticated, ensure user can only refresh their own documents
        auth_type = auth_result.get("type")
        if auth_type == "jwt":
            authenticated_user = auth_result.get("data", {}).get("user")
            if authenticated_user and str(authenticated_user.id) != str(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only refresh your own documents",
                )

        logger.info(f"Refreshing embeddings for document {document_id} by user {user_id}")

        # First check if document exists at all
        stmt = select(Document).where(Document.id == document_id)
        result = await session.execute(stmt)
        document = result.scalar_one_or_none()

        if not document:
            logger.warning(f"Document {document_id} not found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found",
            )

        # Then verify it belongs to the user
        if document.user_id != user_id:
            logger.warning(
                f"Document {document_id} exists but belongs to user {document.user_id}, "
                f"not user {user_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Document {document_id} does not belong to user {user_id}",
            )

        logger.info(
            f"Document {document_id} verified for user {user_id}. "
            f"Filename: {document.filename}, Type: {document.document_type}"
        )

        # Start transaction for embedding deletion
        try:
            # Delete existing embeddings
            deleted_count = await delete_document_embeddings(session, document_id)
            logger.info(f"Deleted {deleted_count} existing embeddings for document {document_id}")

            # Don't commit yet - wait until job is successfully queued
            await session.flush()  # Flush to detect any DB errors but don't commit

            # Re-process the document to generate new embeddings
            # Re-use the existing file URL in S3 for processing
            file_url = document.document_metadata.get("url")

            if not file_url:
                logger.error(
                    f"Document {document_id} missing 'url' in metadata: {document.document_metadata}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing file URL in document metadata",
                )

            logger.info(f"Document file URL: {file_url}")

            # Get voice processing queue service
            vp_queue_service = get_voice_processing_queue_service()
            if not vp_queue_service:
                logger.error("Voice processing queue service not available")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Voice processing queue service not available",
                )

            # Determine file type based on URL extension
            file_ext = Path(file_url).suffix.lower()
            logger.info(f"Document file extension: {file_ext}")

            # Get file type category and persona_id from metadata
            file_type_category = document.document_metadata.get("file_type_category", "pdf")
            logger.info(f"Document file type category: {file_type_category}")

            # Find persona for this document
            stmt = select(PersonaDataSource).where(
                PersonaDataSource.source_record_id == document.id
            )
            result = await session.execute(stmt)
            data_source = result.scalar_one_or_none()

            if not data_source:
                logger.error(f"No persona_data_source found for document {document_id}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No persona data source found for this document",
                )

            logger.info(
                f"Found persona_data_source: persona_id={data_source.persona_id}, source_type={data_source.source_type}"
            )
            # Only commit the transaction after job is successfully queued
            await session.commit()

            # Initialize queue service
            logger.info("Initializing voice processing queue service...")
            await vp_queue_service.initialize()
            logger.info("Voice processing queue service initialized successfully")

            import uuid as _uuid

            job_id = _uuid.uuid4()
            logger.info(f"Created job {job_id} for document refresh")

            # Queue appropriate job based on file type
            success = False
            if file_ext == ".pdf":
                # Queue PDF processing job
                logger.info(f"Queueing PDF processing job for document {document_id}")
                success = await vp_queue_service.publish_pdf_job(
                    user_id=str(user_id),
                    document_id=str(document.id),
                    input_source=file_url,
                    job_id=str(job_id),
                    persona_id=str(data_source.persona_id),
                )
            elif file_ext in [".docx", ".pptx", ".xlsx"]:
                # Queue office document processing job (uses same PDF pipeline with Marker API)
                logger.info(f"Queueing office document processing job for document {document_id}")
                success = await vp_queue_service.publish_pdf_job(
                    user_id=str(user_id),
                    document_id=str(document.id),
                    input_source=file_url,
                    job_id=str(job_id),
                    persona_id=str(data_source.persona_id),
                )
            elif file_ext in [".mp3", ".wav", ".m4a"]:
                # Queue audio processing job
                logger.info(f"Queueing audio processing job for document {document_id}")
                success = await vp_queue_service.publish_audio_job(
                    user_id=str(user_id),
                    document_id=str(document.id),
                    input_source=file_url,
                    job_id=str(job_id),
                    persona_id=str(data_source.persona_id),
                )
            elif file_ext in [".mp4", ".mov", ".avi", ".mkv"]:
                # Queue video processing job
                logger.info(f"Queueing video processing job for document {document_id}")
                success = await vp_queue_service.publish_video_job(
                    user_id=str(user_id),
                    document_id=str(document.id),
                    input_source=file_url,
                    job_id=str(job_id),
                    persona_id=str(data_source.persona_id),
                )
            elif file_ext in [".txt", ".md"]:
                # Queue text processing job for .txt and .md files
                logger.info(f"Queueing text processing job for document {document_id}")
                success = await vp_queue_service.publish_text_job(
                    user_id=str(user_id),
                    document_id=str(document.id),
                    input_source=file_url,
                    job_id=str(job_id),
                    persona_id=str(data_source.persona_id),
                )
            else:
                logger.error(f"Unsupported file type: {file_ext}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file type: {file_ext}. Supported types: .pdf, .docx, .pptx, .xlsx, .mp3, .wav, .m4a, .mp4, .mov, .avi, .mkv, .txt, .md. Cannot refresh embeddings",
                )

            if not success:
                logger.error(f"Failed to queue {file_type_category} refresh job")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to queue {file_type_category} refresh job",
                )

            logger.info(f"Successfully queued refresh job {job_id} for document {document_id}")

            return DocumentResponse(
                success=True,
                message="Document embeddings refresh initiated",
                document_id=document_id,
                job_id=job_id,
            )

        except Exception as e:
            # Rollback the transaction to restore embeddings
            await session.rollback()
            logger.error(f"Failed to refresh document embeddings, rolled back transaction: {e}")
            raise

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh document embeddings: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh document embeddings: {str(e)}",
        )


@router.get("/{user_id}", response_model=DocumentListResponse)
async def get_user_documents(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(require_api_key),
):
    """Retrieve all documents for a user"""
    try:
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.uploaded_at.desc())
        )
        result = await session.execute(stmt)
        documents = result.scalars().all()

        document_list = []
        for doc in documents:
            document_list.append(
                DocumentInfo(
                    id=doc.id,
                    filename=doc.filename,
                    document_type=f".{doc.document_type}",
                    file_size=doc.file_size,
                    uploaded_at=doc.uploaded_at.isoformat(),
                    metadata=doc.document_metadata,
                )
            )

        return DocumentListResponse(
            documents=document_list,
            total_count=len(document_list),
        )

    except Exception as e:
        logger.error(f"Failed to retrieve documents for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve documents: {str(e)}",
        )


@router.delete("/{document_id}", response_model=DocumentResponse)
async def delete_document(
    document_id: UUID,
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(require_api_key),
):
    """
    Delete a document and its associated data

    This endpoint performs a comprehensive deletion of a document and all related data:
    1. Verifies the document exists and belongs to the specified user_id
    2. Checks for associated PersonaDataSource entries
    3. Checks for embeddings in data_llamalite_embeddings table using source_record_id
    4. Deletes all data in a single transaction:
       - Document record from documents table
       - Related PersonaDataSource entries from persona_data_source table
       - Related embeddings from data_llamalite_embeddings table
    5. **Refreshes usage cache from Documents table to ensure accurate limits**
    6. **All operations in single transaction - rollback on any failure**

    Note: No CASCADE DELETE is configured, so all related data must be manually deleted.
    The embeddings are linked via source_record_id field, not metadata_->>'document_id'.

    Parameters:
        document_id: UUID of the document to delete
        user_id: UUID of the user who owns the document

    Returns:
        DocumentResponse with success status and details about what was deleted
    """
    try:
        # ===== START TRANSACTION FOR DELETE + USAGE CACHE REFRESH =====
        # First verify the document exists and belongs to the user
        stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await session.execute(stmt)
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found or does not belong to user {user_id}",
            )

        # Store document info for logging before deletion
        doc_filename = document.filename

        # Check for associated persona_data_source entries
        # Note: source_type can be either "document" or "pdf" depending on the file type
        stmt = select(PersonaDataSource).where(
            PersonaDataSource.source_record_id == document_id,
        )
        result = await session.execute(stmt)
        data_sources = result.scalars().all()

        # Check for embeddings in data_llamalite_embeddings table using source_record_id
        # (more reliable than metadata)
        stmt = select(VoyageLiteEmbedding).where(
            VoyageLiteEmbedding.source_record_id == document_id
        )
        result = await session.execute(stmt)
        embeddings = result.scalars().all()
        embeddings_count = len(embeddings)

        logger.info(
            f"Deleting document {document_id} for user {user_id}: "
            f"Found {len(data_sources)} persona_data_source entries and {embeddings_count} data_llamalite_embeddings"
        )

        # Delete all data in a single transaction

        # 1. Delete embeddings from data_llamalite_embeddings table using source_record_id
        if embeddings_count > 0:
            for embedding in embeddings:
                await session.delete(embedding)
            logger.info(
                f"Deleted {embeddings_count} embeddings from data_llamalite_embeddings for document {document_id}"
            )

        # 2. Delete PersonaDataSource entries
        for data_source in data_sources:
            await session.delete(data_source)
        logger.info(
            f"Deleted {len(data_sources)} persona_data_source entries for document {document_id}"
        )

        # 3. Delete the document
        await session.delete(document)
        logger.info(f"Deleted document {document_id}")

        # Flush deletions to database but don't commit yet
        await session.flush()

        # ===== REFRESH USAGE CACHE AFTER DELETION =====
        # Recalculate usage from Documents table to ensure accurate limits
        # This is done within the same transaction to prevent race conditions
        usage_cache_service = UsageCacheService(session)
        await usage_cache_service.recalculate_usage_from_source(user_id=user_id)
        logger.info(
            f"Refreshed usage cache for user {user_id} after deleting document {document_id}"
        )
        # ===== END USAGE CACHE REFRESH =====

        # Commit all deletions and cache refresh in a single transaction
        await session.commit()

        logger.info(
            f"Successfully deleted document {document_id} ({doc_filename}) with {len(data_sources)} persona_data_source entries "
            f"and {embeddings_count} data_llamalite_embeddings for user {user_id}. Usage cache refreshed."
        )

        return DocumentResponse(
            success=True,
            message=f"Document deleted successfully (including {len(data_sources)} data sources and {embeddings_count} embeddings). Usage limits updated.",
            document_id=document_id,
        )
        # ===== END TRANSACTION =====

    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error(
            f"Failed to delete document {document_id} for user {user_id}, rolled back transaction: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}",
        )


@router.get("/check-embeddings/{user_id}/{document_id}")
async def check_document_has_embeddings(
    user_id: UUID,
    document_id: UUID,
    session: AsyncSession = Depends(get_session),
    api_key: str = Depends(require_api_key),
):
    """
    Check if a document has embeddings

    This endpoint checks whether the specified document has any embeddings
    stored in the data_llamalite_embeddings table.

    Parameters:
        user_id: The UUID of the user who owns the document
        document_id: The UUID of the document to check

    Returns:
        {
            "has_embeddings": true/false,
            "document_id": "uuid-string",
            "user_id": "uuid-string",
            "document_exists": true/false
        }
    """
    try:
        # First verify the document exists and belongs to the user
        stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await session.execute(stmt)
        document = result.scalar_one_or_none()

        if not document:
            logger.warning(f"Document {document_id} not found or does not belong to user {user_id}")
            return {
                "has_embeddings": False,
                "document_id": str(document_id),
                "user_id": str(user_id),
                "document_exists": False,
            }

        # Check if embeddings exist in data_llamalite_embeddings table
        # Embeddings are linked via source_record_id (consistent with delete and cleanup operations)
        embedding_check = await session.execute(
            select(VoyageLiteEmbedding.id)
            .where(VoyageLiteEmbedding.source_record_id == document_id)
            .limit(1)
        )
        has_embeddings = embedding_check.scalar_one_or_none() is not None

        logger.info(
            f"Embedding check for document {document_id} (user {user_id}): "
            f"has_embeddings={has_embeddings}"
        )

        return {
            "has_embeddings": bool(has_embeddings),
            "document_id": str(document_id),
            "user_id": str(user_id),
            "document_exists": True,
        }

    except Exception as e:
        logger.error(f"Failed to check embeddings for document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check document embeddings: {str(e)}",
        )
