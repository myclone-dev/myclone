"""
Utility functions for Langfuse prompt operations
"""

import asyncio
import json
import logging
import math
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.langfuse_observability_service import LangfuseObservabilityService
from app.services.openai_service import OpenAIModelService
from shared.config import settings
from shared.database.models.database import Persona, PersonaPrompt
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.utils.langfuse_utils import get_langfuse_client

logger = logging.getLogger(__name__)


async def _fetch_rag_context(user_id: UUID, persona_id: UUID, query: str, db: AsyncSession) -> str:
    """
    Helper function to fetch RAG context for a query.

    Integrates with your existing RAG system to retrieve relevant context.
    """
    try:
        from shared.rag.rag_singleton import get_rag_system

        # Get RAG system (supports both sync and async factories)
        rag_system = get_rag_system()
        if asyncio.iscoroutine(rag_system):
            rag_system = await rag_system  # type: ignore

        # Retrieve context using the correct method
        retrieval_result = await rag_system.retrieve_context(
            persona_id=persona_id,
            query=query,
            top_k=5,
            similarity_threshold=0.3,
            include_patterns=False,
        )

        # Format context from chunks
        chunks = retrieval_result.get("chunks", [])
        if chunks:
            context_parts = []
            for chunk in chunks[:5]:
                content = chunk.get("content", "").strip()
                if content:
                    context_parts.append(f"- {content[:200]}...")

            if context_parts:
                return "\n\n# Retrieved Context:\n" + "\n".join(context_parts)

        return ""

    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user_id),
                "persona_id": str(persona_id),
                "query_preview": query[:120],
            },
            tags={
                "component": "langfuse_utils",
                "operation": "fetch_rag_context",
                "severity": "low",
                "user_facing": "false",
            },
        )
        logger.warning(f"Failed to fetch RAG context: {e}")
        return ""


async def _compile_prompt_with_rag(
    user_id: UUID,
    persona_id: UUID,
    prompt_name: str,
    version: Optional[int],
    user_query: str,
    include_rag: bool,
    rag_query: Optional[str],
    db: AsyncSession,
) -> tuple[str, Dict[str, Any], int, Dict[str, Any]]:
    """
    Helper to compile prompt with optional RAG context.

    Returns: (compiled_prompt, config, version, variables_used)
    """
    # 1. Get Langfuse prompt template
    client = get_langfuse_client()

    if version:
        langfuse_prompt = client.get_prompt(name=prompt_name, version=version)
    else:
        langfuse_prompt = client.get_prompt(name=prompt_name)

    if not langfuse_prompt:
        raise HTTPException(status_code=404, detail=f"Prompt template '{prompt_name}' not found")

    # 2. Load persona data
    try:
        persona_stmt = select(Persona).where(
            and_(Persona.id == persona_id, Persona.user_id == user_id)
        )
        persona_result = await db.execute(persona_stmt)
        persona = persona_result.scalar_one_or_none()

        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")

        prompt_stmt = select(PersonaPrompt).where(
            and_(PersonaPrompt.persona_id == persona_id, PersonaPrompt.is_active == True)
        )
        prompt_result = await db.execute(prompt_stmt)
        persona_prompt = prompt_result.scalar_one_or_none()

        if not persona_prompt:
            raise HTTPException(status_code=404, detail="No active persona prompt found")

        # LinkedIn repository removed; role/company come from user/persona fields only
        role, company = None, None

        # 3. Get RAG context if requested
        rag_context = ""
        if include_rag:
            rag_context = await _fetch_rag_context(
                user_id=user_id, persona_id=persona_id, query=rag_query or user_query, db=db
            )

        # 4. Parse response_structure
        response_structure = {}
        if persona_prompt.response_structure:
            try:
                if isinstance(persona_prompt.response_structure, str):
                    parsed = json.loads(persona_prompt.response_structure)
                else:
                    parsed = persona_prompt.response_structure

                if isinstance(parsed, dict):
                    response_structure = parsed
            except Exception as parse_e:
                capture_exception_with_context(
                    parse_e,
                    extra={"persona_id": str(persona_id)},
                    tags={
                        "component": "langfuse_utils",
                        "operation": "parse_response_structure",
                        "severity": "low",
                        "user_facing": "false",
                    },
                )
                logger.warning(f"Failed to parse response_structure: {parse_e}")

        # 5. Build variables
        variables = {
            "persona_name": persona.name or "Expert",
            "role": role or "Professional",
            "company": company or "Organization",
            "introduction": persona_prompt.introduction or "",
            "area_of_expertise": persona_prompt.area_of_expertise or "General expertise",
            "thinking_style": persona_prompt.thinking_style or "Thoughtful and analytical",
            "chat_objective": persona_prompt.chat_objective or "Provide helpful guidance",
            "conversation_flow": persona_prompt.conversation_flow or "",
            "objective_response": persona_prompt.objective_response or "",
            "example_responses": persona_prompt.example_responses or "",
            "target_audience": persona_prompt.target_audience or "General audience",
            "user_query": user_query,
            "rag_context": rag_context,
            "response_length": (
                response_structure.get("response_length", "intelligent")
                if isinstance(response_structure, dict)
                else "intelligent"
            ),
            "creativity": (
                response_structure.get("creativity", "adaptive")
                if isinstance(response_structure, dict)
                else "adaptive"
            ),
            "tone": (
                response_structure.get("tone", "professional")
                if isinstance(response_structure, dict)
                else "professional"
            ),
        }

        # 6. Compile
        compiled = langfuse_prompt.compile(**variables)

        return compiled, langfuse_prompt.config or {}, langfuse_prompt.version, variables

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "prompt_name": prompt_name,
                "version": version,
                "user_id": str(user_id),
                "persona_id": str(persona_id),
            },
            tags={
                "component": "langfuse_utils",
                "operation": "compile_prompt_with_rag",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"❌ Failed to compile prompt with RAG: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to compile prompt: {str(e)}")


