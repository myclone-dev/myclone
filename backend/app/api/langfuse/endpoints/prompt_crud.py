"""
Prompt CRUD endpoints for Langfuse prompt management
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.langfuse.schemas import (
    CompilePromptRequest,
    CompilePromptResponse,
    LangfusePromptCreate,
    LangfusePromptResponse,
    LangfusePromptUpdate,
)
from shared.database.models.database import Persona, PersonaPrompt, async_session_maker
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.utils.langfuse_utils import get_langfuse_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Langfuse - Prompt CRUD"])


async def get_db():
    """Database session dependency"""
    async with async_session_maker() as session:
        yield session


@router.post("/create", response_model=LangfusePromptResponse)
async def create_langfuse_prompt(request: LangfusePromptCreate, db: AsyncSession = Depends(get_db)):
    """Create a new prompt template in Langfuse."""
    try:
        client = get_langfuse_client()
        config_dict = request.config.model_dump() if request.config else {}

        prompt = client.create_prompt(
            name=request.name,
            prompt=request.prompt,
            config=config_dict,
            labels=request.labels or [],
            tags=request.tags or [],
        )
        client.flush()

        logger.info(f"✅ Created Langfuse prompt: {request.name} (version {prompt.version})")

        return LangfusePromptResponse(
            status="success",
            name=prompt.name,
            version=prompt.version,
            prompt=prompt.prompt,
            config=prompt.config or {},
            labels=prompt.labels or [],
            tags=prompt.tags or [],
            created_at=(
                prompt.created_at.isoformat()
                if hasattr(prompt, "created_at") and prompt.created_at
                else None
            ),
            updated_at=(
                prompt.updated_at.isoformat()
                if hasattr(prompt, "updated_at") and prompt.updated_at
                else None
            ),
            message=f"Prompt '{request.name}' created successfully (version {prompt.version})",
        )
    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "prompt_name": request.name,
                "config": request.config.model_dump() if request.config else {},
            },
            tags={
                "component": "langfuse_prompts",
                "operation": "create_prompt",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"❌ Failed to create Langfuse prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create prompt: {str(e)}")


@router.get("/get/{prompt_name}", response_model=LangfusePromptResponse)
async def get_langfuse_prompt(
    prompt_name: str,
    version: Optional[int] = Query(None, description="Specific version (null = latest)"),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a prompt template from Langfuse."""
    try:
        client = get_langfuse_client()

        if version:
            prompt = client.get_prompt(name=prompt_name, version=version)
        else:
            prompt = client.get_prompt(name=prompt_name)

        if not prompt:
            raise HTTPException(status_code=404, detail=f"Prompt '{prompt_name}' not found")

        logger.info(f"📖 Retrieved Langfuse prompt: {prompt_name} (version {prompt.version})")

        return LangfusePromptResponse(
            status="success",
            name=prompt.name,
            version=prompt.version,
            prompt=prompt.prompt,
            config=prompt.config or {},
            labels=prompt.labels or [],
            tags=prompt.tags or [],
            created_at=(
                prompt.created_at.isoformat()
                if hasattr(prompt, "created_at") and prompt.created_at
                else None
            ),
            updated_at=(
                prompt.updated_at.isoformat()
                if hasattr(prompt, "updated_at") and prompt.updated_at
                else None
            ),
            message=f"Prompt '{prompt_name}' retrieved successfully (version {prompt.version})",
        )
    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={"prompt_name": prompt_name, "version": version},
            tags={
                "component": "langfuse_prompts",
                "operation": "get_prompt",
                "severity": "low",
                "user_facing": "true",
            },
        )
        logger.error(f"❌ Failed to get Langfuse prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get prompt: {str(e)}")


