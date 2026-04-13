"""
Lifecycle Handler

Manages agent lifecycle events:
- Sending suggested questions to frontend
- Cleanup on agent exit
- Post-turn processing hooks
- STT/TTS/LLM error capture (Sentry)
- Session close error capture (Sentry)

Note: Greeting is handled by livekit_agent.py on_enter() directly.

Created: 2026-01-25
"""

import json
import logging
from typing import Any, Dict, List
from uuid import UUID

from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


class LifecycleHandler:
    """
    Handles agent lifecycle events.

    Responsibilities:
    - Sending suggested questions to frontend
    - Cleanup on agent exit
    - Post-turn processing hooks

    Note: Greeting is handled directly by livekit_agent.py on_enter()
    using session.say() with localized templates.
    """

    def __init__(
        self,
        persona_id: UUID,
        persona_info: Dict[str, Any],
        room,
        room_name: str,
    ):
        """
        Initialize lifecycle handler.

        Args:
            persona_id: Persona UUID
            persona_info: Persona information dict
            room: LiveKit room instance
            room_name: Room name for cleanup
        """
        self.persona_id = persona_id
        self.persona_info = persona_info
        self.room = room
        self.room_name = room_name

        self.logger = logging.getLogger(__name__)

    async def send_suggested_questions(self):
        """Send suggested questions to frontend via data channel."""
        suggested_questions = self.persona_info.get("suggested_questions")

        if not suggested_questions:
            self.logger.debug("No suggested questions to send")
            return

        try:
            payload = {
                "type": "suggested_questions",
                "questions": suggested_questions,
                "persona_id": str(self.persona_id),
            }

            await self.room.local_participant.publish_data(
                payload=json.dumps(payload).encode("utf-8"),
                topic="suggested_questions",
                reliable=True,
            )
            self.logger.info(f"✅ Sent {len(suggested_questions)} suggested questions")

        except Exception as e:
            self.logger.error(f"❌ Failed to send suggested questions: {e}", exc_info=True)
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "question_count": len(suggested_questions),
                    "room_name": self.room_name,
                },
                tags={
                    "component": "lifecycle_handler",
                    "operation": "send_suggested_questions",
                    "severity": "medium",
                    "user_facing": "true",
                },
            )

    async def on_exit(self, document_handler=None):
        """
        Called when agent exits the room.

        Cleanup tasks:
        - Close document processor
        - Clean up room from database
        - Any other resource cleanup

        Args:
            document_handler: Optional DocumentHandler for cleanup
        """
        persona_username = self.persona_info.get("username", "unknown")
        self.logger.info(f"🚪 [{persona_username}] Agent closing")

        # Clean up document processor
        if document_handler:
            try:
                await document_handler.close()
                self.logger.debug("✅ Document processor closed")
            except Exception as e:
                self.logger.error(f"Failed to close document processor: {e}")

        # Clean up room from active rooms database
        try:
            if self.room_name:
                from shared.database.repositories.livekit_repository import LiveKitDatabase

                db = LiveKitDatabase()
                await db.remove_active_room(self.room_name)
                self.logger.info(f"✅ Cleaned up room from database: {self.room_name}")
        except Exception as e:
            self.logger.error(f"Failed to clean up room: {e}")

    async def send_citations(self, sources: List[Dict[str, Any]], user_query: str):
        """
        Send RAG sources/citations to frontend.

        Args:
            sources: List of source dictionaries with URL, title, content
            user_query: Original user query
        """
        if not sources:
            return

        if not self.room:
            self.logger.warning("Room is None - cannot send citations")
            return

        try:
            # Format sources for frontend
            # Frontend CitationSource interface expects:
            #   title, content, similarity, source_url, source_type, raw_source
            formatted_sources = []
            for source in sources[:5]:  # Limit to top 5
                formatted_sources.append(
                    {
                        "title": source.get("title", "Untitled"),
                        "source_url": source.get("source_url") or source.get("url", ""),
                        "content": source.get("content", "")[:300],  # First 300 chars
                        "similarity": source.get("similarity") or source.get("score", 0.0),
                        "source_type": source.get("source_type", "document"),
                        "raw_source": source.get("raw_source") or source.get("source_type", ""),
                    }
                )

            payload = {
                "type": "citations",
                "query": user_query,
                "sources": formatted_sources,
            }

            await self.room.local_participant.publish_data(
                payload=json.dumps(payload).encode("utf-8"),
                topic="citations",
                reliable=True,
            )

            self.logger.info(f"Sent {len(formatted_sources)} citations to frontend")

        except Exception as e:
            self.logger.error(f"Failed to send citations: {e}", exc_info=True)
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "source_count": len(sources),
                    "query": user_query,
                },
                tags={
                    "component": "lifecycle_handler",
                    "operation": "send_citations",
                    "severity": "low",
                    "user_facing": "false",
                },
            )

    def on_agent_error(self, ev) -> None:
        """
        Handle STT/TTS/LLM errors from AgentSession.

        Register with: session.on("error", lifecycle_handler.on_agent_error)

        Logs recoverable errors as warnings. Captures unrecoverable errors in Sentry.
        """
        try:
            error = ev.error
            source_name = type(ev.source).__name__
            error_type = getattr(error, "type", "unknown")
            is_recoverable = getattr(error, "recoverable", True)
            error_label = getattr(error, "label", str(error))
            root_error = getattr(error, "error", error)

            if is_recoverable:
                self.logger.warning(f"⚠️ Recoverable {error_type} from {source_name}: {error_label}")
                return

            self.logger.error(f"🚨 Unrecoverable {error_type} from {source_name}: {error_label}")
            capture_exception_with_context(
                root_error if isinstance(root_error, Exception) else Exception(str(root_error)),
                extra={
                    "error_type": error_type,
                    "source": source_name,
                    "label": error_label,
                    "recoverable": False,
                    "persona_id": str(self.persona_id),
                    "room_name": self.room_name,
                },
                tags={
                    "component": "livekit_agent",
                    "operation": f"{error_type}_error",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
        except Exception as e:
            self.logger.error(f"Error in on_agent_error handler: {e}")

    def on_session_close(self, ev) -> None:
        """
        Handle AgentSession close events.

        Register with: session.on("close", lifecycle_handler.on_session_close)

        Captures unrecoverable errors (reason=ERROR) in Sentry so failures like
        Deepgram 402, TTS timeouts, etc. don't go unnoticed.
        """
        try:
            from livekit.agents.voice import CloseReason

            reason = ev.reason
            self.logger.info(f"🔒 AgentSession closed: reason={reason.value}")

            if reason != CloseReason.ERROR or not ev.error:
                return

            error = ev.error
            error_type = getattr(error, "type", "unknown")
            root_error = getattr(error, "error", error)

            self.logger.error(f"🚨 Session closed due to unrecoverable {error_type}: {root_error}")
            capture_exception_with_context(
                root_error if isinstance(root_error, Exception) else Exception(str(root_error)),
                extra={
                    "close_reason": reason.value,
                    "error_type": error_type,
                    "persona_id": str(self.persona_id),
                    "room_name": self.room_name,
                },
                tags={
                    "component": "livekit_agent",
                    "operation": "session_close_error",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
        except Exception as e:
            self.logger.error(f"Error in on_session_close handler: {e}")
