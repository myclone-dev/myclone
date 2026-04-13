"""
Pydantic schemas for tier plans, subscriptions, and usage tracking
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SubscriptionStatusEnum(str, Enum):
    """Subscription status enum"""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"


class TierPlanResponse(BaseModel):
    """Response schema for tier plan details"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tier_name: str

    # Raw text limits
    max_raw_text_storage_mb: int
    max_raw_text_files: int

    # Document limits
    max_document_file_size_mb: int
    max_document_storage_mb: int
    max_document_files: int

    # Multimedia limits
    max_multimedia_file_size_mb: int
    max_multimedia_storage_mb: int
    max_multimedia_files: int
    max_multimedia_duration_hours: int

    # YouTube limits
    max_youtube_videos: int
    max_youtube_video_duration_minutes: int
    max_youtube_total_duration_hours: int

    # Voice clone limits
    max_voice_clones: int

    created_at: datetime
    updated_at: datetime


class UserSubscriptionResponse(BaseModel):
    """Response schema for user subscription"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    tier_id: int
    subscription_start_date: datetime
    subscription_end_date: Optional[datetime]
    status: SubscriptionStatusEnum
    created_at: datetime
    updated_at: datetime

    # Include tier plan details
    tier_plan: Optional[TierPlanResponse] = None


class UserUsageCacheResponse(BaseModel):
    """Response schema for user usage cache"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int

    # Raw text usage
    raw_text_storage_bytes: int
    raw_text_file_count: int

    # Document usage
    document_storage_bytes: int
    document_file_count: int

    # Multimedia usage
    multimedia_storage_bytes: int
    multimedia_file_count: int
    multimedia_total_duration_seconds: int

    # YouTube usage
    youtube_video_count: int
    youtube_total_duration_seconds: int

    last_updated_at: datetime
    created_at: datetime


class UserUsageWithLimitsResponse(BaseModel):
    """Combined response showing usage and limits"""

    # Current usage
    usage: UserUsageCacheResponse

    # Current tier limits
    tier: TierPlanResponse

    # Subscription details
    subscription: UserSubscriptionResponse

    # Helper fields for frontend
    raw_text_usage_mb: float
    raw_text_limit_mb: int
    raw_text_percentage: float

    document_usage_mb: float
    document_limit_mb: int
    document_percentage: float

    multimedia_usage_mb: float
    multimedia_limit_mb: int
    multimedia_duration_hours: float
    multimedia_duration_percentage: float

    youtube_duration_hours: float
    youtube_duration_percentage: float


class SubscriptionUpgradeRequest(BaseModel):
    """Request to upgrade/downgrade subscription"""

    tier_id: int
    subscription_end_date: Optional[datetime] = None


class SubscriptionCreateRequest(BaseModel):
    """Request to create a new subscription"""

    user_id: int
    tier_id: int
    subscription_end_date: Optional[datetime] = None
    status: SubscriptionStatusEnum = SubscriptionStatusEnum.ACTIVE