# -------------------- Helpers (moved) -------------------- #


async def _run_llm_judge_evaluator(
    question: str,
    answer: str,
    contexts: List[str],
    ground_truth: Optional[str],
    metric_name: str,
) -> float:
    try:
        contexts_text = "\n\n".join(
            [f"Context {i+1}: {ctx[:500]}" for i, ctx in enumerate(contexts[:3])]
        )
        if metric_name == "faithfulness":
            eval_prompt = f"""Evaluate if the answer is faithful to the provided contexts.
Score 1.0 if the answer is fully grounded in contexts, 0.0 if completely unsupported.

Question: {question}

Contexts:
{contexts_text}

Answer: {answer}

Provide ONLY a score between 0.0 and 1.0:"""
        elif metric_name == "answer_relevancy":
            eval_prompt = f"""Evaluate how relevant the answer is to the question.
Score 1.0 if perfectly relevant, 0.0 if completely irrelevant.

Question: {question}

Answer: {answer}

Provide ONLY a score between 0.0 and 1.0:"""
        elif metric_name == "correctness" and ground_truth:
            eval_prompt = f"""Evaluate the correctness of the answer against the ground truth.
Score 1.0 if fully correct, 0.0 if completely incorrect.

Question: {question}

Ground Truth: {ground_truth}

Answer: {answer}

Provide ONLY a score between 0.0 and 1.0:"""
        elif metric_name == "semantic_similarity" and ground_truth:
            eval_prompt = f"""Evaluate semantic similarity between the answer and ground truth.
Score 1.0 if semantically identical, 0.0 if completely different meaning.

Ground Truth: {ground_truth}

Answer: {answer}

Provide ONLY a score between 0.0 and 1.0:"""
        elif metric_name == "context_relevancy":
            eval_prompt = f"""Evaluate how relevant the contexts are to the question.
Score 1.0 if perfectly relevant, 0.0 if completely irrelevant.

Question: {question}

Contexts:
{contexts_text}

Provide ONLY a score between 0.0 and 1.0:"""
        elif metric_name == "retrieval_precision":
            gt_text = f"\n\nGround Truth: {ground_truth}" if ground_truth else ""
            eval_prompt = f"""Evaluate the precision of retrieved contexts.
Score 1.0 if contexts are highly precise and relevant, 0.0 if imprecise or irrelevant.

Question: {question}{gt_text}

Contexts:
{contexts_text}

Provide ONLY a score between 0.0 and 1.0:"""
        else:
            return 0.5

        service = OpenAIModelService(api_key=settings.openai_api_key)
        service.set_system_prompt(
            "You are an expert evaluator. Respond with ONLY a numeric score between 0.0 and 1.0."
        )
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: service.generate_response_raw(
                eval_prompt,
                temperature=0.0,
                max_tokens=10,
            ),
        )
        output = getattr(response, "output_text", "").strip()
        try:
            score = float(output)
            return _sanitize_float(max(0.0, min(1.0, score)))
        except ValueError:
            logger.warning(f"LLM judge returned non-numeric: {output}")
            return 0.5
    except Exception as e:
        logger.warning(f"LLM judge evaluation failed for {metric_name}: {e}")
        return 0.5


