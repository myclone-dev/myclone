"""
Repository for custom_email_domains table database operations.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.custom_email_domain import CustomEmailDomain, EmailDomainStatus

logger = logging.getLogger(__name__)


class CustomEmailDomainRepository:
    """Repository for custom_email_domains table database operations."""

    @staticmethod
    async def create(
        session: AsyncSession,
        user_id: UUID,
        domain: str,
        from_email: str,
        from_name: Optional[str] = None,
        reply_to_email: Optional[str] = None,
        resend_domain_id: Optional[str] = None,
        resend_api_key: Optional[str] = None,
        dns_records: Optional[dict] = None,
        status: EmailDomainStatus = EmailDomainStatus.PENDING,
    ) -> CustomEmailDomain:
        """Create a new custom email domain."""
        try:
            custom_email_domain = CustomEmailDomain(
                user_id=user_id,
                domain=domain.lower().strip(),
                from_email=from_email.lower().strip(),
                from_name=from_name,
                reply_to_email=reply_to_email.lower().strip() if reply_to_email else None,
                resend_domain_id=resend_domain_id,
                resend_api_key=resend_api_key,
                dns_records=dns_records,
                status=status,
            )
            session.add(custom_email_domain)
            await session.commit()
            await session.refresh(custom_email_domain)
            logger.info(f"Created custom email domain: {custom_email_domain.id} for user {user_id}")
            return custom_email_domain
        except Exception as e:
            logger.error(f"Failed to create custom email domain: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_by_id(session: AsyncSession, domain_id: UUID) -> Optional[CustomEmailDomain]:
        """Get a custom email domain by ID."""
        try:
            stmt = select(CustomEmailDomain).where(CustomEmailDomain.id == domain_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get custom email domain by ID {domain_id}: {e}")
            return None

    @staticmethod
    async def get_by_user_id(session: AsyncSession, user_id: UUID) -> list[CustomEmailDomain]:
        """Get all custom email domains for a user."""
        try:
            stmt = (
                select(CustomEmailDomain)
                .where(CustomEmailDomain.user_id == user_id)
                .order_by(CustomEmailDomain.created_at.desc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get custom email domains for user {user_id}: {e}")
            return []

    @staticmethod
    async def get_verified_by_user_id(
        session: AsyncSession, user_id: UUID
    ) -> Optional[CustomEmailDomain]:
        """Get the verified custom email domain for a user (if any)."""
        try:
            stmt = (
                select(CustomEmailDomain)
                .where(
                    CustomEmailDomain.user_id == user_id,
                    CustomEmailDomain.status == EmailDomainStatus.VERIFIED,
                )
                .order_by(CustomEmailDomain.verified_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get verified email domain for user {user_id}: {e}")
            return None

    @staticmethod
    async def get_by_domain(session: AsyncSession, domain: str) -> Optional[CustomEmailDomain]:
        """Get a custom email domain by domain name."""
        try:
            stmt = select(CustomEmailDomain).where(
                CustomEmailDomain.domain == domain.lower().strip()
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get custom email domain by domain {domain}: {e}")
            return None

    @staticmethod
    async def count_by_user_id(session: AsyncSession, user_id: UUID) -> int:
        """Count custom email domains for a user."""
        try:
            stmt = select(func.count(CustomEmailDomain.id)).where(
                CustomEmailDomain.user_id == user_id
            )
            result = await session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Failed to count custom email domains for user {user_id}: {e}")
            return 0

    @staticmethod
    async def update(
        session: AsyncSession,
        domain_id: UUID,
        user_id: UUID,
        **kwargs,
    ) -> Optional[CustomEmailDomain]:
        """Update a custom email domain with ownership verification."""
        try:
            domain = await CustomEmailDomainRepository.get_by_id(session, domain_id)
            if not domain or domain.user_id != user_id:
                logger.warning(
                    f"Custom email domain {domain_id} not found or not owned by user {user_id}"
                )
                return None

            # Update allowed fields
            allowed_fields = {
                "from_email",
                "from_name",
                "reply_to_email",
                "resend_domain_id",
                "resend_api_key",
                "status",
                "dns_records",
                "verified_at",
                "last_verification_attempt",
            }

            for key, value in kwargs.items():
                if key in allowed_fields and hasattr(domain, key):
                    # Lowercase email fields
                    if key in ("from_email", "reply_to_email") and value:
                        value = value.lower().strip()
                    setattr(domain, key, value)

            domain.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(domain)
            logger.info(f"Updated custom email domain: {domain_id}")
            return domain
        except Exception as e:
            logger.error(f"Failed to update custom email domain {domain_id}: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def update_status(
        session: AsyncSession,
        domain_id: UUID,
        user_id: UUID,
        status: EmailDomainStatus,
        dns_records: Optional[dict] = None,
    ) -> Optional[CustomEmailDomain]:
        """Update the status of a custom email domain."""
        update_data = {
            "status": status,
            "last_verification_attempt": datetime.now(timezone.utc),
        }

        if dns_records is not None:
            update_data["dns_records"] = dns_records

        if status == EmailDomainStatus.VERIFIED:
            update_data["verified_at"] = datetime.now(timezone.utc)

        return await CustomEmailDomainRepository.update(session, domain_id, user_id, **update_data)

    @staticmethod
    async def delete(session: AsyncSession, domain_id: UUID, user_id: UUID) -> bool:
        """Delete a custom email domain with ownership verification."""
        try:
            domain = await CustomEmailDomainRepository.get_by_id(session, domain_id)
            if not domain or domain.user_id != user_id:
                logger.warning(
                    f"Custom email domain {domain_id} not found or not owned by user {user_id}"
                )
                return False

            await session.delete(domain)
            await session.commit()
            logger.info(f"Deleted custom email domain: {domain_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete custom email domain {domain_id}: {e}")
            await session.rollback()
            raise
