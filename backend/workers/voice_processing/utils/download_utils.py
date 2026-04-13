"""Download utilities for voice processing worker."""

import asyncio
import os
from typing import Optional

import aiohttp
from loguru import logger

from shared.voice_processing.errors import ErrorCode, VoiceProcessingError


async def download_document_from_url(
    url: str, temp_path: str, document_id: Optional[str] = None
) -> str:
    """Download document from URL and update document metadata if document_id is provided.

    Optimized for AWS signed URLs and other temporary download URLs.

    Args:
        url: Document URL to download (often AWS signed URL)
        temp_path: Temporary file path to save to
        document_id: Optional document ID to update metadata

    Returns:
        Path to downloaded file

    Raises:
        VoiceProcessingError: If download fails
    """
    try:
        # Configure session with appropriate timeouts for large files
        timeout = aiohttp.ClientTimeout(total=3600, connect=30)  # 1 hour total, 30s connect

        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Add appropriate headers for AWS and other cloud storage
            headers = {
                "User-Agent": "VoiceProcessingWorker/1.0",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate",
            }

            async with session.get(url, headers=headers) as response:
                if response.status not in [200, 206]:  # 206 for partial content
                    # Use RATE_LIMITED for retryable HTTP errors, DOWNLOAD_FAILED for others
                    error_code = (
                        ErrorCode.RATE_LIMITED
                        if response.status in [429, 500, 502, 503, 504]
                        else ErrorCode.DOWNLOAD_FAILED
                    )
                    raise VoiceProcessingError(
                        message=f"Failed to download document: HTTP {response.status} - {response.reason}",
                        error_code=error_code,
                    )

                # Extract filename with AWS signed URL awareness
                filename = url.split("/")[-1].split("?")[0]

                # Get content length for progress tracking
                content_length = response.headers.get("Content-Length")
                if content_length:
                    content_length = int(content_length)
                    logger.info(f"Downloading document: {filename} ({content_length} bytes)")
                else:
                    logger.info(f"Downloading document: {filename} (size unknown)")

                # Download content to temp file with progress logging
                bytes_downloaded = 0
                with open(temp_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(
                        65536
                    ):  # 64KB chunks for better performance
                        f.write(chunk)
                        bytes_downloaded += len(chunk)

                        # Log progress for large files
                        if (
                            content_length and bytes_downloaded % (1024 * 1024 * 10) == 0
                        ):  # Every 10MB
                            progress = (bytes_downloaded / content_length) * 100
                            logger.info(
                                f"Download progress: {progress:.1f}% ({bytes_downloaded:,} / {content_length:,} bytes)"
                            )

                file_size = os.path.getsize(temp_path)

                # Validate downloaded file
                if file_size == 0:
                    raise VoiceProcessingError(
                        message="Downloaded file is empty",
                        error_code=ErrorCode.DOWNLOAD_ERROR,
                    )

                # Update document metadata if document_id is provided
                if document_id:
                    await _update_document_metadata(document_id, filename, file_size, url)

                logger.info(
                    f"Successfully downloaded: {filename} ({file_size:,} bytes) from AWS signed URL"
                )
                return temp_path

    except aiohttp.ClientError as e:
        logger.error(f"Network error downloading from {url}: {e}")
        raise VoiceProcessingError(
            message=f"Network error during download: {str(e)}",
            error_code=ErrorCode.DOWNLOAD_ERROR,
        )
    except asyncio.TimeoutError as e:
        logger.error(f"Download timeout for {url}: {e}")
        raise VoiceProcessingError(
            message="Download timeout - file may be too large or connection is slow",
            error_code=ErrorCode.DOWNLOAD_ERROR,
        )
    except Exception as e:
        logger.error(f"Failed to download document from {url}: {e}")
        raise VoiceProcessingError(
            message=f"Document download failed: {str(e)}",
            error_code=ErrorCode.DOWNLOAD_ERROR,
        )


async def _update_document_metadata(
    document_id: str, filename: str, file_size: int, url: str
) -> None:
    """Update document metadata in the database.

    Args:
        document_id: Document ID to update
        filename: Actual filename from download
        file_size: File size in bytes
        url: Original URL
    """
    try:
        from uuid import UUID

        from sqlalchemy import update

        from shared.database.models.database import get_session
        from shared.database.models.document import Document

        async with get_session() as session:
            # Update document metadata
            stmt = (
                update(Document)
                .where(Document.id == UUID(document_id))
                .values(filename=filename, file_size=file_size, document_metadata={})
            )

            await session.execute(stmt)
            await session.commit()

            logger.info(
                f"Updated document {document_id} metadata: filename={filename}, size={file_size}"
            )

    except Exception as e:
        logger.error(f"Failed to update document metadata for {document_id}: {e}")
        # Don't fail the job if metadata update fails
