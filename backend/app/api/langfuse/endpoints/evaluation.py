"""
A/B Testing and Evaluation endpoints for Langfuse prompts
"""

import logging
import time
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.langfuse.schemas import (
    ABTestRequest,
    ABTestResponse,
    GroundTruthEvalRequest,
    GroundTruthEvalResponse,
)
from app.api.langfuse.schemas.evaluation_schemas import (
    LlamaRAGEvalRequest,
    LlamaRAGEvalResult,
    LlamaRAGRetrievalEvalRequest,
    LlamaRAGRetrievalEvalResult,
)
from app.api.langfuse.utils import (
    _compile_prompt_with_rag,
    _log_query_evaluation_trace,
    _run_evaluator,
    _run_llm_judge_evaluator,
    _sanitize_float,
)
from app.services.langfuse_observability_service import LangfuseObservabilityService
from shared.config import settings
from shared.database.models.database import Persona, async_session_maker
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.rag.rag_singleton import get_rag_system

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Langfuse - Evaluation"])


async def get_db():
    """Database session dependency"""
    async with async_session_maker() as session:
        yield session


@router.post("/ab-test", response_model=ABTestResponse)
async def ab_test_prompts(request: ABTestRequest, db: AsyncSession = Depends(get_db)):
    """A/B test two different prompt templates or versions."""
    try:
        # Compile variant A
        compiled_a, config_a, version_a, vars_a = await _compile_prompt_with_rag(
            user_id=request.user_id,
            persona_id=request.persona_id,
            prompt_name=request.prompt_name_a,
            version=request.version_a,
            user_query=request.user_query,
            include_rag=request.include_rag_context,
            rag_query=request.rag_query,
            db=db,
        )

        # Compile variant B
        compiled_b, config_b, version_b, vars_b = await _compile_prompt_with_rag(
            user_id=request.user_id,
            persona_id=request.persona_id,
            prompt_name=request.prompt_name_b,
            version=request.version_b,
            user_query=request.user_query,
            include_rag=request.include_rag_context,
            rag_query=request.rag_query,
            db=db,
        )

        logger.info(
            f"🧪 A/B test: {request.prompt_name_a} v{version_a} vs "
            f"{request.prompt_name_b} v{version_b}"
        )

        return ABTestResponse(
            status="success",
            variant_a={
                "prompt_name": request.prompt_name_a,
                "version": version_a,
                "compiled_prompt": compiled_a,
                "config": config_a,
                "variables_used": vars_a,
                "rag_included": request.include_rag_context,
            },
            variant_b={
                "prompt_name": request.prompt_name_b,
                "version": version_b,
                "compiled_prompt": compiled_b,
                "config": config_b,
                "variables_used": vars_b,
                "rag_included": request.include_rag_context,
            },
            message=f"A/B test compiled: {request.prompt_name_a} v{version_a} vs {request.prompt_name_b} v{version_b}",
        )
    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(request.user_id),
                "persona_id": str(request.persona_id),
                "prompt_a": request.prompt_name_a,
                "prompt_b": request.prompt_name_b,
            },
            tags={
                "component": "langfuse_evaluation",
                "operation": "ab_test",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"❌ A/B test failed: {e}")
        raise HTTPException(status_code=500, detail=f"A/B test failed: {str(e)}")


