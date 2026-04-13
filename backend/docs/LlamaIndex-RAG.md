# LlamaIndex RAG System - Technical Implementation

## Ingestion Flow & Dual Storage Architecture

### Overview

Our system uses LlamaIndex for RAG (Retrieval-Augmented Generation) with a dual storage approach that maintains both raw text and vector embeddings for optimal performance.

### Data Flow Architecture

```
Content Sources → ingest_persona_data() → get_nodes_from_documents() → Dual Storage
                                                ↓
                                      ┌─────────────────────┐
                                      │   LlamaIndex        │
                                      │   SentenceSplitter  │
                                      │   (800 chars,       │
                                      │    200 overlap)     │
                                      └─────────────────────┘
                                        ↓
          ┌──────────────────────────────────────────────────────────────┐
          │                      DUAL STORAGE                            │
          ├──────────────────────────┬───────────────────────────────────┤
          │    ContentChunk Table    │  data_llamaindex_embeddings       │
          │    (Raw Text Storage)    │      (Vector Storage)             │
          ├──────────────────────────┼───────────────────────────────────┤
          │ • content (TEXT)         │ • embedding (VECTOR)              │
          │ • source                 │ • document content                │
          │ • chunk_index            │ • metadata                        │
          │ • chunk_metadata (JSON)  │ • persona filtering               │
          │ • persona_id             │ • persona_id (UUID)               │
          └──────────────────────────┴───────────────────────────────────┘
```

## Key Components

### 1. ingest_persona_data() (llama_rag.py:123)

Main ingestion function that:
- Creates LlamaIndex Document objects from content sources
- Calls LlamaIndex's chunking system
- Orchestrates dual storage
- Manages persona-specific indexes

### 2. get_nodes_from_documents() (llama_rag.py:165)

LlamaIndex's SentenceSplitter that:
- Chunks content into 800-character segments with 200-character overlap
- Handles sentence boundary detection
- Creates Node objects with metadata

### 3. Dual Storage System

**ContentChunk Table (async_session_maker())**
- Purpose: Raw text storage for display/debugging
- Content: Original chunked text + metadata
- Access: Direct SQL queries for human-readable data

**pgvector Table (data_llamaindex_embeddings)**
- Purpose: Vector embeddings for semantic search
- Content: 1536-dimensional vectors from OpenAI text-embedding-3-small
- Access: LlamaIndex VectorStoreIndex for similarity search

### 4. VectorStoreIndex Objects

- **In-Memory**: Cached VectorStoreIndex objects per persona
- **Purpose**: Query interface and retrieval coordination
- **Storage**: `self.persona_indexes = {}` cache
- **Lifecycle**: Created once, reused for performance

## Why Dual Storage?

1. **Performance**: Vector search for retrieval, SQL for management
2. **Debugging**: Human-readable text in ContentChunk table
3. **Flexibility**: Different access patterns for different use cases
4. **Reliability**: Backup storage and audit trail

## Configuration

```python
# LlamaIndex Settings
Settings.embed_model = OpenAIEmbedding("text-embedding-3-small")
Settings.llm = OpenAI("gpt-4o-mini")

# Chunking Configuration
SentenceSplitter(
    chunk_size=800,
    chunk_overlap=200,
    paragraph_separator="\n\n",
    secondary_chunking_regex="[.!?]+"
)

# Vector Store
# Note: LlamaIndex automatically prepends "data_" to the table name
# So table_name="llamaindex_embeddings" creates "data_llamaindex_embeddings"
PGVectorStore.from_params(
    table_name="llamaindex_embeddings",
    embed_dim=1536,
    hybrid_search=True
)
```

## Performance Notes

- **Index Caching**: VectorStoreIndex objects cached per persona for performance
- **Async Operations**: Database operations use async_session_maker()
- **Batch Processing**: Multiple nodes processed in single transactions
- **Vector Optimization**: pgvector with IVFFlat indexes for similarity search

This dual approach ensures both fast semantic search capabilities and maintainable data management.