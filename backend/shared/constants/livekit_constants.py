"""
LiveKit Constants

Configuration and constants for LiveKit voice recording functionality.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.tier_plan import (
    SubscriptionStatus,
    TierPlan,
    UserSubscription,
)
from shared.monitoring.sentry_utils import add_breadcrumb, capture_exception_with_context

# Legacy: Recording Allowed User IDs (deprecated - use tier-based check instead)
# Kept for backwards compatibility, can be removed after migration is verified
RECORDING_ALLOWED_USER_IDS: set[UUID] = set()


async def is_recording_allowed_for_user(user_id: UUID, db: AsyncSession) -> bool:
    """
    Check if user's subscription tier allows voice recording.

    Recording is enabled for enterprise tier users only.

    Args:
        user_id: The user ID to check
        db: SQLAlchemy async session for database operations

    Returns:
        True if recording is allowed for this user (enterprise tier), False otherwise
    """
    try:
        # Query user's active subscription tier
        query = (
            select(TierPlan.tier_name)
            .join(UserSubscription, UserSubscription.tier_id == TierPlan.id)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status == SubscriptionStatus.ACTIVE)
        )
        result = await db.execute(query)
        tier_name = result.scalar_one_or_none()

        # Recording enabled for enterprise tier only
        is_allowed = tier_name == "enterprise"

        add_breadcrumb(
            message="Recording permission check",
            category="recording",
            level="info",
            data={
                "user_id": str(user_id),
                "tier_name": tier_name or "none",
                "allowed": is_allowed,
            },
        )

        return is_allowed

    except Exception as e:
        capture_exception_with_context(
            e,
            extra={"user_id": str(user_id)},
            tags={"component": "recording", "operation": "permission_check"},
        )
        # Default to not recording on error (safe default)
        return False
