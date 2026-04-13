# Persona System Architecture

## System Overview

The persona system creates authentic digital clones by analyzing communication patterns, thinking styles, and knowledge from user content. It uses PostgreSQL with pgvector for efficient semantic search and GPT-4 for response generation.

---

## High-Level Architecture

```plaintext
┌─────────────────────────────────────────────────────────────┐
│                        Client Layer                         │
│                   (Web App / API Clients)                   │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                         API Layer                           │
│                    (FastAPI + WebSocket)                    │
├─────────────────────────────────────────────────────────────┤
│  • Authentication           • Rate Limiting                 │
│  • Request Validation       • Response Formatting           │
│  • Error Handling           • Logging                       │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                       │
├──────────────┬──────────────┬──────────────┬───────────────┤
│  Ingestion   │   Pattern    │  Generation  │   Retrieval   │
│   Service    │  Extraction  │   Service    │    Service    │
├──────────────┼──────────────┼──────────────┼───────────────┤
│ • File       │ • Style      │ • Prompt     │ • Vector      │
│   Processing │   Analysis   │   Building   │   Search      │
│ • Chunking   │ • Thinking   │ • LLM Calls  │ • Reranking   │
│ • Metadata   │   Patterns   │ • Style      │ • Filtering   │
│              │ • Expertise  │   Enforce    │               │
└──────────────┴──────────────┴──────────────┴───────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                        Data Layer                           │
├─────────────────────────┬───────────────────────────────────┤
│     PostgreSQL          │         External APIs            │
│    with pgvector        │                                  │
├─────────────────────────┼───────────────────────────────────┤
│ • Personas              │ • OpenAI (Embeddings & GPT-4)    │
│ • Content Chunks        │ • Transcription Services         │
│ • Embeddings            │ • Content Sources                │
│ • Patterns              │                                  │
│ • Conversations         │                                  │
└─────────────────────────┴───────────────────────────────────┘
```

---

## Component Details

### 1. Ingestion Pipeline

Raw Content → Processor → Chunker → Pattern Extractor → Storage

- Accept multiple file formats
- Extract and clean text
- Chunk intelligently
- Extract patterns
- Generate embeddings
- Store in database

### 2. Pattern Extraction System

Content → NLP Analysis → Pattern Detection → Pattern Storage

- Communication Style (vocabulary, sentence structure)
- Thinking Patterns (problem-solving approach)
- Response Patterns (structure, examples)
- Personality Markers (tone, energy)

### 3. Retrieval System (RAG)

Query → Embedding → Vector Search → Reranking → Context

- Generate query embedding
- Semantic similarity search
- Apply metadata filters
- Rerank by relevance
- Diversify results

### 4. Generation System

Context + Patterns + Query → Prompt → LLM → Style Enforcement → Response

- Classify query type
- Retrieve relevant context
- Build persona-specific prompt
- Generate with GPT-4
- Enforce style consistency
- Validate response

---

## Database Schema

### Personas Table

