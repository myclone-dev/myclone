import asyncio
import logging
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional
from uuid import UUID

import httpx
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes

from app.services.webhook_service import WebhookService
from shared.config import settings
from shared.database.models.database import Conversation, Persona
from shared.generation.prompts import PromptTemplates
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.rag.rag_singleton import get_rag_system

logger = logging.getLogger(__name__)


class ResponseGenerator:
    def __init__(self):
        # Create custom HTTP client with relaxed settings
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=30.0, read=60.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            follow_redirects=True,
            verify=True,
        )

        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key, timeout=60.0, max_retries=3, http_client=http_client
        )
        self.model = settings.llm_model
        self.llama_rag = None  # Will be initialized on first use
        self.prompts = PromptTemplates()

    async def _get_rag_system(self):
        """Get the singleton RAG system instance"""
        if self.llama_rag is None:
            self.llama_rag = await get_rag_system()
        return self.llama_rag

    async def generate_response(
        self,
        session: AsyncSession,
        persona_id: UUID,
        message: str,
        session_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stream: bool = False,
    ) -> Dict[str, Any]:
        try:
            logger.info(
                f"🚀 ResponseGenerator.generate_response ENTERED - persona_id: {persona_id}, stream: {stream}"
            )

            # Get persona
            logger.info(f"🔄 Getting persona for {persona_id}")
            persona = await self.get_persona(session, persona_id)
            if not persona:
                raise ValueError(f"Persona {persona_id} not found")

            # Use LlamaIndex RAG system directly - it handles retrieval and generation
            # Create context dict for LlamaRAG (it expects patterns and history)
            context = {
                "session_id": session_id,  # For Langfuse session tracking
                "patterns": {},  # LlamaRAG will get patterns from the database
                "history": [],  # LlamaRAG will get history if needed
            }

            if stream:
                # Use REAL streaming from LlamaRAG
                logger.info("🔥 REAL STREAMING MODE: Using LlamaRAG.generate_response_stream()")

                async def stream_llama_response():
                    stream_start = time.time()
                    sources_collected = []
                    try:
                        # Get singleton RAG system
                        rag_system = await self._get_rag_system()

                        # Use the new streaming method for real streaming with sources
                        chunk_count = 0
                        async for chunk in rag_system.generate_response_stream(
                            persona_id=persona_id,
                            query=message,
                            context=context,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            return_citations=True,
                            chat_trace=True,
                        ):
                            # Check if this is a sources chunk or content chunk
                            if isinstance(chunk, dict) and chunk.get("type") == "sources":
                                sources_collected = chunk.get("sources", [])
                                # Pass through the sources chunk so session_routes can handle it
                                yield chunk
                            else:
                                chunk_count += 1
                                yield chunk

                        stream_time = time.time() - stream_start
                        logger.info(
                            f"✅ REAL STREAMING COMPLETE - {chunk_count} chunks in {stream_time:.3f}s, {len(sources_collected)} sources"
                        )
                    except Exception as stream_error:
                        logger.error(f"❌ Streaming failed: {stream_error}")
                        raise

                # Note: For streaming, sources will be collected but need to be sent separately
                # The frontend should handle sources in a different way for streaming
                return {
                    "response": stream_llama_response(),
                    "session_id": session_id,
                    "thinking_pattern": "llama_rag",
                    "sources": [],  # Sources are embedded in the stream
                }
            else:
                # Get singleton RAG system
                rag_system = await self._get_rag_system()

                # Generate response using LlamaIndex RAG with sources
                response_data = await rag_system.generate_response(
                    persona_id=persona_id,
                    query=message,
                    context=context,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    return_citations=True,
                )

                # Extract response text and sources
                if isinstance(response_data, dict):
                    response_text = response_data.get("response", "")
                    sources = response_data.get("sources", [])
                else:
                    response_text = str(response_data)
                    sources = []

                # Save conversation with sources
                await self.save_conversation(
                    session, persona_id, session_id, message, response_text, sources
                )

                return {
                    "response": response_text,
                    "session_id": session_id,
                    "thinking_pattern": "llama_rag",
                    "sources": sources,
                }

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    async def generate_response_special(
        self,
        session: AsyncSession,
        persona_id: UUID,
        message: str,
        pdf_url: Optional[str] = None,
        session_id: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Generate response for special evaluation (with optional PDF)"""
        try:
            if pdf_url:
                logger.info(
                    f"🚀 ResponseGenerator.generate_response_special - persona_id: {persona_id}, pdf_url: {pdf_url[:50]}..."
                )
            else:
                logger.info(
                    f"🚀 ResponseGenerator.generate_response_special - persona_id: {persona_id}, no PDF"
                )

            # Get persona
            persona = await self.get_persona(session, persona_id)
            if not persona:
                raise ValueError(f"Persona {persona_id} not found")

            # Parse PDF to markdown using Marker API
            logger.info("📄 Parsing PDF to markdown...")
            markdown_text = None
            if pdf_url:
                markdown_text = await self.parse_pdf_to_markdown(pdf_url)
                markdown_text = f"Parse the above provided pdf to markdown : \n {markdown_text}"
                logger.info(f"✅ PDF parsed: {len(markdown_text)} characters")

            # Create context dict
            context = {
                "session_id": session_id,
                "patterns": {},
                "history": [],
            }

            if stream:
                logger.info(
                    "🔥 SPECIAL STREAMING MODE: Using LlamaRAG.generate_response_stream_special()"
                )

                async def stream_special_response():
                    stream_start = time.time()
                    try:
                        rag_system = await self._get_rag_system()

                        chunk_count = 0
                        async for chunk in rag_system.generate_response_stream_special(
                            persona_id=persona_id,
                            message=message,
                            markdown_text=markdown_text,
                            context=context,
                            temperature=temperature,
                            max_tokens=max_tokens,
                        ):
                            chunk_count += 1
                            yield chunk

                        stream_time = time.time() - stream_start
                        logger.info(
                            f"✅ SPECIAL STREAMING COMPLETE - {chunk_count} chunks in {stream_time:.3f}s"
                        )
                    except Exception as stream_error:
                        logger.error(f"❌ Special streaming failed: {stream_error}")
                        raise

                return {
                    "response": stream_special_response(),
                    "session_id": session_id,
                    "thinking_pattern": "special_pdf",
                    "markdown_text": markdown_text,
                    "sources": [],
                }
            else:
                # Non-streaming mode
                rag_system = await self._get_rag_system()
                response_text = await rag_system.generate_response_special(
                    persona_id=persona_id,
                    message=message,
                    markdown_text=markdown_text,
                    context=context,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                # Build user message with optional PDF reference
                user_msg = f"{message} [PDF: {pdf_url}]" if pdf_url else message

                await self.save_conversation_special(
                    session,
                    persona_id,
                    session_id,
                    user_msg,
                    response_text,
                    markdown_text,
                    [],
                    attachment_url=pdf_url,
                )

                return {
                    "response": response_text,
                    "session_id": session_id,
                    "thinking_pattern": "special_pdf",
                    "sources": [],
                }

        except Exception as e:
            logger.error(f"Error generating special response: {e}")
            raise

    async def parse_pdf_to_markdown(self, pdf_url: str) -> str:
        """Parse PDF/document to markdown using Marker API.

        Supports: PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX
        """
        try:
            import os
            import tempfile
            from pathlib import Path

            import aiohttp

            from shared.config import settings
            from shared.services.s3_service import get_s3_service

            # Map file extensions to MIME types for Marker API
            CONTENT_TYPE_MAP = {
                ".pdf": "application/pdf",
                ".doc": "application/msword",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".xls": "application/vnd.ms-excel",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".ppt": "application/vnd.ms-powerpoint",
                ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            }

            # Get file extension from URL to determine content type and temp file suffix
            file_ext = Path(pdf_url).suffix.lower() or ".pdf"
            content_type = CONTENT_TYPE_MAP.get(file_ext, "application/pdf")

            # Download document if it's a URL
            if pdf_url.startswith("s3://"):
                # Handle S3 URLs using S3 service
                logger.info(f"Downloading document from S3: {pdf_url}")
                s3_service = get_s3_service()

                # Ensure bucket exists
                await s3_service.ensure_bucket_exists()

                # Create temp file for download with correct extension
                tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
                tmp_file.close()

                # Download from S3
                pdf_path = await s3_service.download_file(s3_path=pdf_url, local_path=tmp_file.name)
                logger.info(f"Successfully downloaded file from S3: {pdf_url} to {pdf_path}")

            elif pdf_url.startswith(("http://", "https://")):
                # Handle HTTP/HTTPS URLs
                logger.info(f"Downloading document from URL: {pdf_url}")
                async with aiohttp.ClientSession() as http_session:
                    async with http_session.get(pdf_url) as response:
                        response.raise_for_status()
                        pdf_content = await response.read()

                # Save to temporary file with correct extension
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                    tmp_file.write(pdf_content)
                    pdf_path = tmp_file.name
            else:
                # Local file path - update file_ext and content_type from actual path
                pdf_path = pdf_url
                file_ext = Path(pdf_path).suffix.lower() or ".pdf"
                content_type = CONTENT_TYPE_MAP.get(file_ext, "application/pdf")

            logger.info(
                f"Calling Marker API with content_type={content_type} for file: {os.path.basename(pdf_path)}"
            )

            # Call Marker API
            async with aiohttp.ClientSession() as http_session:
                headers = {"X-API-Key": settings.datalab_api_key}

                with open(pdf_path, "rb") as f:
                    data = aiohttp.FormData()
                    data.add_field(
                        "file",
                        f,
                        filename=os.path.basename(pdf_path),
                        content_type=content_type,
                    )
                    data.add_field("output_format", "markdown")
                    data.add_field("paginate", "false")
                    data.add_field("extract_images", "false")

                    endpoint = "https://www.datalab.to/api/v1/marker"
                    async with http_session.post(endpoint, data=data, headers=headers) as response:
                        response.raise_for_status()
                        submit_result = await response.json()

                if not submit_result.get("success"):
                    raise Exception(
                        f"Marker API failed: {submit_result.get('error', 'Unknown error')}"
                    )

                request_check_url = submit_result["request_check_url"]

                # Poll for results
                timeout = 300
                poll_interval = 2
                elapsed = 0

                while elapsed < timeout:
                    async with http_session.get(
                        request_check_url, headers=headers
                    ) as result_response:
                        result_response.raise_for_status()
                        result_data = await result_response.json()

                        if result_data.get("status") == "complete":
                            markdown_text = result_data.get("markdown", "")
                            logger.info(f"✅ Marker API complete: {len(markdown_text)} chars")

                            # Cleanup temp file
                            if pdf_url.startswith(("http://", "https://", "s3://")):
                                os.unlink(pdf_path)

                            return markdown_text
                        elif result_data.get("status") == "error":
                            raise Exception(f"Marker API error: {result_data.get('error')}")

                        await asyncio.sleep(poll_interval)
                        elapsed += poll_interval

                raise Exception("Marker API timeout")

        except Exception as e:
            logger.error(f"Error parsing {file_ext} document: {e}")
            raise

    async def generate_base_response(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 1000
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error in base response generation: {e}")
            raise

    async def generate_streaming_response(
        self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error in streaming response: {e}")
            raise

    async def classify_question(self, question: str) -> str:
        try:
            prompt = self.prompts.build_question_classification_prompt(question)

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a question classifier."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=50,
            )

            classification = response.choices[0].message.content.strip().upper()
            valid_types = [
                "FACTUAL",
                "ANALYTICAL",
                "CREATIVE",
                "PERSONAL",
                "TECHNICAL",
                "PHILOSOPHICAL",
            ]

            if classification in valid_types:
                return classification
            return "ANALYTICAL"

        except Exception as e:
            logger.error(f"Error classifying question: {e}")
            return "ANALYTICAL"

    async def get_persona(self, session: AsyncSession, persona_id: UUID) -> Optional[Persona]:
        try:
            logger.info(f"🔍 get_persona STARTED for persona_id: {persona_id}")
            stmt = select(Persona).where(Persona.id == persona_id)
            logger.info("🔍 Executing database query for persona...")
            result = await session.execute(stmt)
            logger.info("🔍 Database query completed, getting result...")
            persona = result.scalar_one_or_none()
            logger.info(f"✅ get_persona COMPLETED - found: {persona.name if persona else 'None'}")
            return persona
        except Exception as e:
            logger.error(f"❌ Error getting persona: {e}")
            return None

    async def save_conversation(
        self,
        session: AsyncSession,
        persona_id: UUID,
        session_id: Optional[str],
        user_message: str,
        assistant_response: str,
        sources: Optional[list] = None,
        attachments: Optional[list] = None,
    ):
        """
        Save a conversation message pair to the database.

        Args:
            session: Database session
            persona_id: Persona UUID
            session_id: Session token/ID
            user_message: User's message text
            assistant_response: Assistant's response text
            sources: Optional list of RAG sources
            attachments: Optional list of attachment dicts with keys:
                - id: Attachment UUID
                - filename: Original filename
                - file_type: pdf, png, jpg, jpeg
                - s3_url: S3 URL to file
                - extracted_text: Text extracted from attachment (optional)
        """
        try:
            # Check if conversation exists
            if session_id:
                stmt = select(Conversation).where(
                    Conversation.persona_id == persona_id, Conversation.session_id == session_id
                )
                result = await session.execute(stmt)
                conversation = result.scalar_one_or_none()
            else:
                conversation = None
                session_id = f"session_{datetime.utcnow().timestamp()}"

            # Format sources to match frontend expectations
            formatted_sources = []
            if sources:
                for source in sources:
                    formatted_sources.append(
                        {
                            "source": source.get("source", ""),
                            "title": source.get("title", ""),
                            "content": source.get("content", ""),
                            "similarity": source.get("similarity"),
                            "source_url": source.get("source_url", ""),
                            "type": source.get("type", "other"),
                            "verification_note": source.get("verification_note"),
                        }
                    )

            # Format attachments for storage
            formatted_attachments = []
            if attachments:
                for att in attachments:
                    formatted_attachments.append(
                        {
                            "id": str(att.get("id", "")),
                            "filename": att.get("filename", ""),
                            "file_type": att.get("file_type", ""),
                            "file_size": att.get("file_size", 0),
                            "s3_url": att.get("s3_url", ""),
                        }
                    )

            # Build user message with optional attachments
            user_msg_obj = {
                "role": "user",
                "content": user_message,
                "timestamp": datetime.utcnow().isoformat(),
            }
            if formatted_attachments:
                user_msg_obj["attachments"] = formatted_attachments

            messages = [
                user_msg_obj,
                {
                    "role": "assistant",
                    "content": assistant_response,
                    "timestamp": datetime.utcnow().isoformat(),
                    "sources": formatted_sources if formatted_sources else [],
                },
            ]

            # Track message index for attachment linking
            message_index = 0

            if conversation:
                # Update existing conversation
                existing_messages = conversation.messages or []
                message_index = len(existing_messages)  # Index of the new user message
                existing_messages.extend(messages)
                conversation.messages = existing_messages
                # Mark the JSONB field as modified so SQLAlchemy detects the change
                attributes.flag_modified(conversation, "messages")
            else:
                # Create new conversation
                conversation = Conversation(
                    persona_id=persona_id,
                    session_id=session_id,
                    messages=messages,
                    conversation_type="text",
                )
                session.add(conversation)

            await session.flush()  # Flush to get conversation.id before linking attachments

            # Link attachments to conversation (fix orphaned attachments)
            if attachments and conversation.id:
                from sqlalchemy import update

                from shared.database.models.conversation_attachment import ConversationAttachment

                for att in attachments:
                    att_id = att.get("id")
                    if att_id:
                        try:
                            stmt = (
                                update(ConversationAttachment)
                                .where(ConversationAttachment.id == UUID(att_id))
                                .values(
                                    conversation_id=conversation.id,
                                    message_index=message_index,
                                )
                            )
                            await session.execute(stmt)
                            logger.info(
                                f"📎 Linked attachment {att_id} to conversation {conversation.id}"
                            )
                        except Exception as link_error:
                            logger.warning(f"Failed to link attachment {att_id}: {link_error}")
                            capture_exception_with_context(
                                link_error,
                                extra={
                                    "attachment_id": att_id,
                                    "conversation_id": str(conversation.id),
                                    "session_id": session_id,
                                },
                                tags={
                                    "component": "generator",
                                    "operation": "link_attachment",
                                    "severity": "medium",
                                    "user_facing": "false",
                                },
                            )

            await session.commit()

            # Send webhook notification (fire-and-forget)
            asyncio.create_task(
                self._send_conversation_webhook(
                    persona_id=persona_id,
                    conversation_id=conversation.id,
                    session_id=session_id,
                    conversation_type="text",
                    message_count=len(messages),
                )
            )

            # Return conversation ID for reference
            return conversation.id

        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(persona_id),
                    "session_id": session_id,
                    "has_attachments": bool(attachments),
                    "attachment_count": len(attachments) if attachments else 0,
                },
                tags={
                    "component": "generator",
                    "operation": "save_conversation",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            await session.rollback()
            return None

    async def save_conversation_special(
        self,
        session: AsyncSession,
        persona_id: UUID,
        session_id: Optional[str],
        user_message: str,
        assistant_response: str,
        markdown_content: Optional[str] = None,
        sources: Optional[list] = None,
        attachment_url: Optional[str] = None,
    ):
        try:
            # Check if conversation exists
            if session_id:
                stmt = select(Conversation).where(
                    Conversation.persona_id == persona_id, Conversation.session_id == session_id
                )
                result = await session.execute(stmt)
                conversation = result.scalar_one_or_none()
            else:
                conversation = None
                session_id = f"session_{datetime.utcnow().timestamp()}"

            # Format sources to match frontend expectations
            formatted_sources = []
            if sources:
                for source in sources:
                    formatted_sources.append(
                        {
                            "source": source.get("source", ""),
                            "title": source.get("title", ""),
                            "content": source.get("content", ""),
                            "similarity": source.get("similarity"),
                            "source_url": source.get("source_url", ""),
                            "type": source.get("type", "other"),
                            "verification_note": source.get("verification_note"),
                        }
                    )
            if not markdown_content:
                messages = [
                    {
                        "role": "user",
                        "content": user_message,
                        "type": "text",
                        "hidden": False,
                        "content_type": "text",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    {
                        "role": "assistant",
                        "content": assistant_response,
                        "type": "text",
                        "hidden": False,
                        "content_type": "text",
                        "timestamp": datetime.utcnow().isoformat(),
                        "sources": formatted_sources if formatted_sources else [],
                    },
                ]
            else:
                messages = [
                    {
                        "role": "user",
                        "content": user_message,
                        "type": "text",
                        "hidden": False,
                        "content_type": "text",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    {
                        "role": "user",
                        "content": markdown_content,
                        "type": "attachment",
                        "hidden": True,
                        "content_type": "pdf",
                        "url": attachment_url if attachment_url else "",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    {
                        "role": "assistant",
                        "content": assistant_response,
                        "type": "text",
                        "hidden": False,
                        "content_type": "text",
                        "timestamp": datetime.utcnow().isoformat(),
                        "sources": formatted_sources if formatted_sources else [],
                    },
                ]

            if conversation:
                # Update existing conversation
                existing_messages = conversation.messages or []
                existing_messages.extend(messages)
                conversation.messages = existing_messages
                # Mark the JSONB field as modified so SQLAlchemy detects the change
                attributes.flag_modified(conversation, "messages")
            else:
                # Create new conversation
                conversation = Conversation(
                    persona_id=persona_id,
                    session_id=session_id,
                    messages=messages,
                    conversation_type="text",
                )
                session.add(conversation)

            await session.commit()

        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            await session.rollback()

    async def save_voice_conversation(
        self,
        session: AsyncSession,
        persona_id: UUID,
        session_id: str,
        transcript_messages: list,
        user_email: Optional[str] = None,
    ):
        """Save voice conversation transcripts to database"""
        try:
            # Check if voice conversation exists
            stmt = select(Conversation).where(
                Conversation.persona_id == persona_id,
                Conversation.session_id == session_id,
                Conversation.conversation_type == "voice",
            )
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()

            # Format messages for database
            formatted_messages = []
            for msg in transcript_messages:
                # Normalize speaker to role format
                role = "user" if msg["speaker"] == "user" else "assistant"

                message_data = {
                    "role": role,
                    "content": msg["text"],
                    "timestamp": msg.get("timestamp", datetime.utcnow().isoformat()),
                    "message_type": "transcript",
                    "speaker_raw": msg["speaker"],  # Keep original for debugging
                }

                # Add sources if available (for assistant messages)
                if role == "assistant" and "sources" in msg:
                    message_data["sources"] = msg["sources"]

                formatted_messages.append(message_data)

            if conversation:
                # Update existing conversation with message limits
                existing_messages = conversation.messages or []

                # Implement a rolling window to prevent unbounded growth
                MAX_MESSAGES_PER_CONVERSATION = 1000
                if len(existing_messages) + len(formatted_messages) > MAX_MESSAGES_PER_CONVERSATION:
                    # Keep only the most recent messages
                    messages_to_keep = MAX_MESSAGES_PER_CONVERSATION - len(formatted_messages)
                    existing_messages = (
                        existing_messages[-messages_to_keep:] if messages_to_keep > 0 else []
                    )
                    logger.warning(
                        f"Truncating conversation to {MAX_MESSAGES_PER_CONVERSATION} messages"
                    )

                existing_messages.extend(formatted_messages)
                conversation.messages = existing_messages
                conversation.updated_at = datetime.utcnow()
                # Mark the JSONB field as modified so SQLAlchemy detects the change
                attributes.flag_modified(conversation, "messages")
            else:
                # Create new voice conversation
                conversation = Conversation(
                    persona_id=persona_id,
                    session_id=session_id,
                    conversation_type="voice",
                    user_email=user_email,
                    messages=formatted_messages,
                    conversation_metadata={
                        "total_transcript_messages": len(formatted_messages),
                        "session_type": "voice_chat",
                    },
                )
                session.add(conversation)

            await session.commit()
            logger.info(
                f"✅ Saved voice conversation with {len(formatted_messages)} transcript messages"
            )

            # Send webhook notification (fire-and-forget)
            asyncio.create_task(
                self._send_conversation_webhook(
                    persona_id=persona_id,
                    conversation_id=conversation.id,
                    session_id=session_id,
                    conversation_type="voice",
                    message_count=len(formatted_messages),
                    user_email=user_email,
                )
            )

            return True

        except Exception as e:
            logger.error(f"❌ Error saving voice conversation: {e}")
            await session.rollback()
            return False

    async def _send_conversation_webhook(
        self,
        persona_id: UUID,
        conversation_id: UUID,
        session_id: Optional[str],
        conversation_type: str,
        message_count: int,
        user_email: Optional[str] = None,
    ):
        """
        Send webhook notification for saved conversation (fire-and-forget)

        This runs in background task and handles all errors internally.

        Args:
            persona_id: UUID of the persona
            conversation_id: UUID of the saved conversation
            session_id: Session token/ID
            conversation_type: "voice" or "text"
            message_count: Number of messages in the conversation
            user_email: Optional visitor email (for voice conversations)
        """
        try:
            webhook_service = WebhookService()

            # Build event data payload
            event_data = {
                "conversation_id": str(conversation_id),
                "session_id": session_id,
                "conversation_type": conversation_type,
                "message_count": message_count,
            }

            # Add user_email for voice conversations if available
            if user_email:
                event_data["user_email"] = user_email

            # Send webhook (service handles validation and delivery)
            await webhook_service.send_event(
                persona_id=persona_id, event_type="conversation.finished", event_data=event_data
            )

            # Cleanup
            await webhook_service.close()

        except Exception as e:
            # Log error but don't raise - this is fire-and-forget
            logger.error(
                f"❌ Failed to send webhook for conversation {conversation_id}: {e}", exc_info=True
            )
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(persona_id),
                    "conversation_id": str(conversation_id),
                    "session_id": session_id,
                    "conversation_type": conversation_type,
                },
                tags={
                    "component": "generator",
                    "operation": "send_conversation_webhook",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )

    async def generate_with_fallback(
        self, session: AsyncSession, persona_id: UUID, message: str, **kwargs
    ) -> Dict[str, Any]:
        try:
            # Try primary generation
            return await self.generate_response(session, persona_id, message, **kwargs)
        except Exception as e:
            logger.error(f"Primary generation failed: {e}")

            # Fallback to simpler generation
            try:
                persona = await self.get_persona(session, persona_id)
                if not persona:
                    raise ValueError("Persona not found")

                simple_response = await self.generate_base_response(
                    f"You are {persona.name}. Respond naturally and authentically.",
                    message,
                    temperature=0.7,
                    max_tokens=500,
                )

                return {
                    "response": simple_response,
                    "session_id": kwargs.get("session_id"),
                    "thinking_pattern": "FALLBACK",
                    "sources": [],
                }

            except Exception as fallback_error:
                logger.error(f"Fallback generation also failed: {fallback_error}")
                raise
