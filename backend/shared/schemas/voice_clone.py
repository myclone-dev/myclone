"""
Voice clone schemas for unified API responses
"""

from typing import Optional

from pydantic import BaseModel, Field


class VoiceCloneListItem(BaseModel):
    """
    Voice clone metadata for listing (unified across all platforms)

    Platform field indicates the source: elevenlabs or cartesia
    """

    id: str = Field(..., description="Voice clone record UUID")
    voice_id: str = Field(..., description="Platform-specific voice ID")
    name: str = Field(..., description="Voice clone name")
    description: Optional[str] = Field(None, description="Voice clone description")
    platform: str = Field(..., description="Voice platform: elevenlabs or cartesia")
    total_files: int = Field(..., description="Number of sample files")
    total_size_bytes: int = Field(..., description="Total size of samples in bytes")
    created_at: str = Field(..., description="ISO 8601 timestamp")


class VoiceCloneDetailResponse(BaseModel):
    """Detailed voice clone information including sample files"""

    id: str
    user_id: str
    voice_id: str
    name: str
    description: Optional[str]
    platform: str
    model: Optional[str]
    sample_files: list  # List of S3 metadata dicts
    settings: dict  # Platform-specific settings
    total_files: int
    total_size_bytes: int
    created_at: str
    updated_at: str


class VoiceCloneDeleteResponse(BaseModel):
    """Response model for voice clone deletion"""

    voice_id: str = Field(..., description="Deleted voice ID")
    platform: str = Field(..., description="Platform the voice was deleted from")
    status: str = Field(..., description="Deletion status: success or partial")
    message: str = Field(..., description="Human-readable message")
    platform_deleted: bool = Field(
        default=False, description="Whether voice was deleted from platform API"
    )
    database_deleted: bool = Field(
        default=False, description="Whether voice was deleted from database"
    )
