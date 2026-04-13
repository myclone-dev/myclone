"""
Auth rate limiting service for account lockout protection

This service handles failed login attempt tracking and account lockouts using
the auth_details table (failed_login_attempts, locked_until fields).

Each auth method (password, OAuth) has independent lockout tracking.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database.models.user import AuthDetail
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class AuthRateLimitingService:
    """
    Service for authentication rate limiting and account lockout

    Uses PostgreSQL auth_details table fields for persistent lockout state:
    - failed_login_attempts: Counter for consecutive failures
    - locked_until: Timestamp when lockout expires

    Each AuthDetail record (one per auth method) has independent tracking.
    """

    def __init__(self):
        """Initialize auth rate limiting service"""
        self.logger = logging.getLogger(__name__)
        self.max_attempts = settings.max_failed_login_attempts
        self.lockout_duration = timedelta(minutes=settings.account_lockout_duration_minutes)

    async def record_failed_login(
        self,
        session: AsyncSession,
        auth_detail: AuthDetail,
    ) -> int:
        """
        Record a failed login attempt and increment counter

        If max attempts reached, locks the account for configured duration.

        Args:
            session: Database session
            auth_detail: AuthDetail record to update

        Returns:
            New failed_login_attempts count

        Example:
            >>> service = AuthRateLimitingService()
            >>> attempts = await service.record_failed_login(session, auth_detail)
            >>> if attempts >= 5:
            ...     print("Account locked!")
        """
        try:
            # Increment failed attempts
            auth_detail.failed_login_attempts += 1
            attempts = auth_detail.failed_login_attempts

            # Lock account if max attempts reached
            if attempts >= self.max_attempts:
                auth_detail.locked_until = datetime.now(timezone.utc) + self.lockout_duration
                self.logger.warning(
                    f"Account locked for auth_detail {auth_detail.id} (user {auth_detail.user_id}) "
                    f"after {attempts} failed attempts. Locked until {auth_detail.locked_until}"
                )

                # Capture in Sentry for security monitoring
                capture_exception_with_context(
                    Exception(f"Account locked after {attempts} failed login attempts"),
                    extra={
                        "auth_detail_id": str(auth_detail.id),
                        "user_id": str(auth_detail.user_id),
                        "auth_type": auth_detail.auth_type,
                        "failed_attempts": attempts,
                        "locked_until": str(auth_detail.locked_until),
                    },
                    tags={
                        "component": "auth",
                        "operation": "account_lockout",
                        "severity": "high",  # Security event
                        "user_facing": "true",
                    },
                )
            else:
                self.logger.info(
                    f"Failed login attempt {attempts}/{self.max_attempts} for auth_detail {auth_detail.id}"
                )

            # Commit changes
            await session.commit()
            await session.refresh(auth_detail)

            return attempts

        except Exception as e:
            await session.rollback()
            capture_exception_with_context(
                e,
                extra={
                    "auth_detail_id": str(auth_detail.id),
                    "user_id": str(auth_detail.user_id),
                },
                tags={
                    "component": "auth",
                    "operation": "record_failed_login",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"Failed to record failed login attempt: {e}")
            raise

    async def is_account_locked(
        self,
        auth_detail: AuthDetail,
    ) -> bool:
        """
        Check if account is currently locked

        Accounts are locked if:
        1. locked_until timestamp exists
        2. locked_until is in the future (not expired)

        Args:
            auth_detail: AuthDetail record to check

        Returns:
            True if account is locked, False otherwise

        Example:
            >>> service = AuthRateLimitingService()
            >>> if await service.is_account_locked(auth_detail):
            ...     return {"error": "Account locked. Try again later."}
        """
        if not auth_detail.locked_until:
            return False

        # Check if lock has expired
        now = datetime.now(timezone.utc)
        is_locked = auth_detail.locked_until > now

        if is_locked:
            self.logger.debug(
                f"Account locked for auth_detail {auth_detail.id}, "
                f"unlocks at {auth_detail.locked_until}"
            )
        else:
            self.logger.debug(
                f"Account lock expired for auth_detail {auth_detail.id}, "
                f"was locked until {auth_detail.locked_until}"
            )

        return is_locked

    async def reset_failed_attempts(
        self,
        session: AsyncSession,
        auth_detail: AuthDetail,
    ) -> None:
        """
        Reset failed login attempts to 0 after successful login

        Also clears locked_until timestamp if set.

        Args:
            session: Database session
            auth_detail: AuthDetail record to update

        Example:
            >>> service = AuthRateLimitingService()
            >>> # After successful password verification
            >>> await service.reset_failed_attempts(session, auth_detail)
        """
        try:
            # Reset counters
            auth_detail.failed_login_attempts = 0
            auth_detail.locked_until = None

            # Commit changes
            await session.commit()
            await session.refresh(auth_detail)

            self.logger.info(
                f"Reset failed login attempts for auth_detail {auth_detail.id} after successful login"
            )

        except Exception as e:
            await session.rollback()
            capture_exception_with_context(
                e,
                extra={
                    "auth_detail_id": str(auth_detail.id),
                    "user_id": str(auth_detail.user_id),
                },
                tags={
                    "component": "auth",
                    "operation": "reset_failed_attempts",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"Failed to reset failed login attempts: {e}")
            raise

    async def get_lockout_info(
        self,
        auth_detail: AuthDetail,
    ) -> dict | None:
        """
        Get lockout information for user-friendly error messages

        Returns lockout details if account is locked, None otherwise.

        Args:
            auth_detail: AuthDetail record to check

        Returns:
            Dict with lockout info or None:
            - locked: bool
            - locked_until: datetime
            - remaining_minutes: int
            - attempts: int

        Example:
            >>> service = AuthRateLimitingService()
            >>> info = await service.get_lockout_info(auth_detail)
            >>> if info:
            ...     return {"error": f"Account locked for {info['remaining_minutes']} minutes"}
        """
        if not await self.is_account_locked(auth_detail):
            return None

        now = datetime.now(timezone.utc)
        remaining = auth_detail.locked_until - now
        remaining_minutes = int(remaining.total_seconds() / 60)

        return {
            "locked": True,
            "locked_until": auth_detail.locked_until,
            "remaining_minutes": max(1, remaining_minutes),  # At least 1 minute
            "attempts": auth_detail.failed_login_attempts,
        }
