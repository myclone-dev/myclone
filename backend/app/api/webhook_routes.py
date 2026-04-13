"""
Webhook API Routes - Account-level webhook management

This provides clean, RESTful endpoints for managing webhooks at the account level.

Current Implementation:
- Account-level webhooks (applies to ALL user's personas automatically)
- Uses personas.webhook_* columns (copied to all personas on create/update/delete)
- Supports any HTTPS webhook URL (Zapier, Make, n8n, Slack, etc.)
- No provider-specific logic (generic HTTP POST)
- When webhook is created/updated/deleted, changes apply to ALL user's personas
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_auth import get_current_user
from shared.database.models.database import Persona, get_session
from shared.database.models.user import User
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.schemas.webhook import (
    WebhookCreateRequest,
    WebhookResponse,
    WebhookUpdateRequest,
)

router = APIRouter(prefix="/api/v1/account", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update account webhook",
    description="""
    Configure a webhook URL to receive events from ALL your personas.

    **Supported Providers:**
    - Zapier (https://zapier.com)
    - Make (https://make.com)
    - n8n (https://n8n.io)
    - Slack (https://slack.com)
    - Discord (https://discord.com)
    - Any custom HTTPS endpoint

    **Events:**
    - `conversation.finished` - Sent when a voice conversation ends

    **Security:**
    - Only HTTPS URLs are allowed
    - SSRF protection enabled (blocks private IPs)
    - Fire-and-forget delivery (no retry)

    **Note:** This is an account-level setting. The webhook will automatically
    apply to ALL personas owned by your account. Creating a new webhook will
    replace any existing webhook configuration.
    """,
)
async def create_webhook(
    request: WebhookCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> WebhookResponse:
    """Create or update webhook configuration for ALL user's personas"""
    try:
        # Validate HTTPS URL
        if not str(request.url).startswith("https://"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook URL must use HTTPS",
            )

        # Check if user has any personas
        count_stmt = select(Persona).where(Persona.user_id == current_user.id)
        personas_count = len((await session.execute(count_stmt)).scalars().all())

        if personas_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No personas found for this account",
            )

        # Bulk update ALL user's personas with webhook configuration
        update_values = {
            "webhook_enabled": True,
            "webhook_url": str(request.url),
            "webhook_events": request.events,
        }
        if request.secret:
            update_values["webhook_secret"] = request.secret

        await session.execute(
            update(Persona).where(Persona.user_id == current_user.id).values(**update_values)
        )

        await session.commit()

        logger.info(
            f"Webhook configured for ALL personas ({personas_count} total) by user {current_user.id}: {request.url}"
        )

        # Get one persona to return config (all have identical webhook settings)
        first_persona_stmt = select(Persona).where(Persona.user_id == current_user.id).limit(1)
        first_persona = (await session.execute(first_persona_stmt)).scalar_one()

        return WebhookResponse(
            enabled=first_persona.webhook_enabled,
            url=first_persona.webhook_url,
            events=first_persona.webhook_events or ["conversation.finished"],
            has_secret=bool(first_persona.webhook_secret),
            personas_count=personas_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating webhook for user {current_user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(current_user.id),
                "webhook_url": str(request.url),
            },
            tags={
                "component": "webhook_api",
                "operation": "create_webhook",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create webhook: {str(e)}",
        )


@router.get(
    "/webhook",
    response_model=WebhookResponse,
    summary="Get account webhook configuration",
    description="""
    Get the current webhook configuration for your account.

    Returns the webhook URL, enabled status, event types, and number of personas.
    The webhook secret is never exposed in the response.
    """,
)
async def get_webhook(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> WebhookResponse:
    """Get webhook configuration for user's account"""
    try:
        # Get ANY persona for this user (all have same webhook config)
        persona_stmt = select(Persona).where(Persona.user_id == current_user.id).limit(1)
        persona = (await session.execute(persona_stmt)).scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No personas found for this account",
            )

        # Count total personas to show in response
        count_stmt = select(Persona).where(Persona.user_id == current_user.id)
        personas_count = len((await session.execute(count_stmt)).scalars().all())

        return WebhookResponse(
            enabled=persona.webhook_enabled,
            url=persona.webhook_url,
            events=persona.webhook_events or ["conversation.finished"],
            has_secret=bool(persona.webhook_secret),
            personas_count=personas_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting webhook for user {current_user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(current_user.id),
            },
            tags={
                "component": "webhook_api",
                "operation": "get_webhook",
                "severity": "low",
                "user_facing": "true",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get webhook: {str(e)}",
        )


@router.patch(
    "/webhook",
    response_model=WebhookResponse,
    summary="Update account webhook configuration",
    description="""
    Update webhook settings for your account.

    All fields are optional - only provided fields will be updated.

    **Examples:**
    - Change URL: `{"url": "https://new-url.com/webhook"}`
    - Disable: `{"enabled": false}`
    - Update events: `{"events": ["conversation.finished", "payment.received"]}`

    **Note:** This is an account-level setting. Changes will be applied to ALL personas.
    """,
)
async def update_webhook(
    request: WebhookUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> WebhookResponse:
    """Update webhook configuration for ALL user's personas"""
    try:
        # Check if user has any personas with webhook configured
        first_persona_stmt = select(Persona).where(Persona.user_id == current_user.id).limit(1)
        first_persona = (await session.execute(first_persona_stmt)).scalar_one_or_none()

        if not first_persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No personas found for this account",
            )

        # Check if webhook exists
        if not first_persona.webhook_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No webhook configured. Use POST to create one.",
            )

        # Validate HTTPS URL if provided
        if request.url is not None:
            if not str(request.url).startswith("https://"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Webhook URL must use HTTPS",
                )

        # Build update values (only include provided fields)
        update_values = {}
        if request.url is not None:
            update_values["webhook_url"] = str(request.url)
        if request.events is not None:
            update_values["webhook_events"] = request.events
        if request.secret is not None:
            update_values["webhook_secret"] = request.secret
        if request.enabled is not None:
            update_values["webhook_enabled"] = request.enabled

        # Bulk update ALL user's personas
        if update_values:
            await session.execute(
                update(Persona).where(Persona.user_id == current_user.id).values(**update_values)
            )

        await session.commit()

        # Count personas for response
        count_stmt = select(Persona).where(Persona.user_id == current_user.id)
        personas_count = len((await session.execute(count_stmt)).scalars().all())

        logger.info(
            f"Webhook updated for ALL personas ({personas_count} total) by user {current_user.id}"
        )

        # Get updated persona config to return
        updated_persona_stmt = select(Persona).where(Persona.user_id == current_user.id).limit(1)
        updated_persona = (await session.execute(updated_persona_stmt)).scalar_one()

        return WebhookResponse(
            enabled=updated_persona.webhook_enabled,
            url=updated_persona.webhook_url,
            events=updated_persona.webhook_events or ["conversation.finished"],
            has_secret=bool(updated_persona.webhook_secret),
            personas_count=personas_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating webhook for user {current_user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(current_user.id),
            },
            tags={
                "component": "webhook_api",
                "operation": "update_webhook",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update webhook: {str(e)}",
        )


@router.delete(
    "/webhook",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete account webhook configuration",
    description="""
    Remove webhook configuration from your account.

    This will:
    - Disable webhook delivery
    - Clear the webhook URL
    - Remove event configuration
    - Clear the webhook secret

    **Note:** This is an account-level setting. Webhook will be removed from ALL personas.
    No events will be sent to the webhook URL after deletion.
    """,
)
async def delete_webhook(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete webhook configuration for ALL user's personas"""
    try:
        # Check if user has any personas with webhook configured
        first_persona_stmt = select(Persona).where(Persona.user_id == current_user.id).limit(1)
        first_persona = (await session.execute(first_persona_stmt)).scalar_one_or_none()

        if not first_persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No personas found for this account",
            )

        # Check if webhook exists
        if not first_persona.webhook_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No webhook configured",
            )

        # Count personas before deletion
        count_stmt = select(Persona).where(Persona.user_id == current_user.id)
        personas_count = len((await session.execute(count_stmt)).scalars().all())

        # Bulk delete webhook configuration from ALL user's personas
        await session.execute(
            update(Persona)
            .where(Persona.user_id == current_user.id)
            .values(
                webhook_enabled=False,
                webhook_url=None,
                webhook_events=None,
                webhook_secret=None,
            )
        )

        await session.commit()

        logger.info(
            f"Webhook deleted from ALL personas ({personas_count} total) by user {current_user.id}"
        )

        # Return 204 No Content (no response body)
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting webhook for user {current_user.id}: {e}")
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(current_user.id),
            },
            tags={
                "component": "webhook_api",
                "operation": "delete_webhook",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete webhook: {str(e)}",
        )


@router.get("/webhook/health", summary="Webhook system health check")
async def webhook_health_check():
    """Health check endpoint for webhook system"""
    return {
        "status": "healthy",
        "message": "Webhook system is operational",
        "supported_providers": ["zapier", "make", "n8n", "slack", "discord", "custom"],
        "supported_events": ["conversation.finished"],
    }