@router.post("/ground-truth", response_model=GroundTruthEvalResponse)
async def evaluate_with_ground_truth(
    request: GroundTruthEvalRequest, db: AsyncSession = Depends(get_db)
):
    """Evaluate prompt against ground truth response."""
    try:
        # 1. Compile prompt
        compiled, config, version, variables = await _compile_prompt_with_rag(
            user_id=request.user_id,
            persona_id=request.persona_id,
            prompt_name=request.prompt_name,
            version=request.version,
            user_query=request.query,
            include_rag=request.include_rag_context,
            rag_query=request.rag_query,
            db=db,
        )

        # 2. Generate response
        import asyncio

        from app.services.openai_service import OpenAIModelService

        openai_service = OpenAIModelService(api_key=settings.openai_api_key)
        openai_service.set_system_prompt(compiled)
        openai_service.set_parameters(
            temperature=config.get("temperature", 0.7),
            max_tokens=config.get("max_tokens", 2000),
        )

        # Run synchronous method in executor
        loop = asyncio.get_event_loop()
        generated_response = await loop.run_in_executor(
            None, openai_service.get_response, request.query
        )

        # 3. Evaluate against ground truth using embeddings
        import numpy as np
        from openai import AsyncOpenAI

        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

        embeddings_response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=[generated_response, request.ground_truth_response],
        )

        gen_embedding = np.array(embeddings_response.data[0].embedding)
        gt_embedding = np.array(embeddings_response.data[1].embedding)

        # Cosine similarity
        similarity = np.dot(gen_embedding, gt_embedding) / (
            np.linalg.norm(gen_embedding) * np.linalg.norm(gt_embedding)
        )

        # 4. Calculate scores for each criterion
        scores = {}
        for criterion in request.evaluation_criteria:
            if criterion == "accuracy":
                scores[criterion] = float(similarity * 100)
            elif criterion == "relevance":
                scores[criterion] = float(similarity * 100)
            elif criterion == "completeness":
                length_ratio = len(generated_response) / max(len(request.ground_truth_response), 1)
                length_score = min(100, length_ratio * 100)
                scores[criterion] = float((similarity * 70 + length_score * 0.3))
            elif criterion == "clarity":
                sentences = generated_response.split(".")
                avg_sentence_length = sum(len(s.split()) for s in sentences) / max(
                    len(sentences), 1
                )
                clarity_score = max(0, 100 - (avg_sentence_length - 15) * 2)
                scores[criterion] = float(clarity_score)
            else:
                scores[criterion] = float(similarity * 100)

        overall_score = sum(scores.values()) / len(scores) if scores else 0

        # 5. Log to Langfuse with proper scores and tags
        langfuse_service = LangfuseObservabilityService()
        langfuse_trace_id = await langfuse_service.track_evaluation(
            name="ground-truth-eval",
            user_id=str(request.user_id),
            persona_id=str(request.persona_id),
            input_data={
                "query": request.query,
                "prompt_name": request.prompt_name,
                "version": version,
                "evaluation_criteria": request.evaluation_criteria,
                "ground_truth_present": bool(request.ground_truth_response),
            },
            output_data={},
            metadata={
                "persona_id": str(request.persona_id),
                "persona_name": str(request.persona_id),
                "prompt_name": request.prompt_name,
                "version": version,
                "evaluation_type": "ground_truth",
                "tags": ["eval", "prompt_evaluation", "ground_truth", "quality"],
            },
        )
        normalized_overall = overall_score / 100.0 if overall_score > 1 else overall_score

        if langfuse_trace_id:
            ground_truth_context = request.ground_truth_response or "(no ground truth provided)"
            try:
                query_span = langfuse_service.create_query_span(
                    query_index=1,
                    query=request.query,
                    ground_truth=request.ground_truth_response,
                    response=generated_response,
                    retrieved_context=ground_truth_context,
                    num_contexts=0,
                    metadata={
                        "prompt_name": request.prompt_name,
                        "version": version,
                        "evaluation_type": "ground_truth",
                        "tags": ["eval", "ground_truth", "quality"],
                    },
                )

                if query_span:
                    query_span.score(
                        name="ground_truth_similarity",
                        value=float(similarity),
                        data_type="NUMERIC",
                        comment="Cosine similarity with ground truth",
                    )

                    for criterion, score in scores.items():
                        normalized_score = score / 100.0 if score > 1 else score
                        query_span.score(
                            name=criterion,
                            value=normalized_score,
                            data_type="NUMERIC",
                            comment=f"Ground truth evaluation: {criterion}",
                        )

                    query_span.score(
                        name="overall_quality",
                        value=normalized_overall,
                        data_type="NUMERIC",
                        comment="Overall ground truth evaluation score",
                    )

                    query_span.end()

                await langfuse_service.log_multiple_scores(
                    trace_id=langfuse_trace_id,
                    scores={"overall_quality": normalized_overall},
                    comment_prefix="Ground truth overall",
                    evaluator_type="ground_truth",
                )

                await langfuse_service.update_trace(
                    trace_id=langfuse_trace_id,
                    output={
                        "status": "success",
                        "scores": scores,
                        "overall_score": overall_score,
                        "generated_response": generated_response[:500],
                        "ground_truth": request.ground_truth_response[:500],
                    },
                )

                langfuse_service.flush()
                logger.info(
                    f"✅ Logged ground truth evaluation scores to Langfuse trace: {langfuse_trace_id}"
                )
            except Exception as log_e:
                capture_exception_with_context(
                    log_e,
                    extra={
                        "prompt_name": request.prompt_name,
                        "persona_id": str(request.persona_id),
                        "version": version,
                    },
                    tags={
                        "component": "langfuse_evaluation",
                        "operation": "log_ground_truth_eval",
                        "severity": "low",
                        "user_facing": "false",
                    },
                )
                logger.warning(f"Failed to log to Langfuse: {log_e}")
        else:
            logger.warning("Langfuse trace unavailable; skipping logging for ground truth eval")

        logger.info(
            f"✅ Ground truth eval: {request.prompt_name} v{version} - Score: {overall_score:.2f}%"
        )

        return GroundTruthEvalResponse(
            status="success",
            prompt_name=request.prompt_name,
            version=version,
            compiled_prompt=compiled,
            generated_response=generated_response,
            ground_truth=request.ground_truth_response,
            evaluation_scores=scores,
            overall_score=overall_score,
            langfuse_trace_id=langfuse_trace_id,
            message=f"Ground truth evaluation complete. Overall score: {overall_score:.2f}%",
        )
    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(request.user_id),
                "persona_id": str(request.persona_id),
                "prompt_name": request.prompt_name,
            },
            tags={
                "component": "langfuse_evaluation",
                "operation": "ground_truth_eval",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"❌ Ground truth evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Ground truth evaluation failed: {str(e)}")


