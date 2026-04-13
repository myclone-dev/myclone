# Langfuse Integration Documentation

Welcome to the Langfuse integration documentation for the Expert Clone system. This folder contains comprehensive guides for using Langfuse observability in our LLM application.

## 📚 Documentation Index

### Getting Started

1. **[Current Implementation](./LANGFUSE_CURRENT_IMPLEMENTATION.md)** ⭐ **Start Here (Nov 2025)**
   - Latest architecture and code structure
   - Score tracking system with tags
   - All evaluation endpoints
   - Usage examples and best practices
   - Migration notes from old implementation

2. **[Changelog](./CHANGELOG.md)** 🆕 **What's New**
   - Version 2.0.0 release notes (Nov 16, 2025)
   - All bug fixes and enhancements
   - Migration checklist
   - Breaking changes (none!)

3. **[Feature README](./LANGFUSE_FEATURE_README.md)**
   - What is Langfuse?
   - Why we use it
   - Quick start guide
   - Dashboard examples
   - FAQ

### Developer Guides

3. **[Quick Reference](./LANGFUSE_QUICK_REFERENCE.md)**
   - SDK API reference
   - Code examples
   - Common patterns
   - Troubleshooting

4. **[LlamaRAG Integration](./LANGFUSE_LLAMARAG_INTEGRATION.md)**
   - Complete implementation details
   - Function-by-function breakdown
   - Span structure
   - Filtering & queries
   - Migration guide

### Technical Documentation

5. **[Implementation Summary](./LANGFUSE_IMPLEMENTATION_SUMMARY.md)**
   - System architecture (historical)
   - Component responsibilities
   - Session ID flow
   - Performance metrics
   - Testing procedures

6. **[Prompt Evaluation](./LANGFUSE_PROMPT_EVALUATION.md)**
   - Prompt testing features
   - Evaluation metrics
   - A/B testing setup

## 🚀 Quick Links

