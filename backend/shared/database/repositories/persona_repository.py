"""
Persona Repository - Database operations for personas
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models import get_session
from shared.database.models.database import Persona
from shared.database.models.user import User

logger = logging.getLogger(__name__)


class PersonaRepository:
    """Repository for persona database operations"""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session

        Args:
            session: Database session
        """
        self.session = session

    async def get_by_id(self, persona_id: UUID) -> Optional[Persona]:
        """
        Get persona by ID

        Args:
            persona_id: UUID of the persona

        Returns:
            Persona if found, None otherwise
        """
        try:
            stmt = select(Persona).where(Persona.id == persona_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting persona {persona_id}: {e}")
            return None

    async def exists(self, persona_id: UUID) -> bool:
        """
        Check if persona exists

        Args:
            persona_id: UUID of the persona

        Returns:
            True if persona exists, False otherwise
        """
        persona = await self.get_by_id(persona_id)
        return persona is not None

    async def get_by_username(
        self, username: str, persona_name: str = "default"
    ) -> Optional[Persona]:
        """
        Get persona by user's username and persona_name

        Args:
            username: The user's unique username
            persona_name: The persona name (defaults to "default")

        Returns:
            Persona if found, None otherwise
        """
        try:
            stmt = (
                select(Persona)
                .join(User)
                .where(
                    User.username == username,
                    Persona.persona_name == persona_name,
                    Persona.is_active == True,
                )
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                f"Error getting persona by username {username}, persona_name {persona_name}: {e}"
            )
            return None

    @staticmethod
    async def get_by_username_and_persona(
        session: AsyncSession, username: str, persona_name: str = "default"
    ) -> Optional[Persona]:
        """
        Static helper to get persona by user's username and persona_name

        Args:
            session: Database session
            username: The user's unique username
            persona_name: The persona name (defaults to "default")

        Returns:
            Persona if found, None otherwise
        """
        try:
            stmt = (
                select(Persona)
                .join(User)
                .where(
                    User.username == username,
                    Persona.persona_name == persona_name,
                    Persona.is_active == True,
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                f"Error getting persona by username {username}, persona_name {persona_name}: {e}"
            )
            return None


# Legacy singleton pattern for backward compatibility with livekit routes
# TODO: Refactor livekit routes to use session-based repository
class LegacyPersonaRepository:
    """
    Legacy repository implementation that creates its own sessions.
    This is kept for backward compatibility with livekit routes.
    New code should use PersonaRepository with session dependency injection.
    """

    def __init__(self):
        self.session_factory = get_session

    async def get_by_id(self, persona_id: UUID) -> Optional[Persona]:
        """Get persona by ID (creates own session)"""
        async for session in self.session_factory():
            try:
                stmt = select(Persona).where(Persona.id == persona_id)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Error getting persona {persona_id}: {e}")
                return None

    async def exists(self, persona_id: UUID) -> bool:
        """Check if persona exists (creates own session)"""
        persona = await self.get_by_id(persona_id)
        return persona is not None

    async def get_by_username(
        self, username: str, persona_name: str = "default"
    ) -> Optional[Persona]:
        """Get persona by username (creates own session)"""
        async for session in self.session_factory():
            try:
                stmt = (
                    select(Persona)
                    .join(User)
                    .where(
                        User.username == username,
                        Persona.persona_name == persona_name,
                        Persona.is_active == True,
                    )
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(
                    f"Error getting persona by username {username}, persona_name {persona_name}: {e}"
                )
                return None


_legacy_persona_repository: Optional[LegacyPersonaRepository] = None


def get_persona_repository() -> LegacyPersonaRepository:
    """
    Get legacy persona repository instance (for backward compatibility).
    This function is deprecated and should not be used in new code.
    Use PersonaRepository with session dependency injection instead.
    """
    global _legacy_persona_repository
    if _legacy_persona_repository is None:
        _legacy_persona_repository = LegacyPersonaRepository()
    return _legacy_persona_repository
