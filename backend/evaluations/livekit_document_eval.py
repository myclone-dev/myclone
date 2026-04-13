#!/usr/bin/env python3
"""
LiveKit Document Attachment Evaluation System

This module evaluates document-based Q&A with LiveKit text-only agents by:
1. Connecting to an agent via the connection-details API
2. Sending a document URL (S3) for processing
3. Asking questions about the document content
4. Evaluating responses against ground truth

Usage:
    python -m evaluations.livekit_document_eval --username rishikesh --persona default --test-file document_test_cases.json

Or programmatically:
    from evaluations.livekit_document_eval import DocumentEvaluator
    evaluator = DocumentEvaluator("http://localhost:8000")
    results = await evaluator.run_evaluation("rishikesh", "default", test_cases)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from openai import AsyncOpenAI

from livekit import rtc

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================


class EvaluationError(Exception):
    """Raised when evaluation fails due to system errors (not poor agent performance)"""

    def __init__(self, message: str, metric: str, original_error: Optional[Exception] = None):
        self.message = message
        self.metric = metric
        self.original_error = original_error
        super().__init__(f"[{metric}] {message}")


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class DocumentQuestion:
    """Single question about a document"""

    query: str
    ground_truth: str
    expected_keywords: List[str] = field(default_factory=list)
    requires_specific_section: str = ""  # Which section of doc should be referenced


@dataclass
class DocumentTestCase:
    """Document-based test case with questions"""

    id: str
    document_url: str  # S3 URL or presigned URL
    document_name: str  # Filename for display
    document_type: str = "pdf"  # pdf, txt, docx, etc.
    description: str = ""
    questions: List[DocumentQuestion] = field(default_factory=list)
    category: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QuestionResult:
    """Result of evaluating a single question about a document"""

    question_number: int
    query: str
    ground_truth: str
    agent_response: str
    citations: List[Dict[str, Any]]

    # Scores
    semantic_similarity: Optional[float] = None
    factual_accuracy: Optional[float] = None
    keyword_coverage: Optional[float] = None
    document_grounding: Optional[float] = None  # How well response is grounded in document

    response_time_ms: float = 0.0


@dataclass
class DocumentResult:
    """Result of evaluating a document test case"""

    test_case_id: str
    document_url: str
    document_name: str
    category: str
    description: str
    question_results: List[QuestionResult]

    # Document-level scores
    document_processed: bool = True
    document_processing_time_ms: float = 0.0
    avg_semantic_similarity: float = 0.0
    avg_factual_accuracy: float = 0.0
    avg_keyword_coverage: float = 0.0
    avg_document_grounding: float = 0.0
    overall_score: float = 0.0

    # Timing
    total_response_time_ms: float = 0.0

    # Pass/fail
    passed: bool = False
    failure_reason: str = ""

    # Evaluation errors
    evaluation_error: bool = False
    evaluation_error_details: str = ""


@dataclass
class DocumentEvalReport:
    """Complete document evaluation report"""

    username: str
    persona: str
    timestamp: str
    total_documents: int
    passed_count: int
    failed_count: int

    # Aggregate scores
    avg_semantic_similarity: float = 0.0
    avg_factual_accuracy: float = 0.0
    avg_keyword_coverage: float = 0.0
    avg_document_grounding: float = 0.0
    avg_overall_score: float = 0.0
    avg_response_time_ms: float = 0.0
    avg_document_processing_time_ms: float = 0.0

    # Individual results
    results: List[DocumentResult] = field(default_factory=list)

    # Category breakdown
    category_scores: Dict[str, float] = field(default_factory=dict)

    # Document type breakdown
    document_type_scores: Dict[str, float] = field(default_factory=dict)

    # Evaluation errors count
    evaluation_errors_count: int = 0

    @property
    def has_evaluation_errors(self) -> bool:
        """Check if any results had evaluation system errors"""
        return any(r.evaluation_error for r in self.results)


# ============================================================================
# LiveKit Client with Document Support
# ============================================================================


class LiveKitDocumentClient:
    """Client for connecting to LiveKit text-only agent with document support"""

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.room: Optional[rtc.Room] = None
        self.connected = False
        self.responses: List[Dict[str, Any]] = []
        self.citations: List[Dict[str, Any]] = []
        self.document_status: List[Dict[str, Any]] = []
        self._response_event = asyncio.Event()
        self._document_event = asyncio.Event()

    async def connect(self, username: str, persona: str = "default") -> bool:
        """Connect to LiveKit room for given persona"""
        try:
            # Get connection details
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_url}/api/v1/livekit/connection-details",
                    json={
                        "expert_username": username,
                        "persona_name": persona,
                        "room_config": {"text_only_mode": True},
                    },
                )

                if response.status_code != 200:
                    logger.error(
                        f"Failed to get connection: {response.status_code} - {response.text}"
                    )
                    return False

                details = response.json()

            # Connect to room
            self.room = rtc.Room()

            @self.room.on("connected")
            def on_connected():
                self.connected = True
                logger.info(f"Connected to room: {self.room.name}")

            @self.room.on("disconnected")
            def on_disconnected():
                self.connected = False
                logger.info("Disconnected from room")

            @self.room.on("data_received")
            def on_data(data: rtc.DataPacket):
                asyncio.create_task(self._handle_data(data))

            await self.room.connect(details["serverUrl"], details["participantToken"])

            # Wait for agent to join
            await asyncio.sleep(3)
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def _handle_data(self, data: rtc.DataPacket):
        """Handle incoming data from agent"""
        try:
            payload = json.loads(data.data.decode("utf-8"))
            msg_type = payload.get("type", "unknown")
            topic = data.topic

            if topic == "chat" or msg_type == "chat_response":
                self.responses.append(payload)
                self._response_event.set()

            elif topic == "citations" or msg_type == "citations":
                self.citations.append(payload)

            elif topic == "document_status" or msg_type == "document_status":
                self.document_status.append(payload)
                self._document_event.set()
                logger.info(f"Document status: {payload.get('status', 'unknown')}")

        except Exception as e:
            logger.error(f"Error handling data: {e}")

    async def send_document(
        self, url: str, filename: Optional[str] = None, timeout: float = 120.0
    ) -> bool:
        """Send document URL for processing and wait for acknowledgment"""
        if not self.room or not self.connected:
            return False

        # Clear previous state
        self._document_event.clear()
        self._response_event.clear()

        # Prepare document upload payload
        payload = {
            "type": "document_upload",
            "url": url,
        }
        if filename:
            payload["filename"] = filename

        # Send document via data channel
        await self.room.local_participant.publish_data(
            payload=json.dumps(payload).encode("utf-8"),
            topic="document",
            reliable=True,
        )

        logger.info(f"Sent document: {filename or url[:50]}...")

        # Wait for document processing confirmation
        # The agent might respond via document_status topic or chat
        try:
            # Wait for either document status or chat response
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(self._document_event.wait()),
                    asyncio.create_task(self._response_event.wait()),
                ],
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()

            if done:
                return True

        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for document processing after {timeout}s")

        return False

    async def send_message(self, message: str, timeout: float = 60.0) -> Optional[Dict[str, Any]]:
        """Send message and wait for response"""
        if not self.room or not self.connected:
            return None

        # Clear previous state
        self._response_event.clear()
        initial_count = len(self.responses)

        # Send message
        payload = {"message": message, "timestamp": time.time()}
        await self.room.local_participant.publish_data(
            payload=json.dumps(payload).encode("utf-8"), topic="chat", reliable=True
        )

        # Wait for response
        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=timeout)
            if len(self.responses) > initial_count:
                return self.responses[-1]
        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for response to: {message[:50]}...")

        return None

    def get_latest_citations(self) -> List[Dict[str, Any]]:
        """Get citations from last response"""
        return self.citations[-1].get("sources", []) if self.citations else []

    async def disconnect(self):
        """Disconnect from room"""
        if self.room:
            await self.room.disconnect()
            self.connected = False


# ============================================================================
# Document Response Evaluator
# ============================================================================


class DocumentResponseEvaluator:
    """Evaluates document-based responses using LLM"""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model

        # Validate OPENAI_API_KEY exists
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable is required for LLM-based evaluation. "
                "Please set it in your .env file or environment."
            )
        if not api_key.startswith("sk-"):
            raise ValueError(
                "OPENAI_API_KEY appears to be invalid (should start with 'sk-'). "
                "Please check your API key configuration."
            )

        self.client = AsyncOpenAI(api_key=api_key)
        logger.info(f"DocumentResponseEvaluator initialized with model: {model}")

    async def evaluate_response(
        self,
        document_name: str,
        query: str,
        ground_truth: str,
        agent_response: str,
        expected_keywords: List[str],
        citations: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Evaluate agent response about a document"""

        # 1. Semantic similarity
        semantic_score = await self._evaluate_semantic_similarity(
            query, ground_truth, agent_response
        )

        # 2. Factual accuracy
        factual_score = await self._evaluate_factual_accuracy(ground_truth, agent_response)

        # 3. Keyword coverage
        keyword_score = self._evaluate_keyword_coverage(agent_response, expected_keywords)

        # 4. Document grounding - how well the response is grounded in document content
        grounding_score = await self._evaluate_document_grounding(
            document_name, query, agent_response, citations
        )

        return {
            "semantic_similarity": semantic_score,
            "factual_accuracy": factual_score,
            "keyword_coverage": keyword_score,
            "document_grounding": grounding_score,
        }

    async def _evaluate_semantic_similarity(
        self, question: str, ground_truth: str, response: str
    ) -> float:
        """Use LLM to evaluate semantic similarity"""
        prompt = f"""Evaluate how semantically similar the Agent Response is to the Ground Truth in answering the Question.

Question: {question}

Ground Truth: {ground_truth}

Agent Response: {response}

Score the semantic similarity from 0.0 to 1.0 where:
- 1.0 = Perfectly captures the same meaning and information
- 0.8 = Captures most key information with minor differences
- 0.6 = Captures some key information but misses important points
- 0.4 = Partially related but significant gaps
- 0.2 = Barely related
- 0.0 = Completely unrelated or contradictory

Respond with ONLY a number between 0.0 and 1.0."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10,
            )
            score_text = response.choices[0].message.content.strip()
            try:
                score = float(score_text)
            except ValueError:
                raise EvaluationError(
                    f"LLM returned non-numeric score: '{score_text}'",
                    metric="semantic_similarity",
                )
            return min(max(score, 0.0), 1.0)
        except EvaluationError:
            raise
        except Exception as e:
            logger.error(f"Semantic evaluation error: {e}")
            raise EvaluationError(
                f"OpenAI API call failed: {str(e)}",
                metric="semantic_similarity",
                original_error=e,
            )

    async def _evaluate_factual_accuracy(self, ground_truth: str, response: str) -> float:
        """Use LLM to evaluate factual accuracy"""
        prompt = f"""Evaluate the factual accuracy of the Agent Response compared to the Ground Truth.

