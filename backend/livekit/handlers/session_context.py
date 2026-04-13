"""
Session Context Management

Manages per-session conversation history and context.

Created: 2026-01-25
"""

from typing import Any, Dict, List
from uuid import UUID


class SessionContext:
    """Manages per-session context and conversation history"""

    def __init__(self, session_id: str, persona_id: UUID):
        self.session_id = session_id
        self.persona_id = persona_id
        self.conversation_history = []
        self.retrieved_contexts = []
        self.turn_count = 0
        self.user_message_count = 0  # For email capture threshold

        # Document tracking
        self.uploaded_documents: List[Dict[str, Any]] = []
        self._document_context_cache: str = ""

    def add_user_message(self, message: str):
        """Add user message to history and increment count"""
        self.conversation_history.append({"role": "user", "content": message})
        self.turn_count += 1
        self.user_message_count += 1

    def add_assistant_message(self, message: str):
        """Add assistant message to history"""
        self.conversation_history.append({"role": "assistant", "content": message})

    def add_document(self, filename: str, extracted_text: str, doc_type: str):
        """
        Add uploaded document to session context.

        Args:
            filename: Document filename
            extracted_text: Extracted text content
            doc_type: Document type (pdf, docx, etc.)
        """
        self.uploaded_documents.append(
            {
                "filename": filename,
                "text": extracted_text,
                "type": doc_type,
            }
        )
        # Invalidate cache
        self._document_context_cache = ""

    def get_document_context(self, max_chars: int = 50000) -> str:
        """
        Get combined document context for LLM injection.

        Args:
            max_chars: Maximum characters to return

        Returns:
            Combined document text
        """
        if not self.uploaded_documents:
            return ""

        # Use cache if available
        if self._document_context_cache:
            return self._document_context_cache[:max_chars]

        # Build context from all uploaded documents
        context_parts = []
        context_parts.append("📄 **UPLOADED DOCUMENTS (Reference for answering questions)**\n")

        for doc in self.uploaded_documents:
            context_parts.append(f"\n--- Document: {doc['filename']} ({doc['type']}) ---\n")
            context_parts.append(doc["text"])
            context_parts.append("\n--- End of Document ---\n")

        context_parts.append(
            "\nUse the above documents to answer user questions. "
            "Reference specific parts when answering.\n"
        )

        self._document_context_cache = "".join(context_parts)
        return self._document_context_cache[:max_chars]

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation history"""
        return self.conversation_history[-limit:]

    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
        self.retrieved_contexts = []
        self.turn_count = 0

    def clear_documents(self):
        """Clear uploaded documents"""
        self.uploaded_documents = []
        self._document_context_cache = ""
