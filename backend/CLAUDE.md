# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Repository Overview

MyClone is an AI-powered digital persona platform built with FastAPI, LlamaIndex RAG, and LiveKit for voice interactions. Users create AI personas from uploaded documents, PDFs, and YouTube content, then interact with them via voice or text conversations powered by retrieval-augmented generation.

**Core capabilities:**
- Voice agent (LiveKit + Deepgram STT + ElevenLabs/Cartesia TTS)
- Conversational and linear workflows
- RAG-powered knowledge retrieval (LlamaIndex + pgvector)
- Document/PDF/YouTube ingestion pipeline
- Real-time text chat

---

## Development Commands

### Local Development (uv)

```bash
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Docker Development (Recommended)

```bash
make setup-local     # First time: build, start, migrate
make up              # Start services with logs
make up-local        # Start with LocalStack (S3)
make down            # Stop all
make restart         # Restart services
make logs            # View logs
make logs-api        # API logs only
make logs-voice      # Voice worker logs
```

### Database Migrations (Alembic)

```bash
make migrate                          # Apply migrations
make migrate-create MSG="description" # Create new migration
make migrate-rollback                 # Rollback one
make migrate-status                   # Show current state
```

### Code Quality

```bash
make check     # Auto-fix: isort + black + ruff
make lint      # Check only
make lint-fix  # Check + fix
```

---

## Architecture

### System Flow

**Ingestion → Embedding → Runtime**

1. **Ingestion**: Documents, PDFs, YouTube videos are processed into text chunks
2. **Embedding**: LlamaIndex creates vector embeddings stored in PostgreSQL + pgvector
3. **Runtime**: Voice/text conversations use cached system prompts + dynamic RAG retrieval

### Key Services

| Service | Purpose |
|---------|---------|
| `app/` | FastAPI API — auth, personas, conversations, documents, workflows |
| `livekit/` | Voice agent — LiveKit integration, handlers, managers |
| `workers/voice_processing/` | Background worker — audio/video/PDF processing, transcription |
| `shared/rag/` | RAG system — LlamaIndex, pgvector, context retrieval |
| `shared/generation/` | Prompt generation — system prompts, context pipeline, reranking |
| `shared/database/` | Database layer — SQLAlchemy models, repositories |

### Data Flow

```
User uploads document/PDF/YouTube → Voice Processing Worker
  → Transcription (AssemblyAI/Deepgram)
  → Text chunking
  → LlamaIndex embedding (pgvector)
  → PersonaDataSource linking

User starts voice call → LiveKit Agent
  → Deepgram STT → text query
  → RAG retrieval (persona-filtered embeddings)
  → LLM generation (OpenAI)
  → ElevenLabs/Cartesia TTS → audio response
```

### Workflow System

Two workflow types:
- **Linear**: Step-by-step assessment with defined fields
- **Conversational**: Natural dialogue with field extraction and lead scoring

Key files:
- `livekit/handlers/workflow/linear_handler.py`
- `livekit/handlers/workflow/conversational_handler.py`
- `app/api/workflow_routes.py`

---

## Database Schema

**Core Tables:**
- `users` — User accounts
- `personas` — AI persona profiles
- `persona_data_sources` — Maps personas to knowledge sources
- `documents` — Uploaded documents
- `youtube_videos` — YouTube video metadata
- `data_llamaindex_embeddings` — Vector embeddings (pgvector)
- `conversations` — Chat session records
- `voice_sessions` — Voice call metadata
- `workflow_sessions` — Workflow execution tracking
- `persona_prompts` — Generated system prompts

**Auth Tables:**
- `auth_details` — Email/password credentials
- `user_sessions` — Session tracking
- `widget_tokens` — Widget authentication

---

## Key File Locations

| Component | Path |
|-----------|------|
| Main app entry | `app/main.py` |
| Settings/config | `shared/config.py` |
| RAG system | `shared/rag/llama_rag.py` |
| RAG singleton | `shared/rag/rag_singleton.py` |
| Prompt generation | `shared/generation/prompts.py` |
| Context pipeline | `shared/generation/context_pipeline.py` |
| LiveKit voice agent | `livekit/livekit_agent.py` |
| Prompt manager | `livekit/managers/prompt_manager.py` |
| Database models | `shared/database/models/` |
| Repositories | `shared/database/repositories/` |
| Migration files | `alembic/versions/` |
| Voice processing worker | `workers/voice_processing/worker.py` |

---

## Development Guidelines

### Error Handling

All exception handlers MUST include Sentry monitoring:
```python
from shared.monitoring.sentry_utils import capture_exception_with_context

capture_exception_with_context(
    e,
    extra={"user_id": str(user_id)},
    tags={
        "component": "feature_name",
        "operation": "operation_name",
        "severity": "low|medium|high",
        "user_facing": "true|false",
    },
)
```

### Service Patterns

Use **instance methods** (preferred) for services with state:
```python
class MyService:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.some_key
```

Use **static methods** only for pure utility functions with no state.

### Git Commit Policy

**Never auto-commit.** Always show changes and ask for approval before committing.

### File Size Limits

Keep individual Python files under 500 lines. Split by responsibility if needed.
