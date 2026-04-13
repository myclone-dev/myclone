"""
Custom Domain Routes - API endpoints for white-label domain management

Similar to Delphi's standalone integration feature, this allows users to
connect their own domains to serve their AI clone.
"""

import logging
import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_auth import get_current_user
from shared.config import settings
from shared.database.models.custom_domain import CustomDomain, DomainStatus
from shared.database.models.database import get_session
from shared.database.models.user import User
from shared.database.repositories.custom_domain_repository import CustomDomainRepository
from shared.middleware import clear_custom_domain_cache, extract_domain_from_origin
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.services.tier_service import TierService
from shared.services.vercel_domain_service import get_vercel_domain_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/custom-domains")


# Request/Response Models


class DNSRecordResponse(BaseModel):
    """DNS record information for user to add"""

    type: str = Field(..., description="Record type (TXT, A, CNAME)")
    name: str = Field(..., description="Record name (e.g., '_vercel', '@', 'chat')")
    value: str = Field(..., description="Record value")
    description: Optional[str] = Field(None, description="Human-readable instructions")


class CustomDomainResponse(BaseModel):
    """Custom domain response (USER-LEVEL)"""

    id: str = Field(..., description="Domain UUID")
    domain: str = Field(..., description="Full domain name")
    status: str = Field(..., description="Domain status")
    user_id: str = Field(..., description="Owner user ID")
    username: Optional[str] = Field(None, description="Owner username for routing")
    verified: bool = Field(..., description="Whether domain ownership is verified")
    ssl_ready: bool = Field(..., description="Whether SSL is provisioned")
    verification_record: Optional[DNSRecordResponse] = Field(
        None, description="TXT record for verification"
    )
    routing_record: Optional[DNSRecordResponse] = Field(
        None, description="A or CNAME record for routing"
    )
    last_error: Optional[str] = Field(None, description="Last error message")
    created_at: datetime = Field(..., description="Creation timestamp")
    verified_at: Optional[datetime] = Field(None, description="Verification timestamp")

    class Config:
        from_attributes = True


class CustomDomainListResponse(BaseModel):
    """List of custom domains response"""

    domains: List[CustomDomainResponse] = Field(..., description="List of domains")
    total: int = Field(..., description="Total count")


