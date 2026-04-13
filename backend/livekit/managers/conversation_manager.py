"""
Conversation Manager

Handles conversation history management and injection.

Responsibilities:
- Maintain conversation history list
- Load previous conversation from database
- Extract messages from chat context
- Inject history into chat context
- Track user/assistant message pairs

Created: 2026-01-25
"""

import logging
import os
from typing import Any, Dict, List, Optional
from uuid import UUID

from livekit.agents import llm
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Manages conversation history tracking and injection.

    Keeps conversation history in memory and provides methods to
    update from chat context and inject back into context.
    """

    def __init__(
        self,
        session_context,
        email_capture_handler=None,
        persona_id: Optional[UUID] = None,
        session_token: Optional[str] = None,
        text_only_mode: bool = False,
    ):
        """
        Initialize conversation manager.

        Args:
            session_context: SessionContext instance for message tracking
            email_capture_handler: Optional EmailCaptureHandler for message counting
            persona_id: Persona UUID for loading conversation history
            session_token: Session token for loading conversation history
            text_only_mode: Whether in text-only mode (affects conversation_type)
        """
        self.session_context = session_context
        self.email_capture_handler = email_capture_handler
        self.persona_id = persona_id
        self.session_token = session_token
        self.text_only_mode = text_only_mode

        # Conversation history (in-memory)
        self._conversation_history: List[Dict[str, Any]] = []

        self.logger = logging.getLogger(__name__)

    @property
    def _conversation_type(self) -> str:
        """Determine conversation type based on mode"""
        return "text" if self.text_only_mode else "voice"

    async def load_conversation_history(self):
        """
        Load previous conversation history from database.

        Loads up to VOICE_HISTORY_LIMIT messages from the database if a session_token
        is provided. This allows conversation continuity across reconnections.
        """
        try:
            if not self.session_token or not self.persona_id:
                self.logger.debug("No session token or persona ID - skipping history load")
                return

            from sqlalchemy import select

            from shared.database.models.database import Conversation, async_session_maker

            max_messages = int(os.getenv("VOICE_HISTORY_LIMIT", "50"))

            async with async_session_maker() as db_session:
                stmt = select(Conversation).where(
                    Conversation.persona_id == self.persona_id,
                    Conversation.session_id == self.session_token,
                    Conversation.conversation_type == self._conversation_type,
                )
                result = await db_session.execute(stmt)
                conversation = result.scalar_one_or_none()

                if conversation and conversation.messages:
                    import json

                    total_messages = len(conversation.messages)
                    messages = (
                        conversation.messages[-max_messages:]
                        if total_messages > max_messages
                        else conversation.messages
                    )

                    # Parse messages and clean up JSON-wrapped content
                    cleaned_messages = []
                    for msg in messages:
                        content = msg.get("content", "")
                        if not content:
                            continue

                        # Try to parse JSON-wrapped messages
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, dict) and "message" in parsed:
                                content = parsed["message"]
                        except (json.JSONDecodeError, ValueError, TypeError):
                            # Not JSON or parsing failed, use as-is
                            pass

                        cleaned_messages.append(
                            {"role": msg.get("role", "user"), "content": content}
                        )

                    self._conversation_history = cleaned_messages

                    self.logger.info(
                        f"✅ Loaded {len(self._conversation_history)} history messages "
                        f"(total: {total_messages}, limit: {max_messages})"
                    )
                else:
                    self.logger.debug(
                        f"No conversation history found for session {self.session_token[:8]}"
                    )

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id) if self.persona_id else None,
                    "session_token": self.session_token,
                    "conversation_type": self._conversation_type,
                },
                tags={
                    "component": "conversation_manager",
                    "operation": "load_conversation_history",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to load conversation history: {e}", exc_info=True)
            # Don't raise - conversation can continue without history

    async def update_conversation_history(
        self, chat_ctx: llm.ChatContext, collected_response: list
    ):
        """
        Update conversation history after each turn.

        Extracts user and assistant messages from chat context and adds to history.

        Args:
            chat_ctx: LiveKit chat context
            collected_response: List of response chunks from LLM
        """
        try:
            import json

            # Extract latest user and assistant messages from chat context
            user_msg = None
            assistant_msg = None

            for item in reversed(chat_ctx.items):
                if not hasattr(item, "role") or not hasattr(item, "text_content"):
                    continue

                role = str(item.role).lower()
                content = item.text_content or ""

                if role == "user" and not user_msg:
                    # Parse JSON-wrapped messages from frontend (text-only mode)
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict) and "message" in parsed:
                            user_msg = parsed["message"].strip()
                        else:
                            user_msg = content.strip()
                    except (json.JSONDecodeError, ValueError, TypeError):
                        user_msg = content.strip()

                elif role in ["assistant", "agent"] and not assistant_msg:
                    assistant_msg = content.strip()

                # Stop once we have both
                if user_msg and assistant_msg:
                    break

            # Use collected_response if available (more reliable for streaming responses)
            if collected_response:
                assistant_msg = "".join(collected_response)

            # Add to history (avoid duplicates - check entire history)
            if user_msg and assistant_msg:
                # Check if this exact user+assistant pair already exists ANYWHERE in history
                already_exists = False

                for i in range(len(self._conversation_history) - 1):
                    curr = self._conversation_history[i]
                    next_msg = self._conversation_history[i + 1]

                    if (
                        curr.get("role") == "user"
                        and curr.get("content") == user_msg
                        and next_msg.get("role") == "assistant"
                        and next_msg.get("content") == assistant_msg
                    ):
                        already_exists = True
                        self.logger.info(
                            f"⏭️  Skipping duplicate: user='{user_msg[:50]}...', assistant='{assistant_msg[:50]}...'"
                        )
                        break

                # NOTE: conversation_item_added handler in entrypoint.py handles adding to history
                # This avoids duplicates since that handler fires first
                if not already_exists:
                    # Just update session_context for tracking (not _conversation_history)
                    self.session_context.add_user_message(user_msg)
                    self.session_context.add_assistant_message(assistant_msg)

            # NOTE: Message counting for email capture is handled in entrypoint.py
            # via the conversation_item_added event handler. Don't duplicate here!

            self.logger.info(
                f"✅ Updated conversation history ({len(self._conversation_history)} messages)"
            )

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "has_user_msg": bool(user_msg),
                    "has_assistant_msg": bool(assistant_msg),
                    "history_size": len(self._conversation_history),
                },
                tags={
                    "component": "conversation_manager",
                    "operation": "update_conversation_history",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to update history: {e}", exc_info=True)

    def inject_conversation_history(self, chat_ctx: llm.ChatContext, max_messages: int = 10):
        """
        Inject conversation history into chat context.

        Args:
            chat_ctx: LiveKit chat context
            max_messages: Maximum number of recent messages to inject (default: 10)
        """
        try:
            if not self._conversation_history:
                self.logger.debug("No conversation history to inject")
                return

            # Convert history to chat messages
            history_messages = [
                llm.ChatMessage(role=msg["role"], content=[msg["content"]])
                for msg in self._conversation_history[-max_messages:]
                if msg.get("content")
            ]

            if history_messages:
                # Insert after system prompt (position 1)
                chat_ctx.items[1:1] = history_messages

                # Add session boundary marker after history so the LLM
                # knows prior content/tool workflows are complete
                boundary_msg = llm.ChatMessage(
                    role="system",
                    content=[
                        "--- NEW SESSION ---\n"
                        "The messages above are from a previous session for context only. "
                        "Any prior content requests, tool calls, or workflows are COMPLETE. "
                        "Do NOT resume or continue them. Treat the next user message as a "
                        "fresh request in a new conversation."
                    ],
                )
                # Insert after history (position 1 + len(history))
                chat_ctx.items.insert(1 + len(history_messages), boundary_msg)

                self.logger.info(
                    f"✅ Injected {len(history_messages)} history messages + session boundary"
                )

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "history_size": len(self._conversation_history),
                    "max_messages": max_messages,
                },
                tags={
                    "component": "conversation_manager",
                    "operation": "inject_conversation_history",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Failed to inject history: {e}", exc_info=True)

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """
        Get the conversation history.

        Returns:
            List of message dictionaries with 'role' and 'content' keys
        """
        return self._conversation_history

    def clear_conversation_history(self):
        """Clear conversation history (useful for testing or reset)."""
        self._conversation_history.clear()
        self.logger.info("🗑️ Conversation history cleared")

    def get_message_count(self) -> int:
        """Get total number of messages in conversation history."""
        return len(self._conversation_history)
