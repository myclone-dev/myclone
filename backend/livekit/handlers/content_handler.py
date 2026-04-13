"""
Content Handler

Handles content generation and delivery for content mode.
Uses an isolated LLM call (separate from the voice pipeline) to generate
long-form content without brevity constraints.
Publishes structured content to frontend via data channel.
"""

import json
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from livekit.agents.llm.tool_context import ToolError
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.schemas.livekit import PersonaPromptMetadata

logger = logging.getLogger(__name__)


class ContentHandler:
    """
    Handles content creation tool operations.

    Responsibilities:
    - Build a content-specific prompt (no brevity rules, markdown encouraged)
    - Make an isolated LLM call to generate the content body
    - Format drafted content as structured JSON
    - Queue content for delivery (published after LLM confirmation speech)
    - Return confirmation to voice LLM
    """

    VALID_CONTENT_TYPES = {"blog", "linkedin_post", "newsletter"}

    def __init__(
        self,
        room,
        persona_info: Dict[str, Any],
        persona_prompt_info: Optional[PersonaPromptMetadata] = None,
        persona_id: Optional[UUID] = None,
        rag_system: Optional[Any] = None,
    ):
        self.room = room
        self.persona_info = persona_info
        self.persona_prompt_info = persona_prompt_info
        self.persona_id = persona_id
        self.rag_system = rag_system
        self.logger = logging.getLogger(__name__)
        self._pending_content: bytes | None = None

    async def _publish_status(self, status: str, message: str = "") -> None:
        """Publish agent status event to frontend via data channel."""
        from livekit.utils import publish_agent_status

        await publish_agent_status(self.room, status, message)

    async def generate_content(
        self,
        content_type: str,
        title: str,
        topic: str,
        audience: str = "",
        tone: str = "",
        search_context: str = "",
    ) -> str:
        """
        Generate content via isolated LLM call and deliver to frontend.

        Args:
            content_type: Type of content (blog, linkedin_post, newsletter)
            title: Content title
            topic: The topic to write about
            audience: Target audience description
            tone: Writing tone/style
            search_context: Search results to incorporate (passed from agent)

        Returns:
            Confirmation message for voice LLM

        Raises:
            ToolError: If content_type is invalid or generation/delivery fails
        """
        self.logger.info(
            f"📝 [CONTENT] generate_content(type={content_type}, title={title[:50]}, topic={topic[:50]})"
        )

        if content_type not in self.VALID_CONTENT_TYPES:
            raise ToolError(
                f"Invalid content_type '{content_type}'. "
                f"Must be one of: {', '.join(self.VALID_CONTENT_TYPES)}"
            )

        if self._pending_content is not None:
            raise ToolError(
                "A content piece is already pending delivery. "
                "Please wait for it to be sent before generating another."
            )

        try:
            # Generate content body via isolated LLM call
            body = await self._generate_content_body(
                content_type=content_type,
                title=title,
                topic=topic,
                audience=audience,
                tone=tone,
                search_context=search_context,
            )

            payload = {
                "type": "content_output",
                "content_type": content_type,
                "title": title,
                "body": body,
                "persona_name": self.persona_info.get("name", ""),
                "persona_role": self.persona_info.get("role", ""),
            }

            # Queue content for delivery — will be published at the START
            # of the next llm_node call (the confirmation turn)
            self._pending_content = json.dumps(payload).encode("utf-8")

            self.logger.info(
                f"📦 [CONTENT] Queued {content_type}: '{title}' "
                f"({len(body)} chars) — will publish after confirmation speech"
            )

            content_label = content_type.replace("_", " ")
            return (
                f"Content ready! The {content_label} titled '{title}' "
                f"will appear on the user's screen after you speak. "
                f"Tell the user: 'Here's your {content_label}! It's on your screen now — "
                f"you can copy, download, or share it. Let me know if you want any changes.'"
            )

        except ToolError:
            raise
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "content_type": content_type,
                    "title": title[:200],
                    "topic": topic[:200],
                },
                tags={
                    "component": "content_handler",
                    "operation": "generate_content",
                    "severity": "medium",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Failed to generate/deliver content: {e}", exc_info=True)
            raise ToolError("Failed to generate content. Please try again.")

    async def _generate_content_body(
        self,
        content_type: str,
        title: str,
        topic: str,
        audience: str,
        tone: str,
        search_context: str,
    ) -> str:
        """
        Make an isolated LLM call to generate the content body.

        This is completely separate from the voice pipeline — no brevity rules,
        full markdown, long-form output.

        Returns:
            Generated content body as markdown string
        """
        from livekit.agents import llm
        from livekit.plugins import openai

        # Retrieve relevant RAG context for the topic
        rag_context = await self._retrieve_rag_context(topic)

        # Build the system prompt for the content writer LLM
        system_prompt = self._build_content_system_prompt(content_type)

        # Build the user message with all inputs
        user_message = self._build_content_user_message(
            content_type=content_type,
            title=title,
            topic=topic,
            audience=audience,
            tone=tone,
            search_context=search_context,
            rag_context=rag_context,
        )

        # Build a clean ChatContext for the isolated call
        chat_ctx = llm.ChatContext()
        chat_ctx.items.append(llm.ChatMessage(role="system", content=[system_prompt]))
        chat_ctx.items.append(llm.ChatMessage(role="user", content=[user_message]))

        # Create a separate LLM instance (not shared with voice pipeline)
        content_llm = openai.LLM(
            model="gpt-4.1-mini",
            max_completion_tokens=4096,
        )

        self.logger.info(
            f"🤖 [CONTENT] Starting isolated LLM call for {content_type} "
            f"(system_prompt={len(system_prompt)} chars, user_msg={len(user_message)} chars)"
        )

        # Show writing status to frontend
        content_label = content_type.replace("_", " ")
        await self._publish_status("writing", f"Writing your {content_label}...")

        try:
            # Collect the full response
            # LiveKit's LLM.chat() yields ChatChunk objects with chunk.delta.content
            body_parts = []
            async for chunk in content_llm.chat(chat_ctx=chat_ctx):
                if chunk.delta and chunk.delta.content:
                    body_parts.append(chunk.delta.content)

            body = "".join(body_parts)

            self.logger.info(
                f"✅ [CONTENT] Isolated LLM generated {len(body)} chars for {content_type}"
            )

            if not body.strip():
                raise ToolError("Content generation returned empty result. Please try again.")

            return body
        finally:
            await self._publish_status("idle")

    def _build_content_system_prompt(self, content_type: str) -> str:
        """Build the system prompt for the isolated content writer LLM."""
        from livekit.constants.content_prompts import (
            CONTENT_TYPE_TEMPLATES,
            CONTENT_WRITER_SYSTEM_PROMPT,
        )

        persona_name = self.persona_info.get("name", "the persona")
        persona_role = self.persona_info.get("role", "Expert")

        # Build persona style section from prompt info if available
        persona_style_section = self._build_persona_style_section()

        # Get content-type-specific structure instructions
        content_type_instructions = CONTENT_TYPE_TEMPLATES.get(content_type, "")

        return CONTENT_WRITER_SYSTEM_PROMPT.format(
            persona_name=persona_name,
            persona_role=persona_role,
            persona_style_section=persona_style_section,
            content_type_instructions=content_type_instructions,
        )

    def _build_persona_style_section(self) -> str:
        """Extract persona voice/style info from persona_prompt_info."""
        if not self.persona_prompt_info:
            return "Write in a professional, knowledgeable tone."

        sections = []

        if self.persona_prompt_info.thinking_style:
            sections.append(f"THINKING STYLE: {self.persona_prompt_info.thinking_style}")

        if self.persona_prompt_info.area_of_expertise:
            sections.append(f"AREA OF EXPERTISE: {self.persona_prompt_info.area_of_expertise}")

        if self.persona_prompt_info.example_responses:
            sections.append(
                f"EXAMPLE WRITING STYLE (match this voice):\n{self.persona_prompt_info.example_responses}"
            )

        if self.persona_prompt_info.response_structure:
            sections.append(f"RESPONSE STRUCTURE: {self.persona_prompt_info.response_structure}")

        if not sections:
            return "Write in a professional, knowledgeable tone."

        return "PERSONA VOICE & STYLE:\n" + "\n\n".join(sections)

    def _build_content_user_message(
        self,
        content_type: str,
        title: str,
        topic: str,
        audience: str,
        tone: str,
        search_context: str,
        rag_context: str = "",
    ) -> str:
        """Build the user message combining all inputs for the content writer LLM."""
        parts = [
            f"Write a {content_type.replace('_', ' ')} with the following details:",
            f"\nTitle: {title}",
            f"Topic: {topic}",
        ]

        if audience:
            parts.append(f"Target Audience: {audience}")
        if tone:
            parts.append(f"Tone: {tone}")

        if rag_context:
            parts.append(
                f"\n--- PERSONA KNOWLEDGE BASE (use for opinions, experiences, unique angles) ---\n{rag_context}"
            )

        if search_context:
            parts.append(
                f"\n--- RESEARCH RESULTS (use for facts, stats, recent developments) ---\n{search_context}"
            )

        return "\n".join(parts)

    async def _retrieve_rag_context(self, topic: str) -> str:
        """Retrieve relevant persona knowledge base context for the topic.

        Uses the same ContextPipeline as the voice agent's RAG manager,
        but queries with the content topic instead of the user's spoken query.

        Returns:
            Formatted RAG context string, or empty string if unavailable.
        """
        if not self.rag_system or not self.persona_id:
            self.logger.info("⚠️ [CONTENT] No RAG system or persona_id — skipping RAG retrieval")
            return ""

        try:
            from shared.config import settings
            from shared.generation.context_pipeline import ContextPipeline

            context_result = await ContextPipeline(
                self.rag_system,
                use_reranker=settings.use_reranker,
                reranker_provider=settings.reranker_provider,
            ).process(
                persona_id=str(self.persona_id),
                user_query=topic,
                top_k=5,
                similarity_threshold=0.4,
                chat_history=[],
                return_citations=True,
            )

            if isinstance(context_result, dict):
                context_text = context_result.get("formatted_context", "") or context_result.get(
                    "context", ""
                )
            else:
                context_text = context_result if isinstance(context_result, str) else ""

            if context_text:
                self.logger.info(
                    f"📚 [CONTENT] RAG retrieved {len(context_text)} chars for topic: {topic[:50]}"
                )
            else:
                self.logger.info(
                    f"📚 [CONTENT] No relevant RAG context found for topic: {topic[:50]}"
                )

            return context_text

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"topic": topic[:200], "persona_id": str(self.persona_id)},
                tags={
                    "component": "content_handler",
                    "operation": "retrieve_rag_context",
                    "severity": "low",
                    "user_facing": "false",
                },
            )
            self.logger.warning(f"⚠️ [CONTENT] RAG retrieval failed, proceeding without: {e}")
            return ""

    def update_rag_system(self, rag_system: Any):
        """Update RAG system reference (called after async init)."""
        self.rag_system = rag_system

    async def flush_pending_content(self) -> None:
        """Publish any queued content to the frontend via data channel.

        Called from llm_node at the START of the confirmation turn
        (the turn after generate_content was called), so the content
        card appears when the agent starts saying "Here's your blog!".
        """
        if self._pending_content is None:
            return

        try:
            await self.room.local_participant.publish_data(
                payload=self._pending_content,
                topic="content_output",
                reliable=True,
            )
            self.logger.info("✅ [CONTENT] Flushed pending content to frontend")
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"pending_content_size": len(self._pending_content)},
                tags={
                    "component": "content_handler",
                    "operation": "flush_pending_content",
                    "severity": "medium",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Failed to flush pending content: {e}", exc_info=True)
        finally:
            self._pending_content = None
