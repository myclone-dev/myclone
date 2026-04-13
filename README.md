# MyClone : AI digital Persona

MyClone is a full-stack AI digital persona platform. This repository contains the application code for creating, managing, and interacting with AI-powered personas through text chat, voice chat, embeddable widgets, workflow automation, and knowledge ingestion pipelines.

At a high level, the monorepo includes:

- a `frontend` application built with Next.js for public persona experiences and creator dashboards
- a `backend` application built with FastAPI for APIs, authentication, ingestion, RAG, workflows, and voice orchestration
- an `infra` workspace for local infrastructure and container setup
- GitHub workflows for CI/CD, code quality, migrations, and deployment automation

---

## What this repository contains

This monorepo is organized around three main runtime areas:

### `frontend/`
The web application used by both end users and creators.

It includes:

- public persona pages such as `/{username}` and `/{username}/{persona_name}`
- authentication flows like signup, login, password reset, email verification, and account claiming
- creator onboarding flows
- a dashboard for managing personas, knowledge, conversations, widgets, workflows, access control, whitelabel settings, usage, and voice cloning
- an embeddable widget SDK and iframe app built separately from the main Next.js app

### `backend/`
The API and processing layer for the platform.

It includes:

- FastAPI route modules for personas, users, auth, conversations, documents, workflows, jobs, webhooks, custom domains, evaluations, and voice features
- PostgreSQL-backed application data and vector search
- retrieval-augmented generation infrastructure
- async background processing with NATS JetStream
- voice processing workers
- LiveKit-based real-time voice agent orchestration
- shared repositories, models, services, and integrations used across API and workers

### `infra/`
Local infrastructure and Docker assets.

It includes:

- local Docker Compose setup
- Dockerfiles for API, workers, migrations, NATS, and LocalStack
- local AWS-compatible S3 setup through LocalStack
- container entrypoints and initialization scripts

---

## Product capabilities

From the codebase structure and project documentation, the platform supports a broad set of capabilities:

- AI personas with public profile/chat experiences
- text chat and voice chat
- persona-specific voice configuration and voice cloning
- knowledge ingestion from multiple sources
- document and media processing
- RAG over stored knowledge using vector search
- creator dashboards and management tools
- embeddable website widgets
- workflow and template systems
- access control and visitor management
- custom domains and whitelabel email domain support
- analytics, monitoring, and evaluation tooling

---

## Monorepo structure

```myclone/README.md#L52-84
myclone/
├── .github/                  # CI/CD workflows and automation
├── backend/                  # FastAPI backend, workers, shared services, migrations
│   ├── app/                  # API-specific application code
│   ├── shared/               # Shared config, DB models, repositories, services
│   ├── workers/              # Background workers
│   ├── livekit/              # LiveKit agent runtime
│   ├── alembic/              # Database migrations
│   ├── docs/                 # Backend technical documentation
│   ├── docker-compose.yml    # Backend-focused local dev stack
│   ├── pyproject.toml        # Python dependencies and tooling
│   └── Makefile              # Common development commands
├── frontend/                 # Next.js frontend and embed SDK/app
│   ├── src/app/              # App Router pages and layouts
│   ├── src/components/       # UI and feature components
│   ├── src/lib/              # API client, queries, utilities
│   ├── src/store/            # Zustand stores
│   ├── src/embed/            # Widget SDK and embed app
│   ├── docs/                 # Frontend technical documentation
│   ├── package.json          # Frontend scripts and dependencies
│   └── vite.embed*.ts        # Separate embed build configuration
├── infra/                    # Shared local infrastructure assets
│   ├── docker/               # Dockerfiles and init scripts
│   └── docker-compose.yml    # Infra-focused local services
├── README.md
└── LICENSE
```

---

## Architecture overview

### Frontend architecture

The frontend is a Next.js App Router application designed for both public-facing persona experiences and authenticated creator tooling.

Key characteristics:

- Next.js 15 with React 19
- App Router-based routing
- TanStack Query for server state and API data fetching
- Zustand for client-side UI/auth state
- typed environment validation with `@t3-oss/env-nextjs` and `zod`
- dashboard-heavy UI architecture with domain-organized components and query hooks
- dedicated embed/widget build pipeline using Vite
- analytics and monitoring integrations including Sentry and product analytics support

