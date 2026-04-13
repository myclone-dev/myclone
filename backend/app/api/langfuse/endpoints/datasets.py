"""
Dataset management endpoints for Langfuse
"""

import json
import logging
from typing import TYPE_CHECKING, Any, List, Tuple
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.langfuse.schemas import (
    DatasetItemCreate,
    DatasetItemResponse,
    DatasetTraceItemResult,
    DatasetTraceRequest,
    DatasetTraceResponse,
)
from shared.database.models.database import Persona, PersonaPrompt, async_session_maker
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.rag.rag_singleton import get_rag_system
from shared.utils.langfuse_utils import get_langfuse_client

if TYPE_CHECKING:  # Only import for type-checkers; avoid runtime errors if langfuse extras missing
    try:
        from langfuse.api.resources.datasets.types.dataset_item import DatasetItemWithValue
    except Exception:  # pragma: no cover
        DatasetItemWithValue = Any  # type: ignore
else:  # pragma: no cover - runtime fallback
    DatasetItemWithValue = Any  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Langfuse - Datasets"])


async def get_db():
    async with async_session_maker() as session:
        yield session


async def _validate_persona(db: AsyncSession, user_id, persona_id) -> Persona:
    stmt = select(Persona).where(and_(Persona.id == persona_id, Persona.user_id == user_id))
    result = await db.execute(stmt)
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found or not owned by user")
    return persona


def _extract_dataset_rows(dataset_items: List[DatasetItemWithValue]) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    for item in dataset_items:
        payload = item.input if isinstance(item.input, dict) else {}
        query = payload.get("query") or payload.get("input")
        ground_truth = payload.get("gt") or payload.get("ground_truth") or ""
        if query:
            rows.append((query, ground_truth))
    return rows


@router.post("/create-item", response_model=DatasetItemResponse)
async def create_dataset_item(request: DatasetItemCreate, db: AsyncSession = Depends(get_db)):
    """Create a dataset item in Langfuse for evaluation testing."""
    try:
        # 1. Validate user and persona exist
        persona_stmt = select(Persona).where(
            and_(Persona.id == request.persona_id, Persona.user_id == request.user_id)
        )
        persona_result = await db.execute(persona_stmt)
        persona = persona_result.scalar_one_or_none()

        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found or not owned by user")

        # Get persona prompt for context
        prompt_stmt = select(PersonaPrompt).where(
            and_(PersonaPrompt.persona_id == request.persona_id, PersonaPrompt.is_active == True)
        )
        prompt_result = await db.execute(prompt_stmt)
        persona_prompt = prompt_result.scalar_one_or_none()

        # Build prompt variables
        response_structure = {}
        if persona_prompt and persona_prompt.response_structure:
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
                    extra={"persona_id": str(request.persona_id)},
                    tags={
                        "component": "langfuse_datasets",
                        "operation": "parse_response_structure",
                        "severity": "low",
                        "user_facing": "false",
                    },
                )
                logger.warning(f"Failed to parse response_structure: {parse_e}")

        prompt_variables = {
            "persona_name": persona.name or "Expert",
            "introduction": persona_prompt.introduction if persona_prompt else "",
            "area_of_expertise": (
                persona_prompt.area_of_expertise if persona_prompt else "General expertise"
            ),
            "thinking_style": (
                persona_prompt.thinking_style if persona_prompt else "Thoughtful and analytical"
            ),
            "chat_objective": (
                persona_prompt.chat_objective if persona_prompt else "Provide helpful guidance"
            ),
            "user_query": request.user_query,
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

        full_metadata = {
            "user_id": str(request.user_id),
            "persona_id": str(request.persona_id),
            **(request.metadata or {}),
        }

        # 2. Create dataset in Langfuse
        client = get_langfuse_client()

        try:
            client.create_dataset(
                name=request.dataset_name,
                description=f"Evaluation dataset for user {request.user_id}",
                metadata={"user_id": str(request.user_id), "persona_id": str(request.persona_id)},
            )
            logger.info(f"Created dataset: {request.dataset_name}")
        except Exception as e:
            # Dataset may already exist
            logger.debug(f"Dataset may already exist: {e}")

        # Create dataset item
        dataset_item = client.create_dataset_item(
            dataset_name=request.dataset_name,
            input=prompt_variables,
            expected_output=request.ground_truth_response,
            metadata=full_metadata,
        )

        client.flush()

        logger.info(
            f"✅ Created dataset item in '{request.dataset_name}' "
            f"for user {request.user_id}, persona {request.persona_id}"
        )

        return DatasetItemResponse(
            status="success",
            dataset_name=request.dataset_name,
            item_id=dataset_item.id if hasattr(dataset_item, "id") else "unknown",
            user_query=request.user_query,
            ground_truth=request.ground_truth_response,
            metadata={
                **full_metadata,
                "variables_count": len(prompt_variables),
            },
            message=f"Dataset item created in '{request.dataset_name}'",
        )
    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(request.user_id),
                "persona_id": str(request.persona_id),
                "dataset_name": request.dataset_name,
            },
            tags={
                "component": "langfuse_datasets",
                "operation": "create_item",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"❌ Failed to create dataset item: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create dataset item: {str(e)}")


