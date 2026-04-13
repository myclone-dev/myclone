"""
Visitor Management Routes - Dashboard endpoints for persona owners

These endpoints allow authenticated users (persona owners) to:
1. Manage their global visitor whitelist (CRUD operations)
2. Assign/remove visitors to specific personas
3. Toggle access control on/off for personas
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt_auth import get_current_user
from shared.database.models.database import Persona, get_session
from shared.database.models.user import User
from shared.database.repositories import (
    get_persona_access_repository,
    get_visitor_whitelist_repository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Visitor Management"])


# ==================== Request/Response Models ====================


class VisitorResponse(BaseModel):
    """Visitor information response"""

    id: str
    email: str
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    created_at: datetime = Field(..., alias="createdAt")
    last_accessed_at: Optional[datetime] = Field(None, alias="lastAccessedAt")
    notes: Optional[str] = None
    assigned_persona_count: int = Field(0, alias="assignedPersonaCount")

    class Config:
        populate_by_name = True
        from_attributes = True


class VisitorListResponse(BaseModel):
    """List of visitors response"""

    visitors: List[VisitorResponse]
    total: int


class CreateVisitorRequest(BaseModel):
    """Request to add visitor to whitelist"""

    email: EmailStr
    first_name: Optional[str] = Field(None, min_length=1, max_length=100, alias="firstName")
    last_name: Optional[str] = Field(None, min_length=1, max_length=100, alias="lastName")
    notes: Optional[str] = Field(None, max_length=500)

    class Config:
        populate_by_name = True


class UpdateVisitorRequest(BaseModel):
    """Request to update visitor details"""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100, alias="firstName")
    last_name: Optional[str] = Field(None, min_length=1, max_length=100, alias="lastName")
    notes: Optional[str] = Field(None, max_length=500)

    class Config:
        populate_by_name = True


class PersonaVisitorResponse(BaseModel):
    """Visitor with persona assignment info"""

    id: str
    email: str
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    added_at: datetime = Field(..., alias="addedAt")
    last_accessed_at: Optional[datetime] = Field(None, alias="lastAccessedAt")

    class Config:
        populate_by_name = True
        from_attributes = True


class PersonaVisitorListResponse(BaseModel):
    """List of visitors assigned to persona"""

    visitors: List[PersonaVisitorResponse]
    total: int


class AssignVisitorsRequest(BaseModel):
    """Request to assign visitors to persona"""

    visitor_ids: List[str] = Field(..., min_items=1, alias="visitorIds")

    class Config:
        populate_by_name = True


class AssignVisitorsResponse(BaseModel):
    """Response from visitor assignment"""

    success: bool
    message: str
    assigned_count: int = Field(..., alias="assignedCount")


class ToggleAccessControlRequest(BaseModel):
    """Request to toggle access control"""

    is_private: bool = Field(..., alias="isPrivate")

    class Config:
        populate_by_name = True


class ToggleAccessControlResponse(BaseModel):
    """Response from access control toggle"""

    success: bool
    message: str
    is_private: bool = Field(..., alias="isPrivate")
    access_control_enabled_at: Optional[datetime] = Field(None, alias="accessControlEnabledAt")

    class Config:
        populate_by_name = True


# ==================== Visitor Whitelist Endpoints (User-level) ====================


@router.get("/users/me/visitors", response_model=VisitorListResponse)
async def list_visitors(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    List all visitors in user's global whitelist

    Returns all visitors the user has added, sorted by creation date (newest first).
    Includes count of personas each visitor is assigned to.
    """
    try:
        visitor_repo = get_visitor_whitelist_repository()
        visitors = await visitor_repo.get_all_visitors(user.id)

        # Get persona assignment counts for each visitor
        visitor_responses = []

        for visitor in visitors:
            # Count how many personas this visitor is assigned to
            # (We'll need to add this method to PersonaAccessRepository)
            from shared.database.models.persona_access import PersonaVisitor

            stmt = select(PersonaVisitor).where(PersonaVisitor.visitor_id == visitor.id)
            result = await session.execute(stmt)
            assignment_count = len(list(result.scalars().all()))

            visitor_responses.append(
                VisitorResponse(
                    id=str(visitor.id),
                    email=visitor.email,
                    firstName=visitor.first_name,
                    lastName=visitor.last_name,
                    createdAt=visitor.created_at,
                    lastAccessedAt=visitor.last_accessed_at,
                    notes=visitor.notes,
                    assignedPersonaCount=assignment_count,
                )
            )

        logger.info(f"Retrieved {len(visitor_responses)} visitors for user {user.id}")

        return VisitorListResponse(visitors=visitor_responses, total=len(visitor_responses))

    except Exception as e:
        logger.error(f"Error listing visitors for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve visitors",
        )


