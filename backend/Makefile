# Expert Clone - Development Makefile
# Common commands for running services and managing the application

.PHONY: help build up down restart restart-api logs shell migrate migrate-create migrate-rollback db-reset clean test exec-api exec-postgres exec-nats exec-localstack localstack-up localstack-down localstack-logs localstack-health localstack-test lint lint-fix format check

# Default target - show help
help:
	@echo "🚀 MyClone - Development Commands"
	@echo ""
	@echo "Service Management:"
	@echo "  make up              - Start core services + voice workers with logs (foreground)"
	@echo "  make up-detach       - Start core services + voice workers in background (detached)"
	@echo "  make up-local        - Start core services + voice workers + LocalStack (detached)"
	@echo "  make down            - Stop all services"
	@echo "  make restart         - Restart core services + voice workers"
	@echo "  make restart-api     - Restart API only (after code changes)"
	@echo "  make build           - Build all Docker images"
	@echo "  make build api       - Build specific service (e.g., api, nats, etc.)"
	@echo "  make build api nats  - Build multiple services"
	@echo "  make logs            - View logs from all services"
	@echo "  make logs-api        - View API logs only"
	@echo "  make logs-voice      - View voice processing worker logs"
	@echo ""
	@echo "LocalStack (Local AWS S3):"
	@echo "  make localstack-up   - Start LocalStack service only"
	@echo "  make localstack-down - Stop LocalStack service only"
	@echo "  make localstack-logs - View LocalStack logs"
	@echo "  make localstack-health - Check LocalStack health"
	@echo "  make localstack-test - Test S3 operations with LocalStack"
	@echo "  make localstack-shell - Open shell in LocalStack container"
	@echo ""
	@echo "Database & Migrations:"
	@echo "  make migrate         - Run database migrations"
	@echo "  make migrate-create MSG='description' - Create new migration"
	@echo "  make migrate-rollback - Rollback last migration"
	@echo "  make migrate-status  - Show current migration status"
	@echo "  make db-reset        - Reset database (WARNING: deletes all data)"
	@echo ""
	@echo "Development:"
	@echo "  make shell           - Open shell in API container"
	@echo "  make shell-venv      - Open shell with venv in API container"
	@echo "  make exec-api ARGS='command' - Run command in API container"
	@echo "  make exec-voice-worker ARGS='command' - Run command in voice worker"
	@echo "  make exec-postgres ARGS='command' - Run command in postgres container"
	@echo "  make exec-nats ARGS='command' - Run command in NATS container"
	@echo "  make exec-localstack ARGS='command' - Run command in LocalStack container"
	@echo "  make ps              - Show running containers"
	@echo "  make health          - Check API health endpoint"
	@echo ""
	@echo "Code Quality:"
	@echo "  make check           - Run all checks and auto-fix (format + lint + fix)"
	@echo "  make lint            - Run linting checks (ruff, black, isort)"
	@echo "  make lint-fix        - Run linting with auto-fix"
	@echo "  make format          - Format code with black and isort"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean           - Stop services and remove containers"
	@echo "  make clean-all       - Stop services, remove containers and volumes (deletes DB)"
	@echo ""
	@echo "Full Stack:"
	@echo "  make up-all          - Start ALL services (same as up-detach + voice workers)"
	@echo "  make logs-all        - View logs from ALL services"
	@echo ""
	@echo "Quick Setup:"
	@echo "  make setup           - First time setup (includes voice workers)"
	@echo "  make setup-local     - First time setup with LocalStack (includes voice workers)"

# Build Docker images (all or specific services)
# Usage:
#   make build              - Build all services
#   make build api          - Build only API
#   make build api nats     - Build multiple services
build:
	@$(eval SERVICES := $(filter-out build,$(MAKECMDGOALS)))
	@if [ -z "$(SERVICES)" ]; then \
		echo "🔨 Building ALL Docker images..."; \
		docker-compose build postgres nats api localstack voice-processing-worker; \
		echo "✅ All images built!"; \
	else \
		echo "🔨 Building service(s): $(SERVICES)"; \
		docker-compose build $(SERVICES); \
		echo "✅ Service(s) built: $(SERVICES)"; \
	fi