```sql
CREATE TABLE personas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    role VARCHAR(255),
    company VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Content Chunks Table

```sql
CREATE TABLE content_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id UUID REFERENCES personas(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB,
    source VARCHAR(255),
    chunk_index INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Indexes for performance
    INDEX idx_embedding USING ivfflat (embedding vector_cosine_ops),
    INDEX idx_persona (persona_id),
    INDEX idx_metadata (metadata)
);
```

### Patterns Table

```sql
CREATE TABLE patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id UUID REFERENCES personas(id) ON DELETE CASCADE,
    pattern_type VARCHAR(50), -- 'style', 'thinking', 'response'
    pattern_data JSONB NOT NULL,
    confidence FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_persona_pattern (persona_id, pattern_type)
);
```

### Conversations Table

```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id UUID REFERENCES personas(id) ON DELETE CASCADE,
    messages JSONB NOT NULL, -- Array of {role, content, timestamp}
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_persona_conv (persona_id),
    INDEX idx_updated (updated_at DESC)
);
```

---

## Data Flow

### Creating a Persona

1. User uploads content files
2. System processes and chunks text
3. Extracts communication patterns
4. Generates embeddings for chunks
5. Stores in PostgreSQL
6. Returns persona ID

### Chatting with Persona

1. User sends message
2. System generates query embedding
3. Searches for relevant content
4. Retrieves patterns and context
5. Builds persona-specific prompt
6. Generates response with GPT-4
7. Applies style enforcement
8. Returns response
9. Stores in conversation history

### Updating Persona

1. User uploads new content
2. System processes new content
3. Updates pattern analysis
4. Adds new chunks to database
5. Recomputes embeddings
6. Merges with existing data

---

## Technology Stack

**Backend**

- Framework: FastAPI (async, fast, modern)
- Database: PostgreSQL 15+ with pgvector
- ORM: SQLAlchemy 2.0 (async)
- Validation: Pydantic v2

**ML/AI**

- LLM: OpenAI GPT-4
- Embeddings: OpenAI text-embedding-3-small
- NLP: spaCy, NLTK
- Vector Ops: pgvector

**Infrastructure**

- Container: Docker + Docker Compose
- Queue: Celery + Redis (for async processing)
- Cache: Redis
- Monitoring: Prometheus + Grafana

**Development**

- Testing: pytest + pytest-asyncio
- Linting: ruff, black, mypy
- Docs: OpenAPI/Swagger

---

## Performance Considerations

**Optimization Strategies**

- Embedding Cache: Cache frequently used embeddings
- Connection Pooling: PostgreSQL connection pool
- Batch Processing: Batch embedding requests
- Async Operations: Async database queries
- Index Optimization: Proper indexes on vectors and metadata

**Scalability**

- Horizontal scaling with load balancer
- Read replicas for PostgreSQL
- Distributed vector index (IVFFlat)
- CDN for static content
- Queue for heavy processing

**Expected Performance**

- Ingestion: 100 documents/minute
- Pattern extraction: 10 documents/minute
- Chat response: < 3 seconds
- Vector search: < 200ms
- Concurrent users: 100+

---

## Security Considerations

**Data Protection**

- Encryption at rest (PostgreSQL)
- Encryption in transit (HTTPS)
- API key authentication
- Rate limiting per user
- Input sanitization

**Privacy**

- User data isolation
- Soft deletes for audit trail
- GDPR compliance ready
- Data retention policies

---

## Monitoring & Logging

**Metrics**

- Response times
- Token usage
- Error rates
- Pattern extraction quality
- User engagement

**Logging**

- Structured logging (JSON)
- Request/response logging
- Error tracking
- Performance profiling

---

## Deployment

**Local Development**

```bash
docker-compose up -d  # PostgreSQL + pgvector + Redis
python -m venv venv
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Production**

```bash
# Using Docker
docker build -t persona-system .
docker run -p 8000:8000 persona-system

# Or using PM2
pm2 start "uvicorn app.main:app" --name persona-api
```

---

## API Examples

**Create Persona**

```http
POST /personas
Content-Type: multipart/form-data

{
  "name": "John Doe",
  "role": "VP of Engineering",
  "files": [uploaded_files]
}
```

**Chat with Persona**

```http
POST /personas/{id}/chat
Content-Type: application/json

{
  "message": "How do you approach building scalable systems?"
}
```

**Get Patterns**

```http
GET /personas/{id}/patterns

Response:
{
  "style": {
    "sentence_length": 12.5,
    "vocabulary_complexity": "high",
    "common_phrases": ["let's dive into", "the key here is"]
  },
  "thinking": {
    "approach": "systematic",
    "evidence_style": "data_driven"
  }
}
```

---

---

## LiveKit Voice Agent Architecture (NEW - Modular Design)

### Architecture Overview

The voice agent has been **refactored into a modular architecture** (Jan 2026), reducing code from 2,921 lines to 561 lines (-81%).

```plaintext
┌─────────────────────────────────────────────────────────────┐
│                   LiveKit Orchestrator                      │
│              (app/services/livekit_orchestrator.py)         │
├─────────────────────────────────────────────────────────────┤
│  • Worker Lifecycle Management                              │
│  • Health Monitoring                                        │
│  • Dispatch Coordination                                    │
│  • Agent Version Selection (modular/legacy)                 │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│              Modular Persona Agent (561 lines)              │
│                  (livekit/livekit_agent.py)                 │
├─────────────────────────────────────────────────────────────┤
│  • LLM Orchestration (system prompt, history, RAG)          │
│  • Voice/Text Mode Support (unified pipeline)               │
│  • Handler Composition (delegates to specialized handlers)  │
└─────────────────────────────────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ WorkflowHandler  │  │   ToolHandler    │  │ SessionContext   │
│   (357 lines)    │  │   (173 lines)    │  │   (42 lines)     │
├──────────────────┤  ├──────────────────┤  ├──────────────────┤
│ • Linear         │  │ • Internet       │  │ • Conversation   │
│   Workflows      │  │   Search         │  │   History        │
│ • Conversational │  │ • URL Fetching   │  │ • Turn Tracking  │
│   Workflows      │  │ • Calendar       │  │ • User Messages  │
│ • Field          │  │   Links          │  │   Count          │
│   Extraction     │  │                  │  │                  │
│ • Completion     │  │                  │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│        Conversational Workflow Services (896 lines)         │
├──────────────────┬──────────────────┬───────────────────────┤
│ FieldExtractor   │ ScoringEngine    │ WorkflowCoordinator   │
│  (319 lines)     │  (281 lines)     │    (296 lines)        │
├──────────────────┼──────────────────┼───────────────────────┤
│ • LLM-based      │ • Base Score     │ • Lifecycle           │
│   Extraction     │ • Completeness   │   Management          │
│ • Confidence     │ • Quality        │ • Confirmation Flow   │
│   Tracking       │   Signals        │ • Field Updates       │
│ • Correction     │ • Risk           │ • Session Tracking    │
│   Detection      │   Penalties      │                       │
│ • Field Merge    │ • Priority       │                       │
└──────────────────┴──────────────────┴───────────────────────┘
```

