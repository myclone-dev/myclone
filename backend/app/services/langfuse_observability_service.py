"""
Langfuse Observability Service

This service provides a clean abstraction for tracking evaluations and metrics in Langfuse.
It decouples Langfuse-specific logic from core business operations.

Uses Langfuse OpenTelemetry-based SDK (start_span API).
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LangfuseObservabilityService:
    """Service for tracking evaluations and metrics in Langfuse"""

    def __init__(self):
        """Initialize the service with Langfuse client"""
        from shared.utils.langfuse_utils import get_langfuse_client

        self.client = get_langfuse_client()
        self._root_span = None

    async def track_evaluation(
        self,
        name: str,
        user_id: str,
        persona_id: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Track evaluation in Langfuse, create root span and return trace_id

        Args:
            name: Name/identifier for the evaluation
            user_id: User identifier
            persona_id: Persona identifier
            input_data: Input data for the evaluation
            output_data: Output/results from the evaluation
            metadata: Additional metadata

        Returns:
            Trace ID if successful, None otherwise
        """
        if not self.client:
            logger.warning("Langfuse client not available, skipping tracking")
            return None

        try:
            # Create root span for the evaluation
            # Update trace-level attributes
            combined_metadata = metadata or {}
            combined_metadata.update(
                {
                    "persona_id": persona_id,
                    "user_id": user_id,
                }
            )

            self._root_span = self.client.start_span(
                name=name,
                input=input_data,
                output=output_data,
                metadata=combined_metadata,
            )

            # Update trace attributes
            self._root_span.update_trace(
                user_id=user_id,
                session_id=persona_id,
                metadata=combined_metadata,
                tags=combined_metadata.get("tags", []),
            )

            trace_id = self._root_span.trace_id
            logger.info(f"✅ Created Langfuse trace: {trace_id}")
            return trace_id

        except Exception as e:
            logger.warning(f"⚠️ Failed to create Langfuse trace: {e}")
            return None

    def create_query_span(
        self,
        query_index: int,
        query: str,
        ground_truth: Optional[str],
        response: str,
        retrieved_context: str,
        num_contexts: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """
        Create a child span for a single query evaluation

        Args:
            query_index: Index of query in evaluation batch
            query: User query
            ground_truth: Ground truth response (if available)
            response: Generated response
            retrieved_context: Retrieved context chunks (combined)
            num_contexts: Number of context chunks retrieved
            metadata: Additional metadata

        Returns:
            Span object if successful, None otherwise
        """
        if not self.client:
            return None

        try:
            # Create child span
            combined_metadata = metadata or {}
            combined_metadata.update(
                {
                    "query_index": query_index,
                    "num_contexts": num_contexts,
                }
            )

            query_span = self.client.start_span(
                name=f"eval_query_{query_index}",
                input={
                    "query": query,
                    "ground_truth": ground_truth or "",
                },
                output={
                    "response": response,
                    "retrieved_context": retrieved_context[:2000],  # Truncate for Langfuse
                    "num_contexts": num_contexts,
                },
                metadata=combined_metadata,
            )

            return query_span

        except Exception as e:
            logger.warning(f"⚠️ Failed to create Langfuse span for query {query_index}: {e}")
            return None

    def _get_metric_tags(self, metric_name: str, evaluator_type: Optional[str] = None) -> List[str]:
        """
        Generate appropriate tags for a metric based on its name and evaluator type

        Args:
            metric_name: Name of the metric (e.g., 'faithfulness', 'context_relevancy')
            evaluator_type: Type of evaluator used ('llm_judge', 'llamaindex', 'heuristic', etc.)

        Returns:
            List of tags for categorization
        """
        tags = ["prompt_evaluation"]

        # Add evaluator type tag
        if evaluator_type:
            tags.append(f"evaluator:{evaluator_type}")

        # Categorize by metric type
        generation_metrics = [
            "faithfulness",
            "answer_relevancy",
            "correctness",
            "semantic_similarity",
        ]
        retrieval_metrics = ["context_relevancy", "retrieval_precision", "retrieval_recall"]
        quality_metrics = ["helpfulness", "accuracy", "clarity", "completeness", "actionability"]
        performance_metrics = ["latency_ms", "tokens_per_second", "processing_time"]

        if metric_name in generation_metrics:
            tags.extend(["generation", "rag"])
        elif metric_name in retrieval_metrics:
            tags.extend(["retrieval", "rag"])
        elif metric_name in quality_metrics:
            tags.append("quality")
        elif metric_name in performance_metrics:
            tags.append("performance")

        # Add specific metric category
        if "relevancy" in metric_name or "relevance" in metric_name:
            tags.append("relevance")
        if "precision" in metric_name or "accuracy" in metric_name:
            tags.append("accuracy")
        if "faithfulness" in metric_name or "grounding" in metric_name:
            tags.append("hallucination_detection")

        return tags

    async def log_multiple_scores(
        self,
        trace_id: str,
        scores: Dict[str, float],
        observation_id: Optional[str] = None,
        comment_prefix: Optional[str] = None,
        evaluator_type: Optional[str] = None,
    ) -> int:
        """
        Log multiple metric scores to Langfuse trace (using root span)

        Args:
            trace_id: Trace ID to attach scores to
            scores: Dictionary of metric name to score value
            observation_id: Optional observation/span ID (not used, kept for compatibility)
            comment_prefix: Optional prefix for comments
            evaluator_type: Type of evaluator used ('llm_judge', 'llamaindex', 'heuristic')

        Returns:
            Number of successfully logged scores
        """
        if not self.client or not self._root_span:
            return 0

        success_count = 0
        for name, value in scores.items():
            comment = f"{comment_prefix}: {name}" if comment_prefix else f"{name} score"

            try:
                self._root_span.score_trace(
                    name=name,
                    value=value,
                    data_type="NUMERIC",
                    comment=comment,
                )
                success_count += 1
            except Exception as e:
                logger.warning(f"⚠️ Failed to log score {name}: {e}")

        return success_count

    async def update_trace(
        self,
        trace_id: str,
        output: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update trace with final output and metadata

        Args:
            trace_id: Trace ID to update
            output: Final output data
            metadata: Final metadata

        Returns:
            True if successful, False otherwise
        """
        if not self.client or not self._root_span:
            return False

        try:
            # Update the root span
            if output:
                self._root_span.update(output=output)
            if metadata:
                self._root_span.update(metadata=metadata)
            return True

        except Exception as e:
            logger.warning(f"⚠️ Failed to update Langfuse trace: {e}")
            return False

    def flush(self) -> None:
        """Flush all pending data to Langfuse and end root span"""
        if self.client:
            try:
                # End the root span if it exists
                if self._root_span:
                    self._root_span.end()
                    self._root_span = None
                self.client.flush()
            except Exception as e:
                logger.warning(f"⚠️ Failed to flush Langfuse client: {e}")

    async def track_retrieval_evaluation(
        self,
        name: str,
        user_id: str,
        persona_id: str,
        queries: List[Dict[str, Any]],
        overall_metrics: Dict[str, float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Track retrieval evaluation with multiple queries

        Args:
            name: Evaluation name
            user_id: User identifier
            persona_id: Persona identifier
            queries: List of query results
            overall_metrics: Overall aggregated metrics
            metadata: Additional metadata

        Returns:
            Trace ID if successful, None otherwise
        """
        if not self.client:
            return None

        try:
            trace = self.client.trace(
                name=name,
                user_id=user_id,
                input={"num_queries": len(queries)},
                output={"overall_metrics": overall_metrics},
                metadata=metadata or {},
            )

            trace_id = trace.id if hasattr(trace, "id") else None

            # Log each query as a span
            for idx, query_data in enumerate(queries):
                await self.track_query_span(
                    trace_id=trace_id,
                    query_index=idx,
                    query=query_data.get("question", ""),
                    ground_truth=query_data.get("ground_truth"),
                    response="",  # Retrieval doesn't have response
                    scores=query_data.get("metrics", {}),
                    metadata={
                        "contexts_count": len(query_data.get("contexts", [])),
                        "processing_time_sec": query_data.get("processing_time_sec"),
                    },
                )

            # Log overall scores
            await self.log_multiple_scores(
                trace_id=trace_id, scores=overall_metrics, comment_prefix="Overall retrieval"
            )

            self.flush()
            logger.info(f"✅ Logged retrieval evaluation to Langfuse: {trace_id}")
            return trace_id

        except Exception as e:
            logger.warning(f"⚠️ Failed to track retrieval evaluation: {e}")
            return None