# Dummy targets to prevent "No rule to make target" errors
api nats postgres localstack voice-processing-worker:
	@:

# Start core services with logs (includes voice workers)
up:
	@echo "🚀 Starting services (postgres, nats, api, voice-processing-worker)..."
	@echo "📊 Service URLs:"
	@echo "  - API:       http://localhost:8000"
	@echo "  - API Docs:  http://localhost:8000/docs"
	@echo "  - Postgres:  localhost:5432"
	@echo "  - NATS:      localhost:4222"
	@echo ""
	@echo "📝 In another terminal run: make migrate"
	@echo ""
	docker-compose up postgres nats api voice-processing-worker

# Start core services in detached mode
up-detach:
	@echo "🚀 Starting core services in detached mode..."
	docker-compose up -d postgres nats api voice-processing-worker
	@echo "✅ Services started!"
	@echo ""
	@echo "📊 Service URLs:"
	@echo "  - API:       http://localhost:8000"
	@echo "  - API Docs:  http://localhost:8000/docs"
	@echo "  - Postgres:  localhost:5432"
	@echo "  - NATS:      localhost:4222"
	@echo ""
	@echo "📝 Next steps:"
	@echo "  - Run migrations: make migrate"
	@echo "  - View logs:      make logs"
	@echo "  - Check health:   make health"

# Start core services + LocalStack in detached mode (recommended for local development)
up-local:
	@echo "🚀 Starting core services + LocalStack in detached mode..."
	docker-compose up -d postgres nats localstack api voice-processing-worker
	@echo "✅ Services started with LocalStack!"
	@echo ""
	@echo "📊 Service URLs:"
	@echo "  - API:       http://localhost:8001"
	@echo "  - API Docs:  http://localhost:8001/docs"
	@echo "  - Postgres:  localhost:5432"
	@echo "  - NATS:      localhost:4222"
	@echo "  - LocalStack: http://localhost:4566"
	@echo ""
	@echo "📝 Next steps:"
	@echo "  - Run migrations: make migrate"
	@echo "  - Test S3:        make localstack-test"
	@echo "  - View logs:      make logs"
	@echo "  - Check health:   make health && make localstack-health"

# Start ALL services including voice workers
up-all:
	@echo "🚀 Starting ALL services (including voice workers)..."
	docker-compose up -d
	@echo "✅ All services started!"

# Stop all services
down:
	@echo "🛑 Stopping services..."
	docker-compose down
	@echo "✅ Services stopped"

# Restart core services
restart:
	@echo "🔄 Restarting core services..."
	docker-compose restart postgres nats api voice-processing-worker
	@echo "✅ Services restarted"

# Restart just API (useful for quick reload after Claude Code changes)
restart-api:
	@echo "🔄 Restarting API only..."
	docker-compose restart api
	@echo "✅ API restarted (changes should now be reflected)"

# Restart core services + LocalStack
restart-local:
	@echo "🔄 Restarting core services + LocalStack..."
	docker-compose restart postgres nats localstack api voice-processing-worker
	@echo "✅ Services restarted with LocalStack"

# View logs from core services
logs:
	docker-compose logs -f postgres nats api voice-processing-worker

# View logs from core services + LocalStack
logs-local:
	docker-compose logs -f postgres nats localstack api voice-processing-worker

# View logs from ALL services
logs-all:
	docker-compose logs -f

# View API logs only
logs-api:
	docker-compose logs -f api

# View voice processing worker logs
logs-voice:
	docker-compose logs -f voice-processing-worker

