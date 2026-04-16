# MyClone Backend

> FastAPI backend with LlamaIndex RAG, LiveKit voice agents, and async workers.

For project overview, setup prerequisites, and contributing guidelines, see the [root README](../README.md).

---

## Quick Start

### Docker (Recommended)

```bash
cp .env.example .env
# Edit .env with your API keys (OPENAI_API_KEY at minimum)

make setup-local    # Build, start, and run migrations

# Or manually:
docker-compose build
docker-compose up
docker-compose exec api alembic -c /app/alembic.ini upgrade head
```

### Local (uv)

> Requires a separate PostgreSQL instance (set `DATABASE_URL` in `.env`)

```bash
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

---

## Makefile Commands

```bash
# Services
make up              # Start core services (postgres, nats, api, scraping-consumer)
make up-all          # Start ALL services including voice workers
make down            # Stop all services
make restart         # Restart core services
make logs            # All service logs
make logs-api        # API logs only

# Database
make migrate                              # Run migrations
make migrate-create MSG="add user table"  # Create new migration
make migrate-status                       # Show current state
make migrate-rollback                     # Rollback last migration
make db-reset                             # Reset database (with confirmation)

# Code Quality
make check           # Auto-fix: isort + black + ruff
make lint            # Check only (no changes)
make format          # Format code (black + isort)

# Development
make shell           # Bash in API container
make shell-poetry    # Poetry shell in API container
make health          # Check API health endpoint
make clean           # Stop and remove containers
make clean-all       # Stop, remove containers AND volumes (deletes DB!)
make help            # Show all commands
```

---

## Configuration

### Required Environment Variables

```env
DATABASE_URL=postgresql+asyncpg://username:password@hostname:5432/database_name
OPENAI_API_KEY=your_openai_api_key
EXPERT_CLONE_API_KEY=your_secure_api_key
```

### Optional (Voice Features)

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
DEEPGRAM_API_KEY=your_deepgram_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_default_voice_id
```

### Tunable Settings

```env
HOST_PORT=8001
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
VECTOR_DIMENSION=512
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
```

See `.env.example` for the complete list.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/expert/{username}` | GET | Get expert profile |
| `/api/v1/ingestion/create-persona-with-data` | POST | Create persona with LinkedIn/website data |
| `/api/v1/enrichment/linkedin` | POST | Queue LinkedIn enrichment job |
| `/api/v1/enrichment/twitter` | POST | Queue Twitter enrichment job |
| `/api/v1/enrichment/website` | POST | Queue website enrichment job |
| `/api/v1/ingestion/expert-status/{username}` | GET | Get creation status |
| `/api/v1/ingestion/expert-status-stream/{username}` | SSE | Stream creation status |
| `/api/v1/personas/username/{username}/init-session` | POST | Init anonymous chat session |
| `/api/v1/personas/username/{username}/stream-chat` | POST | Stream chat with persona |
| `/api/v1/sessions/{session_token}/status` | GET | Get session status |
| `/api/v1/sessions/{session_token}/provide-email` | POST | Associate email with session |
| `/api/v1/livekit/connection-details` | POST | Get LiveKit voice connection |
| `/api/v1/auth/register` | POST | Register (email/password) |
| `/api/v1/auth/login` | POST | Login |
| `/api/v1/auth/verify-email` | GET | Verify email address |
| `/api/v1/auth/forgot-password` | POST | Request password reset |
| `/api/v1/auth/reset-password` | POST | Reset password |

Interactive API docs available at `http://localhost:8001/docs` when running locally.

---

## Architecture

```
┌───────────────┐    ┌──────────────────┐    ┌───────────────┐
│   API Server  │    │ Scraping Consumer │    │Voice Processor│
│   (FastAPI)   │    │  (Background)     │    │ (Background)  │
│               │    │                   │    │               │
│ - REST API    │    │ - LinkedIn        │    │ - PDF Parser  │
│ - WebSocket   │    │ - Twitter         │    │ - Audio/Video │
│ - LiveKit     │    │ - Website Crawler │    │ - YouTube     │
└───────┬───────┘    └────────┬─────────┘    └───────┬───────┘
        │                     │                       │
        └─────────────────────┼───────────────────────┘
                              │
                  ┌───────────▼───────────┐
                  │   NATS JetStream      │
                  └───────────┬───────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
┌───────▼───────┐   ┌────────▼────────┐   ┌───────▼───────┐
│  PostgreSQL   │   │  Shared Codebase│   │  OpenAI API   │
│  + pgvector   │   │  - Models       │   │  - GPT-4o-mini│
│  - Personas   │   │  - RAG System   │   │  - Embeddings │
│  - Embeddings │   │  - Services     │   └───────────────┘
└───────────────┘   └─────────────────┘
```

