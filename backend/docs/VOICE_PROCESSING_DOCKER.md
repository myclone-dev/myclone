# Voice Processing Docker Deployment Guide

## Overview

The voice processing service is fully containerized with FFmpeg and all dependencies included. It operates as an **API-based asynchronous job processing system** using NATS for job queuing and PostgreSQL for shared state management.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Docker Compose Stack                                │
├─────────────────┬──────────────────────┬──────────────────────────────┤
│     Backend     │   Voice Workers      │     Shared Storage           │
│   (FastAPI)     │   (2 replicas)       │                              │
│                 │                       │                              │
│ Port: 8001      │ No exposed ports     │ Volumes:                     │
│ API endpoints   │ NATS consumers       │ - uploads/                   │
│ Job submission  │ FFmpeg processing    │ - output/raw/                │
│ PostgreSQL jobs │ PostgreSQL updates   │ - output/segments/           │
└─────────────────┴──────────────────────┴──────────────────────────────┘
                           │
                           ↓
                  ┌────────────────┐
                  │  PostgreSQL    │
                  │  (Job State)   │
                  └────────────────┘
                           │
                           ↓
                  ┌────────────────┐
                  │  NATS Server   │
                  │  (Job Queue)   │
                  │  Port: 4223    │
                  └────────────────┘
```

## Services

### Backend Service
- **Purpose**: Main FastAPI application with voice processing API
- **Port**: 8001
- **Endpoints**:
  - `POST /api/v1/voice-processing/upload` - Upload files
  - `POST /api/v1/voice-processing/jobs` - Create jobs from YouTube URLs
  - `GET /api/v1/voice-processing/jobs/{job_id}` - Get job status
  - `GET /api/v1/voice-processing/jobs` - List jobs
- **Dependencies**: Poetry-managed
- **Database**: PostgreSQL for job state

### Voice Processing Workers
- **Purpose**: Background workers for audio/video processing
- **Port**: None (NATS consumers)
- **Replicas**: 2 workers (configurable via `docker-compose.local.yml`)
- **Dependencies**: FFmpeg + Python packages (pip-based)
- **Job Queue**: NATS JetStream on port 4223
- **Database**: PostgreSQL for job state updates

### NATS Server (External)
- **Purpose**: Job queue and message broker
- **Port**: 4223
- **Location**: Run separately via `nats-server -p 4223 -js`

## Quick Start

### 1. Start NATS Server

```bash
# Install NATS (if not already installed)
# macOS: brew install nats-server
# Linux: Download from https://nats.io/download/

# Start NATS with JetStream enabled
nats-server -p 4223 -js
```

### 2. Build and Start Services

```bash
# Development environment with PostgreSQL
docker-compose -f docker-compose.local.yml up -d

# Production environment
docker-compose up -d
```

### 3. Process Your First Video

```bash
# Upload a video file and process it
curl -X POST http://localhost:8001/api/v1/voice-processing/upload \
  -F "file=@/path/to/video.mp4" \
  -F "profile=elevenlabs" \
  -F "output_format=wav" \
  -F "multiple_segments=false"

# Response:
# {
#   "job_id": "job_abc123",
#   "status": "queued",
#   "message": "Job created and queued for processing"
# }
```

### 4. Check Job Status

```bash
# Get job status and progress
curl http://localhost:8001/api/v1/voice-processing/jobs/job_abc123

# Response:
# {
#   "job_id": "job_abc123",
#   "status": "completed",
#   "result": {
#     "voice_files": [
#       {
#         "file_path": "/app/voice_processing/output/raw/video_extracted.wav",
#         "duration": 120,
#         "quality_score": 0.5
#       }
#     ]
#   }
# }
```

## API Usage

### Upload and Process Files

```bash
# Single file processing
curl -X POST http://localhost:8001/api/v1/voice-processing/upload \
  -F "file=@video.mp4" \
  -F "profile=elevenlabs" \
  -F "output_format=wav"

# With time range extraction (10s-20s)
curl -X POST http://localhost:8001/api/v1/voice-processing/upload \
  -F "file=@video.mp4" \
  -F "start_time=10" \
  -F "end_time=20"

# Multiple segments (extract 3 best quality 60s segments)
curl -X POST http://localhost:8001/api/v1/voice-processing/upload \
  -F "file=@video.mp4" \
  -F "multiple_segments=true" \
  -F "max_segments=3"
```

### Process YouTube Videos

```bash
# Create job from YouTube URL
curl -X POST http://localhost:8001/api/v1/voice-processing/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "VOICE_EXTRACTION",
    "input_source": "https://youtube.com/watch?v=xyz",
    "profile": "elevenlabs",
    "output_format": "wav",
    "multiple_segments": false
  }'