@router.post("/eval-llama-rag", response_model=LlamaRAGEvalResult)
async def evaluate_llama_rag(
    request: LlamaRAGEvalRequest, db: AsyncSession = Depends(get_db)
) -> LlamaRAGEvalResult:
    start_time = time.time()
    persona_stmt = select(Persona).where(Persona.id == request.persona_id)
    persona_result = await db.execute(persona_stmt)
    persona = persona_result.scalar_one_or_none()
    if not persona:
        raise HTTPException(
            status_code=404, detail=f"Persona with ID '{request.persona_id}' not found"
        )
    if persona.user_id != request.user_id:
        raise HTTPException(
            status_code=403, detail=f"User does not have access to persona '{request.persona_id}'"
        )

    from app.services.langfuse_observability_service import LangfuseObservabilityService

    langfuse_service = LangfuseObservabilityService()
    params = request.params
    try:
        from llama_index.core.evaluation import (
            CorrectnessEvaluator,
            FaithfulnessEvaluator,
            RelevancyEvaluator,
            SemanticSimilarityEvaluator,
        )
    except ImportError:
        raise HTTPException(status_code=501, detail="llama_index evaluation modules not installed")

    root_trace_id = await langfuse_service.track_evaluation(
        name="prompt_evaluation_llama_rag",
        user_id=str(request.user_id),
        persona_id=str(persona.id),
        input_data={
            "total_queries": len(request.queries),
            "eval_params": request.params.model_dump(),
        },
        output_data={"status": "running"},
        metadata={
            "persona_id": str(persona.id),
            "persona_name": persona.name,
            "evaluation_type": "llama_rag",
            "evaluator": params.evaluator or "llamaindex",
            "tags": ["eval", "prompt_evaluation", "llama_rag", "batch_eval"],
        },
    )

    evaluators = {
        "faithfulness": FaithfulnessEvaluator(),
        "answer_relevancy": RelevancyEvaluator(),
        "correctness": CorrectnessEvaluator(),
        "semantic_similarity": SemanticSimilarityEvaluator(),
    }

    rag_system = await get_rag_system()
    per_query_metadata: List[Dict[str, Any]] = []
    overall_accumulator: Dict[str, List[float]] = {k: [] for k in evaluators.keys()}
    top_k = params.top_k or 5
    similarity_threshold = params.similarity_threshold or 0.0

    for idx, q in enumerate(request.queries, start=1):
        q_start = time.time()
        question = q.query.strip()
        ground_truth = (q.ground_truth or "").strip() or None
        try:
            retrieval = await rag_system.retrieve_context(
                persona_id=persona.id,
                query=question,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                include_patterns=False,
            )
            chunks = retrieval.get("chunks", [])
        except Exception as e:  # noqa: BLE001
            logger.error(f"Context retrieval failed for query {idx}: {e}")
            chunks = []
        contexts_text = [c.get("content", "").strip() for c in chunks if c.get("content")] or [
            "(no context)"
        ]

        try:
            answer_tokens: List[str] = []
            async for part in rag_system.generate_response_stream(
                persona_id=persona.id,
                query=question,
                context={"patterns": {}},
                temperature=0.7,
                max_tokens=600,
                return_citations=False,
            ):
                if isinstance(part, str):
                    answer_tokens.append(part)
            answer = "".join(answer_tokens).strip() or "(empty response)"
        except Exception as e:  # noqa: BLE001
            logger.error(f"Answer generation failed for query {idx}: {e}")
            answer = "(generation failed)"

        meta_entry: Dict[str, Any] = {
            "index": idx - 1,
            "question": question,
            "answer": answer[:5000],
            "ground_truth": ground_truth or "",
            "contexts_used_count": len(contexts_text),
            "processing_time_sec": round(time.time() - q_start, 3),
        }
        if params.include_contexts:
            limit = params.truncate_context_chars
            meta_entry["contexts"] = [
                ctx[:limit] + ("..." if len(ctx) > limit else "") for ctx in contexts_text[:top_k]
            ]

        metrics_row: Dict[str, float] = {}
        if answer in {"(generation failed)", "(empty response)"}:
            for m in evaluators.keys():
                metrics_row[m] = 0.0
        else:
            use_llm_judge = params.evaluator == "llm_judge"
            if use_llm_judge:
                logger.info(f"Using LLM-as-judge for query {idx}")
                for name in evaluators.keys():
                    score = await _run_llm_judge_evaluator(
                        question, answer, contexts_text, ground_truth, name
                    )
                    metrics_row[name] = score
                    overall_accumulator[name].append(score)
            else:
                for name, evaluator in evaluators.items():
                    score = await _run_evaluator(
                        evaluator, question, answer, contexts_text, ground_truth
                    )
                    metrics_row[name] = score
                    overall_accumulator[name].append(score)

        if answer in {"(generation failed)", "(empty response)"}:
            for name in evaluators.keys():
                overall_accumulator[name].append(0.0)

        meta_entry["metrics"] = metrics_row

        retrieved_context = (
            "\n\n---\n\n".join(contexts_text[:top_k]) if contexts_text else "(no context)"
        )
        await _log_query_evaluation_trace(
            langfuse_service,
            trace_name="llama_rag",
            user_id=str(request.user_id),
            persona_id=str(persona.id),
            persona_name=persona.name,
            evaluator_type=("llm_judge" if params.evaluator == "llm_judge" else "llamaindex"),
            query_index=idx,
            question=question,
            ground_truth=ground_truth,
            response=answer,
            retrieved_context=retrieved_context,
            num_contexts=len(contexts_text),
            metrics=metrics_row,
            processing_time_sec=meta_entry["processing_time_sec"],
            tags=["rag_evaluation", "prompt_testing"],
            extra_metadata={
                "total_queries": len(request.queries),
                "root_trace_id": root_trace_id,
            },
        )

        per_query_metadata.append(meta_entry)

    overall_scores = {
        k: (round(sum(v) / len(v), 4) if v else 0.0) for k, v in overall_accumulator.items()
    }
    total_time = time.time() - start_time

    evaluator_type = "llm_judge" if params.evaluator == "llm_judge" else "llamaindex"
    if root_trace_id:
        await langfuse_service.log_multiple_scores(
            trace_id=root_trace_id,
            scores=overall_scores,
            comment_prefix="Overall average",
            evaluator_type=evaluator_type,
        )
        await langfuse_service.update_trace(
            trace_id=root_trace_id,
            output={
                "status": "success",
                "metrics_overall": overall_scores,
                "total_queries": len(request.queries),
                "eval_time_seconds": round(total_time, 3),
            },
        )
        langfuse_service.flush()

    return LlamaRAGEvalResult(
        status="success",
        persona_id=persona.id,
        total_queries=len(request.queries),
        metrics_overall=overall_scores,
        details=per_query_metadata,
        eval_time_seconds=round(total_time, 3),
        message=f"Evaluation completed in {total_time:.2f}s",
    )