# LocalStack specific commands
localstack-up:
	@echo "🚀 Starting LocalStack service..."
	docker-compose up -d localstack
	@echo "✅ LocalStack started!"
	@echo "📊 LocalStack URL: http://localhost:4566"
	@echo "📝 Test with: make localstack-test"

localstack-down:
	@echo "🛑 Stopping LocalStack service..."
	docker-compose stop localstack
	@echo "✅ LocalStack stopped"

localstack-logs:
	@echo "📜 LocalStack logs:"
	docker-compose logs -f localstack

localstack-health:
	@echo "🏥 Checking LocalStack health..."
	@curl -s http://localhost:4566/_localstack/health | python -m json.tool || echo "❌ LocalStack not responding"

localstack-test:
	@echo "🧪 Testing LocalStack S3 operations..."
	@echo "📝 Installing awscli-local if needed..."
	@pip install awscli-local 2>/dev/null || echo "awscli-local already installed or pip not available"
	@echo ""
	@echo "🔍 Listing S3 buckets:"
	@awslocal s3 ls 2>/dev/null || echo "❌ LocalStack not ready or awscli-local not installed"
	@echo ""
	@echo "📊 LocalStack services status:"
	@curl -s http://localhost:4566/_localstack/health 2>/dev/null | python -c "import sys,json; data=json.load(sys.stdin); print('✅ S3:', data.get('services',{}).get('s3','❌'))" || echo "❌ Cannot connect to LocalStack"

localstack-shell:
	@echo "🐚 Opening shell in LocalStack container..."
	docker-compose exec localstack bash

# Open bash shell in API container
shell:
	docker-compose exec api bash

# Open shell with venv activated in API container
shell-venv:
	docker-compose exec api bash -c "source /app/.venv/bin/activate && bash"

# Execute arbitrary command in API container with virtualenv in PATH
# Usage: make exec-api ARGS="alembic check"
exec-api:
	@if [ -z "$(ARGS)" ]; then \
		echo "❌ Error: ARGS parameter required"; \
		echo "Usage: make exec-api ARGS='your command here'"; \
		echo "Examples:"; \
		echo "  make exec-api ARGS='alembic check'"; \
		echo "  make exec-api ARGS='python --version'"; \
		echo "  make exec-api ARGS='ls -la /app'"; \
		exit 1; \
	fi
	docker-compose exec api bash -c "export PATH=/app/.venv/bin:\$$PATH && $(ARGS)"

# Execute arbitrary command in voice processing worker container
# Usage: make exec-voice-worker ARGS="python --version"
exec-voice-worker:
	@if [ -z "$(ARGS)" ]; then \
		echo "❌ Error: ARGS parameter required"; \
		echo "Usage: make exec-voice-worker ARGS='your command here'"; \
		exit 1; \
	fi
	docker-compose exec voice-processing-worker bash -c "export PATH=/app/.venv/bin:\$$PATH && $(ARGS)"

# Execute arbitrary command in postgres container
# Usage: make exec-postgres ARGS="psql -U persona_user -d persona_db -c 'SELECT version();'"
exec-postgres:
	@if [ -z "$(ARGS)" ]; then \
		echo "❌ Error: ARGS parameter required"; \
		echo "Usage: make exec-postgres ARGS='your command here'"; \
		echo "Example: make exec-postgres ARGS='psql -U postgres -l'"; \
		exit 1; \
	fi
	docker-compose exec postgres $(ARGS)

# Execute arbitrary command in NATS container
# Usage: make exec-nats ARGS="nats-server --version"
exec-nats:
	@if [ -z "$(ARGS)" ]; then \
		echo "❌ Error: ARGS parameter required"; \
		echo "Usage: make exec-nats ARGS='your command here'"; \
		exit 1; \
	fi
	docker-compose exec nats $(ARGS)

