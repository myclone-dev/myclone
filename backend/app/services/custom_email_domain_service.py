"""
Custom Email Domain Service for whitelabel email sending.

This service manages custom email domains through the Resend API, allowing
enterprise users to send emails from their own domain instead of myclone.is.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import resend
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database.models.custom_email_domain import CustomEmailDomain, EmailDomainStatus
from shared.database.repositories.custom_email_domain_repository import (
    CustomEmailDomainRepository,
)
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)

# Tier IDs that can use custom email domains (Enterprise=3)
# These match the numeric tier_id values in the tier_plans table
ENTERPRISE_TIER_IDS = {3}


@dataclass
class SenderConfig:
    """Configuration for email sending."""

    from_email: str
    from_name: Optional[str]
    reply_to: Optional[str]
    resend_api_key: str

    @property
    def formatted_from(self) -> str:
        """Get formatted 'from' address for email headers."""
        if self.from_name:
            return f"{self.from_name} <{self.from_email}>"
        return self.from_email


class CustomEmailDomainService:
    """
    Service for managing custom email domains via Resend API.

    This service handles:
    - Creating domains in Resend
    - Verifying DNS records
    - Fetching domain status and DNS records
    - Deleting domains
    """

    def __init__(self, api_key: str | None = None):
        """Initialize service with Resend API key."""
        self.api_key = api_key or settings.resend_api_key
        self.logger = logging.getLogger(__name__)

        if self.api_key:
            resend.api_key = self.api_key
        else:
            self.logger.warning("Resend API key not configured")

    def _validate_domain(self, domain: str) -> str:
        """
        Validate and normalize domain name.

        Args:
            domain: Raw domain input

        Returns:
            Normalized domain name

        Raises:
            ValueError: If domain is invalid
        """
        domain = domain.lower().strip()

        # Remove any protocol prefix
        domain = re.sub(r"^https?://", "", domain)
        # Remove trailing slashes and paths
        domain = domain.split("/")[0]
        # Remove any port
        domain = domain.split(":")[0]

        # Basic domain validation
        domain_pattern = r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$"
        if not re.match(domain_pattern, domain):
            raise ValueError(f"Invalid domain format: {domain}")

        # Block common free email domains
        blocked_domains = {
            "gmail.com",
            "yahoo.com",
            "hotmail.com",
            "outlook.com",
            "aol.com",
            "icloud.com",
            "mail.com",
            "protonmail.com",
            "zoho.com",
        }
        if domain in blocked_domains:
            raise ValueError(f"Cannot use free email provider domain: {domain}")

        return domain

    def _validate_email(self, email: str, domain: str) -> str:
        """
        Validate email address belongs to the specified domain.

        Args:
            email: Email address to validate
            domain: Domain the email should belong to

        Returns:
            Normalized email address

        Raises:
            ValueError: If email is invalid or doesn't match domain
        """
        email = email.lower().strip()

        # Basic email validation
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise ValueError(f"Invalid email format: {email}")

        # Ensure email belongs to the domain
        email_domain = email.split("@")[1]
        if email_domain != domain:
            raise ValueError(f"Email must belong to domain {domain}, got {email_domain}")

        return email

    async def check_enterprise_access(self, session: AsyncSession, user_id: UUID) -> bool:
        """
        Check if user has enterprise access for custom email domains.

        Args:
            session: Database session
            user_id: User ID to check

        Returns:
            True if user has enterprise access
        """
        from shared.database.models.tier_plan import SubscriptionStatus, UserSubscription

        try:
            from sqlalchemy import select

            stmt = select(UserSubscription).where(
                UserSubscription.user_id == user_id,
                UserSubscription.status == SubscriptionStatus.ACTIVE,
            )
            result = await session.execute(stmt)
            subscription = result.scalar_one_or_none()

            if not subscription:
                return False

            return subscription.tier_id in ENTERPRISE_TIER_IDS

        except Exception as e:
            self.logger.error(f"Failed to check enterprise access for user {user_id}: {e}")
            return False

    async def create_domain(
        self,
        session: AsyncSession,
        user_id: UUID,
        domain: str,
        from_email: str,
        from_name: Optional[str] = None,
        reply_to_email: Optional[str] = None,
    ) -> CustomEmailDomain:
        """
        Create a new custom email domain.

        This creates the domain in Resend and stores it in the database
        with the DNS records needed for verification.

        Args:
            session: Database session
            user_id: Owner user ID
            domain: Domain name (e.g., 'acme.com')
            from_email: Sender email (e.g., 'hello@acme.com')
            from_name: Optional sender display name
            reply_to_email: Optional reply-to address

        Returns:
            Created CustomEmailDomain

        Raises:
            ValueError: If validation fails
            PermissionError: If user doesn't have enterprise access
            Exception: If Resend API fails
        """
        # Validate inputs
        domain = self._validate_domain(domain)
        from_email = self._validate_email(from_email, domain)
        if reply_to_email:
            reply_to_email = self._validate_email(reply_to_email, domain)

        # Check enterprise access
        has_access = await self.check_enterprise_access(session, user_id)
        if not has_access:
            raise PermissionError("Custom email domains require an Enterprise plan")

        # Check if domain already exists
        existing = await CustomEmailDomainRepository.get_by_domain(session, domain)
        if existing:
            raise ValueError(f"Domain {domain} is already registered")

        # Check user's domain limit (1 for now)
        count = await CustomEmailDomainRepository.count_by_user_id(session, user_id)
        if count >= 1:  # Enterprise limit: 1 domain
            raise ValueError("You have reached the maximum number of custom email domains")

        try:
            # Create domain in Resend
            self.logger.info(f"Creating domain {domain} in Resend for user {user_id}")

            resend_response = await asyncio.to_thread(resend.Domains.create, {"name": domain})

            self.logger.info(f"Resend domain created: {resend_response}")

            # Extract DNS records from response
            dns_records = resend_response.get("records", [])

            # Store in database
            custom_domain = await CustomEmailDomainRepository.create(
                session=session,
                user_id=user_id,
                domain=domain,
                from_email=from_email,
                from_name=from_name,
                reply_to_email=reply_to_email,
                resend_domain_id=resend_response.get("id"),
                dns_records=dns_records,
                status=EmailDomainStatus.PENDING,
            )

            self.logger.info(
                f"✅ Created custom email domain {domain} for user {user_id}: {custom_domain.id}"
            )

            return custom_domain

        except Exception as e:
            error_message = str(e).lower()

            # Handle Resend-specific errors with user-friendly messages
            if "already" in error_message or "registered" in error_message:
                self.logger.warning(f"Domain {domain} already registered in Resend: {e}")
                raise ValueError(
                    f"The domain {domain} is already registered. "
                    "If you previously added this domain, please contact support to recover it."
                )
            elif "invalid" in error_message:
                raise ValueError(f"Invalid domain format: {domain}")
            elif "rate limit" in error_message or "too many" in error_message:
                raise ValueError("Too many requests. Please try again in a few minutes.")

            capture_exception_with_context(
                e,
                extra={"user_id": str(user_id), "domain": domain},
                tags={
                    "component": "custom_email_domain",
                    "operation": "create_domain",
                    "severity": "high",
                },
            )
            self.logger.error(f"❌ Failed to create custom email domain {domain}: {e}")
            raise ValueError(f"Failed to register domain: {e}")

    async def verify_domain(
        self,
        session: AsyncSession,
        domain_id: UUID,
        user_id: UUID,
    ) -> CustomEmailDomain:
        """
        Trigger domain verification and update status.

        This calls Resend's verify endpoint and fetches the updated
        domain status and DNS record verification states.

        Args:
            session: Database session
            domain_id: Domain ID to verify
            user_id: User ID for ownership check

        Returns:
            Updated CustomEmailDomain

        Raises:
            ValueError: If domain not found
            PermissionError: If user doesn't own the domain
            Exception: If Resend API fails
        """
        # Get domain with ownership check
        domain = await CustomEmailDomainRepository.get_by_id(session, domain_id)
        if not domain:
            raise ValueError(f"Domain {domain_id} not found")
        if domain.user_id != user_id:
            raise PermissionError("You don't have access to this domain")

        if not domain.resend_domain_id:
            raise ValueError("Domain not properly configured with Resend")

        try:
            self.logger.info(f"Checking verification status for domain {domain.domain}")

            # First, get current status from Resend WITHOUT triggering verify
            # This prevents the issue where Domains.verify() restarts verification
            # and a subsequent Domains.get() returns "pending" even if already verified
            resend_domain = await asyncio.to_thread(resend.Domains.get, domain.resend_domain_id)

            # Extract current status
            current_status = self._extract_status(resend_domain)
            self.logger.info(f"Current Resend status: {current_status}")

            # Only trigger verification if NOT already verified
            # Calling Domains.verify() on an already-verified domain restarts the process
            if current_status.lower() != "verified":
                self.logger.info("Domain not yet verified, triggering verification...")
                verify_response = await asyncio.to_thread(
                    resend.Domains.verify, domain.resend_domain_id
                )
                self.logger.info(f"Resend verify response: {verify_response}")

                # Re-fetch status after triggering verification
                # Note: Status may still show "pending" if DNS hasn't propagated yet
                resend_domain = await asyncio.to_thread(resend.Domains.get, domain.resend_domain_id)
            else:
                self.logger.info("Domain already verified in Resend, skipping verify call")

            self.logger.info(f"Resend domain full response: {resend_domain}")
            self.logger.info(f"Resend domain response type: {type(resend_domain).__name__}")

            # Extract status - handle both dict and object access patterns
            # Resend SDK v2.x may return typed objects or dicts depending on version
            resend_status = self._extract_status(resend_domain)
            self.logger.info(
                f"Resend status value: '{resend_status}' (type: {type(resend_status).__name__})"
            )

            new_status = self._map_resend_status(resend_status)
            self.logger.info(f"Mapped to internal status: {new_status.value}")

            # Extract DNS records using helper
            dns_records = self._extract_records(resend_domain, domain.dns_records)

            # Update in database
            updated_domain = await CustomEmailDomainRepository.update_status(
                session=session,
                domain_id=domain_id,
                user_id=user_id,
                status=new_status,
                dns_records=dns_records,
            )

            if new_status == EmailDomainStatus.VERIFIED:
                self.logger.info(f"✅ Domain {domain.domain} verified successfully")
            else:
                self.logger.info(
                    f"⏳ Domain {domain.domain} verification status: {new_status.value}"
                )

            return updated_domain

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"user_id": str(user_id), "domain_id": str(domain_id)},
                tags={
                    "component": "custom_email_domain",
                    "operation": "verify_domain",
                    "severity": "medium",
                },
            )
            self.logger.error(f"❌ Failed to verify domain {domain_id}: {e}")
            raise

    async def get_domain(
        self,
        session: AsyncSession,
        domain_id: UUID,
        user_id: UUID,
    ) -> Optional[CustomEmailDomain]:
        """
        Get a custom email domain with ownership check.

        Args:
            session: Database session
            domain_id: Domain ID
            user_id: User ID for ownership check

        Returns:
            CustomEmailDomain or None if not found/not owned
        """
        domain = await CustomEmailDomainRepository.get_by_id(session, domain_id)
        if domain and domain.user_id == user_id:
            return domain
        return None

    async def list_domains(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> list[CustomEmailDomain]:
        """
        List all custom email domains for a user.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            List of CustomEmailDomain
        """
        return await CustomEmailDomainRepository.get_by_user_id(session, user_id)

    async def update_domain(
        self,
        session: AsyncSession,
        domain_id: UUID,
        user_id: UUID,
        from_name: Optional[str] = None,
        reply_to_email: Optional[str] = None,
    ) -> Optional[CustomEmailDomain]:
        """
        Update a custom email domain settings.

        Args:
            session: Database session
            domain_id: Domain ID to update
            user_id: User ID for ownership check
            from_name: Optional new sender display name
            reply_to_email: Optional new reply-to address

        Returns:
            Updated CustomEmailDomain or None if not found/not owned
        """
        # Get domain for validation
        domain = await CustomEmailDomainRepository.get_by_id(session, domain_id)
        if not domain or domain.user_id != user_id:
            return None

        # Validate reply_to if provided
        if reply_to_email:
            reply_to_email = self._validate_email(reply_to_email, domain.domain)

        update_data = {}
        if from_name is not None:
            update_data["from_name"] = from_name
        if reply_to_email is not None:
            update_data["reply_to_email"] = reply_to_email

        if not update_data:
            return domain

        return await CustomEmailDomainRepository.update(
            session=session,
            domain_id=domain_id,
            user_id=user_id,
            **update_data,
        )

    async def delete_domain(
        self,
        session: AsyncSession,
        domain_id: UUID,
        user_id: UUID,
    ) -> bool:
        """
        Delete a custom email domain.

        This removes the domain from both Resend and the database.

        Args:
            session: Database session
            domain_id: Domain ID to delete
            user_id: User ID for ownership check

        Returns:
            True if deleted successfully
        """
        # Get domain for Resend deletion
        domain = await CustomEmailDomainRepository.get_by_id(session, domain_id)
        if not domain or domain.user_id != user_id:
            return False

        try:
            # Delete from Resend if we have the ID
            if domain.resend_domain_id:
                self.logger.info(f"Deleting domain {domain.domain} from Resend")
                await asyncio.to_thread(resend.Domains.remove, domain.resend_domain_id)

            # Delete from database
            success = await CustomEmailDomainRepository.delete(
                session=session,
                domain_id=domain_id,
                user_id=user_id,
            )

            if success:
                self.logger.info(f"✅ Deleted custom email domain {domain.domain}")
            return success

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"user_id": str(user_id), "domain_id": str(domain_id)},
                tags={
                    "component": "custom_email_domain",
                    "operation": "delete_domain",
                    "severity": "medium",
                },
            )
            self.logger.error(f"❌ Failed to delete domain {domain_id}: {e}")
            # Still try to delete from database
            return await CustomEmailDomainRepository.delete(
                session=session, domain_id=domain_id, user_id=user_id
            )

    async def get_sender_config(
        self,
        session: AsyncSession,
        user_id: UUID,
    ) -> SenderConfig:
        """
        Get the sender configuration for a user.

        If the user has a verified custom email domain, use that.
        Otherwise, fall back to the default MyClone sender.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            SenderConfig with appropriate sender details
        """
        # Check for verified custom domain
        custom_domain = await CustomEmailDomainRepository.get_verified_by_user_id(session, user_id)

        if custom_domain:
            return SenderConfig(
                from_email=custom_domain.from_email,
                from_name=custom_domain.from_name,
                reply_to=custom_domain.reply_to_email,
                resend_api_key=custom_domain.resend_api_key or self.api_key,
            )

        # Fall back to default
        return SenderConfig(
            from_email=settings.resend_from_email.split("<")[-1].rstrip(">").strip(),
            from_name=(
                settings.resend_from_email.split("<")[0].strip()
                if "<" in settings.resend_from_email
                else None
            ),
            reply_to=None,
            resend_api_key=self.api_key,
        )

    def _extract_status(self, resend_domain) -> str:
        """
        Extract status from Resend domain response.

        Handles both dict and object access patterns since Resend SDK v2.x
        may return different types depending on the version/configuration.

        Args:
            resend_domain: Response from Resend Domains.get()

        Returns:
            Status string (defaults to "pending" if not found)
        """
        # Try dict access first
        if isinstance(resend_domain, dict):
            status = resend_domain.get("status")
            if status:
                self.logger.info(f"Found status via dict access: {status}")
                return status

        # Try attribute access (for typed objects)
        if hasattr(resend_domain, "status"):
            status = getattr(resend_domain, "status", None)
            if status:
                self.logger.info(f"Found status via attribute access: {status}")
                return status

        # Try accessing nested 'data' key (some SDK versions wrap response)
        if isinstance(resend_domain, dict) and "data" in resend_domain:
            data = resend_domain["data"]
            if isinstance(data, dict) and "status" in data:
                status = data["status"]
                self.logger.info(f"Found status via nested data: {status}")
                return status

        # Log all available keys/attributes for debugging
        if isinstance(resend_domain, dict):
            self.logger.warning(f"Status not found. Available keys: {list(resend_domain.keys())}")
        else:
            attrs = [a for a in dir(resend_domain) if not a.startswith("_")]
            self.logger.warning(f"Status not found. Available attributes: {attrs}")

        return "pending"

    def _extract_records(self, resend_domain, fallback_records) -> list:
        """
        Extract DNS records from Resend domain response.

        Args:
            resend_domain: Response from Resend Domains.get()
            fallback_records: Fallback records if extraction fails

        Returns:
            List of DNS records
        """
        # Try dict access first
        if isinstance(resend_domain, dict):
            records = resend_domain.get("records")
            if records is not None:
                return records

        # Try attribute access
        if hasattr(resend_domain, "records"):
            records = getattr(resend_domain, "records", None)
            if records is not None:
                return records

        return fallback_records or []

    def _map_resend_status(self, resend_status: str) -> EmailDomainStatus:
        """
        Map Resend domain status to our status enum.

        Args:
            resend_status: Status string from Resend API

        Returns:
            EmailDomainStatus enum value
        """
        status_map = {
            "not_started": EmailDomainStatus.PENDING,
            "pending": EmailDomainStatus.VERIFYING,
            "verified": EmailDomainStatus.VERIFIED,
            "failed": EmailDomainStatus.FAILED,
            "temporary_failure": EmailDomainStatus.FAILED,  # Handle temporary_failure
        }
        return status_map.get(resend_status.lower(), EmailDomainStatus.PENDING)
