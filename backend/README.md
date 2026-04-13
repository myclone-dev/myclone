# Expert Clone

> **Intelligent Digital Personas with LlamaIndex RAG System**
> Build AI-powered digital clones using modern RAG architecture with LlamaIndex, persistent memory, and real-time interactions.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-000000?style=flat&logo=llamaindex&logoColor=white)](https://www.llamaindex.ai/)

## 📑 Table of Contents

1. [🚀 Features](#-features)
2. [📋 Quick Start](#-quick-start)
3. [🛠 Configuration](#-configuration)
4. [🌐 API Endpoints](#-api-endpoints)
5. [🏗️ Architecture](#️-architecture)
6. [🔧 Development](#-development)
7. [💾 Database Management](#-database-management)
8. [📁 Project Structure](#-project-structure)
9. [🐳 Docker Configuration](#-docker-configuration)
10. [🔐 Security & Authentication](#-security--authentication)
11. [🚨 Troubleshooting](#-troubleshooting)
12. [📖 Documentation](#-documentation)
13. [🤝 Contributing](#-contributing)
14. [📄 License](#-license)
15. [🆘 Support](#-support)
16. [🎯 Roadmap](#-roadmap)

## 🚀 **Features**

- **🔍 LlamaIndex RAG**: Modern retrieval-augmented generation with vector search
- **🧠 Persistent Memory**: Conversations survive restarts using Letta Cloud integration
- **💬 Real-time Chat**: Server-Sent Events (SSE) and WebSocket support
- **🤖 Multi-Source Ingestion**: LinkedIn, Website, Twitter, Document processing
- **🎙️ Voice Integration**: LiveKit with persona-specific ElevenLabs voices
- **📊 Pattern Learning**: AI learns communication patterns from data
- **💳 Payment Integration**: Stripe-powered subscriptions and persona monetization
- **🐳 Docker Ready**: Complete containerized deployment with hot reload
- **🔒 Multi-Auth System**: OAuth (LinkedIn, Google) + Email/Password authentication
- **🛡️ Production Secure**: Email verification, account lockout, bcrypt hashing, JWT tokens

## 📋 **Quick Start**

### **Option 1: Docker Development (Recommended)**

```bash
# Clone repository
git clone https://github.com/myclone-dev/myclone.git
cd myclone/backend

# Setup environment variables
cp .env.example .env
# Edit .env with your API keys (OPENAI_API_KEY, etc.)

# Build and run complete local environment (API + Postgres + NATS + Workers)
docker-compose build
docker-compose up

# Run database migrations (required on first run)
docker-compose exec api alembic -c /app/alembic.ini upgrade head

# View logs
docker-compose logs -f api
```

### **Option 2: Local Poetry Development**

> **Note**: Requires separate database connection (use DATABASE_URL in .env)

```bash
# Use the development script (handles Poetry setup automatically)
./dev.sh

# Or manually:
poetry config virtualenvs.in-project true
poetry install
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## 🛠 **Configuration**

### **Required Environment Variables**

```env
# Database Configuration (External PostgreSQL for Production)
DATABASE_URL=postgresql+asyncpg://username:password@hostname:5432/database_name

# AI Service API Keys
OPENAI_API_KEY=your_openai_api_key_here

# Expert Clone Service Authentication
EXPERT_CLONE_API_KEY=your_secure_api_key_here
EXPERT_CLONE_REQUIRE_API_KEY=true  # Set to false to disable API key requirement

# Application Settings
HOST_PORT=8001  # Port for the backend service
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# Vector Database Settings
VECTOR_DIMENSION=512
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# LiveKit Cloud Configuration (Production)
LIVEKIT_URL=wss://expert-clone-gznr5li2.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
LIVEKIT_AGENT_NAME=expert_agent_rohan


# Voice Service API Keys (Required for LiveKit Voice Integration)
DEEPGRAM_API_KEY=your_deepgram_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here  # Required for TTS
ELEVENLABS_VOICE_ID=your_elevenlabs_voice_id_here  # Default voice (persona-specific voices override this)
```

### **Get API Keys**

1. **OpenAI API Key**: [OpenAI Platform](https://platform.openai.com/api-keys)
2. **LiveKit Keys**: [LiveKit Cloud](https://cloud.livekit.io/) (For voice features)
3. **Voice Service Keys**: [Deepgram](https://deepgram.com/), [ElevenLabs](https://elevenlabs.io/)

## 🌐 **API Endpoints**

### **Active Endpoints (Currently Used)**

| Endpoint                                            | Method  | Description                                |
| --------------------------------------------------- | ------- | ------------------------------------------ |
| `/api/v1/health`                                    | GET     | Health check                               |
| `/api/v1/expert/{username}`                         | GET     | Get expert profile by username             |
| `/api/v1/ingestion/create-persona-with-data`        | POST    | Create persona with LinkedIn/website data  |
| `/api/v1/enrichment/linkedin`                        | POST    | Enqueue LinkedIn enrichment job (async)    |
| `/api/v1/enrichment/twitter`                         | POST    | Enqueue Twitter enrichment job (async)     |
| `/api/v1/enrichment/website`                         | POST    | Enqueue website enrichment job (async)     |
| `/api/v1/ingestion/expert-status/{username}`        | GET     | Get expert creation status                 |
| `/api/v1/ingestion/expert-status-stream/{username}` | SSE     | Stream expert creation status              |
| `/api/v1/personas/username/{username}/init-session` | POST    | Initialize anonymous chat session          |
| `/api/v1/personas/username/{username}/stream-chat`  | POST    | Stream chat with persona                   |
| `/api/v1/sessions/{session_token}/status`           | GET     | Get session status                         |
| `/api/v1/sessions/{session_token}/provide-email`    | POST    | Associate email with session               |
| `/api/v1/livekit/connection-details`                | POST    | Get LiveKit connection for voice chat      |
| `/api/v1/auth/register`                             | POST    | Register with email and password           |
| `/api/v1/auth/login`                                | POST    | Login with email/username and password     |
| `/api/v1/auth/verify-email`                         | GET     | Verify email address                       |
| `/api/v1/auth/forgot-password`                      | POST    | Request password reset                     |
| `/api/v1/auth/reset-password`                       | POST    | Reset password with token                  |
| `/api/v1/auth/set-password`                         | POST    | OAuth user adds password (requires JWT)    |
| `/api/v1/migrations/*`                              | Various | Database migration management              |

### **Example: Create Persona with Data**

```bash
curl -X POST "http://localhost:8001/api/v1/ingestion/create-persona-with-data" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "username": "johndoe",
    "name": "John Doe",
    "linkedin_data": {
      "name": "John Doe",
      "headline": "Senior Software Engineer",
      "about": "Passionate about AI and software development...",
      "experience": [...],
      "posts": [...]
    },
    "website_data": {
      "url": "https://johndoe.com",
      "title": "John Doe - Portfolio",
      "content": "Welcome to my portfolio...",
      "blog_posts": [...]
    }
  }'
```

### **Example: Chat with Expert**

```bash
curl -X POST "http://localhost:8001/api/v1/personas/username/johndoe/stream-chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -d '{
    "message": "Tell me about your experience with AI",
    "session_token": "your-session-token",
    "temperature": 0.7
  }'
```

### **Voice Integration Features**

#### **Persona-Specific Voices**

Each persona can have their own unique ElevenLabs voice ID for voice conversations:

```json
{
  "username": "johndoe",
  "name": "John Doe",
  "voice_id": "21m00Tcm4TlvDq8ikWAM", // ElevenLabs voice ID
  "role": "Senior Software Engineer"
}
```

**Voice Fallback Logic:**

1. **Persona voice_id** (if set) → Uses persona's specific voice
2. **ELEVENLABS_VOICE_ID** (environment) → Uses default voice
3. **ElevenLabs default** → Uses system default

#### **LiveKit Voice Chat**

```bash
# Get LiveKit connection details for voice chat
curl -X POST "http://localhost:8001/api/v1/livekit/connection-details" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "persona_username": "johndoe"
  }'
```

## 🏗️ **Architecture**

### **Distributed Monolith Architecture**

```
┌────────────────────────────────────────────────────────────────┐
│                      Single Repository                          │
│                     (Modular Deployment)                        │
└────────────────────────────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
┌───────▼───────┐    ┌──────────▼──────────┐    ┌───────▼───────┐
│   API Server  │    │ Scraping Consumer   │    │Voice Processor│
│   (FastAPI)   │    │  (Background Worker)│    │(Background    │
│               │    │                     │    │ Worker)       │
│ - REST API    │    │ - LinkedIn Scraper  │    │ - PDF Parser  │
│ - WebSocket   │    │ - Twitter Scraper   │    │ - Audio/Video │
│ - LiveKit     │    │ - Website Crawler   │    │ - YouTube     │
│               │    │ - RAG Ingestion     │    │ - RAG Ingest  │
└───────┬───────┘    └──────────┬──────────┘    └───────┬───────┘
        │                       │                        │
        └───────────────────────┼────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   NATS Message Queue  │
                    │  (Async Communication)│
                    └───────────┬───────────┘
                                │
        ┌───────────────────────┼────────────────────────┐
        │                       │                        │
┌───────▼───────┐    ┌──────────▼──────────┐    ┌───────▼───────┐
│  PostgreSQL   │    │   Shared Codebase   │    │  OpenAI API   │
│  + pgvector   │    │                     │    │               │
│               │    │ - Models & Repos    │    │ - GPT-4o-mini │
│ - Personas    │    │ - RAG System        │    │ - Embeddings  │
│ - Embeddings  │    │ - Services          │    │               │
│ - Sessions    │    │ - Utilities         │    └───────────────┘
└───────────────┘    └─────────────────────┘
```

### **Key Architecture Decisions**

**✅ Independent Service Deployment**
- API, workers, and migrations deploy separately to ECS
- Workers ONLY copy `shared/` directory (no `app/` dependency)
- Eliminates unnecessary redeployments when API-only changes occur

**✅ Shared Database**
- Single PostgreSQL with pgvector for all services
- ACID guarantees and data consistency
- User-owned embeddings (shared across personas)

**✅ Async Processing (NATS)**
- API enqueues jobs → Workers process asynchronously
- Decouples web tier from compute-heavy tasks
- Enables independent worker scaling

**✅ Monorepo with Clear Boundaries**
- `shared/` - Database, RAG, services (used by all)
- `app/` - API-specific routes, auth, ingestion
- `workers/` - Background job processors

### **RAG System (LlamaIndex)**

- **Ingestion**: Multi-source data processing (LinkedIn, websites, documents)
- **Chunking**: Intelligent text chunking with LlamaIndex SentenceSplitter
- **Embeddings**: Voyage AI 3.5 lite (512 dimensions)
- **Storage**: PostgreSQL with pgvector for vector similarity search
- **Retrieval**: Hybrid search combining semantic and keyword matching
- **Generation**: GPT-4o-mini with retrieval-augmented prompts

### **Tech Stack**

- **Backend**: FastAPI, Python 3.11+, Poetry
- **RAG System**: LlamaIndex with PostgreSQL + pgvector
- **LLM**: OpenAI GPT-4o-mini
- **Embeddings**: OpenAI text-embedding-3-small
- **Voice**: LiveKit Cloud + Deepgram + ElevenLabs
- **Database**: PostgreSQL with pgvector extension
- **Message Queue**: NATS JetStream for async job processing
- **Workers**: Scraping consumer, Voice processing (independent deployment)
- **Containerization**: Docker with multi-stage builds
- **Authentication**: API key-based with session tokens

## 🔧 **Development**

### **Local Development Setup**

```bash
# Clone repository
git clone https://github.com/myclone-dev/myclone.git
cd myclone/backend

# Setup Poetry environment (matches Docker)
poetry config virtualenvs.in-project true
poetry install

# Activate virtual environment
poetry shell
# or manually:
source .venv/bin/activate

# Run development server
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### **Docker Development with Hot Reload**

```bash
# Build with virtual environment sync
docker-compose build

# Run with hot reload (code changes reflected immediately)
docker-compose up

# View logs
docker-compose logs -f api

# Execute commands in container
docker-compose exec api bash
docker-compose exec api poetry shell
```

### **Makefile Commands (Recommended)**

For simplified service management, use the provided Makefile commands:

#### **Quick Start**
```bash
# First time setup - builds services and runs migrations
make setup

# Daily development - start core services
make up              # Starts postgres, nats, api, scraping-consumer

# View logs
make logs            # All core services
make logs-api        # API only
make logs-scraper    # Scraping consumer only

# Stop services
make down
```

#### **Service Management**
```bash
make up              # Start core services (postgres, nats, api, scraping-consumer)
make up-all          # Start ALL services including voice workers
make down            # Stop all services
make restart         # Restart core services
make build           # Build Docker images
make ps              # Show running containers
make health          # Check API health endpoint
```

#### **Database & Migrations**
```bash
make migrate                                  # Run migrations
make migrate-create MSG="add user table"     # Create new migration
make migrate-status                           # Show current migration status
make migrate-rollback                         # Rollback last migration
make db-reset                                 # Reset database (prompts for confirmation)
```

#### **Code Quality**
```bash
make check           # Run all checks and auto-fix (format + lint + fix)
make lint            # Run linting checks (no changes)
make lint-fix        # Run linting with auto-fix
make format          # Format code (black + isort only)
```

#### **Development Tools**
```bash
make shell           # Open bash in API container
make shell-poetry    # Open poetry shell in API container
```

#### **Cleanup**
```bash
make clean           # Stop and remove containers
make clean-all       # Stop, remove containers AND volumes (deletes DB!)
```

#### **Full Command List**
```bash
make help            # Show all available commands with descriptions
```

> **Note**: The Makefile simplifies common Docker operations. It starts only the core services (postgres, nats, api, scraping-consumer) by default. Use `make up-all` if you need voice processing workers.

### **Adding/Removing Dependencies**

```bash
# Local development
poetry add new-package
poetry remove old-package

# In Docker container
docker-compose exec api poetry add new-package
docker-compose exec api poetry remove old-package
```

### **Code Quality**

This project uses **Black**, **Ruff**, **isort**, and **mypy** for code quality and formatting.

#### **Using Makefile (Recommended)**
```bash
make check           # Run all checks and auto-fix (format + lint)
make lint            # Run checks only (no changes)
make format          # Format code (black + isort)
```

#### **Using Poetry Directly**
```bash
# Install dev dependencies and pre-commit hooks
poetry install --with dev
poetry run pre-commit install

# Run all checks manually
poetry run pre-commit run --all-files

# Run individual tools
poetry run black .              # Format code
poetry run isort .              # Sort imports
poetry run ruff check --fix .   # Lint and auto-fix
poetry run mypy app/            # Type checking
```

**Pre-commit hooks** run automatically on every commit to ensure code quality. The **GitHub Actions workflow** runs on pushes to `main` and `staging` branches.

For detailed information on linting, formatting, configuration, troubleshooting, and CI/CD workflows, see **[Code Quality Guide](./docs/CODE_QUALITY.md)**.

## 💾 **Database Management**

### **Alembic Commands**

```bash
# Essential commands
poetry run alembic current                    # Check current version
poetry run alembic history --verbose          # View migration history
poetry run alembic revision --autogenerate -m "description"  # Generate migration
poetry run alembic upgrade head               # Apply migrations
poetry run alembic downgrade -1               # Rollback one version
poetry run alembic upgrade head --sql         # Preview SQL without executing

# Docker environment
docker-compose exec api alembic upgrade head
docker-compose exec api alembic revision --autogenerate -m "description"
```

### **Team Workflow - Avoiding Conflicts**

```bash
# Before creating a migration:
git pull origin main
poetry run alembic current  # Verify you're on latest

# Create and test migration:
poetry run alembic revision --autogenerate -m "add_user_preferences"
poetry run alembic upgrade head   # Test upgrade
poetry run alembic downgrade -1   # Test rollback
poetry run alembic upgrade head   # Back to head

# Commit and push quickly:
git add alembic/versions/
git commit -m "migration: add user preferences"
git push
```

### **Resolving Migration Conflicts**

```bash
# ERROR: Multiple head revisions detected

# Option 1: Merge migrations
poetry run alembic merge -m "merge feature branches"

# Option 2: Rebase your migration
git pull origin main
poetry run alembic downgrade -1
rm alembic/versions/your_migration.py
poetry run alembic revision --autogenerate -m "your feature"
```

### **Data Migration Pattern**

```python
def upgrade():
    # Add nullable column first
    op.add_column('personas', sa.Column('voice_id', sa.String(), nullable=True))

    # Migrate existing data
    op.execute("UPDATE personas SET voice_id = 'default_voice_id'")

    # Make non-nullable after data migration
    op.alter_column('personas', 'voice_id', nullable=False)
```

**Note:** Migrations are NOT run automatically. Operators must run them explicitly:

```bash
# Local development
docker-compose exec api alembic -c /app/alembic.ini upgrade head

# Production ECS
# Use the migrations ECS task (see infrastructure/modules/migrations)
```

## 📁 **Project Structure**

```
myclone/
├── alembic/                    # Database migrations
│   ├── versions/               # Migration files
│   ├── env.py                  # Migration configuration (uses shared/)
│   └── script.py.mako          # Migration template
│
├── app/                        # API-specific code (FastAPI application)
│   ├── api/                    # API route handlers
│   │   ├── ingestion_routes.py # Data ingestion endpoints
│   │   ├── livekit_routes.py   # LiveKit voice integration
│   │   ├── routes.py           # Core persona endpoints
│   │   ├── session_routes.py   # Session management
│   │   ├── scraping_routes.py  # Async scraping jobs
│   │   └── user_routes.py      # User management
│   ├── auth/                   # JWT authentication & middleware
│   ├── ingestion/              # Document processing
│   ├── services/               # API-specific services
│   │   ├── elevenlabs_service.py
│   │   ├── livekit_orchestrator.py
│   │   └── persona_prompt_history_service.py
│   └── main.py                 # FastAPI application entry
│
├── shared/                     # Shared code (used by API + workers)
│   ├── database/               # Database layer
│   │   ├── models/             # SQLAlchemy ORM models
│   │   │   ├── database.py     # Core models (Persona, Pattern, etc.)
│   │   │   ├── user.py         # User & AuthDetail models
│   │   │   ├── linkedin.py     # LinkedIn data models
│   │   │   ├── twitter.py      # Twitter data models
│   │   │   ├── website.py      # Website data models
│   │   │   ├── document.py     # Document models
│   │   │   └── embeddings.py   # LlamaIndex embedding model
│   │   ├── repositories/       # Data access layer
│   │   ├── config.py           # Database configuration
│   │   └── base.py             # SQLAlchemy Base
│   ├── rag/                    # RAG system (LlamaIndex)
│   │   ├── llama_rag.py        # Core RAG implementation
│   │   └── rag_singleton.py    # Singleton wrapper
│   ├── generation/             # Prompt generation
│   │   ├── prompts.py          # Prompt templates
│   │   ├── generator.py        # Response generator
│   │   └── context_pipeline.py # Context processing
│   ├── scraping/               # Data scraping
│   │   ├── providers/          # Scraping provider implementations
│   │   │   ├── linkedin/       # LinkedIn scrapers
│   │   │   ├── twitter/        # Twitter scrapers
│   │   │   └── website/        # Website scrapers
│   │   ├── queue_service.py    # NATS queue management
│   │   └── subjects.py         # NATS subjects/topics
│   ├── services/               # Shared business logic
│   │   ├── scraping_service.py # Scraping orchestration
│   │   └── s3_service.py       # S3 file storage
│   ├── schemas/                # Pydantic models
│   │   ├── scraping.py         # Scraping data schemas
│   │   └── livekit.py          # LiveKit schemas
│   ├── utils/                  # Utility functions
│   │   ├── encryption.py       # Token encryption
│   │   ├── conversions/        # Type conversions
│   │   └── config_helpers.py   # Config utilities
│   ├── config.py               # Global configuration
│   └── constants.py            # Application constants
│
├── workers/                    # Background workers (independent deployment)
│   ├── scraping_consumer/      # Scraping worker
│   │   └── worker.py           # NATS consumer for scraping jobs
│   └── voice_processing/       # Voice/document processing worker
│       └── worker.py           # PDF, audio, video processing
│
├── livekit/                    # LiveKit voice agents
│   └── livekit_agent_retrieval.py  # Persona voice agent
│
├── docker/                     # Docker configurations
│   ├── Dockerfile.api          # API service
│   ├── Dockerfile.scraping-consumer  # Scraping worker
│   ├── Dockerfile.voice-processing   # Voice worker
│   └── Dockerfile.migrations   # Migration runner
│
├── Makefile                    # Development commands
├── docker-compose.yml          # Local development stack
├── pyproject.toml              # Poetry dependencies
├── alembic.ini                 # Alembic configuration
├── .pre-commit-config.yaml     # Code quality hooks
└── README.md                   # This file
```

### **Key Directory Purposes**

- **`app/`** - FastAPI application (routes, auth, API-specific logic)
- **`shared/`** - Code shared between API and workers (database, RAG, services)
- **`workers/`** - Independent background job processors
- **`docker/`** - Service-specific Dockerfiles (multi-stage builds)

## 🐳 **Docker Configuration**

### **Volume Mounts for Development**

```yaml
volumes:
  - ./app:/app/app              # API source code (hot reload)
  - ./shared:/app/shared        # Shared modules (hot reload)
  - ./livekit:/app/livekit      # LiveKit voice agents
  - ./workers:/app/workers      # Background workers
  - ./alembic:/app/alembic      # Database migrations
  - poetry_cache:/root/.cache/pypoetry  # Poetry cache (platform-independent)
```

### **Environment Files**

- `docker-compose.yml` - Production deployment
- `docker-compose.local.yml` - Development with local PostgreSQL
- `.dockerignore` - Optimized build context

## 🔐 **Security & Authentication**

### **Authentication Methods**

Expert Clone supports multiple authentication methods:

- **OAuth**: LinkedIn, Google (social login)
- **Email/Password**: Traditional email and password authentication
- **Hybrid**: Users can have both OAuth and password authentication
- **API Key**: Required for service-to-service endpoints
- **Session Tokens**: For anonymous chat sessions

### **Email/Password Authentication**

Comprehensive authentication system with security features:
- ✅ **Email verification** required before login
- ✅ **Account lockout** after 5 failed attempts (15 minutes)
- ✅ **Password strength** validation (configurable requirements)
- ✅ **Bcrypt hashing** with 12 rounds
- ✅ **Password reset** with 1-hour token expiry
- ✅ **Rate limiting** on registration and reset endpoints
- ✅ **JWT tokens** via HTTP-only cookies
- ✅ **OAuth users** can add password as backup method

📖 **[Full Documentation](./docs/EMAIL_PASSWORD_AUTH.md)** - Complete authentication guide

### **Production Security**

- Environment variable configuration
- Docker container isolation
- SSL/TLS support ready
- Secure headers configuration
- No sensitive data in logs
- Email enumeration prevention
- Sentry integration for monitoring

## 🚨 **Troubleshooting**

### **Common Issues**

**Import Errors After Migration:**

```bash
# Check if shared/ directory exists
ls -la shared/rag/
ls -la shared/database/models/

# Restart Docker containers
docker-compose down && docker-compose up --build
```

**Hot Reload Not Working:**

```bash
# Ensure volume mounts are correct
docker-compose down
docker-compose up

# Check if .venv is mounted
docker-compose exec api ls -la /app/.venv/
```

**Poetry Virtual Environment Issues:**

```bash
# Recreate virtual environment
rm -rf .venv/
poetry config virtualenvs.in-project true
poetry install

# In Docker
docker-compose exec api poetry install
```

**Database Connection Issues:**

```bash
# Check database status
docker-compose ps
docker-compose logs postgres

# Reset database (local development)
docker-compose -f docker-compose.local.yml down -v
docker-compose -f docker-compose.local.yml up
```

**LlamaIndex Ingestion Issues:**

```bash
# Check LlamaIndex configuration
docker-compose exec api python -c "
from shared.rag.llama_rag import LlamaRAGSystem
rag = LlamaRAGSystem()
print('LlamaRAG initialized successfully')
"
```

## 📖 **Documentation**

### **Core Documentation**
- **[API Documentation](./docs/API_DOCUMENTATION.md)** - Complete API reference
- **[API Reference](http://localhost:8001/docs)** - API documentation and testing interface (when running locally)
- **[Email/Password Authentication](./docs/EMAIL_PASSWORD_AUTH.md)** - Email/password auth system, flows, and security features
- **[Code Quality Guide](./docs/CODE_QUALITY.md)** - Linting, formatting, pre-commit hooks, and CI/CD
- **[Persona Access Control](./docs/PERSONA_ACCESS_CONTROL.md)** - Private personas with email-based access control
- **[Deployment Guide](./docs/VPS_DEPLOYMENT_UBUNTU.md)** - Production deployment
- **[Project Overview](./docs/PROJECT_OVERVIEW.md)** - Architecture details

### **Prompt System**
- **[Prompt Lifecycle](./docs/prompts/PROMPT_LIFECYCLE.md)** - How prompts are created, stored, and used
- **[Prompt Management](./docs/prompts/PROMPT_MANAGEMENT.md)** - API reference for prompt operations
- **[Persona Structure](./docs/prompts/PERSONA_STRUCTURE.md)** - Persona data model and examples

### **Voice Integration**
- **[LiveKit Worker Lifecycle](./docs/livekit-agent-workflow/WORKER_LIFECYCLE_GUIDE.md)** - Beginner-friendly guide to voice agent system
- **[LiveKit Technical Implementation](./docs/livekit-agent-workflow/ACTUAL_IMPLEMENTATION_GUIDE.md)** - Detailed technical implementation with code

### **Payment & Monetization**
- **[Stripe Payment Architecture](./docs/STRIPE_PAYMENT_ARCHITECTURE.md)** - Complete payment integration architecture, database schema, flows, and design decisions

### **Other Resources**
- **[Cleanup Documentation](./CLEANUP_DOCUMENTATION.md)** - RAG system migration details

## 🤝 **Contributing**

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with proper testing
4. Ensure Docker builds and tests pass
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 **Support**

- **Issues**: [GitHub Issues](https://github.com/myclone-dev/myclone/issues)
- **Documentation**: [docs/](./docs/)
- **API Reference**: [/docs](http://localhost:8001/docs) (when running)

## 🎯 **Roadmap**

### **Completed**
- [x] ~~Custom RAG system~~ → **LlamaIndex migration complete**
- [x] ~~Dual system redundancy~~ → **Unified pipeline**
- [x] Docker hot reload development
- [x] Poetry virtual environment sync
- [x] **Modular architecture** → **API/Worker separation with `shared/` directory**
- [x] **Independent worker deployment** → **Workers no longer depend on `app/`**
- [x] **NATS async processing** → **Decoupled compute-heavy tasks**

### **In Progress**
- [ ] Advanced vector search optimization
- [ ] Multi-language support
- [ ] Voice conversation analytics
- [ ] Enterprise SSO integration
- [ ] Custom model fine-tuning support

### **Recent Architecture Improvements** (2024)

**Distributed Monolith Refactor:**
- Migrated shared code to `shared/` directory for clean separation
- Workers now independently deployable (only copy `shared/`, not `app/`)
- Eliminated unnecessary redeployments when API-only code changes
- Added NATS message queue for async job processing
- Implemented multi-stage Docker builds for each service
- 230+ imports updated across the codebase

---

<div align="center">

**Built with ❤️ using LlamaIndex for intelligent digital personalities**

[⭐ Star this repo](https://github.com/myclone-dev/myclone) | [🐛 Report Bug](https://github.com/myclone-dev/myclone/issues) | [💡 Request Feature](https://github.com/myclone-dev/myclone/issues)

</div>