# Execute arbitrary command in LocalStack container
# Usage: make exec-localstack ARGS="awslocal s3 ls"
exec-localstack:
	@if [ -z "$(ARGS)" ]; then \
		echo "❌ Error: ARGS parameter required"; \
		echo "Usage: make exec-localstack ARGS='your command here'"; \
		echo "Examples:"; \
		echo "  make exec-localstack ARGS='awslocal s3 ls'"; \
		echo "  make exec-localstack ARGS='curl http://localhost:4566/_localstack/health'"; \
		exit 1; \
	fi
	docker-compose exec localstack $(ARGS)

# Run database migrations
migrate:
	@echo "🔄 Running database migrations..."
	docker-compose exec api /app/.venv/bin/alembic upgrade head
	@echo "✅ Migrations complete"

# Create new migration (usage: make migrate-create MSG="description")
migrate-create:
	@if [ -z "$(MSG)" ]; then \
		echo "❌ Error: MSG parameter required"; \
		echo "Usage: make migrate-create MSG='your migration description'"; \
		exit 1; \
	fi
	@echo "📝 Creating migration: $(MSG)"
	docker-compose exec api /app/.venv/bin/alembic revision --autogenerate -m "$(MSG)"

# Rollback last migration
migrate-rollback:
	@echo "⏪ Rolling back last migration..."
	docker-compose exec api /app/.venv/bin/alembic downgrade -1
	@echo "✅ Rollback complete"

# Show current migration status
migrate-status:
	@echo "📊 Current migration status:"
	docker-compose exec api /app/.venv/bin/alembic current
	@echo ""
	@echo "📜 Recent migration history:"
	docker-compose exec api /app/.venv/bin/alembic history --verbose | head -20

# Show running containers
ps:
	@echo "📊 Running containers:"
	docker-compose ps

# Check API health
health:
	@echo "🏥 Checking API health..."
	@curl -s http://localhost:8001/health | python -m json.tool || echo "❌ API not responding"

# Reset database (WARNING: deletes all data)
db-reset:
	@echo "⚠️  WARNING: This will delete ALL database data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "🗑️  Stopping services..."; \
		docker-compose down; \
		echo "🗑️  Removing database volume..."; \
		docker volume rm backend_postgres_data 2>/dev/null || true; \
		echo "🚀 Starting services..."; \
		$(MAKE) up-detach; \
		echo "⏳ Waiting for database to be ready..."; \
		sleep 5; \
		echo "🔄 Running migrations..."; \
		$(MAKE) migrate; \
		echo "✅ Database reset complete!"; \
	else \
		echo "❌ Database reset cancelled"; \
	fi

# Clean: stop and remove containers
clean:
	@echo "🧹 Cleaning up containers..."
	docker-compose down
	@echo "✅ Cleanup complete"

# Clean all: stop, remove containers AND volumes (deletes database)
clean-all:
	@echo "⚠️  WARNING: This will delete ALL data including database!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "🗑️  Removing all containers and volumes..."; \
		docker-compose down -v; \
		echo "✅ Complete cleanup done!"; \
	else \
		echo "❌ Cleanup cancelled"; \
	fi

# Run all checks and auto-fix (like pre-commit hook)
check:
	@echo "🔍 Running all code quality checks with auto-fix..."
	@echo ""
	@echo "📝 Step 1/3: Running isort (fixing imports)..."
	uv run isort --profile black --line-length 100 . \
		--skip .venv --skip alembic/versions --skip build --skip dist
	@echo ""
	@echo "🎨 Step 2/3: Running black (formatting code)..."
	uv run black --line-length 100 . \
		--exclude '/(\.venv|alembic/versions|build|dist|\.git|__pycache__)/'
	@echo ""
	@echo "⚡ Step 3/3: Running ruff (fixing linting issues)..."
	uv run ruff check --fix . \
		--exclude .venv --exclude alembic/versions --exclude build --exclude dist --exclude __pycache__
	@echo ""
	@echo "✅ All checks complete! Code is formatted and linted."

