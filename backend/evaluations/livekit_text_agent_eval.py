#!/usr/bin/env python3
"""
LiveKit Text Agent Evaluation System

This module provides automated evaluation of LiveKit text-only agents by:
1. Connecting to an agent via the connection-details API
2. Sending test questions and capturing responses
3. Evaluating response quality against ground truth
4. Generating detailed reports

Usage:
    python -m evaluations.livekit_text_agent_eval --username rishikesh --persona default --test-file test_cases.json

Or programmatically:
    from evaluations.livekit_text_agent_eval import LiveKitAgentEvaluator
    evaluator = LiveKitAgentEvaluator("http://localhost:8000")
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
class TestCase:
    """Single test case for evaluation"""

    id: str
    question: str
    ground_truth: str
    expected_keywords: List[str] = field(default_factory=list)
    category: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalResult:
    """Result of evaluating a single test case"""

    test_case_id: str
    question: str
    ground_truth: str
    agent_response: str
    citations: List[Dict[str, Any]]

    # Scores (0.0 to 1.0, None if evaluation failed)
    semantic_similarity: Optional[float] = None
    factual_accuracy: Optional[float] = None
    keyword_coverage: Optional[float] = None
    retrieval_relevance: Optional[float] = None

    # Computed overall score
    overall_score: Optional[float] = None

    # Timing
    response_time_ms: float = 0.0

    # Pass/fail
    passed: bool = False
    failure_reason: str = ""

    # Evaluation system errors (distinct from poor agent performance)
    evaluation_error: bool = False
    evaluation_error_details: str = ""


@dataclass
class EvalReport:
    """Complete evaluation report"""

    username: str
    persona: str
    timestamp: str
    total_test_cases: int
    passed_count: int
    failed_count: int

    # Aggregate scores
    avg_semantic_similarity: float = 0.0
    avg_factual_accuracy: float = 0.0
    avg_keyword_coverage: float = 0.0
    avg_retrieval_relevance: float = 0.0
    avg_overall_score: float = 0.0
    avg_response_time_ms: float = 0.0

    # Individual results
    results: List[EvalResult] = field(default_factory=list)

    # Categories breakdown
    category_scores: Dict[str, float] = field(default_factory=dict)

    # Evaluation system errors count
    evaluation_errors_count: int = 0

    @property
    def has_evaluation_errors(self) -> bool:
        """Check if any results had evaluation system errors"""
        return any(r.evaluation_error for r in self.results)


# ============================================================================
# LiveKit Client
# ============================================================================


class LiveKitTextClient:
    """Client for connecting to LiveKit text-only agent"""

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.room: Optional[rtc.Room] = None
        self.connected = False
        self.responses: List[Dict[str, Any]] = []
        self.citations: List[Dict[str, Any]] = []
        self._response_event = asyncio.Event()

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

            if msg_type == "chat_response":
                self.responses.append(payload)
                self._response_event.set()

            elif msg_type == "citations":
                self.citations.append(payload)

        except Exception as e:
            logger.error(f"Error handling data: {e}")

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
# Evaluator
# ============================================================================


class ResponseEvaluator:
    """Evaluates agent responses against ground truth using LLM"""

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
        logger.info(f"ResponseEvaluator initialized with model: {model}")

    async def evaluate_response(
        self,
        question: str,
        ground_truth: str,
        agent_response: str,
        expected_keywords: List[str],
        citations: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Evaluate agent response and return scores"""

        # 1. Semantic similarity via LLM
        semantic_score = await self._evaluate_semantic_similarity(
            question, ground_truth, agent_response
        )

        # 2. Factual accuracy via LLM
        factual_score = await self._evaluate_factual_accuracy(ground_truth, agent_response)

        # 3. Keyword coverage (direct check)
        keyword_score = self._evaluate_keyword_coverage(agent_response, expected_keywords)

        # 4. Retrieval relevance
        retrieval_score = await self._evaluate_retrieval_relevance(question, citations)

        return {
            "semantic_similarity": semantic_score,
            "factual_accuracy": factual_score,
            "keyword_coverage": keyword_score,
            "retrieval_relevance": retrieval_score,
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

    async def _evaluate_retrieval_relevance(
        self, question: str, citations: List[Dict[str, Any]]
    ) -> float:
        """Evaluate if retrieved citations are relevant to the question"""
        if not citations:
            return 0.5  # Neutral score if no citations

        citation_texts = [
            f"Title: {c.get('title', 'N/A')}, Content: {c.get('content', c.get('text', 'N/A'))[:200]}"
            for c in citations[:5]
        ]
        citations_str = "\n".join(citation_texts)

        prompt = f"""Evaluate if the retrieved citations are relevant for answering the question.

Question: {question}

Retrieved Citations:
{citations_str}

Score the retrieval relevance from 0.0 to 1.0 where:
- 1.0 = All citations are highly relevant to the question
- 0.8 = Most citations are relevant
- 0.6 = Some citations are relevant
- 0.4 = Few citations are relevant
- 0.2 = Citations are barely related
- 0.0 = Citations are irrelevant

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
                    metric="retrieval_relevance",
                )
            return min(max(score, 0.0), 1.0)
        except EvaluationError:
            raise
        except Exception as e:
            logger.error(f"Retrieval evaluation error: {e}")
            raise EvaluationError(
                f"OpenAI API call failed: {str(e)}",
                metric="retrieval_relevance",
                original_error=e,
            )


# ============================================================================
# Main Evaluator
# ============================================================================


class LiveKitAgentEvaluator:
    """Main evaluation orchestrator"""

    def __init__(self, api_url: str = "http://localhost:8000", passing_threshold: float = 0.7):
        self.api_url = api_url
        self.passing_threshold = passing_threshold
        self.client: Optional[LiveKitTextClient] = None
        self.evaluator = ResponseEvaluator()

    async def run_evaluation(
        self,
        username: str,
        persona: str,
        test_cases: List[TestCase],
        delay_between_questions: float = 2.0,
    ) -> EvalReport:
        """Run full evaluation and return report"""

        logger.info(
            f"Starting evaluation for {username}/{persona} with {len(test_cases)} test cases"
        )

        # Connect to agent
        self.client = LiveKitTextClient(self.api_url)
        if not await self.client.connect(username, persona):
            raise RuntimeError("Failed to connect to agent")

        results: List[EvalResult] = []

        try:
            for i, test_case in enumerate(test_cases, 1):
                logger.info(f"[{i}/{len(test_cases)}] Testing: {test_case.question[:50]}...")

                # Clear previous citations
                self.client.citations.clear()

                # Send question and measure time
                start_time = time.time()
                response_data = await self.client.send_message(test_case.question)
                response_time_ms = (time.time() - start_time) * 1000

                if not response_data:
                    results.append(
                        EvalResult(
                            test_case_id=test_case.id,
                            question=test_case.question,
                            ground_truth=test_case.ground_truth,
                            agent_response="[NO RESPONSE]",
                            citations=[],
                            passed=False,
                            failure_reason="No response received from agent",
                        )
                    )
                    continue

                agent_response = response_data.get("response", "")
                citations = self.client.get_latest_citations()

                # Evaluate response (handle evaluation system errors)
                try:
                    scores = await self.evaluator.evaluate_response(
                        question=test_case.question,
                        ground_truth=test_case.ground_truth,
                        agent_response=agent_response,
                        expected_keywords=test_case.expected_keywords,
                        citations=citations,
                    )

                    # Calculate overall score (weighted average)
                    overall = (
                        scores["semantic_similarity"] * 0.35
                        + scores["factual_accuracy"] * 0.35
                        + scores["keyword_coverage"] * 0.15
                        + scores["retrieval_relevance"] * 0.15
                    )

                    passed = overall >= self.passing_threshold

                    result = EvalResult(
                        test_case_id=test_case.id,
                        question=test_case.question,
                        ground_truth=test_case.ground_truth,
                        agent_response=agent_response,
                        citations=citations,
                        semantic_similarity=scores["semantic_similarity"],
                        factual_accuracy=scores["factual_accuracy"],
                        keyword_coverage=scores["keyword_coverage"],
                        retrieval_relevance=scores["retrieval_relevance"],
                        overall_score=overall,
                        response_time_ms=response_time_ms,
                        passed=passed,
                        failure_reason=(
                            ""
                            if passed
                            else f"Score {overall:.2f} below threshold {self.passing_threshold}"
                        ),
                    )

                    logger.info(f"   Score: {overall:.2f} ({'PASS' if passed else 'FAIL'})")

                except EvaluationError as eval_err:
                    # Evaluation system failed - mark as error, not as poor performance
                    logger.error(f"   ⚠️  EVALUATION ERROR [{eval_err.metric}]: {eval_err.message}")
                    result = EvalResult(
                        test_case_id=test_case.id,
                        question=test_case.question,
                        ground_truth=test_case.ground_truth,
                        agent_response=agent_response,
                        citations=citations,
                        response_time_ms=response_time_ms,
                        passed=False,
                        failure_reason=f"Evaluation system error: {eval_err.message}",
                        evaluation_error=True,
                        evaluation_error_details=f"[{eval_err.metric}] {eval_err.message}",
                    )

                results.append(result)

                # Delay between questions
                await asyncio.sleep(delay_between_questions)

        finally:
            await self.client.disconnect()

        # Generate report
        return self._generate_report(username, persona, results)

    def _generate_report(
        self, username: str, persona: str, results: List[EvalResult]
    ) -> EvalReport:
        """Generate evaluation report from results"""

        passed_count = sum(1 for r in results if r.passed)
        error_count = sum(1 for r in results if r.evaluation_error)

        # Filter out results with evaluation errors for averaging
        valid_results = [r for r in results if not r.evaluation_error]

        # Category breakdown (only valid results)
        category_results: Dict[str, List[float]] = {}
        for r in valid_results:
            cat = r.test_case_id.split("-")[0] if "-" in r.test_case_id else "general"
            if cat not in category_results:
                category_results[cat] = []
            if r.overall_score is not None:
                category_results[cat].append(r.overall_score)

        category_scores = {
            cat: sum(scores) / len(scores) if scores else 0.0
            for cat, scores in category_results.items()
        }

        # Calculate averages (only from valid results with scores)
        def safe_avg(attr: str) -> float:
            values = [getattr(r, attr) for r in valid_results if getattr(r, attr) is not None]
            return sum(values) / len(values) if values else 0.0

        return EvalReport(
            username=username,
            persona=persona,
            timestamp=datetime.now().isoformat(),
            total_test_cases=len(results),
            passed_count=passed_count,
            failed_count=len(results) - passed_count,
            avg_semantic_similarity=safe_avg("semantic_similarity"),
            avg_factual_accuracy=safe_avg("factual_accuracy"),
            avg_keyword_coverage=safe_avg("keyword_coverage"),
            avg_retrieval_relevance=safe_avg("retrieval_relevance"),
            avg_overall_score=safe_avg("overall_score"),
            avg_response_time_ms=(
                sum(r.response_time_ms for r in results) / len(results) if results else 0.0
            ),
            results=results,
            category_scores=category_scores,
            evaluation_errors_count=error_count,
        )


# ============================================================================
# Report Generation
# ============================================================================


def print_report(report: EvalReport):
    """Print evaluation report to console"""

    print("\n" + "=" * 80)
    print("LIVEKIT TEXT AGENT EVALUATION REPORT")
    print("=" * 80)
    print(f"Username:  {report.username}")
    print(f"Persona:   {report.persona}")
    print(f"Timestamp: {report.timestamp}")
    print("-" * 80)

    # Summary
    pass_rate = (
        (report.passed_count / report.total_test_cases * 100) if report.total_test_cases else 0
    )
    print("\n📊 SUMMARY")
    print(f"   Total Test Cases:    {report.total_test_cases}")
    print(f"   Passed:              {report.passed_count} ({pass_rate:.1f}%)")
    print(f"   Failed:              {report.failed_count}")
    print(f"   Avg Response Time:   {report.avg_response_time_ms:.0f}ms")

    # Evaluation system errors warning
    if report.evaluation_errors_count > 0:
        print(f"\n⚠️  EVALUATION SYSTEM ERRORS: {report.evaluation_errors_count}")
        print("   These tests could not be scored due to LLM API failures.")
        print("   Results are excluded from average scores to avoid false negatives.")

    # Scores
    print("\n📈 AVERAGE SCORES (excluding evaluation errors)")
    print(f"   Semantic Similarity: {report.avg_semantic_similarity:.2f}")
    print(f"   Factual Accuracy:    {report.avg_factual_accuracy:.2f}")
    print(f"   Keyword Coverage:    {report.avg_keyword_coverage:.2f}")
    print(f"   Retrieval Relevance: {report.avg_retrieval_relevance:.2f}")
    print(f"   Overall Score:       {report.avg_overall_score:.2f}")

    # Category breakdown
    if report.category_scores:
        print("\n📁 CATEGORY SCORES")
        for cat, score in sorted(report.category_scores.items()):
            print(f"   {cat}: {score:.2f}")

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
        print(f"   Q: {r.question[:70]}...")
        print(f"   Ground Truth: {r.ground_truth[:70]}...")
        print(f"   Agent Response: {r.agent_response[:70]}...")
        if r.evaluation_error:
            print(f"   ⚠️  Evaluation Error: {r.evaluation_error_details}")
        else:
            sem = f"{r.semantic_similarity:.2f}" if r.semantic_similarity is not None else "N/A"
            fact = f"{r.factual_accuracy:.2f}" if r.factual_accuracy is not None else "N/A"
            kw = f"{r.keyword_coverage:.2f}" if r.keyword_coverage is not None else "N/A"
            ret = f"{r.retrieval_relevance:.2f}" if r.retrieval_relevance is not None else "N/A"
            overall = f"{r.overall_score:.2f}" if r.overall_score is not None else "N/A"
            print(f"   Scores: sem={sem} fact={fact} kw={kw} ret={ret}")
            print(f"   Overall: {overall} | Time: {r.response_time_ms:.0f}ms")
        if not r.passed and not r.evaluation_error:
            print(f"   Reason: {r.failure_reason}")

    print("\n" + "=" * 80)


def save_report(report: EvalReport, output_path: str):
    """Save report to JSON file"""

    # Convert to dict
    report_dict = {
        "username": report.username,
        "persona": report.persona,
        "timestamp": report.timestamp,
        "summary": {
            "total_test_cases": report.total_test_cases,
            "passed_count": report.passed_count,
            "failed_count": report.failed_count,
            "evaluation_errors_count": report.evaluation_errors_count,
            "pass_rate": (
                report.passed_count / report.total_test_cases if report.total_test_cases else 0
            ),
            "has_evaluation_errors": report.has_evaluation_errors,
        },
        "average_scores": {
            "semantic_similarity": report.avg_semantic_similarity,
            "factual_accuracy": report.avg_factual_accuracy,
            "keyword_coverage": report.avg_keyword_coverage,
            "retrieval_relevance": report.avg_retrieval_relevance,
            "overall": report.avg_overall_score,
            "response_time_ms": report.avg_response_time_ms,
            "note": "Averages exclude results with evaluation system errors",
        },
        "category_scores": report.category_scores,
        "results": [
            {
                "test_case_id": r.test_case_id,
                "question": r.question,
                "ground_truth": r.ground_truth,
                "agent_response": r.agent_response,
                "citations_count": len(r.citations),
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
    }

    with open(output_path, "w") as f:
        json.dump(report_dict, f, indent=2)

    logger.info(f"Report saved to: {output_path}")


# ============================================================================
# Test Case Loading
# ============================================================================


def load_test_cases(file_path: str) -> List[TestCase]:
    """Load test cases from JSON file"""

    with open(file_path, "r") as f:
        data = json.load(f)

    test_cases = []
    for item in data.get("test_cases", data if isinstance(data, list) else []):
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


# ============================================================================
# CLI
# ============================================================================


async def main():
    parser = argparse.ArgumentParser(description="Evaluate LiveKit Text Agent")
    parser.add_argument("--username", "-u", required=True, help="Expert username")
    parser.add_argument("--persona", "-p", default="default", help="Persona name")
    parser.add_argument("--test-file", "-t", required=True, help="Path to test cases JSON")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--output", "-o", help="Output JSON report path")
    parser.add_argument("--threshold", type=float, default=0.7, help="Passing threshold (0-1)")
    parser.add_argument(
        "--delay", type=float, default=2.0, help="Delay between questions (seconds)"
    )

    args = parser.parse_args()

    # Load test cases
    test_cases = load_test_cases(args.test_file)
    logger.info(f"Loaded {len(test_cases)} test cases from {args.test_file}")

    # Run evaluation
    evaluator = LiveKitAgentEvaluator(api_url=args.api_url, passing_threshold=args.threshold)

    report = await evaluator.run_evaluation(
        username=args.username,
        persona=args.persona,
        test_cases=test_cases,
        delay_between_questions=args.delay,
    )

    # Print report
    print_report(report)

    # Save report if output specified
    if args.output:
        save_report(report, args.output)
    else:
        # Auto-save to results directory
        output_path = f"evaluations/results/eval_{args.username}_{args.persona}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        save_report(report, output_path)

    # Return exit code based on pass rate
    pass_rate = report.passed_count / report.total_test_cases if report.total_test_cases else 0
    sys.exit(0 if pass_rate >= 0.8 else 1)


if __name__ == "__main__":
    asyncio.run(main())
