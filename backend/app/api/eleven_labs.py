import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Union
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_auth import get_user_or_service
from app.services.elevenlabs_service import ElevenLabsService
from shared.config import settings
from shared.database.models.database import get_session
from shared.database.models.user import User
from shared.database.repositories.persona_repository import PersonaRepository
from shared.database.repositories.voice_clone_repository import VoiceCloneRepository
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.s3_utils import get_s3_client
from shared.schemas.voice_clone import VoiceCloneListItem
from shared.services.s3_service import create_s3_service
from shared.services.voice_clone_service import check_voice_clone_limit
from shared.utils.audio_conversion import convert_to_wav, needs_conversion

router = APIRouter(prefix="/api/v1/eleven_labs", tags=["eleven_labs"])
logger = logging.getLogger(__name__)


class VoiceCloneRequest(BaseModel):
    name: str
    description: Optional[str] = None
    remove_background_noise: bool = True


class VoiceCloneFromPathsRequest(BaseModel):
    name: str
    description: Optional[str] = None
    remove_background_noise: bool = True
    file_paths: List[str]


class VoiceCloneFromS3Request(BaseModel):
    """Request model for creating voice clone from S3 URIs (voice processing job outputs)."""

    user_id: UUID
    name: str
    description: Optional[str] = None
    remove_background_noise: bool = True
    s3_uris: List[str]
    source_job_id: Optional[str] = None  # Link to originating voice processing job


class VoiceCloneResponse(BaseModel):
    voice_id: str
    name: str
    status: str
    message: str
    components: Optional[dict] = None  # For 207 Multi-Status responses