Important frontend areas include:

- `src/app/` for routes and layouts
- `src/components/` for feature and UI components
- `src/lib/queries/` for domain-based query and mutation hooks
- `src/store/` for client state
- `src/embed/` for widget SDK and iframe app

### Backend architecture

The backend is structured as a modular monolith with clear separation between API code, shared domain logic, workers, and real-time voice runtime components.

Key characteristics:

- FastAPI application entrypoint in `backend/app/main.py`
- route modules under `backend/app/api/`
- shared configuration, models, repositories, and services under `backend/shared/`
- PostgreSQL as the primary system of record
- `pgvector` for vector storage and retrieval
- async processing with NATS JetStream
- voice processing workers under `backend/workers/`
- LiveKit runtime under `backend/livekit/`
- Alembic migrations under `backend/alembic/`

Important backend areas include:

- `app/api/` for HTTP endpoints
- `shared/database/` for models and repositories
- `shared/voice_processing/` for job orchestration
- `workers/voice_processing/` for background processing
- `livekit/` for real-time voice agent execution
- `docs/` for backend architecture and operational documentation

### Infrastructure architecture

Local development infrastructure is containerized and centered around a small set of core services:

- PostgreSQL with `pgvector`
- NATS with JetStream
- LocalStack for local S3-compatible storage
- API container
- voice-processing worker container(s)

This setup supports local development of ingestion, storage, async jobs, and voice-related flows without requiring all production services.

---

## Core technology stack

### Frontend

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- Radix UI
- TanStack Query
- Zustand
- Axios
- Zod
- Sentry
- Vite for embed builds
- pnpm

### Backend

- Python 3.11+
- FastAPI
- SQLAlchemy
- PostgreSQL
- asyncpg
- pgvector
- Alembic
- OpenAI
- LlamaIndex
- NATS
- LiveKit
- ElevenLabs
- Cartesia
- Deepgram
- aioboto3 / S3
- Langfuse
- Sentry
- Resend

### Tooling and automation

- Docker
- Docker Compose
- GitHub Actions
- Ruff
- Black
- isort
- pytest
- ESLint
- Prettier
- Husky
- pre-commit

---

## How the system works

### 1. Persona and knowledge ingestion

A typical ingestion flow looks like this:

1. a user or system submits content through backend endpoints
2. the backend creates or publishes processing jobs
3. jobs are sent through NATS JetStream
4. background workers consume and process those jobs
5. extracted content and metadata are stored in PostgreSQL
6. embeddings are stored in vector-enabled tables
7. personas are linked to the resulting knowledge records
8. future chat requests can retrieve that knowledge through RAG

### 2. Text and voice interaction

A typical interaction flow looks like this:

1. a user opens a public persona page or embedded widget
2. the frontend fetches persona/profile/session data from the backend
3. the backend resolves persona context and available knowledge
4. retrieval and prompt assembly happen on the backend
5. the model generates a response
6. the frontend renders the response in chat UI
7. for voice sessions, LiveKit handles real-time media/session transport
8. conversation state and post-processing are persisted by backend services

### 3. Widget/embed flow

The repository includes first-class support for embeddable widgets:

1. creators configure widgets in the dashboard
2. the frontend generates integration code and widget settings
3. a separate embed SDK/app bundle is built from `frontend/src/embed/`
4. external sites load the widget bundle
5. the widget communicates with backend APIs using configured environment/runtime values

---

## Local development options

There are multiple ways to work with this repository depending on what you need to run.

### Option 1: Work on a single app
If you only need to work on one side of the stack:

- use `frontend/` for UI work
- use `backend/` for API, worker, ingestion, or data work

Each app has its own README and app-specific setup instructions.

### Option 2: Run the full local stack
If you need end-to-end development:

- start infrastructure services
- run backend services and migrations
- run the frontend app
- configure environment variables for both apps

Because this is a monorepo with separate app runtimes, you should treat `frontend` and `backend` as independently bootstrapped applications that integrate over HTTP and shared environment configuration.

---

## Recommended setup order

### 1. Clone the repository

```myclone/README.md#L194-197
git clone <your-repository-url>
cd myclone
```

