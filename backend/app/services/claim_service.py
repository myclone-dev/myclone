"""
Claim account service for users created via auto-onboard endpoint

This service handles claim code generation, verification, and account claiming
for users who were created without login credentials.
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.password_service import PasswordService
from shared.database.models.user import AuthDetail, User
from shared.database.repositories.user_repository import UserRepository
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class ClaimService:
    """
    Service for account claiming operations

    Handles:
    - Claim code generation (URL-safe random tokens)
    - Code verification (expiry, attempts tracking)
    - Account claiming (username, email, password setup)
    """

    def __init__(self):
        """
        Initialize claim service

        Dependencies:
        - PasswordService for password hashing
        - UserRepository for database operations
        """
        self.logger = logging.getLogger(__name__)
        self.password_service = PasswordService()

        # Claim code configuration (7 days expiry)
        self.claim_code_expiry_days = 7
        self.max_claim_attempts = 5
        self.grace_period_minutes = 5  # Grace period to prevent race conditions

        self.logger.info(
            f"ClaimService initialized with {self.claim_code_expiry_days}d expiry, "
            f"{self.max_claim_attempts} max attempts, {self.grace_period_minutes}min grace period"
        )

    def generate_claim_code(self) -> tuple[str, datetime]:
        """
        Generate a secure claim code and expiration timestamp

        Returns:
            Tuple of (code, expiration_datetime)
            - code: URL-safe random token (32 bytes = ~43 chars base64)
            - expiration: Datetime when code expires (7 days from now)

        Example:
            >>> service = ClaimService()
            >>> code, expires = service.generate_claim_code()
            >>> len(code) >= 40  # URL-safe base64 token
            True
        """
        # Generate cryptographically secure URL-safe token
        # 32 bytes = 43 characters in base64 URL-safe encoding
        code = secrets.token_urlsafe(32)

        # Calculate expiration (7 days from now)
        expiration = datetime.now(timezone.utc) + timedelta(days=self.claim_code_expiry_days)

        self.logger.debug(f"Generated claim code (expires: {expiration})")
        return (code, expiration)

    async def update_user_claim_code(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> tuple[str, datetime]:
        """
        Generate and store claim code for a user

        Args:
            session: Database session
            user_id: User UUID to generate code for

        Returns:
            Tuple of (claim_code, expiration_datetime)

        Raises:
            HTTPException: If user not found or already has auth credentials

        Example:
            >>> service = ClaimService()
            >>> code, expires = await service.update_user_claim_code(session, user_id)
        """
        try:
            # Get user
            user = await UserRepository.get_by_id(session, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Check if user already has auth_details (already claimed)
            password_auth = await UserRepository.get_password_auth(session, user_id)
            if password_auth:
                raise HTTPException(
                    status_code=400, detail="Account already claimed (password auth exists)"
                )

            # Generate new claim code
            claim_code, expires_at = self.generate_claim_code()

            # Update user record
            user.claim_code = claim_code
            user.claim_code_expires_at = expires_at
            user.claim_code_attempts = 0
            user.claim_code_generated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(user)

            self.logger.info(f"✅ Claim code generated for user {user_id}")
            return (claim_code, expires_at)

        except HTTPException:
            raise
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "user_id": str(user_id),
                },
                tags={
                    "component": "claim",
                    "operation": "update_user_claim_code",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to generate claim code for user {user_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate claim code")

    async def verify_claim_code(self, session: AsyncSession, code: str) -> User:
        """
        Verify claim code is valid (exists, not expired, not max attempts)

        Includes grace period to prevent race conditions where code expires between
        initial verification and final submission (e.g., user filling out form).

        Args:
            session: Database session
            code: Claim code to verify

        Returns:
            User object if code is valid

        Raises:
            HTTPException: If code invalid, expired, or too many attempts

        Example:
            >>> service = ClaimService()
            >>> user = await service.verify_claim_code(session, "abc123...")
        """
        try:
            # Find user by claim code
            result = await session.execute(select(User).where(User.claim_code == code))
            user = result.scalar_one_or_none()

            if not user:
                raise HTTPException(status_code=404, detail="Invalid claim code")

            # Check expiration with grace period to prevent race conditions
            # Grace period prevents UX issue where code expires while user is filling form
            grace_period = timedelta(minutes=self.grace_period_minutes)
            if not user.claim_code_expires_at or (
                user.claim_code_expires_at + grace_period < datetime.now(timezone.utc)
            ):
                raise HTTPException(status_code=400, detail="Claim code has expired")

            # Check attempts
            if user.claim_code_attempts >= self.max_claim_attempts:
                raise HTTPException(
                    status_code=429, detail="Too many claim attempts. Please request a new code."
                )

            # Check if already claimed (has password auth)
            password_auth = await UserRepository.get_password_auth(session, user.id)
            if password_auth:
                raise HTTPException(status_code=400, detail="Account already claimed")

            self.logger.info(f"✅ Claim code verified for user {user.id}")
            return user

        except HTTPException:
            raise
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "code_length": len(code),
                },
                tags={
                    "component": "claim",
                    "operation": "verify_claim_code",
                    "severity": "medium",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Failed to verify claim code: {e}")
            raise HTTPException(status_code=500, detail="Failed to verify claim code")

    async def submit_claim(
        self,
        session: AsyncSession,
        code: str,
        username: str,
        email: str,
        password: str,
    ) -> User:
        """
        Process claim submission: update user details and create password auth

        Args:
            session: Database session
            code: Valid claim code
            username: New username (validated for uniqueness)
            email: New email (validated for uniqueness)
            password: Plain password (will be hashed)

        Returns:
            Updated user object

        Raises:
            HTTPException: If validation fails or claim processing fails

        Example:
            >>> service = ClaimService()
            >>> user = await service.submit_claim(session, code, "john_doe", "john@example.com", "SecurePass123")
        """
        try:
            # Verify claim code first
            user = await self.verify_claim_code(session, code)

            # Validate username availability (if changed)
            if username != user.username:
                existing_user = await UserRepository.get_by_username(session, username)
                if existing_user:
                    raise HTTPException(status_code=400, detail="Username already taken")

            # Validate email availability (if changed and not auto-generated)
            if email != user.email and not email.endswith("@auto-generated.local"):
                existing_user = await UserRepository.get_by_email(session, email)
                if existing_user:
                    raise HTTPException(status_code=400, detail="Email already registered")

            # Validate password strength
            is_valid, error_msg = self.password_service.validate_password_strength(password)
            if not is_valid:
                raise HTTPException(status_code=400, detail=error_msg)

            # Hash password
            hashed_password = await self.password_service.hash_password(password)

            # Update user record
            user.username = username
            user.email = email
            user.email_confirmed = True  # Auto-confirm since they verified claim code

            # Ensure onboarding is fully completed
            from shared.database.models.user import OnboardingStatus

            user.onboarding_status = OnboardingStatus.FULLY_ONBOARDED

            # Clear claim code fields (cleanup)
            user.claim_code = None
            user.claim_code_expires_at = None
            user.claim_code_attempts = 0  # Reset to 0 (NOT NULL constraint)
            user.claim_code_generated_at = None

            # Create password auth record
            auth_detail = AuthDetail(
                user_id=user.id,
                auth_type="password",
                hashed_password=hashed_password,
                failed_login_attempts=0,
                email_verified_at=datetime.now(timezone.utc),  # Mark as verified
            )
            session.add(auth_detail)

            await session.commit()
            await session.refresh(user)

            self.logger.info(f"✅ Account claimed successfully for user {user.id}")
            return user

        except HTTPException:
            raise
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "username": username,
                    "email": email,
                },
                tags={
                    "component": "claim",
                    "operation": "submit_claim",
                    "severity": "high",  # Critical - claim flow broken
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Failed to process claim submission: {e}")
            raise HTTPException(status_code=500, detail="Failed to claim account")

    async def increment_claim_attempts(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        """
        Increment claim code attempt counter for rate limiting

        Args:
            session: Database session
            user_id: User UUID

        Example:
            >>> service = ClaimService()
            >>> await service.increment_claim_attempts(session, user_id)
        """
        try:
            user = await UserRepository.get_by_id(session, user_id)
            if user and user.claim_code:
                user.claim_code_attempts += 1
                await session.commit()
                self.logger.debug(
                    f"Incremented claim attempts for user {user_id}: {user.claim_code_attempts}"
                )

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "user_id": str(user_id),
                },
                tags={
                    "component": "claim",
                    "operation": "increment_claim_attempts",
                    "severity": "low",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to increment claim attempts for user {user_id}: {e}")
            # Don't raise - this is non-critical

    async def check_username_available(self, session: AsyncSession, username: str) -> bool:
        """
        Check if username is available (not taken by another user)

        Args:
            session: Database session
            username: Username to check

        Returns:
            True if available, False if taken

        Example:
            >>> service = ClaimService()
            >>> is_available = await service.check_username_available(session, "john_doe")
        """
        try:
            existing_user = await UserRepository.get_by_username(session, username)
            is_available = existing_user is None

            self.logger.debug(f"Username '{username}' availability: {is_available}")
            return is_available

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "username": username,
                },
                tags={
                    "component": "claim",
                    "operation": "check_username_available",
                    "severity": "low",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Failed to check username availability: {e}")
            # Return False on error (safer to assume unavailable)
            return False
