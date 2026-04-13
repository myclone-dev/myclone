"""
API routes for managing custom email domains (whitelabel email sending).

Enterprise users can configure their own email domain to send verification
and OTP emails from their brand instead of myclone.is.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_auth import get_current_user
from app.services.custom_email_domain_service import CustomEmailDomainService
from shared.database.models.database import get_session
from shared.database.models.user import User
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users/me/email-domains", tags=["Email Domains"])


# ============================================================================
# Request/Response Models
# ============================================================================


class DNSRecordResponse(BaseModel):
    """DNS record information."""

    record: Optional[str] = None
    name: str
    type: str
    value: str
    status: str
    ttl: Optional[str] = None
    priority: Optional[int] = None


class CreateEmailDomainRequest(BaseModel):
    """Request to create a custom email domain."""

    domain: str = Field(
        ...,
        description="The domain name (e.g., 'acme.com')",
        min_length=4,
        max_length=255,
    )
    from_email: EmailStr = Field(
        ...,
        description="The sender email address (e.g., 'hello@acme.com')",
    )
    from_name: Optional[str] = Field(
        None,
        description="The sender display name (e.g., 'Acme Support')",
        max_length=255,
    )
    reply_to_email: Optional[EmailStr] = Field(
        None,
        description="Optional reply-to email address",
    )

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate and normalize domain."""
        import re

        domain = v.lower().strip()
        # Remove protocol if present
        domain = re.sub(r"^https?://", "", domain)
        # Remove paths
        domain = domain.split("/")[0]

        if len(domain) < 4:
            raise ValueError("Domain must be at least 4 characters")

        return domain


class UpdateEmailDomainRequest(BaseModel):
    """Request to update a custom email domain."""

    from_name: Optional[str] = Field(
        None,
        description="The sender display name",
        max_length=255,
    )
    reply_to_email: Optional[EmailStr] = Field(
        None,
        description="Reply-to email address",
    )


class EmailDomainResponse(BaseModel):
    """Response for a single email domain."""

    id: str
    domain: str
    from_email: str
    from_name: Optional[str]
    reply_to_email: Optional[str]
    status: str
    dns_records: Optional[list[DNSRecordResponse]]
    created_at: datetime
    verified_at: Optional[datetime]

    class Config:
        from_attributes = True


class EmailDomainListResponse(BaseModel):
    """Response for listing email domains."""

    domains: list[EmailDomainResponse]
    total: int


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str


# ============================================================================
# Helper Functions
# ============================================================================


