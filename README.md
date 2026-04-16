# MyClone

> Build AI-powered digital clones of yourself — powered by RAG, voice, and real-time chat.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

MyClone is an open-source platform for creating intelligent digital personas. Users ingest data from LinkedIn, Twitter, websites, PDFs, and YouTube — then interact with their AI clone via text chat or real-time voice conversations powered by retrieval-augmented generation (RAG).

---

## Features

- **RAG-Powered Knowledge** — LlamaIndex + pgvector for accurate, context-aware responses
- **Real-Time Voice Chat** — LiveKit + Deepgram STT + ElevenLabs/Cartesia TTS
- **Multi-Source Ingestion** — LinkedIn, Twitter, websites, PDFs, YouTube videos
- **Persistent Memory** — Conversations and context survive restarts
- **Embeddable Widget** — Drop a script tag on any site to add your clone
- **Multi-Auth** — OAuth (LinkedIn, Google) + email/password with email verification
- **Workflow System** — Linear assessments and conversational lead qualification
- **Payment Integration** — Stripe-powered subscriptions and persona monetization
- **Internationalization** — 14 languages supported on public-facing pages

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend** | Next.js 15, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, Zustand, TanStack Query v5 |
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy, Alembic, Poetry/uv |
| **RAG** | LlamaIndex, OpenAI embeddings, pgvector |
| **Voice** | LiveKit Cloud, Deepgram (STT), ElevenLabs/Cartesia (TTS) |
| **Database** | PostgreSQL + pgvector |
| **Message Queue** | NATS JetStream |
| **Infrastructure** | Docker, multi-stage builds, docker-compose |

---

## Repository Structure

```
myclone/
├── frontend/           # Next.js 15 app (App Router, Turbopack)
├── backend/            # FastAPI API + workers + RAG system
│   ├── app/            # API routes, auth, ingestion
│   ├── shared/         # Database, RAG, services (used by API + workers)
│   ├── workers/        # Background job processors
│   └── livekit/        # Voice agent integration
├── infra/              # Docker configs, docker-compose
├── scripts/            # Utility scripts
└── docs/               # Project documentation
```

---

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [Node.js 18+](https://nodejs.org/) and [bun](https://bun.sh/) (frontend)
- [Python 3.11+](https://www.python.org/) (backend, if running locally)
- OpenAI API key

### 1. Clone the Repository

```bash
git clone https://github.com/myclone-dev/myclone.git
cd myclone
```

### 2. Start the Backend (Docker)

```bash
cd backend

# Setup environment
cp .env.example .env
# Edit .env with your API keys (OPENAI_API_KEY at minimum)

# First-time setup: build, start services, run migrations
make setup-local

# Or manually:
docker-compose build
docker-compose up -d
docker-compose exec api alembic -c /app/alembic.ini upgrade head
```

The API will be available at `http://localhost:8001`. Interactive docs at `http://localhost:8001/docs`.

### 3. Start the Frontend

```bash
cd frontend

# Install dependencies
bun install

# Setup environment
cp .env.example .env.local
# Edit .env.local — set NEXT_PUBLIC_API_URL=http://localhost:8001/api

# Start dev server
bun dev
```

The app will be available at `http://localhost:3000`.

---

## Architecture Overview

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Frontend   │     │   FastAPI (API)   │     │  Voice Agent     │
│   Next.js    │────▶│   REST + SSE      │     │  (LiveKit)       │
└──────────────┘     └────────┬─────────┘     └────────┬─────────┘
                              │                         │
                    ┌─────────▼─────────┐               │
                    │   NATS JetStream  │               │
                    │  (Message Queue)  │               │
                    └─────────┬─────────┘               │
                              │                         │
              ┌───────────────┼─────────────────────────┘
              │               │
    ┌─────────▼──────┐  ┌────▼───────────────┐  ┌───────────────┐
    │  Workers       │  │  PostgreSQL        │  │  OpenAI API   │
    │  - Scraping    │  │  + pgvector        │  │  - GPT-4o     │
    │  - Voice proc  │  │  (Personas, RAG)   │  │  - Embeddings │
    └────────────────┘  └────────────────────┘  └───────────────┘
```

**How it works:**

1. **Ingest** — Users upload data (LinkedIn, Twitter, websites, PDFs, YouTube). Workers process and chunk the content.
2. **Embed** — LlamaIndex creates vector embeddings stored in PostgreSQL + pgvector.
3. **Chat** — Text or voice queries trigger RAG retrieval, pulling relevant context for the LLM to generate persona-accurate responses.

---

## Development

### Backend Commands

```bash
cd backend

# Docker workflow (recommended)
make up                # Start core services
make down              # Stop all services
make logs              # View logs
make migrate           # Run database migrations
make check             # Auto-fix: isort + black + ruff

# Local workflow (uv)
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

See the [Backend README](./backend/README.md) for the full API reference, database management, and troubleshooting.

### Frontend Commands

```bash
cd frontend

# Development
bun dev               # Start dev server (Turbopack)
bun run build         # Production build
bun start             # Start production server

# Code quality
bun type-check        # TypeScript check
bun lint:fix          # ESLint with auto-fix
bun format            # Prettier formatting
```

### Adding UI Components

```bash
cd frontend
bunx shadcn@latest add <component-name>
```

Never manually create files in `src/components/ui/` — always use the shadcn CLI.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `OPENAI_API_KEY` | Yes | OpenAI API key for LLM + embeddings |
| `EXPERT_CLONE_API_KEY` | Yes | API authentication key |
| `LIVEKIT_URL` | For voice | LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | For voice | LiveKit API key |
| `LIVEKIT_API_SECRET` | For voice | LiveKit API secret |
| `DEEPGRAM_API_KEY` | For voice | Deepgram STT key |
| `ELEVENLABS_API_KEY` | For voice | ElevenLabs TTS key |

See `backend/.env.example` for the full list.

### Frontend (`frontend/.env.local`)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API URL (e.g., `http://localhost:8001/api`) |
| `NEXT_PUBLIC_APP_URL` | Yes | Frontend URL (e.g., `http://localhost:3000`) |

See `frontend/.env.example` for the full list.

---

## Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/my-feature`
3. **Make** your changes with proper testing
4. **Run checks:**
   ```bash
   # Backend
   cd backend && make check

   # Frontend
   cd frontend && bun lint:fix && bun format && bun type-check
   ```
5. **Commit** your changes: `git commit -m 'Add my feature'`
6. **Push** to your branch: `git push origin feature/my-feature`
7. **Open** a Pull Request

### Guidelines

- Keep PRs focused — one feature or fix per PR
- Follow existing code style (enforced by linters and pre-commit hooks)
- Add tests for new functionality where applicable
- Update documentation if you change public APIs or configuration

---

## Documentation

- **[Backend README](./backend/README.md)** — API reference, architecture details, database management
- **[Backend Docs](./backend/docs/)** — API documentation, auth guides, deployment
- **[Frontend Docs](./frontend/docs/)** — Architecture, tech stack, development guide

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/myclone-dev/myclone/issues)
- **Discussions**: [GitHub Discussions](https://github.com/myclone-dev/myclone/discussions)

---

<div align="center">

**Built with LlamaIndex, FastAPI, Next.js, and LiveKit**

[Report Bug](https://github.com/myclone-dev/myclone/issues) | [Request Feature](https://github.com/myclone-dev/myclone/issues)

</div>
