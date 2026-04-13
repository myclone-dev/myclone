"""
LiveKit Agent Evaluation API Routes

Provides REST API endpoints for running evaluations on LiveKit text-only agents:
- Single Query Evaluation
- Conversation Evaluation
- Document Evaluation

Usage:
    POST /api/v1/evaluations/query - Run single query evaluation
    POST /api/v1/evaluations/conversation - Run conversation evaluation
    POST /api/v1/evaluations/document - Run document evaluation
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from evaluations.livekit_conversation_eval import (
    ConversationEvalReport,
    ConversationEvaluator,
    ConversationTestCase,
    ConversationTurn,
)
from evaluations.livekit_document_eval import (
    DocumentEvalReport,
    DocumentEvaluator,
    DocumentQuestion,
    DocumentTestCase,
)

# Import evaluation modules
from evaluations.livekit_text_agent_eval import (
    EvalReport,
    LiveKitAgentEvaluator,
    TestCase,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


# ============================================================================
# Request/Response Models
# ============================================================================


class EvalConfig(BaseModel):
    """Common evaluation configuration"""

    username: str = Field(..., description="Expert username")
    persona: str = Field(default="default", description="Persona name")
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Passing threshold")
    api_url: str = Field(default="http://localhost:8000", description="API base URL")


class QueryEvalRequest(BaseModel):
    """Request for single query evaluation"""

    config: EvalConfig
    test_cases: List[Dict[str, Any]] = Field(
        ..., description="List of test cases with question, ground_truth, etc."
    )
    delay_between_questions: float = Field(default=2.0, ge=0.0)


class ConversationEvalRequest(BaseModel):
    """Request for conversation evaluation"""

    config: EvalConfig
    test_cases: List[Dict[str, Any]] = Field(
        ..., description="List of conversation test cases with turns"
    )
    delay_between_turns: float = Field(default=2.0, ge=0.0)
    delay_between_conversations: float = Field(default=5.0, ge=0.0)


class DocumentEvalRequest(BaseModel):
    """Request for document evaluation"""

    config: EvalConfig
    test_cases: List[Dict[str, Any]] = Field(
        ..., description="List of document test cases with document_url and questions"
    )
    delay_between_questions: float = Field(default=2.0, ge=0.0)
    delay_between_documents: float = Field(default=5.0, ge=0.0)
    document_processing_timeout: float = Field(default=120.0, ge=10.0)


class EvalSummary(BaseModel):
    """Summary of evaluation results"""

    total: int
    passed: int
    failed: int
    pass_rate: float
    evaluation_errors: int


class QueryEvalResponse(BaseModel):
    """Response for single query evaluation"""

    status: str = "completed"
    summary: EvalSummary
    average_scores: Dict[str, float]
    category_scores: Dict[str, float]
    results: List[Dict[str, Any]]
    timestamp: str


class ConversationEvalResponse(BaseModel):
    """Response for conversation evaluation"""

    status: str = "completed"
    summary: EvalSummary
    average_scores: Dict[str, float]
    category_scores: Dict[str, float]
    results: List[Dict[str, Any]]
    timestamp: str


class DocumentEvalResponse(BaseModel):
    """Response for document evaluation"""

    status: str = "completed"
    summary: EvalSummary
    average_scores: Dict[str, float]
    category_scores: Dict[str, float]
    document_type_scores: Dict[str, float]
    results: List[Dict[str, Any]]
    timestamp: str


# ============================================================================
# Helper Functions
# ============================================================================


def parse_query_test_cases(data: List[Dict[str, Any]]) -> List[TestCase]:
    """Parse query test cases from JSON data"""
    test_cases = []
    for item in data:
        test_cases.append(
            TestCase(
                id=item.get("id", f"test-{len(test_cases)+1}"),
                question=item["question"],
                ground_truth=item["ground_truth"],
                expected_keywords=item.get("expected_keywords", []),
                category=item.get("category", "general"),
                metadata=item.get("metadata", {}),
            )
        )
    return test_cases


def parse_conversation_test_cases(data: List[Dict[str, Any]]) -> List[ConversationTestCase]:
    """Parse conversation test cases from JSON data"""
    test_cases = []
    for item in data:
        turns = []
        for turn_data in item.get("turns", []):
            turns.append(
                ConversationTurn(
                    query=turn_data["query"],
                    ground_truth=turn_data["ground_truth"],
                    expected_keywords=turn_data.get("expected_keywords", []),
                    context_check=turn_data.get("context_check", ""),
                )
            )

        test_cases.append(
            ConversationTestCase(
                id=item.get("id", f"conv-{len(test_cases)+1}"),
                turns=turns,
                category=item.get("category", "general"),
                description=item.get("description", ""),
                metadata=item.get("metadata", {}),
            )
        )
    return test_cases


def parse_document_test_cases(data: List[Dict[str, Any]]) -> List[DocumentTestCase]:
    """Parse document test cases from JSON data"""
    test_cases = []
    for item in data:
        questions = []
        for q_data in item.get("questions", []):
            questions.append(
                DocumentQuestion(
                    query=q_data["query"],
                    ground_truth=q_data["ground_truth"],
                    expected_keywords=q_data.get("expected_keywords", []),
                    requires_specific_section=q_data.get("requires_specific_section", ""),
                )
            )

        test_cases.append(
            DocumentTestCase(
                id=item.get("id", f"doc-{len(test_cases)+1}"),
                document_url=item["document_url"],
                document_name=item.get("document_name", "document"),
                document_type=item.get("document_type", "pdf"),
                description=item.get("description", ""),
                questions=questions,
                category=item.get("category", "general"),
                metadata=item.get("metadata", {}),
            )
        )
    return test_cases


def format_query_report(report: EvalReport) -> QueryEvalResponse:
    """Format query evaluation report for API response"""
    return QueryEvalResponse(
        status="completed",
        summary=EvalSummary(
            total=report.total_test_cases,
            passed=report.passed_count,
            failed=report.failed_count,
            pass_rate=(
                report.passed_count / report.total_test_cases if report.total_test_cases else 0
            ),
            evaluation_errors=report.evaluation_errors_count,
        ),
        average_scores={
            "semantic_similarity": report.avg_semantic_similarity,
            "factual_accuracy": report.avg_factual_accuracy,
            "keyword_coverage": report.avg_keyword_coverage,
            "retrieval_relevance": report.avg_retrieval_relevance,
            "overall": report.avg_overall_score,
            "response_time_ms": report.avg_response_time_ms,
        },
        category_scores=report.category_scores,
        results=[
            {
                "test_case_id": r.test_case_id,
                "question": r.question,
                "ground_truth": r.ground_truth,
                "agent_response": r.agent_response,
                "scores": {
                    "semantic_similarity": r.semantic_similarity,
                    "factual_accuracy": r.factual_accuracy,
                    "keyword_coverage": r.keyword_coverage,
                    "retrieval_relevance": r.retrieval_relevance,
                    "overall": r.overall_score,
                },
                "response_time_ms": r.response_time_ms,
                "passed": r.passed,
                "failure_reason": r.failure_reason,
                "evaluation_error": r.evaluation_error,
                "evaluation_error_details": (
                    r.evaluation_error_details if r.evaluation_error else None
                ),
            }
            for r in report.results
        ],
        timestamp=report.timestamp,
    )


def format_conversation_report(report: ConversationEvalReport) -> ConversationEvalResponse:
    """Format conversation evaluation report for API response"""
    return ConversationEvalResponse(
        status="completed",
        summary=EvalSummary(
            total=report.total_conversations,
            passed=report.passed_count,
            failed=report.failed_count,
            pass_rate=(
                report.passed_count / report.total_conversations
                if report.total_conversations
                else 0
            ),
            evaluation_errors=report.evaluation_errors_count,
        ),
        average_scores={
            "semantic_similarity": report.avg_semantic_similarity,
            "factual_accuracy": report.avg_factual_accuracy,
            "keyword_coverage": report.avg_keyword_coverage,
            "context_retention": report.avg_context_retention,
            "conversation_coherence": report.avg_conversation_coherence,
            "overall": report.avg_overall_score,
            "response_time_ms": report.avg_response_time_ms,
        },
        category_scores=report.category_scores,
        results=[
            {
                "test_case_id": r.test_case_id,
                "category": r.category,
                "description": r.description,
                "turns": [
                    {
                        "turn_number": t.turn_number,
                        "query": t.query,
                        "ground_truth": t.ground_truth,
                        "agent_response": t.agent_response,
                        "scores": {
                            "semantic_similarity": t.semantic_similarity,
                            "factual_accuracy": t.factual_accuracy,
                            "keyword_coverage": t.keyword_coverage,
                            "context_retention": t.context_retention,
                        },
                        "response_time_ms": t.response_time_ms,
                    }
                    for t in r.turn_results
                ],
                "conversation_scores": {
                    "avg_semantic_similarity": r.avg_semantic_similarity,
                    "avg_factual_accuracy": r.avg_factual_accuracy,
                    "avg_keyword_coverage": r.avg_keyword_coverage,
                    "avg_context_retention": r.avg_context_retention,
                    "conversation_coherence": r.conversation_coherence,
                    "overall": r.overall_score,
                },
                "total_response_time_ms": r.total_response_time_ms,
                "passed": r.passed,
                "failure_reason": r.failure_reason,
                "evaluation_error": r.evaluation_error,
                "evaluation_error_details": (
                    r.evaluation_error_details if r.evaluation_error else None
                ),
            }
            for r in report.results
        ],
        timestamp=report.timestamp,
    )


def format_document_report(report: DocumentEvalReport) -> DocumentEvalResponse:
    """Format document evaluation report for API response"""
    return DocumentEvalResponse(
        status="completed",
        summary=EvalSummary(
            total=report.total_documents,
            passed=report.passed_count,
            failed=report.failed_count,
            pass_rate=report.passed_count / report.total_documents if report.total_documents else 0,
            evaluation_errors=report.evaluation_errors_count,
        ),
        average_scores={
            "semantic_similarity": report.avg_semantic_similarity,
            "factual_accuracy": report.avg_factual_accuracy,
            "keyword_coverage": report.avg_keyword_coverage,
            "document_grounding": report.avg_document_grounding,
            "overall": report.avg_overall_score,
            "response_time_ms": report.avg_response_time_ms,
            "document_processing_time_ms": report.avg_document_processing_time_ms,
        },
        category_scores=report.category_scores,
        document_type_scores=report.document_type_scores,
        results=[
            {
                "test_case_id": r.test_case_id,
                "document_url": r.document_url,
                "document_name": r.document_name,
                "category": r.category,
                "description": r.description,
                "document_processed": r.document_processed,
                "document_processing_time_ms": r.document_processing_time_ms,
                "questions": [
                    {
                        "question_number": q.question_number,
                        "query": q.query,
                        "ground_truth": q.ground_truth,
                        "agent_response": q.agent_response,
                        "scores": {
                            "semantic_similarity": q.semantic_similarity,
                            "factual_accuracy": q.factual_accuracy,
                            "keyword_coverage": q.keyword_coverage,
                            "document_grounding": q.document_grounding,
                        },
                        "response_time_ms": q.response_time_ms,
                    }
                    for q in r.question_results
                ],
                "document_scores": {
                    "avg_semantic_similarity": r.avg_semantic_similarity,
                    "avg_factual_accuracy": r.avg_factual_accuracy,
                    "avg_keyword_coverage": r.avg_keyword_coverage,
                    "avg_document_grounding": r.avg_document_grounding,
                    "overall": r.overall_score,
                },
                "total_response_time_ms": r.total_response_time_ms,
                "passed": r.passed,
                "failure_reason": r.failure_reason,
                "evaluation_error": r.evaluation_error,
                "evaluation_error_details": (
                    r.evaluation_error_details if r.evaluation_error else None
                ),
            }
            for r in report.results
        ],
        timestamp=report.timestamp,
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/query", response_model=QueryEvalResponse)
async def run_query_evaluation(request: QueryEvalRequest):
    """
    Run single query evaluation on a LiveKit text-only agent.

    Sends individual questions and evaluates responses against ground truth.

    **Request Body:**
    - `config.username`: Expert username (required)
    - `config.persona`: Persona name (default: "default")
    - `config.threshold`: Passing score threshold (default: 0.7)
    - `test_cases`: List of test cases with `question`, `ground_truth`, `expected_keywords`

    **Returns:**
    - Summary with pass/fail counts
    - Average scores across all metrics
    - Detailed results for each test case
    """
    try:
        logger.info(
            f"Starting query evaluation for {request.config.username}/{request.config.persona} "
            f"with {len(request.test_cases)} test cases"
        )

        # Parse test cases
        test_cases = parse_query_test_cases(request.test_cases)

        # Create evaluator and run
        evaluator = LiveKitAgentEvaluator(
            api_url=request.config.api_url,
            passing_threshold=request.config.threshold,
        )

        report = await evaluator.run_evaluation(
            username=request.config.username,
            persona=request.config.persona,
            test_cases=test_cases,
            delay_between_questions=request.delay_between_questions,
        )

        logger.info(
            f"Query evaluation completed: {report.passed_count}/{report.total_test_cases} passed"
        )

        return format_query_report(report)

    except ValueError as e:
        logger.error(f"Validation error in query evaluation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Query evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.post("/query/upload")
async def run_query_evaluation_with_file(
    username: str = Form(...),
    persona: str = Form(default="default"),
    threshold: float = Form(default=0.7),
    delay: float = Form(default=2.0),
    api_url: str = Form(default="http://localhost:8000"),
    test_file: UploadFile = File(..., description="JSON file with test cases"),
):
    """
    Run single query evaluation with uploaded JSON test file.

    **Form Fields:**
    - `username`: Expert username (required)
    - `persona`: Persona name (default: "default")
    - `threshold`: Passing threshold (default: 0.7)
    - `test_file`: JSON file containing test cases

    **JSON File Format:**
    ```json
    {
      "test_cases": [
        {
          "id": "test-1",
          "question": "What is...",
          "ground_truth": "The answer is...",
          "expected_keywords": ["keyword1", "keyword2"]
        }
      ]
    }
    ```
    """
    try:
        # Read and parse uploaded file
        content = await test_file.read()
        data = json.loads(content.decode("utf-8"))

        # Extract test cases
        test_cases_data = data.get("test_cases", data if isinstance(data, list) else [])

        # Create request and delegate
        request = QueryEvalRequest(
            config=EvalConfig(
                username=username,
                persona=persona,
                threshold=threshold,
                api_url=api_url,
            ),
            test_cases=test_cases_data,
            delay_between_questions=delay,
        )

        return await run_query_evaluation(request)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {str(e)}")
    except Exception as e:
        logger.error(f"Query evaluation with file upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.post("/conversation", response_model=ConversationEvalResponse)
async def run_conversation_evaluation(request: ConversationEvalRequest):
    """
    Run conversation evaluation on a LiveKit text-only agent.

    Sends multi-turn conversations and evaluates context retention and coherence.

    **Request Body:**
    - `config.username`: Expert username (required)
    - `config.persona`: Persona name (default: "default")
    - `config.threshold`: Passing score threshold (default: 0.7)
    - `test_cases`: List of conversation test cases with `turns` array

    **Returns:**
    - Summary with pass/fail counts
    - Average scores including context_retention and conversation_coherence
    - Detailed results for each conversation and turn
    """
    try:
        logger.info(
            f"Starting conversation evaluation for {request.config.username}/{request.config.persona} "
            f"with {len(request.test_cases)} conversations"
        )

        # Parse test cases
        test_cases = parse_conversation_test_cases(request.test_cases)

        # Create evaluator and run
        evaluator = ConversationEvaluator(
            api_url=request.config.api_url,
            passing_threshold=request.config.threshold,
        )

        report = await evaluator.run_evaluation(
            username=request.config.username,
            persona=request.config.persona,
            test_cases=test_cases,
            delay_between_turns=request.delay_between_turns,
            delay_between_conversations=request.delay_between_conversations,
        )

        logger.info(
            f"Conversation evaluation completed: {report.passed_count}/{report.total_conversations} passed"
        )

        return format_conversation_report(report)

    except ValueError as e:
        logger.error(f"Validation error in conversation evaluation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Conversation evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.post("/conversation/upload")
async def run_conversation_evaluation_with_file(
    username: str = Form(...),
    persona: str = Form(default="default"),
    threshold: float = Form(default=0.7),
    turn_delay: float = Form(default=2.0),
    conv_delay: float = Form(default=5.0),
    api_url: str = Form(default="http://localhost:8000"),
    test_file: UploadFile = File(..., description="JSON file with conversation test cases"),
):
    """
    Run conversation evaluation with uploaded JSON test file.

    **Form Fields:**
    - `username`: Expert username (required)
    - `persona`: Persona name (default: "default")
    - `threshold`: Passing threshold (default: 0.7)
    - `turn_delay`: Delay between turns in seconds (default: 2.0)
    - `conv_delay`: Delay between conversations in seconds (default: 5.0)
    - `test_file`: JSON file containing conversation test cases

    **JSON File Format:**
    ```json
    {
      "test_cases": [
        {
          "id": "conv-1",
          "category": "context_retention",
          "turns": [
            {"query": "...", "ground_truth": "...", "context_check": "..."}
          ]
        }
      ]
    }
    ```
    """
    try:
        # Read and parse uploaded file
        content = await test_file.read()
        data = json.loads(content.decode("utf-8"))

        # Extract test cases
        test_cases_data = data.get("test_cases", data if isinstance(data, list) else [])

        # Create request and delegate
        request = ConversationEvalRequest(
            config=EvalConfig(
                username=username,
                persona=persona,
                threshold=threshold,
                api_url=api_url,
            ),
            test_cases=test_cases_data,
            delay_between_turns=turn_delay,
            delay_between_conversations=conv_delay,
        )

        return await run_conversation_evaluation(request)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {str(e)}")
    except Exception as e:
        logger.error(f"Conversation evaluation with file upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.post("/document", response_model=DocumentEvalResponse)
async def run_document_evaluation(request: DocumentEvalRequest):
    """
    Run document evaluation on a LiveKit text-only agent.

    Uploads documents and asks questions to evaluate document-grounded responses.

    **Request Body:**
    - `config.username`: Expert username (required)
    - `config.persona`: Persona name (default: "default")
    - `config.threshold`: Passing score threshold (default: 0.7)
    - `test_cases`: List of document test cases with `document_url` and `questions`

    **Returns:**
    - Summary with pass/fail counts
    - Average scores including document_grounding
    - Document type breakdown scores
    - Detailed results for each document and question
    """
    try:
        logger.info(
            f"Starting document evaluation for {request.config.username}/{request.config.persona} "
            f"with {len(request.test_cases)} documents"
        )

        # Parse test cases
        test_cases = parse_document_test_cases(request.test_cases)

        # Create evaluator and run
        evaluator = DocumentEvaluator(
            api_url=request.config.api_url,
            passing_threshold=request.config.threshold,
        )

        report = await evaluator.run_evaluation(
            username=request.config.username,
            persona=request.config.persona,
            test_cases=test_cases,
            delay_between_questions=request.delay_between_questions,
            delay_between_documents=request.delay_between_documents,
            document_processing_timeout=request.document_processing_timeout,
        )

        logger.info(
            f"Document evaluation completed: {report.passed_count}/{report.total_documents} passed"
        )

        return format_document_report(report)

    except ValueError as e:
        logger.error(f"Validation error in document evaluation: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Document evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.post("/document/upload")
async def run_document_evaluation_with_file(
    username: str = Form(...),
    persona: str = Form(default="default"),
    threshold: float = Form(default=0.7),
    question_delay: float = Form(default=2.0),
    doc_delay: float = Form(default=5.0),
    doc_timeout: float = Form(default=120.0),
    api_url: str = Form(default="http://localhost:8000"),
    test_file: UploadFile = File(..., description="JSON file with document test cases"),
):
    """
    Run document evaluation with uploaded JSON test file.

    **Form Fields:**
    - `username`: Expert username (required)
    - `persona`: Persona name (default: "default")
    - `threshold`: Passing threshold (default: 0.7)
    - `question_delay`: Delay between questions in seconds (default: 2.0)
    - `doc_delay`: Delay between documents in seconds (default: 5.0)
    - `doc_timeout`: Document processing timeout in seconds (default: 120.0)
    - `test_file`: JSON file containing document test cases

    **JSON File Format:**
    ```json
    {
      "test_cases": [
        {
          "id": "doc-1",
          "document_url": "https://s3.../document.pdf",
          "document_name": "report.pdf",
          "questions": [
            {"query": "...", "ground_truth": "...", "expected_keywords": [...]}
          ]
        }
      ]
    }
    ```
    """
    try:
        # Read and parse uploaded file
        content = await test_file.read()
        data = json.loads(content.decode("utf-8"))

        # Extract test cases
        test_cases_data = data.get("test_cases", data if isinstance(data, list) else [])

        # Create request and delegate
        request = DocumentEvalRequest(
            config=EvalConfig(
                username=username,
                persona=persona,
                threshold=threshold,
                api_url=api_url,
            ),
            test_cases=test_cases_data,
            delay_between_questions=question_delay,
            delay_between_documents=doc_delay,
            document_processing_timeout=doc_timeout,
        )

        return await run_document_evaluation(request)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {str(e)}")
    except Exception as e:
        logger.error(f"Document evaluation with file upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health")
async def evaluation_health_check():
    """Check if evaluation service is available"""
    return {
        "status": "healthy",
        "service": "livekit-agent-evaluations",
        "available_endpoints": [
            "/api/v1/evaluations/query",
            "/api/v1/evaluations/query/upload",
            "/api/v1/evaluations/conversation",
            "/api/v1/evaluations/conversation/upload",
            "/api/v1/evaluations/document",
            "/api/v1/evaluations/document/upload",
        ],
        "timestamp": datetime.now().isoformat(),
    }
