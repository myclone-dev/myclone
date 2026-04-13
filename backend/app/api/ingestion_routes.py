import asyncio
import json
import logging
from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.extractors import PatternExtractor
from app.ingestion.processor import FileProcessor, TranscriptProcessor
from shared.database.models.database import get_session
from shared.database.models.embeddings import VoyageLiteEmbedding
from shared.database.models.persona_data_source import PersonaDataSource
from shared.database.repositories.persona_repository import PersonaRepository
from shared.rag.llama_rag import LlamaRAGSystem

logger = logging.getLogger(__name__)

# Import LlamaIndex PDF processor (native LlamaIndex readers, no API key)
try:
    from app.ingestion.llamaindex_pdf_processor import get_llamaindex_pdf_processor

    LLAMAINDEX_PDF_AVAILABLE = True
    logger.info("✅ LlamaIndex PDF readers available for enhanced parsing")
except ImportError:
    LLAMAINDEX_PDF_AVAILABLE = False
    get_llamaindex_pdf_processor = None
    logger.info("ℹ️ LlamaIndex PDF readers not available, using basic pypdf")
from app.auth.sse_compatible_auth import require_api_key_sse_compatible
from shared.constants import (
    ALL_SOURCE_TYPES,
    SOURCE_TYPE_LINKEDIN,
    SOURCE_TYPE_PDF,
    SOURCE_TYPE_TWITTER,
    SOURCE_TYPE_WEBSITE,
)

router = APIRouter(prefix="/api/v1/ingestion", tags=["Data Ingestion"])


class DataIngestionService:
    """Service to handle raw data ingestion from external services"""

    def __init__(self):
        self.transcript_processor = TranscriptProcessor()
        self.pattern_extractor = PatternExtractor()
        self.file_processor = FileProcessor()

        # Use LlamaIndex PDF readers for enhanced parsing (no API key required)
        if LLAMAINDEX_PDF_AVAILABLE:
            self.pdf_processor = get_llamaindex_pdf_processor()
        else:
            self.pdf_processor = None

        self.llama_rag = LlamaRAGSystem()  # LlamaRAGSystem for ingestion


# Initialize service
data_ingestion_service = DataIngestionService()


@router.get("/persona/{persona_id}/data-sources")
async def get_persona_data_sources(persona_id: UUID, session: AsyncSession = Depends(get_session)):
    """Get all data sources for a persona"""
    try:
        result = await session.execute(
            select(PersonaDataSource).where(PersonaDataSource.persona_id == persona_id)
        )
        data_sources = result.scalars().all()

        return {
            "persona_id": str(persona_id),
            "data_sources": [
                {
                    "id": str(source.id),
                    "source_type": source.source_type,
                    "source_record_id": (
                        str(source.source_record_id) if source.source_record_id else None
                    ),
                    "enabled": source.enabled,
                    "created_at": source.created_at,
                    "enabled_at": source.enabled_at,
                    "disabled_at": source.disabled_at,
                }
                for source in data_sources
            ],
        }

    except Exception as e:
        logger.error(f"Error getting data sources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve data sources: {str(e)}")


# =============================================================================
# SPECIALIZED EXPERT CLONE ENDPOINTS
# =============================================================================