@router.post(
    "/users/me/visitors", response_model=VisitorResponse, status_code=status.HTTP_201_CREATED
)
async def create_visitor(
    request: CreateVisitorRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Add visitor to user's global whitelist

    Creates a new visitor entry that can later be assigned to one or more personas.
    Returns 409 if visitor email already exists in user's whitelist.
    """
    try:
        visitor_repo = get_visitor_whitelist_repository()

        # Check if visitor already exists
        existing_visitor = await visitor_repo.get_visitor_by_email(user.id, request.email)
        if existing_visitor:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Visitor with email {request.email} already exists in your whitelist",
            )

        # Create new visitor
        visitor = await visitor_repo.create_visitor(
            user_id=user.id,
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            notes=request.notes,
        )

        logger.info(f"Created visitor {visitor.id} for user {user.id}")

        return VisitorResponse(
            id=str(visitor.id),
            email=visitor.email,
            firstName=visitor.first_name,
            lastName=visitor.last_name,
            createdAt=visitor.created_at,
            lastAccessedAt=visitor.last_accessed_at,
            notes=visitor.notes,
            assignedPersonaCount=0,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating visitor for user {user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create visitor",
        )


@router.patch("/users/me/visitors/{visitor_id}", response_model=VisitorResponse)
async def update_visitor(
    visitor_id: str,
    request: UpdateVisitorRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Update visitor details (name, notes)

    Email cannot be changed. Returns 404 if visitor not found or doesn't belong to user.
    """
    try:
        visitor_repo = get_visitor_whitelist_repository()

        # Verify visitor exists and belongs to user
        try:
            visitor_uuid = UUID(visitor_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid visitor ID format",
            )

        visitor = await visitor_repo.get_visitor_by_id(visitor_uuid)

        if not visitor or visitor.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Visitor not found",
            )

        # Update visitor
        updated_visitor = await visitor_repo.update_visitor(
            visitor_id=visitor_uuid,
            first_name=request.first_name,
            last_name=request.last_name,
            notes=request.notes,
        )

        # Get assignment count
        from shared.database.models.persona_access import PersonaVisitor

        stmt = select(PersonaVisitor).where(PersonaVisitor.visitor_id == visitor_uuid)
        result = await session.execute(stmt)
        assignment_count = len(list(result.scalars().all()))

        logger.info(f"Updated visitor {visitor_id} for user {user.id}")

        return VisitorResponse(
            id=str(updated_visitor.id),
            email=updated_visitor.email,
            firstName=updated_visitor.first_name,
            lastName=updated_visitor.last_name,
            createdAt=updated_visitor.created_at,
            lastAccessedAt=updated_visitor.last_accessed_at,
            notes=updated_visitor.notes,
            assignedPersonaCount=assignment_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating visitor {visitor_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update visitor",
        )


@router.delete("/users/me/visitors/{visitor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_visitor(
    visitor_id: str,
    user: User = Depends(get_current_user),
):
    """
    Remove visitor from whitelist

    CASCADE deletes all persona assignments for this visitor.
    Returns 404 if visitor not found or doesn't belong to user.
    """
    try:
        visitor_repo = get_visitor_whitelist_repository()

        # Verify visitor exists and belongs to user
        try:
            visitor_uuid = UUID(visitor_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid visitor ID format",
            )

        visitor = await visitor_repo.get_visitor_by_id(visitor_uuid)

        if not visitor or visitor.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Visitor not found",
            )

        # Delete visitor (CASCADE deletes all persona assignments)
        deleted = await visitor_repo.delete_visitor(visitor_uuid)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Visitor not found",
            )

        logger.info(f"Deleted visitor {visitor_id} for user {user.id}")
        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting visitor {visitor_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete visitor",
        )


# ==================== Persona-Visitor Assignment Endpoints ====================


