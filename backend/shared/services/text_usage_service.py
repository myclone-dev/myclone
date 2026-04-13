"""
Text usage service for tracking and limiting text chat usage.

Text usage is charged to the PERSONA OWNER, not the visitor.
When anyone chats with a persona (via agent page or embedded widget),
the owner's monthly quota is consumed.

Tier limits:
- Free (0): 500 messages/month
- Pro (1): 10,000 messages/month
- Business (2): 40,000 messages/month
- Enterprise (3): Unlimited (-1)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Tuple
from uuid import UUID

from dateutil.relativedelta import relativedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.database import Persona
from shared.database.models.tier_plan import (
    SubscriptionStatus,
    TierPlan,
    UserSubscription,
    UserUsageCache,
)
from shared.monitoring.sentry_utils import (
    add_breadcrumb,
    capture_message,
)

logger = logging.getLogger(__name__)


class TextLimitExceeded(Exception):
    """Raised when text usage limit is exceeded"""

    def __init__(self, message: str, used_messages: int = 0, limit_messages: int = 0):
        super().__init__(message)
        self.used_messages = used_messages
        self.limit_messages = limit_messages


class TextUsageService:
    """Service for managing text chat usage limits based on persona owner's tier"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_owner_tier_limit(self, owner_id: UUID) -> Tuple[int, str]:
        """
        Get the text message limit for a persona owner based on their tier.

        Returns:
            Tuple of (limit_messages, tier_name)
            limit_messages = -1 means unlimited
        """
        query = (
            select(TierPlan)
            .join(UserSubscription, UserSubscription.tier_id == TierPlan.id)
            .where(UserSubscription.user_id == owner_id)
            .where(UserSubscription.status == SubscriptionStatus.ACTIVE)
        )
        result = await self.db.execute(query)
        tier = result.scalar_one_or_none()

        if not tier:
            # Fallback to free tier
            query = select(TierPlan).where(TierPlan.id == 0)
            result = await self.db.execute(query)
            tier = result.scalar_one()

        return tier.max_text_messages_per_month, tier.tier_name

    async def get_owner_usage(self, owner_id: UUID) -> Tuple[int, datetime]:
        """
        Get the current text usage for a persona owner.

        Returns:
            Tuple of (used_messages, reset_at)
        """
        # Get or create usage cache
        query = select(UserUsageCache).where(UserUsageCache.user_id == owner_id)
        result = await self.db.execute(query)
        usage_cache = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if not usage_cache:
            # Create usage cache with reset date set to next month
            reset_at = (now + relativedelta(months=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            usage_cache = UserUsageCache(
                user_id=owner_id,
                text_messages_used=0,
                text_usage_reset_at=reset_at,
            )
            self.db.add(usage_cache)
            await self.db.flush()
            return 0, reset_at

        # Check if we need to reset (past reset date)
        if usage_cache.text_usage_reset_at and now >= usage_cache.text_usage_reset_at:
            # Reset usage and set new reset date
            usage_cache.text_messages_used = 0
            usage_cache.text_usage_reset_at = (now + relativedelta(months=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            usage_cache.last_updated_at = now
            await self.db.flush()
            return 0, usage_cache.text_usage_reset_at

        # Set reset date if not set
        if not usage_cache.text_usage_reset_at:
            usage_cache.text_usage_reset_at = (now + relativedelta(months=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            await self.db.flush()

        return usage_cache.text_messages_used, usage_cache.text_usage_reset_at

    async def check_owner_text_limit(self, persona_id: UUID) -> Tuple[bool, int, int]:
        """
        Check if the persona owner has remaining text message quota.

        Args:
            persona_id: The persona being chatted with

        Returns:
            Tuple of (can_send, remaining_messages, limit_messages)
            remaining_messages = -1 means unlimited
        """
        # Get persona owner
        query = select(Persona).where(Persona.id == persona_id)
        result = await self.db.execute(query)
        persona = result.scalar_one_or_none()

        if not persona:
            raise ValueError(f"Persona {persona_id} not found")

        owner_id = persona.user_id

        return await self.check_owner_text_limit_by_owner_id(owner_id)

    async def check_owner_text_limit_by_owner_id(self, owner_id: UUID) -> Tuple[bool, int, int]:
        """
        Check if the owner has remaining text message quota by owner ID.

        Args:
            owner_id: The persona owner's user ID

        Returns:
            Tuple of (can_send, remaining_messages, limit_messages)
            remaining_messages = -1 means unlimited
        """
        # Get owner's tier limit
        limit_messages, tier_name = await self.get_owner_tier_limit(owner_id)

        # Unlimited tier
        if limit_messages == -1:
            return True, -1, -1

        # Get current usage
        used_messages, _ = await self.get_owner_usage(owner_id)

        remaining_messages = max(0, limit_messages - used_messages)

        # Allow if there's remaining quota
        can_send = remaining_messages > 0

        if not can_send:
            logger.warning(
                f"Text limit exceeded for owner {owner_id}. "
                f"Used: {used_messages}, Limit: {limit_messages}"
            )
            # Track text limit exceeded event in Sentry
            capture_message(
                f"Text limit exceeded for owner {owner_id}",
                level="warning",
                tags={
                    "event_type": "text_limit_exceeded",
                    "owner_id": str(owner_id),
                    "tier_name": tier_name,
                },
                extra={
                    "used_messages": used_messages,
                    "limit_messages": limit_messages,
                    "percentage": (
                        round(used_messages / limit_messages * 100, 1) if limit_messages > 0 else 0
                    ),
                },
            )

        return can_send, remaining_messages, limit_messages

    async def record_message(self, persona_id: UUID) -> None:
        """
        Record that a message was sent to a persona (increments owner's usage).

        Args:
            persona_id: The persona that received the message
        """
        # Get persona owner
        query = select(Persona).where(Persona.id == persona_id)
        result = await self.db.execute(query)
        persona = result.scalar_one_or_none()

        if not persona:
            raise ValueError(f"Persona {persona_id} not found")

        await self.record_message_for_owner(persona.user_id)

    async def record_message_for_owner(self, owner_id: UUID) -> None:
        """
        Record a message directly for an owner (increments usage).
        Uses SELECT ... FOR UPDATE to prevent race conditions.

        Args:
            owner_id: The persona owner's user ID
        """
        now = datetime.now(timezone.utc)

        # Get or create usage cache with lock
        query = select(UserUsageCache).where(UserUsageCache.user_id == owner_id).with_for_update()
        result = await self.db.execute(query)
        usage_cache = result.scalar_one_or_none()

        if usage_cache:
            # Check if we need to reset first
            if usage_cache.text_usage_reset_at and now >= usage_cache.text_usage_reset_at:
                usage_cache.text_messages_used = 1  # Reset and count this message
                usage_cache.text_usage_reset_at = (now + relativedelta(months=1)).replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
            else:
                usage_cache.text_messages_used += 1

            usage_cache.last_updated_at = now
        else:
            # Create cache if doesn't exist
            reset_at = (now + relativedelta(months=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            usage_cache = UserUsageCache(
                user_id=owner_id,
                text_messages_used=1,
                text_usage_reset_at=reset_at,
            )
            self.db.add(usage_cache)

        await self.db.flush()

        # Track message recorded in Sentry
        add_breadcrumb(
            message=f"Text message recorded for owner {owner_id}",
            category="text_usage",
            level="info",
            data={
                "owner_id": str(owner_id),
                "total_messages": usage_cache.text_messages_used,
            },
        )

        logger.debug(
            f"Recorded text message for owner {owner_id}. "
            f"Total: {usage_cache.text_messages_used}"
        )

    async def record_multiple_messages(self, persona_id: UUID, message_count: int) -> None:
        """
        Record multiple messages for a persona in one transaction (bulk update).
        Used for batch recording at the end of a text session.
        Uses SELECT ... FOR UPDATE to prevent race conditions.

        Args:
            persona_id: The persona that received the messages
            message_count: Number of messages to record
        """
        if message_count <= 0:
            logger.debug(f"No messages to record for persona {persona_id}")
            return

        # Get persona owner
        query = select(Persona).where(Persona.id == persona_id)
        result = await self.db.execute(query)
        persona = result.scalar_one_or_none()

        if not persona:
            raise ValueError(f"Persona {persona_id} not found")

        await self.record_multiple_messages_for_owner(persona.user_id, message_count)

    async def record_multiple_messages_for_owner(self, owner_id: UUID, message_count: int) -> None:
        """
        Record multiple messages directly for an owner in one transaction (bulk update).
        Uses SELECT ... FOR UPDATE to prevent race conditions.

        Args:
            owner_id: The persona owner's user ID
            message_count: Number of messages to record
        """
        if message_count <= 0:
            logger.debug(f"No messages to record for owner {owner_id}")
            return

        now = datetime.now(timezone.utc)

        # Get or create usage cache with lock
        query = select(UserUsageCache).where(UserUsageCache.user_id == owner_id).with_for_update()
        result = await self.db.execute(query)
        usage_cache = result.scalar_one_or_none()

        if usage_cache:
            # Check if we need to reset first
            if usage_cache.text_usage_reset_at and now >= usage_cache.text_usage_reset_at:
                usage_cache.text_messages_used = message_count  # Reset and count these messages
                usage_cache.text_usage_reset_at = (now + relativedelta(months=1)).replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
            else:
                usage_cache.text_messages_used += message_count

            usage_cache.last_updated_at = now
        else:
            # Create cache if doesn't exist
            reset_at = (now + relativedelta(months=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            usage_cache = UserUsageCache(
                user_id=owner_id,
                text_messages_used=message_count,
                text_usage_reset_at=reset_at,
            )
            self.db.add(usage_cache)

        await self.db.flush()

        # Track messages recorded in Sentry
        add_breadcrumb(
            message=f"{message_count} text messages recorded for owner {owner_id}",
            category="text_usage",
            level="info",
            data={
                "owner_id": str(owner_id),
                "messages_recorded": message_count,
                "total_messages": usage_cache.text_messages_used,
            },
        )

        logger.info(
            f"Recorded {message_count} text messages for owner {owner_id}. "
            f"Total: {usage_cache.text_messages_used}"
        )

    async def get_owner_text_usage(self, user_id: UUID) -> Dict:
        """
        Get text usage stats for a persona owner (for dashboard/API).

        Returns:
            Dictionary with usage stats:
            {
                "messages_used": int,
                "messages_limit": int,  # -1 = unlimited
                "percentage": float,
                "reset_date": str | None,
                "tier_name": str
            }
        """
        # Get tier limit
        limit_messages, tier_name = await self.get_owner_tier_limit(user_id)

        # Get current usage
        used_messages, reset_at = await self.get_owner_usage(user_id)

        # Calculate percentage
        if limit_messages == -1:
            percentage = 0  # Unlimited
        else:
            percentage = (
                round((used_messages / limit_messages * 100), 1) if limit_messages > 0 else 0
            )

        return {
            "messages_used": used_messages,
            "messages_limit": limit_messages,
            "percentage": percentage,
            "reset_date": reset_at.isoformat() if reset_at else None,
            "tier_name": tier_name,
        }