### Key Architecture Principles

**1. Composition Pattern**
- Main agent delegates to specialized handlers
- Each handler has single responsibility
- Easy to test independently
- Easy to extend with new handlers

**2. Modular Design**
```python
# Main Agent (livekit_agent.py)
class ModularPersonaAgent(Agent):
    def __init__(self, ...):
        # Initialize handlers
        self.workflow_handler = WorkflowHandler(...)
        self.tool_handler = ToolHandler(...)
        self.session_context = SessionContext(...)

    @function_tool
    async def start_assessment(self):
        # Delegate to handler (5 lines vs 130 lines)
        return await self.workflow_handler.start_workflow()
```

**3. Clean Separation of Concerns**

| Component | Responsibility | Lines |
|-----------|---------------|-------|
| **Main Agent** | LLM orchestration, pipeline management | 561 |
| **WorkflowHandler** | All workflow logic (linear + conversational) | 357 |
| **ToolHandler** | Function tools (search, fetch, calendar) | 173 |
| **SessionContext** | Conversation tracking | 42 |
| **FieldExtractor** | LLM-based field extraction | 319 |
| **ScoringEngine** | Lead scoring algorithm | 281 |
| **Coordinator** | Workflow lifecycle orchestration | 296 |

### Agent Switching

The orchestrator supports **instant switching** between agent versions:

```bash
# Environment variable (default: modular)
export LIVEKIT_AGENT_VERSION=modular  # New refactored agent
export LIVEKIT_AGENT_VERSION=legacy   # Old monolithic agent (fallback)
```

**Benefits of Modular Architecture:**
- ✅ 81% code reduction (2,921 → 561 lines)
- ✅ Easier maintenance and testing
- ✅ Better code organization
- ✅ Faster development of new features
- ✅ Same functionality as legacy agent
- ✅ Instant rollback available

**See also:**
- `docs/LIVEKIT_REFACTORING.md` - Complete refactoring details
- `docs/workflows/AGENT_SWITCHING_GUIDE.md` - How to switch agents
- `docs/workflows/REFACTORING_REVIEW.md` - Thorough code review

---

## Future Enhancements

**Phase 2**

- ✅ Voice synthesis integration (DONE - LiveKit)
- ✅ Multi-language support (DONE - 10+ languages)
- Fine-tuning capabilities
- Advanced pattern detection

**Phase 3**

- Video avatar generation
- Real-time learning
- Collaborative personas
- API marketplace

---

# Architecture Diagram

```mermaid
flowchart TD
    A[Client Layer<br/>(Web App / API Clients)]
    B[API Layer<br/>(FastAPI + WebSocket)]
    C[Application Layer]
    D[Ingestion Service]
    E[Pattern Extraction]
    F[Generation Service]
    G[Retrieval Service]
    H[Data Layer<br/>(PostgreSQL + pgvector)]
    I[External APIs<br/>(OpenAI, Transcription)]

    A --> B
    B --> C
    C --> D
    C --> E
    C --> F
    C --> G
    D --> H
    E --> H
    F --> I
    G --> H
    H --> G
    F --> B
    G --> F
    I --> F
```

---

# Theory & Concepts Document

