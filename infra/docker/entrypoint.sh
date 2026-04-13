#!/bin/bash
set -e

echo "🚀 Starting Expert Clone Backend..."

# Note: Migrations are NOT run automatically.
# Operators must run migrations explicitly via:
#   - Local: docker-compose exec api alembic upgrade head
#   - ECS: Run the migrations task before deployment
# The /health endpoint will verify DB connectivity
# ECS health checks will determine when container is ready

echo "🚀 Starting FastAPI application..."
exec "$@"