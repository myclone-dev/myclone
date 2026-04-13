"""
Dataset-related schemas for Langfuse testing
"""

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DatasetItemCreate(BaseModel):
    """Request model for creating a dataset item in Langfuse"""

    user_id: UUID = Field(..., description="User's UUID")
    persona_id: UUID = Field(..., description="Persona's UUID")
    dataset_name: str = Field(..., description="Name of the dataset in Langfuse")
    user_query: str = Field(..., description="Test query/question")
    ground_truth_response: str = Field(..., description="Expected/correct response")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "persona_id": "987fcdeb-51a2-43f8-9876-543210fedcba",
                "dataset_name": "ml-expert-test-cases",
                "user_query": "How do I optimize ML models?",
                "ground_truth_response": "Focus on feature engineering...",
                "metadata": {"category": "optimization"},
            }
        }


class DatasetItemResponse(BaseModel):
    """Response model for dataset item creation"""

    status: str
    dataset_name: str
    item_id: str
    user_query: str
    ground_truth: str
    metadata: Dict[str, Any]
    message: str


class DatasetTraceRequest(BaseModel):
    """Request payload for running prod-eval tracing over a dataset"""

    user_id: UUID
    persona_id: UUID
    dataset_name: str


class DatasetTraceItemResult(BaseModel):
    """Per-item trace result"""

    query: str
    ground_truth: str | None = None
    response: str
    context: List[str]
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    error: Optional[str] = None


class DatasetTraceResponse(BaseModel):
    """Response payload containing overall status and item summaries"""

    status: Literal["success", "partial", "error"]
    dataset_name: str
    persona_id: UUID
    user_id: UUID
    item_count: int
    processed_items: List[DatasetTraceItemResult]
    failures: int = 0


__all__ = [
    "DatasetItemCreate",
    "DatasetItemResponse",
    "DatasetTraceRequest",
    "DatasetTraceResponse",
    "DatasetTraceItemResult",
]