Ground Truth (correct information): {ground_truth}

Agent Response: {response}

Score the factual accuracy from 0.0 to 1.0 where:
- 1.0 = All facts are accurate and consistent with ground truth
- 0.8 = Mostly accurate with minor factual differences
- 0.6 = Some accurate facts but includes incorrect information
- 0.4 = Mix of accurate and inaccurate information
- 0.2 = Mostly inaccurate
- 0.0 = Completely inaccurate or contradicts ground truth

Respond with ONLY a number between 0.0 and 1.0."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10,
            )
            score_text = response.choices[0].message.content.strip()
            try:
                score = float(score_text)
            except ValueError:
                raise EvaluationError(
                    f"LLM returned non-numeric score: '{score_text}'",
                    metric="factual_accuracy",
                )
            return min(max(score, 0.0), 1.0)
        except EvaluationError:
            raise
        except Exception as e:
            logger.error(f"Factual evaluation error: {e}")
            raise EvaluationError(
                f"OpenAI API call failed: {str(e)}",
                metric="factual_accuracy",
                original_error=e,
            )

    def _evaluate_keyword_coverage(self, response: str, expected_keywords: List[str]) -> float:
        """Check what percentage of expected keywords are present"""
        if not expected_keywords:
            return 1.0  # No keywords to check

        response_lower = response.lower()
        found = sum(1 for kw in expected_keywords if kw.lower() in response_lower)
        return found / len(expected_keywords)

    async def _evaluate_document_grounding(
        self,
        document_name: str,
        query: str,
        agent_response: str,
        citations: List[Dict[str, Any]],
    ) -> float:
        """Evaluate if the response is properly grounded in the document"""

        # Format citations if available
        citations_info = ""
        if citations:
            citation_texts = [
                f"- {c.get('title', 'N/A')}: {c.get('content', c.get('text', 'N/A'))[:150]}"
                for c in citations[:5]
            ]
            citations_info = "\n\nCitations provided by agent:\n" + "\n".join(citation_texts)

        prompt = f"""Evaluate how well the agent's response is grounded in the uploaded document.

Document: {document_name}
Question: {query}
Agent Response: {agent_response}
{citations_info}

Score the document grounding from 0.0 to 1.0 where:
- 1.0 = Response clearly references and is based on document content, cites specific information
- 0.8 = Response is well-grounded with minor generic additions
- 0.6 = Response partially uses document but adds unsupported information
- 0.4 = Response loosely related to document, mostly generic
- 0.2 = Response barely references document content
- 0.0 = Response appears completely unrelated to document or hallucinates

Consider:
1. Does the response reference specific information that would be in the document?
2. Are citations relevant and from the uploaded document?
3. Does it avoid making claims not supported by the document?

Respond with ONLY a number between 0.0 and 1.0."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10,
            )
            score_text = response.choices[0].message.content.strip()
            try:
                score = float(score_text)
            except ValueError:
                raise EvaluationError(
                    f"LLM returned non-numeric score: '{score_text}'",
                    metric="document_grounding",
                )
            return min(max(score, 0.0), 1.0)
        except EvaluationError:
            raise
        except Exception as e:
            logger.error(f"Document grounding evaluation error: {e}")
            raise EvaluationError(
                f"OpenAI API call failed: {str(e)}",
                metric="document_grounding",
                original_error=e,
            )


# ============================================================================
# Main Evaluator
# ============================================================================


class DocumentEvaluator:
    """Main document evaluation orchestrator"""

    def __init__(self, api_url: str = "http://localhost:8000", passing_threshold: float = 0.7):
        self.api_url = api_url
        self.passing_threshold = passing_threshold
        self.client: Optional[LiveKitDocumentClient] = None
        self.evaluator = DocumentResponseEvaluator()

    async def run_evaluation(
        self,
        username: str,
        persona: str,
        test_cases: List[DocumentTestCase],
        delay_between_questions: float = 2.0,
        delay_between_documents: float = 5.0,
        document_processing_timeout: float = 120.0,
    ) -> DocumentEvalReport:
        """Run full document evaluation and return report"""

        logger.info(
            f"Starting document evaluation for {username}/{persona} "
            f"with {len(test_cases)} documents"
        )

        results: List[DocumentResult] = []

        for doc_idx, test_case in enumerate(test_cases, 1):
            logger.info(
                f"[{doc_idx}/{len(test_cases)}] "
                f"Document: {test_case.document_name} ({len(test_case.questions)} questions)"
            )

            # Connect fresh for each document to ensure clean state
            self.client = LiveKitDocumentClient(self.api_url)
            if not await self.client.connect(username, persona):
                results.append(
                    DocumentResult(
                        test_case_id=test_case.id,
                        document_url=test_case.document_url,
                        document_name=test_case.document_name,
                        category=test_case.category,
                        description=test_case.description,
                        question_results=[],
                        document_processed=False,
                        passed=False,
                        failure_reason="Failed to connect to agent",
                    )
                )
                continue

            try:
                result = await self._evaluate_document(
                    test_case,
                    delay_between_questions,
                    document_processing_timeout,
                )
                results.append(result)
            except EvaluationError as eval_err:
                logger.error(f"Evaluation error for {test_case.id}: {eval_err}")
                results.append(
                    DocumentResult(
                        test_case_id=test_case.id,
                        document_url=test_case.document_url,
                        document_name=test_case.document_name,
                        category=test_case.category,
                        description=test_case.description,
                        question_results=[],
                        passed=False,
                        evaluation_error=True,
                        evaluation_error_details=str(eval_err),
                    )
                )
            finally:
                await self.client.disconnect()

            # Delay between documents
            if doc_idx < len(test_cases):
                await asyncio.sleep(delay_between_documents)

        # Generate report
        return self._generate_report(username, persona, results)

    async def _evaluate_document(
        self,
        test_case: DocumentTestCase,
        delay_between_questions: float,
        document_processing_timeout: float,
    ) -> DocumentResult:
        """Evaluate a single document test case"""

        question_results: List[QuestionResult] = []
        total_time = 0.0

        # Step 1: Send document for processing
        logger.info(f"   Uploading document: {test_case.document_name}...")
        doc_start_time = time.time()

        doc_processed = await self.client.send_document(
            url=test_case.document_url,
            filename=test_case.document_name,
            timeout=document_processing_timeout,
        )

        doc_processing_time = (time.time() - doc_start_time) * 1000

        if not doc_processed:
            logger.warning("   Document processing may have timed out or failed")
            # Continue anyway - the document might still be processed

        # Wait a bit for document to be fully indexed
        await asyncio.sleep(2.0)

        # Step 2: Ask questions about the document
        for q_idx, question in enumerate(test_case.questions, 1):
            logger.info(f"   Question {q_idx}/{len(test_case.questions)}: {question.query[:50]}...")

            # Clear previous citations
            self.client.citations.clear()

            # Send question and measure time
            start_time = time.time()
            response_data = await self.client.send_message(question.query)
            response_time_ms = (time.time() - start_time) * 1000
            total_time += response_time_ms

            if not response_data:
                # No response - record failure
                question_results.append(
                    QuestionResult(
                        question_number=q_idx,
                        query=question.query,
                        ground_truth=question.ground_truth,
                        agent_response="[NO RESPONSE]",
                        citations=[],
                        response_time_ms=response_time_ms,
                    )
                )
                continue

            agent_response = response_data.get("response", "")
            citations = self.client.get_latest_citations()

            # Evaluate response
            scores = await self.evaluator.evaluate_response(
                document_name=test_case.document_name,
                query=question.query,
                ground_truth=question.ground_truth,
                agent_response=agent_response,
                expected_keywords=question.expected_keywords,
                citations=citations,
            )

            question_result = QuestionResult(
                question_number=q_idx,
                query=question.query,
                ground_truth=question.ground_truth,
                agent_response=agent_response,
                citations=citations,
                semantic_similarity=scores["semantic_similarity"],
                factual_accuracy=scores["factual_accuracy"],
                keyword_coverage=scores["keyword_coverage"],
                document_grounding=scores["document_grounding"],
                response_time_ms=response_time_ms,
            )
            question_results.append(question_result)

            logger.info(
                f"      Scores: sem={scores['semantic_similarity']:.2f} "
                f"fact={scores['factual_accuracy']:.2f} "
                f"ground={scores['document_grounding']:.2f}"
            )

            # Delay between questions
            if q_idx < len(test_case.questions):
                await asyncio.sleep(delay_between_questions)

        # Calculate document-level averages
        valid_results = [q for q in question_results if q.agent_response != "[NO RESPONSE]"]

        def safe_avg(attr: str) -> float:
            values = [getattr(q, attr) for q in valid_results if getattr(q, attr) is not None]
            return sum(values) / len(values) if values else 0.0

        avg_semantic = safe_avg("semantic_similarity")
        avg_factual = safe_avg("factual_accuracy")
        avg_keyword = safe_avg("keyword_coverage")
        avg_grounding = safe_avg("document_grounding")

        # Overall score (weighted - emphasize document grounding)
        overall = (
            avg_semantic * 0.25
            + avg_factual * 0.25
            + avg_keyword * 0.10
            + avg_grounding * 0.40  # Document grounding is most important
        )

        passed = overall >= self.passing_threshold

        return DocumentResult(
            test_case_id=test_case.id,
            document_url=test_case.document_url,
            document_name=test_case.document_name,
            category=test_case.category,
            description=test_case.description,
            question_results=question_results,
            document_processed=doc_processed,
            document_processing_time_ms=doc_processing_time,
            avg_semantic_similarity=avg_semantic,
            avg_factual_accuracy=avg_factual,
            avg_keyword_coverage=avg_keyword,
            avg_document_grounding=avg_grounding,
            overall_score=overall,
            total_response_time_ms=total_time,
            passed=passed,
            failure_reason=(
                "" if passed else f"Score {overall:.2f} below threshold {self.passing_threshold}"
            ),
        )

    def _generate_report(
        self, username: str, persona: str, results: List[DocumentResult]
    ) -> DocumentEvalReport:
        """Generate evaluation report from results"""

        passed_count = sum(1 for r in results if r.passed)
        error_count = sum(1 for r in results if r.evaluation_error)

        # Filter out results with evaluation errors for averaging
        valid_results = [r for r in results if not r.evaluation_error]

        # Category breakdown
        category_results: Dict[str, List[float]] = {}
        for r in valid_results:
            if r.category not in category_results:
                category_results[r.category] = []
            category_results[r.category].append(r.overall_score)

        category_scores = {
            cat: sum(scores) / len(scores) if scores else 0.0
            for cat, scores in category_results.items()
        }

        # Document type breakdown (extract from document_name extension or document_type)
        doc_type_results: Dict[str, List[float]] = {}
        for r in valid_results:
            doc_type = (
                r.document_name.split(".")[-1].lower() if "." in r.document_name else "unknown"
            )
            if doc_type not in doc_type_results:
                doc_type_results[doc_type] = []
            doc_type_results[doc_type].append(r.overall_score)

        document_type_scores = {
            dt: sum(scores) / len(scores) if scores else 0.0
            for dt, scores in doc_type_results.items()
        }

        # Calculate averages
        def safe_avg(attr: str) -> float:
            values = [getattr(r, attr) for r in valid_results if getattr(r, attr) is not None]
            return sum(values) / len(values) if values else 0.0

        return DocumentEvalReport(
            username=username,
            persona=persona,
            timestamp=datetime.now().isoformat(),
            total_documents=len(results),
            passed_count=passed_count,
            failed_count=len(results) - passed_count,
            avg_semantic_similarity=safe_avg("avg_semantic_similarity"),
            avg_factual_accuracy=safe_avg("avg_factual_accuracy"),
            avg_keyword_coverage=safe_avg("avg_keyword_coverage"),
            avg_document_grounding=safe_avg("avg_document_grounding"),
            avg_overall_score=safe_avg("overall_score"),
            avg_response_time_ms=(
                sum(r.total_response_time_ms for r in results) / len(results) if results else 0.0
            ),
            avg_document_processing_time_ms=(
                sum(r.document_processing_time_ms for r in valid_results) / len(valid_results)
                if valid_results
                else 0.0
            ),
            results=results,
            category_scores=category_scores,
            document_type_scores=document_type_scores,
            evaluation_errors_count=error_count,
        )


# ============================================================================
# Report Generation
# ============================================================================


def print_report(report: DocumentEvalReport):
    """Print evaluation report to console"""

    print("\n" + "=" * 80)
    print("LIVEKIT DOCUMENT EVALUATION REPORT")
    print("=" * 80)
    print(f"Username:  {report.username}")
    print(f"Persona:   {report.persona}")
    print(f"Timestamp: {report.timestamp}")
    print("-" * 80)

    # Summary
    pass_rate = (
        (report.passed_count / report.total_documents * 100) if report.total_documents else 0
    )
    print("\n📊 SUMMARY")
    print(f"   Total Documents:         {report.total_documents}")
    print(f"   Passed:                  {report.passed_count} ({pass_rate:.1f}%)")
    print(f"   Failed:                  {report.failed_count}")
    print(f"   Avg Doc Processing Time: {report.avg_document_processing_time_ms:.0f}ms")
    print(f"   Avg Response Time:       {report.avg_response_time_ms:.0f}ms")

    # Evaluation system errors warning
    if report.evaluation_errors_count > 0:
        print(f"\n⚠️  EVALUATION SYSTEM ERRORS: {report.evaluation_errors_count}")
        print("   These documents could not be scored due to LLM API failures.")

    # Scores
    print("\n📈 AVERAGE SCORES (excluding evaluation errors)")
    print(f"   Semantic Similarity:  {report.avg_semantic_similarity:.2f}")
    print(f"   Factual Accuracy:     {report.avg_factual_accuracy:.2f}")
    print(f"   Keyword Coverage:     {report.avg_keyword_coverage:.2f}")
    print(f"   Document Grounding:   {report.avg_document_grounding:.2f}")
    print(f"   Overall Score:        {report.avg_overall_score:.2f}")

    # Category breakdown
    if report.category_scores:
        print("\n📁 CATEGORY SCORES")
        for cat, score in sorted(report.category_scores.items()):
            print(f"   {cat}: {score:.2f}")

    # Document type breakdown
    if report.document_type_scores:
        print("\n📄 DOCUMENT TYPE SCORES")
        for dt, score in sorted(report.document_type_scores.items()):
            print(f"   {dt}: {score:.2f}")

    # Detailed results
    print("\n📝 DETAILED RESULTS")
    print("-" * 80)

    for r in report.results:
        if r.evaluation_error:
            status = "⚠️  EVAL ERROR"
        elif r.passed:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"

        print(f"\n[{r.test_case_id}] {status}")
        print(f"   Document: {r.document_name}")
        print(f"   Category: {r.category}")
        if r.description:
            print(f"   Description: {r.description[:70]}...")

        if r.evaluation_error:
            print(f"   ⚠️  Evaluation Error: {r.evaluation_error_details}")
        else:
            doc_status = "✅" if r.document_processed else "⚠️ timeout"
            print(f"   Doc Processed: {doc_status} ({r.document_processing_time_ms:.0f}ms)")
            print(f"   Questions: {len(r.question_results)}")
            print(
                f"   Scores: sem={r.avg_semantic_similarity:.2f} "
                f"fact={r.avg_factual_accuracy:.2f} "
                f"kw={r.avg_keyword_coverage:.2f} "
                f"ground={r.avg_document_grounding:.2f}"
            )
            print(f"   Overall: {r.overall_score:.2f} | " f"Time: {r.total_response_time_ms:.0f}ms")

            # Show each question
            for q in r.question_results:
                print(f"\n   Q{q.question_number}: {q.query[:55]}...")
                print(f"      A: {q.agent_response[:55]}...")
                sem = f"{q.semantic_similarity:.2f}" if q.semantic_similarity is not None else "N/A"
                fact = f"{q.factual_accuracy:.2f}" if q.factual_accuracy is not None else "N/A"
                ground = (
                    f"{q.document_grounding:.2f}" if q.document_grounding is not None else "N/A"
                )
                print(f"      sem={sem} fact={fact} ground={ground}")

        if not r.passed and not r.evaluation_error:
            print(f"   Reason: {r.failure_reason}")

    print("\n" + "=" * 80)


def save_report(report: DocumentEvalReport, output_path: str):
    """Save report to JSON file"""

    report_dict = {
        "username": report.username,
        "persona": report.persona,
        "timestamp": report.timestamp,
        "summary": {
            "total_documents": report.total_documents,
            "passed_count": report.passed_count,
            "failed_count": report.failed_count,
            "evaluation_errors_count": report.evaluation_errors_count,
            "pass_rate": (
                report.passed_count / report.total_documents if report.total_documents else 0
            ),
            "has_evaluation_errors": report.has_evaluation_errors,
        },
        "average_scores": {
            "semantic_similarity": report.avg_semantic_similarity,
            "factual_accuracy": report.avg_factual_accuracy,
            "keyword_coverage": report.avg_keyword_coverage,
            "document_grounding": report.avg_document_grounding,
            "overall": report.avg_overall_score,
            "response_time_ms": report.avg_response_time_ms,
            "document_processing_time_ms": report.avg_document_processing_time_ms,
            "note": "Averages exclude results with evaluation system errors",
        },
        "category_scores": report.category_scores,
        "document_type_scores": report.document_type_scores,
        "results": [
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
                        "citations_count": len(q.citations),
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
    }

    with open(output_path, "w") as f:
        json.dump(report_dict, f, indent=2)

    logger.info(f"Report saved to: {output_path}")


# ============================================================================
# Test Case Loading
# ============================================================================


def load_test_cases(file_path: str) -> List[DocumentTestCase]:
    """Load document test cases from JSON file"""

    with open(file_path, "r") as f:
        data = json.load(f)

    test_cases = []
    for item in data.get("test_cases", data if isinstance(data, list) else []):
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


# ============================================================================
# CLI
# ============================================================================


async def main():
    parser = argparse.ArgumentParser(description="Evaluate LiveKit Document Agent")
    parser.add_argument("--username", "-u", required=True, help="Expert username")
    parser.add_argument("--persona", "-p", default="default", help="Persona name")
    parser.add_argument("--test-file", "-t", required=True, help="Path to document test cases JSON")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--output", "-o", help="Output JSON report path")
    parser.add_argument("--threshold", type=float, default=0.7, help="Passing threshold (0-1)")
    parser.add_argument(
        "--question-delay",
        type=float,
        default=2.0,
        help="Delay between questions (seconds)",
    )
    parser.add_argument(
        "--doc-delay",
        type=float,
        default=5.0,
        help="Delay between documents (seconds)",
    )
    parser.add_argument(
        "--doc-timeout",
        type=float,
        default=120.0,
        help="Document processing timeout (seconds)",
    )

    args = parser.parse_args()

    # Load test cases
    test_cases = load_test_cases(args.test_file)
    logger.info(f"Loaded {len(test_cases)} document test cases from {args.test_file}")

    # Run evaluation
    evaluator = DocumentEvaluator(api_url=args.api_url, passing_threshold=args.threshold)

    report = await evaluator.run_evaluation(
        username=args.username,
        persona=args.persona,
        test_cases=test_cases,
        delay_between_questions=args.question_delay,
        delay_between_documents=args.doc_delay,
        document_processing_timeout=args.doc_timeout,
    )

    # Print report
    print_report(report)

    # Save report if output specified
    if args.output:
        save_report(report, args.output)
    else:
        # Auto-save to results directory
        output_path = (
            f"evaluations/results/doc_eval_{args.username}_{args.persona}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        save_report(report, output_path)

    # Return exit code based on pass rate and errors
    pass_rate = report.passed_count / report.total_documents if report.total_documents else 0
    sys.exit(0 if pass_rate >= 0.8 and not report.has_evaluation_errors else 1)


if __name__ == "__main__":
    asyncio.run(main())
