"""
Custom Domain Repository - Database operations for custom_domains table

Handles CRUD operations and queries for white-label custom domain integration.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.custom_domain import CustomDomain, DomainStatus

logger = logging.getLogger(__name__)


class CustomDomainRepository:
    """Repository for custom_domains table database operations"""

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: UUID,
        domain: str,
        verification_records: Optional[list] = None,
        routing_record: Optional[dict] = None,
    ) -> CustomDomain:
        """
        Create a new custom domain record (USER-LEVEL)

        Args:
            session: Database session
            user_id: User ID who owns this domain
            domain: Full domain name (e.g., 'chat.example.com')
            verification_records: DNS records for verification (from Vercel)
            routing_record: A or CNAME record for traffic routing

        Returns:
            Created CustomDomain instance

        Raises:
            Exception: If database operation fails
        """
        try:
            custom_domain = CustomDomain(
                user_id=user_id,
                domain=domain.lower().strip(),
                verification_records=verification_records,
                routing_record=routing_record,
                status=DomainStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(custom_domain)
            await session.commit()
            await session.refresh(custom_domain)

            logger.info(f"Created custom domain record: {custom_domain.id} (domain: {domain})")
            return custom_domain

        except Exception as e:
            logger.error(f"Failed to create custom domain record: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_by_id(session: AsyncSession, domain_id: UUID) -> Optional[CustomDomain]:
        """
        Get custom domain by ID

        Args:
            session: Database session
            domain_id: Custom domain UUID

        Returns:
            CustomDomain instance or None if not found
        """
        try:
            stmt = select(CustomDomain).where(CustomDomain.id == domain_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get custom domain {domain_id}: {e}")
            return None

    @staticmethod
    async def get_by_domain(session: AsyncSession, domain: str) -> Optional[CustomDomain]:
        """
        Get custom domain by domain name

        Args:
            session: Database session
            domain: Full domain name (e.g., 'chat.example.com')

        Returns:
            CustomDomain instance or None if not found
        """
        try:
            stmt = select(CustomDomain).where(CustomDomain.domain == domain.lower().strip())
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get custom domain by name {domain}: {e}")
            return None

    @staticmethod
    async def get_active_by_domain(session: AsyncSession, domain: str) -> Optional[CustomDomain]:
        """
        Get active custom domain by domain name (for routing)

        Args:
            session: Database session
            domain: Full domain name

        Returns:
            CustomDomain instance if active, None otherwise
        """
        try:
            stmt = select(CustomDomain).where(
                CustomDomain.domain == domain.lower().strip(),
                CustomDomain.status == DomainStatus.ACTIVE,
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get active custom domain {domain}: {e}")
            return None

    @staticmethod
    async def get_by_user_id(session: AsyncSession, user_id: UUID) -> List[CustomDomain]:
        """
        Get all custom domains for a user

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            List of CustomDomain instances
        """
        try:
            stmt = (
                select(CustomDomain)
                .where(CustomDomain.user_id == user_id)
                .order_by(CustomDomain.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get custom domains for user {user_id}: {e}")
            return []

    @staticmethod
    async def count_by_user_id(session: AsyncSession, user_id: UUID) -> int:
        """
        Count total custom domains for a user

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            Number of custom domains
        """
        try:
            stmt = select(func.count(CustomDomain.id)).where(CustomDomain.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Failed to count custom domains for user {user_id}: {e}")
            return 0

    @staticmethod
    async def count_active_by_user_id(session: AsyncSession, user_id: UUID) -> int:
        """
        Count active custom domains for a user

        Args:
            session: Database session
            user_id: User UUID

        Returns:
            Number of active custom domains
        """
        try:
            stmt = select(func.count(CustomDomain.id)).where(
                CustomDomain.user_id == user_id,
                CustomDomain.status == DomainStatus.ACTIVE,
            )
            result = await session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Failed to count active custom domains for user {user_id}: {e}")
            return 0

    @staticmethod
    async def delete(session: AsyncSession, domain_id: UUID, user_id: UUID) -> bool:
        """
        Delete a custom domain record (user ownership check)

        Args:
            session: Database session
            domain_id: Custom domain UUID
            user_id: User UUID (for ownership verification)

        Returns:
            True if deleted, False if not found or not owned by user

        Raises:
            Exception: If database operation fails
        """
        try:
            custom_domain = await CustomDomainRepository.get_by_id(session, domain_id)
            if not custom_domain or custom_domain.user_id != user_id:
                return False

            await session.delete(custom_domain)
            await session.commit()

            logger.info(f"Deleted custom domain record: {domain_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete custom domain {domain_id}: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def update(
        session: AsyncSession, domain_id: UUID, user_id: UUID, **kwargs
    ) -> Optional[CustomDomain]:
        """
        Update custom domain fields (with user ownership check)

        Args:
            session: Database session
            domain_id: Custom domain UUID
            user_id: User UUID (for ownership verification)
            **kwargs: Fields to update

        Returns:
            Updated CustomDomain instance or None if not found

        Raises:
            Exception: If database operation fails
        """
        try:
            custom_domain = await CustomDomainRepository.get_by_id(session, domain_id)
            if not custom_domain or custom_domain.user_id != user_id:
                return None

            for key, value in kwargs.items():
                if hasattr(custom_domain, key):
                    setattr(custom_domain, key, value)

            custom_domain.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(custom_domain)

            logger.info(f"Updated custom domain record: {domain_id}")
            return custom_domain

        except Exception as e:
            logger.error(f"Failed to update custom domain {domain_id}: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def update_status(
        session: AsyncSession,
        domain_id: UUID,
        status: DomainStatus,
        error_message: Optional[str] = None,
    ) -> Optional[CustomDomain]:
        """
        Update custom domain status (internal use, no ownership check)

        Args:
            session: Database session
            domain_id: Custom domain UUID
            status: New status
            error_message: Optional error message for failed status

        Returns:
            Updated CustomDomain instance or None if not found
        """
        try:
            custom_domain = await CustomDomainRepository.get_by_id(session, domain_id)
            if not custom_domain:
                return None

            custom_domain.status = status
            custom_domain.last_check_at = datetime.now(timezone.utc)
            custom_domain.updated_at = datetime.now(timezone.utc)

            if status == DomainStatus.VERIFIED:
                custom_domain.verified_at = datetime.now(timezone.utc)
            elif status == DomainStatus.ACTIVE:
                # ACTIVE implies verified, set both timestamps
                if not custom_domain.verified_at:
                    custom_domain.verified_at = datetime.now(timezone.utc)
                custom_domain.ssl_provisioned_at = datetime.now(timezone.utc)
            elif status == DomainStatus.FAILED:
                custom_domain.last_error = error_message

            await session.commit()
            await session.refresh(custom_domain)

            logger.info(f"Updated custom domain status: {domain_id} -> {status.value}")
            return custom_domain

        except Exception as e:
            logger.error(f"Failed to update custom domain status {domain_id}: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_domains_pending_verification(
        session: AsyncSession, limit: int = 100
    ) -> List[CustomDomain]:
        """
        Get domains that need verification check (for background job)

        Args:
            session: Database session
            limit: Maximum number of domains to return

        Returns:
            List of CustomDomain instances pending verification
        """
        try:
            stmt = (
                select(CustomDomain)
                .where(
                    CustomDomain.status.in_(
                        [DomainStatus.PENDING, DomainStatus.VERIFYING, DomainStatus.VERIFIED]
                    )
                )
                .order_by(CustomDomain.last_check_at.asc().nulls_first())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get domains pending verification: {e}")
            return []

    @staticmethod
    async def domain_exists(session: AsyncSession, domain: str) -> bool:
        """
        Check if a domain already exists

        Args:
            session: Database session
            domain: Full domain name

        Returns:
            True if domain exists, False otherwise
        """
        try:
            stmt = select(func.count(CustomDomain.id)).where(
                CustomDomain.domain == domain.lower().strip()
            )
            result = await session.execute(stmt)
            count = result.scalar() or 0
            return count > 0
        except Exception as e:
            logger.error(f"Failed to check if domain exists {domain}: {e}")
            return False
