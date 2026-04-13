# Standard library imports
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from evaluations.evaluators.factual_evaluator import FactualAccuracyEvaluator, FactualResult

# Internal evaluator components
from evaluations.evaluators.llama_evaluator import LlamaEvalResult, LlamaIndexEvaluator

# Configure logger for composite evaluation
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """
    Comprehensive evaluation result for a single test case.

    This dataclass encapsulates all evaluation metrics and metadata for
    a single test case, providing a complete picture of AI persona performance.
    Used for detailed analysis, debugging, and reporting.

    Contains results from:
    - LlamaIndex evaluations (faithfulness, relevancy)
    - Factual accuracy evaluation (ground truth comparison)
    - Overall scoring and pass/fail determination
    - Performance timing and metadata
    - Qualitative feedback (issues and strengths)
    """

    test_case_id: str
    category: str
    question: str
    response: str
    contexts: List[str]

    # LlamaIndex evaluation results
    llama_result: LlamaEvalResult

    # Factual accuracy results
    factual_result: FactualResult

    # Overall assessment
    overall_score: float
    passed: bool

    # Timing and metadata
    evaluation_time: float  # seconds
    timestamp: str

    # Detailed feedback
    issues: List[str]
    strengths: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "test_case_id": self.test_case_id,
            "category": self.category,
            "question": self.question,
            "response": self.response[:500] + "..." if len(self.response) > 500 else self.response,
            "contexts_count": len(self.contexts),
            # Scores
            "overall_score": round(self.overall_score, 3),
            "passed": self.passed,
            # LlamaIndex results
            "faithfulness_score": round(self.llama_result.faithfulness_score, 3),
            "relevancy_score": round(self.llama_result.relevancy_score, 3),
            "faithfulness_passing": self.llama_result.faithfulness_passing,
            "relevancy_passing": self.llama_result.relevancy_passing,
            # Factual results
            "factual_accuracy": round(self.factual_result.accuracy, 3),
            "factual_passing": self.factual_result.factual_passing,
            "missing_facts_count": len(self.factual_result.missing_facts),
            "false_info_count": len(self.factual_result.false_information),
            # Metadata
            "evaluation_time": round(self.evaluation_time, 2),
            "timestamp": self.timestamp,
            # Feedback
            "issues": self.issues,
            "strengths": self.strengths,
            # Detailed results (for debugging)
            "detailed": {
                "faithfulness_feedback": self.llama_result.faithfulness_feedback,
                "relevancy_feedback": self.llama_result.relevancy_feedback,
                "missing_facts": self.factual_result.missing_facts,
                "false_information": self.factual_result.false_information,
                "required_info_missing": self.factual_result.required_info_missing,
            },
        }


@dataclass
class EvaluationSummary:
    """
    Aggregated summary of evaluation results for an entire persona evaluation.

    Provides high-level insights into persona performance across all test cases,
    including statistical analysis, failure patterns, and performance breakdowns.
    Used for dashboard reporting and persona improvement recommendations.

    Key insights provided:
    - Overall performance metrics and trends
    - Category-specific performance analysis
    - Common failure patterns and root causes
    - Performance benchmarking data
    """

    persona_username: str
    timestamp: str
    total_tests: int
    tests_passed: int
    tests_failed: int
    overall_score: float

    # Breakdown by metric
    avg_faithfulness: float
    avg_relevancy: float
    avg_factual_accuracy: float

    # Breakdown by category
    category_scores: Dict[str, float]
    category_pass_rates: Dict[str, float]

    # Failure analysis
    common_failure_reasons: List[str]
    failing_categories: List[str]

    # Performance
    total_evaluation_time: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "persona_username": self.persona_username,
            "timestamp": self.timestamp,
            "total_tests": self.total_tests,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "overall_score": round(self.overall_score, 3),
            "pass_rate": (
                round(self.tests_passed / self.total_tests, 3) if self.total_tests > 0 else 0.0
            ),
            "metrics": {
                "avg_faithfulness": round(self.avg_faithfulness, 3),
                "avg_relevancy": round(self.avg_relevancy, 3),
                "avg_factual_accuracy": round(self.avg_factual_accuracy, 3),
            },
            "categories": {
                "scores": {k: round(v, 3) for k, v in self.category_scores.items()},
                "pass_rates": {k: round(v, 3) for k, v in self.category_pass_rates.items()},
            },
            "analysis": {
                "common_failure_reasons": self.common_failure_reasons,
                "failing_categories": self.failing_categories,
            },
            "performance": {"total_evaluation_time": round(self.total_evaluation_time, 2)},
        }


