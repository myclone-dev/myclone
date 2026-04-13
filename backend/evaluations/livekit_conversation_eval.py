#!/usr/bin/env python3
"""
LiveKit Conversation Evaluation System

This module evaluates multi-turn conversations with LiveKit text-only agents by:
1. Connecting to an agent via the connection-details API
2. Sending a series of queries (up to 3 turns) and capturing responses
3. Evaluating context retention across turns
4. Scoring the entire conversation holistically

Usage:
    python -m evaluations.livekit_conversation_eval --username rishikesh --persona default --test-file conversation_test_cases.json

Or programmatically:
    from evaluations.livekit_conversation_eval import ConversationEvaluator
    evaluator = ConversationEvaluator("http://localhost:8000")
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
class ConversationTurn:
    """Single turn in a conversation"""

    query: str
    ground_truth: str
    expected_keywords: List[str] = field(default_factory=list)
    context_check: str = ""  # Description of what context should be retained


@dataclass
class ConversationTestCase:
    """Multi-turn conversation test case"""

    id: str
    turns: List[ConversationTurn]
    category: str = "general"
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnResult:
    """Result of a single turn in a conversation"""

    turn_number: int
    query: str
    ground_truth: str
    agent_response: str
    citations: List[Dict[str, Any]]

    # Per-turn scores
    semantic_similarity: Optional[float] = None
    factual_accuracy: Optional[float] = None
    keyword_coverage: Optional[float] = None
    context_retention: Optional[float] = None  # How well it used previous context

    response_time_ms: float = 0.0


@dataclass
class ConversationResult:
    """Result of evaluating a full conversation"""

    test_case_id: str
    category: str
    description: str
    turn_results: List[TurnResult]

    # Conversation-level scores
    avg_semantic_similarity: float = 0.0
    avg_factual_accuracy: float = 0.0
    avg_keyword_coverage: float = 0.0
    avg_context_retention: float = 0.0
    conversation_coherence: float = 0.0  # Overall flow and coherence
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
class ConversationEvalReport:
    """Complete conversation evaluation report"""

    username: str
    persona: str
    timestamp: str
    total_conversations: int
    passed_count: int
    failed_count: int

    # Aggregate scores
    avg_semantic_similarity: float = 0.0
    avg_factual_accuracy: float = 0.0
    avg_keyword_coverage: float = 0.0
    avg_context_retention: float = 0.0
    avg_conversation_coherence: float = 0.0
    avg_overall_score: float = 0.0
    avg_response_time_ms: float = 0.0

    # Individual results
    results: List[ConversationResult] = field(default_factory=list)

    # Category breakdown
    category_scores: Dict[str, float] = field(default_factory=dict)

    # Evaluation errors count
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
# Conversation Evaluator
# ============================================================================


class ConversationResponseEvaluator:
    """Evaluates conversation responses using LLM"""

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
        logger.info(f"ConversationResponseEvaluator initialized with model: {model}")

    async def evaluate_turn(
        self,
        turn_number: int,
        query: str,
        ground_truth: str,
        agent_response: str,
        expected_keywords: List[str],
        context_check: str,
        conversation_history: List[Dict[str, str]],
    ) -> Dict[str, float]:
        """Evaluate a single turn in a conversation"""

        # 1. Semantic similarity
        semantic_score = await self._evaluate_semantic_similarity(
            query, ground_truth, agent_response
        )

        # 2. Factual accuracy
        factual_score = await self._evaluate_factual_accuracy(ground_truth, agent_response)

        # 3. Keyword coverage
        keyword_score = self._evaluate_keyword_coverage(agent_response, expected_keywords)

        # 4. Context retention (only for turns > 1)
        context_score = 1.0
        if turn_number > 1 and conversation_history:
            context_score = await self._evaluate_context_retention(
                query, agent_response, context_check, conversation_history
            )

        return {
            "semantic_similarity": semantic_score,
            "factual_accuracy": factual_score,
            "keyword_coverage": keyword_score,
            "context_retention": context_score,
        }

    async def evaluate_conversation_coherence(self, conversation: List[Dict[str, str]]) -> float:
        """Evaluate overall conversation coherence and flow"""

        if len(conversation) < 2:
            return 1.0  # Single turn, coherence is trivially 1.0

        # Format conversation for LLM
        conv_text = "\n".join(
            [f"User: {turn['query']}\nAgent: {turn['response']}" for turn in conversation]
        )

        prompt = f"""Evaluate the coherence and flow of this multi-turn conversation.