```

### Job Management

```bash
# List all jobs
curl http://localhost:8001/api/v1/voice-processing/jobs

# List jobs for specific user
curl "http://localhost:8001/api/v1/voice-processing/jobs?user_id=user123"

# Get job progress details
curl http://localhost:8001/api/v1/voice-processing/jobs/job_abc123/progress

# Retry failed job
curl -X POST http://localhost:8001/api/v1/voice-processing/jobs/job_abc123/retry

# Cancel pending job
curl -X DELETE http://localhost:8001/api/v1/voice-processing/jobs/job_abc123
```

## File Storage Structure

### Input Files
- **Location**: `./uploads/`
- **Format**: `{timestamp}_{original_filename}`
- **Example**: `/app/uploads/20251002_130000_video.mp4`

### Output Files

#### Single File Processing
- **Location**: `./app/voice_processing/output/raw/`
- **Format**: `{filename}_extracted.wav` or `{filename}_processed.wav`
- **Example**: `/app/voice_processing/output/raw/video_extracted.wav`

#### Multiple Segments
- **Location**: `./app/voice_processing/output/segments/`
- **Format**: `{filename}_segment_{N}.wav`
- **Example**:
  - `/app/voice_processing/output/segments/video_segment_1.wav`
  - `/app/voice_processing/output/segments/video_segment_2.wav`
  - `/app/voice_processing/output/segments/video_segment_3.wav`

### Accessing Output Files

```bash
# List processed files in raw directory
docker exec persona_backend_dev ls -lh /app/voice_processing/output/raw/

# List segment files
docker exec persona_backend_dev ls -lh /app/voice_processing/output/segments/

# Copy file from container to host
docker cp persona_backend_dev:/app/voice_processing/output/raw/video_extracted.wav ./

# View worker logs
docker-compose -f docker-compose.local.yml logs -f voice-processing-worker
```

## Job State Management

### PostgreSQL Database

All job state is stored in PostgreSQL table `voice_processing_jobs`:

```sql
-- Key columns:
job_id VARCHAR(255)          -- Unique job identifier
status VARCHAR(50)           -- pending, processing, completed, failed, cancelled
request_data JSONB           -- Original job request (input_source, profile, etc.)
result JSONB                 -- Processing results including voice_files array
current_stage VARCHAR(100)   -- Current processing stage
progress_percentage INTEGER  -- 0-100
error_message TEXT           -- Error details if failed
created_at TIMESTAMP         -- Job creation time
started_at TIMESTAMP         -- Processing start time
completed_at TIMESTAMP       -- Processing completion time
```

### Retrieving Files by job_id

```python
# Python example - get output files from database
from app.voice_processing.src.api.job_repository import JobRepository
from app.database.models.database import async_session_maker

async with async_session_maker() as session:
    repo = JobRepository(session)
    job = await repo.get_job_by_id("job_abc123")

    if job.result:
        for voice_file in job.result.get('voice_files', []):
            file_path = voice_file['file_path']
            # /app/voice_processing/output/segments/video_segment_1.wav
            duration = voice_file['duration']  # 60 seconds
            quality_score = voice_file['quality_score']  # 0.35
```

## Configuration

### Environment Variables

```bash
# .env file
NATS_URL=nats://host.docker.internal:4223  # NATS server URL
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/db  # PostgreSQL
```

### Worker Scaling

```yaml
# docker-compose.local.yml
voice-processing-worker:
  deploy:
    replicas: 2  # Increase for more parallel processing
```

### Profiles

- **elevenlabs**: Optimized for Eleven Labs voice cloning
  - Duration: 60 seconds per segment
  - Quality: RMS-based selection
  - Format: WAV (default)

- **generic**: General-purpose audio processing

## Deployment

### Local Development

```bash
# 1. Start NATS
nats-server -p 4223 -js

# 2. Start services
docker-compose -f docker-compose.local.yml up -d

# 3. Check worker status
docker-compose -f docker-compose.local.yml ps

# 4. Monitor worker logs
docker-compose -f docker-compose.local.yml logs -f voice-processing-worker
```

### Production Deployment

```bash
# Build services
docker-compose build

# Run migrations
docker exec persona_backend alembic upgrade head

# Start services
docker-compose up -d

# Scale workers
docker-compose up -d --scale voice-processing-worker=4
```

## Monitoring and Maintenance

### Health Checks

```bash
# Check API health
curl http://localhost:8001/api/v1/voice-processing/health

# Response:
# {
#   "status": "healthy",
#   "nats_connected": true,
#   "service": "voice-processing"
# }

# Check system stats
curl http://localhost:8001/api/v1/voice-processing/stats