class AddCustomDomainRequest(BaseModel):
    """Request to add a custom domain (USER-LEVEL)"""

    domain: str = Field(
        ...,
        description="Full domain name (e.g., 'chat.example.com' or 'example.com')",
        min_length=4,
        max_length=253,
    )

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain format with security checks"""
        domain = v.lower().strip()

        # Homograph attack protection: convert to punycode to catch lookalike characters
        # (e.g., Cyrillic 'е' that looks like Latin 'e')
        try:
            domain = domain.encode("idna").decode("ascii")
        except (UnicodeError, UnicodeDecodeError):
            raise ValueError("Invalid domain characters detected")

        # Basic domain validation regex
        # Allows: example.com, chat.example.com, my-site.example.co.uk
        pattern = r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$"

        if not re.match(pattern, domain):
            raise ValueError("Invalid domain format. Example: chat.example.com or example.com")

        # Block reserved domains and TLDs
        # Dynamically include the platform's own domain from FRONTEND_URL
        _platform_domain = settings.frontend_url.replace("https://", "").replace("http://", "").split(":")[0].split("/")[0]
        # Extract root domain (e.g., "app.example.com" -> "example.com")
        _parts = _platform_domain.split(".")
        _root_domain = ".".join(_parts[-2:]) if len(_parts) >= 2 else _platform_domain

        reserved = [
            # Platform domain (derived from FRONTEND_URL)
            _root_domain,
            # Vercel domains
            "vercel.app",
            "vercel.com",
            "now.sh",
            # Local/test domains
            "localhost",
            "local",
            "internal",
            "test",
            "example",
            "invalid",
            # Other reserved
            "onion",
        ]
        for r in reserved:
            if domain == r or domain.endswith(f".{r}"):
                raise ValueError(f"Cannot use reserved domain: {r}")

        return domain

    class Config:
        json_schema_extra = {
            "example": {
                "domain": "chat.example.com",
            }
        }


class AddCustomDomainResponse(BaseModel):
    """Response after adding a custom domain"""

    success: bool = Field(..., description="Whether domain was added")
    domain: CustomDomainResponse = Field(..., description="Domain details")
    message: str = Field(..., description="Status message")
    dns_instructions: str = Field(..., description="Instructions for DNS setup")


class VerifyDomainResponse(BaseModel):
    """Response from domain verification"""

    success: bool = Field(..., description="Whether verification was successful")
    verified: bool = Field(..., description="Domain verification status")
    domain: CustomDomainResponse = Field(..., description="Updated domain details")
    message: str = Field(..., description="Status message")


# Helper functions


def _format_domain_response(
    domain: CustomDomain, username: Optional[str] = None
) -> CustomDomainResponse:
    """Convert CustomDomain model to response (USER-LEVEL)"""
    # Extract verification record
    # Vercel API uses "domain" field for TXT record name, we normalize it to "name"
    verification_record = None
    if domain.verification_records:
        for record in domain.verification_records:
            if record.get("type") == "TXT":
                # Vercel uses "domain" field, but we also support "name" as fallback
                txt_name = record.get("domain") or record.get("name") or f"_vercel.{domain.domain}"
                verification_record = DNSRecordResponse(
                    type="TXT",
                    name=txt_name,
                    value=record.get("value", ""),
                    description="Add this TXT record to verify domain ownership",
                )
                break

    # Extract routing record
    routing_record = None
    additional_routing_records: List[DNSRecordResponse] = []
    if domain.routing_record:
        routing_record = DNSRecordResponse(
            type=domain.routing_record.get("type", "A"),
            name=domain.routing_record.get("name", "@"),
            value=domain.routing_record.get("value", "76.76.21.21"),
            description="Add this record to route traffic to your clone",
        )

    # Include optional additional routing records (e.g., AAAA for apex)
    if hasattr(domain, "additional_routing_records") and domain.additional_routing_records:
        for rec in domain.additional_routing_records:
            additional_routing_records.append(
                DNSRecordResponse(
                    type=rec.get("type", "AAAA"),
                    name=rec.get("name", "@"),
                    value=rec.get("value", ""),
                    description="Optional: Add IPv6 AAAA record for improved routing",
                )
            )

    return CustomDomainResponse(
        id=str(domain.id),
        domain=domain.domain,
        status=domain.status.value,
        user_id=str(domain.user_id),
        username=username,
        verified=domain.status == DomainStatus.ACTIVE,
        ssl_ready=domain.status == DomainStatus.ACTIVE,
        verification_record=verification_record,
        routing_record=routing_record,
        last_error=domain.last_error,
        created_at=domain.created_at,
        verified_at=domain.verified_at,
    )


# Routes


@router.get("", response_model=CustomDomainListResponse)
async def list_custom_domains(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    List all custom domains for the authenticated user (USER-LEVEL)

    Returns all domains with their current status, DNS records, and verification state.
    Custom domains route to: domain.com → /{username}, domain.com/persona → /{username}/{persona}
    """
    try:
        domains = await CustomDomainRepository.get_by_user_id(session, user.id)

        # Pass user's username for response formatting
        domain_responses = [_format_domain_response(d, user.username) for d in domains]

        return CustomDomainListResponse(
            domains=domain_responses,
            total=len(domain_responses),
        )

    except Exception as e:
        logger.error(f"Failed to list custom domains for user {user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={"user_id": str(user.id)},
            tags={
                "component": "custom_domain",
                "operation": "list_domains",
                "severity": "medium",
                "user_facing": "true",
            },
            level="error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list custom domains",
        )


