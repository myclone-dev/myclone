"""Centralized RAG ingestion module for voice processing worker.

This module provides a single point of entry for ingesting content into the RAG system,
supporting both chunked and pre-chunked data ingestion for various content types
(PDF, YouTube, audio, video).
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from loguru import logger

from shared.database.voice_job_model import async_session_maker
from shared.monitoring.sentry_utils import add_breadcrumb, capture_exception_with_context
from shared.rag.rag_singleton import get_rag_system


async def ingest_chunked_content_to_rag(
    chunks: List[Dict[str, Any]],
    user_id: UUID,
    persona_id: UUID,
    source_type: str,
    source_record_id: Optional[UUID] = None,
    document_id: Optional[str] = None,
    additional_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ingest pre-chunked content into RAG system.

    This function handles content that has already been chunked (e.g., PDF chunks,
    YouTube transcript chunks, audio/video transcript chunks) and creates embeddings
    for RAG retrieval.

    Args:
        chunks: List of content chunks with text and metadata
        user_id: User UUID who owns the content
        persona_id: Persona UUID to associate content with
        source_type: Type of content ('pdf', 'youtube', 'audio', 'video')
        source_record_id: Optional source record UUID (e.g., document_id, youtube_video_id)
        document_id: Optional document ID string (for backward compatibility)
        additional_metadata: Optional metadata to merge into chunk metadata

    Returns:
        Dict with ingestion results including chunks_added count

    Raises:
        ValueError: If chunks are empty or invalid parameters
    """
    add_breadcrumb(
        f"Starting RAG ingestion: {len(chunks)} chunks",
        "rag.ingestion",
        data={
            "user_id": str(user_id),
            "document_id": document_id,
            "source_type": source_type,
        },
    )
    if not chunks:
        logger.warning(f"No chunks provided for {source_type} ingestion (user={user_id})")
        return {"status": "skipped", "chunks_added": 0, "message": "No chunks to ingest"}

    if not user_id or not persona_id:
        raise ValueError("user_id and persona_id are required for RAG ingestion")

    logger.info(
        f"📚 Starting RAG ingestion for {source_type}: "
        f"user={user_id}, persona={persona_id}, chunks={len(chunks)}"
    )

    try:
        # Convert document_id to UUID if provided
        doc_uuid = None
        if document_id:
            try:
                doc_uuid = UUID(document_id) if isinstance(document_id, str) else document_id
                logger.debug(f"✅ Converted document_id to UUID: {doc_uuid}")
            except (ValueError, AttributeError) as e:
                error_msg = f"Invalid document_id '{document_id}': {e}"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg) from e

        # Determine source_record_id (priority: explicit > document_id > user_id)
        if source_record_id:
            final_source_record_id = source_record_id
        elif doc_uuid:
            final_source_record_id = doc_uuid
        else:
            final_source_record_id = user_id

        logger.debug(
            f"�� Using source_record_id: {final_source_record_id} "
            f"(type: {type(final_source_record_id).__name__})"
        )

        # Validate source_record_id is a UUID
        if not isinstance(final_source_record_id, UUID):
            error_msg = f"source_record_id must be a UUID, got {type(final_source_record_id)}"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)

        # Prepare content sources for RAG ingestion
        content_sources = []
        skipped_chunks = 0

        for i, chunk in enumerate(chunks):
            # Extract text content (support multiple field names)
            content = chunk.get("text") or chunk.get("content") or chunk.get("vectorized_text", "")

            if not content.strip():
                logger.warning(f"⚠️ Skipping empty chunk at index {i}")
                skipped_chunks += 1
                continue

            # Build chunk metadata
            chunk_metadata = {
                # Core identifiers
                "source_record_id": str(final_source_record_id),
                "user_id": str(user_id),
                "persona_id": str(persona_id),
                "chunk_index": i,
                "chunk_id": chunk.get("chunk_id", f"{source_type}_{i}"),
                # Source information - preserve chunk's source if available, otherwise use parameter
                "source": chunk.get("source", source_type),  # Preserve chunk's source type
                "content_length": len(content),
            }

            # Add document_id if available
            if document_id:
                chunk_metadata["document_id"] = str(document_id)

            # Merge additional metadata if provided
            if additional_metadata:
                chunk_metadata.update(additional_metadata)

            # Add chunk-specific metadata (timestamps, page numbers, etc.)
            # Copy all non-text fields from original chunk
            for key, value in chunk.items():
                if key not in ["text", "content", "vectorized_text"] and key not in chunk_metadata:
                    chunk_metadata[key] = value

            # Get the actual source from chunk metadata (preserves dynamic source type)
            actual_source = chunk_metadata["source"]

            # Determine source_type for RAG categorization
            # Map content types to appropriate RAG source types
            rag_source_type = {
                "pdf": "documents",
                "audio": "documents",
                "video": "documents",
                "text": "documents",
                "markdown": "documents",
                "txt": "documents",
                "md": "documents",
                "ppt": "documents",
                "pptx": "documents",
                "xls": "documents",
                "xlsx": "documents",
                "doc": "documents",
                "docx": "documents",
                "youtube": "transcript",
            }.get(actual_source, actual_source)

            # Create content source with chunk's actual source type
            content_source = {
                "content": content,
                "source": actual_source,  # Use chunk's source, not parameter
                "source_type": rag_source_type,
                "source_record_id": final_source_record_id,
                "metadata": chunk_metadata,
            }

            content_sources.append(content_source)

        if not content_sources:
            logger.warning(
                f"⚠️ No valid content sources prepared for {source_type} (user={user_id}). "
                f"Total chunks: {len(chunks)}, Skipped: {skipped_chunks}"
            )
            return {
                "status": "failed",
                "chunks_added": 0,
                "message": f"All {len(chunks)} chunks were empty or invalid",
            }

        logger.info(
            f"✅ Prepared {len(content_sources)} content sources for RAG ingestion "
            f"(skipped {skipped_chunks} empty chunks)"
        )

        # Log sample content sources for debugging
        for i, cs in enumerate(content_sources[:3]):
            logger.debug(
                f"🔍 Content source {i}: "
                f"content_length={len(cs['content'])}, "
                f"source={cs['source']}, "
                f"source_type={cs['source_type']}, "
                f"source_record_id={cs['source_record_id']}"
            )

        # Get RAG system
        rag = await get_rag_system()

        # Ingest using pre-chunked data method (avoids re-chunking)
        logger.info(
            f"🚀 Calling RAG ingest_pre_chunked_data with {len(content_sources)} sources..."
        )

        result = await rag.ingest_pre_chunked_data(
            user_id=user_id,
            persona_id=persona_id,
            content_sources=content_sources,
        )

        chunks_added = result.get("chunks_added", 0)
        add_breadcrumb(
            f"RAG ingestion completed: {chunks_added} chunks",
            "rag.ingestion.success",
        )
        logger.info(
            f"✅ RAG ingestion completed for {source_type}: "
            f"persona_id={persona_id}, "
            f"chunks_added={chunks_added}, "
            f"chunks_expected={len(content_sources)}, "
            f"status={result.get('status', 'unknown')}"
        )

        # Warn if chunks_added doesn't match expected
        if chunks_added != len(content_sources):
            logger.warning(
                f"⚠️ Chunk count mismatch for {source_type}: "
                f"expected {len(content_sources)}, added {chunks_added}"
            )

        return result

    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "user_id": str(user_id),
                "document_id": document_id,
                "persona_id": str(persona_id),
                "source_type": source_type,
                "input_source": source_type,
                "chunk_count": len(chunks),
            },
            tags={
                "component": "voice_worker",
                "operation": "rag_ingestion",
                "source_type": source_type,
                "severity": "high",
            },
        )
        logger.error(
            f"❌ RAG ingestion failed for {source_type} (user={user_id}): {e}",
            exc_info=True,
        )
        raise


