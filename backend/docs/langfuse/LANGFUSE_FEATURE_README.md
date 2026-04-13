# Langfuse Features - README

## What is Langfuse?

Langfuse is an open-source LLM observability and analytics platform that helps you trace, monitor, and evaluate your LLM applications.

## Why We Use Langfuse

### Key Benefits

1. **🔍 Complete Visibility**: See every RAG operation, query, and response
2. **📊 Performance Monitoring**: Track latency, token usage, and TTFT
3. **🎯 Session Tracking**: Follow multi-turn conversations
4. **👤 User Analytics**: Understand per-persona usage patterns
5. **🐛 Debugging**: Troubleshoot issues with full context
6. **📈 Quality Metrics**: Evaluate retrieval quality and response accuracy

## What We Track

### Traced Operations

| Operation | What's Captured | Use Case |
|-----------|----------------|----------|
| **RAG Retrieval** | Query, retrieved chunks, similarity scores | Optimize retrieval quality |
| **Streaming Chat** | Full response, token-by-token, TTFT | Monitor streaming performance |
| **Non-Streaming Chat** | Complete response, citations, timing | Batch operation analysis |

### Metadata Captured

```json
{
  "user_id": "persona-uuid",
  "session_id": "session-token",
  "tags": ["llama_rag", "stream", "persona:xxx", "session:yyy"],
  "token_count": 247,
  "total_time_seconds": 3.456,
  "first_token_time_seconds": 0.234,
  "retrieval_time_seconds": 0.123,
  "response_length": 543,
  "source_nodes_count": 3
}
```

## Quick Start

### Prerequisites

```bash
# 1. Get Langfuse credentials
# Sign up at https://cloud.langfuse.com
# Or self-host: https://langfuse.com/docs/deployment

# 2. Add to .env
LANGFUSE_PUBLIC_KEY=pk_your_key
LANGFUSE_SECRET_KEY=sk_your_key
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Viewing Traces

1. Go to [Langfuse Dashboard](https://cloud.langfuse.com)
2. Navigate to "Traces"
3. Filter by:
   - `metadata.user_id` - See all traces for a persona
   - `metadata.session_id` - See all traces in a session
   - `metadata.tags` - Filter by operation type

## Features

### 1. Session Continuity

**Track entire conversations**:
```
Session: session-abc-123
├─ Message 1: "What are your skills?"
│  └─ Trace: llama_rag_stream (2.3s, 150 tokens)
├─ Message 2: "Tell me more about Python"
│  └─ Trace: llama_rag_stream (1.8s, 200 tokens)
└─ Message 3: "What projects have you worked on?"
   └─ Trace: llama_rag_stream (3.1s, 300 tokens)
```

**Dashboard Query**:
```
metadata.session_id = "session-abc-123"
```

### 2. Persona Analytics

**Track per-persona usage**:
- Total queries
- Average response time
- Token usage
- Most common topics (via embeddings)
- Peak usage times

**Dashboard Query**:
```
metadata.user_id = "550e8400-e29b-41d4-a716-446655440000"
```

### 3. Performance Monitoring

**Track key metrics**:
- **TTFT** (Time To First Token): User-perceived latency
- **Total Latency**: End-to-end response time
- **Token Rate**: Tokens per second
- **Retrieval Time**: RAG context fetch time

**Dashboard Query**:
```
metadata.total_time_seconds > 5.0  // Slow queries
metadata.first_token_time_seconds > 1.0  // Slow TTFT
```

### 4. RAG Quality Analysis

**Analyze retrieval quality**:
- View retrieved chunks for each query
- See similarity scores
- Identify when RAG context is irrelevant
- Compare responses with/without good context

**Example Trace**:
```json
{
  "input": {"query": "What are your Python skills?"},
  "output": {
    "full_response": "I have 10 years of Python experience...",
    "retrieved_nodes": [
      {
        "content": "Worked with Python at Google for 5 years...",
        "score": 0.89
      },
      {
        "content": "Built ML pipeline with Python...",
        "score": 0.76
      }
    ]
  }
}
```

### 5. Debugging

**Full context for troubleshooting**:
- Input query
- Retrieved context
- Generated response
- Timing breakdown
- Error messages (if any)

**Use Case**: User reports poor response quality
1. Find trace by session_id
2. Review retrieved_nodes
3. Check similarity scores
4. Identify root cause (poor retrieval vs poor generation)

## Dashboard Examples

### Example 1: Monitor Production Performance

**Goal**: Track all queries in production

**Filter**:
```
metadata.tags contains "llama_rag"
AND metadata.environment = "production"
```

**Metrics to Watch**:
- P95 latency
- Average token count
- Error rate

### Example 2: Analyze Specific Session

**Goal**: Debug user-reported issue

**Filter**:
```
metadata.session_id = "user-reported-session-id"
```

**What to Check**:
- Query sequence
- Retrieved context quality
- Response relevance
- Any error spans

### Example 3: Compare Persona Performance

**Goal**: See which personas are most used

**Filter**:
```
metadata.tags contains "llama_rag"
GROUP BY metadata.user_id
```

**Metrics**:
- Query count per persona
- Average latency per persona
- Token usage per persona

### Example 4: Find Slow Queries

**Goal**: Optimize performance

**Filter**:
```
metadata.total_time_seconds > 5.0
ORDER BY metadata.total_time_seconds DESC
```

**Analysis**:
- Why were these slow?
- Large retrieved context?
- Long response generation?
- Network issues?

## Advanced Features

### A/B Testing

**Coming Soon**: Test different prompts/models
```python
# Track which variant performed better
metadata = {
    "variant": "prompt_v2",
    "experiment_id": "prompt-test-001"
}
```

### Cost Tracking

**Coming Soon**: Monitor API costs
```python
span.update(
    cost_details={
        "total_cost": 0.0023,
        "prompt_tokens_cost": 0.0003,
        "completion_tokens_cost": 0.0020
    }
)
```

### User Feedback

**Coming Soon**: Link user ratings to traces
```python
# User gives thumbs up
client.score(
    trace_id=trace_id,
    name="user_rating",
    value=1.0,  # 1.0 = positive, 0.0 = negative
)
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LANGFUSE_PUBLIC_KEY` | Yes | - | Your public API key |
| `LANGFUSE_SECRET_KEY` | Yes | - | Your secret API key |
| `LANGFUSE_HOST` | No | `https://cloud.langfuse.com` | Langfuse server URL |

