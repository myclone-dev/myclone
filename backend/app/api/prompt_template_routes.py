"""
Prompt Template Management Routes

This module handles all prompt template related endpoints including:
- Creating/inserting prompt templates
- Updating template parameters
- Deactivating templates
- Fetching templates by various criteria
"""

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.prompt_defaults_service import PromptDefaultsService
from shared.database.models.database import PromptTemplate, async_session_maker
from shared.utils.conversions import str_to_uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/prompt-templates", tags=["Prompt Templates"])


# -------------------- Constants -------------------- #

ALLOWED_TEMPLATE_TYPES = {"basic", "advance", "test"}
ALLOWED_PLATFORMS = {"openai", "custom", "local", "gemini", "qwen", "claude"}
ALLOWED_TEMPLATE_UPDATE_FIELDS = {
    "template",
    "example",
    "remarks",
    "is_active",
    "thinking_style",
    "chat_objective",
    "objective_response",
    "response_structure",
    "conversation_flow",
    "strict_guideline",
}


# -------------------- Request / Response Models -------------------- #


class PromptTemplateCreateRequest(BaseModel):
    """Request model to insert (or reactivate) a prompt template."""

    type: str
    expertise: Optional[str] = "general"
    persona_id: Optional[str] = None
    platform: str = "openai"
    template: str
    example: Optional[str] = None
    remarks: Optional[str] = None
    thinking_style: Optional[str] = None
    chat_objective: Optional[str] = None
    objective_response: Optional[str] = None
    response_structure: Optional[str] = None
    conversation_flow: Optional[str] = None
    strict_guideline: Optional[str] = None


class PromptTemplateParamUpdate(BaseModel):
    """Update a single field on a PromptTemplate (identified by id)."""

    id: UUID
    field: str
    value: Any


# -------------------- Helpers -------------------- #


def get_default_values():
    """
    Get default values for optional prompt template fields.
    Uses PromptDefaultsService for consistency across the application.

    Returns:
        dict: Dictionary of default values for optional fields
    """
    return PromptDefaultsService.get_all_defaults()


def format_template_data(template: PromptTemplate) -> dict:
    """
    Format PromptTemplate object into a dictionary for API responses.

    Args:
        template: PromptTemplate object

    Returns:
        dict: Formatted template data
    """
    return {
        "type": template.type,
        "expertise": template.expertise,
        "persona_id": str(template.persona_id) if template.persona_id else None,
        "platform": template.platform,
        "template": template.template,
        "example": template.example,
        "remarks": template.remarks,
        "thinking_style": template.thinking_style,
        "chat_objective": template.chat_objective,
        "objective_response": template.objective_response,
        "response_structure": template.response_structure,
        "conversation_flow": template.conversation_flow,
        "strict_guideline": template.strict_guideline,
        "is_active": template.is_active,
    }


async def get_db():
    """
    Database session dependency for FastAPI routes.

    Yields:
        AsyncSession: Database session for async operations
    """
    async with async_session_maker() as session:
        yield session


