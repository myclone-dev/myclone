"""
Knowledge Library API Routes

Endpoints for managing user's knowledge library:
- View all knowledge sources
- Get source details
- Delete knowledge sources
- Re-ingest knowledge sources
"""

import logging
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.jwt_auth import get_current_user
from app.services.knowledge_library_service import get_knowledge_library_service
from shared.database.models.user import User
from shared.schemas.knowledge_library import (
    DeleteKnowledgeSourceResponse,
    KnowledgeLibraryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge-library", tags=["Knowledge Library"])


@router.get(
    "/users/{user_id}",
    response_model=KnowledgeLibraryResponse,
    summary="Get user's knowledge library",
    description="""
    Get all knowledge sources for a user, grouped by type.

    Returns:
    - LinkedIn profiles with post/experience counts
    - Twitter profiles with tweet counts
    - Website scrapes with page counts
    - Documents with metadata
    - YouTube videos with transcript status

    Each source includes:
    - Embeddings count
    - Number of personas using it
    - Platform-specific metadata
    """,
)
async def get_user_knowledge_library(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
) -> KnowledgeLibraryResponse:
    """Get all knowledge sources for a user"""
    try:
        # Authorization check - users can only access their own knowledge library
        if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this user's knowledge library",
            )

        service = get_knowledge_library_service()
        library = await service.get_user_knowledge_library(user_id)
        return library
    except Exception as e:
        logger.error(f"Error fetching knowledge library for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch knowledge library: {str(e)}",
        )


@router.get(
    "/{source_type}/{source_id}",
    response_model=Dict[str, Any],
    summary="Get knowledge source details",
    description="""
    Get detailed information about a specific knowledge source.

    Returns:
    - Source metadata
    - Embeddings count
    - List of personas using this source
    - Preview of chunks (first 5)
    """,
)
async def get_knowledge_source_detail(
    source_type: str,
    source_id: UUID,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get detailed info about a specific knowledge source"""
    try:
        service = get_knowledge_library_service()

        # Get personas using this source
        personas = await service.get_personas_using_source(source_id)

        # TODO: Add chunk preview functionality if needed
        # For now, return basic info
        return {
            "source_type": source_type,
            "source_id": str(source_id),
            "used_by_personas": personas,
            "personas_count": len(personas),
        }
    except Exception as e:
        logger.error(f"Error fetching knowledge source {source_type}/{source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch knowledge source details: {str(e)}",
        )


@router.delete(
    "/{source_type}/{source_id}",
    response_model=DeleteKnowledgeSourceResponse,
    summary="Delete knowledge source",
    description="""
    Delete a knowledge source and all its embeddings.

    WARNING: This is destructive and cascades to:
    - All embeddings for this source
    - All persona attachments (persona_data_sources)
    - The source record itself

    Personas using this source will lose access to it.
    """,
)
async def delete_knowledge_source(
    source_type: str,
    source_id: UUID,
    current_user: User = Depends(get_current_user),
) -> DeleteKnowledgeSourceResponse:
    """Delete a knowledge source and all its embeddings"""
    try:
        service = get_knowledge_library_service()

        # Verify ownership before deletion
        source_owner_id = await service.get_source_owner_id(source_type, source_id)
        if not source_owner_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Knowledge source {source_type}/{source_id} not found",
            )

        if source_owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this knowledge source",
            )

        # Perform deletion
        embeddings_deleted, personas_affected = await service.delete_knowledge_source(
            source_type, source_id, current_user.id
        )

        return DeleteKnowledgeSourceResponse(
            success=True,
            source_type=source_type,
            source_record_id=source_id,
            embeddings_deleted=embeddings_deleted,
            personas_affected=personas_affected,
            message=f"Successfully deleted {source_type} source. "
            f"Removed {embeddings_deleted} embeddings and "
            f"detached from {personas_affected} persona(s).",
        )
    except Exception as e:
        logger.error(f"Error deleting knowledge source {source_type}/{source_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete knowledge source: {str(e)}",
        )


# TODO: Implement re-ingestion endpoint when needed
# @router.post(
#     "/{source_type}/{source_id}/re-ingest",
#     response_model=ReIngestKnowledgeSourceResponse,
#     summary="Re-ingest knowledge source",
#     description="""
#     Delete existing embeddings and re-ingest this source.
#     Useful when ingestion logic changes or content updates.
#     """,
# )
# async def re_ingest_knowledge_source(
#     source_type: str,
#     source_id: UUID,
#     current_user: User = Depends(get_current_user),
# ) -> ReIngestKnowledgeSourceResponse:
#     """Re-ingest a knowledge source"""
#     # Implementation would:
#     # 1. Delete old embeddings
#     # 2. Call ingestion service to re-process
#     # 3. Return statistics
#     pass