@router.post("", response_model=AddCustomDomainResponse, status_code=status.HTTP_201_CREATED)
async def add_custom_domain(
    request: AddCustomDomainRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Add a custom domain for white-label deployment (USER-LEVEL)

    This endpoint:
    1. Validates the domain format
    2. Checks if domain is already in use
    3. Calls Vercel API to add domain to the project
    4. Returns DNS records for the user to configure

    User-level routing:
    - domain.com → equivalent to myclone.is/{username}
    - domain.com/persona → equivalent to myclone.is/{username}/{persona}

    After adding the domain, user needs to:
    1. Add the TXT record for verification
    2. Add the A record (apex) or CNAME record (subdomain) for routing
    3. Call the verify endpoint to complete setup
    """
    try:
        # Check tier limits for custom domains
        tier_service = TierService(session)
        tier_limits = await tier_service.get_user_tier_limits(user.id)
        max_custom_domains = tier_limits.get("max_custom_domains", 0)

        # Get current domain count for user
        current_domain_count = await CustomDomainRepository.count_by_user_id(session, user.id)

        # Check if user has reached their domain limit (-1 means unlimited)
        if max_custom_domains != -1 and current_domain_count >= max_custom_domains:
            tier_name = tier_limits.get("tier_name", "your current plan")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Custom domain limit reached. {tier_name} allows {max_custom_domains} custom domain(s). "
                f"You currently have {current_domain_count}. Please upgrade your plan to add more domains.",
            )

        # Check if domain already exists
        existing = await CustomDomainRepository.get_by_domain(session, request.domain)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This domain is already registered",
            )

        # Check Vercel integration
        vercel_service = get_vercel_domain_service()
        if not vercel_service.is_configured():
            # Log to Sentry - this is a config issue that shouldn't happen in production
            capture_exception_with_context(
                Exception("Vercel domain service not configured"),
                extra={"user_id": str(user.id), "domain": request.domain},
                tags={
                    "component": "custom_domain",
                    "operation": "add_domain",
                    "severity": "critical",
                    "config_error": "true",
                },
                level="error",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom domain feature is not configured. Please contact support",
            )

        # Add domain to Vercel
        vercel_result = await vercel_service.add_domain(request.domain)

        if not vercel_result.get("success"):
            error = vercel_result.get("error", "unknown")
            message = vercel_result.get("message", "Failed to add domain")

            if error == "domain_already_in_use":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This domain is already in use by another project. "
                    "Remove it from the other project first.",
                )
            elif error == "invalid_domain":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid domain: {message}",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Failed to add domain: {message}",
                )

        # Create database record (USER-LEVEL - no persona_id)
        # Handle race condition: catch IntegrityError if another request created the domain
        try:
            custom_domain = await CustomDomainRepository.create(
                session=session,
                user_id=user.id,
                domain=request.domain,
                verification_records=vercel_result.get("verification_records"),
                routing_record=vercel_result.get("routing_record"),
            )
        except IntegrityError:
            # Race condition: domain was created by another request
            # Clean up the domain we added to Vercel
            try:
                await vercel_service.remove_domain(request.domain)
            except Exception:
                pass  # Best effort cleanup
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This domain is already registered",
            )

        domain_response = _format_domain_response(custom_domain, user.username)

        # Build DNS instructions
        dns_instructions = """
To complete setup, add these DNS records at your domain registrar:

1. **Verification Record (TXT)**
   - Type: TXT
   - Name: {verification_name}
   - Value: {verification_value}

2. **Routing Record ({routing_type})**
   - Type: {routing_type}
   - Name: {routing_name}
   - Value: {routing_value}

After adding records, DNS propagation may take up to 48 hours.
Click "Verify Domain" once records are added.
        """.format(
            verification_name=(
                domain_response.verification_record.name
                if domain_response.verification_record
                else "_vercel"
            ),
            verification_value=(
                domain_response.verification_record.value
                if domain_response.verification_record
                else ""
            ),
            routing_type=(
                domain_response.routing_record.type if domain_response.routing_record else "A"
            ),
            routing_name=(
                domain_response.routing_record.name if domain_response.routing_record else "@"
            ),
            routing_value=(
                domain_response.routing_record.value
                if domain_response.routing_record
                else "76.76.21.21"
            ),
        )

        logger.info(f"Custom domain added: {request.domain} for user {user.id}")

        return AddCustomDomainResponse(
            success=True,
            domain=domain_response,
            message="Domain added successfully. Configure DNS records to complete setup.",
            dns_instructions=dns_instructions.strip(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add custom domain {request.domain} for user {user.id}: {e}")
        await session.rollback()
        # Clean up Vercel if database operation failed
        # This prevents orphaned domains in Vercel
        try:
            vercel_service = get_vercel_domain_service()
            if vercel_service.is_configured():
                await vercel_service.remove_domain(request.domain)
        except Exception:
            pass  # Best effort cleanup
        capture_exception_with_context(
            e,
            extra={"user_id": str(user.id), "domain": request.domain},
            tags={
                "component": "custom_domain",
                "operation": "add_domain",
                "severity": "high",
                "user_facing": "true",
            },
            level="error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add custom domain",
        )


@router.post("/{domain_id}/verify", response_model=VerifyDomainResponse)
async def verify_custom_domain(
    domain_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Verify a custom domain's DNS configuration

    This endpoint:
    1. Calls Vercel API to verify DNS records
    2. Updates domain status based on verification result
    3. Returns updated domain details

    User should call this after adding DNS records at their registrar.
    DNS propagation may take up to 48 hours.
    """
    try:
        # Parse domain_id
        try:
            domain_uuid = UUID(domain_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid domain ID format",
            )

        # Get domain and verify ownership
        custom_domain = await CustomDomainRepository.get_by_id(session, domain_uuid)

        if not custom_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain not found",
            )

        if custom_domain.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this domain",
            )

        # Already active?
        if custom_domain.status == DomainStatus.ACTIVE:
            return VerifyDomainResponse(
                success=True,
                verified=True,
                domain=_format_domain_response(custom_domain),
                message="Domain is already verified and active",
            )

        # Call Vercel to verify
        vercel_service = get_vercel_domain_service()
        if not vercel_service.is_configured():
            # Log to Sentry - this is a config issue that shouldn't happen in production
            capture_exception_with_context(
                Exception("Vercel domain service not configured"),
                extra={"user_id": str(user.id), "domain_id": domain_id},
                tags={
                    "component": "custom_domain",
                    "operation": "verify_domain",
                    "severity": "critical",
                    "config_error": "true",
                },
                level="error",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Custom domain feature is not configured. Please contact support",
            )

        # Update status to verifying
        await CustomDomainRepository.update_status(session, domain_uuid, DomainStatus.VERIFYING)

        # Verify with Vercel (ownership + configuration checks)
        verify_result = await vercel_service.verify_domain(custom_domain.domain)

        ownership_verified = bool(verify_result.get("ownership_verified", False))
        fully_verified = bool(verify_result.get("verified", False))

        if fully_verified:
            # Domain is verified - automatically mark as ACTIVE
            updated_domain = await CustomDomainRepository.update_status(
                session, domain_uuid, DomainStatus.ACTIVE
            )

            # Clear CORS cache so the domain is immediately allowed
            cache_key = extract_domain_from_origin(f"https://{custom_domain.domain}")
            clear_custom_domain_cache(cache_key)

            logger.info(f"Custom domain is ACTIVE: {custom_domain.domain} for user {user.id}")

            return VerifyDomainResponse(
                success=True,
                verified=True,
                domain=_format_domain_response(updated_domain),
                message="Domain is fully active and verified.",
            )
        else:
            # Verification failed or incomplete configuration
            error_message = verify_result.get(
                "message", "DNS records not found or not propagated yet"
            )

            # If TXT ownership is verified but routing missing, set VERIFIED; otherwise PENDING
            next_status = DomainStatus.VERIFIED if ownership_verified else DomainStatus.PENDING

            updated_domain = await CustomDomainRepository.update_status(
                session,
                domain_uuid,
                next_status,
                error_message=error_message,
            )

            # Build a more helpful message for the user
            if ownership_verified:
                user_message = (
                    f"{error_message}. Your TXT verification record is correct, "
                    "but the routing record (A/AAAA for apex or CNAME for subdomain) is not configured yet. "
                    "Please add the routing record and try again."
                )
            else:
                user_message = (
                    f"{error_message}. "
                    "Please check that both DNS records are added correctly and try again. "
                    "DNS propagation can take up to 48 hours."
                )

            return VerifyDomainResponse(
                success=False,
                verified=False,
                domain=_format_domain_response(updated_domain),
                message=user_message,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to verify domain {domain_id} for user {user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={"user_id": str(user.id), "domain_id": domain_id},
            tags={
                "component": "custom_domain",
                "operation": "verify_domain",
                "severity": "medium",
                "user_facing": "true",
            },
            level="error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify domain",
        )


@router.get("/{domain_id}", response_model=CustomDomainResponse)
async def get_custom_domain(
    domain_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get details for a specific custom domain
    """
    try:
        # Parse domain_id
        try:
            domain_uuid = UUID(domain_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid domain ID format",
            )

        custom_domain = await CustomDomainRepository.get_by_id(session, domain_uuid)

        if not custom_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain not found",
            )

        if custom_domain.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this domain",
            )

        return _format_domain_response(custom_domain)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get domain {domain_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get domain",
        )


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_domain(
    domain_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Remove a custom domain

    This will:
    1. Remove the domain from Vercel
    2. Delete the database record
    """
    try:
        # Parse domain_id
        try:
            domain_uuid = UUID(domain_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid domain ID format",
            )

        # Get domain and verify ownership
        custom_domain = await CustomDomainRepository.get_by_id(session, domain_uuid)

        if not custom_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain not found",
            )

        if custom_domain.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this domain",
            )

        # Remove from Vercel
        vercel_service = get_vercel_domain_service()
        if vercel_service.is_configured():
            await vercel_service.remove_domain(custom_domain.domain)

        # Delete from database
        await CustomDomainRepository.delete(session, domain_uuid, user.id)

        # Clear CORS cache so the domain is no longer allowed
        # Normalize domain to match middleware cache key format
        cache_key = extract_domain_from_origin(f"https://{custom_domain.domain}")
        clear_custom_domain_cache(cache_key)

        logger.info(f"Custom domain deleted: {custom_domain.domain} for user {user.id}")

        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete domain {domain_id}: {e}")
        await session.rollback()
        capture_exception_with_context(
            e,
            extra={"user_id": str(user.id), "domain_id": domain_id},
            tags={
                "component": "custom_domain",
                "operation": "delete_domain",
                "severity": "medium",
                "user_facing": "true",
            },
            level="error",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete domain",
        )


