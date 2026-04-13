"""
Document utility functions for duplicate detection and management
"""

import hashlib
import logging
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.document import Document
from shared.database.models.embeddings import VoyageLiteEmbedding
from shared.database.models.persona_data_source import PersonaDataSource

logger = logging.getLogger(__name__)


def calculate_file_checksum(content: bytes) -> str:
    """
    Calculate SHA-256 checksum of file content.

    Args:
        content: File content as bytes

    Returns:
        Hexadecimal string representation of SHA-256 hash
    """
    return hashlib.sha256(content).hexdigest()


async def check_document_dependency(
    session: AsyncSession,
    user_id: UUID,
    checksum: str,
) -> Tuple[Optional[Document], bool]:
    """
    Check if document exists by checksum and verify embeddings existence.

    Args:
        session: Database session
        user_id: User UUID
        checksum: SHA-256 checksum of file content

    Returns:
        Tuple of (Document, has_embeddings):
        - Document: Document object if exists, None otherwise
        - has_embeddings: True if embeddings exist in data_llamalite_embeddings
    """
    # Find document by checksum
    logger.info(f"Checksum check for user {user_id} with checksum {checksum}")
    stmt = select(Document).where(Document.user_id == user_id, Document.checksum == checksum)
    result = await session.execute(stmt)
    document = result.scalar_one_or_none()

    if not document:
        logger.info(f"No existing document found for user {user_id} with checksum {checksum}")
        return None, False

    # Check if embeddings exist in data_llamalite_embeddings table
    # Embeddings are linked via source_record_id (more reliable than metadata_->>'document_id')
    try:
        stmt = select(VoyageLiteEmbedding).where(
            VoyageLiteEmbedding.source_record_id == document.id
        )
        result = await session.execute(stmt)
        embeddings = result.scalars().all()
        has_embeddings = len(embeddings) > 0

        logger.info(
            f"Document {document.id} exists. Embeddings present: {has_embeddings} (count: {len(embeddings)})"
        )

    except Exception as e:
        logger.warning(f"Could not check embeddings existence: {e}")
        has_embeddings = False

    return document, has_embeddings


async def cleanup_document_data(
    session: AsyncSession, document_id: UUID, persona_id: Optional[UUID] = None
) -> None:
    """
    Clean up document, embeddings, and persona data source.
    Used for force re-upload scenarios.

    Args:
        session: Database session
        document_id: Document UUID to clean up
        persona_id: Optional persona UUID (if provided, only delete data source for this persona)

    Note:
        This function does NOT commit the session. The caller is responsible for
        committing the transaction after all operations are complete.

        Row-level locking is used to prevent race conditions when checking for
        duplicate documents during concurrent uploads of the same file.
    """
    # Acquire row-level lock on the document to prevent race conditions
    # This ensures that concurrent requests for the same document will be serialized
    stmt = select(Document).where(Document.id == document_id).with_for_update()
    result = await session.execute(stmt)
    locked_document = result.scalar_one_or_none()

    if not locked_document:
        logger.warning(f"Document {document_id} not found for cleanup")
        return

    logger.info(f"Acquired row lock on document {document_id} for cleanup")

    # Delete embeddings from data_llamalite_embeddings using source_record_id
    try:
        stmt = delete(VoyageLiteEmbedding).where(
            VoyageLiteEmbedding.source_record_id == document_id
        )
        result = await session.execute(stmt)
        deleted_count = result.rowcount
        logger.info(f"Deleted {deleted_count} embeddings for document {document_id}")
    except Exception as e:
        logger.warning(f"Error deleting embeddings: {e}")

    # Delete persona_data_source entries
    if persona_id:
        # Only delete for specific persona
        stmt = delete(PersonaDataSource).where(
            PersonaDataSource.persona_id == persona_id,
            PersonaDataSource.source_record_id == document_id,
        )
    else:
        # Delete all persona data sources for this document
        stmt = delete(PersonaDataSource).where(PersonaDataSource.source_record_id == document_id)

    result = await session.execute(stmt)
    logger.info(f"Deleted {result.rowcount} persona_data_source entries for document {document_id}")

    # Delete document
    stmt = delete(Document).where(Document.id == document_id)
    await session.execute(stmt)

    # Flush changes but don't commit - let caller control transaction
    await session.flush()
    logger.info(f"Cleaned up document {document_id} and associated data (pending commit)")


async def delete_document_embeddings(session: AsyncSession, document_id: UUID) -> int:
    """
    Delete embeddings for a document from data_llamalite_embeddings.

    Args:
        session: Database session
        document_id: Document UUID

    Returns:
        Number of embeddings deleted
    """
    try:
        stmt = delete(VoyageLiteEmbedding).where(
            VoyageLiteEmbedding.source_record_id == document_id
        )
        result = await session.execute(stmt)
        deleted_count = result.rowcount
        logger.info(
            f"Deleted {deleted_count} embeddings from data_llamalite_embeddings for document {document_id}"
        )
        return deleted_count
    except Exception as e:
        logger.error(
            f"Error deleting embeddings from data_llamalite_embeddings for document {document_id}: {e}"
        )
        raise