# Linting and code quality checks
lint:
	@echo "🔍 Running linting checks..."
	@echo ""
	@echo "📝 Running isort (import sorting check)..."
	uv run isort --check-only --profile black --line-length 100 . \
		--skip .venv --skip alembic/versions --skip build --skip dist || true
	@echo ""
	@echo "🎨 Running black (code formatting check)..."
	uv run black --check --line-length 100 . \
		--exclude '/(\.venv|alembic/versions|build|dist|\.git|__pycache__)/' || true
	@echo ""
	@echo "⚡ Running ruff (linting)..."
	uv run ruff check . \
		--exclude .venv --exclude alembic/versions --exclude build --exclude dist --exclude __pycache__ || true
	@echo ""
	@echo "✅ Linting checks complete!"

# Linting with auto-fix
lint-fix:
	@echo "🔧 Running linting with auto-fix..."
	@echo ""
	@echo "📝 Running isort (fixing imports)..."
	uv run isort --profile black --line-length 100 . \
		--skip .venv --skip alembic/versions --skip build --skip dist
	@echo ""
	@echo "🎨 Running black (formatting code)..."
	uv run black --line-length 100 . \
		--exclude '/(\.venv|alembic/versions|build|dist|\.git|__pycache__)/'
	@echo ""
	@echo "⚡ Running ruff (fixing issues)..."
	uv run ruff check --fix . \
		--exclude .venv --exclude alembic/versions --exclude build --exclude dist --exclude __pycache__
	@echo ""
	@echo "✅ Linting fixes applied!"

# Format code (black + isort only, no ruff)
format:
	@echo "🎨 Formatting code..."
	@echo ""
	@echo "📝 Running isort..."
	uv run isort --profile black --line-length 100 . \
		--skip .venv --skip alembic/versions --skip build --skip dist
	@echo ""
	@echo "🎨 Running black..."
	uv run black --line-length 100 . \
		--exclude '/(\.venv|alembic/versions|build|dist|\.git|__pycache__)/'
	@echo ""
	@echo "✅ Code formatted!"

# Quick development cycle: rebuild and restart
dev-restart: build down up-detach migrate
	@echo "✅ Development environment restarted!"

# Quick development cycle with LocalStack: rebuild and restart
dev-restart-local: build down up-local migrate
	@echo "✅ Development environment restarted with LocalStack!"

# First time setup (runs in detached mode)
setup: build up-detach
	@echo "⏳ Waiting for services to be ready..."
	@sleep 5
	@echo "🔄 Running migrations..."
	@$(MAKE) migrate
	@echo ""
	@echo "✅ Setup complete!"
	@echo ""
	@echo "🎉 Your development environment is ready!"
	@echo ""
	@echo "📊 Service URLs:"
	@echo "  - API:       http://localhost:8000"
	@echo "  - API Docs:  http://localhost:8000/docs"
	@echo ""
	@echo "📝 Useful commands:"
	@echo "  - View logs:  make logs"
	@echo "  - Open shell: make shell"
	@echo "  - Stop:       make down"

# First time setup with LocalStack (recommended for local development)
setup-local: build up-local
	@echo "⏳ Waiting for services to be ready..."
	@sleep 8
	@echo "🔄 Running migrations..."
	@$(MAKE) migrate
	@echo "🧪 Testing LocalStack..."
	@$(MAKE) localstack-test
	@echo ""
	@echo "✅ Setup complete with LocalStack!"
	@echo ""
	@echo "🎉 Your local development environment is ready!"
	@echo ""
	@echo "📊 Service URLs:"
	@echo "  - API:        http://localhost:8001"
	@echo "  - API Docs:   http://localhost:8001/docs"
	@echo "  - LocalStack: http://localhost:4566"
	@echo ""
	@echo "📝 Useful commands:"
	@echo "  - View logs:      make logs-local"
	@echo "  - Test S3:        make localstack-test"
	@echo "  - LocalStack logs: make localstack-logs"
	@echo "  - Open shell:     make shell"
	@echo "  - Stop:           make down"

