# 🚀 Digital Clone POC - Deployment Guide

## Overview

This guide provides instructions for deploying the Digital Clone POC application using Docker and Docker Compose. The application is fully containerized and includes all necessary services.

## Architecture

The application consists of the following services:
- **Frontend**: React app served by Nginx (Port 3000)
- **Backend**: FastAPI application (Port 8000)
- **PostgreSQL**: Database with pgvector extension (Port 5432)
- **Redis**: Caching and session management (Port 6379)
- **pgAdmin**: Database management UI (Port 5050) - Optional

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM available
- 10GB+ disk space

## Quick Start

### 1. Clone the Repository
```bash
git clone <your-repo-url>
cd digital-clone-poc
```

### 2. Environment Configuration
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API keys
nano .env
```

Required environment variables:
```env
# Database
POSTGRES_USER=persona_user
POSTGRES_PASSWORD=persona_pass
POSTGRES_DB=persona_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# API Keys (Optional but recommended)
OPENAI_API_KEY=your_openai_key_here
EXA_API_KEY=your_exa_key_here  # Optional

# pgAdmin (Optional)
PGADMIN_EMAIL=admin@persona.com
PGADMIN_PASSWORD=admin
```

### 3. Build and Start Services

Using Make (Recommended):
```bash
# Build all images
make build

# Start all services
make up

# Check status
make status
```

Using Docker Compose directly:
```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f
```

### 4. Verify Deployment

Once services are running, access:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **pgAdmin**: http://localhost:5050

## External Data Ingestion API

The application exposes an API endpoint for ingesting data from external sources without using ScrapingDog.

### API Endpoint
```
POST http://localhost:8000/api/v1/external-data/ingest
```

### Supported Data Types
- LinkedIn profiles
- Twitter/X data
- GitHub profiles
- Custom data sources

### Example: LinkedIn Data Ingestion

```bash
curl -X POST http://localhost:8000/api/v1/external-data/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "your-persona-uuid",
    "data_type": "linkedin",
    "linkedin_data": {
      "name": "John Doe",
      "headline": "Senior Software Engineer",
      "about": "Experienced developer...",
      "experience": [
        {
          "company": "TechCorp",
          "title": "Senior Engineer",
          "description": "Led development of..."
        }
      ],
      "skills": ["Python", "AI", "ML"],
      "posts": [
        {
          "text": "Excited about the latest AI developments...",
          "date": "2024-01-15"
        }
      ]
    },
    "process_immediately": true
  }'
```

### Example: Twitter Data Ingestion

```bash
curl -X POST http://localhost:8000/api/v1/external-data/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "your-persona-uuid",
    "data_type": "twitter",
    "twitter_data": {
      "username": "johndoe",
      "name": "John Doe",
      "bio": "AI enthusiast and developer",
      "tweets": [
        {
          "text": "Just deployed a new ML model...",
          "date": "2024-01-15",
          "likes": 45,
          "retweets": 12
        }
      ],
      "followers_count": 5000
    },
    "process_immediately": true
  }'
```

### Example: Custom Data Ingestion

```bash
curl -X POST http://localhost:8000/api/v1/external-data/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "persona_id": "your-persona-uuid",
    "data_type": "custom",
    "custom_data": {
      "source_name": "blog_posts",
      "content_type": "articles",
      "data": {
        "articles": [
          {
            "title": "Understanding RAG Systems",
            "content": "RAG systems combine retrieval and generation...",
            "date": "2024-01-10"
          }
        ]
      }
    },
    "process_immediately": true
  }'
```

### Check Ingestion Status

```bash
curl http://localhost:8000/api/v1/external-data/{persona_id}/status
```

## Common Operations

### Create a New Persona
```bash
curl -X POST http://localhost:8000/api/v1/personas \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Smith",
    "role": "AI Researcher",
    "company": "AI Labs",
    "description": "Leading researcher in NLP"
  }'
```

### View Logs
```bash
# All services
make logs

# Specific service
make logs-backend
make logs-frontend
make logs-postgres
```

### Access Container Shell
```bash
# Backend shell
make shell-backend

# PostgreSQL shell
make shell-postgres
```

### Backup Database
```bash
make backup-db
```

### Restore Database
```bash
make restore-db
```

## Production Deployment

### Using Docker Swarm
```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml persona-stack

# Check services
docker service ls
```

### Using Kubernetes
```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: persona-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: persona-backend
  template:
    metadata:
      labels:
        app: persona-backend
    spec:
      containers:
      - name: backend
        image: persona-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: persona-secrets
              key: database-url
```

### Environment-Specific Configurations

Create environment-specific compose files:
```bash
# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Staging
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d
```

## Monitoring & Maintenance

### Health Checks
```bash
# Backend health
curl http://localhost:8000/health

# Frontend health
curl http://localhost:3000

# Database health
docker-compose exec postgres pg_isready
```

### Resource Usage
```bash
# Check container stats
docker stats

# Check disk usage
docker system df
```

### Cleanup
```bash
# Stop and remove containers
make down

# Clean all Docker resources
make clean

# Full reset (removes data)
make reset
```

## Troubleshooting

### Common Issues

1. **Port conflicts**
   ```bash
   # Check if ports are in use
   lsof -i :3000
   lsof -i :8000
   lsof -i :5432
   
   # Change ports in docker-compose.yml if needed
   ```

2. **Database connection issues**
   ```bash
   # Check PostgreSQL logs
   docker-compose logs postgres
   
   # Verify connection
   docker-compose exec postgres psql -U persona_user -d persona_db -c "SELECT 1"
   ```

3. **Permission issues**
   ```bash
   # Fix volume permissions
   sudo chown -R $USER:$USER ./uploads ./logs
   ```

4. **Memory issues**
   ```bash
   # Increase Docker memory limit
   # Docker Desktop: Preferences > Resources > Memory
   
   # Or use docker-compose limits
   # Add to service in docker-compose.yml:
   deploy:
     resources:
       limits:
         memory: 2G
   ```

## Security Considerations

1. **Environment Variables**: Never commit `.env` files with real credentials
2. **Network Security**: Use Docker networks to isolate services
3. **Data Encryption**: Enable SSL/TLS for production deployments
4. **Access Control**: Implement proper authentication and authorization
5. **Regular Updates**: Keep Docker images and dependencies updated

## Support

For issues or questions:
1. Check the logs: `make logs`
2. Review the documentation in `/docs`
3. Check service status: `make status`
4. Restart services: `make restart`

## License

[Your License Here]

---
*Last Updated: December 2024*