"""
Unified Voice Clone API - Platform-agnostic endpoints
Aggregates voice clones from all platforms (ElevenLabs, Cartesia, PlayHT, Custom)
"""

import logging
from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_auth import get_user_or_service
from app.services.cartesia_service import CartesiaService
from app.services.elevenlabs_service import ElevenLabsService
from shared.database.models.database import get_session
from shared.database.models.user import User
from shared.database.repositories.voice_clone_repository import VoiceCloneRepository
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.schemas.voice_clone import VoiceCloneDeleteResponse, VoiceCloneListItem

router = APIRouter(prefix="/api/v1/voice-clones", tags=["voice_clones"])
logger = logging.getLogger(__name__)


@router.get("/users/{user_id}", response_model=List[VoiceCloneListItem])
async def get_user_voice_clones_unified(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """
    Get all voice clones for a user across ALL platforms (unified endpoint)

    **This is the recommended endpoint for fetching voice clones.**

    Returns voice clones from:
    - ElevenLabs
    - Cartesia

    Each voice clone includes a `platform` field indicating its source.

    **Authentication**:
    - Users: JWT cookie (can only access their own voice clones)
    - Operators: X-API-Key header (can access any user's voice clones)

    Args:
        user_id: User UUID
        session: Database session
        auth: User (JWT) or "service" (API key)

    Returns:
        List of voice clones with platform field

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
            logger.info(f"User {auth.id} accessing their voice clones (unified endpoint)")
        else:
            # Service/operator auth - can access any user's voice clones
            logger.info(f"Service account accessing voice clones for user {user_id} (unified)")

        # Get all voice clones for user (all platforms)
        voice_clones = await VoiceCloneRepository.get_by_user_id(session, user_id)

        # Build unified response with platform field
        result = [
            VoiceCloneListItem(
                id=str(vc.id),
                voice_id=vc.voice_id,
                name=vc.name,
                description=vc.description,
                platform=vc.platform,  # elevenlabs or cartesia
                total_files=vc.total_files,
                total_size_bytes=vc.total_size_bytes,
                created_at=vc.created_at.isoformat(),
            )
            for vc in voice_clones
        ]

        logger.info(
            f"Retrieved {len(result)} voice clones for user {user_id} "
            f"(platforms: {set(vc.platform for vc in voice_clones)})"
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get unified voice clones for user {user_id}: {str(e)}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user_id),
                "auth_type": "user" if isinstance(auth, User) else "service",
            },
            tags={
                "component": "voice_clones",
                "operation": "get_unified_voice_clones",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/users/{user_id}/platform/{platform}", response_model=List[VoiceCloneListItem])
async def get_user_voice_clones_by_platform(
    user_id: UUID,
    platform: str,
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """
    Get voice clones for a user filtered by platform

    **Platforms**: elevenlabs, cartesia

    **Authentication**:
    - Users: JWT cookie (can only access their own voice clones)
    - Operators: X-API-Key header (can access any user's voice clones)

    Args:
        user_id: User UUID
        platform: Platform name (elevenlabs, cartesia)
        session: Database session
        auth: User (JWT) or "service" (API key)

    Returns:
        List of voice clones for the specified platform

    Raises:
        HTTPException: 400 for invalid platform, 403 if unauthorized, 500 for server errors
    """
    try:
        # Validate platform
        valid_platforms = ["elevenlabs", "cartesia"]
        if platform.lower() not in valid_platforms:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid platform: {platform}. Must be one of: {', '.join(valid_platforms)}",
            )

        # Authorization check
        if isinstance(auth, User):
            if auth.id != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only access your own voice clones",
                )
            logger.info(f"User {auth.id} accessing their {platform} voice clones")
        else:
            logger.info(f"Service account accessing {platform} voice clones for user {user_id}")

        # Get all voice clones and filter by platform
        all_voice_clones = await VoiceCloneRepository.get_by_user_id(session, user_id)
        voice_clones = [vc for vc in all_voice_clones if vc.platform == platform.lower()]

        # Build response
        result = [
            VoiceCloneListItem(
                id=str(vc.id),
                voice_id=vc.voice_id,
                name=vc.name,
                description=vc.description,
                platform=vc.platform,
                total_files=vc.total_files,
                total_size_bytes=vc.total_size_bytes,
                created_at=vc.created_at.isoformat(),
            )
            for vc in voice_clones
        ]

        logger.info(f"Retrieved {len(result)} {platform} voice clones for user {user_id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get {platform} voice clones for user {user_id}: {str(e)}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user_id),
                "platform": platform,
                "auth_type": "user" if isinstance(auth, User) else "service",
            },
            tags={
                "component": "voice_clones",
                "operation": "get_voice_clones_by_platform",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{voice_id}", response_model=VoiceCloneDeleteResponse)
async def delete_voice_clone_unified(
    voice_id: str,
    session: AsyncSession = Depends(get_session),
    auth: Union[User, str] = Depends(get_user_or_service),
):
    """
    Delete a voice clone (unified endpoint - auto-detects platform)

    **This is the recommended endpoint for deleting voice clones.**

    Automatically detects whether the voice is from ElevenLabs or Cartesia
    and calls the appropriate deletion service.

    **Deletion Process**:
    1. Find voice clone in database
    2. Verify user ownership
    3. Delete from platform API (ElevenLabs or Cartesia)
    4. Clear persona.voice_id references
    5. Delete from database

    **Authentication**:
    - Users: JWT cookie (can only delete their own voice clones)
    - Operators: X-API-Key header (can delete any voice clone)

    Args:
        voice_id: Voice ID to delete
        session: Database session
        auth: User (JWT) or "service" (API key)

    Returns:
        VoiceCloneDeleteResponse with deletion status

    Raises:
        HTTPException: 404 if voice not found, 403 if unauthorized, 500 for server errors
    """
    try:
        logger.info(f"Unified delete request for voice_id: {voice_id}")

        # Step 1: Find voice clone in database
        voice_clone = await VoiceCloneRepository.get_by_voice_id(session, voice_id)

        if not voice_clone:
            raise HTTPException(
                status_code=404,
                detail=f"Voice clone not found: {voice_id}",
            )

        platform = voice_clone.platform
        logger.info(f"Voice clone platform detected: {platform}")

        # Step 2: Authorization check
        if isinstance(auth, User):
            # User JWT auth - can only delete their own voice clones
            if voice_clone.user_id != auth.id:
                raise HTTPException(
                    status_code=403,
                    detail="You can only delete your own voice clones",
                )
            logger.info(f"User {auth.id} deleting their {platform} voice clone: {voice_id}")
        else:
            # Service/operator auth - can delete any voice clone
            logger.info(f"Service account deleting {platform} voice clone: {voice_id}")

        platform_deleted = False
        database_deleted = False

        # Step 3: Delete from platform API (route based on platform field)
        try:
            if platform == "elevenlabs":
                elevenlabs_service = ElevenLabsService()
                elevenlabs_service.delete_voice(voice_id)
                logger.info(f"Deleted voice from ElevenLabs API: {voice_id}")
            elif platform == "cartesia":
                cartesia_service = CartesiaService()
                await cartesia_service.delete_voice(voice_id)
                logger.info(f"Deleted voice from Cartesia API: {voice_id}")
            else:
                logger.warning(
                    f"Unknown platform '{platform}' for voice {voice_id}, skipping API deletion"
                )

            platform_deleted = True
        except Exception as e:
            logger.warning(
                f"Failed to delete voice from {platform} API (may already be deleted): {e}"
            )
            # Continue with database deletion even if platform deletion fails

        # Step 4: Clear persona.voice_id references
        try:
            from sqlalchemy import update

            from shared.database.models.database import Persona

            stmt = update(Persona).where(Persona.voice_id == voice_id).values(voice_id=None)
            await session.execute(stmt)
            logger.info(f"Cleared persona.voice_id references for: {voice_id}")
        except Exception as e:
            logger.warning(f"Failed to clear persona.voice_id references: {e}")

        # Step 5: Delete from database
        try:
            deleted = await VoiceCloneRepository.delete(session, voice_clone.id)
            database_deleted = deleted
            logger.info(f"Deleted voice clone from database: {voice_id}")
        except Exception as e:
            logger.error(f"Failed to delete voice clone from database: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete voice clone from database: {str(e)}",
            )

        return VoiceCloneDeleteResponse(
            voice_id=voice_id,
            platform=platform,
            status="success",
            message=f"Voice clone deleted successfully from {platform}",
            platform_deleted=platform_deleted,
            database_deleted=database_deleted,
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
                "component": "voice_clones",
                "operation": "delete_voice_clone_unified",
                "severity": "high",
                "user_facing": "true",
            },
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Unified voice clone service is ready"}
