import asyncio
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urlparse
from uuid import UUID

import httpx
from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.schema import Document
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.database.models.database import Pattern, Persona, PersonaPrompt
from shared.generation.prompts import PromptTemplates
from shared.monitoring.sentry_utils import add_breadcrumb, capture_exception_with_context
from shared.utils.langfuse_utils import setup_langfuse_instrumentation

logger = logging.getLogger(__name__)


class LlamaRAGSystem:
    """Enhanced RAG system using LlamaIndex with persona-specific knowledge"""

    def __init__(self):
        # Initialize langfuse_client to None to prevent AttributeError
        self.langfuse_client = None

        # Get embedding configuration based on EMBEDDING_PROVIDER env var
        embedding_config = settings.get_embedding_config

        # Configure embedding model based on provider
        if embedding_config["provider"] == "voyage":
            from llama_index.embeddings.voyageai import VoyageEmbedding

            Settings.embed_model = VoyageEmbedding(
                model_name=embedding_config["model"],
                voyage_api_key=embedding_config["api_key"],
                output_dtype="float",  # Specifies float type
                output_dimension=embedding_config["dimension"],  # Specifies dimension 512
                timeout=60.0,
            )
        else:  # Default to OpenAI
            Settings.embed_model = OpenAIEmbedding(
                model=embedding_config["model"],
                api_key=embedding_config["api_key"],
                timeout=60.0,
                max_retries=3,
            )

        Settings.llm = OpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            timeout=30.0,  # Reduced timeout
            max_retries=1,  # Reduce retries to fail faster
            max_tokens=500,  # Limit response length
        )

        # Store embedding config for later use
        self.embedding_config = embedding_config

        # Log the embedding configuration at initialization
        logger.info(
            f"🚀 LlamaRAG Initialized - Embedding Provider: {embedding_config['provider']}, "
            f"Model: {embedding_config['model']}, "
            f"Dimension: {embedding_config['dimension']}, "
            f"Table: {embedding_config['table_name']}"
        )
        logger.info(f"🔍 Settings.embed_model type: {type(Settings.embed_model).__name__}")

        # Initialize PromptTemplates for consistent prompt generation
        self.prompts = PromptTemplates()

        # Initialize Langfuse instrumentation for LlamaIndex observability using OpenInference instrumentor
        self.langfuse_client = setup_langfuse_instrumentation(
            langfuse_public_key=settings.langfuse_public_key,
            langfuse_secret_key=settings.langfuse_secret_key,
            langfuse_host=settings.langfuse_host,
        )

        # Initialize PostgreSQL vector store using shared database config
        # Uses appropriate table based on embedding provider
        from shared.database.config import get_database_params

        db_params = get_database_params()
        self.vector_store = PGVectorStore.from_params(
            database=db_params["database"],
            host=db_params["host"],
            password=db_params["password"],
            port=db_params["port"],
            user=db_params["user"],
            table_name=embedding_config["table_name"],  # Uses config-based table name
            embed_dim=embedding_config["dimension"],  # Uses config-based dimension
            hybrid_search=True,
            text_search_config="english",
        )

        # Node parser for chunking (using configurable settings)
        self.node_parser = SentenceSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            paragraph_separator="\n\n",
            secondary_chunking_regex="[.!?]+",
        )

        # Storage context
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)

        self.index = VectorStoreIndex.from_vector_store(vector_store=self.vector_store)

        # Index for each persona (will be created dynamically)
        self.persona_indexes = {}
        self.persona_chat_engines = {}  # <<< FOR STORING STATEFUL CHAT ENGINES
        self.simple_chat_engines = {}
        self.persona_user_ids = {}  # Cache user_id for each persona to avoid repeated DB lookups

    async def ingest_persona_data(
        self,
        user_id: UUID,
        persona_id: UUID,
        content_sources: List[Dict[str, Any]],
        source_record_id: Optional[UUID] = None,
        force_rebuild: bool = False,
    ) -> Dict[str, Any]:
        """
        Ingest user data into LlamaIndex with enhanced chunking.

        Args:
            user_id: Owner of the embeddings (user who scraped the data)
            persona_id: Persona requesting ingestion (for logging/caching only)
            content_sources: List of content dicts with 'content', 'source', 'metadata' keys.
                            Each dict can include 'source_record_id' for per-source tracking.
            source_record_id: Optional single source_record_id to use for ALL content sources.
                            If not provided, each content_source must include 'source_record_id' in its dict.
            force_rebuild: Whether to force rebuild the index

        Note: Embeddings are user-owned and shared across all user's personas.
        """
        add_breadcrumb(
            f"RAG ingestion: {len(content_sources)} sources",
            "rag.ingest",
            data={"user_id": str(user_id), "persona_id": str(persona_id)},
        )

        try:
            persona_key = str(persona_id)
            logger.info(
                f"📊 Retriever Embedding Config - Provider: {self.embedding_config['provider']}, "
                f"Dimension: {self.embedding_config['dimension']}, "
                f"Table: {self.embedding_config['table_name']}"
            )

            # Check if we need to force rebuild (clear existing index)
            if force_rebuild and persona_key in self.persona_indexes:
                logger.info(
                    f"Force rebuild requested - clearing existing index for persona {persona_id}"
                )
                del self.persona_indexes[persona_key]
            # Prepare documents with rich metadata
            documents = []
            total_content_length = 0

            for source in content_sources:
                content = source.get("content", "")
                if not content.strip():
                    continue

                # Determine source_record_id for this specific source
                # Priority: 1) function parameter (if provided), 2) per-source field, 3) extract from metadata
                current_source_record_id = source_record_id
                if not current_source_record_id:
                    # Look for source_record_id in the source dict itself
                    current_source_record_id = source.get("source_record_id")

                    # If still not found, try to extract from metadata
                    if not current_source_record_id:
                        metadata = source.get("metadata", {})
                        # Try common ID fields
                        current_source_record_id = (
                            metadata.get("source_record_id")
                            or metadata.get("profile_id")
                            or metadata.get("record_id")
                            or metadata.get("id")
                        )

                if not current_source_record_id:
                    logger.warning(
                        f"No source_record_id found for source: {source.get('source')}, skipping"
                    )
                    continue

                # Create document with comprehensive metadata
                doc = Document(
                    text=content,
                    metadata={
                        "user_id": str(user_id),
                        "source_record_id": str(current_source_record_id),
                        "source": source.get("source", "unknown"),
                        "source_type": source.get("source_type", "text"),
                        "content_length": len(content),
                        **source.get("metadata", {}),
                    },
                )
                documents.append(doc)
                total_content_length += len(content)

            if not documents:
                logger.warning(f"No valid documents found for persona {persona_id}")
                return {"status": "no_content", "chunks_added": 0}

            # Parse into nodes with enhanced chunking
            nodes = self.node_parser.get_nodes_from_documents(documents)

            # Enhance nodes with metadata (no DB saving - that's handled by ORM after embedding)
            enhanced_nodes = []
            for i, node in enumerate(nodes):
                # Get source_record_id from node's metadata (already set correctly during document creation)
                node_source_record_id = node.metadata.get("source_record_id")

                node.metadata.update(
                    {
                        "chunk_id": f"{node_source_record_id}_{i}",  # Use node's source_record_id
                        "source_record_id": str(
                            node_source_record_id
                        ),  # Explicitly set to prevent corruption
                        "chunk_index": i,
                        "total_chunks": len(nodes),
                    }
                )

                # Infer source and content_type from metadata
                source = node.metadata.get("platform") or node.metadata.get("source", "unknown")
                content_type = node.metadata.get("content_type")
                if not content_type:
                    if "profile" in str(node.metadata.get("source", "")).lower():
                        content_type = "profile"
                    elif node.metadata.get("tweet_id"):
                        content_type = "tweet"
                    elif node.metadata.get("post_url"):
                        content_type = "post"
                    elif source == "website":
                        content_type = "page"
                    elif source == "youtube":
                        content_type = "transcript"
                    else:
                        content_type = "unknown"

                node.metadata["source"] = source
                node.metadata["source_type"] = content_type
                enhanced_nodes.append(node)

                if source == "unknown":
                    logger.warning(f"Unknown source detected for chunk {i}: {node.metadata}")
            # Create or update index
            if persona_key in self.persona_indexes:
                # Add nodes to existing index
                logger.info(
                    f"📝 Adding {len(enhanced_nodes)} nodes to existing index for persona {persona_id}"
                )

                def add_nodes_sync():
                    return self.persona_indexes[persona_key].insert_nodes(enhanced_nodes)

                await asyncio.get_event_loop().run_in_executor(None, add_nodes_sync)
                logger.info("✅ Successfully added nodes to existing index")
            else:
                # Create new index using run_in_executor to prevent blocking
                def create_index_sync():
                    return VectorStoreIndex(
                        enhanced_nodes,
                        storage_context=self.storage_context,
                        show_progress=True,
                    )

                logger.info(f"🔄 Creating new vector index for {len(enhanced_nodes)} nodes...")
                logger.info(
                    f"📊 Before index creation - persona_indexes keys: {list(self.persona_indexes.keys())}"
                )

                index = await asyncio.get_event_loop().run_in_executor(None, create_index_sync)

                logger.info(
                    f"🔧 Index object created, storing in persona_indexes['{persona_key}']..."
                )
                self.persona_indexes[persona_key] = index
                logger.info(
                    f"📊 After storing - persona_indexes keys: {list(self.persona_indexes.keys())}"
                )
                logger.info(f"📊 Index object type: {type(index)}")
                logger.info(f"✅ Vector index created successfully for persona {persona_key}")

            # Custom columns (user_id, source_record_id, source, source_type) are automatically
            # populated from metadata_ JSONB by a database trigger on INSERT.
            # See migration: 1e15f11578ab_make_custom_embedding_columns_nullable
            logger.info(
                f"Successfully ingested {len(enhanced_nodes)} chunks for user {user_id}, source {source_record_id}"
            )

            add_breadcrumb(
                f"RAG ingestion completed: {len(enhanced_nodes)} chunks",
                "rag.ingest.success",
            )

            return {
                "status": "success",
                "chunks_added": len(enhanced_nodes),
                "total_content_length": total_content_length,
                "sources_processed": len(content_sources),
                "source_record_id": str(source_record_id) if source_record_id else None,
            }

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "user_id": str(user_id),
                    "persona_id": str(persona_id),
                    "source_count": len(content_sources),
                    "source_record_id": str(source_record_id) if source_record_id else None,
                },
                tags={
                    "component": "rag",
                    "operation": "ingest",
                    "severity": "high",
                },
            )
            logger.error(f"Error ingesting persona data: {e}")
            raise

    async def ingest_pre_chunked_data(
        self,
        user_id: UUID,
        persona_id: UUID,
        content_sources: List[Dict[str, Any]],
        source_record_id: Optional[UUID] = None,
        force_rebuild: bool = False,
    ) -> Dict[str, Any]:
        """
        Ingest pre-chunked data into LlamaIndex WITHOUT re-chunking.

        This method is designed for content that has already been optimally chunked
        (e.g., PDF chunks with enrichment, transcript chunks with timestamps).

        Args:
            user_id: Owner of the embeddings (user who scraped the data)
            persona_id: Persona requesting ingestion (for logging/caching only)
            content_sources: List of content dicts with 'content', 'source', 'metadata' keys.
                            Each dict can include 'source_record_id' for per-source tracking.
            source_record_id: Optional single source_record_id to use for ALL content sources.
                            If not provided, each content_source must include 'source_record_id' in its dict.
            force_rebuild: Whether to force rebuild the index

        Note: This bypasses the SentenceSplitter node parser to preserve pre-chunked content.
        """
        from llama_index.core.schema import TextNode

        try:
            persona_key = str(persona_id)
            logger.info(
                f"📊 Retriever Embedding Config - Provider: {self.embedding_config['provider']}, "
                f"Dimension: {self.embedding_config['dimension']}, "
                f"Table: {self.embedding_config['table_name']}"
            )

            # Check if we need to force rebuild (clear existing index)
            if force_rebuild and persona_key in self.persona_indexes:
                logger.info(
                    f"Force rebuild requested - clearing existing index for persona {persona_id}"
                )
                del self.persona_indexes[persona_key]

            # Create nodes directly from content sources WITHOUT re-chunking
            enhanced_nodes = []
            total_content_length = 0

            for i, source in enumerate(content_sources):
                content = source.get("content", "")
                if not content.strip():
                    continue

                # Determine source_record_id for this specific source
                current_source_record_id = source_record_id
                if not current_source_record_id:
                    current_source_record_id = source.get("source_record_id")
                    if not current_source_record_id:
                        metadata = source.get("metadata", {})
                        current_source_record_id = (
                            metadata.get("source_record_id")
                            or metadata.get("profile_id")
                            or metadata.get("record_id")
                            or metadata.get("id")
                        )

                if not current_source_record_id:
                    logger.warning(
                        f"No source_record_id found for source: {source.get('source')}, skipping"
                    )
                    continue

                # Get source and source_type
                node_source = source.get("source", "unknown")
                node_source_type = source.get("source_type", "text")

                # Create metadata
                node_metadata = {
                    "user_id": str(user_id),
                    "source_record_id": str(current_source_record_id),
                    "source": node_source,
                    "source_type": node_source_type,
                    "content_length": len(content),
                    "chunk_id": f"{current_source_record_id}_{i}",
                    "chunk_index": i,
                    **source.get("metadata", {}),
                }

                # Create TextNode directly (bypassing document parsing)
                node = TextNode(
                    text=content,
                    metadata=node_metadata,
                )

                enhanced_nodes.append(node)
                total_content_length += len(content)

            if not enhanced_nodes:
                logger.warning(f"No valid nodes created for persona {persona_id}")
                return {"status": "no_content", "chunks_added": 0}

            # Update total_chunks metadata for all nodes
            for node in enhanced_nodes:
                node.metadata["total_chunks"] = len(enhanced_nodes)

            logger.info(f"📦 Created {len(enhanced_nodes)} pre-chunked nodes (no re-chunking)")

            # Create or update index
            if persona_key in self.persona_indexes:
                # Add nodes to existing index
                logger.info(
                    f"📝 Adding {len(enhanced_nodes)} pre-chunked nodes to existing index for persona {persona_id}"
                )

                def add_nodes_sync():
                    return self.persona_indexes[persona_key].insert_nodes(enhanced_nodes)

                await asyncio.get_event_loop().run_in_executor(None, add_nodes_sync)
                logger.info("✅ Successfully added pre-chunked nodes to existing index")
            else:
                # Create new index using run_in_executor to prevent blocking
                def create_index_sync():
                    return VectorStoreIndex(
                        enhanced_nodes,
                        storage_context=self.storage_context,
                        show_progress=True,
                    )

                logger.info(
                    f"🔄 Creating new vector index for {len(enhanced_nodes)} pre-chunked nodes..."
                )

                index = await asyncio.get_event_loop().run_in_executor(None, create_index_sync)

                self.persona_indexes[persona_key] = index
                logger.info(f"�� Vector index created successfully for persona {persona_key}")

            # NOTE: Custom column population is now handled by the ingestion pipeline
            # using VoyageLiteEmbedding model with Voyage AI embeddings

            logger.info(
                f"Successfully ingested {len(enhanced_nodes)} pre-chunked chunks for user {user_id}, source {source_record_id}"
            )

            return {
                "status": "success",
                "chunks_added": len(enhanced_nodes),
                "total_content_length": total_content_length,
                "sources_processed": len(content_sources),
                "source_record_id": str(source_record_id) if source_record_id else None,
            }

        except Exception as e:
            logger.error(f"Error ingesting pre-chunked persona data: {e}")
            raise

    async def retrieve_context(
        self,
        persona_id: UUID,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = 0.3,
        include_patterns: bool = True,
    ) -> Dict[str, Any]:
        """Retrieve relevant context using LlamaIndex with pattern integration"""

        trace_span = None
        if self.langfuse_client:
            try:
                trace_span = self.langfuse_client.start_span(
                    name="llama_rag_retrieve_context",
                    input={
                        "persona_id": str(persona_id),
                        "query": query,
                        "top_k": top_k,
                        "similarity_threshold": similarity_threshold,
                    },
                    metadata={
                        "user_id": str(persona_id),
                        "tags": ["retrieval", "rag", "llamaindex", f"persona:{persona_id}"],
                    },
                )
            except Exception as e:
                logger.warning(f"⚠️ Failed to create Langfuse span: {e}")

        try:
            import time

            start_time = time.time()

            persona_key = str(persona_id)

            logger.info(
                f"📊 Retriever Embedding Config - Provider: {self.embedding_config['provider']}, "
                f"Dimension: {self.embedding_config['dimension']}, "
                f"Table: {self.embedding_config['table_name']}"
            )

            # Check if persona index exists, try to load it if not
            if persona_key not in self.persona_indexes:
                logger.info(
                    f"Index not found for persona {persona_id}, attempting to load from database"
                )
                await self._ensure_persona_index(persona_id)

                # If still no index after loading attempt, return empty result
                if persona_key not in self.persona_indexes:
                    logger.warning(f"No index found for persona {persona_id} after loading attempt")
                    return {"chunks": [], "patterns": {}, "total_retrieved": 0}

            # Step 1: Get source_record_ids for this persona
            source_record_ids = await self.get_persona_source_record_ids(persona_id)
            if not source_record_ids:
                logger.warning(f"No source_record_ids found for persona {persona_id}")
                return {"chunks": [], "patterns": {}, "total_retrieved": 0}

            source_record_ids_str = [str(sid) for sid in source_record_ids]

            # Step 2: Filter by source_record_id instead of persona_id
            from llama_index.core.vector_stores.types import (
                MetadataFilter,
                MetadataFilters,
            )

            metadata_filters = MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="source_record_id", value=source_record_ids_str, operator="in"
                    )
                ]
            )

            logger.info(
                f"🔒 Applying source filter: {len(source_record_ids)} source_record_ids for persona {persona_id}"
            )

            # Log the embedding model being used for query
            logger.info(
                f"🔍 Retrieve Query Embedding Model: {type(Settings.embed_model).__name__} - "
                f"Model: {getattr(Settings.embed_model, 'model_name', getattr(Settings.embed_model, 'model', 'unknown'))}"
            )

            retriever = VectorIndexRetriever(
                index=self.persona_indexes[persona_key],
                similarity_top_k=top_k,
                vector_store_query_mode="hybrid",  # Use hybrid search
                filters=metadata_filters,  # Only return this persona's data
            )

            # Retrieve nodes
            retrieved_nodes = await asyncio.to_thread(retriever.retrieve, query)

            # Smart filtering with fallback strategy
            # First try with the requested threshold
            filtered_nodes = [
                node for node in retrieved_nodes if node.score >= similarity_threshold
            ]

            # If no results, progressively lower threshold with warnings
            if not filtered_nodes and retrieved_nodes:
                logger.warning(
                    f"No chunks found with similarity >= {similarity_threshold}, trying lower thresholds"
                )

                # Try with 0.2 threshold
                filtered_nodes = [node for node in retrieved_nodes if node.score >= 0.2]
                if filtered_nodes:
                    logger.warning(f"Found {len(filtered_nodes)} chunks with similarity >= 0.2")

                # Last resort: take top 2 chunks regardless of score, but warn
                if not filtered_nodes and len(retrieved_nodes) > 0:
                    filtered_nodes = retrieved_nodes[:2]
                    logger.warning(
                        f"Using top 2 chunks regardless of similarity score: {[n.score for n in filtered_nodes]}"
                    )

            # Convert to our format
            chunks = []
            for node in filtered_nodes:
                chunk_data = {
                    "content": node.text,
                    "source": node.metadata.get("source", "unknown"),
                    "metadata": node.metadata,
                    "similarity": node.score,
                    "chunk_index": node.metadata.get("chunk_index", 0),
                }
                chunks.append(chunk_data)

            result = {
                "chunks": chunks,
                "total_retrieved": len(chunks),
                "query": query,
                "similarity_info": {
                    "threshold_used": similarity_threshold,
                    "original_results": len(retrieved_nodes),
                    "filtered_results": len(filtered_nodes),
                    "score_range": (
                        [
                            min([n.score for n in filtered_nodes]),
                            max([n.score for n in filtered_nodes]),
                        ]
                        if filtered_nodes
                        else [0, 0]
                    ),
                },
            }

            # Include communication patterns if requested
            if include_patterns:
                patterns = await self._get_persona_patterns(persona_id)
                result["patterns"] = patterns

            logger.info(f"Retrieved {len(chunks)} relevant chunks for query: {query[:50]}...")

            retrieval_time = time.time() - start_time

            # Track retrieval results with Langfuse
            if trace_span:
                try:
                    trace_span.update(
                        output={
                            "chunks_count": len(chunks),
                            "similarity_info": result["similarity_info"],
                        },
                        metadata={"retrieval_time_seconds": round(retrieval_time, 3)},
                    )
                finally:
                    trace_span.end()

            return result

        except Exception as e:
            logger.error(f"Error retrieving context: {e}")

            # Track error with Langfuse
            if trace_span:
                try:
                    trace_span.update(
                        metadata={
                            "error_type": type(e).__name__,
                            "error_message": str(e)[:200],
                        }
                    )
                finally:
                    trace_span.end()

            raise

    async def generate_response_stream(
        self,
        persona_id: UUID,
        query: str,
        context: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        return_citations: bool = False,
        chat_trace: bool = False,
    ) -> AsyncGenerator[Any, None]:
        """Generate streaming persona-specific response using OpenAI directly with RAG context"""

        logger.info(
            f"🎯 STREAMING LLAMARAG START - persona_id: {persona_id}, query: '{query[:50]}...'"
        )

        persona_key = str(persona_id)
        session_id = context.get("session_id")

        try:
            logger.info("🚀 Starting streaming response generation")
            logger.info(
                f"📊 Embedding Config - Provider: {self.embedding_config['provider']}, "
                f"Dimension: {self.embedding_config['dimension']}, "
                f"Table: {self.embedding_config['table_name']}"
            )

            # Ensure persona index exists
            if persona_key not in self.persona_indexes:
                logger.info(f"Index not found for persona {persona_id}, loading from database")
                await self._ensure_persona_index(persona_id)
                if persona_key not in self.persona_indexes:
                    raise ValueError(f"No index found for persona {persona_id}")

            # Use the persona-specific index
            current_index = self.persona_indexes[persona_key]
            logger.info(f"✅ Using persona index for {persona_id}")
            # Create Langfuse callback handler for this request
            from contextlib import nullcontext

            # current_date = datetime.now().strftime("%Y-%m-%d")
            langfuse_context = nullcontext()
            system_prompt = None

            if self.langfuse_client and chat_trace:
                try:
                    # Create session name following the pattern: llama_stream_{persona_id}_{session_id}
                    session_name = (
                        f"llama_stream_{persona_id}_{session_id if session_id else 'unknown'}"
                    )

                    # Use start_as_current_span which returns a context manager
                    langfuse_context = self.langfuse_client.start_as_current_span(
                        name=session_name,  # Session-consistent naming
                        input={
                            "query": query,
                            "persona_id": str(persona_id),
                            "session_id": session_id,
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        },
                        metadata={
                            "user_id": str(persona_id),  # For user-based filtering
                            "session_id": (
                                session_id if session_id else "unknown"
                            ),  # For session-based filtering
                            "session_name": session_name,  # For session grouping
                            "tags": [
                                "llama_rag",
                                "stream",
                                f"persona:{persona_id}",
                                f"session:{session_id}" if session_id else "session:unknown",
                            ],
                        },
                    )
                    # The context manager will yield the span when entered
                except Exception as e:
                    logger.warning(f"⚠️ Failed to create Langfuse span: {e}")
                    langfuse_context = nullcontext()

            with langfuse_context as langfuse_span:
                # Build chat engine if not cached
                if persona_key not in self.persona_chat_engines:
                    # Get persona info
                    from shared.database.models.database import async_session_maker

                    async with async_session_maker() as session:
                        persona = await self._get_persona_info(session, persona_id)
                        if persona:
                            logger.info(f"✅ Got persona info: {persona.name}")
                            persona_prompt = await self._get_persona_prompts(session, persona_id)

                    if not persona:
                        logger.error(f"❌ Persona {persona_id} not found in database")
                        yield "I apologize, but the persona you're trying to access doesn't exist. Please check the persona ID and try again."
                        return

                    # Get role and company with priority: Persona > User > LinkedIn
                    role = persona.role  # Try Persona table first
                    if not role and persona.user:
                        role = persona.user.role  # Try User table if Persona.role is null

                    company = None
                    if persona.user:
                        company = persona.user.company  # Get company from User table

                    # LinkedIn repository removed; role/company come from user/persona fields only
                    description = None

                    persona_dict = {
                        "name": persona.name,
                        "role": role or "Expert",  # Fallback if no current job
                        "company": company or "Independent",  # Fallback if no current job
                        "description": description if description else persona.description,
                    }

                    # Attach persona-specific patterns
                    context["patterns"] = await self._get_persona_patterns(persona_id)
                    if persona_prompt is not None:
                        logger.info(
                            f"✅ Got persona prompt for {persona.name}, Dynamic: {persona_prompt.is_dynamic}"
                        )
                        system_prompt = self.prompts.build_system_prompt_dynamic(
                            persona_prompt, persona_dict
                        )
                    else:
                        system_prompt = self.prompts.build_system_prompt_alt(
                            persona_dict, context["patterns"]
                        )

                    # Get source_record_ids for filtering
                    source_record_ids = await self.get_persona_source_record_ids(persona_id)
                    if not source_record_ids:
                        logger.warning(f"No source_record_ids found for persona {persona_id}")
                        yield "I apologize, but I don't have access to any knowledge sources yet. Please add some data sources to this persona first."
                        return

                    source_record_ids_str = [str(sid) for sid in source_record_ids]

                    from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters

                    metadata_filters = MetadataFilters(
                        filters=[
                            MetadataFilter(
                                key="source_record_id", value=source_record_ids_str, operator="in"
                            )
                        ]
                    )

                    logger.info(
                        f"🔒 Streaming: Applying source filter for {len(source_record_ids)} source_record_ids"
                    )

                    # Log the embedding model being used for query
                    logger.info(
                        f"🔍 Streaming Query Embedding Model: {type(Settings.embed_model).__name__} - "
                        f"Model: {getattr(Settings.embed_model, 'model_name', getattr(Settings.embed_model, 'model', 'unknown'))}"
                    )

                    chat_engine = CondensePlusContextChatEngine.from_defaults(
                        retriever=current_index.as_retriever(
                            filters=metadata_filters,
                            similarity_top_k=5,
                            vector_store_query_mode="hybrid",  # Use hybrid search
                        ),
                        llm=Settings.llm,
                        memory=ChatMemoryBuffer.from_defaults(token_limit=16384),
                        system_prompt=system_prompt,
                        context_prompt=self.prompts.get_context_prompt(),
                        verbose=True,
                    )
                    self.persona_chat_engines[persona_key] = chat_engine
                    # Store user_id for future lookups (special URL handling, etc.)
                    self.persona_user_ids[persona_key] = persona.user_id
                else:
                    # Chat engine retrieved from cache
                    chat_engine = self.persona_chat_engines[persona_key]

                logger.info(f"✅ Persona chat engine ready for {persona_id}")

                # --- URL content extraction ---
                # If the query contains URLs, fetch their content and append to the query
                user_id = self.persona_user_ids.get(persona_key)

                def _is_safe_url(url: str) -> bool:
                    """Validate URL to prevent SSRF attacks"""
                    try:
                        parsed = urlparse(url)
                        blocked_hosts = ["localhost", "127.0.0.1", "169.254.169.254", "0.0.0.0"]

                        if parsed.scheme not in ["http", "https"]:
                            logger.warning(f"⚠️ Blocked URL with invalid scheme: {url}")
                            return False
                        if not parsed.hostname:
                            logger.warning(f"⚠️ Blocked URL with no hostname: {url}")
                            return False
                        if parsed.hostname in blocked_hosts:
                            logger.warning(f"⚠️ Blocked URL targeting internal host: {url}")
                            return False
                        if (
                            parsed.hostname.startswith("10.")
                            or parsed.hostname.startswith("192.168.")
                            or parsed.hostname.startswith("172.16.")
                            or parsed.hostname.startswith("172.17.")
                            or parsed.hostname.startswith("172.18.")
                            or parsed.hostname.startswith("172.19.")
                            or parsed.hostname.startswith("172.2")
                            or parsed.hostname.startswith("172.30.")
                            or parsed.hostname.startswith("172.31.")
                        ):
                            logger.warning(f"⚠️ Blocked URL targeting private IP range: {url}")
                            return False
                        return True
                    except Exception as e:
                        logger.warning(f"⚠️ URL validation error for {url}: {e}")
                        return False

                url_pattern = r"https?://[^\s]+"
                urls = re.findall(url_pattern, query)

                if urls:
                    logger.info(f"🔗 Found {len(urls)} URL(s) in query")
                    url_contents = []
                    MAX_TOTAL_URL_CONTENT = 100_000  # 100KB total limit
                    total_content_size = 0

                    # Initialize Firecrawl provider if API key is available
                    firecrawl_provider = None
                    if settings.firecrawl_api_key:
                        from shared.services.firecrawl_service import FirecrawlService

                        firecrawl_provider = FirecrawlService(
                            api_key=settings.firecrawl_api_key,
                            base_url=settings.firecrawl_base_url,
                            timeout_sec=30,
                        )
                        logger.info(
                            "Using Firecrawl for URL content fetching (anti-bot protection)"
                        )
                    else:
                        logger.warning(
                            "⚠️ Firecrawl API key not configured, using basic httpx (may be blocked by some sites)"
                        )

                    for url in urls:
                        try:
                            # SSRF protection: Validate URL before fetching
                            if not _is_safe_url(url):
                                add_breadcrumb(
                                    category="security",
                                    message=f"Blocked unsafe URL: {url}",
                                    level="warning",
                                    data={"url": url, "user_id": str(user_id)},
                                )
                                continue

                            # Check total content size limit
                            if total_content_size >= MAX_TOTAL_URL_CONTENT:
                                logger.warning(
                                    f"⚠️ Total URL content limit reached ({MAX_TOTAL_URL_CONTENT} bytes), skipping remaining URLs"
                                )
                                break

                            content_text = None

                            # Try Firecrawl first (handles anti-bot protection, JavaScript rendering)
                            if firecrawl_provider:
                                try:
                                    logger.info(f"🔥 Fetching {url} via Firecrawl...")
                                    page_result = await firecrawl_provider.scrape_page(url)
                                    content_text = (
                                        page_result.markdown or page_result.html or ""
                                    )
                                    content_text = content_text[:50000]  # Limit to 50KB per URL
                                    logger.info(
                                        f"✅ Firecrawl successfully fetched {len(content_text)} chars from {url}"
                                    )
                                except Exception as fc_error:
                                    logger.warning(
                                        f"⚠️ Firecrawl failed for {url}: {fc_error}, falling back to httpx"
                                    )
                                    content_text = None

                            # Fallback to basic httpx if Firecrawl not available or failed
                            if content_text is None:
                                async with httpx.AsyncClient(
                                    timeout=10.0,
                                    follow_redirects=True,
                                    headers={
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                                        "Accept-Language": "en-US,en;q=0.9",
                                        "Accept-Encoding": "gzip, deflate, br",
                                        "DNT": "1",
                                        "Connection": "keep-alive",
                                        "Upgrade-Insecure-Requests": "1",
                                    },
                                ) as client:
                                    head_response = await client.head(url)
                                    content_length = head_response.headers.get("content-length")

                                    if content_length and int(content_length) > 300 * 1024:
                                        logger.warning(f"⚠️ URL {url} exceeds 300KB, skipping")
                                        continue

                                    response = await client.get(url)

                                    if len(response.content) > 300 * 1024:
                                        logger.warning(
                                            f"⚠️ URL {url} content exceeds 300KB, skipping"
                                        )
                                        continue

                                    content_text = response.text[:50000]

                            if not content_text:
                                logger.warning(f"⚠️ No content retrieved from {url}")
                                continue

                            if total_content_size + len(content_text) > MAX_TOTAL_URL_CONTENT:
                                remaining = MAX_TOTAL_URL_CONTENT - total_content_size
                                content_text = content_text[:remaining]
                                logger.warning(
                                    f"⚠️ Truncating content from {url} to fit within total limit"
                                )

                            url_contents.append(
                                f"\n\n--- Content from {url} ---\n{content_text}\n--- End of URL content ---\n"
                            )
                            total_content_size += len(content_text)
                            logger.info(
                                f"✅ Fetched {len(content_text)} chars from {url} (total: {total_content_size} bytes)"
                            )

                        except Exception as e:
                            capture_exception_with_context(
                                e,
                                extra={
                                    "url": url,
                                    "user_id": str(user_id) if user_id else "unknown",
                                    "persona_id": str(persona_id),
                                    "total_urls": len(urls),
                                    "fetched_count": len(url_contents),
                                },
                                tags={
                                    "component": "rag",
                                    "operation": "fetch_url_content",
                                    "severity": "medium",
                                    "user_facing": "false",
                                },
                            )
                            logger.warning(f"⚠️ Failed to fetch {url}: {e}")

                    if url_contents:
                        query = query + "".join(url_contents)
                        logger.info(
                            f"📎 Appended {len(url_contents)} URL content(s) to query (total size: {total_content_size} bytes)"
                        )

                # --- Streaming starts here ---
                import time

                stream_start = time.time()
                first_token_time = None
                token_count = 0
                full_response = ""  # Collect full response for tracking

                logger.info("🔄 Initializing streaming chat call")

                streams = await asyncio.wait_for(chat_engine.astream_chat(query), timeout=30.0)
                retrieved_context: List[Dict[str, Any]] = []

                # DEBUG: Log retrieved nodes BEFORE streaming starts
                source_nodes = []
                if hasattr(streams, "source_nodes"):
                    source_nodes = getattr(streams, "source_nodes", []) or []
                    logger.info(f"📚 Retrieval complete: {len(source_nodes)} nodes retrieved")
                else:
                    logger.warning(
                        "⚠️ streams object has no source_nodes attribute - cannot verify retrieval"
                    )

                # --- Handle case when no context retrieved ---
                # If no nodes retrieved, use fallback direct chat without RAG context
                if len(source_nodes) == 0:
                    logger.info(
                        "🔄 No context retrieved - using direct chat mode with system prompt"
                    )
                    # Get system_prompt from cached engine for fallback mode
                    # CondensePlusContextChatEngine stores system_prompt in _system_prompt attribute
                    if hasattr(chat_engine, "_system_prompt"):
                        system_prompt = chat_engine._system_prompt
                    else:
                        # Fallback: rebuild system prompt if not accessible from engine
                        from shared.database.models.database import async_session_maker

                        async with async_session_maker() as session:
                            persona = await self._get_persona_info(session, persona_id)
                            persona_prompt = (
                                await self._get_persona_prompts(session, persona_id)
                                if persona
                                else None
                            )

                        if persona:
                            role = persona.role or (persona.user.role if persona.user else None)
                            company = persona.user.company if persona.user else None
                            # LinkedIn repository removed; description comes from persona fields
                            description = None

                            persona_dict = {
                                "name": persona.name,
                                "role": role or "Expert",
                                "company": company or "Independent",
                                "description": description or persona.description,
                            }
                            context["patterns"] = await self._get_persona_patterns(persona_id)

                            if persona_prompt:
                                system_prompt = self.prompts.build_system_prompt_dynamic(
                                    persona_prompt, persona_dict
                                )
                            else:
                                system_prompt = self.prompts.build_system_prompt_alt(
                                    persona_dict, context["patterns"]
                                )
                        else:
                            system_prompt = "You are a helpful AI assistant."

                    # Build messages for direct LLM call
                    from llama_index.core.llms import ChatMessage, MessageRole

                    messages = [
                        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                    ]

                    # Add chat history if available
                    if hasattr(chat_engine, "_memory") and chat_engine._memory:
                        chat_history = chat_engine._memory.get()
                        for msg in chat_history:
                            messages.append(msg)

                    # Add current query
                    messages.append(ChatMessage(role=MessageRole.USER, content=query))

                    logger.info(f"💬 Calling LLM directly with {len(messages)} messages")

                    # Stream response directly from LLM
                    # stream_chat returns a generator directly
                    llm_stream = Settings.llm.stream_chat(messages)

                    # Iterate directly over the generator in async context
                    for chunk in llm_stream:
                        # Extract delta/token from the chunk
                        if hasattr(chunk, "delta"):
                            token = chunk.delta
                        elif hasattr(chunk, "message"):
                            token = (
                                chunk.message.content
                                if hasattr(chunk.message, "content")
                                else str(chunk.message)
                            )
                        else:
                            token = str(chunk) if chunk else None

                        if token is not None and token:
                            if first_token_time is None:
                                first_token_time = time.time() - stream_start
                                logger.info(f"⚡ First token received in {first_token_time:.3f}s")

                            token_count += 1
                            full_response += token  # Collect for tracking
                            yield token

                        # Yield control to event loop
                        await asyncio.sleep(0)
                else:
                    # Normal flow with retrieved context
                    # --- Iterate over stream ---
                    async for token in streams.async_response_gen():
                        if token is not None:
                            if first_token_time is None:
                                first_token_time = time.time() - stream_start
                                logger.info(f"⚡ First token received in {first_token_time:.3f}s")

                            token_count += 1
                            full_response += token  # Collect for tracking
                            yield token

                total_time = time.time() - stream_start
                logger.info(f"✅ Streaming complete: {token_count} tokens in {total_time:.3f}s")

                # DEBUG: Warn if response is empty or very short
                if len(full_response.strip()) == 0:
                    logger.error("❌ EMPTY RESPONSE GENERATED!")
                    logger.error("This usually means retrieval failed or LLM returned nothing")
                    logger.error(
                        f"Token count: {token_count}, Response length: {len(full_response)}"
                    )
                elif len(full_response.strip()) < 10:
                    logger.warning(f"⚠️ Very short response generated: '{full_response}'")

                # Collect source nodes for langfuse tracking and optional return
                if hasattr(streams, "source_nodes"):
                    source_nodes = getattr(streams, "source_nodes", []) or []
                    logger.info(f"📊 Processing {len(source_nodes)} retrieved nodes for context")

                    for node_with_score in source_nodes:
                        node = node_with_score.node
                        retrieved_context.append(
                            {
                                "content": node.get_content(),
                                "metadata": node.metadata,
                                "score": node_with_score.score,
                            }
                        )

                    # DEBUG: Check if similarity postprocessor filtered everything out
                    if len(retrieved_context) == 0 and len(source_nodes) > 0:
                        logger.warning(
                            "⚠️ All retrieved nodes were filtered out by similarity postprocessor"
                        )
                        logger.warning("Consider lowering similarity_cutoff (currently 0.45)")

                    logger.info(f"📚 Final context: {len(retrieved_context)} nodes passed filters")

                if langfuse_span:
                    try:
                        langfuse_span.update(
                            output={
                                "full_response": full_response,
                                "retrieved_nodes": retrieved_context,
                            },
                            metadata={
                                "token_count": token_count,
                                "total_time_seconds": total_time,
                                "first_token_time_seconds": first_token_time or 0,
                                "context_count": len(retrieved_context),
                            },
                        )
                        # Note: span.end() is called automatically by context manager
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to update Langfuse span: {e}")

                # Yield sources if requested (after all content tokens)
                MINIMUM_SIMILARITY = 0.3  # Or whatever threshold you prefer
                # Assuming 'source' in metadata corresponds to 'persona_profile'
                EXCLUDED_SOURCES = ["persona_profile"]
                if return_citations and retrieved_context:
                    sources = []
                    for ctx in retrieved_context:
                        metadata = ctx.get("metadata", {})
                        # This 'source' key in metadata should match what you ingested
                        source_type = metadata.get("source", "unknown")
                        similarity = ctx.get("score")
                        # Extract source_url from various metadata fields
                        # Your filtering criteria
                        if (
                            source_type not in EXCLUDED_SOURCES
                            and similarity >= MINIMUM_SIMILARITY
                            and len(ctx["content"]) > 50
                        ):
                            source_url = (
                                metadata.get("post_url")  # LinkedIn posts
                                or metadata.get("tweet_url")  # Twitter tweets
                                or metadata.get("linkedin_url")  # LinkedIn profile
                                or metadata.get("url")  # Generic URL field
                                or metadata.get("website_url")  # Website pages
                                or metadata.get("source_url")
                                or ""
                            )

                            # Format source with flattened structure for frontend
                            source = {
                                "content": ctx["content"],
                                "source_url": source_url,
                                "source": metadata.get("source", ""),
                                "title": metadata.get("title", ""),
                                "similarity": ctx.get("score"),
                                "type": source_type,
                                "metadata": metadata,
                            }
                            sources.append(source)
                            # Limit to 3 high-quality sources
                            if len(sources) >= 3:
                                break

                    logger.info(f"📚 Yielding {len(sources)} source citations")
                    yield {"type": "sources", "sources": sources}

            # Flush after context manager exits
            if self.langfuse_client and chat_trace:
                try:
                    self.langfuse_client.flush()
                    logger.info("🔍 Langfuse: Flushed streaming trace to server")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to flush Langfuse data: {e}")

        except Exception as e:
            logger.error(f"❌ Streaming generation error: {type(e).__name__}: {e}")
            logger.error(
                f"❌ Error occurred at step: {'database' if 'session' in str(e).lower() else 'openai' if 'openai' in str(e).lower() else 'unknown'}"
            )

            # Ensure trace is flushed even on error (span auto-ends via context manager)
            if self.langfuse_client:
                try:
                    self.langfuse_client.flush()
                except Exception as flush_error:
                    logger.warning(f"⚠️ Failed to flush Langfuse on error: {flush_error}")

    async def generate_response(
        self,
        persona_id: UUID,
        query: str,
        context: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        return_citations: bool = False,
    ) -> Any:
        """Generate persona-specific response using LlamaIndex query engine"""

        trace_span = None
        session_id = context.get("session_id")
        if self.langfuse_client:
            try:
                # Create session name following the pattern: llama_stream_{persona_id}_{session_id}
                session_name = (
                    f"llama_stream_{persona_id}_{session_id if session_id else 'unknown'}"
                )

                trace_span = self.langfuse_client.start_span(
                    name=session_name,  # Session-consistent naming
                    input={
                        "persona_id": str(persona_id),
                        "query": query,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "return_citations": return_citations,
                        "session_id": session_id,
                    },
                    metadata={
                        "user_id": str(persona_id),
                        "session_id": session_id if session_id else "unknown",
                        "session_name": session_name,  # For session grouping
                        "tags": [
                            "chat",
                            "rag",
                            "llamaindex",
                            f"persona:{persona_id}",
                            f"session:{session_id}" if session_id else "session:unknown",
                        ],
                    },
                )
            except Exception as e:
                logger.warning(f"⚠️ Failed to create Langfuse span: {e}")

        try:
            import time

            start_time = time.time()

            persona_key = str(persona_id)

            logger.info(
                f"📊 Embedding Config - Provider: {self.embedding_config['provider']}, "
                f"Dimension: {self.embedding_config['dimension']}, "
                f"Table: {self.embedding_config['table_name']}"
            )

            # Ensure persona index exists
            if persona_key not in self.persona_indexes:
                logger.info(
                    f"Index not found for persona {persona_id}, attempting to load from database"
                )
                self.persona_indexes[persona_key] = self.index

                if persona_key not in self.persona_indexes:
                    raise ValueError(
                        f"No index found for persona {persona_id} after loading attempt"
                    )

            # Get persona information using proper session acquisition
            logger.info(f"🔄 Getting persona info for non-streaming response: {persona_id}")
            from shared.database.models.database import async_session_maker

            async with async_session_maker() as session:
                persona = await self._get_persona_info(session, persona_id)

                if not persona:
                    raise ValueError(f"Persona {persona_id} not found")

                # Get role and company with priority: Persona > User > LinkedIn
                role = persona.role  # Try Persona table first
                if not role and persona.user:
                    role = persona.user.role  # Try User table if Persona.role is null

                company = None
                if persona.user:
                    company = persona.user.company  # Get company from User table

                # LinkedIn repository removed; role/company come from user/persona fields only
                description = None

            logger.info(f"✅ Got persona info: {persona.name if persona else 'None'}")

            # Build persona dict and system prompt (needed for fallback even if engine is cached)
            persona_dict = {
                "name": persona.name,
                "role": role or "Expert",  # Fallback if no current job
                "company": company or "Independent",  # Fallback if no current job
                "description": description if description else persona.description,
            }

            # Get patterns if not provided
            context["patterns"] = await self._get_persona_patterns(persona_id)

            # Build prompts using PromptTemplates
            system_prompt = self.prompts.build_system_prompt_alt(persona_dict, context["patterns"])

            if persona_key in self.persona_chat_engines:
                chat_engine = self.persona_chat_engines[persona_key]
            else:
                # Get source_record_ids for filtering
                source_record_ids = await self.get_persona_source_record_ids(persona_id)
                if not source_record_ids:
                    logger.warning(f"No source_record_ids found for persona {persona_id}")
                    return "I apologize, but I don't have access to any knowledge sources yet. Please add some data sources to this persona first."

                source_record_ids_str = [str(sid) for sid in source_record_ids]

                # Configure query engine with persona-specific prompt and filtering
                from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters

                # Create metadata filter using source_record_ids
                metadata_filters = MetadataFilters(
                    filters=[
                        MetadataFilter(
                            key="source_record_id", value=source_record_ids_str, operator="in"
                        )
                    ]
                )

                logger.info(
                    f"🔒 Non-streaming: Applying source filter for {len(source_record_ids)} source_record_ids"
                )

                # Log the embedding model being used for query
                logger.info(
                    f"🔍 Non-streaming Query Embedding Model: {type(Settings.embed_model).__name__} - "
                    f"Model: {getattr(Settings.embed_model, 'model_name', getattr(Settings.embed_model, 'model', 'unknown'))}"
                )

                chat_engine = CondensePlusContextChatEngine.from_defaults(
                    retriever=self.index.as_retriever(filters=metadata_filters, similarity_top_k=5),
                    llm=Settings.llm,
                    memory=ChatMemoryBuffer.from_defaults(token_limit=16384),
                    system_prompt=system_prompt,
                    node_postprocessors=[SimilarityPostprocessor(similarity_cutoff=0.45)],
                    verbose=True,  # Set to True to see the internal queries
                )
                self.persona_chat_engines[persona_key] = chat_engine

            logger.info(f"🚀 Starting LlamaIndex query for persona {persona_id}")

            # Generate response with timeout
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(chat_engine.chat, query),
                    timeout=10.0,  # 10 second timeout
                )
                logger.info("✅ LlamaIndex query completed successfully")
            except asyncio.TimeoutError:
                logger.error(f"⏱️ Query timeout for persona {persona_id} after 10 seconds")
                return "I apologize, but I'm having trouble processing your request right now. Please try again."
            except Exception as e:
                logger.error(f"❌ Query failed with error: {e}")
                raise

            response_text = str(response)

            # Handle case when response is empty due to no context
            if not response_text or len(response_text.strip()) == 0:
                logger.warning("⚠️ Empty response detected - checking for retrieved nodes")

                # Check if no nodes were retrieved
                has_nodes = (
                    hasattr(response, "source_nodes")
                    and response.source_nodes
                    and len(response.source_nodes) > 0
                )

                if not has_nodes:
                    logger.info(
                        "🔄 No context retrieved and empty response - using direct chat mode"
                    )

                    # Build messages for direct LLM call
                    from llama_index.core.llms import ChatMessage, MessageRole

                    messages = [
                        ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
                    ]

                    # Add chat history if available
                    if hasattr(chat_engine, "_memory") and chat_engine._memory:
                        chat_history = chat_engine._memory.get()
                        for msg in chat_history:
                            messages.append(msg)

                    # Add current query
                    messages.append(ChatMessage(role=MessageRole.USER, content=query))

                    logger.info(f"💬 Calling LLM directly with {len(messages)} messages")

                    # Get response directly from LLM
                    direct_response = await asyncio.to_thread(Settings.llm.chat, messages)
                    response_text = str(direct_response.message.content)
                    logger.info(f"✅ Direct LLM response generated: {len(response_text)} chars")

            total_time = time.time() - start_time

            # Citations handling (same as before)
            citations = None
            if hasattr(response, "source_nodes") and response.source_nodes:
                citations = "\n\nSources:\n"
                for i, node_with_score in enumerate(response.source_nodes, 1):
                    node = node_with_score.node
                    score = node_with_score.score
                    snippet = node.get_content()[:150].replace("\n", " ")
                    metadata = node.metadata
                    logger.info(f"  -> Source Node (Score: {score:.4f}): {node.text[:120]}...")
                    citations += f"[{i}] {metadata.get('source', 'unknown')} | {snippet}...\n"

                logger.info(f"citations_found: {citations}")

            # Track the response with Langfuse
            if trace_span:
                try:
                    trace_span.update(
                        output={
                            "response": response_text,
                            "has_citations": citations is not None,
                        },
                        metadata={
                            "total_time_seconds": round(total_time, 3),
                            "response_length": len(response_text),
                            "source_nodes_count": (
                                len(response.source_nodes)
                                if hasattr(response, "source_nodes")
                                else 0
                            ),
                        },
                    )
                finally:
                    trace_span.end()

            # Flush Langfuse trace to send to server
            if self.langfuse_client:
                try:
                    self.langfuse_client.flush()
                    logger.info("🔍 Langfuse: Flushed trace data to server")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to flush Langfuse data: {e}")

            # Return response with sources if requested
            if return_citations:
                return {"response": response_text, "sources": citations}

            return response_text

        except Exception as e:
            logger.error(f"Error generating response: {e}")

            raise

    async def generate_response_stream_special(
        self,
        persona_id: UUID,
        message: str,
        markdown_text: str,
        context: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response for special PDF chat without retrieval"""

        logger.info(
            f"🎯 SPECIAL STREAMING - persona_id: {persona_id}, markdown length: {len(markdown_text) if markdown_text else 0}"
        )

        try:
            # Get persona info to build system prompt
            from shared.database.models.database import async_session_maker

            async with async_session_maker() as session:
                persona = await self._get_persona_info(session, persona_id)
                if not persona:
                    yield "I apologize, but I couldn't find the persona information."
                    return

                persona_prompt = await self._get_persona_prompts(session, persona_id)

                # Get role and company
                role = persona.role or (persona.user.role if persona.user else None)
                company = persona.user.company if persona.user else None

                # LinkedIn repository removed; description comes from persona fields
                description = None

                persona_dict = {
                    "name": persona.name,
                    "role": role or "Expert",
                    "company": company or "Independent",
                    "description": description or persona.description,
                }

                # Build system prompt
                context["patterns"] = await self._get_persona_patterns(persona_id)
                if persona_prompt:
                    system_prompt = self.prompts.build_system_prompt_upload(
                        persona_prompt, persona_dict
                    )
                else:
                    system_prompt = self.prompts.build_system_prompt_alt(
                        persona_dict, context["patterns"]
                    )

            # Create vanilla chat engine without retrieval (no vector index)
            from llama_index.core.chat_engine import SimpleChatEngine
            from llama_index.core.memory import ChatMemoryBuffer

            persona_key = str(persona_id)
            if persona_key in self.simple_chat_engines and not markdown_text:
                logger.info("Follow Up Query for Special request for already uploaded Pitch Deck")
                chat_engine = self.simple_chat_engines[persona_key]
            else:
                logger.info(
                    f"New Special request for new uploaded Pitch Deck : {markdown_text[:50]}"
                )
                chat_engine = SimpleChatEngine.from_defaults(
                    llm=Settings.llm,
                    memory=ChatMemoryBuffer.from_defaults(token_limit=16384),
                    system_prompt=system_prompt,
                )
                self.simple_chat_engines[persona_key] = chat_engine

            # Combine markdown text with user message
            if not markdown_text:
                full_message = f"{message}"
            else:
                full_message = f"""{markdown_text} \n\nUser's question/request: {message}"""

            logger.info("🔄 Starting special streaming chat")

            # Stream response
            import time

            stream_start = time.time()
            first_token_time = None
            token_count = 0

            streams = await asyncio.wait_for(chat_engine.astream_chat(full_message), timeout=30.0)

            async for token in streams.async_response_gen():
                if token is not None:
                    if first_token_time is None:
                        first_token_time = time.time() - stream_start
                        logger.info(f"⚡ First token in {first_token_time:.3f}s")

                    token_count += 1
                    yield token

            total_time = time.time() - stream_start
            logger.info(f"✅ Special streaming complete: {token_count} tokens in {total_time:.3f}s")

        except Exception as e:
            logger.error(f"❌ Special streaming error: {e}")
            yield f"I apologize, but I encountered an error processing your document: {str(e)}"

    async def get_similar_content(
        self, persona_id: UUID, content: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Find similar content within persona's knowledge base"""
        try:
            persona_key = str(persona_id)

            if persona_key not in self.persona_indexes:
                return []

            # Use content as query to find similar chunks
            context = await self.retrieve_context(
                persona_id, content, top_k=top_k, include_patterns=False
            )

            return context.get("chunks", [])

        except Exception as e:
            logger.error(f"Error finding similar content: {e}")
            return []

    async def update_persona_content(
        self, persona_id: UUID, new_content: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update persona's knowledge base with new content"""
        try:
            # Remove existing index to rebuild
            persona_key = str(persona_id)
            if persona_key in self.persona_indexes:
                del self.persona_indexes[persona_key]

            # Reingest with new content
            return await self.ingest_persona_data(persona_id, new_content, force_rebuild=True)

        except Exception as e:
            logger.error(f"Error updating persona content: {e}")
            raise

    async def _get_persona_patterns(self, persona_id: UUID) -> Dict[str, Any]:
        """Get communication patterns for persona"""
        try:
            from shared.database.models.database import async_session_maker

            async with async_session_maker() as session:
                stmt = select(Pattern).where(Pattern.persona_id == persona_id)
                result = await session.execute(stmt)
                patterns = result.scalars().all()

                pattern_dict = {}
                for pattern in patterns:
                    pattern_dict[pattern.pattern_type] = pattern.pattern_data

                return pattern_dict
        except Exception as e:
            logger.error(f"Error getting patterns: {e}")
            return {}

    async def _get_persona_info(self, session: AsyncSession, persona_id: UUID):
        """Get persona basic information"""
        from sqlalchemy.orm import selectinload

        stmt = select(Persona).options(selectinload(Persona.user)).where(Persona.id == persona_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_persona_prompts(self, session: AsyncSession, persona_id: UUID):
        """Get persona prompt by persona_id"""
        stmt = select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_persona_source_record_ids(self, persona_id: UUID) -> List[UUID]:
        """
        Resolve which source_record_ids a persona can access.

        This expands from root sources (profiles) to all content (posts, experiences, etc.)

        Returns:
            List of content IDs that this persona's embeddings use

        Logic:
            1. Get enabled sources from persona_data_sources
            2. For each source type, expand to all content:
               - linkedin: profile + all posts + all experiences
               - twitter: profile + all tweets
               - website: all pages from scrape
               - document: the document itself
            3. Return complete list of source_record_ids
        """
        from shared.database.models.database import async_session_maker
        from shared.database.models.persona_data_source import PersonaDataSource

        source_record_ids = []

        async with async_session_maker() as session:
            # Get enabled sources for this persona
            stmt = select(PersonaDataSource).where(
                PersonaDataSource.persona_id == persona_id, PersonaDataSource.enabled.is_(True)
            )
            result = await session.execute(stmt)
            persona_sources = result.scalars().all()

            logger.info(f"Found {len(persona_sources)} enabled sources for persona {persona_id}")

            for source in persona_sources:
                root_source_id = source.source_record_id

                if not root_source_id:
                    logger.warning(
                        f"Source {source.source_type} has no source_record_id, skipping"
                    )
                    continue

                # Add the root source itself (e.g., profile, document, youtube video)
                source_record_ids.append(root_source_id)

            # Note: LinkedIn/Twitter/Website sub-record expansion has been removed along
            # with the scraping infrastructure. Only root source IDs are returned now.

        logger.info(f"Total source_record_ids for persona {persona_id}: {len(source_record_ids)}")
        return source_record_ids

    def get_index_stats(self, persona_id: UUID) -> Dict[str, Any]:
        """Get statistics about persona's knowledge base"""
        persona_key = str(persona_id)

        if persona_key not in self.persona_indexes:
            return {"status": "no_index"}

        index = self.persona_indexes[persona_key]

        # Get basic stats
        stats = {
            "status": "active",
            "has_index": True,
            "vector_store_type": "PostgreSQL with pgvector",
            "embedding_model": "text-embedding-3-small",
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
        }

        try:
            # Try to get more detailed stats if available
            docstore = index.docstore
            stats["total_nodes"] = len(docstore.docs)
        except Exception:
            stats["total_nodes"] = "unknown"

        return stats

    def _get_source_title(self, source_type: str, metadata: dict) -> str:
        """Generate appropriate title for source"""
        if source_type == "linkedin_profile":
            return "LinkedIn Profile"
        elif source_type == "twitter_profile":
            return "X (Twitter) Profile"
        elif source_type == "website_content":
            return metadata.get("title", "Website Content")
        else:
            return source_type.replace("_", " ").title()

    def _get_source_context(self, source_type: str, metadata: dict, content: str) -> str:
        """Generate appropriate context for source"""
        # Get the source_type from metadata (e.g., 'document' for audio/video/pdf)
        metadata_source_type = metadata.get("source_type", "")

        # For document source types (audio, video, pdf), use context from metadata
        if metadata_source_type == "document":
            context = metadata.get("context", "").strip()
            if context:
                return context

        # For YouTube source, use title from metadata
        if source_type == "youtube":
            title = metadata.get("title", "").strip()
            if title:
                return title

        # For all other sources, use truncated content
        if len(content) > 300:
            return content[:300] + "..."
        else:
            return content

    async def _ensure_persona_index(self, persona_id: UUID) -> bool:
        """Ensure persona index exists by creating reference to existing vector data only"""
        logger.info("📊 === ENSURE_PERSONA_INDEX CALLED ===")
        logger.info(f"🔍 Requested persona_id: {persona_id}")

        try:
            persona_key = str(persona_id)
            logger.info(f"🔍 Converted persona_key: '{persona_key}'")

            if persona_key in self.persona_indexes:
                logger.info(f"✅ Index already exists for persona {persona_id}, using cached index")
                return True

            logger.info(
                f"🔄 Creating index reference for existing vector data for persona {persona_id}..."
            )

            # Create index from existing vector store data - NO RE-INGESTION
            # The vector data should already exist from initial persona creation
            def create_index_from_existing():
                return VectorStoreIndex.from_vector_store(
                    vector_store=self.vector_store,
                    storage_context=self.storage_context,
                )

            # Create index reference to existing vector data
            index = await asyncio.get_event_loop().run_in_executor(None, create_index_from_existing)

            self.persona_indexes[persona_key] = index
            logger.info(f"✅ Successfully created index reference for persona {persona_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error creating index reference: {e}")
            logger.error(f"❌ This indicates vector data may not exist for persona {persona_id}")
            logger.error("❌ Persona should be properly ingested during creation, not during chat")
            return False

    async def refresh_persona_index(self, persona_id: UUID) -> bool:
        """
        Refresh the persona index by clearing the cache and reloading from the database.
        This ensures the latest vector embeddings are used for retrieval.

        This method updates the retriever in the existing chat engine (if present) to preserve
        chat history while using fresh embeddings from the database.

        Args:
            persona_id: UUID of the persona whose index should be refreshed

        Returns:
            True if refresh was successful, False otherwise
        """
        logger.info(f"🔄 === REFRESHING INDEX FOR PERSONA {persona_id} ===")

        try:
            persona_key = str(persona_id)

            # Clear the cached index if it exists
            if persona_key in self.persona_indexes:
                logger.info(f"🗑️ Clearing cached index for persona {persona_id}")
                del self.persona_indexes[
                    persona_key
                ]  # Fixed: use persona_key instead of persona_id

            # Recreate index from vector store (loads latest data from database)
            logger.info(f"📊 Loading fresh index from vector store for persona {persona_id}")

            def create_fresh_index():
                return VectorStoreIndex.from_vector_store(
                    vector_store=self.vector_store,
                    storage_context=self.storage_context,
                )

            index = await asyncio.get_event_loop().run_in_executor(None, create_fresh_index)
            self.persona_indexes[persona_key] = index

            # Update the retriever in existing chat engine (if present) to preserve chat history
            if persona_key in self.persona_chat_engines:
                logger.info(
                    f"🔄 Updating retriever in existing chat engine for persona {persona_id}"
                )
                chat_engine = self.persona_chat_engines[persona_key]

                # Get source_record_ids for filtering
                source_record_ids = await self.get_persona_source_record_ids(persona_id)
                if source_record_ids:
                    source_record_ids_str = [str(sid) for sid in source_record_ids]

                    from llama_index.core.vector_stores.types import MetadataFilter, MetadataFilters

                    metadata_filters = MetadataFilters(
                        filters=[
                            MetadataFilter(
                                key="source_record_id", value=source_record_ids_str, operator="in"
                            )
                        ]
                    )

                    # Create new retriever with fresh index and updated filters
                    new_retriever = index.as_retriever(
                        filters=metadata_filters,
                        similarity_top_k=5,
                        vector_store_query_mode="hybrid",
                    )

                    # Update the retriever in the chat engine
                    # CondensePlusContextChatEngine stores retriever in _retriever attribute
                    if hasattr(chat_engine, "_retriever"):
                        chat_engine._retriever = new_retriever
                        logger.info(f"✅ Updated retriever in chat engine for persona {persona_id}")
                    else:
                        logger.warning(
                            "⚠️ Chat engine doesn't have _retriever attribute, skipping update"
                        )
                else:
                    logger.warning(f"⚠️ No source_record_ids found for persona {persona_id}")

            logger.info(f"✅ Successfully refreshed index for persona {persona_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Error refreshing index for persona {persona_id}: {e}")
            return False