@router.post("/create_voice_clone", response_model=VoiceCloneResponse)
async def create_voice_clone(
    user_id: UUID = Form(..., description="User ID who owns this voice clone"),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    remove_background_noise: bool = Form(True),
    files: List[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a voice clone using ElevenLabs IVC API and store samples in S3

    - **user_id**: User ID who owns this voice clone (required)
    - **name**: Name for the voice clone (required)
    - **description**: Optional description for the voice
    - **remove_background_noise**: Whether to remove background noise (default: True)
    - **files**: Audio files for voice cloning (1-5 files, max 10MB each)

    Voice clone limits are enforced based on user's subscription tier:
    - Free: 1 voice clone
    - Pro: 1 voice clone
    - Business: 3 voice clones
    - Enterprise: Unlimited
    """
    try:
        # Check voice clone limit based on user's tier
        can_create, current_count, max_allowed = await check_voice_clone_limit(session, user_id)
        if not can_create:
            raise HTTPException(
                status_code=400,
                detail=f"Voice clone limit reached. You have {current_count}/{max_allowed} voice clones. "
                f"Please delete an existing voice clone or upgrade your plan.",
            )

        # Basic input validation
        if not name or not name.strip():
            raise HTTPException(status_code=400, detail="Voice name is required")

        if not files or len(files) == 0:
            raise HTTPException(status_code=400, detail="At least one audio file is required")

        if len(files) > 5:
            raise HTTPException(status_code=400, detail="Maximum 5 files allowed")

        # Get S3 service with voiceclone directory prefix
        s3_service = create_s3_service(directory="voiceclone")

        # Read files, upload to S3, and prepare tuples for ElevenLabs
        file_tuples: List[Tuple[str, bytes]] = []
        s3_uploaded_files = []
        total_size_bytes = 0
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        for idx, file in enumerate(files):
            content = await file.read()
            original_filename = file.filename
            original_size = len(content)

            # Convert to WAV if needed (WebM, OGG, etc.)
            if needs_conversion(file.filename):
                logger.info(
                    f"Converting {file.filename} to WAV format for ElevenLabs compatibility"
                )
                try:
                    content, file.filename = await convert_to_wav(content, file.filename)
                    logger.info(
                        f"✅ Conversion successful: {original_filename} → {file.filename} "
                        f"({original_size} bytes → {len(content)} bytes)"
                    )
                except ValueError as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Audio conversion failed for {original_filename}: {str(e)}",
                    )

            file_size = len(content)
            total_size_bytes += file_size

            # Generate S3 filename with timestamp to prevent collisions
            s3_filename = f"{timestamp}_{idx+1}_{file.filename}"

            # Upload to S3: voiceclone/{user_id}/{timestamp}_{filename}
            s3_path = await s3_service.upload_file(
                file_content=content,
                user_id=str(user_id),
                filename=s3_filename,
                content_type="audio/wav",  # Always WAV after conversion
            )

            # Track S3 upload metadata
            s3_uploaded_files.append(
                {
                    "s3_path": s3_path,
                    "original_filename": original_filename,
                    "converted_filename": (
                        file.filename if needs_conversion(original_filename) else None
                    ),
                    "s3_filename": s3_filename,
                    "file_size_bytes": file_size,
                    "content_type": "audio/wav",
                    "uploaded_at": datetime.now(timezone.utc).isoformat(),
                }
            )

            # Prepare tuple for ElevenLabs API
            file_tuples.append((file.filename, content))
            logger.info(f"Uploaded to S3: {s3_path} ({file_size} bytes)")

        # Step 1: Create voice clone via ElevenLabs API
        elevenlabs_service = ElevenLabsService()
        result = elevenlabs_service.create_voice_clone(
            name=name.strip(),
            files=file_tuples,
            description=description,
            remove_background_noise=remove_background_noise,
        )

        voice_id = result.get("voice_id", "unknown")
        logger.info(f"Voice clone created in ElevenLabs: {name} (voice_id: {voice_id})")

        # Step 2: Save voice clone metadata to database
        db_saved = False
        try:
            await VoiceCloneRepository.create(
                session=session,
                user_id=user_id,
                voice_id=voice_id,
                name=name.strip(),
                description=description,
                sample_files=s3_uploaded_files,
                settings={
                    "remove_background_noise": remove_background_noise,
                    "provider": "elevenlabs",
                },
                total_files=len(s3_uploaded_files),
                total_size_bytes=total_size_bytes,
            )
            logger.info(f"Saved voice clone metadata to database (voice_id: {voice_id})")
            db_saved = True
        except Exception as db_error:
            logger.error(f"Failed to save voice clone to database: {db_error}")
            logger.warning(
                f"OPERATOR ALERT: Voice clone created (voice_id: {voice_id}) but DB save failed. "
                f"Manual reconciliation required for user_id: {user_id}"
            )
            # Capture in Sentry for monitoring and alerting
            capture_exception_with_context(
                db_error,
                extra={
                    "user_id": str(user_id),
                    "voice_id": voice_id,
                    "voice_name": name,
                    "files_count": len(s3_uploaded_files),
                    "s3_files": s3_uploaded_files,
                },
                tags={
                    "component": "elevenlabs",
                    "operation": "create_voice_clone",
                    "severity": "critical",
                    "user_facing": "true",
                },
            )

        # Return 207 Multi-Status if database save failed
        if not db_saved:
            return VoiceCloneResponse(
                voice_id=voice_id,
                name=name,
                status="partial_success",
                message="Voice clone created successfully, but there was an issue saving metadata. Please contact support if you experience any issues.",
                components={
                    "s3_upload": {"status": "success", "files_count": len(s3_uploaded_files)},
                    "elevenlabs_api": {"status": "success", "voice_id": voice_id},
                    "database_save": {"status": "failed"},
                },
            )

        return VoiceCloneResponse(
            voice_id=voice_id,
            name=name,
            status="success",
            message=f"Voice clone created successfully with {len(files)} sample(s) stored in S3",
            components={
                "s3_upload": {"status": "success", "files_count": len(s3_uploaded_files)},
                "elevenlabs_api": {"status": "success", "voice_id": voice_id},
                "database_save": {"status": "success"},
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create voice clone: {str(e)}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user_id),
                "voice_name": name,
                "files_count": len(files) if files else 0,
            },
            tags={
                "component": "elevenlabs",
                "operation": "create_voice_clone",
                "severity": "high",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/create_voice_clone_from_paths")
async def create_voice_clone_from_paths(voice_data: VoiceCloneFromPathsRequest):
    """
    Create a voice clone from existing file paths (for internal use)

    - **name**: Name for the voice clone
    - **description**: Optional description for the voice
    - **remove_background_noise**: Whether to remove background noise
    - **file_paths**: List of file paths to audio files
    """
    try:
        # Validate file paths
        for file_path in voice_data.file_paths:
            if not os.path.exists(file_path):
                raise HTTPException(status_code=400, detail=f"File not found: {file_path}")

        # Create voice clone via ElevenLabs API (no DB save for internal endpoint)
        elevenlabs_service = ElevenLabsService()
        result = elevenlabs_service.create_voice_clone(
            name=voice_data.name,
            files=voice_data.file_paths,
            description=voice_data.description,
            remove_background_noise=voice_data.remove_background_noise,
        )

        return VoiceCloneResponse(
            voice_id=result.get("voice_id", "unknown"),
            name=voice_data.name,
            status="success",
            message="Voice clone created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create voice clone from paths: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/create_voice_clone_from_s3", response_model=VoiceCloneResponse)
async def create_voice_clone_from_s3(
    voice_data: VoiceCloneFromS3Request,
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """
    Create a voice clone from S3 URIs (typically from voice processing job outputs).

    **Authentication**:
    - Users: JWT cookie (can only create voice clones for themselves)
    - Operators: X-API-Key header (can create for any user)

    **Workflow**:
    1. Download voice segments from S3 (voice-processing/output/segments/...)
    2. Copy to permanent storage (voiceclone/...)
    3. Create ElevenLabs voice clone
    4. Save metadata to database with audit trail

    **Typical Usage**:
    1. POST /voice-processing/jobs with multiple_segments=true (extract segments from podcast/video)
    2. GET /voice-processing/jobs/{job_id} (get S3 URIs of segments)
    3. POST /create_voice_clone_from_s3 (create voice clone from those segments)

    **Storage Strategy**:
    - Source files (voice-processing/output/): Temporary, can be deleted after 30-90 days
    - Voice clone files (voiceclone/): Permanent, kept for audit/retraining

    Args:
        voice_data: Request containing S3 URIs, name, and settings
        session: Database session
        auth: User (JWT) or "service" (API key)

    Returns:
        VoiceCloneResponse with voice_id and status

    Raises:
        HTTPException: 400 for validation errors, 403 for authorization errors, 500 for processing errors
    """
    try:
        # Authorization check
        if isinstance(auth, User):
            # User JWT auth - verify ownership
            if auth.id != voice_data.user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only create voice clones for yourself",
                )
            logger.info(f"User {auth.id} creating voice clone from S3 URIs for themselves")
        else:
            # Service/operator auth - can act on behalf of any user
            logger.info(
                f"Service account creating voice clone from S3 URIs for user {voice_data.user_id}"
            )

        # Check voice clone limit based on user's tier
        can_create, current_count, max_allowed = await check_voice_clone_limit(
            session, voice_data.user_id
        )
        if not can_create:
            raise HTTPException(
                status_code=400,
                detail=f"Voice clone limit reached. You have {current_count}/{max_allowed} voice clones. "
                f"Please delete an existing voice clone or upgrade your plan.",
            )

        # Input validation
        if not voice_data.s3_uris or len(voice_data.s3_uris) == 0:
            raise HTTPException(status_code=400, detail="At least one S3 URI is required")

        if len(voice_data.s3_uris) > 5:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum 5 files allowed, received {len(voice_data.s3_uris)}",
            )

        if not voice_data.name or not voice_data.name.strip():
            raise HTTPException(status_code=400, detail="Voice name is required")

        # Validate S3 URIs format
        for s3_uri in voice_data.s3_uris:
            if not s3_uri.startswith("s3://"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid S3 URI format: {s3_uri}. Must start with s3://",
                )

        logger.info(
            f"Creating voice clone from {len(voice_data.s3_uris)} S3 URIs for user {voice_data.user_id}"
        )

        # Initialize S3 client for operations
        s3_client = get_s3_client(bucket_name=settings.user_data_bucket, region=settings.aws_region)

        # Prepare for processing
        file_tuples: List[Tuple[str, bytes]] = []
        voiceclone_s3_files = []
        total_size_bytes = 0
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Process each S3 URI
        for idx, s3_uri in enumerate(voice_data.s3_uris):
            # Parse S3 URI to get source key and filename
            if not s3_uri.startswith("s3://"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid S3 URI format: {s3_uri}",
                )

            # Extract key from URI: s3://bucket/key -> key
            uri_parts = s3_uri[5:].split("/", 1)
            if len(uri_parts) != 2:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid S3 URI format: {s3_uri}",
                )

            source_bucket, source_key = uri_parts
            filename = Path(source_key).name
            original_filename = filename

            # Security: Validate S3 path access (prevent cross-user access)
            # Only allow access to user's own voice-processing outputs
            expected_prefix = f"voice-processing/output/{voice_data.user_id}/"
            if not source_key.startswith(expected_prefix):
                logger.warning(
                    f"Access denied: User {voice_data.user_id} attempted to access {source_key}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied: S3 URI must be from your voice processing outputs "
                    f"(expected path: {expected_prefix}...)",
                )

            # Generate destination key for permanent storage
            s3_filename = f"{timestamp}_{idx+1}_{original_filename}"
            dest_key = f"voiceclone/{voice_data.user_id}/{s3_filename}"

            logger.info(f"Processing file {idx+1}/{len(voice_data.s3_uris)}: {original_filename}")

            # Step 1: Server-side S3 copy (instant, no download/upload)
            logger.info(f"Copying to permanent storage (server-side): {source_key} -> {dest_key}")

            try:
                voiceclone_s3_path = await s3_client.copy_from_uri(
                    source_uri=s3_uri,
                    dest_key=dest_key,
                    content_type="audio/wav",
                )
                logger.info(f"✓ Server-side copy completed: {voiceclone_s3_path}")

            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f"Failed to copy {s3_uri}: {e}")
                capture_exception_with_context(
                    e,
                    extra={
                        "user_id": str(voice_data.user_id),
                        "s3_uri": s3_uri,
                        "source_key": source_key,
                        "dest_key": dest_key,
                        "file_index": idx + 1,
                        "total_files": len(voice_data.s3_uris),
                    },
                    tags={
                        "component": "elevenlabs",
                        "operation": "create_voice_clone_from_s3",
                        "severity": "high",
                        "user_facing": "true",
                    },
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to copy file from S3: {s3_uri}. Error: {str(e)}",
                )

            # Step 2: Download file content (only once, for ElevenLabs)
            logger.info(f"Downloading content for ElevenLabs: {original_filename}")

            try:
                content = await s3_client.download_to_bytes(s3_uri)
                file_size = len(content)
                total_size_bytes += file_size

                logger.info(f"✓ Downloaded {original_filename} ({file_size} bytes)")

            except Exception as e:
                logger.error(f"Failed to download {s3_uri}: {e}")
                capture_exception_with_context(
                    e,
                    extra={
                        "user_id": str(voice_data.user_id),
                        "s3_uri": s3_uri,
                        "file_index": idx + 1,
                        "total_files": len(voice_data.s3_uris),
                    },
                    tags={
                        "component": "elevenlabs",
                        "operation": "create_voice_clone_from_s3",
                        "severity": "high",
                        "user_facing": "true",
                    },
                )
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to download file from S3: {s3_uri}. Error: {str(e)}",
                )

            # Track permanent S3 paths for database
            voiceclone_s3_files.append(
                {
                    "s3_path": voiceclone_s3_path,
                    "original_filename": original_filename,
                    "s3_filename": s3_filename,
                    "file_size_bytes": file_size,
                    "content_type": "audio/wav",
                    "uploaded_at": datetime.now(timezone.utc).isoformat(),
                    "source_s3_uri": s3_uri,
                    "source_job_id": voice_data.source_job_id,
                }
            )

            # Prepare tuple for ElevenLabs API
            file_tuples.append((original_filename, content))

        # Step 3: Create voice clone via ElevenLabs API
        logger.info(f"Creating voice clone in ElevenLabs: {voice_data.name}")

        elevenlabs_service = ElevenLabsService()
        result = elevenlabs_service.create_voice_clone(
            name=voice_data.name.strip(),
            files=file_tuples,
            description=voice_data.description,
            remove_background_noise=voice_data.remove_background_noise,
        )

        voice_id = result.get("voice_id", "unknown")
        logger.info(
            f"✓ Voice clone created in ElevenLabs: {voice_data.name} (voice_id: {voice_id})"
        )

        # Step 4: Save voice clone metadata to database
        # CRITICAL: Database save is mandatory - fail loudly if it fails to prevent data inconsistency
        try:
            await VoiceCloneRepository.create(
                session=session,
                user_id=voice_data.user_id,
                voice_id=voice_id,
                name=voice_data.name.strip(),
                description=voice_data.description,
                sample_files=voiceclone_s3_files,  # Permanent voiceclone/ paths
                settings={
                    "remove_background_noise": voice_data.remove_background_noise,
                    "source_job_id": voice_data.source_job_id,
                    "created_from": "s3_uris",
                    "provider": "elevenlabs",
                },
                total_files=len(voiceclone_s3_files),
                total_size_bytes=total_size_bytes,
            )
            logger.info(f"✓ Saved voice clone metadata to database (voice_id: {voice_id})")

        except Exception as db_error:
            logger.error(
                f"CRITICAL: Failed to save voice clone metadata to database. "
                f"Voice created in ElevenLabs (voice_id: {voice_id}) but not tracked. "
                f"User: {voice_data.user_id}, Error: {db_error}"
            )
            # Fail the entire operation to prevent data inconsistency
            # Operator must manually reconcile: voice exists in ElevenLabs but not in DB
            raise HTTPException(
                status_code=500,
                detail=f"Voice clone created (voice_id: {voice_id}) but failed to save metadata. "
                f"Please contact support with this voice_id for manual reconciliation.",
            )

        return VoiceCloneResponse(
            voice_id=voice_id,
            name=voice_data.name,
            status="success",
            message=f"Voice clone created successfully from {len(voice_data.s3_uris)} S3 file(s)",
            components={
                "s3_copy_permanent": {
                    "status": "success",
                    "files_count": len(voiceclone_s3_files),
                },
                "s3_download_for_elevenlabs": {
                    "status": "success",
                    "files_count": len(file_tuples),
                },
                "elevenlabs_api": {"status": "success", "voice_id": voice_id},
                "database_save": {"status": "success"},
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create voice clone from S3 URIs: {str(e)}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(voice_data.user_id),
                "voice_name": voice_data.name,
                "s3_uris_count": len(voice_data.s3_uris),
                "source_job_id": voice_data.source_job_id,
            },
            tags={
                "component": "elevenlabs",
                "operation": "create_voice_clone_from_s3",
                "severity": "high",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/users/{user_id}/voice-clones", response_model=List[VoiceCloneListItem])
async def get_user_voice_clones(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """
    Get all voice clones for a user

    **Authentication**:
    - Users: JWT cookie (can only access their own voice clones)
    - Operators: X-API-Key header (can access any user's voice clones)

    Args:
        user_id: User UUID
        session: Database session
        auth: User (JWT) or "service" (API key)

    Returns:
        List of voice clones

    Raises:
        HTTPException: 403 if unauthorized, 500 for server errors
    """
    try:
        # Authorization check
        if isinstance(auth, User):
            # User JWT auth - can only access their own voice clones
            if auth.id != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only access your own voice clones",
                )
            logger.info(f"User {auth.id} accessing their voice clones")
        else:
            # Service/operator auth - can access any user's voice clones
            logger.info(f"Service account accessing voice clones for user {user_id}")

        # Get all voice clones for user (filter by provider=elevenlabs)
        all_voice_clones = await VoiceCloneRepository.get_by_user_id(session, user_id)
        voice_clones = [
            vc
            for vc in all_voice_clones
            if vc.settings and vc.settings.get("provider") == "elevenlabs"
        ]

        # Build response
        result = [
            VoiceCloneListItem(
                id=str(vc.id),
                voice_id=vc.voice_id,
                name=vc.name,
                description=vc.description,
                platform=vc.platform,  # Platform field from database
                total_files=vc.total_files,
                total_size_bytes=vc.total_size_bytes,
                created_at=vc.created_at.isoformat(),
            )
            for vc in voice_clones
        ]

        logger.info(f"Retrieved {len(result)} Eleven Labs voice clones for user {user_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get voice clones for user {user_id}: {str(e)}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user_id),
                "auth_type": "user" if isinstance(auth, User) else "service",
            },
            tags={
                "component": "elevenlabs",
                "operation": "get_voice_clones",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "ElevenLabs service is ready"}


class VoiceDeleteResponse(BaseModel):
    """Response model for voice deletion"""

    voice_id: str
    status: str
    message: str
    database_deleted: bool = False
    elevenlabs_deleted: bool = False


@router.delete("/voice/{voice_id}", response_model=VoiceDeleteResponse)
async def delete_voice(
    voice_id: str,
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """
    Delete a voice clone from ElevenLabs and database

    **Authentication**:
    - Users: JWT cookie (can only delete their own voice clones)
    - Operators: X-API-Key header (can delete any voice clone)

    **Deletion Process**:
    1. Find voice clone record in database
    2. Delete from ElevenLabs API
    3. Clear persona.voice_id reference
    4. Delete voice clone record from database

    Args:
        voice_id: ElevenLabs voice ID
        session: Database session
        auth: User (JWT) or "service" (API key)

    Returns:
        VoiceDeleteResponse with deletion status

    Raises:
        HTTPException: 404 if voice not found, 403 for authorization errors
    """
    try:
        logger.info(f"Delete voice request for voice_id: {voice_id}")

        # Find voice clone in database
        voice_clone = await VoiceCloneRepository.get_by_voice_id(session, voice_id)

        if not voice_clone:
            raise HTTPException(
                status_code=404,
                detail=f"Voice clone not found in database: {voice_id}",
            )

        # Authorization check
        if isinstance(auth, User):
            if auth.id != voice_clone.user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete your own voice clones",
                )
            logger.info(f"User {auth.id} deleting their voice clone: {voice_id}")
        else:
            logger.info(
                f"Service account deleting voice clone: {voice_id} for user {voice_clone.user_id}"
            )

        # Verify this is an ElevenLabs voice clone
        if voice_clone.settings and voice_clone.settings.get("provider") == "cartesia":
            raise HTTPException(
                status_code=400,
                detail="This endpoint only handles ElevenLabs voice clones. Use /cartesia/voice-clones/{voice_id} for Cartesia voice clones.",
            )

        elevenlabs_deleted = False
        database_deleted = False

        # Step 1: Delete from ElevenLabs
        try:
            elevenlabs_service = ElevenLabsService()
            elevenlabs_service.delete_voice(voice_id)
            elevenlabs_deleted = True
            logger.info(f"Deleted voice from ElevenLabs: {voice_id}")
        except Exception as e:
            logger.warning(f"Failed to delete from ElevenLabs (may already be deleted): {e}")
            # Continue with database cleanup even if ElevenLabs deletion fails

        # Step 2: Clear persona.voice_id reference
        try:
            from sqlalchemy import update

            from shared.database.models.database import Persona

            stmt = update(Persona).where(Persona.voice_id == voice_id).values(voice_id=None)
            await session.execute(stmt)
            logger.info(f"Cleared persona.voice_id reference for: {voice_id}")
        except Exception as e:
            logger.warning(f"Failed to clear persona.voice_id: {e}")

        # Step 3: Delete voice clone record from database
        try:
            deleted = await VoiceCloneRepository.delete(session, voice_clone.id)
            database_deleted = deleted
            logger.info(f"Deleted voice clone record from database: {voice_id}")
        except Exception as e:
            logger.error(f"Failed to delete voice clone record: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete voice clone record: {str(e)}",
            )

        return VoiceDeleteResponse(
            voice_id=voice_id,
            status="success",
            message=f"Voice clone {voice_id} deleted successfully",
            database_deleted=database_deleted,
            elevenlabs_deleted=elevenlabs_deleted,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete voice clone {voice_id}: {str(e)}")
        capture_exception_with_context(
            e,
            extra={
                "voice_id": voice_id,
                "auth_type": "user" if isinstance(auth, User) else "service",
            },
            tags={
                "component": "elevenlabs",
                "operation": "delete_voice",
                "severity": "high",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/voice/by-username/{username}", response_model=VoiceDeleteResponse)
async def delete_voice_by_username(
    username: str,
    persona_name: str = "default",
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """
    Delete a voice clone by username (for n8n workflow integration)

    **Authentication**:
    - Operators only: X-API-Key header required

    **Use Case**:
    This endpoint is designed for the n8n workflow that triggers when a loom link
    is present in the Google Sheet. It looks up the voice_id from the persona table
    using the username and deletes it.

    **Deletion Process**:
    1. Find persona by username
    2. Get voice_id from persona
    3. Delete from ElevenLabs API
    4. Clear persona.voice_id reference
    5. Delete voice clone record from database

    Args:
        username: User's username
        persona_name: Persona name (default: "default")
        session: Database session
        auth: Must be service/operator auth

    Returns:
        VoiceDeleteResponse with deletion status

    Raises:
        HTTPException: 404 if persona/voice not found, 403 for non-operator access
    """
    try:
        # Only allow operator/service access for this endpoint
        if isinstance(auth, User):
            raise HTTPException(
                status_code=403,
                detail="This endpoint is only accessible via API key authentication",
            )

        logger.info(f"Delete voice request by username: {username}, persona_name: {persona_name}")

        # Find persona by username
        persona = await PersonaRepository.get_by_username_and_persona(
            session=session,
            username=username,
            persona_name=persona_name,
        )

        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"Persona not found for username: {username}",
            )

        voice_id = persona.voice_id

        if not voice_id:
            raise HTTPException(
                status_code=404,
                detail=f"No voice_id found for username: {username}. Voice may not have been created or already deleted.",
            )

        logger.info(f"Found voice_id {voice_id} for username {username}")

        elevenlabs_deleted = False
        database_deleted = False

        # Step 1: Delete from ElevenLabs
        try:
            elevenlabs_service = ElevenLabsService()
            elevenlabs_service.delete_voice(voice_id)
            elevenlabs_deleted = True
            logger.info(f"Deleted voice from ElevenLabs: {voice_id}")
        except Exception as e:
            logger.warning(f"Failed to delete from ElevenLabs (may already be deleted): {e}")
            # Continue with database cleanup even if ElevenLabs deletion fails

        # Step 2: Clear persona.voice_id reference
        try:
            persona.voice_id = None
            await session.commit()
            logger.info(f"Cleared persona.voice_id for username: {username}")
        except Exception as e:
            logger.warning(f"Failed to clear persona.voice_id: {e}")
            await session.rollback()

        # Step 3: Delete voice clone record from database (if exists)
        try:
            voice_clone = await VoiceCloneRepository.get_by_voice_id(session, voice_id)
            if voice_clone:
                deleted = await VoiceCloneRepository.delete(session, voice_clone.id)
                database_deleted = deleted
                logger.info(f"Deleted voice clone record from database: {voice_id}")
            else:
                logger.info(f"No voice clone record found in database for: {voice_id}")
                database_deleted = True  # Consider it deleted if not found
        except Exception as e:
            logger.warning(f"Failed to delete voice clone record: {e}")

        return VoiceDeleteResponse(
            voice_id=voice_id,
            status="success",
            message=f"Voice clone for username '{username}' deleted successfully",
            database_deleted=database_deleted,
            elevenlabs_deleted=elevenlabs_deleted,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete voice for username {username}: {str(e)}")
        capture_exception_with_context(
            e,
            extra={
                "username": username,
                "persona_name": persona_name,
            },
            tags={
                "component": "elevenlabs",
                "operation": "delete_voice_by_username",
                "severity": "high",
                "user_facing": "false",
            },
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
