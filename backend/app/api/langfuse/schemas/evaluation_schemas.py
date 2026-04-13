"""
Evaluation-related schemas for Langfuse prompt testing
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ABTestRequest(BaseModel):
    """Request for A/B testing two prompt versions"""

    user_id: UUID = Field(..., description="User's UUID")
    persona_id: UUID = Field(..., description="Persona's UUID")
    prompt_name_a: str = Field(..., description="First prompt template name")
    prompt_name_b: str = Field(..., description="Second prompt template name")
    version_a: Optional[int] = Field(None, description="Version of prompt A (null = latest)")
    version_b: Optional[int] = Field(None, description="Version of prompt B (null = latest)")
    user_query: str = Field(..., description="User's question to test with")
    include_rag_context: bool = Field(False, description="Include RAG context in prompts")
    rag_query: Optional[str] = Field(
        None, description="Query for RAG retrieval (defaults to user_query)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "persona_id": "987fcdeb-51a2-43f8-9876-543210fedcba",
                "prompt_name_a": "persona-expert-v1",
                "prompt_name_b": "persona-expert-v2",
                "user_query": "How do I optimize ML models?",
                "include_rag_context": True,
            }
        }


class ABTestResponse(BaseModel):
    """Response from A/B test"""

    status: str
    variant_a: Dict[str, Any]
    variant_b: Dict[str, Any]
    message: str


class GroundTruthEvalRequest(BaseModel):
    """Request for ground truth evaluation"""

    user_id: UUID = Field(..., description="User's UUID")
    persona_id: UUID = Field(..., description="Persona's UUID")
    prompt_name: str = Field(..., description="Langfuse prompt template name")
    version: Optional[int] = Field(None, description="Prompt version (null = latest)")
    query: str = Field(..., description="Test query")
    ground_truth_response: str = Field(..., description="Expected/ideal response")
    include_rag_context: bool = Field(False, description="Include RAG context")
    rag_query: Optional[str] = Field(None, description="Query for RAG retrieval")
    evaluation_criteria: Optional[List[str]] = Field(
        default_factory=lambda: ["accuracy", "relevance", "completeness"],
        description="Criteria to evaluate against",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "persona_id": "987fcdeb-51a2-43f8-9876-543210fedcba",
                "prompt_name": "persona-expert-v1",
                "query": "What is the best approach to model deployment?",
                "ground_truth_response": "The best approach involves containerization...",
                "include_rag_context": True,
            }
        }


class GroundTruthEvalResponse(BaseModel):
    """Response from ground truth evaluation"""

    status: str
    prompt_name: str
    version: int
    compiled_prompt: str
    generated_response: str
    ground_truth: str
    evaluation_scores: Dict[str, float]
    overall_score: float
    langfuse_trace_id: Optional[str] = None
    message: str


class LLMJudgeEvalRequest(BaseModel):
    """Request for LLM-as-judge evaluation"""

    user_id: UUID = Field(..., description="User's UUID")
    persona_id: UUID = Field(..., description="Persona's UUID")
    prompt_name: str = Field(..., description="Langfuse prompt template name")
    version: Optional[int] = Field(None, description="Prompt version (null = latest)")
    query: str = Field(..., description="Test query")
    response: Optional[str] = Field(
        None, description="Response to evaluate (if None, will generate)"
    )
    include_rag_context: bool = Field(False, description="Include RAG context")
    rag_query: Optional[str] = Field(None, description="Query for RAG retrieval")
    judge_criteria: Optional[List[str]] = Field(
        default_factory=lambda: ["helpfulness", "accuracy", "clarity", "relevance"],
        description="Criteria for judge to evaluate",
    )
    judge_model: str = Field("gpt-4o", description="Model to use as judge")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "persona_id": "987fcdeb-51a2-43f8-9876-543210fedcba",
                "prompt_name": "persona-expert-v1",
                "query": "How should I structure my ML pipeline?",
                "include_rag_context": True,
            }
        }


class LLMJudgeEvalResponse(BaseModel):
    """Response from LLM-as-judge evaluation"""

    status: str
    prompt_name: str
    version: int
    compiled_prompt: str
    generated_response: str
    judge_evaluation: Dict[str, Any]
    scores: Dict[str, float]
    overall_score: float
    judge_reasoning: str
    langfuse_trace_id: Optional[str] = None
    message: str


class LLMJudgePerformanceRequest(BaseModel):
    """Request for LLM-as-judge evaluation with performance metrics"""

    user_id: UUID = Field(..., description="User's UUID")
    persona_id: UUID = Field(..., description="Persona's UUID")
    prompt_name: str = Field(..., description="Langfuse prompt template name")
    version: Optional[int] = Field(None, description="Prompt version (null = latest)")
    query: str = Field(..., description="Test query")
    response: Optional[str] = Field(None, description="Response to evaluate (if None, generates)")
    include_rag_context: bool = Field(False, description="Include RAG context")
    rag_query: Optional[str] = Field(None, description="Query for RAG retrieval")
    performance_metrics: List[str] = Field(
        default_factory=lambda: ["latency", "token_efficiency", "relevance", "quality"],
        description="Performance metrics to evaluate",
    )
    judge_criteria: Optional[List[str]] = Field(
        default_factory=lambda: ["helpfulness", "accuracy", "clarity"],
        description="Judge criteria",
    )
    judge_model: str = Field("gpt-4o", description="Model to use as judge")
    measure_generation_time: bool = Field(True, description="Measure response generation time")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "persona_id": "987fcdeb-51a2-43f8-9876-543210fedcba",
                "prompt_name": "persona-expert-v1",
                "query": "How do I scale ML infrastructure?",
                "performance_metrics": ["latency", "token_efficiency", "quality"],
            }
        }


class LLMJudgePerformanceResponse(BaseModel):
    """Response from LLM-as-judge performance evaluation"""

    status: str
    prompt_name: str
    version: int
    compiled_prompt: str
    generated_response: str
    performance_metrics: Dict[str, Any]
    judge_evaluation: Dict[str, Any]
    quality_scores: Dict[str, float]
    overall_quality_score: float
    generation_time_ms: Optional[float] = None
    token_count: int
    langfuse_trace_id: Optional[str] = None
    message: str


# -------------------- RAG Evaluation Schemas (moved) -------------------- #


class LlamaRAGEvalQuery(BaseModel):
    query: str = Field(..., description="User query / question to evaluate")
    ground_truth: Optional[str] = Field(
        None, description="Optional ground truth answer for relevancy metrics"
    )


class LlamaRAGEvalParams(BaseModel):
    top_k: Optional[int] = Field(
        5, ge=1, le=50, description="Number of chunks to retrieve for each query"
    )
    similarity_threshold: Optional[float] = Field(
        0.3, ge=0.0, le=1.0, description="Minimum similarity score filter"
    )
    include_contexts: bool = Field(
        True, description="Whether to include contexts in the response payload"
    )
    truncate_context_chars: int = Field(
        350, ge=40, le=2000, description="Max chars for each returned context snippet"
    )
    evaluator: Optional[str] = Field(
        None,
        description="Optional custom evaluator type: 'llm_judge' for LLM-as-judge, None for default LlamaIndex evaluators",
    )


class LlamaRAGEvalRequest(BaseModel):
    persona_id: UUID = Field(..., description="Persona ID to evaluate against")
    user_id: UUID = Field(..., description="User ID for ownership validation")
    queries: List[LlamaRAGEvalQuery] = Field(
        ..., description="List of queries (and optional ground truths)"
    )
    params: LlamaRAGEvalParams = Field(
        default_factory=LlamaRAGEvalParams,
        description="Evaluation parameter overrides (defaults applied if omitted)",
    )


class LlamaRAGEvalResult(BaseModel):
    status: str
    persona_id: UUID
    total_queries: int
    metrics_overall: Dict[str, float]
    details: List[Dict[str, Any]]
    eval_time_seconds: float
    message: str


class LlamaRAGRetrievalEvalRequest(BaseModel):
    persona_id: UUID = Field(..., description="Persona ID to evaluate against")
    user_id: UUID = Field(..., description="User ID for ownership validation")
    queries: List[LlamaRAGEvalQuery] = Field(
        ..., description="List of queries (ground_truth optional)"
    )
    params: LlamaRAGEvalParams = Field(
        default_factory=LlamaRAGEvalParams,
        description="Retrieval parameter overrides (defaults applied if omitted)",
    )


class LlamaRAGRetrievalEvalResult(BaseModel):
    status: str
    persona_id: UUID
    total_queries: int
    metrics_overall: Dict[str, float]
    details: List[Dict[str, Any]]
    eval_time_seconds: float
    message: str