def _format_domain_response(domain) -> EmailDomainResponse:
    """Format a CustomEmailDomain model to response."""
    dns_records = None
    if domain.dns_records:
        dns_records = [
            DNSRecordResponse(
                record=r.get("record"),
                name=r.get("name", ""),
                type=r.get("type", ""),
                value=r.get("value", ""),
                status=r.get("status", "pending"),
                ttl=r.get("ttl"),
                priority=r.get("priority"),
            )
            for r in domain.dns_records
        ]

    return EmailDomainResponse(
        id=str(domain.id),
        domain=domain.domain,
        from_email=domain.from_email,
        from_name=domain.from_name,
        reply_to_email=domain.reply_to_email,
        status=domain.status.value,
        dns_records=dns_records,
        created_at=domain.created_at,
        verified_at=domain.verified_at,
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("", response_model=EmailDomainListResponse)
async def list_email_domains(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    List all custom email domains for the authenticated user.

    Returns all email domains with their verification status and DNS records.
    """
    try:
        service = CustomEmailDomainService()
        domains = await service.list_domains(session, user.id)

        domain_responses = [_format_domain_response(d) for d in domains]

        return EmailDomainListResponse(
            domains=domain_responses,
            total=len(domain_responses),
        )

    except Exception as e:
        logger.error(f"Failed to list email domains for user {user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={"user_id": str(user.id)},
            tags={
                "component": "custom_email_domain",
                "operation": "list_domains",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list email domains",
        )


@router.post("", response_model=EmailDomainResponse, status_code=status.HTTP_201_CREATED)
async def create_email_domain(
    request: CreateEmailDomainRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new custom email domain.

    This registers the domain with our email provider and returns
    the DNS records that need to be configured for verification.

    **Requires Enterprise plan.**
    """
    try:
        service = CustomEmailDomainService()
        domain = await service.create_domain(
            session=session,
            user_id=user.id,
            domain=request.domain,
            from_email=request.from_email,
            from_name=request.from_name,
            reply_to_email=request.reply_to_email,
        )

        logger.info(f"Created email domain {domain.domain} for user {user.id}")
        return _format_domain_response(domain)

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create email domain for user {user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user.id),
                "domain": request.domain,
            },
            tags={
                "component": "custom_email_domain",
                "operation": "create_domain",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create email domain",
        )


@router.get("/{domain_id}", response_model=EmailDomainResponse)
async def get_email_domain(
    domain_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get a specific custom email domain by ID.

    Returns the domain details including DNS records and verification status.
    """
    try:
        service = CustomEmailDomainService()
        domain = await service.get_domain(session, domain_id, user.id)

        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email domain not found",
            )

        return _format_domain_response(domain)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get email domain {domain_id} for user {user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user.id),
                "domain_id": str(domain_id),
            },
            tags={
                "component": "custom_email_domain",
                "operation": "get_domain",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get email domain",
        )


@router.post("/{domain_id}/verify", response_model=EmailDomainResponse)
async def verify_email_domain(
    domain_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Trigger DNS verification for an email domain.

    This checks if the required DNS records have been configured correctly.
    DNS propagation can take up to 48 hours, so verification may not
    succeed immediately after adding records.
    """
    try:
        service = CustomEmailDomainService()
        domain = await service.verify_domain(session, domain_id, user.id)

        return _format_domain_response(domain)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to verify email domain {domain_id} for user {user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user.id),
                "domain_id": str(domain_id),
            },
            tags={
                "component": "custom_email_domain",
                "operation": "verify_domain",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify email domain",
        )


@router.patch("/{domain_id}", response_model=EmailDomainResponse)
async def update_email_domain(
    domain_id: UUID,
    request: UpdateEmailDomainRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Update an email domain's settings.

    Only the sender display name and reply-to email can be updated.
    The domain and from_email cannot be changed after creation.
    """
    try:
        service = CustomEmailDomainService()
        domain = await service.update_domain(
            session=session,
            domain_id=domain_id,
            user_id=user.id,
            from_name=request.from_name,
            reply_to_email=request.reply_to_email,
        )

        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email domain not found",
            )

        return _format_domain_response(domain)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update email domain {domain_id} for user {user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user.id),
                "domain_id": str(domain_id),
            },
            tags={
                "component": "custom_email_domain",
                "operation": "update_domain",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update email domain",
        )


@router.delete("/{domain_id}", response_model=MessageResponse)
async def delete_email_domain(
    domain_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a custom email domain.

    This removes the domain from both the email provider and the database.
    After deletion, emails will be sent from the default MyClone domain.
    """
    try:
        service = CustomEmailDomainService()
        success = await service.delete_domain(session, domain_id, user.id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email domain not found",
            )

        return MessageResponse(message="Email domain deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete email domain {domain_id} for user {user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user.id),
                "domain_id": str(domain_id),
            },
            tags={
                "component": "custom_email_domain",
                "operation": "delete_domain",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete email domain",
        )


class ResendDebugResponse(BaseModel):
    """Debug response for Resend API testing."""

    resend_domain_id: str
    raw_response: dict
    raw_response_type: str
    extracted_status: str
    mapped_status: str
    available_keys: Optional[list[str]] = None


@router.get("/{domain_id}/debug-resend", response_model=ResendDebugResponse)
async def debug_resend_domain(
    domain_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Debug endpoint to check raw Resend API response.

    This endpoint fetches the domain directly from Resend and returns
    the raw response for debugging purposes.
    """
    import asyncio

    import resend

    from shared.config import settings

    try:
        service = CustomEmailDomainService()
        domain = await service.get_domain(session, domain_id, user.id)

        if not domain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email domain not found",
            )

        if not domain.resend_domain_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Domain not properly configured with Resend",
            )

        # Set API key and fetch directly from Resend
        resend.api_key = settings.resend_api_key
        resend_domain = await asyncio.to_thread(resend.Domains.get, domain.resend_domain_id)

        # Convert to dict if needed
        if isinstance(resend_domain, dict):
            raw_response = resend_domain
            available_keys = list(resend_domain.keys())
        else:
            raw_response = (
                dict(resend_domain)
                if hasattr(resend_domain, "__dict__")
                else {"repr": str(resend_domain)}
            )
            available_keys = [a for a in dir(resend_domain) if not a.startswith("_")]

        # Extract and map status
        extracted_status = service._extract_status(resend_domain)
        mapped_status = service._map_resend_status(extracted_status).value

        return ResendDebugResponse(
            resend_domain_id=domain.resend_domain_id,
            raw_response=raw_response,
            raw_response_type=type(resend_domain).__name__,
            extracted_status=extracted_status,
            mapped_status=mapped_status,
            available_keys=available_keys,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to debug resend domain {domain_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Debug failed: {str(e)}",
        )