async def ingest_persona_content_to_rag(
    content_sources: List[Dict[str, Any]],
    user_id: UUID,
    persona_id: UUID,
    source_type: str,
) -> Dict[str, Any]:
    """Ingest content directly to persona using RAG's ingest_persona_data method.

    This function is used for content that should be associated with a persona
    via PersonaDataSource (e.g., YouTube videos, social media content).

    Args:
        content_sources: List of content sources with content, metadata, source_record_id
        user_id: User UUID who owns the persona
        persona_id: Persona UUID to associate content with
        source_type: Type of content ('youtube', 'linkedin', 'twitter', etc.)

    Returns:
        Dict with ingestion results including chunks_added count

    Raises:
        ValueError: If content_sources are empty or invalid parameters
    """
    if not content_sources:
        logger.warning(f"No content sources provided for {source_type} ingestion (user={user_id})")
        return {"status": "skipped", "chunks_added": 0, "message": "No content to ingest"}

    if not user_id or not persona_id:
        raise ValueError("user_id and persona_id are required for persona content ingestion")

    logger.info(
        f"📚 Starting persona RAG ingestion for {source_type}: "
        f"user={user_id}, persona={persona_id}, sources={len(content_sources)}"
    )

    try:
        # Validate all content sources have required fields
        for i, cs in enumerate(content_sources):
            if "content" not in cs or not cs["content"].strip():
                logger.warning(f"⚠️ Skipping content source {i} with empty content")
                continue

            if "source_record_id" not in cs:
                raise ValueError(f"Content source {i} missing source_record_id")

        # Get RAG system
        rag = await get_rag_system()

        # Ingest using persona data method
        logger.info(f"🚀 Calling RAG ingest_persona_data with {len(content_sources)} sources...")

        result = await rag.ingest_persona_data(
            user_id=user_id,
            persona_id=persona_id,
            content_sources=content_sources,
        )

        # Add safety check for None result
        if result is None:
            raise ValueError(
                "RAG ingestion returned None - this may indicate a configuration issue or database problem"
            )

        chunks_added = result.get("chunks_added", 0)
        logger.info(
            f"✅ Persona RAG ingestion completed for {source_type}: "
            f"persona_id={persona_id}, "
            f"chunks_added={chunks_added}, "
            f"status={result.get('status', 'unknown')}"
        )

        return result

    except Exception as e:
        logger.error(
            f"❌ Persona RAG ingestion failed for {source_type} (user={user_id}): {e}",
            exc_info=True,
        )
        raise


