"""
Voice clone service for shared logic across Cartesia and ElevenLabs APIs.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.database.models.tier_plan import SubscriptionStatus, TierPlan, UserSubscription
from shared.database.repositories.voice_clone_repository import VoiceCloneRepository


async def check_voice_clone_limit(session: AsyncSession, user_id: UUID) -> tuple[bool, int, int]:
    """
    Check if user has reached their voice clone limit.

    Args:
        session: Database session
        user_id: User UUID

    Returns:
        Tuple of (can_create: bool, current_count: int, max_allowed: int)
        max_allowed = -1 means unlimited
    """
    # Get user's subscription and tier plan
    stmt = (
        select(UserSubscription)
        .where(
            UserSubscription.user_id == user_id,
            UserSubscription.status == SubscriptionStatus.ACTIVE,
        )
        .options(selectinload(UserSubscription.tier_plan))
    )
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()

    # Default to free tier if no subscription
    if subscription:
        max_voice_clones = subscription.tier_plan.max_voice_clones
    else:
        # Get free tier limits
        tier_stmt = select(TierPlan).where(TierPlan.id == 0)
        tier_result = await session.execute(tier_stmt)
        free_tier = tier_result.scalar_one_or_none()
        max_voice_clones = free_tier.max_voice_clones if free_tier else 1

    # Get current voice clone count
    current_count = await VoiceCloneRepository.count_by_user_id(session, user_id)

    # -1 means unlimited
    if max_voice_clones == -1:
        return (True, current_count, max_voice_clones)

    can_create = current_count < max_voice_clones
    return (can_create, current_count, max_voice_clones)
