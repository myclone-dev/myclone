"""
Singleton RAG System Manager
Ensures only one RAG system instance exists and manages persona index preloading
"""

import asyncio
import logging
from typing import Optional

from shared.rag.llama_rag import LlamaRAGSystem

logger = logging.getLogger(__name__)


class RAGManager:
    """Singleton manager for RAG system with prewarming support"""

    _instance: Optional["RAGManager"] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    async def initialize(self):
        """Initialize the RAG system once"""
        async with self._lock:
            if not self._initialized:
                logger.info("🚀 Initializing singleton RAG system...")
                self.rag_system = LlamaRAGSystem()
                self._initialized = True
                logger.info("✅ RAG system initialized")

    async def get_rag_system(self) -> LlamaRAGSystem:
        """Get the singleton RAG system instance"""
        if not self._initialized:
            await self.initialize()
        return self.rag_system

    def get_stats(self) -> dict:
        """Get statistics about the RAG system"""
        if not self._initialized:
            return {"status": "not_initialized"}

        return {
            "status": "initialized",
            "loaded_indexes": len(self.rag_system.persona_indexes),
        }

    async def refresh_persona_index(self, persona_id) -> bool:
        """
        Refresh the index for a specific persona by clearing cache and reloading from database.
        This ensures the latest embeddings are used for retrieval.

        Args:
            persona_id: UUID of the persona whose index should be refreshed

        Returns:
            True if refresh was successful, False otherwise
        """
        if not self._initialized:
            await self.initialize()

        return await self.rag_system.refresh_persona_index(persona_id)


# Global singleton instance
_rag_manager = RAGManager()


async def get_rag_manager() -> RAGManager:
    """Get the global RAG manager instance"""
    return _rag_manager


async def get_rag_system() -> LlamaRAGSystem:
    """Convenience function to get RAG system directly"""
    manager = await get_rag_manager()
    return await manager.get_rag_system()
