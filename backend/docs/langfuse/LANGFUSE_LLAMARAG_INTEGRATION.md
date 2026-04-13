# Langfuse Integration with LlamaRAG - Complete Guide

## Overview

This document describes the complete Langfuse tracing integration with the LlamaRAG system. The implementation uses Langfuse SDK v3.9.2 with OpenTelemetry-based APIs.

## Table of Contents
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Implementation Details](#implementation-details)
- [Span Structure](#span-structure)
- [Filtering & Queries](#filtering--queries)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites
- Langfuse SDK v3.9.2+ installed
- Langfuse credentials configured in `.env`:
  ```bash
  LANGFUSE_PUBLIC_KEY=pk_xxx
  LANGFUSE_SECRET_KEY=sk_xxx
  LANGFUSE_HOST=https://cloud.langfuse.com
  ```

### What Gets Traced
1. **RAG Retrieval** (`retrieve_context`) - Context retrieval operations
2. **Streaming Chat** (`generate_response_stream`) - Real-time response generation
3. **Non-Streaming Chat** (`generate_response`) - Batch response generation

### Automatic Session Tracking
Session IDs are automatically propagated from API routes → ResponseGenerator → LlamaRAG:

```python
# API route passes session_id
response_data = await response_generator.generate_response(
    session=session,
    persona_id=persona_id,
    message=message,
    session_id=request.session_token,  # ← Passed here
    stream=True
)

# ResponseGenerator includes it in context
context = {
    "session_id": session_id,  # ← Added to context
    "patterns": {}
}

# LlamaRAG extracts and uses it
session_id = context.get("session_id")  # ← Extracted in RAG
```

---

## Architecture

### Flow Diagram
```
API Request (session_routes.py)
    ↓
ResponseGenerator (generator.py)
    ↓ (context with session_id)
LlamaRAGSystem (llama_rag.py)
    ↓
Langfuse Span Created
    ├─ user_id: persona_id
    ├─ session_id: session_token
    ├─ input: {query, params}
    ├─ output: {response, nodes}
    └─ metadata: {tags, metrics}
    ↓
Langfuse Dashboard
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| `LlamaRAGSystem` | Creates and manages Langfuse spans |
| `ResponseGenerator` | Propagates session_id via context |
| `API Routes` | Provides session_token from request |
| `Langfuse Client` | Sends telemetry to Langfuse server |

---

## Implementation Details

### 1. Streaming Response (`generate_response_stream`)

**Location**: `shared/rag/llama_rag.py:692`

**API Used**: `start_as_current_span()` (context manager)

**Implementation**:
```python
async def generate_response_stream(
    self,
    persona_id: UUID,
    query: str,
    context: Dict[str, Any],
    ...
) -> AsyncGenerator[Any, None]:
    session_id = context.get("session_id")
    
    if self.langfuse_client:
        # Session-based naming: llama_stream_{persona_id}_{session_id}
        session_name = f"llama_stream_{persona_id}_{session_id if session_id else 'unknown'}"
        
        langfuse_context = self.langfuse_client.start_as_current_span(
            name=session_name,  # Groups all traces from same conversation
            input={
                "query": query,
                "persona_id": str(persona_id),
                "session_id": session_id,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            metadata={
                "user_id": str(persona_id),  # ← For user filtering
                "session_id": session_id if session_id else "unknown",  # ← For session filtering
                "tags": [
                    "llama_rag",
                    "stream",
                    f"persona:{persona_id}",
                    f"session:{session_id}" if session_id else "session:unknown",
                ]
            },
        )
    
    with langfuse_context as span:
        # Stream tokens...
        async for token in streams.async_response_gen():
            full_response += token
            yield token
        
        # Update with output
        if span:
            span.update(
                output={
                    "full_response": full_response,
                    "retrieved_nodes": retrieved_context,
                },
                metadata={
                    "token_count": token_count,
                    "total_time_seconds": total_time,
                    "first_token_time_seconds": first_token_time,
                },
            )
        # span.end() called automatically by context manager
    
    # Flush to server
    self.langfuse_client.flush()
```

**Features**:
- ✅ Automatic span lifecycle (context manager)
- ✅ User ID tracking (persona_id)
- ✅ Session ID tracking
- ✅ Real-time token streaming
- ✅ Retrieved context capture
- ✅ Performance metrics (TTFT, latency)

---

### 2. Context Retrieval (`retrieve_context`)

**Location**: `shared/rag/llama_rag.py:498`

**API Used**: `start_span()` (manual lifecycle)

**Implementation**:
```python
async def retrieve_context(
    self,
    persona_id: UUID,
    query: str,
    ...
) -> Dict[str, Any]:
    trace_span = None
    
    if self.langfuse_client:
        trace_span = self.langfuse_client.start_span(
            name="llama_rag_retrieve_context",
            input={
                "persona_id": str(persona_id),
                "query": query,
                "top_k": top_k,
                "similarity_threshold": similarity_threshold,
            },
            metadata={
                "user_id": str(persona_id),  # ← User tracking
                "tags": [
                    "retrieval",
                    "rag",
                    "llamaindex",
                    f"persona:{persona_id}"
                ]
            },
        )
    
    try:
        # Retrieve chunks...
        chunks = retriever.retrieve(query)
        
        # Update span
        if trace_span:
            trace_span.update(
                output={
                    "chunks_count": len(chunks),
                    "similarity_info": result["similarity_info"],
                },
                metadata={"retrieval_time_seconds": retrieval_time},
            )
    finally:
        if trace_span:
            trace_span.end()  # ← Manual end required
```

**Features**:
- ✅ Manual span lifecycle control
- ✅ User ID tracking
- ✅ Retrieval metrics
- ✅ Error handling with finally block

---

### 3. Non-Streaming Chat (`generate_response`)

**Location**: `shared/rag/llama_rag.py:934`

**API Used**: `start_span()` (manual lifecycle)

**Implementation**:
```python
async def generate_response(
    self,
    persona_id: UUID,
    query: str,
    context: Dict[str, Any],
    ...
) -> Any:
    trace_span = None
    session_id = context.get("session_id")
    
    if self.langfuse_client:
        trace_span = self.langfuse_client.start_span(
            name="llama_rag_chat",
            input={
                "persona_id": str(persona_id),
                "query": query,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "session_id": session_id,
            },
            metadata={
                "user_id": str(persona_id),  # ← User tracking
                "session_id": session_id if session_id else "unknown",  # ← Session tracking
                "tags": [
                    "chat",
                    "rag",
                    "llamaindex",
                    f"persona:{persona_id}",
                    f"session:{session_id}" if session_id else "session:unknown",
                ]
            },
        )
    
    try:
        # Generate response...
        response = chat_engine.chat(query)
        
        # Update span
        if trace_span:
            trace_span.update(
                output={
                    "response": response_text,
                    "has_citations": citations is not None,
                },
                metadata={
                    "total_time_seconds": total_time,
                    "response_length": len(response_text),
                    "source_nodes_count": len(response.source_nodes),
                },
            )
    finally:
        if trace_span:
            trace_span.end()  # ← Manual end required
```

**Features**:
- ✅ Manual span lifecycle control
- ✅ User ID and Session ID tracking
- ✅ Full response capture
- ✅ Citation tracking
- ✅ Performance metrics

---

## Span Structure

### Metadata Schema

```json
{
  "name": "llama_stream_{persona_id}_{session_id}",
  "input": {
    "query": "What are your main skills?",
    "persona_id": "550e8400-e29b-41d4-a716-446655440000",
    "session_id": "session-abc-123",
    "temperature": 0.7,
    "max_tokens": 1000
  },
  "output": {
    "full_response": "I specialize in software engineering...",
    "retrieved_nodes": [
      {
        "content": "10 years of experience in Python...",
        "metadata": {"source": "linkedin", "chunk_index": 0},
        "score": 0.89
      }
    ]
  },
  "metadata": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "session_id": "session-abc-123",
    "session_name": "llama_stream_550e8400-e29b-41d4-a716-446655440000_session-abc-123",
    "tags": [
      "llama_rag",
      "stream",
      "persona:550e8400-e29b-41d4-a716-446655440000",
      "session:session-abc-123"
    ],
    "token_count": 247,
    "total_time_seconds": 3.456,
    "first_token_time_seconds": 0.234
  }
}
```

### Key Fields

| Field | Purpose | Type | Example |
|-------|---------|------|---------|
| `metadata.user_id` | Filter by user/persona | string | `"550e8400-e29b-41d4..."` |
| `metadata.session_id` | Filter by session | string | `"session-abc-123"` |
| `metadata.tags` | Multiple filters | array | `["llama_rag", "stream"]` |
| `input.query` | User question | string | `"What are your skills?"` |
| `output.full_response` | Complete answer | string | `"I specialize in..."` |
| `output.retrieved_nodes` | RAG context | array | `[{content, score}]` |

---

## Filtering & Queries

### Langfuse Dashboard Filters

#### 1. Filter by User/Persona
```
metadata.user_id = "550e8400-e29b-41d4-a716-446655440000"
```

#### 2. Filter by Session
```
metadata.session_id = "session-abc-123"
```

#### 3. Filter by Tags
```
metadata.tags contains "llama_rag"
metadata.tags contains "stream"
metadata.tags contains "persona:550e8400-e29b-41d4-a716-446655440000"
metadata.tags contains "session:session-abc-123"
```

#### 4. Combined Filters
```
metadata.user_id = "550e8400..." AND metadata.session_id = "session-abc-123"
```

#### 5. Performance Queries
```
metadata.total_time_seconds > 5.0
metadata.token_count > 500
metadata.first_token_time_seconds > 1.0
```

### API Query Examples

```python
from langfuse import Langfuse

client = Langfuse()

# Get all traces for a persona
traces = client.get_traces(
    filter=[
        {"field": "metadata.user_id", "operator": "=", "value": persona_id}
    ]
)

# Get all traces for a session
traces = client.get_traces(
    filter=[
        {"field": "metadata.session_id", "operator": "=", "value": session_id}
    ]
)

# Get slow traces
traces = client.get_traces(
    filter=[
        {"field": "metadata.total_time_seconds", "operator": ">", "value": 5.0}
    ]
)
```

---

## Troubleshooting

### Common Issues

#### 1. Spans Not Appearing in Dashboard

**Check**:
```bash
# Verify credentials
echo $LANGFUSE_PUBLIC_KEY
echo $LANGFUSE_SECRET_KEY
echo $LANGFUSE_HOST

# Check logs for flush confirmation
grep "Langfuse: Flushed" logs/app.log
```

**Solution**: Ensure credentials are set and `client.flush()` is called.

---

#### 2. Missing session_id

**Check**: Verify session_id is passed through the stack:
```python
# In API route
logger.info(f"Session ID: {request.session_token}")

# In ResponseGenerator
logger.info(f"Context: {context}")

# In LlamaRAG
logger.info(f"Session ID extracted: {session_id}")
```

**Solution**: Ensure `session_id` is in context dictionary.

---

#### 3. Old API Errors (`'Langfuse' object has no attribute 'trace'`)

**Problem**: Code using old API (`.trace()` doesn't exist in v3.9.2)

**Solution**: Use span-based API:
```python
# ❌ OLD (doesn't work)
trace = client.trace(name="...", user_id="...", tags=[])

# ✅ NEW (works in v3.9.2)
span = client.start_span(
    name="...",
    metadata={"user_id": "...", "tags": [...]}
)
```

---

#### 4. Context Manager Errors

**Problem**: `langfuse_span` is None inside `with` block

**Solution**: Initialize with nullcontext():
```python
from contextlib import nullcontext

langfuse_context = nullcontext()  # ← Default fallback

if self.langfuse_client:
    try:
        langfuse_context = self.langfuse_client.start_as_current_span(...)
    except Exception as e:
        logger.warning(f"Failed: {e}")
        langfuse_context = nullcontext()  # ← Fallback

with langfuse_context as span:  # ← span may be None if fallback
    if span:  # ← Always check before using
        span.update(...)
```

---

## Performance Considerations

### Overhead
- Span creation: ~5-10ms
- Span update: ~2-5ms
- Flush (async): Non-blocking

### Best Practices
1. **Flush after operations**: Call `client.flush()` after span completion
2. **Use context managers for streaming**: Automatic lifecycle management
3. **Manual `.end()` for non-streaming**: Ensure spans are always closed
4. **Batch flushes**: Langfuse batches spans automatically (default: 512 spans or 5s)

---

## Migration Guide

### From Old API (Pre-3.9.2)

```python
# ❌ OLD
trace = client.trace(
    name="chat",
    user_id=str(user_id),
    metadata={"key": "value"},
    tags=["tag1", "tag2"]
)
span = trace.span(name="operation")

# ✅ NEW
span = client.start_span(
    name="chat",
    input={"query": "..."},
    metadata={
        "user_id": str(user_id),
        "tags": ["tag1", "tag2"],
        "key": "value"
    }
)
try:
    # Do work
    span.update(output={"result": "..."})
finally:
    span.end()
```

---

## See Also

- [Langfuse Quick Reference](./LANGFUSE_QUICK_REFERENCE.md)
- [Langfuse Prompt Evaluation](./LANGFUSE_PROMPT_EVALUATION.md)
- [Implementation Summary](./LANGFUSE_IMPLEMENTATION_SUMMARY.md)
- [Official Langfuse Docs](https://langfuse.com/docs)

---

**Last Updated**: November 14, 2024  
**SDK Version**: Langfuse 3.9.2  
**API**: OpenTelemetry-based (span API)

