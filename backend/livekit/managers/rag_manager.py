"""
RAG Manager

Handles RAG context injection with document support.

Responsibilities:
- Retrieve context from knowledge base
- Include uploaded document context
- Send citations to frontend
- Inject combined context into chat

Created: 2026-01-25
"""

import json
import logging
from typing import Any, Optional
from uuid import UUID

from livekit.agents import llm
from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class RAGManager:
    """
    Manages RAG context injection with document support.

    Combines knowledge base retrieval with uploaded document context.
    """

    def __init__(
        self,
        persona_id: UUID,
        session_context,
        lifecycle_handler,
        rag_system: Optional[Any] = None,
    ):
        """
        Initialize RAG manager.

        Args:
            persona_id: Persona UUID for filtering RAG results
            session_context: SessionContext instance for document access
            lifecycle_handler: LifecycleHandler for sending citations
            rag_system: Optional RAG system (lazy loaded if not provided)
        """
        self.persona_id = persona_id
        self.session_context = session_context
        self.lifecycle_handler = lifecycle_handler
        self.rag_system = rag_system

        self.logger = logging.getLogger(__name__)

    async def inject_rag_context(self, chat_ctx: llm.ChatContext):
        """
        Inject RAG context from knowledge base and uploaded documents.

        Process:
        1. Extract user query from chat context
        2. Retrieve relevant context from RAG system
        3. Get document context from session (uploaded files)
        4. Combine both contexts
        5. Send citations to frontend
        6. Inject combined context into chat

        Args:
            chat_ctx: LiveKit chat context to inject RAG into
        """
        try:
            # Step 1: Lazy load RAG system if needed
            if not self.rag_system:
                from shared.rag.rag_singleton import get_rag_system

                self.rag_system = get_rag_system()

            # Step 2: Check chat_ctx.items
            if not chat_ctx.items:
                return

            # Step 3: Parse message text helper
            def parse_message_text(text: str) -> str:
                """Parse JSON-wrapped messages from frontend (text-only mode sends {"message": "..."})"""
                if not text:
                    return ""
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict) and "message" in parsed:
                        return parsed["message"].strip()
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass
                return text.strip()

            # Step 4: Extract user queries
            user_queries = []
            for item in reversed(chat_ctx.items):
                if not hasattr(item, "role"):
                    continue

                if item.role == "user":
                    text = item.text_content or ""
                    parsed_text = parse_message_text(text)
                    if parsed_text:
                        user_queries.insert(0, parsed_text)
                elif item.role in ["assistant", "agent"]:
                    break

            if not user_queries:
                return

            user_query = " ".join(user_queries)

            # Step 5: Build chat history
            chat_history = []
            for item in chat_ctx.items:
                if hasattr(item, "role") and hasattr(item, "text_content"):
                    role_name = str(getattr(item, "role", "user")).lower()
                    if role_name == "system":
                        continue
                    text = item.text_content or ""
                    text = parse_message_text(text)
                    chat_history.append({"role": role_name, "content": text})

            # Step 6: Call ContextPipeline
            from shared.generation.context_pipeline import ContextPipeline

            context_result = await ContextPipeline(
                self.rag_system,
                use_reranker=settings.use_reranker,
                reranker_provider=settings.reranker_provider,
            ).process(
                persona_id=str(self.persona_id),
                user_query=user_query,
                top_k=5,
                similarity_threshold=0.4,
                chat_history=chat_history,
                return_citations=True,
            )

            # Step 7: Parse context result
            if isinstance(context_result, dict):
                context_text = context_result.get("context", "")
                sources = context_result.get("sources", [])
                formatted_context = context_result.get("formatted_context", "")

                # If context is empty but formatted_context exists, use that
                if not context_text and formatted_context:
                    context_text = formatted_context
            else:
                context_text = context_result if isinstance(context_result, str) else ""
                sources = []

            # Step 8: Get document context
            document_context = self.session_context.get_document_context(max_chars=50000)

            # Step 9: Build combined context
            combined_context = []

            if document_context:
                combined_context.append(document_context)

            if context_text:
                rag_context_block = (
                    "Knowledge Base Context:\n"
                    "---------------------\n"
                    f"{context_text}\n"
                    "---------------------\n"
                )
                combined_context.append(rag_context_block)

                # Send citations to frontend
                await self.lifecycle_handler.send_citations(sources, user_query)

            # Step 10: Inject into chat context
            if combined_context:
                combined_text = (
                    "\n\n".join(combined_context) + "\nGiven the context above, answer the query.\n"
                )

                # Use EXACT same format as legacy agent for compatibility
                rag_msg = llm.ChatMessage(
                    role="system",
                    content=[
                        "Context information is below.\n"
                        "---------------------\n"
                        f"{combined_text}\n"
                        "---------------------\n"
                        "Given the context above, answer the query.\n"
                    ],
                )

                # Calculate insertion position: Insert BEFORE the last user message
                insert_position = 1  # Default: right after system prompt

                # Find position of the LAST user message (the current query)
                for i in range(len(chat_ctx.items) - 1, -1, -1):
                    item = chat_ctx.items[i]
                    if hasattr(item, "role") and item.role == "user":
                        insert_position = i  # Insert BEFORE the last user message
                        break

                chat_ctx.items.insert(insert_position, rag_msg)

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "has_rag_system": bool(self.rag_system),
                    "has_document_context": bool(
                        self.session_context.get_document_context(max_chars=1)
                    ),
                },
                tags={
                    "component": "rag_manager",
                    "operation": "inject_rag_context",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"RAG retrieval failed: {e}", exc_info=True)

    def update_rag_system(self, rag_system: Any):
        """
        Update RAG system reference.

        Args:
            rag_system: New RAG system instance
        """
        self.rag_system = rag_system
        self.logger.info("RAG system updated")