@router.post("/eval-llama-retrieval", response_model=LlamaRAGRetrievalEvalResult)
async def evaluate_llama_rag_retrieval(
    request: LlamaRAGRetrievalEvalRequest, db: AsyncSession = Depends(get_db)
) -> LlamaRAGRetrievalEvalResult:
    start_time = time.time()
    persona_stmt = select(Persona).where(Persona.id == request.persona_id)
    persona_result = await db.execute(persona_stmt)
    persona = persona_result.scalar_one_or_none()
    if not persona:
        raise HTTPException(
            status_code=404, detail=f"Persona with ID '{request.persona_id}' not found"
        )
    if persona.user_id != request.user_id:
        raise HTTPException(
            status_code=403, detail=f"User does not have access to persona '{request.persona_id}'"
        )

    from app.services.langfuse_observability_service import LangfuseObservabilityService

    langfuse_service = LangfuseObservabilityService()
    langfuse_trace_id = await langfuse_service.track_evaluation(
        name="prompt_evaluation_retrieval",
        user_id=str(request.user_id),
        persona_id=str(persona.id),
        input_data={
            "total_queries": len(request.queries),
            "eval_params": request.params.model_dump(),
            "queries": [q.query for q in request.queries],
        },
        output_data={},
        metadata={
            "persona_id": str(persona.id),
            "persona_name": persona.name,
            "evaluation_type": "retrieval_only",
            "evaluator": request.params.evaluator or "llamaindex",
            "tags": ["eval", "prompt_evaluation", "retrieval_only", "batch_eval"],
        },
    )
    params = request.params
    try:
        from llama_index.core.evaluation import RelevancyEvaluator
    except ImportError:
        raise HTTPException(status_code=501, detail="llama_index evaluation modules not installed")
    relevancy_evaluator = RelevancyEvaluator()
    rag_system = await get_rag_system()
    metric_names = ["context_relevancy", "retrieval_precision"]
    overall_accumulator: Dict[str, List[float]] = {m: [] for m in metric_names}
    per_query_metadata: List[Dict[str, Any]] = []
    top_k = params.top_k or 5
    similarity_threshold = params.similarity_threshold or 0.0

    for idx, q in enumerate(request.queries, start=1):
        q_start = time.time()
        question = q.query.strip()
        ground_truth = (q.ground_truth or "").strip() or None
        try:
            retrieval = await rag_system.retrieve_context(
                persona_id=persona.id,
                query=question,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                include_patterns=False,
            )
            chunks = retrieval.get("chunks", [])
        except Exception as e:  # noqa: BLE001
            logger.error(f"Retrieval failed for query {idx}: {e}")
            chunks = []
        contexts_text = [c.get("content", "").strip() for c in chunks if c.get("content")] or [
            "(no context)"
        ]
        similarities = [round(c.get("similarity", 0.0), 4) for c in chunks]

        use_llm_judge = params.evaluator == "llm_judge"
        if use_llm_judge:
            logger.info(f"Using LLM-as-judge for retrieval query {idx}")
            context_relevancy = await _run_llm_judge_evaluator(
                question, "", contexts_text, ground_truth, "context_relevancy"
            )
            retrieval_precision = await _run_llm_judge_evaluator(
                question, "", contexts_text, ground_truth, "retrieval_precision"
            )
        else:
            per_context_scores: List[float] = []
            for ctx in contexts_text:
                score = await _run_evaluator(
                    relevancy_evaluator, question, ctx, [ctx], ground_truth
                )
                per_context_scores.append(score)
            if per_context_scores:
                context_relevancy = sum(per_context_scores) / len(per_context_scores)
            else:
                context_relevancy = 0.0
            if ground_truth and per_context_scores:
                sorted_scores = sorted(per_context_scores)
                median = sorted_scores[len(sorted_scores) // 2]
                selected = [s for s in per_context_scores if s >= median]
                retrieval_precision = sum(selected) / len(selected) if selected else 0.0
            else:
                retrieval_precision = (
                    (sum(similarities) / len(similarities)) if similarities else 0.0
                )

        context_relevancy = _sanitize_float(context_relevancy)
        retrieval_precision = _sanitize_float(retrieval_precision)
        metrics_row = {
            "context_relevancy": context_relevancy,
            "retrieval_precision": retrieval_precision,
        }
        overall_accumulator["context_relevancy"].append(context_relevancy)
        overall_accumulator["retrieval_precision"].append(retrieval_precision)

        retrieved_context = (
            "\n\n---\n\n".join(contexts_text[:top_k]) if contexts_text else "(no context)"
        )
        await _log_query_evaluation_trace(
            langfuse_service,
            trace_name="retrieval_only",
            user_id=str(request.user_id),
            persona_id=str(persona.id),
            persona_name=persona.name,
            evaluator_type=params.evaluator or "llamaindex",
            query_index=idx,
            question=question,
            ground_truth=ground_truth,
            response="",
            retrieved_context=retrieved_context,
            num_contexts=len(contexts_text),
            metrics=metrics_row,
            processing_time_sec=round(time.time() - q_start, 3),
            tags=["retrieval_evaluation", "context_only"],
            extra_metadata={"total_queries": len(request.queries)},
        )

        meta: Dict[str, Any] = {
            "index": idx - 1,
            "question": question,
            "ground_truth": ground_truth or "",
            "contexts_used_count": len(contexts_text),
            "similarities": similarities[:top_k],
            "processing_time_sec": round(time.time() - q_start, 3),
            "metrics": metrics_row,
        }
        if params.include_contexts:
            limit = params.truncate_context_chars
            meta["contexts"] = [
                c[:limit] + ("..." if len(c) > limit else "") for c in contexts_text[:top_k]
            ]
        per_query_metadata.append(meta)

    overall_scores = {
        m: (round(sum(v) / len(v), 4) if v else 0.0) for m, v in overall_accumulator.items()
    }
    total_time = time.time() - start_time

    evaluator_type = params.evaluator if params.evaluator else "llamaindex"
    await langfuse_service.log_multiple_scores(
        trace_id=langfuse_trace_id,
        scores=overall_scores,
        comment_prefix="Overall average",
        evaluator_type=evaluator_type,
    )
    await langfuse_service.update_trace(
        trace_id=langfuse_trace_id,
        output={
            "status": "success",
            "metrics_overall": overall_scores,
            "total_queries": len(request.queries),
            "eval_time_seconds": round(total_time, 3),
        },
    )
    langfuse_service.flush()
    logger.info(f"✅ Logged retrieval evaluation results to Langfuse trace: {langfuse_trace_id}")

    return LlamaRAGRetrievalEvalResult(
        status="success",
        persona_id=persona.id,
        total_queries=len(request.queries),
        metrics_overall=overall_scores,
        details=per_query_metadata,
        eval_time_seconds=round(total_time, 3),
        message=f"Retrieval evaluation completed in {total_time:.2f}s",
    )


@router.post("/custom-eval-llama-rag", response_model=LlamaRAGEvalResult)
async def custom_evaluate_llama_rag(
    request: LlamaRAGEvalRequest, db: AsyncSession = Depends(get_db)
) -> LlamaRAGEvalResult:
    start_time = time.time()
    persona_stmt = select(Persona).where(Persona.id == request.persona_id)
    persona_result = await db.execute(persona_stmt)
    persona = persona_result.scalar_one_or_none()
    if not persona:
        raise HTTPException(
            status_code=404, detail=f"Persona with ID '{request.persona_id}' not found"
        )
    if persona.user_id != request.user_id:
        raise HTTPException(
            status_code=403, detail=f"User does not have access to persona '{request.persona_id}'"
        )

    from app.services.langfuse_observability_service import LangfuseObservabilityService

    langfuse_service = LangfuseObservabilityService()
    params = request.params

    # Create root trace for custom evaluation
    langfuse_trace_id = await langfuse_service.track_evaluation(
        name="custom_prompt_evaluation_llama_rag",
        user_id=str(request.user_id),
        persona_id=str(persona.id),
        input_data={
            "total_queries": len(request.queries),
            "eval_params": request.params.model_dump(),
        },
        output_data={"status": "running"},
        metadata={
            "persona_id": str(persona.id),
            "persona_name": persona.name,
            "evaluation_type": "custom_heuristic",
            "evaluator": params.evaluator or "heuristic",
            "tags": ["eval", "prompt_evaluation", "custom_eval", "llama_rag"],
        },
    )

    rag_system = await get_rag_system()
    top_k = params.top_k or 5
    similarity_threshold = params.similarity_threshold or 0.0

    per_query_metadata: List[Dict[str, Any]] = []
    overall_accumulator: Dict[str, List[float]] = {
        "faithfulness": [],
        "answer_relevancy": [],
        "correctness": [],
        "semantic_similarity": [],
    }

    for idx, q in enumerate(request.queries, start=1):
        q_start = time.time()
        question = q.query.strip()
        ground_truth = (q.ground_truth or "").strip()
        try:
            retrieval = await rag_system.retrieve_context(
                persona_id=persona.id,
                query=question,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                include_patterns=False,
            )
            chunks = retrieval.get("chunks", [])
        except Exception as e:  # noqa: BLE001
            logger.error(f"Context retrieval failed (custom) for query {idx}: {e}")
            chunks = []
        contexts_text = [c.get("content", "").strip() for c in chunks if c.get("content")] or [
            "(no context)"
        ]

        try:
            answer_tokens_parts: List[str] = []
            async for part in rag_system.generate_response_stream(
                persona_id=persona.id,
                query=question,
                context={"patterns": {}},
                temperature=0.7,
                max_tokens=600,
                return_citations=False,
            ):
                if isinstance(part, str):
                    answer_tokens_parts.append(part)
            answer = "".join(answer_tokens_parts).strip() or "(empty response)"
        except Exception as e:  # noqa: BLE001
            logger.error(f"Answer generation failed (custom) for query {idx}: {e}")
            answer = "(generation failed)"

        meta_entry: Dict[str, Any] = {
            "index": idx - 1,
            "question": question,
            "answer": answer[:5000],
            "ground_truth": ground_truth,
            "contexts_used_count": len(contexts_text),
            "processing_time_sec": round(time.time() - q_start, 3),
        }
        if params.include_contexts:
            limit = params.truncate_context_chars
            meta_entry["contexts"] = [
                ctx[:limit] + ("..." if len(ctx) > limit else "") for ctx in contexts_text[:top_k]
            ]

        metrics_row: Dict[str, float] = {}
        use_llm_judge = params.evaluator == "llm_judge"
        if answer in {"(generation failed)", "(empty response)"}:
            for k in overall_accumulator.keys():
                metrics_row[k] = 0.0
                overall_accumulator[k].append(0.0)
        else:
            if use_llm_judge:
                logger.info(f"Using LLM-as-judge for custom eval query {idx}")
                faithfulness = await _run_llm_judge_evaluator(
                    question, answer, contexts_text, ground_truth, "faithfulness"
                )
                answer_relevancy = await _run_llm_judge_evaluator(
                    question, answer, contexts_text, ground_truth, "answer_relevancy"
                )
                correctness = await _run_llm_judge_evaluator(
                    question, answer, contexts_text, ground_truth, "correctness"
                )
                semantic_similarity = await _run_llm_judge_evaluator(
                    question, answer, contexts_text, ground_truth, "semantic_similarity"
                )
                for k, v in {
                    "faithfulness": faithfulness,
                    "answer_relevancy": answer_relevancy,
                    "correctness": correctness,
                    "semantic_similarity": semantic_similarity,
                }.items():
                    v_clean = _sanitize_float(v)
                    metrics_row[k] = v_clean
                    overall_accumulator[k].append(v_clean)
            else:
                lower_answer = answer.lower()
                question_words = set(question.lower().split())
                answer_words = set(lower_answer.split())
                gt_words = set(ground_truth.lower().split()) if ground_truth else set()
                ctx_basis_words = set()
                for ctx in contexts_text[:top_k]:
                    ctx_basis_words.update(ctx.lower().split()[:10])
                faithfulness = 0.8 if any(w in ctx_basis_words for w in answer_words) else 0.3
                common_q = question_words.intersection(answer_words)
                answer_relevancy = min(1.0, (len(common_q) / max(1, len(question_words))) * 2)
                if ground_truth and gt_words:
                    common_gt = gt_words.intersection(answer_words)
                    correctness = min(1.0, (len(common_gt) / max(1, len(gt_words))) * 1.5)
                else:
                    correctness = 0.7
                if ground_truth and gt_words and answer_words:
                    semantic_similarity = len(gt_words.intersection(answer_words)) / len(
                        gt_words.union(answer_words)
                    )
                else:
                    semantic_similarity = 0.5
                for k, v in {
                    "faithfulness": faithfulness,
                    "answer_relevancy": answer_relevancy,
                    "correctness": correctness,
                    "semantic_similarity": semantic_similarity,
                }.items():
                    v_clean = _sanitize_float(v)
                    metrics_row[k] = v_clean
                    overall_accumulator[k].append(v_clean)

        meta_entry["metrics"] = metrics_row

        retrieved_context = (
            "\n\n---\n\n".join(contexts_text[:top_k]) if contexts_text else "(no context)"
        )
        await _log_query_evaluation_trace(
            langfuse_service,
            trace_name="custom_eval",
            user_id=str(request.user_id),
            persona_id=str(persona.id),
            persona_name=persona.name,
            evaluator_type=("llm_judge" if params.evaluator == "llm_judge" else "heuristic"),
            query_index=idx,
            question=question,
            ground_truth=ground_truth,
            response=answer,
            retrieved_context=retrieved_context,
            num_contexts=len(contexts_text),
            metrics=metrics_row,
            processing_time_sec=meta_entry["processing_time_sec"],
            tags=["custom_evaluation", "heuristic"],
            extra_metadata={"total_queries": len(request.queries)},
        )

        per_query_metadata.append(meta_entry)

    overall_scores = {
        k: (round(sum(v) / len(v), 4) if v else 0.0) for k, v in overall_accumulator.items()
    }
    total_time = time.time() - start_time

    evaluator_type = "llm_judge" if params.evaluator == "llm_judge" else "heuristic"
    if langfuse_trace_id:
        await langfuse_service.log_multiple_scores(
            trace_id=langfuse_trace_id,
            scores=overall_scores,
            comment_prefix="Overall average",
            evaluator_type=evaluator_type,
        )
        await langfuse_service.update_trace(
            trace_id=langfuse_trace_id,
            output={
                "status": "success",
                "metrics_overall": overall_scores,
                "total_queries": len(request.queries),
                "eval_time_seconds": round(total_time, 3),
            },
        )
        langfuse_service.flush()
        logger.info(f"✅ Logged custom evaluation results to Langfuse trace: {langfuse_trace_id}")

    return LlamaRAGEvalResult(
        status="success",
        persona_id=persona.id,
        total_queries=len(request.queries),
        metrics_overall=overall_scores,
        details=per_query_metadata,
        eval_time_seconds=round(total_time, 3),
        message=f"Custom {'LLM-as-judge' if params.evaluator == 'llm_judge' else 'heuristic'} evaluation completed in {total_time:.2f}s",
    )


@router.post("/custom-eval-llama-rag-retrieval", response_model=LlamaRAGRetrievalEvalResult)
async def custom_evaluate_llama_rag_retrieval(
    request: LlamaRAGRetrievalEvalRequest, db: AsyncSession = Depends(get_db)
) -> LlamaRAGRetrievalEvalResult:
    start_time = time.time()
    persona_stmt = select(Persona).where(Persona.id == request.persona_id)
    persona_result = await db.execute(persona_stmt)
    persona = persona_result.scalar_one_or_none()
    if not persona:
        raise HTTPException(
            status_code=404, detail=f"Persona with ID '{request.persona_id}' not found"
        )
    if persona.user_id != request.user_id:
        raise HTTPException(
            status_code=403, detail=f"User does not have access to persona '{request.persona_id}'"
        )

    from app.services.langfuse_observability_service import LangfuseObservabilityService

    langfuse_service = LangfuseObservabilityService()
    params = request.params

    # Create root trace for custom retrieval evaluation
    langfuse_trace_id = await langfuse_service.track_evaluation(
        name="custom_prompt_evaluation_retrieval",
        user_id=str(request.user_id),
        persona_id=str(persona.id),
        input_data={
            "total_queries": len(request.queries),
            "eval_params": request.params.model_dump(),
            "queries": [q.query for q in request.queries],
        },
        output_data={"status": "running"},
        metadata={
            "persona_id": str(persona.id),
            "persona_name": persona.name,
            "evaluation_type": "custom_heuristic_retrieval",
            "evaluator": params.evaluator or "heuristic",
            "tags": ["eval", "prompt_evaluation", "custom_eval", "retrieval_only"],
        },
    )

    rag_system = await get_rag_system()
    top_k = params.top_k or 5
    similarity_threshold = params.similarity_threshold or 0.0

    per_query_metadata: List[Dict[str, Any]] = []
    overall_accumulator: Dict[str, List[float]] = {
        "context_relevancy": [],
        "retrieval_precision": [],
    }

    for idx, q in enumerate(request.queries, start=1):
        q_start = time.time()
        question = q.query.strip()
        ground_truth = (q.ground_truth or "").strip() or None
        try:
            retrieval = await rag_system.retrieve_context(
                persona_id=persona.id,
                query=question,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                include_patterns=False,
            )
            chunks = retrieval.get("chunks", [])
        except Exception as e:  # noqa: BLE001
            logger.error(f"Retrieval failed for query {idx}: {e}")
            chunks = []
        contexts_text = [c.get("content", "").strip() for c in chunks if c.get("content")] or [
            "(no context)"
        ]
        similarities = [round(c.get("similarity", 0.0), 4) for c in chunks]

        use_llm_judge = params.evaluator == "llm_judge"
        if use_llm_judge:
            logger.info(f"Using LLM-as-judge for custom retrieval query {idx}")
            context_relevancy = await _run_llm_judge_evaluator(
                question, "", contexts_text, ground_truth, "context_relevancy"
            )
            retrieval_precision = await _run_llm_judge_evaluator(
                question, "", contexts_text, ground_truth, "retrieval_precision"
            )
        else:
            question_words = set(question.lower().split())
            gt_words = set(ground_truth.lower().split()) if ground_truth else set()
            if contexts_text == ["(no context)"]:
                context_relevancy = 0.0
            else:
                overlap_count = 0
                for ctx in contexts_text:
                    ctx_words = set(ctx.lower().split())
                    if question_words.intersection(ctx_words):
                        overlap_count += 1
                context_relevancy = overlap_count / max(1, len(contexts_text))
            if ground_truth and gt_words and contexts_text != ["(no context)"]:
                hit = 0
                for ctx in contexts_text:
                    ctx_words = set(ctx.lower().split())
                    if gt_words.intersection(ctx_words):
                        hit += 1
                retrieval_precision = hit / max(1, len(contexts_text))
            else:
                retrieval_precision = (
                    (sum(similarities) / len(similarities)) if similarities else 0.0
                )

        context_relevancy = _sanitize_float(context_relevancy)
        retrieval_precision = _sanitize_float(retrieval_precision)
        metrics_row = {
            "context_relevancy": context_relevancy,
            "retrieval_precision": retrieval_precision,
        }
        overall_accumulator["context_relevancy"].append(context_relevancy)
        overall_accumulator["retrieval_precision"].append(retrieval_precision)

        meta: Dict[str, Any] = {
            "index": idx - 1,
            "question": question,
            "ground_truth": ground_truth or "",
            "contexts_used_count": len(contexts_text),
            "similarities": similarities[:top_k],
            "processing_time_sec": round(time.time() - q_start, 3),
            "metrics": metrics_row,
        }
        if params.include_contexts:
            limit = params.truncate_context_chars
            meta["contexts"] = [
                c[:limit] + ("..." if len(c) > limit else "") for c in contexts_text[:top_k]
            ]
        per_query_metadata.append(meta)

        retrieved_context = (
            "\n\n---\n\n".join(contexts_text[:top_k]) if contexts_text else "(no context)"
        )
        await _log_query_evaluation_trace(
            langfuse_service,
            trace_name="custom_retrieval",
            user_id=str(request.user_id),
            persona_id=str(persona.id),
            persona_name=persona.name,
            evaluator_type=params.evaluator or "heuristic",
            query_index=idx,
            question=question,
            ground_truth=ground_truth,
            response="",
            retrieved_context=retrieved_context,
            num_contexts=len(contexts_text),
            metrics=metrics_row,
            processing_time_sec=meta["processing_time_sec"],
            tags=["custom_retrieval_evaluation", "heuristic"],
            extra_metadata={
                "total_queries": len(request.queries),
                "similarities": similarities[:top_k],
            },
        )

    overall_scores = {
        m: (round(sum(v) / len(v), 4) if v else 0.0) for m, v in overall_accumulator.items()
    }
    total_time = time.time() - start_time

    evaluator_type = "llm_judge" if params.evaluator == "llm_judge" else "heuristic"
    if langfuse_trace_id:
        await langfuse_service.log_multiple_scores(
            trace_id=langfuse_trace_id,
            scores=overall_scores,
            comment_prefix="Overall average",
            evaluator_type=evaluator_type,
        )
        await langfuse_service.update_trace(
            trace_id=langfuse_trace_id,
            output={
                "status": "success",
                "metrics_overall": overall_scores,
                "total_queries": len(request.queries),
                "eval_time_seconds": round(total_time, 3),
            },
        )
        langfuse_service.flush()
        logger.info(
            f"✅ Logged custom retrieval evaluation results to Langfuse trace: {langfuse_trace_id}"
        )

    return LlamaRAGRetrievalEvalResult(
        status="success",
        persona_id=persona.id,
        total_queries=len(request.queries),
        metrics_overall=overall_scores,
        details=per_query_metadata,
        eval_time_seconds=round(total_time, 3),
        message=f"Custom {'LLM-as-judge' if params.evaluator == 'llm_judge' else 'heuristic'} retrieval evaluation completed in {total_time:.2f}s",
    )
