"""
Password service for hashing, verification, and strength validation

This service handles all password-related operations using bcrypt for secure hashing.
All operations are CPU-intensive, so we use asyncio.to_thread() to avoid blocking
the event loop.
"""

import logging
import re
from typing import Optional

import bcrypt

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class PasswordService:
    """
    Service for password hashing, verification, and validation

    Uses bcrypt algorithm directly for secure password hashing.
    All password operations are CPU-intensive and run in thread pool.
    """

    def __init__(self):
        """
        Initialize password service

        Bcrypt configuration:
        - Rounds: 12 (configurable via settings, default is secure)
        - Automatic salt generation
        - Automatic hash versioning
        """
        self.logger = logging.getLogger(__name__)
        self.bcrypt_rounds = settings.bcrypt_rounds

        self.logger.info(f"PasswordService initialized with bcrypt rounds={self.bcrypt_rounds}")

    async def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt

        This operation is CPU-intensive and runs in a thread pool to avoid
        blocking the async event loop.

        Args:
            password: Plain text password to hash

        Returns:
            Bcrypt hash string (includes salt and algorithm version)

        Example:
            >>> service = PasswordService()
            >>> hash1 = await service.hash_password("MySecurePass123")
            >>> hash2 = await service.hash_password("MySecurePass123")
            >>> hash1 != hash2  # Different salts, different hashes
            True
        """
        try:
            # Convert password to bytes
            password_bytes = password.encode("utf-8")

            # Generate salt with configured rounds
            salt = bcrypt.gensalt(rounds=self.bcrypt_rounds)

            # Run CPU-intensive bcrypt hash in thread pool
            hashed_bytes = await self._run_in_thread(bcrypt.hashpw, password_bytes, salt)

            # Convert bytes back to string for database storage
            hashed_str = hashed_bytes.decode("utf-8")

            self.logger.debug("Password hashed successfully")
            return hashed_str

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "password_length": len(password),
                },
                tags={
                    "component": "password",
                    "operation": "hash_password",
                    "severity": "high",  # Critical - auth won't work
                    "user_facing": "true",
                },
            )
            self.logger.error(f"Failed to hash password: {e}")
            raise

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its bcrypt hash

        This operation is CPU-intensive and runs in a thread pool to avoid
        blocking the async event loop.

        Args:
            plain_password: Plain text password to verify
            hashed_password: Bcrypt hash to verify against (stored as string in DB)

        Returns:
            True if password matches hash, False otherwise

        Example:
            >>> service = PasswordService()
            >>> hash = await service.hash_password("MySecurePass123")
            >>> await service.verify_password("MySecurePass123", hash)
            True
            >>> await service.verify_password("WrongPassword", hash)
            False
        """
        try:
            # Convert password and hash to bytes
            password_bytes = plain_password.encode("utf-8")
            hash_bytes = hashed_password.encode("utf-8")

            # Run CPU-intensive bcrypt verification in thread pool
            is_valid = await self._run_in_thread(bcrypt.checkpw, password_bytes, hash_bytes)

            self.logger.debug(f"Password verification: {'success' if is_valid else 'failed'}")
            return is_valid

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "password_length": len(plain_password),
                    "hash_length": len(hashed_password),
                },
                tags={
                    "component": "password",
                    "operation": "verify_password",
                    "severity": "high",  # Critical - login won't work
                    "user_facing": "true",
                },
            )
            self.logger.error(f"Failed to verify password: {e}")
            raise

    def validate_password_strength(self, password: str) -> tuple[bool, Optional[str]]:
        """
        Validate password meets strength requirements

        Requirements (from settings):
        - Minimum length (default: 8 characters)
        - At least 1 uppercase letter (if enabled)
        - At least 1 lowercase letter (if enabled)
        - At least 1 number (if enabled)
        - At least 1 special character (if enabled)

        Args:
            password: Plain text password to validate

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if password meets requirements
            - error_message: Human-readable error if invalid, None if valid

        Example:
            >>> service = PasswordService()
            >>> service.validate_password_strength("weak")
            (False, "Password must be at least 8 characters long")
            >>> service.validate_password_strength("StrongPass123")
            (True, None)
        """
        # Check minimum length
        if len(password) < settings.password_min_length:
            return (
                False,
                f"Password must be at least {settings.password_min_length} characters long",
            )

        # Check uppercase requirement
        if settings.password_require_uppercase and not re.search(r"[A-Z]", password):
            return (False, "Password must contain at least one uppercase letter")

        # Check lowercase requirement
        if settings.password_require_lowercase and not re.search(r"[a-z]", password):
            return (False, "Password must contain at least one lowercase letter")

        # Check number requirement
        if settings.password_require_number and not re.search(r"\d", password):
            return (False, "Password must contain at least one number")

        # Check special character requirement
        if settings.password_require_special and not re.search(
            r"[!@#$%^&*(),.?\":{}|<>]", password
        ):
            return (
                False,
                'Password must contain at least one special character (!@#$%^&*(),.?":{}|<>)',
            )

        # All checks passed
        return (True, None)

    async def _run_in_thread(self, func, *args, **kwargs):
        """
        Run a synchronous function in a thread pool

        Helper method to run CPU-intensive operations (bcrypt hashing/verification)
        in a thread pool to avoid blocking the async event loop.

        Args:
            func: Synchronous function to run
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func
        """
        import asyncio

        return await asyncio.to_thread(func, *args, **kwargs)
