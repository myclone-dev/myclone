"""
Document processing module for LiveKit Voice Agent
Handles extraction of text from various document formats uploaded during sessions.

Supports:
- Complex formats (PDF, DOCX, XLSX, PPTX) via Marker Datalab API
- Simple formats (TXT, MD, JSON, CSV, HTML) via direct extraction
"""

import asyncio
import csv
import io
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

import aiohttp

from shared.config import settings

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Supported document types"""

    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    TXT = "txt"
    MD = "md"
    JSON = "json"
    CSV = "csv"
    HTML = "html"
    UNKNOWN = "unknown"


@dataclass
class ProcessedDocument:
    """Result of document processing"""

    filename: str
    document_type: DocumentType
    extracted_text: str
    page_count: Optional[int] = None
    error: Optional[str] = None
    metadata: Optional[dict] = field(default_factory=dict)


class DocumentProcessor:
    """
    Processes documents uploaded to LiveKit sessions.

    Uses Marker Datalab API for complex documents (PDF, DOCX, XLSX, PPTX)
    and direct text extraction for simple formats (TXT, MD, JSON, CSV, HTML).
    """

    # File extensions to document types
    EXTENSION_MAP = {
        ".pdf": DocumentType.PDF,
        ".docx": DocumentType.DOCX,
        ".doc": DocumentType.DOCX,
        ".xlsx": DocumentType.XLSX,
        ".xls": DocumentType.XLSX,
        ".pptx": DocumentType.PPTX,
        ".ppt": DocumentType.PPTX,
        ".txt": DocumentType.TXT,
        ".md": DocumentType.MD,
        ".markdown": DocumentType.MD,
        ".json": DocumentType.JSON,
        ".csv": DocumentType.CSV,
        ".html": DocumentType.HTML,
        ".htm": DocumentType.HTML,
    }

    # Content types for Marker API
    CONTENT_TYPE_MAP = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".ppt": "application/vnd.ms-powerpoint",
    }

    # Types requiring Marker Datalab processing
    COMPLEX_TYPES = {DocumentType.PDF, DocumentType.DOCX, DocumentType.XLSX, DocumentType.PPTX}

    # Maximum file size (10MB default)
    MAX_FILE_SIZE = int(os.getenv("DOC_MAX_FILE_SIZE", 10 * 1024 * 1024))

    # Marker Datalab API configuration
    MARKER_API_URL = "https://www.datalab.to/api/v1/marker"

    def __init__(self):
        self._http_session: Optional[aiohttp.ClientSession] = None

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session for API calls"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def close(self):
        """Close HTTP session"""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()

    def detect_document_type(self, filename: str) -> DocumentType:
        """Detect document type from filename extension"""
        ext = os.path.splitext(filename.lower())[1]
        return self.EXTENSION_MAP.get(ext, DocumentType.UNKNOWN)

    def _get_file_extension(self, filename: str) -> str:
        """Get file extension from filename"""
        return os.path.splitext(filename.lower())[1]

    async def process_from_url(self, url: str, filename: Optional[str] = None) -> ProcessedDocument:
        """
        Process a document from S3 URL or HTTP URL.

        Args:
            url: S3 presigned URL or HTTP URL to the document
            filename: Optional filename override (extracted from URL if not provided)

        Returns:
            ProcessedDocument with extracted text or error
        """
        try:
            # Fetch document content
            content, resolved_filename = await self._fetch_from_url(url)
            final_filename = filename or resolved_filename

            logger.info(f"📄 Fetched document from URL: {final_filename} ({len(content)} bytes)")

            # Process the document
            return await self.process_document(content, final_filename)

        except Exception as e:
            logger.error(f"❌ Failed to process document from URL: {e}", exc_info=True)
            return ProcessedDocument(
                filename=filename or "unknown",
                document_type=DocumentType.UNKNOWN,
                extracted_text="",
                error=str(e),
            )

    async def process_document(
        self,
        content: bytes,
        filename: str,
    ) -> ProcessedDocument:
        """
        Process a document and extract text.

        Args:
            content: Raw document bytes
            filename: Original filename

        Returns:
            ProcessedDocument with extracted text or error
        """
        doc_type = self.detect_document_type(filename)

        if doc_type == DocumentType.UNKNOWN:
            return ProcessedDocument(
                filename=filename,
                document_type=doc_type,
                extracted_text="",
                error=f"Unsupported file type: {filename}",
            )

        # Check file size
        if len(content) > self.MAX_FILE_SIZE:
            return ProcessedDocument(
                filename=filename,
                document_type=doc_type,
                extracted_text="",
                error=f"File too large: {len(content)} bytes (max: {self.MAX_FILE_SIZE})",
            )

        try:
            if doc_type in self.COMPLEX_TYPES:
                return await self._process_with_marker(content, filename, doc_type)
            else:
                return await self._process_simple(content, filename, doc_type)
        except Exception as e:
            logger.error(f"Document processing failed for {filename}: {e}", exc_info=True)
            return ProcessedDocument(
                filename=filename, document_type=doc_type, extracted_text="", error=str(e)
            )

    async def _process_with_marker(
        self, content: bytes, filename: str, doc_type: DocumentType
    ) -> ProcessedDocument:
        """Process complex documents using Marker Datalab API"""

        api_key = settings.datalab_api_key
        if not api_key:
            logger.warning("DATALAB_API_KEY not set, cannot process complex documents")
            return ProcessedDocument(
                filename=filename,
                document_type=doc_type,
                extracted_text="",
                error="Marker Datalab API key not configured",
            )

        session = await self._get_http_session()
        file_ext = self._get_file_extension(filename)
        content_type = self.CONTENT_TYPE_MAP.get(file_ext, "application/octet-stream")

        # Prepare multipart form data
        form_data = aiohttp.FormData()
        form_data.add_field("file", content, filename=filename, content_type=content_type)
        form_data.add_field("output_format", "markdown")
        form_data.add_field("paginate", "false")
        form_data.add_field("extract_images", "false")

        headers = {"X-API-Key": api_key}

        try:
            logger.info(f"📄 Sending {filename} to Marker Datalab for processing...")

            async with session.post(
                self.MARKER_API_URL,
                data=form_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Marker API error: {response.status} - {error_text}")
                    return ProcessedDocument(
                        filename=filename,
                        document_type=doc_type,
                        extracted_text="",
                        error=f"Marker API error: {response.status}",
                    )

                result = await response.json()

                if not result.get("success"):
                    return ProcessedDocument(
                        filename=filename,
                        document_type=doc_type,
                        extracted_text="",
                        error=result.get("error", "Marker API submission failed"),
                    )

                # Poll for results (async processing)
                request_check_url = result.get("request_check_url")
                if request_check_url:
                    return await self._poll_marker_result(
                        request_check_url, filename, doc_type, api_key
                    )

                # Synchronous result (unlikely but handle it)
                extracted_text = result.get("markdown", "") or result.get("text", "")
                logger.info(f"✅ Marker processed {filename}: {len(extracted_text)} chars")

                return ProcessedDocument(
                    filename=filename,
                    document_type=doc_type,
                    extracted_text=extracted_text,
                    metadata=result.get("metadata"),
                )

        except asyncio.TimeoutError:
            logger.error(f"Marker API timeout for {filename}")
            return ProcessedDocument(
                filename=filename,
                document_type=doc_type,
                extracted_text="",
                error="Marker API timeout",
            )
        except Exception as e:
            logger.error(f"Marker API error: {e}")
            return ProcessedDocument(
                filename=filename, document_type=doc_type, extracted_text="", error=str(e)
            )

    async def _poll_marker_result(
        self,
        check_url: str,
        filename: str,
        doc_type: DocumentType,
        api_key: str,
        max_attempts: int = 60,
        poll_interval: float = 2.0,
    ) -> ProcessedDocument:
        """Poll Marker Datalab for async processing result"""
        session = await self._get_http_session()
        headers = {"X-API-Key": api_key}

        for attempt in range(max_attempts):
            await asyncio.sleep(poll_interval)

            try:
                async with session.get(check_url, headers=headers) as response:
                    if response.status != 200:
                        continue

                    result = await response.json()
                    status = result.get("status")

                    if status == "complete":
                        extracted_text = result.get("markdown", "") or result.get("text", "")
                        logger.info(
                            f"✅ Marker async complete for {filename}: {len(extracted_text)} chars"
                        )
                        return ProcessedDocument(
                            filename=filename,
                            document_type=doc_type,
                            extracted_text=extracted_text,
                            metadata=result.get("metadata"),
                        )
                    elif status == "error":
                        return ProcessedDocument(
                            filename=filename,
                            document_type=doc_type,
                            extracted_text="",
                            error=result.get("error", "Processing failed"),
                        )
                    # Still processing, continue polling
                    logger.debug(f"Marker processing {filename}: attempt {attempt + 1}")
            except Exception as e:
                logger.warning(f"Poll error for {filename}: {e}")

        return ProcessedDocument(
            filename=filename, document_type=doc_type, extracted_text="", error="Processing timeout"
        )

    async def _process_simple(
        self, content: bytes, filename: str, doc_type: DocumentType
    ) -> ProcessedDocument:
        """Process simple text-based documents directly"""

        try:
            # Detect encoding
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
            except Exception:
                text = content.decode("utf-8", errors="ignore")

        extracted_text = ""

        if doc_type == DocumentType.TXT or doc_type == DocumentType.MD:
            extracted_text = text

        elif doc_type == DocumentType.JSON:
            try:
                data = json.loads(text)
                # Pretty print JSON for readability
                extracted_text = json.dumps(data, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                extracted_text = text

        elif doc_type == DocumentType.CSV:
            extracted_text = self._csv_to_text(text)

        elif doc_type == DocumentType.HTML:
            extracted_text = self._html_to_text(text)

        logger.info(f"✅ Simple extraction for {filename}: {len(extracted_text)} chars")

        return ProcessedDocument(
            filename=filename, document_type=doc_type, extracted_text=extracted_text
        )

    def _csv_to_text(self, csv_text: str) -> str:
        """Convert CSV to readable text format"""
        try:
            reader = csv.reader(io.StringIO(csv_text))
            rows = list(reader)

            if not rows:
                return ""

            # Format as markdown table
            headers = rows[0]
            lines = [
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join(["---"] * len(headers)) + " |",
            ]

            for row in rows[1:]:
                # Pad row if shorter than headers
                padded_row = row + [""] * (len(headers) - len(row))
                lines.append("| " + " | ".join(padded_row[: len(headers)]) + " |")

            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"CSV parsing failed: {e}")
            return csv_text

    def _html_to_text(self, html_text: str) -> str:
        """Extract text from HTML"""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_text, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "head", "meta", "link"]):
                element.decompose()

            # get_text with separator
            text = soup.get_text(separator="\n")
            return "\n".join(line.strip() for line in text.splitlines() if line.strip())
        except ImportError:
            # Fallback: basic tag stripping
            import re

            text = re.sub(
                r"<script[^>]*>.*?</script>", "", html_text, flags=re.DOTALL | re.IGNORECASE
            )
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)
            return text.strip()

    async def _fetch_from_url(self, url: str) -> tuple[bytes, str]:
        """
        Fetch document from URL (S3 presigned URL or HTTP).

        Returns:
            tuple: (content bytes, filename)
        """
        session = await self._get_http_session()

        async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
            if response.status != 200:
                raise ValueError(f"Failed to fetch document: HTTP {response.status}")

            content = await response.read()

            # Extract filename from URL or Content-Disposition
            filename = "document"

            # Try Content-Disposition header
            cd = response.headers.get("Content-Disposition", "")
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip("\"'")
            else:
                # Extract from URL path
                parsed = urlparse(url)
                path_filename = os.path.basename(parsed.path)
                if path_filename:
                    filename = path_filename.split("?")[0]

            return content, filename
