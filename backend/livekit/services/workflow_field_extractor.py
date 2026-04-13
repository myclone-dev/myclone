"""
Workflow Field Extraction Models.

Contains Pydantic models for extracted field values used by the single-LLM
lead capture approach.

Note: The WorkflowFieldExtractor class (dual-LLM approach) has been removed.
Field extraction is now done directly by the main LLM via update_lead_field() tool.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExtractedFieldValue(BaseModel):
    """Represents a single extracted field with metadata.

    Used by:
    - WorkflowHandler.store_extracted_field() to build extracted field data
    - workflow_sessions.extracted_fields JSONB column schema
    """

    value: Any = Field(..., description="Extracted value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    extraction_method: str = Field(
        ...,
        description="How field was extracted: direct_tool_call, natural_language, inference",
    )
    raw_input: str = Field(..., description="Original user input that led to extraction")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)

    def model_dump(self, **kwargs) -> dict:
        """Override model_dump to serialize datetime to ISO string for JSON compatibility."""
        data = super().model_dump(**kwargs)
        # Convert datetime to ISO string for JSONB storage
        if isinstance(data.get("extracted_at"), datetime):
            data["extracted_at"] = data["extracted_at"].isoformat()
        return data
