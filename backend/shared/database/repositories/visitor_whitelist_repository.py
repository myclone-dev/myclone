"""
Visitor Whitelist Repository - Database operations for global visitor management
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, select, update

from shared.database.models.database import async_session_maker
from shared.database.models.persona_access import PersonaVisitor, VisitorWhitelist

logger = logging.getLogger(__name__)


class VisitorWhitelistRepository:
    """Repository for visitor whitelist operations (user-level global whitelist)"""

    async def create_visitor(
        self,
        user_id: UUID,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> VisitorWhitelist:
        """
        Add visitor to user's global whitelist

        Args:
            user_id: User UUID (owner of whitelist)
            email: Visitor's email (normalized to lowercase)
            first_name: Visitor's first name (optional)
            last_name: Visitor's last name (optional)
            notes: User's notes about visitor (optional)

        Returns:
            Created VisitorWhitelist instance
        """
        async with async_session_maker() as session:
            try:
                # Normalize email to lowercase
                normalized_email = email.lower().strip()

                visitor = VisitorWhitelist(
                    user_id=user_id,
                    email=normalized_email,
                    first_name=first_name,
                    last_name=last_name,
                    notes=notes,
                )

                session.add(visitor)
                await session.commit()
                await session.refresh(visitor)

                logger.info(
                    f"Created visitor {visitor.id} for user {user_id}, email={normalized_email}"
                )
                return visitor

            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating visitor for user {user_id}: {e}")
                raise

    async def get_visitor_by_id(self, visitor_id: UUID) -> Optional[VisitorWhitelist]:
        """Get visitor by ID"""
        async with async_session_maker() as session:
            try:
                stmt = select(VisitorWhitelist).where(VisitorWhitelist.id == visitor_id)
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Error getting visitor {visitor_id}: {e}")
                return None

    async def get_visitor_by_email(self, user_id: UUID, email: str) -> Optional[VisitorWhitelist]:
        """
        Get visitor by user_id and email

        Args:
            user_id: User UUID
            email: Visitor's email

        Returns:
            VisitorWhitelist instance or None if not found
        """
        async with async_session_maker() as session:
            try:
                normalized_email = email.lower().strip()
                stmt = select(VisitorWhitelist).where(
                    VisitorWhitelist.user_id == user_id,
                    VisitorWhitelist.email == normalized_email,
                )
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"Error getting visitor by email {email} for user {user_id}: {e}")
                return None

    async def get_all_visitors(self, user_id: UUID) -> List[VisitorWhitelist]:
        """
        Get all visitors in user's whitelist

        Args:
            user_id: User UUID

        Returns:
            List of VisitorWhitelist instances
        """
        async with async_session_maker() as session:
            try:
                stmt = (
                    select(VisitorWhitelist)
                    .where(VisitorWhitelist.user_id == user_id)
                    .order_by(VisitorWhitelist.created_at.desc())
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
            except Exception as e:
                logger.error(f"Error getting visitors for user {user_id}: {e}")
                return []

    async def update_visitor(
        self,
        visitor_id: UUID,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[VisitorWhitelist]:
        """
        Update visitor information

        Args:
            visitor_id: Visitor UUID
            first_name: Updated first name (optional)
            last_name: Updated last name (optional)
            notes: Updated notes (optional)

        Returns:
            Updated VisitorWhitelist instance or None if not found
        """
        async with async_session_maker() as session:
            try:
                stmt = select(VisitorWhitelist).where(VisitorWhitelist.id == visitor_id)
                result = await session.execute(stmt)
                visitor = result.scalar_one_or_none()

                if not visitor:
                    logger.warning(f"Visitor {visitor_id} not found")
                    return None

                # Update fields (only if provided)
                if first_name is not None:
                    visitor.first_name = first_name
                if last_name is not None:
                    visitor.last_name = last_name
                if notes is not None:
                    visitor.notes = notes

                await session.commit()
                await session.refresh(visitor)

                logger.info(f"Updated visitor {visitor_id}")
                return visitor

            except Exception as e:
                await session.rollback()
                logger.error(f"Error updating visitor {visitor_id}: {e}")
                raise

    async def update_last_accessed(self, visitor_id: UUID) -> bool:
        """
        Update last_accessed_at timestamp for visitor

        Args:
            visitor_id: Visitor UUID

        Returns:
            True if updated successfully
        """
        async with async_session_maker() as session:
            try:
                stmt = (
                    update(VisitorWhitelist)
                    .where(VisitorWhitelist.id == visitor_id)
                    .values(last_accessed_at=datetime.now(timezone.utc))
                )
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"Updated last_accessed_at for visitor {visitor_id}")
                    return True
                return False

            except Exception as e:
                await session.rollback()
                logger.error(f"Error updating last_accessed for visitor {visitor_id}: {e}")
                return False

    async def delete_visitor(self, visitor_id: UUID) -> bool:
        """
        Delete visitor from whitelist

        Note: This will CASCADE delete all persona_visitors entries
        (removes visitor from all personas they were assigned to)

        Args:
            visitor_id: Visitor UUID

        Returns:
            True if deleted successfully
        """
        async with async_session_maker() as session:
            try:
                stmt = delete(VisitorWhitelist).where(VisitorWhitelist.id == visitor_id)
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"Deleted visitor {visitor_id} (CASCADE deleted from all personas)")
                    return True

                logger.warning(f"Visitor {visitor_id} not found for deletion")
                return False

            except Exception as e:
                await session.rollback()
                logger.error(f"Error deleting visitor {visitor_id}: {e}")
                raise

    async def get_visitors_for_persona(self, persona_id: UUID) -> List[VisitorWhitelist]:
        """
        Get all visitors assigned to a specific persona

        Args:
            persona_id: Persona UUID

        Returns:
            List of VisitorWhitelist instances
        """
        async with async_session_maker() as session:
            try:
                stmt = (
                    select(VisitorWhitelist)
                    .join(PersonaVisitor, PersonaVisitor.visitor_id == VisitorWhitelist.id)
                    .where(PersonaVisitor.persona_id == persona_id)
                    .order_by(PersonaVisitor.added_at.desc())
                )
                result = await session.execute(stmt)
                return list(result.scalars().all())
            except Exception as e:
                logger.error(f"Error getting visitors for persona {persona_id}: {e}")
                return []


# Singleton instance
_visitor_whitelist_repository: Optional[VisitorWhitelistRepository] = None


def get_visitor_whitelist_repository() -> VisitorWhitelistRepository:
    """Get singleton visitor whitelist repository instance"""
    global _visitor_whitelist_repository
    if _visitor_whitelist_repository is None:
        _visitor_whitelist_repository = VisitorWhitelistRepository()
    return _visitor_whitelist_repository