### Key Design Decisions

- **Independent service deployment** — API, workers, and migrations deploy separately; workers only need `shared/`, not `app/`
- **Shared database** — Single PostgreSQL + pgvector for ACID guarantees and data consistency
- **Async processing via NATS** — API enqueues jobs, workers process them independently
- **Monorepo with clear boundaries** — `app/` (API), `shared/` (common), `workers/` (background)

---

## Database Management

### Alembic Commands

```bash
# Essential
poetry run alembic current                                      # Check version
poetry run alembic history --verbose                             # View history
poetry run alembic revision --autogenerate -m "description"      # Generate migration
poetry run alembic upgrade head                                  # Apply all
poetry run alembic downgrade -1                                  # Rollback one
poetry run alembic upgrade head --sql                            # Preview SQL

# Docker
docker-compose exec api alembic upgrade head
docker-compose exec api alembic revision --autogenerate -m "description"
```

### Avoiding Migration Conflicts

```bash
git pull origin main
poetry run alembic current          # Verify you're on latest
poetry run alembic revision --autogenerate -m "add_feature"
poetry run alembic upgrade head     # Test upgrade
poetry run alembic downgrade -1     # Test rollback
poetry run alembic upgrade head     # Back to head
git add alembic/versions/ && git commit && git push
```

If you hit "multiple head revisions":

```bash
poetry run alembic merge -m "merge feature branches"
```

---

## Project Structure

```
backend/
├── app/                        # FastAPI application
│   ├── api/                    # Route handlers
│   ├── auth/                   # JWT auth & middleware
│   ├── ingestion/              # Document processing
│   ├── services/               # API-specific services
│   └── main.py                 # App entry point
├── shared/                     # Shared code (API + workers)
│   ├── database/               # Models, repositories, config
│   ├── rag/                    # LlamaIndex RAG system
│   ├── generation/             # Prompt generation & context
│   ├── scraping/               # Data scraping providers
│   ├── services/               # Shared business logic
│   ├── schemas/                # Pydantic models
│   └── config.py               # Global configuration
├── workers/                    # Background workers
│   ├── scraping_consumer/      # LinkedIn/Twitter/website scraping
│   └── voice_processing/       # PDF, audio, video processing
├── livekit/                    # Voice agent integration
├── alembic/                    # Database migrations
├── docker-compose.yml          # Local dev stack
├── Makefile                    # Dev commands
└── pyproject.toml              # Dependencies
```

---

## Troubleshooting

**Import errors after migration:**
```bash
ls -la shared/rag/ && ls -la shared/database/models/
docker-compose down && docker-compose up --build
```

**Hot reload not working:**
```bash
docker-compose down && docker-compose up
docker-compose exec api ls -la /app/.venv/
```

**Poetry virtual environment issues:**
```bash
rm -rf .venv/
poetry config virtualenvs.in-project true
poetry install
```

**Database connection issues:**
```bash
docker-compose ps
docker-compose logs postgres
docker-compose -f docker-compose.local.yml down -v
docker-compose -f docker-compose.local.yml up
```

---

## Documentation

- **[API Documentation](./docs/API_DOCUMENTATION.md)** — Complete API reference
- **[Email/Password Auth](./docs/EMAIL_PASSWORD_AUTH.md)** — Auth system details
- **[Code Quality Guide](./docs/CODE_QUALITY.md)** — Linting, formatting, CI/CD
- **[Persona Access Control](./docs/PERSONA_ACCESS_CONTROL.md)** — Private persona access
- **[Deployment Guide](./docs/VPS_DEPLOYMENT_UBUNTU.md)** — Production deployment
- **[Prompt Lifecycle](./docs/prompts/PROMPT_LIFECYCLE.md)** — How prompts work
- **[Stripe Payments](./docs/STRIPE_PAYMENT_ARCHITECTURE.md)** — Payment integration