class CompositeEvaluator:
    """
    Orchestrates comprehensive evaluation using multiple evaluation dimensions.

    This is the main evaluation coordinator that combines:
    1. **LlamaIndex Evaluation**: Industry-standard faithfulness and relevancy metrics
    2. **Factual Accuracy Evaluation**: Custom ground-truth comparison
    3. **Weighted Scoring**: Balanced assessment across multiple dimensions
    4. **Performance Analysis**: Timing and efficiency metrics
    5. **Qualitative Feedback**: Issues identification and strengths recognition

    The composite approach ensures comprehensive evaluation that covers:
    - Technical quality (faithfulness, relevancy)
    - Factual correctness (accuracy against ground truth)
    - Completeness (coverage of required information)
    - Performance (response time and efficiency)

    Scoring Weights (configurable):
    - Faithfulness: 25% (response supported by context)
    - Relevancy: 25% (response answers the question)
    - Factual Accuracy: 35% (alignment with ground truth)
    - Completeness: 15% (coverage of required info)
    """

    def __init__(self):
        """
        Initialize the composite evaluator with all sub-evaluators and configuration.

        Sets up the evaluation pipeline with optimized scoring weights based on
        empirical testing and domain expertise. Factual accuracy gets the highest
        weight as it directly measures correctness against ground truth.
        """
        # Initialize sub-evaluators
        self.llama_evaluator = LlamaIndexEvaluator()
        self.factual_evaluator = FactualAccuracyEvaluator()

        # Configure weighted scoring system
        # These weights were determined through empirical testing and domain expertise
        self.score_weights = {
            "faithfulness": 0.25,  # Response grounded in context
            "relevancy": 0.25,  # Response answers the question
            "factual_accuracy": 0.35,  # Highest weight - correctness against ground truth
            "completeness": 0.15,  # Coverage of required information
        }

        # Log initialization for monitoring
        logger.info("Composite evaluator initialized successfully")
        logger.info(f"Scoring weights: {self.score_weights}")
        logger.info("Sub-evaluators: LlamaIndex (faithfulness/relevancy) + Factual accuracy")

    async def evaluate_test_case(
        self, test_case: Dict[str, Any], response: str, contexts: List[str]
    ) -> TestResult:
        """
        Evaluate a single test case using all available evaluation metrics.

        This is the core evaluation method that orchestrates all sub-evaluators
        to produce a comprehensive assessment of AI persona performance for
        a single test case.

        Evaluation Process:
        1. Run LlamaIndex and factual evaluations concurrently for performance
        2. Handle evaluation failures gracefully with default scores
        3. Calculate weighted overall score across all dimensions
        4. Generate qualitative feedback identifying issues and strengths
        5. Record timing and metadata for performance analysis

        Args:
            test_case (Dict[str, Any]): Test case configuration containing:
                - id: Unique test case identifier
                - category: Test category (profile, skills, experience, etc.)
                - question: The question to ask the AI persona
                - expected_facts: List of facts that should be present
                - must_include: Required information that must be present
                - must_exclude: Information that should not be present

            response (str): AI persona's response to evaluate

            contexts (List[str]): Retrieved context chunks used for response generation
                                 Used for faithfulness evaluation

        Returns:
            TestResult: Comprehensive evaluation result with:
                - Individual metric scores (faithfulness, relevancy, factual accuracy)
                - Weighted overall score and pass/fail determination
                - Detailed qualitative feedback (issues and strengths)
                - Performance timing and metadata
                - All raw evaluation data for debugging
        """
        # Record evaluation start time for performance measurement
        start_time = asyncio.get_event_loop().time()
        timestamp = datetime.now().isoformat()

        # Extract test case metadata with safe defaults
        test_case_id = test_case.get("id", "unknown")
        category = test_case.get("category", "unknown")
        question = test_case.get("question", "")

        # Log evaluation start for debugging and monitoring
        logger.debug(f"Starting comprehensive evaluation for test case: {test_case_id}")
        logger.debug(f"Category: {category}, Question length: {len(question)} chars")

        try:
            # Run both evaluation types concurrently for optimal performance
            # This reduces total evaluation time by ~40-50% compared to sequential execution

            # LlamaIndex evaluation (faithfulness + relevancy)
            llama_task = self.llama_evaluator.evaluate_response(
                query=question, response=response, contexts=contexts
            )

            # Factual accuracy evaluation (run in thread pool to avoid blocking)
            # Using asyncio.to_thread for CPU-bound factual comparison work
            factual_task = asyncio.to_thread(
                self.factual_evaluator.evaluate_facts,
                response=response,
                expected_facts=test_case.get("expected_facts", []),
                must_include=test_case.get("must_include", []),
                must_exclude=test_case.get("must_exclude", []),
            )

            # Execute both evaluations concurrently with exception isolation
            # return_exceptions=True ensures one failure doesn't cancel the other
            llama_result, factual_result = await asyncio.gather(
                llama_task, factual_task, return_exceptions=True  # Critical for robust evaluation
            )

            # Handle evaluation failures gracefully with detailed error logging
            # This ensures partial results are available even if some evaluators fail

            if isinstance(llama_result, Exception):
                logger.error(f"LlamaIndex evaluation failed for {test_case_id}: {llama_result}")
                logger.error(f"Question: {question[:100]}...")
                logger.error(f"Response: {response[:100]}...")

                # Create default failed result for LlamaIndex evaluation
                llama_result = LlamaEvalResult(
                    faithfulness_score=0.0,
                    relevancy_score=0.0,
                    faithfulness_feedback=f"LlamaIndex evaluation error: {str(llama_result)}",
                    relevancy_feedback=f"LlamaIndex evaluation error: {str(llama_result)}",
                    faithfulness_passing=False,
                    relevancy_passing=False,
                    overall_passing=False,
                )

            if isinstance(factual_result, Exception):
                logger.error(
                    f"Factual accuracy evaluation failed for {test_case_id}: {factual_result}"
                )
                logger.error(f"Expected facts count: {len(test_case.get('expected_facts', []))}")
                logger.error(f"Must include count: {len(test_case.get('must_include', []))}")

                # Create default failed result for factual accuracy evaluation
                factual_result = FactualResult(
                    accuracy=0.0,
                    fact_checks=[],
                    missing_facts=[],
                    false_information=[],
                    required_info_missing=[],
                    factual_passing=False,
                )

            # Calculate weighted overall score across all evaluation dimensions
            overall_score = self._calculate_overall_score(llama_result, factual_result)

            # Determine overall pass/fail status based on individual metric thresholds
            passed = self._determine_overall_pass(llama_result, factual_result)

            # Generate qualitative feedback for improvement and debugging
            issues, strengths = self._generate_feedback(llama_result, factual_result, test_case)

            # Record total evaluation time for performance monitoring
            evaluation_time = asyncio.get_event_loop().time() - start_time

            result = TestResult(
                test_case_id=test_case_id,
                category=category,
                question=question,
                response=response,
                contexts=contexts,
                llama_result=llama_result,
                factual_result=factual_result,
                overall_score=overall_score,
                passed=passed,
                evaluation_time=evaluation_time,
                timestamp=timestamp,
                issues=issues,
                strengths=strengths,
            )

            # Log successful evaluation completion with key metrics
            logger.debug(f"Test case {test_case_id} evaluation completed successfully")
            logger.debug(f"Overall score: {overall_score:.3f}, Passed: {passed}")
            logger.debug(
                f"Individual scores - Faithfulness: {llama_result.faithfulness_score:.2f}, "
                f"Relevancy: {llama_result.relevancy_score:.2f}, "
                f"Factual: {factual_result.accuracy:.2f}"
            )
            logger.debug(f"Evaluation time: {evaluation_time:.2f}s")

            return result

        except Exception as e:
            logger.error(f"Critical error in composite evaluation for {test_case_id}: {e}")
            logger.error(f"Test case data: {test_case}")
            logger.error(f"Response length: {len(response) if response else 0}")
            logger.error(f"Context count: {len(contexts) if contexts else 0}")

            # Calculate evaluation time even for failed cases
            evaluation_time = asyncio.get_event_loop().time() - start_time

            # Return comprehensive failed evaluation result
            # This ensures consistent result structure even for critical failures
            return TestResult(
                test_case_id=test_case_id,
                category=category,
                question=question,
                response=response,
                contexts=contexts,
                # Create minimal failed results for both evaluators
                llama_result=LlamaEvalResult(
                    0.0,
                    0.0,
                    f"Critical error: {str(e)}",
                    f"Critical error: {str(e)}",
                    False,
                    False,
                    False,
                ),
                factual_result=FactualResult(0.0, [], [], [], [], False),
                overall_score=0.0,
                passed=False,
                evaluation_time=evaluation_time,
                timestamp=timestamp,
                issues=[f"Critical evaluation error: {str(e)}"],
                strengths=[],
            )

    def _calculate_overall_score(
        self, llama_result: LlamaEvalResult, factual_result: FactualResult
    ) -> float:
        """Calculate weighted overall score"""

        # Completeness score based on missing required info and false information
        completeness_score = 1.0
        if factual_result.required_info_missing:
            completeness_score -= 0.5
        if factual_result.false_information:
            completeness_score -= 0.5
        completeness_score = max(0.0, completeness_score)

        # Weighted combination
        score = (
            llama_result.faithfulness_score * self.score_weights["faithfulness"]
            + llama_result.relevancy_score * self.score_weights["relevancy"]
            + factual_result.accuracy * self.score_weights["factual_accuracy"]
            + completeness_score * self.score_weights["completeness"]
        )

        return min(score, 1.0)

    def _determine_overall_pass(
        self, llama_result: LlamaEvalResult, factual_result: FactualResult
    ) -> bool:
        """Determine if the test case passes overall"""
        return llama_result.overall_passing and factual_result.factual_passing

    def _generate_feedback(
        self,
        llama_result: LlamaEvalResult,
        factual_result: FactualResult,
        test_case: Dict[str, Any],
    ) -> tuple[List[str], List[str]]:
        """Generate issues and strengths feedback"""

        issues = []
        strengths = []

        # LlamaIndex issues
        if not llama_result.faithfulness_passing:
            issues.append(
                f"Low faithfulness score ({llama_result.faithfulness_score:.2f}) - response may not align with provided context"
            )

        if not llama_result.relevancy_passing:
            issues.append(
                f"Low relevancy score ({llama_result.relevancy_score:.2f}) - response may not adequately answer the question"
            )

        # Factual accuracy issues
        if factual_result.missing_facts:
            issues.append(f"Missing {len(factual_result.missing_facts)} expected facts")

        if factual_result.false_information:
            issues.append(
                f"Contains {len(factual_result.false_information)} pieces of false information: {', '.join(factual_result.false_information)}"
            )

        if factual_result.required_info_missing:
            issues.append(
                f"Missing required information: {', '.join(factual_result.required_info_missing)}"
            )

        # Strengths
        if llama_result.faithfulness_passing:
            strengths.append(
                f"High faithfulness score ({llama_result.faithfulness_score:.2f}) - well-grounded in context"
            )

        if llama_result.relevancy_passing:
            strengths.append(
                f"High relevancy score ({llama_result.relevancy_score:.2f}) - directly addresses the question"
            )

        if factual_result.accuracy >= 0.9:
            strengths.append(
                f"High factual accuracy ({factual_result.accuracy:.1%}) - contains expected information"
            )

        if not factual_result.false_information and not factual_result.required_info_missing:
            strengths.append("Complete and accurate response with no false information")

        return issues, strengths

    def create_evaluation_summary(
        self, results: List[TestResult], persona_username: str
    ) -> EvaluationSummary:
        """Create summary of evaluation results"""

        if not results:
            return EvaluationSummary(
                persona_username=persona_username,
                timestamp=datetime.now().isoformat(),
                total_tests=0,
                tests_passed=0,
                tests_failed=0,
                overall_score=0.0,
                avg_faithfulness=0.0,
                avg_relevancy=0.0,
                avg_factual_accuracy=0.0,
                category_scores={},
                category_pass_rates={},
                common_failure_reasons=[],
                failing_categories=[],
                total_evaluation_time=0.0,
            )

        # Basic stats
        total_tests = len(results)
        tests_passed = sum(1 for r in results if r.passed)
        tests_failed = total_tests - tests_passed

        # Average scores
        avg_faithfulness = sum(r.llama_result.faithfulness_score for r in results) / total_tests
        avg_relevancy = sum(r.llama_result.relevancy_score for r in results) / total_tests
        avg_factual_accuracy = sum(r.factual_result.accuracy for r in results) / total_tests
        overall_score = sum(r.overall_score for r in results) / total_tests

        # Category breakdown
        categories = {}
        for result in results:
            category = result.category
            if category not in categories:
                categories[category] = []
            categories[category].append(result)

        category_scores = {}
        category_pass_rates = {}
        for category, cat_results in categories.items():
            category_scores[category] = sum(r.overall_score for r in cat_results) / len(cat_results)
            category_pass_rates[category] = sum(1 for r in cat_results if r.passed) / len(
                cat_results
            )

        # Failure analysis
        failing_results = [r for r in results if not r.passed]
        failing_categories = list(set(r.category for r in failing_results))

        # Common failure reasons
        all_issues = []
        for result in failing_results:
            all_issues.extend(result.issues)

        # Count issue types
        issue_counts = {}
        for issue in all_issues:
            # Extract the main issue type
            if "faithfulness" in issue.lower():
                issue_type = "Low faithfulness"
            elif "relevancy" in issue.lower():
                issue_type = "Low relevancy"
            elif "missing" in issue.lower() and "facts" in issue.lower():
                issue_type = "Missing facts"
            elif "false information" in issue.lower():
                issue_type = "False information"
            elif "required information" in issue.lower():
                issue_type = "Missing required info"
            else:
                issue_type = "Other"

            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        # Sort by frequency
        common_failure_reasons = [
            f"{issue_type} ({count} cases)"
            for issue_type, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        # Total evaluation time
        total_evaluation_time = sum(r.evaluation_time for r in results)

        return EvaluationSummary(
            persona_username=persona_username,
            timestamp=datetime.now().isoformat(),
            total_tests=total_tests,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            overall_score=overall_score,
            avg_faithfulness=avg_faithfulness,
            avg_relevancy=avg_relevancy,
            avg_factual_accuracy=avg_factual_accuracy,
            category_scores=category_scores,
            category_pass_rates=category_pass_rates,
            common_failure_reasons=common_failure_reasons[:5],  # Top 5
            failing_categories=failing_categories,
            total_evaluation_time=total_evaluation_time,
        )