@router.get("/expert-status/{username}", response_model=Dict[str, Any])
async def get_expert_status(
    username: str,
    persona_name: str = "default",  # Optional query param, defaults to "default"
    session: AsyncSession = Depends(get_session),
    api_key_valid: bool = Depends(require_api_key_sse_compatible),
):
    """
    Get the enrichment status and chat availability for an expert profile

    Returns:
    {
        "username": "expert123",
        "persona_id": "uuid",
        "enrichment_status": {
            "linkedin_completed": true,
            "website_completed": false,
            "twitter_completed": true
        },
        "chat_enabled": true,
        "total_chunks_processed": 45,
        "last_updated": "2024-01-01T00:00:00Z"
    }
    """
    try:
        # Find persona by User.username + persona_name
        persona = await PersonaRepository.get_by_username_and_persona(
            session, username, persona_name
        )
        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"Expert profile '{username}' (persona: {persona_name}) not found",
            )

        # Get data sources from persona_data_sources
        sources_result = await session.execute(
            select(PersonaDataSource).where(PersonaDataSource.persona_id == persona.id)
        )
        data_sources = sources_result.scalars().all()

        # Check completion status for each source type (completed = has source_record_id)
        enrichment_status = {
            "linkedin_completed": False,
            "website_completed": False,
            "twitter_completed": False,
            "pdf_completed": False,
        }

        last_updated = persona.created_at

        for source in data_sources:
            # Source is "completed" if it has a source_record_id (linked to actual data)
            is_completed = source.source_record_id is not None

            if source.source_type == SOURCE_TYPE_LINKEDIN and is_completed:
                enrichment_status["linkedin_completed"] = True
                if source.updated_at and source.updated_at > last_updated:
                    last_updated = source.updated_at
            elif source.source_type == SOURCE_TYPE_WEBSITE and is_completed:
                enrichment_status["website_completed"] = True
                if source.updated_at and source.updated_at > last_updated:
                    last_updated = source.updated_at
            elif source.source_type == SOURCE_TYPE_TWITTER and is_completed:
                enrichment_status["twitter_completed"] = True
                if source.updated_at and source.updated_at > last_updated:
                    last_updated = source.updated_at
            elif source.source_type in [SOURCE_TYPE_PDF, "document"] and is_completed:
                enrichment_status["pdf_completed"] = True
                if source.updated_at and source.updated_at > last_updated:
                    last_updated = source.updated_at

        # Count total content chunks (embeddings accessible by this persona)
        rag_system = LlamaRAGSystem()
        source_record_ids = await rag_system.get_persona_source_record_ids(persona.id)

        if source_record_ids:
            chunks_result = await session.execute(
                select(func.count(VoyageLiteEmbedding.id)).where(
                    VoyageLiteEmbedding.source_record_id.in_(source_record_ids)
                )
            )
            total_chunks = chunks_result.scalar() or 0
        else:
            total_chunks = 0

        # Chat is enabled if ANY enrichment is complete
        chat_enabled = any(enrichment_status.values())

        return {
            "username": username,
            "persona_id": str(persona.id),
            "enrichment_status": enrichment_status,
            "chat_enabled": chat_enabled,
            "total_chunks_processed": total_chunks,
            "last_updated": last_updated.isoformat() if last_updated else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expert status: {e}")
        raise HTTPException(status_code=500, detail=f"Status retrieval failed: {str(e)}")


@router.get("/expert-status-stream/{username}")
async def stream_expert_status(
    username: str,
    persona_name: str = "default",  # Optional query param, defaults to "default"
    session: AsyncSession = Depends(get_session),
    api_key_valid: bool = Depends(require_api_key_sse_compatible),
):
    """
    SSE stream for real-time expert enrichment status updates

    Sends events like:
    data: {"type": "linkedin_complete", "chunks_added": 25, "chat_enabled": true}
    data: {"type": "website_complete", "chunks_added": 15, "chat_enabled": true}
    data: {"type": "twitter_complete", "chunks_added": 8, "chat_enabled": true}
    """

    async def event_generator():
        # Find persona by User.username + persona_name
        persona = await PersonaRepository.get_by_username_and_persona(
            session, username, persona_name
        )
        if not persona:
            yield f'event: error\ndata: {{"error": "Expert profile \'{username}\' (persona: {persona_name}) not found"}}\n\n'
            return

        # Track previous state
        previous_status = {
            "linkedin_completed": False,
            "website_completed": False,
            "twitter_completed": False,
            "pdf_completed": False,
        }
        previous_chunks = 0

        # Initial status check
        try:
            sources_result = await session.execute(
                select(PersonaDataSource).where(PersonaDataSource.persona_id == persona.id)
            )
            data_sources = sources_result.scalars().all()

            for source in data_sources:
                # Source is "completed" if it has a source_record_id
                if source.source_type in previous_status and source.source_record_id is not None:
                    previous_status[f"{source.source_type}_completed"] = True

            # Count embeddings accessible by this persona
            rag_system = LlamaRAGSystem()
            source_record_ids = await rag_system.get_persona_source_record_ids(persona.id)

            if source_record_ids:
                chunks_result = await session.execute(
                    select(func.count(VoyageLiteEmbedding.id)).where(
                        VoyageLiteEmbedding.source_record_id.in_(source_record_ids)
                    )
                )
                previous_chunks = chunks_result.scalar() or 0
            else:
                previous_chunks = 0
        except Exception as e:
            logger.error(f"Error in initial status check: {e}")

        # Send initial status
        chat_enabled = any(previous_status.values())
        yield f"event: status\ndata: {json.dumps({**previous_status, 'chat_enabled': chat_enabled, 'total_chunks': previous_chunks})}\n\n"

        # Poll for changes every 2 seconds
        while True:
            try:
                await asyncio.sleep(2)

                # Get fresh session for each check
                from shared.database.models.database import async_session_maker

                async with async_session_maker() as fresh_session:
                    # Check current status
                    sources_result = await fresh_session.execute(
                        select(PersonaDataSource).where(PersonaDataSource.persona_id == persona.id)
                    )
                    data_sources = sources_result.scalars().all()

                    current_status = {
                        "linkedin_completed": False,
                        "website_completed": False,
                        "twitter_completed": False,
                        "pdf_completed": False,
                    }

                    for source in data_sources:
                        # Source is "completed" if it has a source_record_id
                        if (
                            source.source_type in ALL_SOURCE_TYPES
                            and source.source_record_id is not None
                        ):
                            current_status[f"{source.source_type}_completed"] = True

                    # Check for changes
                    for source_type in [
                        SOURCE_TYPE_LINKEDIN,
                        SOURCE_TYPE_WEBSITE,
                        SOURCE_TYPE_TWITTER,
                        SOURCE_TYPE_PDF,
                    ]:
                        key = f"{source_type}_completed"
                        if current_status[key] and not previous_status[key]:
                            # New completion detected - count embeddings accessible by this persona
                            fresh_rag_system = LlamaRAGSystem()
                            source_record_ids = (
                                await fresh_rag_system.get_persona_source_record_ids(persona.id)
                            )

                            if source_record_ids:
                                chunks_result = await fresh_session.execute(
                                    select(func.count(VoyageLiteEmbedding.id)).where(
                                        VoyageLiteEmbedding.source_record_id.in_(source_record_ids)
                                    )
                                )
                                current_chunks = chunks_result.scalar() or 0
                            else:
                                current_chunks = 0

                            chunks_added = current_chunks - previous_chunks

                            chat_enabled = True  # Any completion enables chat

                            event_data = {
                                "type": f"{source_type}_complete",
                                "chunks_added": chunks_added,
                                "chat_enabled": chat_enabled,
                                "total_chunks": current_chunks,
                            }

                            yield f"event: enrichment_complete\ndata: {json.dumps(event_data)}\n\n"

                            previous_chunks = current_chunks

                    previous_status = current_status

            except Exception as e:
                logger.error(f"Error in status stream: {e}")
                yield f'event: error\ndata: {{"error": "Stream error: {str(e)}"}}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )
