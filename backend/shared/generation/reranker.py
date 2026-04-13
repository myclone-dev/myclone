"""
Document Reranker Module

This module provides reranking capabilities for retrieved documents to improve
relevance of search results. By default uses VoyageAI reranker but can be easily
extended to support other reranking services.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List

import httpx

from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


# --- Base Reranker Interface ---
class BaseReranker(ABC):
    """Abstract base class for document rerankers."""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents based on relevance to the query.

        Args:
            query: The search query
            documents: List of document dictionaries with 'content' field
            top_k: Number of top documents to return after reranking

        Returns:
            List of reranked documents with relevance scores
        """
        pass


# --- VoyageAI Reranker ---
class VoyageAIReranker(BaseReranker):
    """
    VoyageAI reranker implementation.
    Uses Voyage AI's reranking API to reorder documents by relevance.
    """

    def __init__(self, api_key: str = None, model: str = "rerank-2"):
        """
        Initialize VoyageAI reranker.

        Args:
            api_key: VoyageAI API key (defaults to settings.voyage_api_key)
            model: Reranking model to use (default: "rerank-2")
        """
        self.api_key = api_key or settings.voyage_api_key
        self.model = model
        self.api_url = os.getenv("VOYAGEAI_RERANK_URL", "https://api.voyageai.com/v1/rerank")

        if not self.api_key:
            logger.warning("VoyageAI API key not configured. Reranking will be disabled.")

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents using VoyageAI's reranking API.

        Args:
            query: The search query
            documents: List of document dictionaries with 'content' field
            top_k: Number of top documents to return after reranking

        Returns:
            List of reranked documents with updated relevance scores
        """
        if not self.api_key:
            logger.warning("VoyageAI API key not available. Returning original documents.")
            return documents[:top_k]

        if not documents:
            logger.info("No documents to rerank.")
            return []

        logger.info(f"🎯 Reranking {len(documents)} documents using VoyageAI (model: {self.model})")

        try:
            # Extract content strings for reranking
            document_texts = [doc.get("content", "") for doc in documents]

            # Make API request
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": query,
                        "documents": document_texts,
                        "model": self.model,
                        "top_k": top_k,
                    },
                )
                response.raise_for_status()
                result = response.json()

            # Parse reranking results
            reranked_results = result.get("data", [])

            # Map reranked results back to original documents
            reranked_docs = []
            for item in reranked_results:
                index = item.get("index")
                relevance_score = item.get("relevance_score", 0.0)

                if index is not None and index < len(documents):
                    doc = documents[index].copy()
                    # Update with reranking score
                    doc["rerank_score"] = relevance_score
                    doc["original_similarity"] = doc.get("similarity", 0.0)
                    doc["similarity"] = relevance_score  # Override with rerank score
                    reranked_docs.append(doc)

            logger.info(
                f"✅ Reranked {len(reranked_docs)} documents. "
                f"Top score: {reranked_docs[0].get('rerank_score', 0):.3f} "
                if reranked_docs
                else "✅ Reranking complete (no results)"
            )

            return reranked_docs

        except httpx.HTTPStatusError as e:
            capture_exception_with_context(
                e,
                extra={
                    "query": query,
                    "document_count": len(documents),
                    "top_k": top_k,
                    "status_code": e.response.status_code,
                    "response_text": e.response.text[:500],
                },
                tags={
                    "component": "reranker",
                    "operation": "rerank_documents",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            logger.error(f"VoyageAI API error (status {e.response.status_code}): {e.response.text}")
            logger.warning("Falling back to original document order.")
            return documents[:top_k]
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "query": query,
                    "document_count": len(documents),
                    "top_k": top_k,
                },
                tags={
                    "component": "reranker",
                    "operation": "rerank_documents",
                    "severity": "high",
                    "user_facing": "false",
                },
            )
            logger.error(f"Error during reranking: {e}", exc_info=True)
            logger.warning("Falling back to original document order.")
            return documents[:top_k]


# --- Reranker Factory ---
class RerankerFactory:
    """Factory for creating reranker instances based on configuration."""

    _rerankers = {
        "voyageai": VoyageAIReranker,
        # Add other rerankers here in the future:
        # "cohere": CohereReranker,
        # "colbert": ColBERTReranker,
    }

    @classmethod
    def create(cls, provider: str = "voyageai", **kwargs) -> BaseReranker:
        """
        Create a reranker instance.

        Args:
            provider: Reranker provider name (default: "voyageai")
            **kwargs: Additional arguments to pass to the reranker

        Returns:
            Reranker instance

        Raises:
            ValueError: If provider is not supported
        """
        provider = provider.lower()

        if provider not in cls._rerankers:
            available = ", ".join(cls._rerankers.keys())
            raise ValueError(
                f"Unknown reranker provider: {provider}. " f"Available providers: {available}"
            )

        reranker_class = cls._rerankers[provider]
        return reranker_class(**kwargs)

    @classmethod
    def register_reranker(cls, name: str, reranker_class: type):
        """
        Register a custom reranker.

        Args:
            name: Provider name
            reranker_class: Reranker class (must inherit from BaseReranker)
        """
        if not issubclass(reranker_class, BaseReranker):
            raise ValueError(
                f"Reranker class must inherit from BaseReranker, " f"got {reranker_class.__name__}"
            )
        cls._rerankers[name.lower()] = reranker_class
        logger.info(f"Registered reranker: {name}")
