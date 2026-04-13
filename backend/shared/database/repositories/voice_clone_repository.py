"""
Voice Clone Repository - Database operations for voice_clones table
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.voice_clone import VoiceClone

logger = logging.getLogger(__name__)


class VoiceCloneRepository:
    """Repository for voice_clones table database operations"""

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: UUID,
        voice_id: str,
        name: str,
        description: Optional[str],
        sample_files: list,
        settings: dict,
        total_files: int,
        total_size_bytes: int,
        platform: str = "elevenlabs",
    ) -> VoiceClone:
        """
        Create a new voice clone record

        Args:
            session: Database session
            user_id: User ID who owns this voice clone
            voice_id: Voice ID from the platform (ElevenLabs, Cartesia, etc.)
            name: Voice clone name
            description: Optional description
            sample_files: List of S3 file metadata dicts
            settings: Platform-specific settings dict
            total_files: Total number of files
            total_size_bytes: Total size in bytes
            platform: Voice platform (elevenlabs, cartesia, playht, custom)

        Returns:
            Created VoiceClone instance

        Raises:
            Exception: If database operation fails
        """
        try:
            voice_clone = VoiceClone(
                user_id=user_id,
                voice_id=voice_id,
                name=name,
                description=description,
                sample_files=sample_files,
                settings=settings,
                total_files=total_files,
                total_size_bytes=total_size_bytes,
                platform=platform,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(voice_clone)
            await session.commit()
            await session.refresh(voice_clone)

            logger.info(f"Created voice clone record: {voice_clone.id} (voice_id: {voice_id})")
            return voice_clone

        except Exception as e:
            logger.error(f"Failed to create voice clone record: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_by_id(session: AsyncSession, voice_clone_id: UUID) -> Optional[VoiceClone]:
        """
        Get voice clone by ID

        Args:
            session: Database session
            voice_clone_id: Voice clone UUID

        Returns:
            VoiceClone instance or None if not found
        """
        try:
            stmt = select(VoiceClone).where(VoiceClone.id == voice_clone_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get voice clone {voice_clone_id}: {e}")
            return None

    @staticmethod
    async def get_by_voice_id(session: AsyncSession, voice_id: str) -> Optional[VoiceClone]:
        """
        Get voice clone by ElevenLabs voice_id

        Args:
            session: Database session
            voice_id: ElevenLabs voice ID

        Returns:
            VoiceClone instance or None if not found
        """
        try:
            stmt = select(VoiceClone).where(VoiceClone.voice_id == voice_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get voice clone by voice_id {voice_id}: {e}")
            return None

    @staticmethod
    async def get_by_user_id(session: AsyncSession, user_id: UUID) -> List[VoiceClone]:
        """
        Get all voice clones for a user

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            List of VoiceClone instances
        """
        try:
            stmt = (
                select(VoiceClone)
                .where(VoiceClone.user_id == user_id)
                .order_by(VoiceClone.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get voice clones for user {user_id}: {e}")
            return []

    @staticmethod
    async def count_by_user_id(session: AsyncSession, user_id: UUID) -> int:
        """
        Count total voice clones for a user

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            Number of voice clones
        """
        try:
            stmt = select(func.count(VoiceClone.id)).where(VoiceClone.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Failed to count voice clones for user {user_id}: {e}")
            return 0

    @staticmethod
    async def delete(session: AsyncSession, voice_clone_id: UUID) -> bool:
        """
        Delete a voice clone record

        Args:
            session: Database session
            voice_clone_id: Voice clone UUID

        Returns:
            True if deleted, False if not found

        Raises:
            Exception: If database operation fails
        """
        try:
            voice_clone = await VoiceCloneRepository.get_by_id(session, voice_clone_id)
            if not voice_clone:
                return False

            await session.delete(voice_clone)
            await session.commit()

            logger.info(f"Deleted voice clone record: {voice_clone_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete voice clone {voice_clone_id}: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def update(session: AsyncSession, voice_clone_id: UUID, **kwargs) -> Optional[VoiceClone]:
        """
        Update voice clone fields

        Args:
            session: Database session
            voice_clone_id: Voice clone UUID
            **kwargs: Fields to update

        Returns:
            Updated VoiceClone instance or None if not found

        Raises:
            Exception: If database operation fails
        """
        try:
            voice_clone = await VoiceCloneRepository.get_by_id(session, voice_clone_id)
            if not voice_clone:
                return None

            for key, value in kwargs.items():
                if hasattr(voice_clone, key):
                    setattr(voice_clone, key, value)

            voice_clone.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(voice_clone)

            logger.info(f"Updated voice clone record: {voice_clone_id}")
            return voice_clone

        except Exception as e:
            logger.error(f"Failed to update voice clone {voice_clone_id}: {e}")
            await session.rollback()
            raise