# Public endpoint for domain lookup (used by middleware)


class DomainLookupResponse(BaseModel):
    """Response for domain lookup (used by middleware)"""

    domain: str = Field(..., description="The domain name")
    user_id: str = Field(..., description="User UUID")
    username: str = Field(..., description="Username for routing")


@router.get("/lookup/{domain}", response_model=DomainLookupResponse)
async def lookup_domain(
    domain: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Lookup a domain to get routing information (internal use, USER-LEVEL)

    This endpoint is called by the Next.js middleware to determine
    which user to display for a custom domain.

    User-level routing:
    - domain.com → routes to /{username}
    - domain.com/persona_name → routes to /{username}/{persona_name}

    Returns 404 if domain is not found or not active.
    """
    try:
        custom_domain = await CustomDomainRepository.get_active_by_domain(
            session, domain.lower().strip()
        )

        if not custom_domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain not found or not active",
            )

        # Get user to find username
        from shared.database.repositories.user_repository import UserRepository

        user = await UserRepository.get_by_id(session, custom_domain.user_id)

        if not user or not user.username:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain owner not found",
            )

        # USER-LEVEL: Return username for routing, path segments handled by middleware
        return DomainLookupResponse(
            domain=custom_domain.domain,
            user_id=str(custom_domain.user_id),
            username=user.username,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to lookup domain {domain}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to lookup domain",
        )