async def _run_evaluator(
    evaluator,
    question: str,
    answer: Optional[str],
    contexts: List[str],
    ground_truth: Optional[str],
):
    try:
        kwargs = {
            "query": question,
            "response": answer if answer is not None else "",
            "contexts": contexts,
        }
        if ground_truth:
            kwargs["reference"] = ground_truth
        if hasattr(evaluator, "a_evaluate") and asyncio.iscoroutinefunction(
            getattr(evaluator, "a_evaluate")
        ):
            res = await evaluator.a_evaluate(**kwargs)  # type: ignore
        elif hasattr(evaluator, "evaluate"):
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: evaluator.evaluate(**kwargs))  # type: ignore
        else:
            return 0.0
        if hasattr(res, "score"):
            return _sanitize_float(res.score)  # type: ignore
        if isinstance(res, dict) and "score" in res:
            return _sanitize_float(res["score"])  # type: ignore
        return _sanitize_float(res)  # type: ignore
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Evaluator run failed: {e}")
        return 0.0


def _sanitize_float(val: Any) -> float:
    try:
        f = float(val)
    except Exception:
        return 0.0
    if not math.isfinite(f):
        return 0.0
    return f


async def _log_query_evaluation_trace(
    langfuse_service: LangfuseObservabilityService,
    *,
    trace_name: str,
    user_id: str,
    persona_id: str,
    persona_name: str,
    evaluator_type: str,
    query_index: int,
    question: str,
    ground_truth: Optional[str],
    response: str,
    retrieved_context: str,
    num_contexts: int,
    metrics: Dict[str, float],
    processing_time_sec: float,
    tags: Optional[List[str]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Create a Langfuse query span with standardized inputs/outputs and metric scores."""
    if not langfuse_service:
        return

    base_tags = ["eval", "prompt_evaluation", trace_name]
    if tags:
        base_tags.extend(tags)
    base_tags.append(f"evaluator:{evaluator_type}")

    metadata = {
        "persona_id": persona_id,
        "persona_name": persona_name,
        "evaluation_type": trace_name,
        "evaluator": evaluator_type,
        "query_index": query_index,
        "num_contexts": num_contexts,
        "processing_time_sec": processing_time_sec,
        "tags": list(dict.fromkeys(base_tags)),
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    try:
        query_span = langfuse_service.create_query_span(
            query_index=query_index,
            query=question,
            ground_truth=ground_truth,
            response=response,
            retrieved_context=retrieved_context,
            num_contexts=num_contexts,
            metadata=metadata,
        )
        if not query_span:
            return

        for metric_name, metric_value in metrics.items():
            try:
                query_span.score(
                    name=metric_name,
                    value=metric_value,
                    data_type="NUMERIC",
                    comment=f"Query {query_index}: {metric_name}",
                )
            except Exception as score_err:
                logger.warning(f"⚠️ Failed to log score {metric_name}: {score_err}")

        query_span.end()
    except Exception as e:
        logger.warning(f"⚠️ Failed to create Langfuse span for query {query_index}: {e}")


# -------------------- Endpoints (moved) -------------------- #