@router.put("/update/{prompt_name}", response_model=LangfusePromptResponse)
async def update_langfuse_prompt(
    prompt_name: str, request: LangfusePromptUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a prompt template (creates new version)."""
    try:
        client = get_langfuse_client()
        current = client.get_prompt(name=prompt_name)
        if not current:
            raise HTTPException(status_code=404, detail=f"Prompt '{prompt_name}' not found")

        new_template = request.prompt or current.prompt
        new_config = request.config.model_dump() if request.config else current.config or {}
        new_labels = request.labels if request.labels is not None else current.labels or []
        new_tags = request.tags if request.tags is not None else current.tags or []

        updated = client.create_prompt(
            name=prompt_name,
            prompt=new_template,
            config=new_config,
            labels=new_labels,
            tags=new_tags,
        )
        client.flush()

        logger.info(
            f"🔄 Updated Langfuse prompt: {prompt_name} (v{current.version} → v{updated.version})"
        )

        return LangfusePromptResponse(
            status="success",
            name=updated.name,
            version=updated.version,
            prompt=updated.prompt,
            config=updated.config or {},
            labels=updated.labels or [],
            tags=updated.tags or [],
            created_at=(
                updated.created_at.isoformat()
                if hasattr(updated, "created_at") and updated.created_at
                else None
            ),
            updated_at=(
                updated.updated_at.isoformat()
                if hasattr(updated, "updated_at") and updated.updated_at
                else None
            ),
            message=f"Prompt '{prompt_name}' updated (v{current.version} → v{updated.version})",
        )
    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "prompt_name": prompt_name,
                "update": request.model_dump() if request else {},
            },
            tags={
                "component": "langfuse_prompts",
                "operation": "update_prompt",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"❌ Failed to update Langfuse prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update prompt: {str(e)}")


@router.post("/compile", response_model=CompilePromptResponse)
async def compile_prompt_with_persona_data(
    request: CompilePromptRequest, db: AsyncSession = Depends(get_db)
):
    """Compile a Langfuse prompt template with persona data."""
    try:
        client = get_langfuse_client()

        if request.version:
            langfuse_prompt = client.get_prompt(name=request.prompt_name, version=request.version)
        else:
            langfuse_prompt = client.get_prompt(name=request.prompt_name)

        if not langfuse_prompt:
            raise HTTPException(
                status_code=404,
                detail=f"Prompt template '{request.prompt_name}' not found in Langfuse",
            )

        # Load persona data
        persona_stmt = select(Persona).where(
            and_(Persona.id == request.persona_id, Persona.user_id == request.user_id)
        )
        persona_result = await db.execute(persona_stmt)
        persona = persona_result.scalar_one_or_none()

        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found or not owned by user")

        prompt_stmt = select(PersonaPrompt).where(
            and_(PersonaPrompt.persona_id == request.persona_id, PersonaPrompt.is_active == True)
        )
        prompt_result = await db.execute(prompt_stmt)
        persona_prompt = prompt_result.scalar_one_or_none()

        if not persona_prompt:
            raise HTTPException(status_code=404, detail="No active persona prompt found")

        # LinkedIn repository removed; role/company come from user/persona fields only
        role, company = None, None

        # Parse response_structure
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
                    extra={"persona_id": str(request.persona_id)},
                    tags={
                        "component": "langfuse_prompts",
                        "operation": "parse_response_structure",
                        "severity": "low",
                        "user_facing": "false",
                    },
                )
                logger.warning(f"Failed to parse response_structure: {parse_e}")

        # Build variable dictionary
        variables = {
            "name": persona.name or "Expert",
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
            "response_structure_full": (
                json.dumps(response_structure) if response_structure else "{}"
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

        # Compile prompt
        compiled = langfuse_prompt.compile(**variables)

        logger.info(
            f"✅ Compiled prompt '{request.prompt_name}' v{langfuse_prompt.version} "
            f"for persona {request.persona_id}"
        )

        return CompilePromptResponse(
            status="success",
            prompt_name=langfuse_prompt.name,
            version=langfuse_prompt.version,
            compiled_prompt=compiled,
            config=langfuse_prompt.config or {},
            variables_used=variables,
            message=f"Prompt compiled successfully with {len(variables)} variables",
        )
    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "prompt_name": request.prompt_name,
                "version": request.version,
                "persona_id": str(request.persona_id),
            },
            tags={
                "component": "langfuse_prompts",
                "operation": "compile_prompt",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"❌ Failed to compile prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to compile prompt: {str(e)}")


@router.get("/list")
async def list_langfuse_prompts(db: AsyncSession = Depends(get_db)):
    """List all prompt templates (placeholder)."""
    raise HTTPException(
        status_code=501,
        detail="List prompts not implemented. Use Langfuse UI or REST API directly.",
    )
