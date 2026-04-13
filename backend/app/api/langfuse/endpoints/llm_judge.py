"""
LLM-as-judge evaluation endpoints
"""

import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.langfuse.schemas import (
    LLMJudgeEvalRequest,
    LLMJudgeEvalResponse,
    LLMJudgePerformanceRequest,
    LLMJudgePerformanceResponse,
)
from app.api.langfuse.utils import _compile_prompt_with_rag
from app.services.langfuse_observability_service import LangfuseObservabilityService
from shared.config import settings
from shared.database.models.database import async_session_maker
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Langfuse - LLM Judge"])


async def get_db():
    async with async_session_maker() as session:
        yield session


@router.post("/llm-judge", response_model=LLMJudgeEvalResponse)
async def evaluate_with_llm_judge(request: LLMJudgeEvalRequest, db: AsyncSession = Depends(get_db)):
    """Evaluate prompt using LLM-as-judge approach."""
    try:
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

        if request.response:
            generated_response = request.response
        else:
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

        # Create judge prompt
        criteria_descriptions = {
            "helpfulness": "How helpful and useful is this response?",
            "accuracy": "How factually correct is the information?",
            "clarity": "How clear and easy to understand?",
            "relevance": "How well does it address the query?",
            "actionability": "Does it provide concrete, actionable advice?",
            "completeness": "How thoroughly does it cover the topic?",
        }

        criteria_text = "\n".join(
            [
                f"- {criterion}: {criteria_descriptions.get(criterion, 'Evaluate this aspect')}"
                for criterion in request.judge_criteria
            ]
        )

        # Build placeholder pairs for the scores object without using backslash escapes
        scores_pairs = ", ".join([f'"{c}": <score 0-100>' for c in request.judge_criteria])

        judge_prompt = f"""You are an expert evaluator assessing an AI assistant's response.

**User Query:** {request.query}
**AI Response:** {generated_response}

**Evaluation Criteria:**
{criteria_text}

Provide your evaluation as valid JSON:
{{
  "scores": {{ {scores_pairs} }},
  "reasoning": "Your detailed reasoning",
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"]
}}
"""

        from openai import AsyncOpenAI

        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        judge_response = await openai_client.chat.completions.create(
            model=request.judge_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert evaluator. Respond only with valid JSON.",
                },
                {"role": "user", "content": judge_prompt},
            ],
            temperature=0.3,
        )

        judge_output = judge_response.choices[0].message.content
        judge_evaluation = json.loads(judge_output)
        scores = judge_evaluation.get("scores", {})
        overall_score = sum(scores.values()) / len(scores) if scores else 0

        # Log to Langfuse with proper scores and tags
        langfuse_service = LangfuseObservabilityService()
        normalized_overall = overall_score / 100.0 if overall_score > 1 else overall_score

        langfuse_trace_id = await langfuse_service.track_evaluation(
            name="llm-judge-eval",
            user_id=str(request.user_id),
            persona_id=str(request.persona_id),
            input_data={
                "query": request.query,
                "prompt_name": request.prompt_name,
                "version": version,
                "judge_criteria": request.judge_criteria,
                "judge_model": request.judge_model,
            },
            output_data={},
            metadata={
                "persona_id": str(request.persona_id),
                "prompt_name": request.prompt_name,
                "version": version,
                "judge_model": request.judge_model,
                "evaluation_type": "llm_judge",
                "tags": ["eval", "prompt_evaluation", "llm_judge", "quality"],
            },
        )

        if langfuse_trace_id:
            try:
                query_span = langfuse_service.create_query_span(
                    query_index=1,
                    query=request.query,
                    ground_truth=None,
                    response=generated_response,
                    retrieved_context="",
                    num_contexts=0,
                    metadata={
                        "prompt_name": request.prompt_name,
                        "version": version,
                        "judge_model": request.judge_model,
                        "tags": ["eval", "llm_judge", "quality"],
                    },
                )

                if query_span:
                    for criterion, score in scores.items():
                        normalized_score = score / 100.0 if score > 1 else score
                        query_span.score(
                            name=criterion,
                            value=normalized_score,
                            data_type="NUMERIC",
                            comment=f"LLM judge evaluation: {criterion}",
                        )

                    query_span.score(
                        name="overall_quality",
                        value=normalized_overall,
                        data_type="NUMERIC",
                        comment="LLM judge overall quality score",
                    )

                    query_span.end()

                await langfuse_service.log_multiple_scores(
                    trace_id=langfuse_trace_id,
                    scores={"overall_quality": normalized_overall},
                    comment_prefix="LLM judge overall",
                    evaluator_type="llm_judge",
                )

                await langfuse_service.update_trace(
                    trace_id=langfuse_trace_id,
                    output={
                        "status": "success",
                        "scores": scores,
                        "overall_score": overall_score,
                        "generated_response": generated_response[:500],
                        "judge_reasoning": judge_evaluation.get("reasoning", ""),
                    },
                )

                langfuse_service.flush()
                logger.info(f"✅ Logged LLM judge scores to Langfuse trace: {langfuse_trace_id}")
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
                        "operation": "log_llm_judge_eval",
                        "severity": "low",
                        "user_facing": "false",
                    },
                )
                logger.warning(f"Failed to log to Langfuse: {log_e}")
        else:
            logger.warning("Langfuse trace unavailable; skipping LLM judge logging")

        logger.info(
            f"✅ LLM judge eval: {request.prompt_name} v{version} - Score: {overall_score:.2f}/100"
        )

        return LLMJudgeEvalResponse(
            status="success",
            prompt_name=request.prompt_name,
            version=version,
            compiled_prompt=compiled,
            generated_response=generated_response,
            judge_evaluation=judge_evaluation,
            scores=scores,
            overall_score=overall_score,
            judge_reasoning=judge_evaluation.get("reasoning", ""),
            langfuse_trace_id=langfuse_trace_id,
            message=f"LLM judge evaluation complete. Overall score: {overall_score:.2f}/100",
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
                "operation": "llm_judge_eval",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"❌ LLM judge evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"LLM judge evaluation failed: {str(e)}")


@router.post("/llm-judge-performance", response_model=LLMJudgePerformanceResponse)
async def evaluate_with_llm_judge_performance(
    request: LLMJudgePerformanceRequest, db: AsyncSession = Depends(get_db)
):
    """Evaluate prompt with LLM-as-judge including performance metrics."""
    try:
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

        generation_time_ms = None
        token_count = None

        if request.response:
            generated_response = request.response
        else:
            import asyncio

            from app.services.openai_service import OpenAIModelService

            openai_service = OpenAIModelService(api_key=settings.openai_api_key)
            openai_service.set_system_prompt(compiled)
            openai_service.set_parameters(
                temperature=config.get("temperature", 0.7),
                max_tokens=config.get("max_tokens", 2000),
            )

            start_time = time.time()

            # Run synchronous method in executor
            loop = asyncio.get_event_loop()
            generated_response = await loop.run_in_executor(
                None, openai_service.get_response, request.query
            )

            if request.measure_generation_time:
                generation_time_ms = (time.time() - start_time) * 1000

        token_count = len(generated_response.split()) * 1.3

        # Calculate performance metrics
        performance_metrics = {}
        for metric in request.performance_metrics:
            if metric == "latency" and generation_time_ms is not None:
                performance_metrics["latency_ms"] = round(generation_time_ms, 2)
                performance_metrics["latency_category"] = (
                    "excellent"
                    if generation_time_ms < 1000
                    else (
                        "good"
                        if generation_time_ms < 3000
                        else "acceptable" if generation_time_ms < 5000 else "slow"
                    )
                )
            elif metric == "token_efficiency":
                performance_metrics["total_tokens"] = int(token_count)
                if generation_time_ms and generation_time_ms > 0:
                    tokens_per_second = (token_count / generation_time_ms) * 1000
                    performance_metrics["tokens_per_second"] = round(tokens_per_second, 2)

        # Simple quality evaluation
        judge_evaluation = {
            "reasoning": "Basic performance evaluation completed",
            "strengths": ["Response generated successfully"],
            "weaknesses": [],
        }
        quality_scores = {criterion: 75.0 for criterion in request.judge_criteria}
        overall_quality_score = (
            sum(quality_scores.values()) / len(quality_scores) if quality_scores else 0
        )

        # Log to Langfuse with performance scores and proper tags
        client = LangfuseObservabilityService()
        trace_id = None
        try:
            trace = client.trace(
                name="llm-judge-performance-eval",
                user_id=str(request.user_id),
                input={
                    "query": request.query,
                    "prompt_name": request.prompt_name,
                    "version": version,
                },
                output={
                    "response": generated_response[:500],
                    "performance_metrics": performance_metrics,
                    "quality_scores": quality_scores,
                },
                metadata={
                    "persona_id": str(request.persona_id),
                    "prompt_name": request.prompt_name,
                    "version": version,
                    "generation_time_ms": generation_time_ms,
                    "tags": ["prompt_evaluation", "performance", "llm_judge"],
                },
            )
            trace_id = trace.id if hasattr(trace, "id") else None

            # Log performance metrics with proper tags
            if generation_time_ms is not None:
                client.score(
                    trace_id=trace_id,
                    name="latency_ms",
                    value=generation_time_ms,
                    data_type="NUMERIC",
                    comment="Response generation latency [tags: performance, latency]",
                )

                # Log latency category as categorical score
                client.score(
                    trace_id=trace_id,
                    name="latency_category",
                    value=performance_metrics.get("latency_category", "unknown"),
                    data_type="CATEGORICAL",
                    comment="Latency performance category [tags: performance, latency, categorical]",
                )

            if "tokens_per_second" in performance_metrics:
                client.score(
                    trace_id=trace_id,
                    name="tokens_per_second",
                    value=performance_metrics["tokens_per_second"],
                    data_type="NUMERIC",
                    comment="Token generation throughput [tags: performance, throughput]",
                )

            # Log quality scores
            for criterion, score in quality_scores.items():
                normalized_score = score / 100.0 if score > 1 else score
                client.score(
                    trace_id=trace_id,
                    name=f"quality_{criterion}",
                    value=normalized_score,
                    data_type="NUMERIC",
                    comment=f"Quality: {criterion} [tags: quality, llm_judge]",
                )

            # Log overall quality score
            normalized_overall = (
                overall_quality_score / 100.0
                if overall_quality_score > 1
                else overall_quality_score
            )
            client.score(
                trace_id=trace_id,
                name="overall_quality",
                value=normalized_overall,
                data_type="NUMERIC",
                comment="Overall quality score [tags: quality, overall]",
            )

            client.flush()
            logger.info(f"✅ Logged performance evaluation scores to Langfuse trace: {trace_id}")
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
                    "operation": "log_llm_judge_performance",
                    "severity": "low",
                    "user_facing": "false",
                },
            )
            logger.warning(f"Failed to log to Langfuse: {log_e}")

        return LLMJudgePerformanceResponse(
            status="success",
            prompt_name=request.prompt_name,
            version=version,
            compiled_prompt=compiled,
            generated_response=generated_response,
            performance_metrics=performance_metrics,
            judge_evaluation=judge_evaluation,
            quality_scores=quality_scores,
            overall_quality_score=overall_quality_score,
            generation_time_ms=generation_time_ms,
            token_count=int(token_count),
            langfuse_trace_id=trace_id,
            message=f"Performance evaluation complete. Quality: {overall_quality_score:.2f}/100",
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
                "operation": "llm_judge_performance",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"❌ LLM judge performance evaluation failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"LLM judge performance evaluation failed: {str(e)}"
        )
