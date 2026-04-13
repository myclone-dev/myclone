"""
Document Handler

Handles document upload and processing for LiveKit agent:
- Process documents from URLs (S3 presigned URLs)
- Extract text from PDF, DOCX, XLSX, PPTX, TXT, etc.
- Add documents to session context
- Save documents to conversation history

Created: 2026-01-25
"""

import asyncio
import base64
import json
import logging
from typing import Callable, Optional
from uuid import UUID

from shared.database.models.database import Conversation, async_session_maker
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.utils.document_processor import DocumentProcessor, DocumentType, ProcessedDocument

logger = logging.getLogger(__name__)


class DocumentHandler:
    """
    Handles document upload and processing.

    Responsibilities:
    - Processing documents from URLs or base64
    - Extracting text via DocumentProcessor
    - Managing per-session document context
    - Saving documents to conversation history
    """

    def __init__(
        self,
        persona_id: UUID,
        session_token: str,
        room,
        session_context,
        text_only_mode: bool = False,
        output_callback: Optional[Callable] = None,
    ):
        """
        Initialize document handler.

        Args:
            persona_id: Persona UUID
            session_token: Session token for conversation tracking
            room: LiveKit room instance
            session_context: SessionContext instance for tracking documents
            text_only_mode: Whether in text-only mode
            output_callback: Function to send messages to user
        """
        self.persona_id = persona_id
        self.session_token = session_token
        self.room = room
        self.session_context = session_context
        self.text_only_mode = text_only_mode
        self._output_message = output_callback

        # Document processor
        self._document_processor = DocumentProcessor()
        self._document_processing_lock = asyncio.Lock()

        self.logger = logging.getLogger(__name__)

    async def handle_document_upload(self, data: dict) -> dict:
        """
        Handle document upload from frontend via data channel.

        Expected data format:
        {
            "type": "document_upload",
            "filename": "report.pdf",  # Optional, extracted from URL if not provided
            "url": "https://s3.../presigned-url" OR "content": "<base64 encoded>",
            "extracted_text": "..."  # Optional, pre-extracted text from upload-attachment endpoint
        }

        Returns:
            dict with status and message for frontend acknowledgment
        """
        async with self._document_processing_lock:
            try:
                filename = data.get("filename", "document")

                # Debug: Log received data keys
                self.logger.info(
                    f"📄 [DEBUG] Received document upload data keys: {list(data.keys())}"
                )
                self.logger.info(
                    f"📄 [DEBUG] Has extracted_text: {'extracted_text' in data and bool(data.get('extracted_text'))}"
                )

                # Check if pre-extracted text is provided (from upload-attachment endpoint)
                # This avoids redundant S3 fetch and re-parsing
                extracted_text = data.get("extracted_text")

                # Log the actual extracted_text value for debugging
                if extracted_text:
                    self.logger.info(
                        f"📄 [DEBUG] extracted_text length: {len(extracted_text)} chars"
                    )
                else:
                    self.logger.warning(
                        "📄 [DEBUG] extracted_text is empty/null - text extraction may have failed on upload"
                    )

                if extracted_text is not None:
                    try:
                        self.logger.info(
                            f"📄 Using pre-extracted text for {filename} ({len(extracted_text)} chars)"
                        )
                        # Determine document type from filename extension
                        ext = filename.lower().split(".")[-1] if "." in filename else "unknown"
                        doc_type_map = {
                            "pdf": DocumentType.PDF,
                            "doc": DocumentType.DOCX,  # Treat .doc as DOCX
                            "docx": DocumentType.DOCX,
                            "xls": DocumentType.XLSX,  # Treat .xls as XLSX
                            "xlsx": DocumentType.XLSX,
                            "ppt": DocumentType.PPTX,  # Treat .ppt as PPTX
                            "pptx": DocumentType.PPTX,
                            "txt": DocumentType.TXT,
                            "md": DocumentType.MD,
                            "csv": DocumentType.CSV,
                            "json": DocumentType.JSON,
                            "html": DocumentType.HTML,
                            "png": DocumentType.UNKNOWN,  # Images don't have a specific type
                            "jpg": DocumentType.UNKNOWN,
                            "jpeg": DocumentType.UNKNOWN,
                        }
                        doc_type = doc_type_map.get(ext, DocumentType.UNKNOWN)

                        result = ProcessedDocument(
                            filename=filename,
                            document_type=doc_type,
                            extracted_text=extracted_text,
                            page_count=None,  # Unknown for pre-extracted text
                            error=None,
                        )
                    except Exception as e:
                        self.logger.error(
                            f"❌ Failed to create ProcessedDocument from pre-extracted text: {e}"
                        )
                        capture_exception_with_context(
                            e,
                            extra={
                                "filename": filename,
                                "extracted_text_length": (
                                    len(extracted_text) if extracted_text else 0
                                ),
                                "persona_id": str(self.persona_id),
                            },
                            tags={
                                "component": "document_handler",
                                "operation": "handle_document_upload_pre_extracted",
                                "severity": "high",
                                "user_facing": "true",
                            },
                        )
                        return {
                            "status": "error",
                            "message": f"Failed to process pre-extracted document: {e}",
                        }

                # Fallback: Get document content from URL (S3 presigned URL)
                elif "url" in data:
                    url = data["url"]
                    self.logger.info(f"📄 Processing document from URL: {url[:80]}...")

                    result = await self._document_processor.process_from_url(url, filename)

                elif "content" in data:
                    # Direct upload (base64 encoded) - less common for large files
                    content = base64.b64decode(data["content"])
                    self.logger.info(
                        f"📄 Processing direct upload: {filename} ({len(content)} bytes)"
                    )
                    result = await self._document_processor.process_document(content, filename)
                else:
                    return {
                        "status": "error",
                        "message": "No URL, content, or extracted_text provided",
                    }

                if result.error:
                    self.logger.error(f"❌ Document processing failed: {result.error}")
                    # Still notify user about the failure in voice mode
                    if not self.text_only_mode and self._output_message:
                        try:
                            await self._output_message(
                                f"I received your file {filename}, but I wasn't able to read its contents. "
                                "The text extraction service may be temporarily unavailable. "
                                "Please try again later or share the key points verbally.",
                                allow_interruptions=True,
                            )
                        except Exception as e:
                            self.logger.warning(f"Could not speak error notification: {e}")
                    return {
                        "status": "error",
                        "message": f"Failed to process {result.filename}: {result.error}",
                    }

                if not result.extracted_text:
                    self.logger.warning(
                        f"⚠️ Document processed but no text extracted: {result.filename}"
                    )
                    # Notify user that document was received but is empty/unreadable
                    if not self.text_only_mode and self._output_message:
                        try:
                            await self._output_message(
                                f"I received your file {filename}, but it appears to be empty or I couldn't extract any text from it. "
                                "Could you share the key points you'd like me to know about?",
                                allow_interruptions=True,
                            )
                        except Exception as e:
                            self.logger.warning(f"Could not speak empty document notification: {e}")
                    return {
                        "status": "warning",
                        "message": f"Document {result.filename} received but no text could be extracted",
                    }

                # Add to session context
                self.session_context.add_document(
                    filename=result.filename,
                    extracted_text=result.extracted_text,
                    doc_type=result.document_type.value,
                )

                self.logger.info(
                    f"✅ Document processed: {result.filename} "
                    f"({len(result.extracted_text)} chars extracted)"
                )
                self.logger.info(
                    f"📄 [DEBUG] Session now has {len(self.session_context.uploaded_documents)} documents"
                )

                # Notify user via appropriate channel
                notification = f"I've received and processed {result.filename}. Feel free to ask me questions about it."

                if self.text_only_mode:
                    # Send status on document_status topic for clients to track processing state
                    status_payload = json.dumps(
                        {
                            "status": "success",
                            "filename": result.filename,
                            "chars_extracted": len(result.extracted_text),
                            "document_type": result.document_type.value,
                        }
                    )
                    await self.room.local_participant.publish_data(
                        status_payload.encode("utf-8"),
                        topic="document_status",
                        reliable=True,
                    )
                    self.logger.info(
                        f"📤 Published document status on 'document_status' topic: {result.filename}"
                    )

                    # Save parsed document data as hidden conversation entry
                    await self._save_document_to_conversation(result)

                    # Also send as chat message for user feedback
                    await self.room.local_participant.publish_data(
                        json.dumps({"message": notification}).encode("utf-8"),
                        topic="chat",
                        reliable=True,
                    )
                else:
                    # Note: We don't speak a notification in voice mode as the UI already shows the upload status
                    # and speaking the filename (which may be a UUID) is not helpful
                    self.logger.info(
                        f"📄 Voice mode: Document {result.filename} processed, skipping voice notification (UI shows status)"
                    )

                return {
                    "status": "success",
                    "message": f"Processed {result.filename}",
                    "chars_extracted": len(result.extracted_text),
                    "document_type": result.document_type.value,
                }

            except Exception as e:
                self.logger.error(f"❌ Document upload handling failed: {e}", exc_info=True)
                capture_exception_with_context(
                    e,
                    extra={"filename": data.get("filename"), "persona_id": str(self.persona_id)},
                    tags={
                        "component": "document_handler",
                        "operation": "handle_document_upload",
                        "severity": "high",
                        "user_facing": "true",
                    },
                )
                return {"status": "error", "message": str(e)}

    async def _save_document_to_conversation(self, document_result: ProcessedDocument):
        """
        Save document as hidden conversation entry (text mode only).

        Documents are stored as special message entries with visibility=hidden
        so they can be retrieved for conversation summaries but not shown in UI.

        Args:
            document_result: Processed document with extracted text
        """
        try:
            from datetime import datetime, timezone

            # Build document entry
            document_entry = {
                "role": "system",
                "content": f"[DOCUMENT UPLOADED]\nFilename: {document_result.filename}\nType: {document_result.document_type.value}\n\nContent:\n{document_result.extracted_text}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "visibility": "hidden",  # Mark as hidden from frontend
                "metadata": {
                    "type": "document",
                    "filename": document_result.filename,
                    "document_type": document_result.document_type.value,
                    "char_count": len(document_result.extracted_text),
                },
            }

            # Get conversation type (text or voice)
            conversation_type = "text" if self.text_only_mode else "voice"

            async with async_session_maker() as db_session:
                # Find or create conversation
                from sqlalchemy import select

                stmt = select(Conversation).where(
                    Conversation.persona_id == self.persona_id,
                    Conversation.session_id == self.session_token,
                    Conversation.conversation_type == conversation_type,
                )
                result = await db_session.execute(stmt)
                conversation = result.scalar_one_or_none()

                if conversation:
                    # Append to existing messages
                    existing_messages = conversation.messages or []
                    existing_messages.append(document_entry)
                    conversation.messages = existing_messages
                    from sqlalchemy.orm import attributes

                    attributes.flag_modified(conversation, "messages")
                else:
                    # Create new conversation with document
                    conversation = Conversation(
                        persona_id=self.persona_id,
                        session_id=self.session_token,
                        conversation_type=conversation_type,
                        messages=[document_entry],
                    )
                    db_session.add(conversation)

                await db_session.commit()
                self.logger.info(
                    f"✅ Saved document '{document_result.filename}' as hidden {conversation_type} conversation entry "
                    f"({len(document_result.extracted_text)} chars)"
                )

        except Exception as e:
            self.logger.error(f"❌ Failed to save document to conversation: {e}")
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "session_token": self.session_token,
                    "filename": document_result.filename,
                },
                tags={
                    "component": "document_handler",
                    "operation": "save_document_to_conversation",
                    "severity": "medium",
                },
            )

    async def close(self):
        """Cleanup document processor resources."""
        try:
            if self._document_processor:
                await self._document_processor.close()
        except Exception as e:
            self.logger.error(f"Failed to close document processor: {e}")