# Response:
# {
#   "total_jobs": 150,
#   "pending_jobs": 5,
#   "processing_jobs": 2,
#   "completed_jobs": 140,
#   "failed_jobs": 3,
#   "nats_connected": true
# }
```

### Log Management

```bash
# View backend logs
docker logs persona_backend_dev -f

# View worker logs
docker-compose -f docker-compose.local.yml logs -f voice-processing-worker

# View NATS logs
# Check NATS terminal where it's running

# Check job-specific logs from database
curl http://localhost:8001/api/v1/voice-processing/jobs/job_abc123
```

### Storage Management

```bash
# Check disk usage
docker exec persona_backend_dev df -h /app/voice_processing/output

# Clean old uploaded files (manual)
find ./uploads -mtime +7 -type f -delete

# Clean temp files
docker exec persona_backend_dev rm -rf /app/voice_processing/temp/*
```

## Troubleshooting

### Common Issues

1. **Jobs stuck in "queued" status**
   ```bash
   # Check NATS connection
   curl http://localhost:8001/api/v1/voice-processing/health

   # Restart NATS server
   nats-server -p 4223 -js

   # Check worker logs
   docker-compose logs voice-processing-worker
   ```

2. **Workers not processing jobs**
   ```bash
   # Check worker count
   docker-compose ps | grep voice-processing-worker

   # Restart workers
   docker-compose restart voice-processing-worker

   # Check PostgreSQL connection
   docker exec persona_postgres_dev psql -U persona_user -d persona_db -c "SELECT COUNT(*) FROM voice_processing_jobs WHERE status='pending';"
   ```

3. **Permission issues with output files**
   ```bash
   # Both backend and workers run as appuser (UID 1000)
   # Check file ownership
   docker exec persona_backend_dev ls -la /app/voice_processing/output/raw/

   # Files should be owned by appuser:appuser
   ```

4. **FFmpeg not found**
   ```bash
   # Verify FFmpeg in worker container
   docker-compose exec voice-processing-worker ffmpeg -version

   # Should show FFmpeg 4.x or later
   ```

### Performance Optimization

1. **Scale Workers**
   ```yaml
   # docker-compose.local.yml
   voice-processing-worker:
     deploy:
       replicas: 4  # Increase based on CPU cores
   ```

2. **Adjust NATS Settings**
   ```bash
   # Increase NATS max payload for large videos
   nats-server -p 4223 -js -m 8222 --max_payload 10485760
   ```

3. **Database Connection Pooling**
   - PostgreSQL connection pooling is handled by SQLAlchemy async engine
   - Default pool size is sufficient for most workloads

## Migration from CLI to API

### Key Differences

| Feature | CLI (Old) | API (Current) |
|---------|-----------|---------------|
| Invocation | `docker exec ... python -m src.cli.main` | `curl POST /api/v1/voice-processing/upload` |
| Processing | Synchronous | Asynchronous via NATS |
| State | In-memory (lost on restart) | PostgreSQL (persistent) |
| Scaling | Single container | Multiple workers |
| Output Dir | `/output/final/` | `/output/raw/` or `/output/segments/` |
| File Tracking | None | Database `result.voice_files` |

### Removed Components

- ❌ CLI commands (`src/cli/main.py`)
- ❌ `scripts/voice-processing.sh` wrapper
- ❌ `/output/final/` directory usage
- ❌ Quality assessor module
- ❌ Audio normalizer module

### New Components

- ✅ FastAPI endpoints in backend
- ✅ NATS job queue
- ✅ PostgreSQL job state
- ✅ Multiple worker processes
- ✅ Job retry mechanism
- ✅ Real-time progress tracking

## Security Considerations

1. **Container Security**
   - Runs as non-root user (`appuser`, UID 1000)
   - No exposed ports on workers
   - Limited filesystem access

2. **File Access**
   - Workers only access mounted volumes
   - Consistent UID/GID between backend and workers
   - No chmod operations needed

3. **Network Security**
   - Workers connect to NATS via Docker internal network
   - YouTube downloads use HTTPS only
   - No direct internet access from backend

## Backup and Recovery

### Backup Strategy

```bash
# Backup PostgreSQL job state
docker exec persona_postgres_dev pg_dump -U persona_user -d persona_db -t voice_processing_jobs > voice_jobs_backup.sql

# Backup processed audio files
tar czf voice_processing_output_$(date +%Y%m%d).tar.gz ./app/voice_processing/output/

# Backup uploads
tar czf uploads_$(date +%Y%m%d).tar.gz ./uploads/
```

### Recovery

```bash
# Restore PostgreSQL job state
docker exec -i persona_postgres_dev psql -U persona_user -d persona_db < voice_jobs_backup.sql

# Restore processed files
tar xzf voice_processing_output_20241202.tar.gz
```

This API-based architecture provides better scalability, reliability, and monitoring compared to the previous CLI-based approach.