async def update_document_content(
    document_id: str, content_text: str, duration_seconds: int = 0
) -> None:
    """Update Document table with full content text and duration.

    This is used for audio/video transcriptions to store the full unchunked transcript
    in the document record for reference, along with the duration in seconds.

    Args:
        document_id: UUID of the document
        content_text: Full text content (unchunked)
        duration_seconds: Duration in seconds for audio/video files (default: 0)
    """
    try:
        from sqlalchemy import update

        from shared.database.models.document import Document

        logger.info(
            f"📝 Attempting to update document {document_id}: content_length={len(content_text)}, duration={duration_seconds}s"
        )

        async with async_session_maker() as session:
            stmt = (
                update(Document)
                .where(Document.id == UUID(document_id))
                .values(content_text=content_text, duration_seconds=duration_seconds)
            )
            result = await session.execute(stmt)
            await session.commit()

            # Log how many rows were actually updated
            rows_updated = result.rowcount
            logger.info(
                f"✅ Updated {rows_updated} document(s) - ID: {document_id}, content: {len(content_text)} chars, duration: {duration_seconds}s"
            )

            if rows_updated == 0:
                logger.warning(
                    f"⚠️ No rows updated for document {document_id} - document may not exist"
                )

    except Exception as e:
        logger.error(f"❌ Failed to update document {document_id} with content: {e}", exc_info=True)
        # Don't fail the job if document update fails - this is a nice-to-have
        logger.warning("⚠️ Continuing despite document update failure")


async def ensure_persona_exists(
    user_id: UUID,
    persona_id: Optional[UUID] = None,
    persona_name: str = "default",
) -> UUID:
    """Ensure a persona exists for the user, creating default if needed.

    Args:
        user_id: User UUID
        persona_id: Optional specific persona ID to use
        persona_name: Name for default persona if creating

    Returns:
        UUID of the persona (existing or newly created)

    Raises:
        ValueError: If specified persona_id doesn't exist for user
    """
    from sqlalchemy import select

    from shared.database.models.database import Persona

    async with async_session_maker() as session:
        if persona_id:
            # Verify specified persona exists for user
            persona_query = select(Persona).where(
                Persona.id == persona_id, Persona.user_id == user_id, Persona.is_active == True
            )
            persona = (await session.execute(persona_query)).scalar_one_or_none()

            if not persona:
                raise ValueError(f"Persona with ID {persona_id} not found for user {user_id}")

            logger.info(f"✅ Using existing persona: {persona.name} ({persona_id})")
            return persona.id
        else:
            # Find or create default persona
            persona_query = select(Persona).where(
                Persona.user_id == user_id,
                Persona.persona_name == persona_name,
                Persona.is_active == True,
            )
            persona = (await session.execute(persona_query)).scalar_one_or_none()

            if persona:
                logger.info(f"✅ Using existing default persona: {persona.name} ({persona.id})")
                return persona.id
            else:
                # Create default persona
                new_persona = Persona(
                    user_id=user_id,
                    persona_name=persona_name,
                    name=persona_name.title() + " Persona",
                    description=f"Auto-created {persona_name} persona for content ingestion",
                )
                session.add(new_persona)
                await session.commit()
                await session.refresh(new_persona)

                logger.info(
                    f"✅ Created new default persona: {new_persona.name} ({new_persona.id})"
                )
                return new_persona.id


async def create_persona_data_source_link(
    persona_id: UUID,
    source_type: str,
    source_record_id: UUID,
) -> None:
    """Create PersonaDataSource link if it doesn't exist.

    Args:
        persona_id: Persona UUID
        source_type: Type of source ('youtube', 'pdf', 'linkedin', etc.)
        source_record_id: UUID of the source record
    """
    from datetime import datetime, timezone

    from sqlalchemy import select

    from shared.database.models.persona_data_source import PersonaDataSource

    async with async_session_maker() as session:
        # Check if link already exists
        existing_link_query = select(PersonaDataSource).where(
            PersonaDataSource.persona_id == persona_id,
            PersonaDataSource.source_type == source_type,
            PersonaDataSource.source_record_id == source_record_id,
        )
        existing_link = (await session.execute(existing_link_query)).scalar_one_or_none()

        if existing_link:
            logger.info(
                f"♻️  PersonaDataSource link already exists: "
                f"persona={persona_id}, type={source_type}, record={source_record_id}"
            )
            return

        # Create new link
        persona_data_source = PersonaDataSource(
            persona_id=persona_id,
            source_type=source_type,
            source_record_id=source_record_id,
            enabled=True,
            source_filters={},
            enabled_at=datetime.now(timezone.utc),
        )
        session.add(persona_data_source)
        await session.commit()

        logger.info(
            f"🔗 Created PersonaDataSource link: "
            f"persona={persona_id}, type={source_type}, record={source_record_id}"
        )