async def fetch_prompt_template(
    session: AsyncSession, template_type: str, expertise: Optional[str], platform: str
):
    """
    Fetch a prompt template based on type, expertise, and platform.

    Args:
        session (AsyncSession): Database session
        template_type (str): Type of template to fetch
        expertise (Optional[str]): Expertise area filter (optional)
        platform (str): Platform type filter

    Returns:
        PromptTemplate | None: Matching prompt template if found, None otherwise
    """
    stmt = select(PromptTemplate).where(
        and_(PromptTemplate.type == template_type, PromptTemplate.platform == platform)
    )
    if expertise:
        stmt = stmt.where(PromptTemplate.expertise == expertise)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def fetch_prompt_template_active(
    session: AsyncSession,
    p_type: str,
    expertise: Optional[str],
    persona_id: Optional[UUID],
    platform: str,
):
    """Fetch active prompt template by type, expertise, persona_id, and platform."""
    stmt = select(PromptTemplate).where(
        and_(
            PromptTemplate.type == p_type,
            PromptTemplate.platform == platform,
            PromptTemplate.expertise == expertise,
            PromptTemplate.persona_id == persona_id,
            PromptTemplate.is_active.is_(True),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def fetch_prompt_template_inactive(
    session: AsyncSession,
    p_type: str,
    expertise: Optional[str],
    persona_id: Optional[UUID],
    platform: str,
):
    """Fetch inactive prompt template by type, expertise, persona_id, and platform."""
    stmt = select(PromptTemplate).where(
        and_(
            PromptTemplate.type == p_type,
            PromptTemplate.platform == platform,
            PromptTemplate.expertise == expertise,
            PromptTemplate.persona_id == persona_id,
            PromptTemplate.is_active.is_(False),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def fetch_prompt_template_by_id(session: AsyncSession, template_id: UUID):
    """Fetch prompt template by ID."""
    stmt = select(PromptTemplate).where(PromptTemplate.id == template_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# -------------------- Routes -------------------- #


@router.post("/", summary="Insert or reactivate a prompt template")
async def insert_prompt_template(
    data: PromptTemplateCreateRequest, db: AsyncSession = Depends(get_db)
):
    """
    Insert a new prompt template if no active one exists for the (type, expertise, persona_id, platform) key.
    If an active template exists, return it (idempotent). If only an inactive one exists, reactivate & update it.
    """
    # Validate enums
    if data.type not in ALLOWED_TEMPLATE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid type '{data.type}'. Allowed: {sorted(ALLOWED_TEMPLATE_TYPES)}",
        )
    if data.platform not in ALLOWED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid platform '{data.platform}'. Allowed: {sorted(ALLOWED_PLATFORMS)}",
        )

    # Convert persona_id string to UUID if provided
    persona_id_uuid = str_to_uuid(data.persona_id) if data.persona_id else None

    active = await fetch_prompt_template_active(
        db, data.type, data.expertise, persona_id_uuid, data.platform
    )
    if active:
        return {
            "status": "success",
            "action": "existing",
            "template_id": active.id,
            "message": "Active prompt template already exists",
            "data": format_template_data(active),
        }

    inactive = await fetch_prompt_template_inactive(
        db, data.type, data.expertise, persona_id_uuid, data.platform
    )
    if inactive:
        # Reactivate and update with defaults for optional fields
        defaults = get_default_values()
        inactive.template = data.template
        inactive.example = data.example
        inactive.remarks = data.remarks
        inactive.thinking_style = data.thinking_style or defaults["thinking_style"]
        inactive.chat_objective = data.chat_objective or defaults["chat_objective"]
        inactive.objective_response = data.objective_response or defaults["objective_response"]
        inactive.response_structure = data.response_structure or defaults["response_structure"]
        inactive.conversation_flow = data.conversation_flow or defaults["conversation_flow"]
        inactive.strict_guideline = data.strict_guideline or defaults["strict_guideline"]
        inactive.is_active = True
        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=409, detail="Conflict: Could not reactivate template"
            ) from e
        return {
            "status": "success",
            "action": "reactivated",
            "template_id": inactive.id,
            "message": "Inactive template reactivated and updated",
            "data": {
                "type": inactive.type,
                "expertise": inactive.expertise,
                "persona_id": str(inactive.persona_id) if inactive.persona_id else None,
                "platform": inactive.platform,
                "template": inactive.template,
                "example": inactive.example,
                "remarks": inactive.remarks,
                "is_active": inactive.is_active,
            },
        }

    # Create new template with defaults for optional fields
    defaults = get_default_values()
    new_template = PromptTemplate(
        type=data.type,
        expertise=data.expertise,
        persona_id=persona_id_uuid,
        platform=data.platform,
        template=data.template,
        example=data.example,
        remarks=data.remarks,
        thinking_style=data.thinking_style or defaults["thinking_style"],
        chat_objective=data.chat_objective or defaults["chat_objective"],
        objective_response=data.objective_response or defaults["objective_response"],
        response_structure=data.response_structure or defaults["response_structure"],
        conversation_flow=data.conversation_flow or defaults["conversation_flow"],
        strict_guideline=data.strict_guideline or defaults["strict_guideline"],
        is_active=True,
    )
    db.add(new_template)
    try:
        await db.commit()
        await db.refresh(new_template)
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Conflict: Could not insert template") from e

    return {
        "status": "success",
        "action": "created",
        "template_id": new_template.id,
        "message": "New prompt template created",
        "data": format_template_data(new_template),
    }


@router.patch("/update-parameter", summary="Update a single template field")
async def update_prompt_template_parameter(
    data: PromptTemplateParamUpdate, db: AsyncSession = Depends(get_db)
):
    """
    Update a single mutable field on a prompt template.
    Allowed fields: template, example, remarks, is_active.
    Does not allow changing identifying dimensions (type/platform/etc.).
    """
    field = data.field.strip()
    if field not in ALLOWED_TEMPLATE_UPDATE_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Field '{field}' is not allowed. Allowed: {sorted(ALLOWED_TEMPLATE_UPDATE_FIELDS)}",
        )

    tmpl = await fetch_prompt_template_by_id(db, data.id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    # Boolean coercion for is_active
    if field == "is_active":
        if isinstance(data.value, str):
            val = data.value.lower()
            if val in {"true", "1", "yes", "y"}:
                setattr(tmpl, field, True)
            elif val in {"false", "0", "no", "n"}:
                setattr(tmpl, field, False)
            else:
                raise HTTPException(status_code=400, detail="Invalid boolean string for is_active")
        else:
            setattr(tmpl, field, bool(data.value))
    else:
        setattr(tmpl, field, str(data.value) if data.value is not None else None)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Update violates uniqueness constraint") from e

    return {
        "status": "success",
        "action": "template_field_updated",
        "template_id": tmpl.id,
        "field": field,
        "value": getattr(tmpl, field),
        "message": f"Template field '{field}' updated successfully",
    }


@router.patch("/{template_id}/deactivate", summary="Deactivate a prompt template")
async def deactivate_prompt_template(template_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Deactivate (soft delete) a prompt template by setting is_active = False.
    If already inactive, returns idempotent response.
    """
    tmpl = await fetch_prompt_template_by_id(db, template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    if not tmpl.is_active:
        return {
            "status": "success",
            "action": "already_inactive",
            "template_id": tmpl.id,
            "message": "Prompt template already inactive",
        }
    tmpl.is_active = False
    await db.commit()
    return {
        "status": "success",
        "action": "deactivated_template",
        "template_id": tmpl.id,
        "message": "Prompt template deactivated",
    }


@router.get("/{template_id}", summary="Get template by ID")
async def get_prompt_template(template_id: UUID, db: AsyncSession = Depends(get_db)):
    """Fetch a prompt template by its ID."""
    tmpl = await fetch_prompt_template_by_id(db, template_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    return {
        "status": "success",
        "template": {
            "id": tmpl.id,
            "type": tmpl.type,
            "expertise": tmpl.expertise,
            "persona_id": str(tmpl.persona_id) if tmpl.persona_id else None,
            "platform": tmpl.platform,
            "template": tmpl.template,
            "example": tmpl.example,
            "remarks": tmpl.remarks,
            "is_active": tmpl.is_active,
            "created_at": tmpl.created_at,
            "updated_at": tmpl.updated_at,
        },
    }


@router.get("/", summary="List all active prompt templates")
async def list_prompt_templates(
    platform: Optional[str] = None,
    template_type: Optional[str] = None,
    expertise: Optional[str] = None,
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    List prompt templates with optional filters.

    Args:
        platform: Filter by platform (openai, custom, etc.)
        template_type: Filter by type (basic, advance, test)
        expertise: Filter by expertise area
        include_inactive: Include inactive templates in results
    """
    stmt = select(PromptTemplate)

    # Apply filters
    filters = []
    if platform:
        filters.append(PromptTemplate.platform == platform)
    if template_type:
        filters.append(PromptTemplate.type == template_type)
    if expertise:
        filters.append(PromptTemplate.expertise == expertise)
    if not include_inactive:
        filters.append(PromptTemplate.is_active.is_(True))

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(PromptTemplate.created_at.desc())

    result = await db.execute(stmt)
    templates = result.scalars().all()

    template_list = []
    for t in templates:
        template_data = format_template_data(t)
        template_data["id"] = t.id
        template_data["created_at"] = t.created_at
        template_data["updated_at"] = t.updated_at
        template_list.append(template_data)

    return {
        "status": "success",
        "count": len(templates),
        "templates": template_list,
    }
