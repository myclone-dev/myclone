"""
Vector Embedding Service for Document Processing

Creates vector embeddings for processed document chunks using LlamaIndex
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.database import get_session
from shared.database.models.embeddings import VoyageLiteEmbedding
from shared.rag.rag_singleton import get_rag_system

logger = logging.getLogger(__name__)


class DocumentVectorService:
    """Service for creating vector embeddings from document chunks"""

    def __init__(self):
        # Use singleton pattern to share the same RAG instance across workers
        self.llama_rag = None  # Will be initialized lazily via get_rag_system()

    async def _get_rag_system(self):
        """Get the singleton RAG system instance"""
        if self.llama_rag is None:
            self.llama_rag = await get_rag_system()
        return self.llama_rag

    async def create_embeddings_for_chunks(
        self,
        user_id: UUID,
        document_id: UUID,
        chunks: List[Dict[str, Any]],
        source_type: str,  # 'pdf', 'audio', 'video'
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Create vector embeddings for document chunks

        Args:
            user_id: User who owns the document
            document_id: Document ID to use as source_record_id
            chunks: List of processed chunks from document
            source_type: Type of document ('pdf', 'audio', 'video')
            session: Optional database session

        Returns:
            Dict with embedding creation results
        """
        try:
            logger.info(f"Creating embeddings for {len(chunks)} {source_type} chunks")

            # Convert chunks to LlamaIndex format
            content_sources = []
            for i, chunk in enumerate(chunks):
                # Extract text content based on chunk type
                if source_type == "pdf":
                    text_content = chunk.get("text", "")
                    metadata = {
                        "chunk_index": i,
                        "page_number": chunk.get("page_number"),
                        "word_count": chunk.get("word_count", 0),
                        "character_count": chunk.get("character_count", 0),
                        "has_images": chunk.get("has_images", False),
                        "image_descriptions": chunk.get("image_descriptions", []),
                    }
                elif source_type in ["audio", "video"]:
                    text_content = chunk.get("text", "")
                    metadata = {
                        "chunk_index": i,
                        "start_time": chunk.get("start_time", 0),
                        "end_time": chunk.get("end_time", 0),
                        "duration": chunk.get("duration", 0),
                        "confidence": chunk.get("confidence", 1.0),
                        "speaker": chunk.get("speaker"),
                        "token_count": chunk.get("token_count", 0),
                    }
                else:
                    logger.warning(f"Unknown source type: {source_type}")
                    continue

                if not text_content.strip():
                    logger.warning(f"Empty text content in chunk {i}, skipping")
                    continue

                content_sources.append(
                    {
                        "content": text_content,
                        "source": "document",
                        "source_type": source_type,
                        "source_record_id": document_id,
                        "metadata": {
                            **metadata,
                            "document_id": str(document_id),
                            "user_id": str(user_id),
                            "source": "document",
                            "source_type": source_type,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        },
                    }
                )

            if not content_sources:
                logger.warning("No valid content sources to create embeddings for")
                return {
                    "success": False,
                    "message": "No valid content found to create embeddings",
                    "embeddings_created": 0,
                }

            # Create embeddings using LlamaRAG system
            # Note: We use a dummy persona_id since this is for document ingestion

            # Get or create default persona for the user
            if not session:
                async with get_session() as session:
                    return await self._create_embeddings_with_session(
                        user_id, document_id, content_sources, source_type, session
                    )
            else:
                return await self._create_embeddings_with_session(
                    user_id, document_id, content_sources, source_type, session
                )

        except Exception as e:
            logger.error(
                f"Failed to create embeddings for {source_type} document {document_id}: {e}"
            )
            return {
                "success": False,
                "message": f"Failed to create embeddings: {str(e)}",
                "embeddings_created": 0,
                "error": str(e),
            }

    async def _create_embeddings_with_session(
        self,
        user_id: UUID,
        document_id: UUID,
        content_sources: List[Dict[str, Any]],
        source_type: str,
        session: AsyncSession,
    ) -> Dict[str, Any]:
        """Create embeddings with provided session"""
        from sqlalchemy import select

        from shared.database.models.database import Persona

        # Get default persona for user
        stmt = select(Persona).where(
            Persona.user_id == user_id, Persona.persona_name == "default", Persona.is_active == True
        )
        result = await session.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            # Create default persona if it doesn't exist
            persona = Persona(
                user_id=user_id,
                persona_name="default",
                name="Default Persona",
                description="Default persona for document ingestion",
            )
            session.add(persona)
            await session.flush()
            await session.refresh(persona)

        # Get singleton RAG system instance (FIXED: now uses singleton)
        llama_rag = await self._get_rag_system()

        # Ingest data using LlamaRAG system
        ingestion_result = await llama_rag.ingest_persona_data(
            user_id=user_id,
            persona_id=persona.id,
            content_sources=content_sources,
            source_record_id=document_id,
        )

        if not ingestion_result.get("success", False):
            raise Exception(
                f"LlamaRAG ingestion failed: {ingestion_result.get('error', 'Unknown error')}"
            )

        # Update the custom columns in embeddings table
        # LlamaIndex creates embeddings with only core columns, we need to populate our custom columns
        embeddings_created = ingestion_result.get("embeddings_created", 0)

        if embeddings_created > 0:
            # Update embeddings with our custom metadata
            stmt = (
                update(VoyageLiteEmbedding)
                .where(
                    VoyageLiteEmbedding.user_id.is_(
                        None
                    ),  # Find newly created embeddings without user_id
                    VoyageLiteEmbedding.metadata_["document_id"].astext == str(document_id),
                )
                .values(
                    user_id=user_id,
                    source_record_id=document_id,
                    source="document",
                    source_type=source_type,
                    created_at=datetime.now(timezone.utc),
                )
            )

            await session.execute(stmt)
            await session.commit()

            logger.info(
                f"Successfully created {embeddings_created} embeddings for {source_type} document {document_id}"
            )

        return {
            "success": True,
            "message": f"Successfully created {embeddings_created} embeddings",
            "embeddings_created": embeddings_created,
            "chunks_processed": len(content_sources),
            "persona_id": str(persona.id),
        }


# Singleton instance
_vector_service: Optional[DocumentVectorService] = None


def get_document_vector_service() -> DocumentVectorService:
    """Get singleton document vector service instance"""
    global _vector_service
    if _vector_service is None:
        _vector_service = DocumentVectorService()
    return _vector_service