### For Product Managers
- [What We Track](#what-we-track)
- [Dashboard Examples](./LANGFUSE_FEATURE_README.md#dashboard-examples)
- [Analytics Use Cases](./LANGFUSE_FEATURE_README.md#features)

### For Developers
- [API Reference](./LANGFUSE_QUICK_REFERENCE.md#span-api)
- [Code Examples](./LANGFUSE_QUICK_REFERENCE.md#code-examples)
- [Integration Details](./LANGFUSE_LLAMARAG_INTEGRATION.md#implementation-details)

### For DevOps
- [Configuration](./LANGFUSE_IMPLEMENTATION_SUMMARY.md#configuration)
- [Performance Impact](./LANGFUSE_IMPLEMENTATION_SUMMARY.md#performance-impact)
- [Troubleshooting](./LANGFUSE_QUICK_REFERENCE.md#troubleshooting)

## 📊 What We Track

### Operations Traced

| Operation | Function | Purpose |
|-----------|----------|---------|
| **RAG Retrieval** | `retrieve_context()` | Track context retrieval quality |
| **Streaming Chat** | `generate_response_stream()` | Monitor real-time responses |
| **Non-Streaming Chat** | `generate_response()` | Track batch responses |

### Metadata Collected

```json
{
  "user_id": "persona-uuid",           // Filter by persona
  "session_id": "session-token",       // Track conversations
  "tags": ["llama_rag", "stream"],     // Categorize operations
  "token_count": 247,                  // Response size
  "total_time_seconds": 3.456,         // Total latency
  "first_token_time_seconds": 0.234,   // TTFT (streaming)
  "retrieved_nodes": [...]             // RAG context
}
```

## 🎯 Common Use Cases

### Use Case 1: Debug Poor Response Quality

**Problem**: User reports irrelevant answer

**Solution**:
1. Filter by `metadata.session_id`
2. View trace for that query
3. Check `retrieved_nodes` - are they relevant?
4. Check similarity scores - are they too low?
5. Adjust retrieval threshold or re-index data

**Dashboard**: `metadata.session_id = "reported-session-id"`

### Use Case 2: Monitor Production Performance

**Problem**: Need to track system health

**Solution**:
1. Filter by `metadata.tags contains "llama_rag"`
2. View metrics:
   - P95 latency
   - Average TTFT
   - Error rate
3. Set alerts for anomalies

**Dashboard**: `metadata.total_time_seconds > 5.0`

### Use Case 3: Analyze User Engagement

**Problem**: Which personas are most used?

**Solution**:
1. Group by `metadata.user_id`
2. Count traces per persona
3. Analyze usage patterns
4. Identify popular features

**Dashboard**: Group by `metadata.user_id`, sort by count

### Use Case 4: Optimize Token Usage

**Problem**: Need to reduce API costs

**Solution**:
1. Filter by `metadata.token_count > 500`
2. Identify long responses
3. Analyze if length is necessary
4. Adjust max_tokens or prompts

**Dashboard**: `metadata.token_count > 500`

## 🔧 Configuration

### Environment Variables

Add to `.env`:
```bash
LANGFUSE_PUBLIC_KEY=pk_your_key_here
LANGFUSE_SECRET_KEY=sk_your_key_here
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Get Credentials

1. **Cloud**: Sign up at [langfuse.com](https://langfuse.com)
2. **Self-Hosted**: See [deployment docs](https://langfuse.com/docs/deployment)

## 📈 Dashboard Access

### Langfuse Cloud

1. Go to [cloud.langfuse.com](https://cloud.langfuse.com)
2. Navigate to "Traces"
3. Use filters to find specific traces

### Useful Filters

```
# All traces for a persona
metadata.user_id = "{persona_uuid}"

# All traces in a session
metadata.session_id = "{session_token}"

# All streaming operations
metadata.tags contains "stream"

# Slow queries (>5s)
metadata.total_time_seconds > 5.0

# Combined filters
metadata.user_id = "{uuid}" AND metadata.session_id = "{session}"
```

## 🏗️ Architecture

### Data Flow

```
User Request
    ↓
API Route (session_routes.py)
    ↓ session_token
ResponseGenerator (generator.py)
    ↓ context with session_id
LlamaRAGSystem (llama_rag.py)
    ↓ creates span
Langfuse Client
    ↓ sends data
Langfuse Dashboard
```

### Span Lifecycle

#### Streaming (Context Manager)
```python
with client.start_as_current_span(...) as span:
    # Stream tokens
    span.update(output={...})
    # Auto-ends on exit
client.flush()
```

#### Non-Streaming (Manual)
```python
span = client.start_span(...)
try:
    # Do work
    span.update(output={...})
finally:
    span.end()
    client.flush()
```

## 🐛 Troubleshooting

### Quick Diagnostics

```bash
# Check credentials
echo $LANGFUSE_PUBLIC_KEY
echo $LANGFUSE_SECRET_KEY

# Check logs for flush confirmation
grep "Langfuse: Flushed" logs/app.log

# Test connection
python test_langfuse_fix.py
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Traces not appearing | Check credentials, verify flush() called |
| Missing session_id | Ensure passed through API → Generator → RAG |
| Old API errors | Update to span-based API (v3.9.2) |
| High latency | Check batch size and flush interval |

See [Troubleshooting Guide](./LANGFUSE_QUICK_REFERENCE.md#troubleshooting) for details.

## 📖 Additional Resources

### Official Documentation
- [Langfuse Docs](https://langfuse.com/docs)
- [Python SDK](https://langfuse.com/docs/sdk/python)
- [OpenTelemetry Integration](https://langfuse.com/docs/integrations/opentelemetry)

### Internal Resources
- [RAG Implementation](../../shared/rag/llama_rag.py)
- [Response Generator](../../shared/generation/generator.py)
- [API Routes](../../app/api/session_routes.py)

## 🤝 Contributing

### Adding New Traces

1. Import Langfuse client
2. Create span with metadata
3. Update with output
4. End span and flush
5. Document in this folder

Example:
```python
span = self.langfuse_client.start_span(
    name="new_operation",
    input={...},
    metadata={
        "user_id": str(user_id),
        "session_id": session_id,
        "tags": ["operation_type"]
    }
)
try:
    result = do_work()
    span.update(output={"result": result})
finally:
    span.end()
    self.langfuse_client.flush()
```

## 📝 Changelog

### 2025-11-14
- ✅ Updated to Langfuse SDK v3.9.2
- ✅ Fixed span-based API (removed old `.trace()` method)
- ✅ Added user_id and session_id to metadata
- ✅ Updated all documentation
- ✅ Added comprehensive guides

### 2024-XX-XX
- Initial Langfuse integration
- Basic tracing for RAG operations

## 📞 Support

### Internal
- **Slack**: #eng-observability
- **Email**: dev-team@company.com
- **Issues**: GitHub Issues

### External
- **Langfuse Support**: support@langfuse.com
- **Community**: [Discord](https://discord.gg/langfuse)
- **GitHub**: [langfuse/langfuse](https://github.com/langfuse/langfuse)

---

## Summary

This documentation covers:
- ✅ Complete implementation guide
- ✅ API reference for SDK v3.9.2
- ✅ Architecture and data flow
- ✅ Dashboard usage examples
- ✅ Troubleshooting procedures
- ✅ Best practices

**Status**: Production Ready ✅  
**SDK Version**: Langfuse 3.9.2  
**Last Updated**: November 14, 2025

---

**Need help?** Start with the [Feature README](./LANGFUSE_FEATURE_README.md) or [Quick Reference](./LANGFUSE_QUICK_REFERENCE.md).