```markdown
# Theoretical Foundation for Persona System

## Core Concept: Digital Persona Modeling

### What We're Building

We're creating a system that captures not just WHAT someone knows, but HOW they think and communicate. This requires understanding:

1. **Cognitive Patterns**: How they approach problems
2. **Communication Style**: How they express ideas
3. **Knowledge Domains**: What they know about
4. **Personality Markers**: Their unique traits

## Key Technologies Explained

### 1. Embeddings & Vector Search

**What are embeddings?**
Embeddings convert text into numerical vectors that capture semantic meaning. Similar concepts have vectors that are close together in high-dimensional space.

**Why pgvector?**

- Native PostgreSQL integration
- SQL + vector search in one query
- No external dependencies
- Cost-effective at scale

**How it works:**
"How do you scale?" → [0.23, -0.45, 0.67, ...] (1536 dimensions)
↓
Compare with stored vectors
↓
Find semantically similar content

### 2. RAG (Retrieval Augmented Generation)

**The Problem:**
LLMs have general knowledge but don't know specific person's content.

**The Solution:**

1. Store person's content in searchable format
2. Retrieve relevant content for each query
3. Include context in prompt to LLM
4. Generate response based on retrieved context

**Why it works:**

- Grounds responses in actual content
- Reduces hallucination
- Maintains accuracy
- Allows updates without retraining

### 3. Pattern Extraction

**Communication Patterns:**

- Sentence structure (short vs complex)
- Vocabulary choices (formal vs casual)
- Emotional tone (enthusiastic vs measured)
- Transition words (how they connect ideas)

**Thinking Patterns:**

- Top-down (start with big picture)
- Bottom-up (start with details)
- Framework-based (use mental models)
- Narrative (tell stories)

**Why patterns matter:**
Patterns make responses authentic. Without them, all personas sound like generic ChatGPT.

### 4. Prompt Engineering for Personas

**Prompt Structure:**
System Context → Persona Identity → Patterns → Retrieved Content → Query → Instructions

**Key Elements:**

1. **Identity**: Who they are, role, company
2. **Patterns**: How they think and communicate
3. **Context**: Relevant past content
4. **Constraints**: What to avoid
5. **Examples**: Sample responses

## Implementation Strategies

### 1. Chunking Strategy

**Why chunk?**

- LLMs have token limits
- Better retrieval precision
- Maintains context

**Smart Chunking:**
Original Text (10,000 words)
↓
Chunk 1 (500 words + 100 overlap)
Chunk 2 (500 words + 100 overlap)
Chunk 3 (500 words + 100 overlap)

### 2. Hybrid Search

**Combine three approaches:**

1. **Semantic Search**: Find conceptually similar
2. **Keyword Search**: Find exact matches
3. **Metadata Filtering**: Filter by source, date

**Formula:**
Score = α(semantic_score) + β(keyword_score) + γ(metadata_boost)

### 3. Style Enforcement

**Techniques:**

1. **Template Matching**: Use their sentence structures
2. **Phrase Injection**: Include signature phrases
3. **Tone Adjustment**: Match emotional patterns
4. **Length Matching**: Similar response lengths

### 4. Consistency Maintenance

**Challenge:**
Maintaining consistent personality across conversations.

**Solution:**

- Store conversation history
- Track persona evolution
- Validate responses against patterns
- Use feedback loops

## Quality Metrics

### 1. Authenticity Score

Authenticity = (Style Match + Pattern Match + Knowledge Accuracy) / 3

### 2. Consistency Score

Consistency = 1 - (Variance in Responses to Similar Questions)

### 3. Engagement Score

Engagement = (Response Relevance + Conversation Flow + User Satisfaction)

## Challenges & Solutions

### Challenge 1: Limited Data

**Solution**: Few-shot learning with pattern amplification

### Challenge 2: Maintaining Voice

**Solution**: Strong pattern enforcement in post-processing

### Challenge 3: Avoiding Hallucination

**Solution**: Strict RAG with fact-checking layer

### Challenge 4: Response Speed

**Solution**: Caching, async operations, optimized queries

## Ethical Considerations

### 1. Consent

- Only create personas with explicit permission
- Clear data usage policies
- Right to deletion

### 2. Authenticity

- Clear disclosure that it's AI
- No impersonation for harm
- Transparency about limitations

### 3. Privacy

- Secure data storage
- No sharing without permission
- Anonymization options

## Success Factors

### What Makes Great Personas

1. **Rich Data Sources**

   - Minimum 10 hours of content
   - Diverse contexts
   - Recent material

2. **Strong Patterns**

   - Clear communication style
   - Consistent thinking approach
   - Distinctive personality

3. **Accurate Retrieval**

   - High-quality embeddings
   - Smart chunking
   - Good reranking

4. **Sophisticated Prompting**
   - Detailed instructions
   - Pattern enforcement
   - Context integration

## Mathematical Foundation

### Vector Similarity

Cosine Similarity = (A · B) / (||A|| × ||B||)
Where:

A, B are embedding vectors
Result ranges from -1 to 1
Higher = more similar

### Pattern Matching

Pattern Score = Σ(weight_i × feature_match_i)
Features:

Sentence length similarity
Vocabulary overlap
Style markers present

### Relevance Scoring

Relevance = semantic_similarity × recency_factor × source_weight

## Future Directions

### Near Term

- Multi-modal personas (text + voice)
- Real-time learning from interactions
- Collaborative personas

### Long Term

- Video avatars
- Emotional intelligence
- Creative generation in their style
- Autonomous agents

## Conclusion

Building authentic digital personas requires:

1. Understanding patterns beyond content
2. Sophisticated retrieval and generation
3. Careful attention to consistency
4. Continuous improvement from feedback

The key insight: Personas are more about HOW someone thinks than WHAT they know.

This comprehensive guide gives you everything needed to build a Delphi-like system with PostgreSQL vector storage.
```
