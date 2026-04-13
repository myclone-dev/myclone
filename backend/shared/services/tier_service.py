"""
Tier-based usage limits service

This service manages usage tracking and limit enforcement for:
1. Raw text files (txt, md)
2. Document files (pdf, docx, xlsx, pptx)
3. Multimedia files (audio, video) with duration tracking
4. YouTube videos (duration-based limits only)

Hard limits that cannot be exceeded even in enterprise tier:
- Multimedia: 6 hours total duration
- YouTube: 2 hours max per video, 1000 videos max
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.database import Persona
from shared.database.models.document import Document
from shared.database.models.tier_plan import (
    SubscriptionStatus,
    TierPlan,
    UserSubscription,
)
from shared.database.models.user import User
from shared.database.models.youtube import YouTubeVideo
from shared.services.text_usage_service import TextUsageService
from shared.services.voice_usage_service import VoiceUsageService

logger = logging.getLogger(__name__)


class TierLimitExceeded(Exception):
    """Raised when a tier limit is exceeded"""

    def __init__(self, message: str, limit_type: str = None):
        super().__init__(message)
        self.limit_type = limit_type


class TierService:
    """Service for managing tier-based usage limits"""

    # File type categorization
    RAW_TEXT_TYPES = {"txt", "md"}
    DOCUMENT_TYPES = {"pdf", "docx", "xlsx", "pptx", "doc", "xls", "ppt"}
    MULTIMEDIA_TYPES = {"mp3", "mp4", "wav", "m4a", "mov", "avi", "mkv", "webm"}

    # Hard limits (cannot be exceeded even in enterprise)
    HARD_LIMIT_MULTIMEDIA_DURATION_HOURS = 6
    HARD_LIMIT_YOUTUBE_VIDEO_DURATION_MINUTES = 120
    HARD_LIMIT_YOUTUBE_VIDEOS = 1000

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_tier_limits(self, user_id: UUID) -> Dict:
        """Fetch user's tier plan limits"""
        query = (
            select(TierPlan)
            .join(UserSubscription, UserSubscription.tier_id == TierPlan.id)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status == SubscriptionStatus.ACTIVE)
        )
        result = await self.db.execute(query)
        tier = result.scalar_one_or_none()

        if not tier:
            # Fallback to free tier if no active subscription
            query = select(TierPlan).where(TierPlan.id == 0)
            result = await self.db.execute(query)
            tier = result.scalar_one()

        return {
            "tier_id": tier.id,  # Add tier_id for template access control
            "tier_name": tier.tier_name,
            # Raw text limits
            "max_raw_text_storage_mb": tier.max_raw_text_storage_mb,
            "max_raw_text_files": tier.max_raw_text_files,
            # Document limits
            "max_document_file_size_mb": tier.max_document_file_size_mb,
            "max_document_storage_mb": tier.max_document_storage_mb,
            "max_document_files": tier.max_document_files,
            # Multimedia limits
            "max_multimedia_file_size_mb": tier.max_multimedia_file_size_mb,
            "max_multimedia_storage_mb": tier.max_multimedia_storage_mb,
            "max_multimedia_files": tier.max_multimedia_files,
            "max_multimedia_duration_hours": tier.max_multimedia_duration_hours,
            # YouTube limits
            "max_youtube_videos": tier.max_youtube_videos,
            "max_youtube_video_duration_minutes": tier.max_youtube_video_duration_minutes,
            "max_youtube_total_duration_hours": tier.max_youtube_total_duration_hours,
            # Persona limits
            "max_personas": tier.max_personas,
            # Custom domain limits
            "max_custom_domains": tier.max_custom_domains,
        }

    def categorize_file_type(self, file_extension: str) -> str:
        """Categorize file type into raw_text, document, or multimedia"""
        ext = file_extension.lower().lstrip(".")

        if ext in self.RAW_TEXT_TYPES:
            return "raw_text"
        elif ext in self.DOCUMENT_TYPES:
            return "document"
        elif ext in self.MULTIMEDIA_TYPES:
            return "multimedia"
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

    async def get_document_usage(self, user_id: UUID) -> Dict:
        """Calculate actual usage from Documents table, categorized by type"""

        # Get all documents for user with file_size
        query = select(Document.document_type, Document.file_size, Document.id).where(
            Document.user_id == user_id
        )

        result = await self.db.execute(query)
        documents = result.all()

        # Initialize usage counters
        usage = {
            "raw_text": {"count": 0, "storage_mb": 0.0, "files": []},
            "document": {"count": 0, "storage_mb": 0.0, "files": []},
            "multimedia": {"count": 0, "storage_mb": 0.0, "duration_hours": 0.0, "files": []},
        }

        for doc_type, file_size, doc_id in documents:
            try:
                category = self.categorize_file_type(doc_type)
                file_size_mb = (file_size or 0) / (1024 * 1024)

                usage[category]["count"] += 1
                usage[category]["storage_mb"] += file_size_mb
                usage[category]["files"].append(str(doc_id))

                # TODO: Add duration tracking for multimedia from metadata
                # For now, duration tracking would need to be added to document metadata

            except ValueError:
                # Unknown file type, skip
                logger.warning(f"Unknown file type: {doc_type}")
                continue

        return usage

    async def get_youtube_usage(self, user_id: UUID) -> Dict:
        """Calculate YouTube usage from youtube_videos table"""
        query = select(
            func.count(YouTubeVideo.id).label("total_videos"),
            func.coalesce(func.sum(YouTubeVideo.duration_seconds), 0).label(
                "total_duration_seconds"
            ),
        ).where(YouTubeVideo.user_id == user_id)

        result = await self.db.execute(query)
        row = result.one()

        return {
            "total_videos": row.total_videos,
            "total_duration_hours": float(row.total_duration_seconds) / 3600,
            "total_duration_minutes": float(row.total_duration_seconds) / 60,
        }

    async def get_persona_count(self, user_id: UUID) -> int:
        """
        Get count of active personas for a user.

        Only counts active personas (is_active=True AND deleted_at IS NULL).
        Soft-deleted personas do not count towards the limit.

        Args:
            user_id: User UUID

        Returns:
            Number of active personas
        """
        query = (
            select(func.count(Persona.id))
            .where(Persona.user_id == user_id)
            .where(Persona.is_active == True)  # noqa: E712
            .where(Persona.deleted_at.is_(None))
        )
        result = await self.db.execute(query)
        count = result.scalar() or 0
        return count

    async def check_persona_creation_allowed(self, user_id: UUID) -> Tuple[bool, int, int]:
        """
        Validate persona creation against tier limits.

        Args:
            user_id: User UUID

        Returns:
            Tuple of (allowed: bool, current_count: int, max_personas: int)
            - allowed: True if user can create more personas
            - current_count: Number of personas user currently has
            - max_personas: Maximum personas allowed (-1 = unlimited)

        Raises:
            TierLimitExceeded: If persona limit is reached
        """
        limits = await self.get_user_tier_limits(user_id)
        current_count = await self.get_persona_count(user_id)
        max_personas = limits.get("max_personas", 1)

        # -1 means unlimited
        if max_personas == -1:
            return True, current_count, max_personas

        if current_count >= max_personas:
            raise TierLimitExceeded(
                f"Persona limit reached: {max_personas} personas. "
                f"Please upgrade your plan to create more personas.",
                limit_type="persona_count",
            )

        return True, current_count, max_personas

    async def check_document_upload_allowed(
        self, user_id: UUID, file_size_bytes: int, file_extension: str, duration_seconds: int = None
    ) -> Tuple[bool, str]:
        """
        Validate document upload against tier limits with row-level locking to prevent race conditions


        Args:
            user_id: User UUID
            file_size_bytes: File size in bytes
            file_extension: File extension (e.g., 'pdf', 'txt', 'mp4')
            duration_seconds: Duration for multimedia files (optional)

        Returns:
            Tuple of (is_allowed: bool, category: str)

        Raises:
            TierLimitExceeded: If any limit is exceeded
        """

        # Acquire row-level lock on user's documents to prevent race conditions
        # This ensures concurrent uploads don't bypass limits
        lock_query = select(Document.id).where(Document.user_id == user_id).with_for_update()
        await self.db.execute(lock_query)

        limits = await self.get_user_tier_limits(user_id)
        usage = await self.get_document_usage(user_id)

        file_size_mb = file_size_bytes / (1024 * 1024)
        category = self.categorize_file_type(file_extension)

        if category == "raw_text":
            # Check raw text limits
            if (
                limits["max_raw_text_files"] != -1
                and usage["raw_text"]["count"] >= limits["max_raw_text_files"]
            ):
                raise TierLimitExceeded(
                    f"Raw text file limit reached: {limits['max_raw_text_files']} files",
                    limit_type="raw_text_count",
                )

            if limits["max_raw_text_storage_mb"] != -1:
                projected = usage["raw_text"]["storage_mb"] + file_size_mb
                if projected > limits["max_raw_text_storage_mb"]:
                    raise TierLimitExceeded(
                        f"Raw text storage limit would be exceeded. "
                        f"Used: {usage['raw_text']['storage_mb']:.2f}MB, "
                        f"Available: {limits['max_raw_text_storage_mb'] - usage['raw_text']['storage_mb']:.2f}MB, "
                        f"Limit: {limits['max_raw_text_storage_mb']}MB",
                        limit_type="raw_text_storage",
                    )

        elif category == "document":
            # Check single file size
            if (
                limits["max_document_file_size_mb"] != -1
                and file_size_mb > limits["max_document_file_size_mb"]
            ):
                raise TierLimitExceeded(
                    f"Document file size {file_size_mb:.2f}MB exceeds limit of {limits['max_document_file_size_mb']}MB",
                    limit_type="document_file_size",
                )

            # Check document count
            if (
                limits["max_document_files"] != -1
                and usage["document"]["count"] >= limits["max_document_files"]
            ):
                raise TierLimitExceeded(
                    f"Document file limit reached: {limits['max_document_files']} files",
                    limit_type="document_count",
                )

            # Check total storage
            if limits["max_document_storage_mb"] != -1:
                projected = usage["document"]["storage_mb"] + file_size_mb
                if projected > limits["max_document_storage_mb"]:
                    raise TierLimitExceeded(
                        f"Document storage limit would be exceeded. "
                        f"Used: {usage['document']['storage_mb']:.2f}MB, "
                        f"Available: {limits['max_document_storage_mb'] - usage['document']['storage_mb']:.2f}MB, "
                        f"Limit: {limits['max_document_storage_mb']}MB",
                        limit_type="document_storage",
                    )

        elif category == "multimedia":
            # Check single file size
            if (
                limits["max_multimedia_file_size_mb"] != -1
                and file_size_mb > limits["max_multimedia_file_size_mb"]
            ):
                raise TierLimitExceeded(
                    f"Multimedia file size {file_size_mb:.2f}MB exceeds limit of {limits['max_multimedia_file_size_mb']}MB",
                    limit_type="multimedia_file_size",
                )

            # Check file count
            if (
                limits["max_multimedia_files"] != -1
                and usage["multimedia"]["count"] >= limits["max_multimedia_files"]
            ):
                raise TierLimitExceeded(
                    f"Multimedia file limit reached: {limits['max_multimedia_files']} files",
                    limit_type="multimedia_count",
                )

            # Check total storage
            if limits["max_multimedia_storage_mb"] != -1:
                projected = usage["multimedia"]["storage_mb"] + file_size_mb
                if projected > limits["max_multimedia_storage_mb"]:
                    raise TierLimitExceeded(
                        f"Multimedia storage limit would be exceeded. "
                        f"Used: {usage['multimedia']['storage_mb']:.2f}MB, "
                        f"Available: {limits['max_multimedia_storage_mb'] - usage['multimedia']['storage_mb']:.2f}MB, "
                        f"Limit: {limits['max_multimedia_storage_mb']}MB",
                        limit_type="multimedia_storage",
                    )

            # Check duration (HARD LIMIT: 6 hours)
            if duration_seconds:
                duration_hours = duration_seconds / 3600

                # Hard limit check (always enforced)
                projected_duration = usage["multimedia"]["duration_hours"] + duration_hours
                if projected_duration > self.HARD_LIMIT_MULTIMEDIA_DURATION_HOURS:
                    raise TierLimitExceeded(
                        f"Multimedia duration hard limit would be exceeded. "
                        f"Used: {usage['multimedia']['duration_hours']:.1f}h, "
                        f"This file: {duration_hours:.1f}h, "
                        f"Hard limit: {self.HARD_LIMIT_MULTIMEDIA_DURATION_HOURS}h",
                        limit_type="multimedia_duration_hard",
                    )

                # Tier-specific limit check
                if limits["max_multimedia_duration_hours"] != -1:
                    if projected_duration > limits["max_multimedia_duration_hours"]:
                        raise TierLimitExceeded(
                            f"Multimedia duration limit would be exceeded. "
                            f"Used: {usage['multimedia']['duration_hours']:.1f}h, "
                            f"This file: {duration_hours:.1f}h, "
                            f"Limit: {limits['max_multimedia_duration_hours']}h",
                            limit_type="multimedia_duration",
                        )

        return True, category

    async def check_youtube_ingest_allowed(
        self, user_id: UUID, video_duration_seconds: int
    ) -> bool:
        """
        Validate YouTube ingestion against tier limits with row-level locking to prevent race conditions


        Hard limits (always enforced):
        - Max 2 hours (120 minutes) per video
        - Max 1000 videos total

        Args:
            user_id: User UUID
            video_duration_seconds: Video duration in seconds

        Raises:
            TierLimitExceeded: If any limit is exceeded
        """

        # Acquire row-level lock on user's YouTube videos to prevent race conditions
        # This ensures concurrent ingests don't bypass limits
        lock_query = (
            select(YouTubeVideo.id).where(YouTubeVideo.user_id == user_id).with_for_update()
        )
        await self.db.execute(lock_query)

        limits = await self.get_user_tier_limits(user_id)
        usage = await self.get_youtube_usage(user_id)

        duration_minutes = video_duration_seconds / 60
        duration_hours = video_duration_seconds / 3600

        # HARD LIMIT: Max 2 hours per video (always enforced)
        if duration_minutes > self.HARD_LIMIT_YOUTUBE_VIDEO_DURATION_MINUTES:
            raise TierLimitExceeded(
                f"YouTube video duration {duration_minutes:.1f} min exceeds hard limit of "
                f"{self.HARD_LIMIT_YOUTUBE_VIDEO_DURATION_MINUTES} min (2 hours)",
                limit_type="youtube_video_duration_hard",
            )

        # Tier-specific single video duration check
        if limits["max_youtube_video_duration_minutes"] != -1:
            if duration_minutes > limits["max_youtube_video_duration_minutes"]:
                raise TierLimitExceeded(
                    f"YouTube video duration {duration_minutes:.1f} min exceeds tier limit of "
                    f"{limits['max_youtube_video_duration_minutes']} min",
                    limit_type="youtube_video_duration",
                )

        # HARD LIMIT: Max 1000 videos (always enforced)
        if usage["total_videos"] >= self.HARD_LIMIT_YOUTUBE_VIDEOS:
            raise TierLimitExceeded(
                f"YouTube video hard limit reached: {self.HARD_LIMIT_YOUTUBE_VIDEOS} videos",
                limit_type="youtube_count_hard",
            )

        # Tier-specific video count check
        if limits["max_youtube_videos"] != -1:
            if usage["total_videos"] >= limits["max_youtube_videos"]:
                raise TierLimitExceeded(
                    f"YouTube video limit reached: {limits['max_youtube_videos']} videos",
                    limit_type="youtube_count",
                )

        # Tier-specific total duration check
        if limits["max_youtube_total_duration_hours"] != -1:
            projected_hours = usage["total_duration_hours"] + duration_hours
            if projected_hours > limits["max_youtube_total_duration_hours"]:
                raise TierLimitExceeded(
                    f"YouTube total duration limit would be exceeded. "
                    f"Used: {usage['total_duration_hours']:.1f}h, "
                    f"This video: {duration_hours:.1f}h, "
                    f"Limit: {limits['max_youtube_total_duration_hours']}h",
                    limit_type="youtube_total_duration",
                )

        return True

    async def get_usage_stats(self, user_id: UUID) -> Dict:
        """Get comprehensive usage statistics for a user"""
        limits = await self.get_user_tier_limits(user_id)
        doc_usage = await self.get_document_usage(user_id)
        youtube_usage = await self.get_youtube_usage(user_id)
        persona_count = await self.get_persona_count(user_id)

        # Get voice usage stats
        voice_service = VoiceUsageService(self.db)
        voice_usage = await voice_service.get_owner_voice_usage(user_id)
        per_persona_usage = await voice_service.get_per_persona_usage(user_id)

        def calc_percentage(used, limit):
            if limit == -1:
                return 0  # Unlimited
            return round((used / limit * 100), 1) if limit > 0 else 0

        return {
            "tier": limits["tier_name"],
            "raw_text": {
                "files": {
                    "used": doc_usage["raw_text"]["count"],
                    "limit": limits["max_raw_text_files"],
                    "percentage": calc_percentage(
                        doc_usage["raw_text"]["count"], limits["max_raw_text_files"]
                    ),
                },
                "storage": {
                    "used_mb": round(doc_usage["raw_text"]["storage_mb"], 2),
                    "limit_mb": limits["max_raw_text_storage_mb"],
                    "percentage": calc_percentage(
                        doc_usage["raw_text"]["storage_mb"], limits["max_raw_text_storage_mb"]
                    ),
                },
            },
            "documents": {
                "files": {
                    "used": doc_usage["document"]["count"],
                    "limit": limits["max_document_files"],
                    "percentage": calc_percentage(
                        doc_usage["document"]["count"], limits["max_document_files"]
                    ),
                },
                "storage": {
                    "used_mb": round(doc_usage["document"]["storage_mb"], 2),
                    "limit_mb": limits["max_document_storage_mb"],
                    "percentage": calc_percentage(
                        doc_usage["document"]["storage_mb"], limits["max_document_storage_mb"]
                    ),
                },
                "max_file_size_mb": limits["max_document_file_size_mb"],
            },
            "multimedia": {
                "files": {
                    "used": doc_usage["multimedia"]["count"],
                    "limit": limits["max_multimedia_files"],
                    "percentage": calc_percentage(
                        doc_usage["multimedia"]["count"], limits["max_multimedia_files"]
                    ),
                },
                "storage": {
                    "used_mb": round(doc_usage["multimedia"]["storage_mb"], 2),
                    "limit_mb": limits["max_multimedia_storage_mb"],
                    "percentage": calc_percentage(
                        doc_usage["multimedia"]["storage_mb"], limits["max_multimedia_storage_mb"]
                    ),
                },
                "duration": {
                    "used_hours": round(doc_usage["multimedia"]["duration_hours"], 2),
                    "limit_hours": limits["max_multimedia_duration_hours"],
                    "hard_limit_hours": self.HARD_LIMIT_MULTIMEDIA_DURATION_HOURS,
                    "percentage": calc_percentage(
                        doc_usage["multimedia"]["duration_hours"],
                        limits["max_multimedia_duration_hours"],
                    ),
                },
                "max_file_size_mb": limits["max_multimedia_file_size_mb"],
            },
            "youtube": {
                "videos": {
                    "used": youtube_usage["total_videos"],
                    "limit": limits["max_youtube_videos"],
                    "hard_limit": self.HARD_LIMIT_YOUTUBE_VIDEOS,
                    "percentage": calc_percentage(
                        youtube_usage["total_videos"], limits["max_youtube_videos"]
                    ),
                },
                "duration": {
                    "used_hours": round(youtube_usage["total_duration_hours"], 2),
                    "limit_hours": limits["max_youtube_total_duration_hours"],
                    "percentage": calc_percentage(
                        youtube_usage["total_duration_hours"],
                        limits["max_youtube_total_duration_hours"],
                    ),
                },
                "max_video_duration_minutes": limits["max_youtube_video_duration_minutes"],
                "hard_limit_video_duration_minutes": self.HARD_LIMIT_YOUTUBE_VIDEO_DURATION_MINUTES,
            },
            "voice": {
                "minutes_used": voice_usage["minutes_used"],
                "minutes_limit": voice_usage["minutes_limit"],
                "percentage": voice_usage["percentage"],
                "reset_date": voice_usage["reset_date"],
                "per_persona": per_persona_usage,
            },
            "text": await self._get_text_usage_stats(user_id),
            "personas": {
                "used": persona_count,
                "limit": limits["max_personas"],
                "percentage": calc_percentage(persona_count, limits["max_personas"]),
            },
            "custom_domains": {
                "limit": limits["max_custom_domains"],
            },
        }

    async def _get_text_usage_stats(self, user_id: UUID) -> Dict:
        """Get text chat usage stats for a user"""
        text_service = TextUsageService(self.db)
        text_usage = await text_service.get_owner_text_usage(user_id)

        return {
            "messages_used": text_usage["messages_used"],
            "messages_limit": text_usage["messages_limit"],
            "percentage": text_usage["percentage"],
            "reset_date": text_usage["reset_date"],
        }

    async def update_user_tier(
        self, user_id: UUID, new_tier_id: int, expires_at: str = None
    ) -> Dict:
        """
        Update a user's tier plan via subscription

        Args:
            user_id: User UUID
            new_tier_id: New tier plan ID (0=free, 1=pro, 2=business, 3=enterprise)
            expires_at: Optional expiration date (ISO format)

        Returns:
            Updated user tier information
        """
        # Verify tier exists
        tier_query = select(TierPlan).where(TierPlan.id == new_tier_id)
        tier_result = await self.db.execute(tier_query)
        tier = tier_result.scalar_one_or_none()

        if not tier:
            raise ValueError(f"Tier plan with ID {new_tier_id} does not exist")

        # Verify user exists
        user_query = select(User).where(User.id == user_id)
        user_result = await self.db.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User with ID {user_id} does not exist")

        # Deactivate current active subscription
        current_sub_query = (
            select(UserSubscription)
            .where(UserSubscription.user_id == user_id)
            .where(UserSubscription.status == SubscriptionStatus.ACTIVE)
        )
        current_sub_result = await self.db.execute(current_sub_query)
        current_sub = current_sub_result.scalar_one_or_none()

        if current_sub:
            current_sub.status = SubscriptionStatus.CANCELLED
            current_sub.updated_at = datetime.now(timezone.utc)

        # Create new subscription
        new_subscription = UserSubscription(
            user_id=user_id,
            tier_id=new_tier_id,
            subscription_start_date=datetime.now(timezone.utc),
            subscription_end_date=(
                datetime.fromisoformat(expires_at.replace("Z", "+00:00")) if expires_at else None
            ),
            status=SubscriptionStatus.ACTIVE,
        )
        self.db.add(new_subscription)

        await self.db.commit()
        await self.db.refresh(new_subscription)

        return {
            "user_id": str(user_id),
            "tier_id": new_tier_id,
            "tier_name": tier.tier_name,
            "subscription_start_date": new_subscription.subscription_start_date.isoformat(),
            "subscription_end_date": (
                new_subscription.subscription_end_date.isoformat()
                if new_subscription.subscription_end_date
                else None
            ),
        }

    async def create_tier_plan(self, tier_data: Dict) -> Dict:
        """
        Create a new tier plan

        Args:
            tier_data: Dictionary containing tier plan fields

        Returns:
            Created tier plan information
        """
        tier = TierPlan(**tier_data)
        self.db.add(tier)
        await self.db.commit()
        await self.db.refresh(tier)

        return {
            "id": tier.id,
            "tier_name": tier.tier_name,
            "created_at": tier.created_at.isoformat(),
        }

    async def delete_tier_plan(self, tier_id: int) -> Dict:
        """
        Delete a tier plan and downgrade affected users to the next lower tier

        Args:
            tier_id: Tier plan ID to delete

        Returns:
            Summary of deletion and user downgrades
        """
        # Prevent deletion of free tier
        if tier_id == 0:
            raise ValueError("Cannot delete the free tier (ID 0)")

        # Get tier to delete
        tier_query = select(TierPlan).where(TierPlan.id == tier_id)
        tier_result = await self.db.execute(tier_query)
        tier = tier_result.scalar_one_or_none()

        if not tier:
            raise ValueError(f"Tier plan with ID {tier_id} does not exist")

        # Find active subscriptions on this tier
        subs_query = (
            select(UserSubscription)
            .where(UserSubscription.tier_id == tier_id)
            .where(UserSubscription.status == SubscriptionStatus.ACTIVE)
        )
        subs_result = await self.db.execute(subs_query)
        affected_subscriptions = subs_result.scalars().all()

        # Determine downgrade tier (one level lower)
        downgrade_tier_id = max(0, tier_id - 1)

        # Update affected subscriptions
        for subscription in affected_subscriptions:
            subscription.tier_id = downgrade_tier_id
            subscription.updated_at = datetime.now(timezone.utc)

        # Delete the tier
        await self.db.delete(tier)
        await self.db.commit()

        return {
            "deleted_tier_id": tier_id,
            "deleted_tier_name": tier.tier_name,
            "affected_users_count": len(affected_subscriptions),
            "downgraded_to_tier_id": downgrade_tier_id,
        }

    async def update_tier_limits(self, tier_id: int, limit_updates: Dict) -> Dict:
        """
        Update limits for a specific tier plan

        Args:
            tier_id: Tier plan ID to update
            limit_updates: Dictionary of fields to update

        Returns:
            Updated tier plan information
        """
        # Get tier
        tier_query = select(TierPlan).where(TierPlan.id == tier_id)
        tier_result = await self.db.execute(tier_query)
        tier = tier_result.scalar_one_or_none()

        if not tier:
            raise ValueError(f"Tier plan with ID {tier_id} does not exist")

        # Update allowed fields
        allowed_fields = {
            "max_raw_text_storage_mb",
            "max_raw_text_files",
            "max_document_file_size_mb",
            "max_document_storage_mb",
            "max_document_files",
            "max_multimedia_file_size_mb",
            "max_multimedia_storage_mb",
            "max_multimedia_files",
            "max_multimedia_duration_hours",
            "max_youtube_videos",
            "max_youtube_video_duration_minutes",
            "max_youtube_total_duration_hours",
        }

        updated_fields = []
        for field, value in limit_updates.items():
            if field in allowed_fields:
                setattr(tier, field, value)
                updated_fields.append(field)

        tier.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(tier)

        return {
            "tier_id": tier.id,
            "tier_name": tier.tier_name,
            "updated_fields": updated_fields,
            "updated_at": tier.updated_at.isoformat(),
        }

    async def get_all_tier_plans(self) -> list[Dict]:
        """Get all tier plans"""
        query = select(TierPlan).order_by(TierPlan.id)
        result = await self.db.execute(query)
        tiers = result.scalars().all()

        return [
            {
                "id": tier.id,
                "tier_name": tier.tier_name,
                "max_raw_text_storage_mb": tier.max_raw_text_storage_mb,
                "max_raw_text_files": tier.max_raw_text_files,
                "max_document_file_size_mb": tier.max_document_file_size_mb,
                "max_document_storage_mb": tier.max_document_storage_mb,
                "max_document_files": tier.max_document_files,
                "max_multimedia_file_size_mb": tier.max_multimedia_file_size_mb,
                "max_multimedia_storage_mb": tier.max_multimedia_storage_mb,
                "max_multimedia_files": tier.max_multimedia_files,
                "max_multimedia_duration_hours": tier.max_multimedia_duration_hours,
                "max_youtube_videos": tier.max_youtube_videos,
                "max_youtube_video_duration_minutes": tier.max_youtube_video_duration_minutes,
                "max_youtube_total_duration_hours": tier.max_youtube_total_duration_hours,
                "max_personas": tier.max_personas,
                "max_custom_domains": tier.max_custom_domains,
                "created_at": tier.created_at.isoformat(),
                "updated_at": tier.updated_at.isoformat(),
            }
            for tier in tiers
        ]
