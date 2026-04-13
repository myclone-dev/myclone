"""
Persona Access Repository - Database operations for OTP verification and persona-visitor assignments
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, select

from shared.database.models.database import async_session_maker
from shared.database.models.persona_access import PersonaAccessOTP, PersonaVisitor, VisitorWhitelist

logger = logging.getLogger(__name__)


class PersonaAccessRepository:
    """Repository for persona access control operations (OTP and visitor assignments)"""

    # ==================== OTP Operations ====================

    async def create_otp(
        self,
        persona_id: UUID,
        email: str,
        expires_in_minutes: int = 5,
    ) -> PersonaAccessOTP:
        """
        Create OTP for persona access verification

        Args:
            persona_id: Persona UUID
            email: Visitor's email (normalized to lowercase)
            expires_in_minutes: OTP expiry time in minutes (default: 5)

        Returns:
            Created PersonaAccessOTP instance with otp_code

        Raises:
            ValueError: If rate limit exceeded (max 5 OTPs per hour)
        """
        async with async_session_maker() as session:
            try:
                # Normalize email
                normalized_email = email.lower().strip()

                # SECURITY: Rate limiting - prevent OTP spam
                recent_count = await self.get_recent_otp_count(
                    persona_id, normalized_email, hours=1
                )
                if recent_count >= 6:
                    logger.warning(
                        f"Rate limit exceeded for persona {persona_id}, email={normalized_email} "
                        f"({recent_count} OTPs in last hour)"
                    )
                    raise ValueError("Rate limit exceeded. Please try again later.")

                # SECURITY: Generate cryptographically secure 6-digit OTP
                # Using secrets module instead of random for unpredictability
                otp_code = str(secrets.randbelow(900000) + 100000)

                # Calculate expiry time
                expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)

                otp = PersonaAccessOTP(
                    persona_id=persona_id,
                    email=normalized_email,
                    otp_code=otp_code,
                    expires_at=expires_at,
                    attempts=0,
                    max_attempts=3,
                )

                session.add(otp)
                await session.commit()
                await session.refresh(otp)

                logger.info(
                    f"Created OTP for persona {persona_id}, email={normalized_email}, "
                    f"expires_at={expires_at}"
                )
                return otp

            except ValueError:
                # Re-raise rate limit errors without rollback
                raise
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating OTP for persona {persona_id}: {e}")
                raise

    async def verify_otp(
        self, persona_id: UUID, email: str, otp_code: str
    ) -> tuple[bool, Optional[str]]:
        """
        Verify OTP code

        Args:
            persona_id: Persona UUID
            email: Visitor's email
            otp_code: 6-digit OTP code to verify

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
            - (True, None) if OTP is valid
            - (False, error_message) if OTP is invalid/expired
        """
        async with async_session_maker() as session:
            try:
                normalized_email = email.lower().strip()

                # Find most recent unverified OTP for this persona/email
                stmt = (
                    select(PersonaAccessOTP)
                    .where(
                        PersonaAccessOTP.persona_id == persona_id,
                        PersonaAccessOTP.email == normalized_email,
                        PersonaAccessOTP.verified_at.is_(None),  # Not yet verified
                    )
                    .order_by(PersonaAccessOTP.created_at.desc())
                    .limit(1)  # Only get the most recent one
                )
                result = await session.execute(stmt)
                otp = result.scalar_one_or_none()

                if not otp:
                    return False, "No OTP found. Please request a new one."

                # Check if OTP has expired
                if datetime.now(timezone.utc) > otp.expires_at:
                    return False, "OTP has expired. Please request a new one."

                # Check if max attempts reached
                if otp.attempts >= otp.max_attempts:
                    return False, "Maximum verification attempts reached. Please request a new OTP."

                # Increment attempts
                otp.attempts += 1

                # Check if OTP code matches
                if otp.otp_code != otp_code:
                    await session.commit()
                    remaining = otp.max_attempts - otp.attempts
                    return False, f"Invalid OTP. {remaining} attempt(s) remaining."

                # OTP is valid - mark as verified
                otp.verified_at = datetime.now(timezone.utc)
                await session.commit()

                logger.info(
                    f"OTP verified successfully for persona {persona_id}, email={normalized_email}"
                )
                return True, None

            except Exception as e:
                await session.rollback()
                logger.error(f"Error verifying OTP: {e}")
                raise

    async def cleanup_expired_otps(self, hours_old: int = 24) -> int:
        """
        Delete expired OTPs older than specified hours

        Args:
            hours_old: Delete OTPs older than this many hours (default: 24)

        Returns:
            Number of OTPs deleted

        Note:
            Uses index on expires_at for efficient cleanup. For high-volume scenarios,
            consider implementing partition-based cleanup or a composite index
            (expires_at, created_at) if table scans become an issue.
        """
        async with async_session_maker() as session:
            try:
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_old)

                # Uses idx_persona_access_otps_expires index for efficient deletion
                stmt = delete(PersonaAccessOTP).where(PersonaAccessOTP.expires_at < cutoff_time)
                result = await session.execute(stmt)
                await session.commit()

                deleted_count = result.rowcount
                logger.info(f"Cleaned up {deleted_count} expired OTPs older than {hours_old} hours")
                return deleted_count

            except Exception as e:
                await session.rollback()
                logger.error(f"Error cleaning up expired OTPs: {e}")
                raise

    async def get_recent_otp_count(self, persona_id: UUID, email: str, hours: int = 1) -> int:
        """
        Count OTPs created for a persona/email in the last N hours (for rate limiting)

        Args:
            persona_id: Persona UUID
            email: Visitor's email
            hours: Look back this many hours (default: 1)

        Returns:
            Count of OTPs created
        """
        async with async_session_maker() as session:
            try:
                normalized_email = email.lower().strip()
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

                stmt = select(PersonaAccessOTP).where(
                    PersonaAccessOTP.persona_id == persona_id,
                    PersonaAccessOTP.email == normalized_email,
                    PersonaAccessOTP.created_at >= cutoff_time,
                )
                result = await session.execute(stmt)
                return len(list(result.scalars().all()))

            except Exception as e:
                logger.error(f"Error counting recent OTPs: {e}")
                return 0

    # ==================== Persona-Visitor Assignment Operations ====================

    async def assign_visitor_to_persona(
        self, persona_id: UUID, visitor_id: UUID
    ) -> Optional[PersonaVisitor]:
        """
        Assign visitor to persona (create junction table entry)

        Args:
            persona_id: Persona UUID
            visitor_id: Visitor UUID

        Returns:
            Created PersonaVisitor instance or None if already exists
        """
        async with async_session_maker() as session:
            try:
                # Check if already assigned
                stmt = select(PersonaVisitor).where(
                    PersonaVisitor.persona_id == persona_id,
                    PersonaVisitor.visitor_id == visitor_id,
                )
                result = await session.execute(stmt)
                existing = result.scalar_one_or_none()

                if existing:
                    logger.info(f"Visitor {visitor_id} already assigned to persona {persona_id}")
                    return existing

                # Create new assignment
                assignment = PersonaVisitor(
                    persona_id=persona_id,
                    visitor_id=visitor_id,
                )

                session.add(assignment)
                await session.commit()
                await session.refresh(assignment)

                logger.info(f"Assigned visitor {visitor_id} to persona {persona_id}")
                return assignment

            except Exception as e:
                await session.rollback()
                logger.error(f"Error assigning visitor to persona: {e}")
                raise

    async def assign_multiple_visitors_to_persona(
        self, persona_id: UUID, visitor_ids: List[UUID]
    ) -> int:
        """
        Assign multiple visitors to a persona

        Args:
            persona_id: Persona UUID
            visitor_ids: List of visitor UUIDs

        Returns:
            Number of new assignments created
        """
        async with async_session_maker() as session:
            try:
                # Get existing assignments
                stmt = select(PersonaVisitor).where(
                    PersonaVisitor.persona_id == persona_id,
                    PersonaVisitor.visitor_id.in_(visitor_ids),
                )
                result = await session.execute(stmt)
                existing_visitor_ids = {pv.visitor_id for pv in result.scalars().all()}

                # Create new assignments for visitors not already assigned
                new_assignments = []
                for visitor_id in visitor_ids:
                    if visitor_id not in existing_visitor_ids:
                        new_assignments.append(
                            PersonaVisitor(persona_id=persona_id, visitor_id=visitor_id)
                        )

                if new_assignments:
                    session.add_all(new_assignments)
                    await session.commit()

                logger.info(f"Assigned {len(new_assignments)} new visitors to persona {persona_id}")
                return len(new_assignments)

            except Exception as e:
                await session.rollback()
                logger.error(f"Error assigning multiple visitors to persona: {e}")
                raise

    async def remove_visitor_from_persona(self, persona_id: UUID, visitor_id: UUID) -> bool:
        """
        Remove visitor from persona (delete junction table entry)

        Args:
            persona_id: Persona UUID
            visitor_id: Visitor UUID

        Returns:
            True if removed successfully
        """
        async with async_session_maker() as session:
            try:
                stmt = delete(PersonaVisitor).where(
                    PersonaVisitor.persona_id == persona_id,
                    PersonaVisitor.visitor_id == visitor_id,
                )
                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"Removed visitor {visitor_id} from persona {persona_id}")
                    return True

                logger.warning(f"Visitor {visitor_id} was not assigned to persona {persona_id}")
                return False

            except Exception as e:
                await session.rollback()
                logger.error(f"Error removing visitor from persona: {e}")
                raise

    async def is_visitor_allowed(self, persona_id: UUID, email: str) -> bool:
        """
        Check if visitor email is in persona's allowlist

        Args:
            persona_id: Persona UUID
            email: Visitor's email

        Returns:
            True if visitor is allowed to access this persona
        """
        async with async_session_maker() as session:
            try:
                normalized_email = email.lower().strip()

                # Join visitor_whitelist and persona_visitors to check access
                stmt = (
                    select(PersonaVisitor)
                    .join(VisitorWhitelist, VisitorWhitelist.id == PersonaVisitor.visitor_id)
                    .where(
                        PersonaVisitor.persona_id == persona_id,
                        VisitorWhitelist.email == normalized_email,
                    )
                )
                result = await session.execute(stmt)
                assignment = result.scalar_one_or_none()

                return assignment is not None

            except Exception as e:
                logger.error(f"Error checking visitor access: {e}")
                return False

    async def get_visitor_count_for_persona(self, persona_id: UUID) -> int:
        """
        Get count of visitors assigned to a persona

        Args:
            persona_id: Persona UUID

        Returns:
            Number of visitors assigned
        """
        async with async_session_maker() as session:
            try:
                stmt = select(PersonaVisitor).where(PersonaVisitor.persona_id == persona_id)
                result = await session.execute(stmt)
                return len(list(result.scalars().all()))

            except Exception as e:
                logger.error(f"Error counting visitors for persona {persona_id}: {e}")
                return 0


# Singleton instance
_persona_access_repository: Optional[PersonaAccessRepository] = None


def get_persona_access_repository() -> PersonaAccessRepository:
    """Get singleton persona access repository instance"""
    global _persona_access_repository
    if _persona_access_repository is None:
        _persona_access_repository = PersonaAccessRepository()
    return _persona_access_repository