### 2. Read the app-specific READMEs

Start with:

- `backend/README.md`
- `frontend/README.md`

These contain the most specific setup and workflow details for each application.

### 3. Configure backend environment

Use the backend example environment file as your starting point:

```myclone/README.md#L206-209
cd backend
cp .env.example .env
```

Then fill in the required values for services such as database access, model providers, voice providers, email, and observability.

### 4. Configure frontend environment

Create the frontend local environment file from its template if present in your checkout, then set at least the API and app URLs expected by the frontend.

Common frontend variables referenced in code include:

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_APP_URL`
- `NEXT_PUBLIC_LIVEKIT_URL`
- `NEXT_PUBLIC_LANDING_PAGE_URL`
- `NEXT_PUBLIC_SENTRY_DSN`
- `NEXT_PUBLIC_POSTHOG_KEY`

### 5. Start infrastructure and backend

Use the backend Docker Compose setup and migration workflow described in `backend/README.md`.

Typical backend local flow includes:

- building containers
- starting PostgreSQL, NATS, LocalStack, API, and workers
- running Alembic migrations explicitly

### 6. Start the frontend

From `frontend/`, install dependencies and run the development server using the scripts documented in `frontend/README.md`.

---git push --set-upstream origin rishi/update-readme

## Common development workflows

### Frontend workflow

Typical commands are documented in `frontend/README.md`, including:

- install dependencies
- run dev server
- build production assets
- run linting and type checks
- format code

The frontend also includes dedicated documentation for:

- architecture
- tech stack
- development guide
- query architecture
- embed SDK
- i18n and other feature-specific topics

### Backend workflow

Typical commands are documented in `backend/README.md` and `backend/Makefile`, including:

- local environment startup
- service management
- migrations
- linting and formatting
- shell access
- code quality checks

The backend includes extensive docs for:

- architecture
- API behavior
- migrations
- deployment
- LiveKit
- voice processing
- RAG
- persona knowledge architecture
- workflow system behavior
- auth and access control

---

## Important repository docs

### Root
- `README.md`
- `LICENSE`

### Frontend docs
- `frontend/README.md`
- `frontend/docs/README.md`
- `frontend/docs/ARCHITECTURE.md`
- `frontend/docs/TECH_STACK.md`
- `frontend/docs/DEVELOPMENT_GUIDE.md`

Additional frontend docs exist for query architecture, embed SDK, i18n, LiveKit-related frontend behavior, and other implementation details.

### Backend docs
- `backend/README.md`
- `backend/docs/API_DOCUMENTATION.md`
- `backend/docs/DEPLOYMENT.md`
- `backend/docs/MIGRATIONS.md`
- `backend/docs/LIVEKIT_AGENT_ARCHITECTURE.md`
- `backend/docs/LlamaIndex-RAG.md`
- `backend/docs/PERSONA_KNOWLEDGE_ARCHITECTURE.md`
- `backend/docs/VOICE_PROCESSING_DOCKER.md`
- `backend/docs/WORKFLOW_SYSTEM_DEVELOPER_GUIDE.md`

There are many more backend docs covering integrations, auth, evaluation, custom domains, deployment details, and operational procedures.

---

## CI/CD and automation

The `.github/workflows/` directory contains automation for areas such as:

- backend code quality
- frontend code quality
- backend API CI/CD
- production deployment flows
- migration verification
- worker deployment
- review/automation workflows

This repository is set up for active automation around quality checks and deployment pipelines.

---

## Notes for contributors

- prefer reading the app-specific READMEs before making changes
- backend and frontend have separate dependency management and runtime expectations
- migrations are an explicit part of backend development
- widget/embed functionality is a distinct frontend subsystem
- voice and async processing involve multiple services, not just the API server
- there is extensive internal documentation in both `frontend/docs` and `backend/docs`

---

## Where to start

If you are new to the codebase, this is a good order:

1. read `frontend/README.md`
2. read `backend/README.md`
3. review `frontend/docs/README.md`
4. review key backend docs in `backend/docs/`
5. boot the backend local stack
6. boot the frontend app
7. verify end-to-end connectivity between frontend and backend

---

## License

See `LICENSE` for repository licensing terms.
