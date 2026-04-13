# Standard library imports
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

# LlamaIndex evaluation framework imports
# These provide industry-standard evaluation metrics for RAG systems
from llama_index.core.evaluation import (
    FaithfulnessEvaluator,  # Measures if response is supported by context
)
from llama_index.core.evaluation import (
    RelevancyEvaluator,  # Measures if response answers the question
)
from llama_index.llms.openai import OpenAI

# Internal configuration
from evaluations.config.settings import evaluation_settings

# Configure logger for LlamaIndex evaluation
logger = logging.getLogger(__name__)


@dataclass
class LlamaEvalResult:
    """
    Structured result container for LlamaIndex evaluation metrics.

    This dataclass encapsulates the results from both faithfulness and relevancy
    evaluations, providing both numerical scores and qualitative feedback.
    Used to maintain consistency in evaluation result handling and enable
    easy aggregation of results across multiple test cases.

    Attributes:
        faithfulness_score (float): Score 0.0-1.0 measuring if response is supported by context
        relevancy_score (float): Score 0.0-1.0 measuring if response answers the question
        faithfulness_feedback (str): Qualitative feedback explaining faithfulness score
        relevancy_feedback (str): Qualitative feedback explaining relevancy score
        faithfulness_passing (bool): Whether faithfulness meets minimum threshold
        relevancy_passing (bool): Whether relevancy meets minimum threshold
        overall_passing (bool): Whether both metrics pass their thresholds
    """

    faithfulness_score: float  # 0.0-1.0: Context support score
    relevancy_score: float  # 0.0-1.0: Question answering score
    faithfulness_feedback: str  # Qualitative faithfulness explanation
    relevancy_feedback: str  # Qualitative relevancy explanation
    faithfulness_passing: bool  # Meets faithfulness threshold
    relevancy_passing: bool  # Meets relevancy threshold
    overall_passing: bool  # Both metrics pass