@router.post("/trace-dataset", response_model=DatasetTraceResponse)
async def trace_llama_rag_dataset(
    request: DatasetTraceRequest, db: AsyncSession = Depends(get_db)
) -> DatasetTraceResponse:
    await _validate_persona(db, request.user_id, request.persona_id)

    client = get_langfuse_client()
    if not client:
        raise HTTPException(status_code=503, detail="Langfuse client unavailable")

    try:
        dataset = client.get_dataset(name=request.dataset_name)
    except Exception as e:
        logger.error(f"Langfuse dataset fetch failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=404, detail=f"Langfuse dataset '{request.dataset_name}' not found: {str(e)}"
        )

    items = dataset.items if dataset else []
    rows = _extract_dataset_rows(items)
    if not rows:
        raise HTTPException(status_code=404, detail="Dataset has no valid rows")

    rag_system = await get_rag_system()
    processed: List[DatasetTraceItemResult] = []
    failures = 0

    base_trace_name = f"prod_eval_{request.persona_id}"
    run_session_id = f"prod-eval-{uuid4()}"

    for idx, (query, ground_truth) in enumerate(rows, start=1):
        trace = client.start_span(
            name="dataset_prod_eval",
            input={"query": query, "gt": ground_truth},
            metadata={
                "tags": ["prod_eval", f"dataset:{request.dataset_name}"],
                "item_index": idx,
                "dataset_name": request.dataset_name,
            },
        )
        trace.update_trace(
            name=base_trace_name,
            user_id=str(request.user_id),
            session_id=run_session_id,
            tags=["prod_eval", f"persona:{request.persona_id}"],
        )

        response_text = ""
        contexts: List[str] = []
        error_msg = None

        try:
            logger.info(f"Processing query {idx}/{len(rows)}: '{query[:100]}'...")

            chunk_count = 0
            async for chunk in rag_system.generate_response_stream(
                persona_id=request.persona_id,
                query=query,
                context={"session_id": run_session_id, "patterns": {}},
                temperature=0.7,
                max_tokens=600,
                return_citations=True,
            ):
                chunk_count += 1
                if isinstance(chunk, str):
                    response_text += chunk
                elif isinstance(chunk, dict) and chunk.get("type") == "sources":
                    # Extract content from sources - these are now properly yielded from the stream
                    contexts = [src.get("content", "") for src in chunk.get("sources", [])]
                    logger.debug(f"Received {len(contexts)} source contexts from stream")

            logger.info(
                f"Generated response: {len(response_text)} chars, {chunk_count} chunks, {len(contexts)} contexts"
            )

            trace.update(
                output={"response": response_text, "context": contexts},
                metadata={
                    "status": "success",
                    "response_length": len(response_text),
                    "context_count": len(contexts),
                },
            )
            logger.info(f"✅ Successfully traced query {idx}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            error_msg = str(e)
            logger.error(f"❌ Error processing query {idx}: {error_msg}", exc_info=True)
            trace.update(metadata={"status": "error", "error": error_msg})
        finally:
            trace.end()

        processed.append(
            DatasetTraceItemResult(
                query=query,
                ground_truth=ground_truth,
                response=response_text,
                context=contexts,
                trace_id=getattr(trace, "trace_id", None),
                span_id=getattr(trace, "id", None),
                error=error_msg,
            )
        )

    # Flush Langfuse client to ensure all traces are sent
    client.flush()
    logger.info(
        f"✅ Flushed Langfuse client. Processed {len(processed)} items with {failures} failures"
    )

    status = "success" if failures == 0 else ("partial" if failures < len(rows) else "error")
    return DatasetTraceResponse(
        status=status,
        dataset_name=request.dataset_name,
        persona_id=request.persona_id,
        user_id=request.user_id,
        item_count=len(rows),
        processed_items=processed,
        failures=failures,
    )
