# Langfuse Quick Reference - Current Implementation

**Last Updated:** November 16, 2025

## Table of Contents
- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
- [Enhanced Score Tracking](#enhanced-score-tracking) ⭐ **NEW**
- [Span API](#span-api)
- [Filtering & Queries](#filtering--queries)
- [Code Examples](#code-examples)

---

## Installation

```bash
# Install Langfuse SDK
pip install langfuse==3.9.2

# Or with poetry
poetry add langfuse
```

---

## Configuration

### Environment Variables

```bash
# .env file
LANGFUSE_PUBLIC_KEY=pk_your_public_key
LANGFUSE_SECRET_KEY=sk_your_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Initialize Client

```python
from langfuse import Langfuse

client = Langfuse(
    public_key="pk_...",
    secret_key="sk_...",
    host="https://cloud.langfuse.com"
)
```

---

## Basic Usage

### Create a Span

```python
# Start a span
span = client.start_span(
    name="my_operation",
    input={"query": "What is AI?"},
    metadata={
        "user_id": "user-123",
        "session_id": "session-abc",
        "tags": ["ai", "query"]
    }
)

try:
    # Do work
    result = process_query()
    
    # Update with output
    span.update(
        output={"response": result},
        metadata={"duration": 1.23}
    )
finally:
    # End the span
    span.end()

# Send to server
client.flush()
```

### Use Context Manager (Streaming)

```python
# Automatic lifecycle management
with client.start_as_current_span(
    name="streaming_operation",
    input={"query": "Tell me more"},
    metadata={
        "user_id": "user-123",
        "session_id": "session-abc",
        "tags": ["stream"]
    }
) as span:
    # Stream data
    for chunk in generate_stream():
        full_response += chunk
        yield chunk
    
    # Update before exit (auto-ends)
    if span:
        span.update(output={"full_response": full_response})

# Flush after context exits
client.flush()
```

---

## Enhanced Score Tracking

### Overview

**New in November 2025:** All evaluation endpoints now support enhanced score tracking with:
- ✅ Data types (NUMERIC, CATEGORICAL, BOOLEAN)
- ✅ Automatic contextual tags
- ✅ Score normalization (0-1 range)
- ✅ Evaluator type tracking

### Using LangfuseObservabilityService

```python
from app.services.langfuse_observability_service import LangfuseObservabilityService

service = LangfuseObservabilityService()

# Get automatic tags for a metric
tags = service._get_metric_tags('faithfulness', 'llm_judge')
# Returns: ['prompt_evaluation', 'evaluator:llm_judge', 'generation', 'rag', 'hallucination_detection']

# Log score with enhanced metadata
await service.log_score(
    trace_id=trace_id,
    name="faithfulness",
    value=0.87,                      # Normalized 0-1
    data_type="NUMERIC",             # NUMERIC, CATEGORICAL, or BOOLEAN
    tags=tags,                       # Automatic contextual tags
    observation_id=span_id,          # Optional: attach to span
    comment="Hallucination detection score"
)
```

### Data Types

```python
# NUMERIC - Evaluation scores (0-1 range)
await service.log_score(
    name="faithfulness",
    value=0.87,
    data_type="NUMERIC"
)

# CATEGORICAL - Classifications
await service.log_score(
    name="latency_category",
    value="excellent",  # excellent/good/acceptable/slow
    data_type="CATEGORICAL"
)

# BOOLEAN - Pass/fail flags
await service.log_score(
    name="passed_threshold",
    value=True,
    data_type="BOOLEAN"
)
```

### Automatic Tag Generation

Tags are automatically generated based on metric type and evaluator:

```python
# Generation metrics
service._get_metric_tags('faithfulness', 'llm_judge')
# ['prompt_evaluation', 'evaluator:llm_judge', 'generation', 'rag', 'hallucination_detection']

# Retrieval metrics
service._get_metric_tags('context_relevancy', 'llamaindex')
# ['prompt_evaluation', 'evaluator:llamaindex', 'retrieval', 'rag', 'relevance']

# Quality metrics
service._get_metric_tags('helpfulness', 'llm_judge')
# ['prompt_evaluation', 'evaluator:llm_judge', 'quality']

# Performance metrics
service._get_metric_tags('latency_ms', None)
# ['prompt_evaluation', 'performance']
```

### Log Multiple Scores

```python
# Batch log with automatic tags
overall_scores = {
    "faithfulness": 0.87,
    "answer_relevancy": 0.82,
    "correctness": 0.90,
    "semantic_similarity": 0.85
}

await service.log_multiple_scores(
    trace_id=trace_id,
    scores=overall_scores,
    evaluator_type="llm_judge",      # Adds evaluator tag to all scores
    comment_prefix="Overall average"
)
```

### Score Normalization

Always normalize scores to 0-1 range for consistency:

```python
# Raw score (0-100)
raw_score = 85.5

# Normalize to 0-1
normalized = raw_score / 100.0 if raw_score > 1 else raw_score

# Log normalized score
await service.log_score(
    name="accuracy",
    value=normalized,  # 0.855
    data_type="NUMERIC"
)
```

### Tag Categories

**Base Tags:**
- `prompt_evaluation` - Always included

**Evaluator Tags:**
- `evaluator:llm_judge` - LLM-as-judge evaluator
- `evaluator:llamaindex` - LlamaIndex evaluators
- `evaluator:heuristic` - Custom heuristics

**Category Tags:**
- `generation` - Generation quality
- `retrieval` - Retrieval performance
- `quality` - Overall quality
- `performance` - Latency/throughput
- `rag` - RAG-specific

**Aspect Tags:**
- `relevance` - Relevancy metrics
- `accuracy` - Precision metrics
- `hallucination_detection` - Faithfulness

### Querying by Tags

```python
from langfuse import Langfuse

client = Langfuse()

# Filter by evaluator type
traces = client.get_traces(tags=["evaluator:llm_judge"])

# Filter by category
traces = client.get_traces(tags=["retrieval", "rag"])

# Filter by aspect
scores = client.get_scores(tags=["hallucination_detection"])

# Get categorical scores
perf_scores = client.get_scores(
    name="latency_category",
    data_type="CATEGORICAL"
)
```

---

## Span API

### Langfuse 3.9.2 Methods

#### ✅ Available Methods

| Method | Use Case | Lifecycle |
|--------|----------|-----------|
| `start_span()` | Manual control | Requires `.end()` |
| `start_as_current_span()` | Context manager | Auto-ends |
| `span.update()` | Update span data | Any time before end |
| `span.end()` | Close span | Required for `start_span()` |
| `client.flush()` | Send to server | After operations |

#### ❌ Unavailable Methods (Pre-3.9.2)

| Method | Status | Alternative |
|--------|--------|-------------|
| `client.trace()` | ❌ Not available | Use `start_span()` |
| `trace.span()` | ❌ Not available | Use `start_span()` |
| `trace.generation()` | ❌ Not available | Use `span.update()` |

### `start_span()` Parameters

```python
span = client.start_span(
    name="operation_name",           # Required: Span name
    input={"key": "value"},          # Optional: Input data
    output={"result": "value"},      # Optional: Output data
    metadata={"custom": "data"},     # Optional: Metadata
    version="1.0",                   # Optional: Version
    level="info",                    # Optional: info|warning|error
    status_message="Success",        # Optional: Status message
)
```

### `start_as_current_span()` Parameters

```python
with client.start_as_current_span(
    name="streaming_operation",
    input={"key": "value"},
    metadata={"user_id": "123"},
    end_on_exit=True,                # Auto-end (default: True)
) as span:
    # Do work
    if span:
        span.update(output={"result": "..."})
    # span.end() called automatically
```

### `span.update()` Parameters

```python
span.update(
    name="updated_name",             # Optional: Change name
    input={"new": "input"},          # Optional: Update input
    output={"final": "output"},      # Optional: Set output
    metadata={"extra": "data"},      # Optional: Add metadata
    level="warning",                 # Optional: Change level
    status_message="Updated",        # Optional: Status
    model="gpt-4",                   # Optional: Model name
    model_parameters={"temp": 0.7},  # Optional: Model params
    usage_details={"tokens": 100},   # Optional: Usage stats
    cost_details={"cost": 0.001},    # Optional: Cost info
)
```

---

## Filtering & Queries

### Metadata Structure

```json
{
  "metadata": {
    "user_id": "user-123",
    "session_id": "session-abc",
    "tags": ["llama_rag", "stream", "persona:xxx", "session:abc"],
    "custom_field": "value"
  }
}
```

### Dashboard Filters

#### By User ID
```
metadata.user_id = "user-123"
```

#### By Session ID
```
metadata.session_id = "session-abc"
```

#### By Tags
```
metadata.tags contains "llama_rag"
metadata.tags contains "persona:550e8400-e29b-41d4-a716-446655440000"
```

#### Combined
```
metadata.user_id = "user-123" AND metadata.session_id = "session-abc"
```

#### Performance
```
metadata.total_time_seconds > 5.0
metadata.token_count > 500
```

### API Queries

```python
from langfuse import Langfuse

client = Langfuse()

# Filter by user
traces = client.get_traces(
    filter=[
        {"field": "metadata.user_id", "operator": "=", "value": "user-123"}
    ]
)

# Filter by session
traces = client.get_traces(
    filter=[
        {"field": "metadata.session_id", "operator": "=", "value": "session-abc"}
    ]
)

# Filter by time range
traces = client.get_traces(
    from_timestamp="2024-01-01T00:00:00Z",
    to_timestamp="2024-01-31T23:59:59Z"
)
```

---

## Code Examples

### Example 1: Simple Operation

```python
from langfuse import Langfuse

client = Langfuse()

span = client.start_span(
    name="process_request",
    input={"request": "data"},
    metadata={
        "user_id": "user-123",
        "tags": ["api", "request"]
    }
)

try:
    result = process_data()
    span.update(
        output={"response": result},
        metadata={"success": True}
    )
except Exception as e:
    span.update(
        level="error",
        status_message=str(e),
        metadata={"success": False}
    )
    raise
finally:
    span.end()
    client.flush()
```

### Example 2: Streaming with Context Manager

```python
from langfuse import Langfuse

client = Langfuse()

async def stream_response(query: str, user_id: str, session_id: str):
    with client.start_as_current_span(
        name="streaming_chat",
        input={"query": query},
        metadata={
            "user_id": user_id,
            "session_id": session_id,
            "tags": ["stream", "chat"]
        }
    ) as span:
        full_response = ""
        token_count = 0
        
        async for token in generate_tokens(query):
            full_response += token
            token_count += 1
            yield token
        
        # Update before exiting
        if span:
            span.update(
                output={"full_response": full_response},
                metadata={"token_count": token_count}
            )
    
    # Flush after context manager
    client.flush()
```

### Example 3: RAG with Retrieved Context

```python
from langfuse import Langfuse

client = Langfuse()

def rag_query(query: str, user_id: str):
    span = client.start_span(
        name="rag_query",
        input={"query": query},
        metadata={
            "user_id": user_id,
            "tags": ["rag", "retrieval"]
        }
    )
    
    try:
        # Retrieve context
        context = retrieve_context(query)
        
        # Generate response
        response = generate_with_context(query, context)
        
        # Update with output
        span.update(
            output={
                "response": response,
                "retrieved_nodes": [
                    {
                        "content": node.content,
                        "score": node.score
                    }
                    for node in context
                ]
            },
            metadata={
                "context_count": len(context),
                "avg_score": sum(n.score for n in context) / len(context)
            }
        )
        
        return response
    finally:
        span.end()
        client.flush()
```

### Example 4: Session Tracking

```python
from langfuse import Langfuse

client = Langfuse()

class ConversationSession:
    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id
        self.client = Langfuse()
    
    def send_message(self, message: str):
        with self.client.start_as_current_span(
            name=f"conversation.{self.session_id}",
            input={"message": message},
            metadata={
                "user_id": self.user_id,
                "session_id": self.session_id,
                "tags": [
                    "conversation",
                    f"user:{self.user_id}",
                    f"session:{self.session_id}"
                ]
            }
        ) as span:
            response = process_message(message)
            
            if span:
                span.update(output={"response": response})
            
            return response
        
        # Auto-flush or manual
        self.client.flush()
```

---

## Best Practices

### 1. Always Use Try-Finally for Manual Spans

```python
span = client.start_span(name="operation")
try:
    # Do work
    span.update(output={"result": "..."})
finally:
    span.end()  # ← Always end, even on error
    client.flush()
```

### 2. Check Span Before Update in Context Manager

```python
with client.start_as_current_span(name="op") as span:
    # Do work
    if span:  # ← Check before using
        span.update(output={"result": "..."})
```

### 3. Use Meaningful Names

```python
# ❌ Bad
span = client.start_span(name="function")

# ✅ Good
span = client.start_span(name="llama_rag_stream.persona_123.2024-11-14")
```

### 4. Include Rich Metadata

```python
metadata = {
    "user_id": str(user_id),
    "session_id": str(session_id),
    "tags": [
        "operation_type",
        f"user:{user_id}",
        f"session:{session_id}"
    ],
    "version": "1.0",
    "environment": "production"
}
```

### 5. Flush After Operations

```python
# After single operation
span.end()
client.flush()

# After batch operations
for item in items:
    span = process(item)
    span.end()
client.flush()  # ← Single flush for batch
```

---

## Common Patterns

### Fallback Pattern (Nullcontext)

```python
from contextlib import nullcontext

langfuse_context = nullcontext()  # Default

if client:
    try:
        langfuse_context = client.start_as_current_span(...)
    except Exception:
        langfuse_context = nullcontext()  # Fallback

with langfuse_context as span:
    # Always safe, span may be None
    if span:
        span.update(...)
```

### Error Handling Pattern

```python
span = client.start_span(name="operation")
try:
    result = risky_operation()
    span.update(output={"result": result}, level="info")
except Exception as e:
    span.update(
        level="error",
        status_message=str(e),
        metadata={"error_type": type(e).__name__}
    )
    raise
finally:
    span.end()
    client.flush()
```

---

## Troubleshooting

### Issue: Spans Not Appearing

**Check credentials**:
```python
from langfuse import Langfuse
client = Langfuse()
# Should not raise authentication error
```

**Check flush**:
```python
client.flush()
# Look for log: "Flushed X spans to Langfuse"
```

### Issue: `AttributeError: 'Langfuse' object has no attribute 'trace'`

**Problem**: Using old API

**Solution**: Use span API
```python
# ❌ OLD (doesn't work in 3.9.2)
trace = client.trace(...)

# ✅ NEW (works in 3.9.2)
span = client.start_span(...)
```

### Issue: Missing metadata fields

**Problem**: Metadata not properly structured

**Solution**: Ensure correct format
```python
# ✅ Correct
metadata = {
    "user_id": "value",
    "tags": ["tag1", "tag2"]
}
```

---

## See Also

- [LlamaRAG Integration](./LANGFUSE_LLAMARAG_INTEGRATION.md)
- [Prompt Evaluation](./LANGFUSE_PROMPT_EVALUATION.md)
- [Official Docs](https://langfuse.com/docs)

---

**Last Updated**: November 14, 2024  
**SDK Version**: Langfuse 3.9.2  
**API**: OpenTelemetry-based (Span API)

