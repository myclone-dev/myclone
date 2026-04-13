"""
Voice usage service for tracking and limiting voice chat usage.

Voice usage is charged to the PERSONA OWNER, not the caller.
When anyone calls a persona, the owner's monthly quota is consumed.

Tier limits:
- Free (0): 10 minutes/month
- Pro (1): 100 minutes/month
- Business (2): 400 minutes/month
- Enterprise (3): Unlimited (-1)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.database import Persona
from shared.database.models.tier_plan import (
    SubscriptionStatus,
    TierPlan,
    UserSubscription,
    UserUsageCache,
)
from shared.database.models.voice_session import VoiceSession, VoiceSessionStatus
from shared.monitoring.sentry_utils import (
    add_breadcrumb,
    capture_message,
)

logger = logging.getLogger(__name__)


class VoiceLimitExceeded(Exception):
    """Raised when voice usage limit is exceeded"""

    def __init__(self, message: str, used_seconds: int = 0, limit_seconds: int = 0):
        super().__init__(message)
        self.used_seconds = used_seconds
        self.limit_seconds = limit_seconds


class VoiceUsageService:
    """Service for managing voice chat usage limits based on persona owner's tier"""

    # Grace period in seconds (30 seconds for goodbye)
    GRACE_PERIOD_SECONDS = 30

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_owner_tier_limit(self, owner_id: UUID) -> Tuple[int, str]:
        """
        Get the voice minutes limit for a persona owner based on their tier.

        Returns:
            Tuple of (limit_seconds, tier_name)
            limit_seconds = -1 means unlimited
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

        # Convert minutes to seconds (-1 stays as -1 for unlimited)
        limit_seconds = (
            tier.max_voice_minutes_per_month * 60 if tier.max_voice_minutes_per_month != -1 else -1
        )

        return limit_seconds, tier.tier_name

    async def get_owner_usage(self, owner_id: UUID) -> Tuple[int, datetime]:
        """
        Get the current voice usage for a persona owner.

        Returns:
            Tuple of (used_seconds, reset_at)
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
                voice_seconds_used=0,
                voice_usage_reset_at=reset_at,
            )
            self.db.add(usage_cache)
            await self.db.flush()
            return 0, reset_at

        # Check if we need to reset (past reset date)
        if usage_cache.voice_usage_reset_at and now >= usage_cache.voice_usage_reset_at:
            # Reset usage and set new reset date
            usage_cache.voice_seconds_used = 0
            usage_cache.voice_usage_reset_at = (now + relativedelta(months=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            usage_cache.last_updated_at = now
            await self.db.flush()
            return 0, usage_cache.voice_usage_reset_at

        # Set reset date if not set
        if not usage_cache.voice_usage_reset_at:
            usage_cache.voice_usage_reset_at = (now + relativedelta(months=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            await self.db.flush()

        return usage_cache.voice_seconds_used, usage_cache.voice_usage_reset_at

    async def check_owner_voice_limit(self, persona_id: UUID) -> Tuple[bool, int, int]:
        """
        Check if the persona owner has remaining voice quota.

        Args:
            persona_id: The persona being called

        Returns:
            Tuple of (can_start, remaining_seconds, limit_seconds)
            remaining_seconds = -1 means unlimited
        """
        # Get persona owner
        query = select(Persona).where(Persona.id == persona_id)
        result = await self.db.execute(query)
        persona = result.scalar_one_or_none()

        if not persona:
            raise ValueError(f"Persona {persona_id} not found")

        owner_id = persona.user_id

        # Get owner's tier limit
        limit_seconds, tier_name = await self.get_owner_tier_limit(owner_id)

        # Unlimited tier
        if limit_seconds == -1:
            return True, -1, -1

        # Get current usage
        used_seconds, _ = await self.get_owner_usage(owner_id)

        remaining_seconds = max(0, limit_seconds - used_seconds)

        # Allow start if there's any remaining time
        can_start = remaining_seconds > 0

        if not can_start:
            logger.warning(
                f"Voice limit exceeded for owner {owner_id}. "
                f"Used: {used_seconds}s, Limit: {limit_seconds}s"
            )
            # Track voice limit exceeded event in Sentry
            capture_message(
                f"Voice limit exceeded for owner {owner_id}",
                level="warning",
                tags={
                    "event_type": "voice_limit_exceeded",
                    "persona_id": str(persona_id),
                    "owner_id": str(owner_id),
                },
                extra={
                    "used_seconds": used_seconds,
                    "limit_seconds": limit_seconds,
                    "percentage": (
                        round(used_seconds / limit_seconds * 100, 1) if limit_seconds > 0 else 0
                    ),
                },
            )

        return can_start, remaining_seconds, limit_seconds

    async def start_voice_session(
        self,
        persona_id: UUID,
        room_name: str,
        session_token: Optional[str] = None,
    ) -> VoiceSession:
        """
        Start a new voice session and record it.

        Args:
            persona_id: The persona being called
            room_name: LiveKit room name
            session_token: Caller's session token (for analytics)

        Returns:
            Created VoiceSession
        """
        # Get persona to find owner
        query = select(Persona).where(Persona.id == persona_id)
        result = await self.db.execute(query)
        persona = result.scalar_one_or_none()

        if not persona:
            raise ValueError(f"Persona {persona_id} not found")

        # Create voice session
        session = VoiceSession(
            persona_id=persona_id,
            persona_owner_id=persona.user_id,
            caller_session_token=session_token,
            room_name=room_name,
            status=VoiceSessionStatus.ACTIVE,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)

        logger.info(
            f"Started voice session {session.id} for persona {persona_id}, "
            f"owner {persona.user_id}"
        )

        # Track session start in Sentry
        add_breadcrumb(
            message=f"Voice session started: {session.id}",
            category="voice_session",
            level="info",
            data={
                "session_id": str(session.id),
                "persona_id": str(persona_id),
                "owner_id": str(persona.user_id),
                "room_name": room_name,
            },
        )

        return session

    async def update_session_duration(
        self, session_id: UUID, duration_seconds: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Update the duration of an active session (heartbeat).
        Also checks if the owner's limit has been reached.

        Args:
            session_id: Voice session ID
            duration_seconds: Current session duration in seconds

        Returns:
            Tuple of (should_continue, reason)
            should_continue = False means the call should be disconnected
        """
        # Get session with lock
        query = select(VoiceSession).where(VoiceSession.id == session_id).with_for_update()
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()

        if not session:
            logger.warning(f"Voice session {session_id} not found")
            return False, "session_not_found"

        if session.status != VoiceSessionStatus.ACTIVE:
            return False, "session_ended"

        # Update duration
        session.duration_seconds = duration_seconds
        session.ended_at = datetime.now(timezone.utc)  # Update last activity

        # Get owner's limit and usage
        limit_seconds, _ = await self.get_owner_tier_limit(session.persona_owner_id)

        # Unlimited tier - always continue
        if limit_seconds == -1:
            await self.db.flush()
            return True, None

        # Calculate total usage including this session
        used_seconds, _ = await self.get_owner_usage(session.persona_owner_id)

        # Add this session's NEW duration (delta from last heartbeat)
        # For simplicity, we track total duration and will update cache on end
        total_with_session = used_seconds + duration_seconds

        # Check if limit exceeded (with grace period)
        if total_with_session >= limit_seconds + self.GRACE_PERIOD_SECONDS:
            session.status = VoiceSessionStatus.LIMIT_EXCEEDED
            await self.db.flush()
            logger.warning(
                f"Voice limit exceeded during session {session_id}. "
                f"Total: {total_with_session}s, Limit: {limit_seconds}s"
            )
            # Track mid-call limit exceeded in Sentry
            capture_message(
                f"Voice limit exceeded mid-call for session {session_id}",
                level="warning",
                tags={
                    "event_type": "voice_limit_exceeded_mid_call",
                    "session_id": str(session_id),
                    "owner_id": str(session.persona_owner_id),
                },
                extra={
                    "total_with_session": total_with_session,
                    "limit_seconds": limit_seconds,
                    "duration_seconds": duration_seconds,
                    "persona_id": str(session.persona_id),
                },
            )
            return False, "limit_exceeded"

        await self.db.flush()
        return True, None

    async def end_voice_session(
        self, session_id: UUID, final_duration_seconds: int
    ) -> VoiceSession:
        """
        End a voice session and update the owner's usage.

        Args:
            session_id: Voice session ID
            final_duration_seconds: Final session duration in seconds

        Returns:
            Updated VoiceSession
        """
        # Get session with lock
        query = select(VoiceSession).where(VoiceSession.id == session_id).with_for_update()
        result = await self.db.execute(query)
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError(f"Voice session {session_id} not found")

        # Update session
        now = datetime.now(timezone.utc)
        session.duration_seconds = final_duration_seconds
        session.ended_at = now

        # Only update status if still active
        if session.status == VoiceSessionStatus.ACTIVE:
            session.status = VoiceSessionStatus.COMPLETED

        # Update owner's usage cache
        usage_query = (
            select(UserUsageCache)
            .where(UserUsageCache.user_id == session.persona_owner_id)
            .with_for_update()
        )
        usage_result = await self.db.execute(usage_query)
        usage_cache = usage_result.scalar_one_or_none()

        if usage_cache:
            usage_cache.voice_seconds_used += final_duration_seconds
            usage_cache.last_updated_at = now
        else:
            # Create cache if doesn't exist
            reset_at = (now + relativedelta(months=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            usage_cache = UserUsageCache(
                user_id=session.persona_owner_id,
                voice_seconds_used=final_duration_seconds,
                voice_usage_reset_at=reset_at,
            )
            self.db.add(usage_cache)

        await self.db.flush()
        await self.db.refresh(session)

        logger.info(
            f"Ended voice session {session_id}. Duration: {final_duration_seconds}s, "
            f"Owner usage now: {usage_cache.voice_seconds_used}s"
        )

        # Track session end in Sentry
        add_breadcrumb(
            message=f"Voice session ended: {session_id}",
            category="voice_session",
            level="info",
            data={
                "session_id": str(session_id),
                "final_duration_seconds": final_duration_seconds,
                "owner_id": str(session.persona_owner_id),
                "status": session.status.value,
                "total_usage_seconds": usage_cache.voice_seconds_used,
            },
        )

        return session

    async def get_session_by_id(self, session_id: UUID) -> Optional[VoiceSession]:
        """Get a voice session by ID"""
        query = select(VoiceSession).where(VoiceSession.id == session_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_session_by_room(self, room_name: str) -> Optional[VoiceSession]:
        """Get an active voice session by room name"""
        query = select(VoiceSession).where(
            and_(
                VoiceSession.room_name == room_name,
                VoiceSession.status == VoiceSessionStatus.ACTIVE,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_owner_voice_usage(self, user_id: UUID) -> Dict:
        """
        Get voice usage stats for a persona owner (for dashboard).

        Returns:
            Dictionary with usage stats including per-persona breakdown
        """
        # Get tier limit
        limit_seconds, tier_name = await self.get_owner_tier_limit(user_id)

        # Get current usage
        used_seconds, reset_at = await self.get_owner_usage(user_id)

        # Calculate percentage
        if limit_seconds == -1:
            percentage = 0  # Unlimited
        else:
            percentage = round((used_seconds / limit_seconds * 100), 1) if limit_seconds > 0 else 0

        # Convert to minutes for display
        used_minutes = round(used_seconds / 60, 1)
        limit_minutes = limit_seconds // 60 if limit_seconds != -1 else -1

        return {
            "minutes_used": used_minutes,
            "minutes_limit": limit_minutes,
            "percentage": percentage,
            "reset_date": reset_at.isoformat() if reset_at else None,
            "tier_name": tier_name,
        }

    async def get_per_persona_usage(self, user_id: UUID) -> List[Dict]:
        """
        Get voice usage breakdown by persona for the current billing period.

        Args:
            user_id: Persona owner's user ID

        Returns:
            List of per-persona usage dictionaries
        """
        # Get reset date to determine billing period start
        _, reset_at = await self.get_owner_usage(user_id)

        # Calculate billing period start (1 month before reset)
        period_start = reset_at - relativedelta(months=1) if reset_at else None

        # Query completed sessions grouped by persona
        query = (
            select(
                VoiceSession.persona_id,
                Persona.persona_name,
                Persona.name.label("display_name"),
                func.sum(VoiceSession.duration_seconds).label("total_seconds"),
            )
            .join(Persona, Persona.id == VoiceSession.persona_id)
            .where(VoiceSession.persona_owner_id == user_id)
            .where(
                VoiceSession.status.in_(
                    [
                        VoiceSessionStatus.COMPLETED,
                        VoiceSessionStatus.LIMIT_EXCEEDED,
                        VoiceSessionStatus.DISCONNECTED,
                    ]
                )
            )
        )

        if period_start:
            query = query.where(VoiceSession.started_at >= period_start)

        query = query.group_by(
            VoiceSession.persona_id,
            Persona.persona_name,
            Persona.name,
        ).order_by(func.sum(VoiceSession.duration_seconds).desc())

        result = await self.db.execute(query)
        rows = result.all()

        return [
            {
                "persona_id": str(row.persona_id),
                "persona_name": row.persona_name,
                "display_name": row.display_name,
                "minutes_used": round(row.total_seconds / 60, 1),
            }
            for row in rows
        ]

    async def cleanup_stale_sessions(self, timeout_minutes: int = 15) -> int:
        """
        Clean up stale active sessions that haven't had activity.
        Should be run as a periodic background job.

        Args:
            timeout_minutes: Minutes of inactivity before marking as timeout

        Returns:
            Number of sessions cleaned up
        """
        cutoff = datetime.now(timezone.utc) - relativedelta(minutes=timeout_minutes)
        # Grace period for sessions that never sent a heartbeat (5 min startup time)
        startup_grace = datetime.now(timezone.utc) - relativedelta(minutes=timeout_minutes + 5)

        # Find stale active sessions:
        # 1. Sessions with heartbeat activity that have gone stale (ended_at < cutoff)
        # 2. Sessions that never sent a heartbeat (ended_at is NULL) and started > 5 min + timeout ago
        query = (
            select(VoiceSession)
            .where(VoiceSession.status == VoiceSessionStatus.ACTIVE)
            .where(
                or_(
                    # Heartbeat timeout - ended_at is set but old
                    VoiceSession.ended_at < cutoff,
                    # Never sent heartbeat - started long ago with no activity
                    and_(
                        VoiceSession.ended_at.is_(None),
                        VoiceSession.started_at < startup_grace,
                    ),
                )
            )
        )
        result = await self.db.execute(query)
        stale_sessions = result.scalars().all()

        cleaned = 0
        for session in stale_sessions:
            session.status = VoiceSessionStatus.TIMEOUT
            session.ended_at = datetime.now(timezone.utc)

            # Update owner's usage with the recorded duration
            if session.duration_seconds > 0:
                usage_query = select(UserUsageCache).where(
                    UserUsageCache.user_id == session.persona_owner_id
                )
                usage_result = await self.db.execute(usage_query)
                usage_cache = usage_result.scalar_one_or_none()

                if usage_cache:
                    usage_cache.voice_seconds_used += session.duration_seconds
                    usage_cache.last_updated_at = datetime.now(timezone.utc)

            cleaned += 1
            logger.info(f"Cleaned up stale voice session {session.id}")

        if cleaned > 0:
            await self.db.flush()
            # Track stale session cleanup in Sentry
            capture_message(
                f"Cleaned up {cleaned} stale voice sessions",
                level="info",
                tags={"event_type": "voice_session_cleanup"},
                extra={"cleaned_count": cleaned, "timeout_minutes": timeout_minutes},
            )

        return cleaned