@router.get("/personas/{persona_id}/visitors", response_model=PersonaVisitorListResponse)
async def list_persona_visitors(
    persona_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    List all visitors assigned to a specific persona

    Returns visitors sorted by assignment date (newest first).
    Only persona owner can access this endpoint.
    """
    try:
        # Verify persona exists and belongs to user
        try:
            persona_uuid = UUID(persona_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid persona ID format",
            )

        stmt = select(Persona).where(Persona.id == persona_uuid, Persona.user_id == user.id)
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Persona not found",
            )

        # Get visitors assigned to this persona
        visitor_repo = get_visitor_whitelist_repository()
        visitors = await visitor_repo.get_visitors_for_persona(persona_uuid)

        # Get assignment dates
        from shared.database.models.persona_access import PersonaVisitor

        visitor_responses = []
        for visitor in visitors:
            # Get assignment date
            stmt = select(PersonaVisitor).where(
                PersonaVisitor.persona_id == persona_uuid,
                PersonaVisitor.visitor_id == visitor.id,
            )
            result = await session.execute(stmt)
            assignment = result.scalar_one_or_none()

            visitor_responses.append(
                PersonaVisitorResponse(
                    id=str(visitor.id),
                    email=visitor.email,
                    firstName=visitor.first_name,
                    lastName=visitor.last_name,
                    addedAt=assignment.added_at if assignment else visitor.created_at,
                    lastAccessedAt=visitor.last_accessed_at,
                )
            )

        logger.info(f"Retrieved {len(visitor_responses)} visitors for persona {persona_id}")

        return PersonaVisitorListResponse(visitors=visitor_responses, total=len(visitor_responses))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing visitors for persona {persona_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve persona visitors",
        )


@router.post("/personas/{persona_id}/visitors", response_model=AssignVisitorsResponse)
async def assign_visitors_to_persona(
    persona_id: str,
    request: AssignVisitorsRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Assign visitors to persona

    Accepts a list of visitor IDs to assign. Skips visitors already assigned.
    All visitor IDs must belong to the authenticated user's whitelist.
    """
    try:
        # Verify persona exists and belongs to user
        try:
            persona_uuid = UUID(persona_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid persona ID format",
            )

        stmt = select(Persona).where(Persona.id == persona_uuid, Persona.user_id == user.id)
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Persona not found",
            )

        # Convert visitor IDs to UUIDs and verify they belong to user
        visitor_uuids = []
        visitor_repo = get_visitor_whitelist_repository()

        for vid in request.visitor_ids:
            try:
                visitor_uuid = UUID(vid)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid visitor ID format: {vid}",
                )

            # Verify visitor belongs to user
            visitor = await visitor_repo.get_visitor_by_id(visitor_uuid)
            if not visitor or visitor.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Visitor {vid} not found in your whitelist",
                )

            visitor_uuids.append(visitor_uuid)

        # Assign visitors to persona
        persona_repo = get_persona_access_repository()
        assigned_count = await persona_repo.assign_multiple_visitors_to_persona(
            persona_id=persona_uuid,
            visitor_ids=visitor_uuids,
        )

        logger.info(f"Assigned {assigned_count} visitors to persona {persona_id}")

        return AssignVisitorsResponse(
            success=True,
            message=f"Successfully assigned {assigned_count} visitor(s) to persona",
            assignedCount=assigned_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning visitors to persona {persona_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign visitors",
        )


@router.delete(
    "/personas/{persona_id}/visitors/{visitor_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_visitor_from_persona(
    persona_id: str,
    visitor_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Remove visitor from persona

    Removes the persona-visitor assignment. Visitor remains in global whitelist.
    Returns 404 if persona/visitor not found or visitor not assigned.
    """
    try:
        # Verify persona exists and belongs to user
        try:
            persona_uuid = UUID(persona_id)
            visitor_uuid = UUID(visitor_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid persona or visitor ID format",
            )

        stmt = select(Persona).where(Persona.id == persona_uuid, Persona.user_id == user.id)
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Persona not found",
            )

        # Verify visitor belongs to user
        visitor_repo = get_visitor_whitelist_repository()
        visitor = await visitor_repo.get_visitor_by_id(visitor_uuid)

        if not visitor or visitor.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Visitor not found",
            )

        # Remove assignment
        persona_repo = get_persona_access_repository()
        removed = await persona_repo.remove_visitor_from_persona(
            persona_id=persona_uuid,
            visitor_id=visitor_uuid,
        )

        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Visitor not assigned to this persona",
            )

        logger.info(f"Removed visitor {visitor_id} from persona {persona_id}")
        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing visitor {visitor_id} from persona {persona_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove visitor",
        )


# ==================== Access Control Toggle Endpoint ====================


@router.patch("/personas/{persona_id}/access-control", response_model=ToggleAccessControlResponse)
async def toggle_access_control(
    persona_id: str,
    request: ToggleAccessControlRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Toggle access control (public/private) for persona

    When enabled (is_private=true), only whitelisted visitors can access.
    When disabled (is_private=false), persona is publicly accessible.
    """
    try:
        # Verify persona exists and belongs to user
        try:
            persona_uuid = UUID(persona_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid persona ID format",
            )

        stmt = select(Persona).where(Persona.id == persona_uuid, Persona.user_id == user.id)
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Persona not found",
            )

        # Update access control
        old_value = persona.is_private
        persona.is_private = request.is_private

        # Update access_control_enabled_at timestamp if enabling for first time
        if request.is_private and not old_value:
            persona.access_control_enabled_at = datetime.now()

        session.add(persona)
        await session.commit()
        await session.refresh(persona)

        status_text = "enabled" if request.is_private else "disabled"
        logger.info(f"Access control {status_text} for persona {persona_id}")

        return ToggleAccessControlResponse(
            success=True,
            message=f"Access control {status_text} successfully",
            isPrivate=persona.is_private,
            accessControlEnabledAt=persona.access_control_enabled_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling access control for persona {persona_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle access control",
        )