### Optional Settings

```python
# In shared/rag/llama_rag.py
client = Langfuse(
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
    host=settings.langfuse_host,
    flush_at=512,  # Batch size (default: 512)
    flush_interval=5.0,  # Flush every 5s (default: 5.0)
    debug=False,  # Enable debug logging
)
```

## Privacy & Security

### What Gets Sent

- ✅ **Metadata**: User IDs, session IDs, timing metrics
- ✅ **Queries**: User questions (for debugging)
- ✅ **Responses**: AI-generated answers
- ✅ **Context**: Retrieved RAG chunks
- ❌ **Credentials**: Never sent
- ❌ **API Keys**: Never sent

### Data Retention

- **Langfuse Cloud**: 30 days (free tier), longer for paid plans
- **Self-Hosted**: You control retention

### Compliance

- **GDPR**: User IDs can be pseudonymized
- **Data Location**: EU or US regions available
- **Self-Hosting**: Full data control

## Troubleshooting

### Traces Not Appearing

**Check**:
1. Credentials set in `.env`
2. Network access to Langfuse host
3. Look for "Flushed X spans" in logs
4. Check Langfuse status page

**Debug**:
```python
from langfuse import Langfuse
client = Langfuse()
# Should not raise authentication error
client.flush()
```

### Missing session_id

**Check**:
1. Session token in API request
2. Passed to ResponseGenerator
3. Added to context dictionary
4. Extracted in LlamaRAG

**Debug**:
```python
# Add logging
logger.info(f"Session ID: {context.get('session_id')}")
```

### High Latency

**Possible causes**:
- Flush blocking (should be async)
- Large payloads (truncate if needed)
- Network issues (check Langfuse host)

**Solutions**:
- Increase `flush_at` (batch size)
- Decrease `flush_interval`
- Use async flushing (default)

## Best Practices

### 1. Consistent Naming

```python
# ✅ Good: Descriptive, consistent
name = f"llama_rag_stream.{persona_id}.{date}"

# ❌ Bad: Generic, not filterable
name = "chat"
```

### 2. Rich Metadata

```python
# ✅ Good: Includes context
metadata = {
    "user_id": str(persona_id),
    "session_id": session_id,
    "tags": ["operation", "type", "identifiers"],
    "custom_field": "value"
}

# ❌ Bad: Minimal info
metadata = {"tags": ["chat"]}
```

### 3. Always Flush

```python
# ✅ Good: Ensures data sent
try:
    # Do work
    span.update(output={...})
finally:
    span.end()
    client.flush()  # ← Important!
```

### 4. Handle Errors Gracefully

```python
# ✅ Good: Application continues
try:
    span = client.start_span(...)
except Exception as e:
    logger.warning(f"Langfuse error: {e}")
    span = None  # Continue without tracing
```

## Resources

### Documentation

- [Quick Reference](./LANGFUSE_QUICK_REFERENCE.md) - API guide
- [LlamaRAG Integration](./LANGFUSE_LLAMARAG_INTEGRATION.md) - Implementation details
- [Implementation Summary](./LANGFUSE_IMPLEMENTATION_SUMMARY.md) - Architecture overview

### External Links

- [Langfuse Website](https://langfuse.com)
- [Langfuse Docs](https://langfuse.com/docs)
- [Python SDK](https://langfuse.com/docs/sdk/python)
- [Self-Hosting Guide](https://langfuse.com/docs/deployment)

## FAQ

### Q: Does Langfuse slow down my app?

**A**: Overhead is ~10-20ms per request (<1% of total latency). Flushing is async and non-blocking.

### Q: Can I filter by custom fields?

**A**: Yes! Add any JSON-serializable data to `metadata` and filter by it in the dashboard.

### Q: How do I track multi-turn conversations?

**A**: Use the same `session_id` for all messages in a conversation.

### Q: Can I disable Langfuse temporarily?

**A**: Yes! Remove credentials from `.env` or set `LANGFUSE_TRACING_ENABLED=false`.

### Q: How do I self-host Langfuse?

**A**: Follow the [self-hosting guide](https://langfuse.com/docs/deployment/self-host). Then set `LANGFUSE_HOST` to your server URL.

### Q: Can I export data from Langfuse?

**A**: Yes! Use the API or dashboard to export traces as JSON/CSV.

---

**Status**: ✅ Production Ready  
**SDK Version**: Langfuse 3.9.2  
**Last Updated**: November 14, 2025