Conversation:
{conv_text}

Score the conversation coherence from 0.0 to 1.0 where:
- 1.0 = Perfectly coherent, natural flow, agent maintains context throughout
- 0.8 = Good coherence with minor inconsistencies
- 0.6 = Some coherence issues, agent occasionally loses track of context
- 0.4 = Noticeable coherence problems, responses feel disconnected
- 0.2 = Poor coherence, agent frequently ignores previous context
- 0.0 = No coherence, each response is completely independent

Consider:
1. Does the agent remember what was discussed?
2. Are follow-up questions answered appropriately?
3. Does the conversation flow naturally?
4. Are there any contradictions between responses?

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
                    metric="conversation_coherence",
                )
            return min(max(score, 0.0), 1.0)
        except EvaluationError:
            raise
        except Exception as e:
            logger.error(f"Coherence evaluation error: {e}")
            raise EvaluationError(
                f"OpenAI API call failed: {str(e)}",
                metric="conversation_coherence",
                original_error=e,
            )

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

    async def _evaluate_context_retention(
        self,
        current_query: str,
        current_response: str,
        context_check: str,
        conversation_history: List[Dict[str, str]],
    ) -> float:
        """Evaluate if the agent retained context from previous turns"""

        # Format previous conversation
        prev_conv = "\n".join(
            [
                f"Turn {i+1}:\nUser: {turn['query']}\nAgent: {turn['response']}"
                for i, turn in enumerate(conversation_history)
            ]
        )

        context_hint = f"\nExpected context usage: {context_check}" if context_check else ""

        prompt = f"""Evaluate if the agent's current response appropriately uses context from the previous conversation.

Previous Conversation:
{prev_conv}

Current Turn:
User: {current_query}
Agent: {current_response}
{context_hint}

Score the context retention from 0.0 to 1.0 where:
- 1.0 = Perfectly uses and builds upon previous context
- 0.8 = Good use of context with minor gaps
- 0.6 = Uses some context but misses important references
- 0.4 = Limited context usage, could have referenced more
- 0.2 = Barely uses any previous context
- 0.0 = Completely ignores previous conversation

Consider:
1. Does the response reference information from earlier turns?
2. Does it avoid redundant explanations of already-discussed topics?
3. Does it correctly interpret follow-up questions in context?

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
                    metric="context_retention",
                )
            return min(max(score, 0.0), 1.0)
        except EvaluationError:
            raise
        except Exception as e:
            logger.error(f"Context retention evaluation error: {e}")
            raise EvaluationError(
                f"OpenAI API call failed: {str(e)}",
                metric="context_retention",
                original_error=e,
            )


# ============================================================================
# Main Evaluator
# ============================================================================


class ConversationEvaluator:
    """Main conversation evaluation orchestrator"""

    def __init__(self, api_url: str = "http://localhost:8000", passing_threshold: float = 0.7):
        self.api_url = api_url
        self.passing_threshold = passing_threshold
        self.client: Optional[LiveKitTextClient] = None
        self.evaluator = ConversationResponseEvaluator()

    async def run_evaluation(
        self,
        username: str,
        persona: str,
        test_cases: List[ConversationTestCase],
        delay_between_turns: float = 2.0,
        delay_between_conversations: float = 5.0,
    ) -> ConversationEvalReport:
        """Run full conversation evaluation and return report"""

        logger.info(
            f"Starting conversation evaluation for {username}/{persona} "
            f"with {len(test_cases)} conversations"
        )

        results: List[ConversationResult] = []

        for conv_idx, test_case in enumerate(test_cases, 1):
            logger.info(
                f"[{conv_idx}/{len(test_cases)}] "
                f"Conversation: {test_case.id} ({len(test_case.turns)} turns)"
            )

            # Connect fresh for each conversation to ensure clean state
            self.client = LiveKitTextClient(self.api_url)
            if not await self.client.connect(username, persona):
                results.append(
                    ConversationResult(
                        test_case_id=test_case.id,
                        category=test_case.category,
                        description=test_case.description,
                        turn_results=[],
                        passed=False,
                        failure_reason="Failed to connect to agent",
                    )
                )
                continue

            try:
                result = await self._evaluate_conversation(test_case, delay_between_turns)
                results.append(result)
            except EvaluationError as eval_err:
                logger.error(f"Evaluation error for {test_case.id}: {eval_err}")
                results.append(
                    ConversationResult(
                        test_case_id=test_case.id,
                        category=test_case.category,
                        description=test_case.description,
                        turn_results=[],
                        passed=False,
                        evaluation_error=True,
                        evaluation_error_details=str(eval_err),
                    )
                )
            finally:
                await self.client.disconnect()

            # Delay between conversations
            if conv_idx < len(test_cases):
                await asyncio.sleep(delay_between_conversations)

        # Generate report
        return self._generate_report(username, persona, results)

    async def _evaluate_conversation(
        self, test_case: ConversationTestCase, delay_between_turns: float
    ) -> ConversationResult:
        """Evaluate a single multi-turn conversation"""

        turn_results: List[TurnResult] = []
        conversation_history: List[Dict[str, str]] = []
        total_time = 0.0

        for turn_idx, turn in enumerate(test_case.turns, 1):
            logger.info(f"   Turn {turn_idx}/{len(test_case.turns)}: {turn.query[:50]}...")

            # Clear previous citations
            self.client.citations.clear()

            # Send query and measure time
            start_time = time.time()
            response_data = await self.client.send_message(turn.query)
            response_time_ms = (time.time() - start_time) * 1000
            total_time += response_time_ms

            if not response_data:
                # No response - record failure and continue
                turn_results.append(
                    TurnResult(
                        turn_number=turn_idx,
                        query=turn.query,
                        ground_truth=turn.ground_truth,
                        agent_response="[NO RESPONSE]",
                        citations=[],
                        response_time_ms=response_time_ms,
                    )
                )
                conversation_history.append({"query": turn.query, "response": "[NO RESPONSE]"})
                continue

            agent_response = response_data.get("response", "")
            citations = self.client.get_latest_citations()

            # Evaluate turn
            scores = await self.evaluator.evaluate_turn(
                turn_number=turn_idx,
                query=turn.query,
                ground_truth=turn.ground_truth,
                agent_response=agent_response,
                expected_keywords=turn.expected_keywords,
                context_check=turn.context_check,
                conversation_history=conversation_history,
            )

            turn_result = TurnResult(
                turn_number=turn_idx,
                query=turn.query,
                ground_truth=turn.ground_truth,
                agent_response=agent_response,
                citations=citations,
                semantic_similarity=scores["semantic_similarity"],
                factual_accuracy=scores["factual_accuracy"],
                keyword_coverage=scores["keyword_coverage"],
                context_retention=scores["context_retention"],
                response_time_ms=response_time_ms,
            )
            turn_results.append(turn_result)

            # Add to history for next turn
            conversation_history.append({"query": turn.query, "response": agent_response})

            logger.info(
                f"      Scores: sem={scores['semantic_similarity']:.2f} "
                f"fact={scores['factual_accuracy']:.2f} "
                f"ctx={scores['context_retention']:.2f}"
            )

            # Delay between turns
            if turn_idx < len(test_case.turns):
                await asyncio.sleep(delay_between_turns)

        # Evaluate overall conversation coherence
        coherence_score = await self.evaluator.evaluate_conversation_coherence(conversation_history)

        # Calculate conversation-level averages
        valid_turns = [t for t in turn_results if t.agent_response != "[NO RESPONSE]"]

        def safe_avg(attr: str) -> float:
            values = [getattr(t, attr) for t in valid_turns if getattr(t, attr) is not None]
            return sum(values) / len(values) if values else 0.0

        avg_semantic = safe_avg("semantic_similarity")
        avg_factual = safe_avg("factual_accuracy")
        avg_keyword = safe_avg("keyword_coverage")
        avg_context = safe_avg("context_retention")

        # Overall score (weighted)
        overall = (
            avg_semantic * 0.25
            + avg_factual * 0.25
            + avg_keyword * 0.10
            + avg_context * 0.25
            + coherence_score * 0.15
        )

        passed = overall >= self.passing_threshold

        return ConversationResult(
            test_case_id=test_case.id,
            category=test_case.category,
            description=test_case.description,
            turn_results=turn_results,
            avg_semantic_similarity=avg_semantic,
            avg_factual_accuracy=avg_factual,
            avg_keyword_coverage=avg_keyword,
            avg_context_retention=avg_context,
            conversation_coherence=coherence_score,
            overall_score=overall,
            total_response_time_ms=total_time,
            passed=passed,
            failure_reason=(
                "" if passed else f"Score {overall:.2f} below threshold {self.passing_threshold}"
            ),
        )

    def _generate_report(
        self, username: str, persona: str, results: List[ConversationResult]
    ) -> ConversationEvalReport:
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

        # Calculate averages
        def safe_avg(attr: str) -> float:
            values = [getattr(r, attr) for r in valid_results if getattr(r, attr) is not None]
            return sum(values) / len(values) if values else 0.0

        return ConversationEvalReport(
            username=username,
            persona=persona,
            timestamp=datetime.now().isoformat(),
            total_conversations=len(results),
            passed_count=passed_count,
            failed_count=len(results) - passed_count,
            avg_semantic_similarity=safe_avg("avg_semantic_similarity"),
            avg_factual_accuracy=safe_avg("avg_factual_accuracy"),
            avg_keyword_coverage=safe_avg("avg_keyword_coverage"),
            avg_context_retention=safe_avg("avg_context_retention"),
            avg_conversation_coherence=safe_avg("conversation_coherence"),
            avg_overall_score=safe_avg("overall_score"),
            avg_response_time_ms=(
                sum(r.total_response_time_ms for r in results) / len(results) if results else 0.0
            ),
            results=results,
            category_scores=category_scores,
            evaluation_errors_count=error_count,
        )


# ============================================================================
# Report Generation
# ============================================================================


def print_report(report: ConversationEvalReport):
    """Print evaluation report to console"""

    print("\n" + "=" * 80)
    print("LIVEKIT CONVERSATION EVALUATION REPORT")
    print("=" * 80)
    print(f"Username:  {report.username}")
    print(f"Persona:   {report.persona}")
    print(f"Timestamp: {report.timestamp}")
    print("-" * 80)

    # Summary
    pass_rate = (
        (report.passed_count / report.total_conversations * 100)
        if report.total_conversations
        else 0
    )
    print("\n📊 SUMMARY")
    print(f"   Total Conversations: {report.total_conversations}")
    print(f"   Passed:              {report.passed_count} ({pass_rate:.1f}%)")
    print(f"   Failed:              {report.failed_count}")
    print(f"   Avg Response Time:   {report.avg_response_time_ms:.0f}ms (total per conv)")

    # Evaluation system errors warning
    if report.evaluation_errors_count > 0:
        print(f"\n⚠️  EVALUATION SYSTEM ERRORS: {report.evaluation_errors_count}")
        print("   These conversations could not be scored due to LLM API failures.")

    # Scores
    print("\n📈 AVERAGE SCORES (excluding evaluation errors)")
    print(f"   Semantic Similarity:    {report.avg_semantic_similarity:.2f}")
    print(f"   Factual Accuracy:       {report.avg_factual_accuracy:.2f}")
    print(f"   Keyword Coverage:       {report.avg_keyword_coverage:.2f}")
    print(f"   Context Retention:      {report.avg_context_retention:.2f}")
    print(f"   Conversation Coherence: {report.avg_conversation_coherence:.2f}")
    print(f"   Overall Score:          {report.avg_overall_score:.2f}")

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
        print(f"   Category: {r.category}")
        if r.description:
            print(f"   Description: {r.description[:70]}...")

        if r.evaluation_error:
            print(f"   ⚠️  Evaluation Error: {r.evaluation_error_details}")
        else:
            print(f"   Turns: {len(r.turn_results)}")
            print(
                f"   Scores: sem={r.avg_semantic_similarity:.2f} "
                f"fact={r.avg_factual_accuracy:.2f} "
                f"ctx={r.avg_context_retention:.2f} "
                f"coh={r.conversation_coherence:.2f}"
            )
            print(f"   Overall: {r.overall_score:.2f} | " f"Time: {r.total_response_time_ms:.0f}ms")

            # Show each turn
            for turn in r.turn_results:
                ctx = (
                    f" ctx={turn.context_retention:.2f}"
                    if turn.context_retention is not None
                    else ""
                )
                print(f"\n   Turn {turn.turn_number}:")
                print(f"      Q: {turn.query[:60]}...")
                print(f"      A: {turn.agent_response[:60]}...")
                sem = (
                    f"{turn.semantic_similarity:.2f}"
                    if turn.semantic_similarity is not None
                    else "N/A"
                )
                fact = (
                    f"{turn.factual_accuracy:.2f}" if turn.factual_accuracy is not None else "N/A"
                )
                print(f"      sem={sem} fact={fact}{ctx}")

        if not r.passed and not r.evaluation_error:
            print(f"   Reason: {r.failure_reason}")

    print("\n" + "=" * 80)


def save_report(report: ConversationEvalReport, output_path: str):
    """Save report to JSON file"""

    report_dict = {
        "username": report.username,
        "persona": report.persona,
        "timestamp": report.timestamp,
        "summary": {
            "total_conversations": report.total_conversations,
            "passed_count": report.passed_count,
            "failed_count": report.failed_count,
            "evaluation_errors_count": report.evaluation_errors_count,
            "pass_rate": (
                report.passed_count / report.total_conversations
                if report.total_conversations
                else 0
            ),
            "has_evaluation_errors": report.has_evaluation_errors,
        },
        "average_scores": {
            "semantic_similarity": report.avg_semantic_similarity,
            "factual_accuracy": report.avg_factual_accuracy,
            "keyword_coverage": report.avg_keyword_coverage,
            "context_retention": report.avg_context_retention,
            "conversation_coherence": report.avg_conversation_coherence,
            "overall": report.avg_overall_score,
            "response_time_ms": report.avg_response_time_ms,
            "note": "Averages exclude results with evaluation system errors",
        },
        "category_scores": report.category_scores,
        "results": [
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
                        "citations_count": len(t.citations),
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
    }

    with open(output_path, "w") as f:
        json.dump(report_dict, f, indent=2)

    logger.info(f"Report saved to: {output_path}")


# ============================================================================
# Test Case Loading
# ============================================================================


def load_test_cases(file_path: str) -> List[ConversationTestCase]:
    """Load conversation test cases from JSON file"""

    with open(file_path, "r") as f:
        data = json.load(f)

    test_cases = []
    for item in data.get("test_cases", data if isinstance(data, list) else []):
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


# ============================================================================
# CLI
# ============================================================================


async def main():
    parser = argparse.ArgumentParser(description="Evaluate LiveKit Conversation Agent")
    parser.add_argument("--username", "-u", required=True, help="Expert username")
    parser.add_argument("--persona", "-p", default="default", help="Persona name")
    parser.add_argument(
        "--test-file", "-t", required=True, help="Path to conversation test cases JSON"
    )
    parser.add_argument("--api-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--output", "-o", help="Output JSON report path")
    parser.add_argument("--threshold", type=float, default=0.7, help="Passing threshold (0-1)")
    parser.add_argument(
        "--turn-delay",
        type=float,
        default=2.0,
        help="Delay between turns (seconds)",
    )
    parser.add_argument(
        "--conv-delay",
        type=float,
        default=5.0,
        help="Delay between conversations (seconds)",
    )

    args = parser.parse_args()

    # Load test cases
    test_cases = load_test_cases(args.test_file)
    logger.info(f"Loaded {len(test_cases)} conversation test cases from {args.test_file}")

    # Run evaluation
    evaluator = ConversationEvaluator(api_url=args.api_url, passing_threshold=args.threshold)

    report = await evaluator.run_evaluation(
        username=args.username,
        persona=args.persona,
        test_cases=test_cases,
        delay_between_turns=args.turn_delay,
        delay_between_conversations=args.conv_delay,
    )

    # Print report
    print_report(report)

    # Save report if output specified
    if args.output:
        save_report(report, args.output)
    else:
        # Auto-save to results directory
        output_path = (
            f"evaluations/results/conv_eval_{args.username}_{args.persona}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        save_report(report, output_path)

    # Return exit code based on pass rate and errors
    pass_rate = (
        report.passed_count / report.total_conversations if report.total_conversations else 0
    )
    sys.exit(0 if pass_rate >= 0.8 and not report.has_evaluation_errors else 1)


if __name__ == "__main__":
    asyncio.run(main())