class LlamaIndexEvaluator:
    """
    Comprehensive evaluator using LlamaIndex's industry-standard evaluation metrics.

    This evaluator implements two critical dimensions of RAG system evaluation:

    1. **Faithfulness**: Measures whether the AI response is grounded in and supported
       by the retrieved context chunks. Helps detect hallucination and ensures responses
       don't contain information not present in the knowledge base.

    2. **Relevancy**: Measures whether the AI response actually answers the posed question.
       A response can be factually correct but irrelevant if it doesn't address what
       was asked.

    Key Features:
    - Async evaluation for performance with concurrent test cases
    - Configurable confidence thresholds for pass/fail determination
    - Robust error handling with graceful degradation
    - Detailed feedback generation for debugging and improvement
    - Batch processing capabilities with rate limiting
    - Integration with OpenAI models for evaluation consistency

    The evaluator uses the same LLM model as configured in evaluation settings
    to ensure consistency between response generation and evaluation.
    """

    def __init__(self):
        """
        Initialize the LlamaIndex evaluator with configured LLM and thresholds.

        Sets up the evaluation infrastructure including:
        - OpenAI LLM client with evaluation-specific settings
        - Faithfulness and relevancy evaluator instances
        - Pass/fail thresholds from configuration
        - Comprehensive logging for monitoring
        """
        # Configure LLM for evaluation with optimized settings
        # Using evaluation-specific model and temperature for consistent results
        self.llm = OpenAI(
            model=evaluation_settings.eval_model,
            temperature=evaluation_settings.eval_temperature,  # Low temp for consistent evaluation
            timeout=60.0,  # Extended timeout for complex evaluations
            max_retries=3,  # Retry logic for reliability
        )

        # Initialize LlamaIndex evaluators with configured LLM
        # Both evaluators use the same LLM for consistency
        self.faithfulness_evaluator = FaithfulnessEvaluator(llm=self.llm)
        self.relevancy_evaluator = RelevancyEvaluator(llm=self.llm)

        # Load pass/fail thresholds from configuration
        # These determine when an evaluation is considered successful
        self.faithfulness_threshold = evaluation_settings.faithfulness_threshold
        self.relevancy_threshold = evaluation_settings.relevancy_threshold

        # Log initialization for monitoring and debugging
        logger.info("LlamaIndex evaluator initialized successfully")
        logger.info(f"Faithfulness threshold: {self.faithfulness_threshold}")
        logger.info(f"Relevancy threshold: {self.relevancy_threshold}")
        logger.info(f"Using model: {evaluation_settings.eval_model}")

    async def evaluate_response(
        self, query: str, response: str, contexts: List[str]
    ) -> LlamaEvalResult:
        """
        Evaluate a single AI response using LlamaIndex's faithfulness and relevancy metrics.

        This is the core evaluation method that processes a query-response pair
        against retrieved context to produce comprehensive evaluation scores.

        The evaluation process:
        1. Validates all required inputs are present and non-empty
        2. Runs faithfulness and relevancy evaluations concurrently for performance
        3. Handles evaluation failures gracefully with default scores
        4. Computes pass/fail status against configured thresholds
        5. Returns structured results with both scores and feedback

        Args:
            query (str): The original question asked by the user
                        Used to evaluate relevancy of the response
            response (str): The AI-generated response to evaluate
                          This is what gets scored for faithfulness and relevancy
            contexts (List[str]): List of retrieved context chunks used for generation
                                 These serve as the ground truth for faithfulness evaluation

        Returns:
            LlamaEvalResult: Comprehensive evaluation results containing:
                - Individual scores for faithfulness and relevancy (0.0-1.0)
                - Detailed feedback explaining each score
                - Pass/fail status for each metric based on thresholds
                - Overall pass status (both metrics must pass)

        Raises:
            ValueError: If required inputs (query, response, contexts) are missing or empty
        """
        try:
            # Comprehensive input validation to ensure evaluation quality
            # Empty or whitespace-only inputs would produce meaningless evaluations

            if not query or not query.strip():
                logger.error("Empty or whitespace-only query provided for evaluation")
                raise ValueError("query must be a non-empty string")

            if not response or not response.strip():
                logger.error("Empty or whitespace-only response provided for evaluation")
                raise ValueError("response must be a non-empty string")

            if not contexts:
                logger.error("Empty contexts list provided for evaluation")
                raise ValueError("contexts must be a non-empty list of strings")

            # Additional validation: ensure contexts contain meaningful content
            meaningful_contexts = [ctx for ctx in contexts if ctx and ctx.strip()]
            if not meaningful_contexts:
                logger.error("No meaningful content found in contexts")
                raise ValueError("contexts must contain at least one non-empty string")

            # Log evaluation details for debugging and monitoring
            logger.debug(f"Starting evaluation for query: {query[:50]}...")
            logger.debug(f"Response length: {len(response)} chars")
            logger.debug(f"Context count: {len(contexts)} chunks")
            logger.debug(f"Meaningful context count: {len(meaningful_contexts)} chunks")

            # Run both evaluations concurrently for performance optimization
            # This reduces total evaluation time by ~50% compared to sequential execution
            faithfulness_task = self._evaluate_faithfulness(query, response, meaningful_contexts)
            relevancy_task = self._evaluate_relevancy(query, response, meaningful_contexts)

            # Use asyncio.gather with exception handling to ensure robust evaluation
            # return_exceptions=True prevents one failure from canceling the other
            faithfulness_result, relevancy_result = await asyncio.gather(
                faithfulness_task,
                relevancy_task,
                return_exceptions=True,  # Critical for handling partial failures
            )

            # Process faithfulness evaluation result with error handling
            # Graceful degradation ensures partial results even if one evaluator fails
            if isinstance(faithfulness_result, Exception):
                logger.error(f"Faithfulness evaluation failed: {faithfulness_result}")
                # Assign minimum score for failed evaluation
                faithfulness_score = 0.0
                faithfulness_feedback = f"Evaluation error: {str(faithfulness_result)}"
            else:
                # Extract score and feedback from successful evaluation
                faithfulness_score = faithfulness_result.score
                faithfulness_feedback = faithfulness_result.feedback or "No feedback provided"

            # Process relevancy evaluation result with error handling
            if isinstance(relevancy_result, Exception):
                logger.error(f"Relevancy evaluation failed: {relevancy_result}")
                # Assign minimum score for failed evaluation
                relevancy_score = 0.0
                relevancy_feedback = f"Evaluation error: {str(relevancy_result)}"
            else:
                # Extract score and feedback from successful evaluation
                relevancy_score = relevancy_result.score
                relevancy_feedback = relevancy_result.feedback or "No feedback provided"

            # Compute pass/fail status based on configured thresholds
            # Both metrics must pass for overall success
            faithfulness_passing = faithfulness_score >= self.faithfulness_threshold
            relevancy_passing = relevancy_score >= self.relevancy_threshold
            overall_passing = faithfulness_passing and relevancy_passing  # Requires both to pass

            # Create structured result object with all evaluation data
            result = LlamaEvalResult(
                faithfulness_score=faithfulness_score,
                relevancy_score=relevancy_score,
                faithfulness_feedback=faithfulness_feedback,
                relevancy_feedback=relevancy_feedback,
                faithfulness_passing=faithfulness_passing,
                relevancy_passing=relevancy_passing,
                overall_passing=overall_passing,
            )

            # Log detailed evaluation results for monitoring and debugging
            logger.debug(
                f"Evaluation completed successfully: "
                f"faithfulness={faithfulness_score:.2f} ({'PASS' if faithfulness_passing else 'FAIL'}), "
                f"relevancy={relevancy_score:.2f} ({'PASS' if relevancy_passing else 'FAIL'}), "
                f"overall={'PASS' if overall_passing else 'FAIL'}"
            )

            return result

        except Exception as e:
            logger.error(f"Critical error in LlamaIndex evaluation: {e}")
            logger.error(f"Query: {query[:100]}...")
            logger.error(f"Response: {response[:100]}...")
            logger.error(f"Context count: {len(contexts) if contexts else 0}")

            # Return failed evaluation with detailed error information
            # This ensures the evaluation pipeline continues even with individual failures
            return LlamaEvalResult(
                faithfulness_score=0.0,
                relevancy_score=0.0,
                faithfulness_feedback=f"Critical evaluation error: {str(e)}",
                relevancy_feedback=f"Critical evaluation error: {str(e)}",
                faithfulness_passing=False,
                relevancy_passing=False,
                overall_passing=False,
            )

    async def _evaluate_faithfulness(self, query: str, response: str, contexts: List[str]):
        """
        Evaluate faithfulness using LlamaIndex's FaithfulnessEvaluator.

        Faithfulness measures whether the AI response is grounded in and supported
        by the retrieved context chunks. This is critical for detecting hallucination
        and ensuring responses don't contain fabricated information.

        The evaluation works by:
        1. Breaking down the response into individual claims
        2. Checking each claim against the provided contexts
        3. Scoring based on how well the contexts support each claim
        4. Providing detailed feedback on which parts are/aren't supported

        Args:
            query (str): Original user question (used for context)
            response (str): AI-generated response to evaluate
            contexts (List[str]): Retrieved context chunks that should support the response

        Returns:
            EvaluationResult: LlamaIndex result object with score and feedback

        Raises:
            Exception: Re-raises any evaluation errors for handling by parent method
        """
        try:
            # Log evaluation attempt for debugging
            logger.debug("Starting faithfulness evaluation")
            logger.debug(f"Query: {query[:50]}...")
            logger.debug(f"Response: {response[:50]}...")
            logger.debug(f"Context chunks: {len(contexts)}")

            # Call LlamaIndex's async faithfulness evaluator
            # Note: contexts parameter is required (learned from source code analysis)
            result = await self.faithfulness_evaluator.aevaluate(
                query=query,  # Original question for context
                response=response,  # AI response to evaluate
                contexts=contexts,  # Ground truth contexts
            )

            # Log successful evaluation result
            logger.debug(
                f"Faithfulness evaluation completed: score={result.score}, passing={result.passing}"
            )
            return result

        except Exception as e:
            logger.error(f"Faithfulness evaluation failed: {e}")
            logger.error("This may indicate issues with LlamaIndex setup or API connectivity")
            raise  # Re-raise for parent method error handling

    async def _evaluate_relevancy(self, query: str, response: str, contexts: List[str]):
        """
        Evaluate relevancy using LlamaIndex's RelevancyEvaluator.

        Relevancy measures whether the AI response actually answers the question
        that was asked. A response can be factually correct and well-grounded
        but still irrelevant if it doesn't address the specific question.

        The evaluation considers:
        1. Does the response address the main question asked?
        2. Is the response on-topic and focused?
        3. Does it provide the type of information requested?
        4. Is it helpful for the user's specific query?

        Args:
            query (str): Original user question to evaluate relevancy against
            response (str): AI-generated response to evaluate
            contexts (List[str]): Context chunks (required by RelevancyEvaluator)

        Returns:
            EvaluationResult: LlamaIndex result object with score and feedback

        Raises:
            Exception: Re-raises any evaluation errors for handling by parent method
        """
        try:
            # Log evaluation attempt for debugging
            logger.debug("Starting relevancy evaluation")
            logger.debug(f"Query: {query[:50]}...")
            logger.debug(f"Response: {response[:50]}...")
            logger.debug(f"Context chunks: {len(contexts)}")

            # Call LlamaIndex's async relevancy evaluator
            # Note: contexts parameter is required even for relevancy (learned from debugging)
            result = await self.relevancy_evaluator.aevaluate(
                query=query,  # Question to check relevancy against
                response=response,  # AI response to evaluate
                contexts=contexts,  # Required by evaluator implementation
            )

            # Log successful evaluation result
            logger.debug(
                f"Relevancy evaluation completed: score={result.score}, passing={result.passing}"
            )
            return result

        except Exception as e:
            logger.error(f"Relevancy evaluation failed: {e}")
            logger.error("This may indicate issues with LlamaIndex setup or API connectivity")
            raise  # Re-raise for parent method error handling

    async def batch_evaluate(self, evaluations: List[Dict[str, Any]]) -> List[LlamaEvalResult]:
        """
        Evaluate multiple responses in batch for efficiency

        Args:
            evaluations: List of dicts with 'query', 'response', 'contexts' keys

        Returns:
            List of LlamaEvalResult objects
        """
        logger.info(f"Starting batch evaluation of {len(evaluations)} responses")

        tasks = []
        for eval_data in evaluations:
            task = self.evaluate_response(
                query=eval_data["query"],
                response=eval_data["response"],
                contexts=eval_data["contexts"],
            )
            tasks.append(task)

        # Run all evaluations concurrently with some rate limiting
        batch_size = 5  # Limit concurrent evaluations
        results = []

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)

            # Handle any exceptions in batch
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch evaluation error: {result}")
                    results.append(
                        LlamaEvalResult(
                            faithfulness_score=0.0,
                            relevancy_score=0.0,
                            faithfulness_feedback=f"Batch error: {str(result)}",
                            relevancy_feedback=f"Batch error: {str(result)}",
                            faithfulness_passing=False,
                            relevancy_passing=False,
                            overall_passing=False,
                        )
                    )
                else:
                    results.append(result)

            # Small delay between batches to avoid rate limits
            if i + batch_size < len(tasks):
                await asyncio.sleep(1)

        logger.info(f"Completed batch evaluation: {len(results)} results")
        return results
