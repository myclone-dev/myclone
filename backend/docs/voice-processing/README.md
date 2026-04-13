# Voice Processing System Documentation

This directory contains comprehensive documentation for the voice processing system, covering job types, worker architecture, deployment, and usage.

## 📚 Documentation Index

### Core Documentation

1. **[JOB_TYPES_REFERENCE.md](./JOB_TYPES_REFERENCE.md)** - Complete reference for all 7 job types
   - Request/response formats
   - Processing stages
   - Use cases and examples
   - Error handling

2. **[WORKER_ARCHITECTURE.md](./WORKER_ARCHITECTURE.md)** - Worker system architecture
   - Internal architecture diagrams
   - Handler responsibilities
   - Processing flows
   - Scalability and monitoring

3. **[VOICE_PROCESSING_DEPLOYMENT_SUMMARY.md](./VOICE_PROCESSING_DEPLOYMENT_SUMMARY.md)** - Docker deployment guide
   - Container setup
   - API usage
   - File storage
   - Troubleshooting

### Specialized Guides

4. **[YOUTUBE_TRANSCRIPT_INGESTION.md](./YOUTUBE_TRANSCRIPT_INGESTION.md)** - YouTube ingestion details
5. **[DOCUMENT_PROCESSING_IMPLEMENTATION.md](./DOCUMENT_PROCESSING_IMPLEMENTATION.md)** - PDF processing
6. **[voice-cloning-best-practices.txt](./voice-cloning-best-practices.txt)** - Voice cloning optimization

## 🎯 Quick Navigation by Use Case

### I want to extract voice samples for cloning
→ See [JOB_TYPES_REFERENCE.md - VOICE_EXTRACTION](./JOB_TYPES_REFERENCE.md#1-voice_extraction)

### I want to process PDF documents
→ See [JOB_TYPES_REFERENCE.md - PDF_PARSING](./JOB_TYPES_REFERENCE.md#4-pdf_parsing)

### I want to transcribe audio/video files
→ See [JOB_TYPES_REFERENCE.md - AUDIO_TRANSCRIPTION](./JOB_TYPES_REFERENCE.md#5-audio_transcription)
→ See [JOB_TYPES_REFERENCE.md - VIDEO_TRANSCRIPTION](./JOB_TYPES_REFERENCE.md#6-video_transcription)

### I want to ingest YouTube videos for RAG
→ See [JOB_TYPES_REFERENCE.md - YOUTUBE_INGESTION](./JOB_TYPES_REFERENCE.md#7-youtube_ingestion)

### I want to understand the system architecture
→ See [WORKER_ARCHITECTURE.md](./WORKER_ARCHITECTURE.md)

### I want to deploy the system
→ See [VOICE_PROCESSING_DEPLOYMENT_SUMMARY.md](./VOICE_PROCESSING_DEPLOYMENT_SUMMARY.md)

## 🚀 Quick Start

### 1. Extract Voice from YouTube Video

```bash
curl -X POST http://localhost:8001/api/v1/voice-processing/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "VOICE_EXTRACTION",
    "input_source": "https://youtube.com/watch?v=xyz",
    "user_id": "uuid-string",
    "output_format": "wav",
    "multiple_segments": true,
    "max_segments": 3
  }'
```

### 2. Parse PDF Document

```bash
curl -X POST http://localhost:8001/api/v1/voice-processing/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "PDF_PARSING",
    "input_source": "s3://bucket/document.pdf",
    "user_id": "uuid-string",
    "persona_id": "uuid-string",
    "chunk_size": 1000,
    "overlap": 200
  }'
```

### 3. Ingest YouTube for RAG

```bash
curl -X POST http://localhost:8001/api/v1/voice-processing/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "YOUTUBE_INGESTION",
    "input_source": "https://youtube.com/watch?v=xyz",
    "user_id": "uuid-string",
    "persona_id": "uuid-string"
  }'
```

### 4. Check Job Status

```bash
curl http://localhost:8001/api/v1/voice-processing/jobs/{job_id}
```

## 📋 Supported Job Types

| Job Type | Purpose | Input | Output |
|----------|---------|-------|--------|
| **VOICE_EXTRACTION** | Extract voice samples | Video/Audio/YouTube | Audio files (WAV/MP3) |
| **TRANSCRIPT_EXTRACTION** | Extract transcripts | Video/Audio | Text transcript |
| **COMBINED_PROCESSING** | Voice + Transcript | Video/Audio/YouTube | Audio + Text |
| **PDF_PARSING** | Parse & chunk PDFs | PDF file/URL | Text chunks + RAG |
| **AUDIO_TRANSCRIPTION** | Transcribe audio | Audio file | Transcript + RAG |
| **VIDEO_TRANSCRIPTION** | Transcribe video | Video file | Transcript + RAG |
| **YOUTUBE_INGESTION** | YouTube to RAG | YouTube URL | Enriched chunks + RAG |

## 🏗️ System Architecture

### High-Level Overview

```
┌─────────���────────────────────────────────────────────────────────────┐
│                     Voice Processing System                           │
└──────────────────────────────────────────────────────────────────────┘

┌─────────────┐         ┌──────────────┐         ┌──��──────────────┐
│   Client    │────────▶│   FastAPI    │────────▶│  PostgreSQL     │
│ Application │         │   Backend    │         │  (Job State)    │
└─────────────┘         └──────┬───────┘         └─────────────────┘
                               │
                               │ Publish Job
                               ▼
                        ┌──────────────┐
                        │     NATS     │
                        │  JetStream   │
                        │   (Queue)    │
                        └──────┬───────┘
                               │
                    ┌──────────┼──────────┐
                    │          │          ���
                    ▼          ▼          ▼
            ┌───────────�� ┌───────────┐ ┌───���───────┐
            │  Worker 1 │ │  Worker 2 │ │  Worker N │
            └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
                  │             │             │
                  └─────────────┼─────────────┘
                                │
                    ┌───────────┼───────────┐
                    │           │           │
                    ▼           ▼           ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │     PDF     │ │   YouTube   │ │ Audio/Video │
            │   Handler   │ │   Handler   │ │   Handler   │
            └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
                   │               │               │
                   └───────────────┼───────────────┘
                                   │
            ┌──────────────────────┼──────────────────────┐
            │                      │                      │
            ▼                      ▼                      ▼
    ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
    │  S3 Storage  │      │   OpenAI     │      │  AssemblyAI  │
    │ (Files/RAG)  │      │ (Embeddings) │      │(Transcription)│
    └──────────────┘      └──────────────┘      └──────────────┘
            │                      │                      │
            └──────────────────────┼──────────────────────┘
                                   │
                                   ▼
                        ┌──────────────────┐
                        │   RAG System     │
                        │ (Vector Store)   │
                        └──────────────────┘
```

### Component Breakdown

#### 1. **Client Layer**
- REST API clients (web apps, mobile apps)
- Direct HTTP requests to FastAPI backend
- Real-time progress monitoring via polling

#### 2. **API Layer (FastAPI)**
- **Endpoints**:
  - `POST /api/v1/voice-processing/jobs` - Create new jobs
  - `GET /api/v1/voice-processing/jobs/{job_id}` - Get job status
  - `GET /api/v1/voice-processing/jobs` - List jobs with filters
  - `POST /api/v1/voice-processing/jobs/{job_id}/retry` - Retry failed jobs
- **Responsibilities**:
  - Request validation
  - Job creation in PostgreSQL
  - NATS message publishing
  - Status queries and monitoring

#### 3. **Message Queue (NATS JetStream)**
- **Purpose**: Reliable job distribution and retry logic
- **Features**:
  - Durable message storage
  - Automatic retry on failure (max 3 attempts)
  - 5-minute ACK timeout
  - Pull-based consumption (workers fetch jobs)
- **Configuration**:
  - Stream: `VOICE_JOBS`
  - Consumer: `voice_workers` (shared across workers)
  - Max pending per worker: 10 jobs

#### 4. **Worker Pool**
- **Scalability**: 1-N worker instances (horizontally scalable)
- **Concurrency**: Each worker processes 1 job at a time
- **Load Distribution**: NATS automatically distributes jobs
- **Components**:
  - **VoiceProcessingWorker**: Main worker class
  - **JobService**: NATS communication and state management
  - **ProgressTracker**: Real-time progress updates

#### 5. **Handler Layer (Processors)**
Specialized handlers for different job types:

- **`pdf_handler.py`**
  - Downloads PDFs from S3/HTTP
  - Parses with Marker API (DataLab)
  - Creates semantic chunks
  - Ingests to RAG system

- **`youtube_handler.py`**
  - Extracts video metadata
  - Downloads transcripts
  - Enriches with OpenAI (summaries + keywords)
  - Stores in database and RAG

- **`audio_video_handlers.py`**
  - Transcribes with AssemblyAI
  - Creates timestamped chunks
  - Ingests to RAG system

- **`download_utils.py`**
  - Generic file downloader
  - AWS signed URL support
  - Progress tracking for large files

#### 6. **External Services**
- **S3 Storage**: 
  - Input files (uploaded documents)
  - Output files (processed audio, segments)
  - Permanent storage with versioning
  
- **OpenAI API**:
  - Text embeddings (text-embedding-3-small)
  - Content summarization (GPT-4)
  - Keyword extraction
  
- **AssemblyAI API**:
  - Audio/video transcription
  - Speaker detection
  - Timestamp generation
  
- **Marker API (DataLab)**:
  - PDF to Markdown conversion
  - OCR for scanned documents
  - Table and image extraction

#### 7. **Data Storage**

**PostgreSQL**:
- `voice_processing_jobs`: Job state and results
- `youtube_videos`: Video metadata
- `persona_data_sources`: Content-persona links
- `documents`: Document metadata

**Vector Database (via RAG)**:
- Embedded text chunks
- Similarity search indices
- Persona knowledge bases

### Data Flow Example: YouTube Ingestion

```
1. Client Request
   └─▶ POST /api/v1/voice-processing/jobs
       {
         "job_type": "YOUTUBE_INGESTION",
         "input_source": "https://youtube.com/watch?v=xyz",
         "user_id": "uuid",
         "persona_id": "uuid"
       }

2. API Layer
   └─▶ Create job in PostgreSQL (status: PENDING)
   └─▶ Publish to NATS queue
   └─▶ Return job_id to client

3. NATS Queue
   └─▶ Store message durably
   └─▶ Make available to workers

4. Worker Pulls Job
   └─▶ Update status: PROCESSING
   └─▶ Create ProgressTracker
   └─▶ Route to youtube_handler

5. YouTube Handler
   ├─▶ [0-10%] Validate URL and user_id
   ├─▶ [10-30%] Extract metadata and transcript
   ├─▶ [30-50%] Chunk transcript (400-800 tokens)
   ├─▶ [50-70%] OpenAI enrichment (summaries + keywords)
   ├─▶ [70-80%] Store in youtube_videos table
   ├─▶ [80-98%] Generate embeddings and ingest to RAG
   └─▶ [98-100%] Link to persona and cleanup

6. Result Storage
   ├─▶ Update PostgreSQL (status: COMPLETED, result: JSON)
   ├─▶ Vector embeddings in RAG system
   └─▶ PersonaDataSource link created

7. Client Receives Result
   └─▶ Poll GET /jobs/{job_id}
   └─▶ Access transcript chunks and metadata
```

### Scalability Architecture

#### Horizontal Scaling
```
Load Balancer
    │
    ├─▶ FastAPI Instance 1
    ├─▶ FastAPI Instance 2
    └─▶ FastAPI Instance N
             │
             ▼
        NATS Cluster
        (3+ nodes)
             │
    ┌────────┼────────┐
    │        │        │
Worker 1  Worker 2  Worker N
    │        │        │
    └────────┼────────┘
             │
      Shared Resources:
      - PostgreSQL (Primary + Replicas)
      - S3 (Unlimited capacity)
      - Redis (Caching layer)
```

#### Performance Characteristics
- **API Response Time**: <100ms for job creation
- **Worker Throughput**: 1 job/worker (concurrent workers scale linearly)
- **Queue Capacity**: Unlimited (NATS persistent storage)
- **Database Load**: Read-heavy (job status queries) + Write spikes (progress updates)

#### Fault Tolerance
- **Worker Failure**: Job automatically requeued (NAK with delay)
- **NATS Failure**: Messages persisted to disk, resume on restart
- **Database Failure**: Retry logic with exponential backoff
- **External API Failure**: Retryable errors (3 attempts max)

**Workers**: Multiple instances process jobs concurrently
**Handlers**: Specialized processors for each job type
- `pdf_handler.py` - PDF processing
- `youtube_handler.py` - YouTube ingestion
- `audio_video_handlers.py` - Audio/video transcription

## 🔄 Processing Flow

1. **Job Submission** → API creates job in PostgreSQL (PENDING)
2. **Queue** → Job published to NATS JetStream
3. **Consumption** → Worker fetches job (PROCESSING)
4. **Execution** → Handler processes with progress tracking
5. **Storage** → Results stored in S3 and PostgreSQL
6. **Completion** → Job status updated (COMPLETED/FAILED)

## 📊 Job States

- **PENDING**: Job created, not yet queued
- **QUEUED**: In NATS queue, waiting for worker
- **PROCESSING**: Actively being processed
- **COMPLETED**: Successfully finished
- **FAILED**: Failed with error message
- **CANCELLED**: Manually cancelled

## 🛠️ Development

### Project Structure

```
workers/voice_processing/
├── worker.py                    # Main worker class
├── processors/
│   ├── pdf_handler.py          # PDF processing
│   ├── youtube_handler.py      # YouTube ingestion
│   ├── audio_video_handlers.py # Audio/video transcription
│   ├── download_utils.py       # Download utilities
│   └── rag_ingestion.py        # RAG integration
├── extractors/
│   ├── audio_extractor.py      # Audio extraction (FFmpeg)
│   └── youtube_extractor.py    # YouTube downloads
└── utils/
    ├── progress.py             # Progress tracking
    └── config.py               # Configuration
```

### Key Dependencies

- **FFmpeg**: Audio/video processing
- **AssemblyAI**: Audio/video transcription
- **OpenAI**: Embeddings and enrichment
- **Marker API (DataLab)**: PDF parsing
- **NATS**: Job queue
- **PostgreSQL**: State management
- **S3**: File storage

## 📖 API Reference

### Create Job

```http
POST /api/v1/voice-processing/jobs
Content-Type: application/json

{
  "job_type": "VOICE_EXTRACTION",
  "input_source": "https://youtube.com/watch?v=xyz",
  "user_id": "uuid-string",
  ...
}
```

### Get Job Status

```http
GET /api/v1/voice-processing/jobs/{job_id}
```

### List Jobs

```http
GET /api/v1/voice-processing/jobs?user_id={uuid}&status=completed
```

### Retry Failed Job

```http
POST /api/v1/voice-processing/jobs/{job_id}/retry
```

### Cancel Job

```http
DELETE /api/v1/voice-processing/jobs/{job_id}
```

## 🔍 Monitoring

### Health Check

```bash
curl http://localhost:8001/api/v1/voice-processing/health
```

### System Stats

```bash
curl http://localhost:8001/api/v1/voice-processing/stats
```

### Worker Logs

```bash
docker-compose logs -f voice-processing-worker
```

## 🚀 Deployment

### Prerequisites

Before deploying the voice processing workers, ensure you have:

1. **Docker & Docker Compose** installed
2. **Network**: `myclone-network` created
3. **Dependencies running**:
   - PostgreSQL database (`rappo-review_db-1`)
   - NATS server (`myclone_nats`)
   - LocalStack for S3 (`myclone_localstack`) - optional but recommended
4. **Environment variables** configured in `.env` file

### Required Environment Variables

Create a `.env` file in the project root with:

```bash
# Database Configuration
POSTGRES_HOST=rappo-review_db-1
POSTGRES_PORT=5432
POSTGRES_DB=your_database
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# NATS Configuration
NATS_URL=nats://myclone_nats:4222

# S3 Configuration (LocalStack or AWS)
AWS_ENDPOINT_URL=http://myclone_localstack:4566  # For LocalStack
AWS_ACCESS_KEY_ID=test                            # LocalStack default
AWS_SECRET_ACCESS_KEY=test                        # LocalStack default
AWS_S3_BUCKET=voice-processing
AWS_REGION=us-east-1

# API Keys (Required for Processing)
DATALAB_API_KEY=your_marker_api_key              # For PDF parsing
OPENAI_API_KEY=your_openai_key                   # For embeddings & enrichment
ASSEMBLYAI_API_KEY=your_assemblyai_key           # For audio/video transcription

# Worker Configuration
WORKER_COUNT=2                                    # Number of worker instances
MAX_FILE_SIZE_MB=100                              # Max upload size
```

### Deployment Methods

#### Method 1: Automated Deployment (Recommended)

Use the provided deployment script:

```bash
# Make script executable
chmod +x deploy_voice_worker.sh

# Run deployment
./deploy_voice_worker.sh
```

**What the script does:**
1. ✅ Stops and removes existing worker container
2. 🔨 Builds Docker image from `docker/Dockerfile.voice-processing`
3. 🔍 Detects LocalStack IP address automatically
4. 🚀 Starts worker container with proper configuration
5. 📊 Shows container status and helpful commands

**Expected Output:**
```
🚀 Deploying Voice Processing Worker...
================================================
🛑 Stopping existing container (if any)...
🔨 Building Docker image...
✅ Found LocalStack at IP: 172.18.0.3
🚀 Starting Voice Processing Worker container...
   Using AWS endpoint: http://172.18.0.3:4566

✅ Voice Processing Worker deployed successfully!
================================================

📊 Container Status:
NAMES                   STATUS              PORTS
myclone_voice_worker    Up 2 seconds        8002/tcp

📝 View logs with:
   docker logs -f myclone_voice_worker

🔍 Check health:
   docker exec myclone_voice_worker python -c 'import youtube_transcript_api, openai; print("✅ All dependencies loaded")'
```

#### Method 2: Docker Compose Deployment

Add to your `docker-compose.yml`:

```yaml
version: '3.8'

services:
  voice-processing-worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.voice-processing
    container_name: myclone_voice_worker
    networks:
      - myclone-network
    environment:
      - POSTGRES_HOST=rappo-review_db-1
      - POSTGRES_PORT=5432
      - NATS_URL=nats://myclone_nats:4222
      - AWS_ENDPOINT_URL=http://myclone_localstack:4566
      - PYTHONPATH=/app/dependencies:/app/voice_processing:/app
    env_file:
      - .env
    volumes:
      - ./shared:/app/shared
      - ./app:/app/app
      - ./workers/voice_processing:/app/voice_processing
      - ./uploads:/app/uploads
      - ./logs:/app/logs
    depends_on:
      - db
      - nats
      - localstack
    restart: unless-stopped
    deploy:
      replicas: 2  # Scale to 2 workers
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 512M

networks:
  myclone-network:
    external: true
```

Deploy with:

```bash
docker-compose up -d voice-processing-worker

# Scale workers
docker-compose up -d --scale voice-processing-worker=3
```

#### Method 3: Manual Docker Deployment

Step-by-step manual deployment:

```bash
# 1. Create Docker network (if not exists)
docker network create myclone-network

# 2. Build the image
docker build -f docker/Dockerfile.voice-processing \
  -t myclone-voice-processing .

# 3. Get LocalStack IP (if using LocalStack)
LOCALSTACK_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' myclone_localstack)

# 4. Run the worker
docker run -d \
  --name myclone_voice_worker \
  --network myclone-network \
  --env-file .env \
  -e POSTGRES_HOST=rappo-review_db-1 \
  -e POSTGRES_PORT=5432 \
  -e NATS_URL=nats://myclone_nats:4222 \
  -e AWS_ENDPOINT_URL="http://$LOCALSTACK_IP:4566" \
  -e PYTHONPATH=/app/dependencies:/app/voice_processing:/app \
  --add-host=myclone_localstack:$LOCALSTACK_IP \
  -v $(pwd)/shared:/app/shared \
  -v $(pwd)/app:/app/app \
  -v $(pwd)/workers/voice_processing:/app/voice_processing \
  -v $(pwd)/uploads:/app/uploads \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  myclone-voice-processing
```

### Scaling Workers

#### Scale Horizontally (Multiple Workers)

**Docker Compose:**
```bash
docker-compose up -d --scale voice-processing-worker=5
```

**Manual:**
```bash
# Start multiple worker instances
for i in {1..5}; do
  docker run -d \
    --name myclone_voice_worker_$i \
    --network myclone-network \
    --env-file .env \
    -e WORKER_ID=worker_$i \
    [... other options ...]
    myclone-voice-processing
done
```

**Verify scaling:**
```bash
docker ps --filter name=myclone_voice_worker
```

### Deployment Verification

#### 1. Check Container Status

```bash
# Container is running
docker ps --filter name=myclone_voice_worker

# View resource usage
docker stats myclone_voice_worker
```

#### 2. Verify Dependencies

```bash
# Test Python dependencies
docker exec myclone_voice_worker python -c "
import youtube_transcript_api
import openai
import assemblyai
import ffmpeg
print('✅ All dependencies loaded successfully')
"

# Check FFmpeg
docker exec myclone_voice_worker ffmpeg -version
```

#### 3. Test Worker Connection

```bash
# Check NATS connection
docker logs myclone_voice_worker | grep "initialized successfully"

# Check database connection
docker logs myclone_voice_worker | grep "PostgreSQL"
```

#### 4. Submit Test Job

```bash
# Create a test job
curl -X POST http://localhost:8001/api/v1/voice-processing/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "VOICE_EXTRACTION",
    "input_source": "https://youtube.com/watch?v=test",
    "user_id": "test-user-id"
  }'

# Check worker logs
docker logs -f myclone_voice_worker
```

### Monitoring Deployed Workers

#### Real-Time Logs

```bash
# Follow logs
docker logs -f myclone_voice_worker

# Last 100 lines
docker logs --tail 100 myclone_voice_worker

# Logs with timestamps
docker logs -t myclone_voice_worker

# Filter for errors
docker logs myclone_voice_worker 2>&1 | grep ERROR
```

#### Worker Statistics

```bash
# Get worker stats via API
curl http://localhost:8001/api/v1/voice-processing/stats

# Response:
# {
#   "workers_active": 2,
#   "jobs_pending": 5,
#   "jobs_processing": 2,
#   "jobs_completed_last_hour": 45,
#   "average_processing_time": 67.3
# }
```

#### Container Health

```bash
# Container health
docker inspect myclone_voice_worker | grep -A 10 "Health"

# Resource usage
docker stats myclone_voice_worker --no-stream

# Process list inside container
docker top myclone_voice_worker
```

### Updating Deployed Workers

#### Rolling Update (Zero Downtime)

```bash
# 1. Build new image
docker build -f docker/Dockerfile.voice-processing \
  -t myclone-voice-processing:latest .

# 2. Start new workers
for i in {1..2}; do
  docker run -d \
    --name myclone_voice_worker_new_$i \
    [... same options ...]
    myclone-voice-processing:latest
done

# 3. Wait for new workers to initialize (30 seconds)
sleep 30

# 4. Stop old workers gracefully
docker stop myclone_voice_worker_1 myclone_voice_worker_2

# 5. Remove old containers
docker rm myclone_voice_worker_1 myclone_voice_worker_2
```

#### Hot Reload (Development)

For code changes without rebuilding:

```bash
# Workers auto-reload when mounted volumes change
# Just modify the code in workers/voice_processing/

# Watch logs to see reload
docker logs -f myclone_voice_worker
```

### Production Deployment Checklist

- [ ] Environment variables configured in `.env`
- [ ] API keys set (OPENAI_API_KEY, ASSEMBLYAI_API_KEY, DATALAB_API_KEY)
- [ ] PostgreSQL database accessible
- [ ] NATS server running and accessible
- [ ] S3 bucket created (or LocalStack configured)
- [ ] Docker network `myclone-network` created
- [ ] Worker container built and started
- [ ] Worker logs show "initialized successfully"
- [ ] Test job submitted and completed
- [ ] Monitoring/alerting configured
- [ ] Log aggregation setup (optional)
- [ ] Auto-restart enabled (`--restart unless-stopped`)
- [ ] Resource limits configured (memory, CPU)
- [ ] Multiple workers deployed (2-5 recommended)

### Troubleshooting Deployment

#### Container Won't Start

```bash
# Check logs
docker logs myclone_voice_worker

# Common issues:
# - Missing environment variables
# - Database connection failed
# - NATS connection failed
# - Invalid AWS credentials
```

#### Database Connection Issues

```bash
# Test PostgreSQL connectivity
docker exec myclone_voice_worker \
  psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1"

# Check network
docker network inspect myclone-network
```

#### NATS Connection Issues

```bash
# Verify NATS is running
docker ps --filter name=nats

# Test NATS connection
docker exec myclone_voice_worker \
  python -c "import nats; print('NATS module loaded')"
```

#### S3/LocalStack Issues

```bash
# Test S3 connection
docker exec myclone_voice_worker \
  python -c "
import boto3
s3 = boto3.client('s3', endpoint_url='$AWS_ENDPOINT_URL')
print(s3.list_buckets())
"
```

#### FFmpeg Not Working

```bash
# Verify FFmpeg installation
docker exec myclone_voice_worker which ffmpeg
docker exec myclone_voice_worker ffmpeg -version

# Test audio processing
docker exec myclone_voice_worker \
  ffmpeg -f lavfi -i sine=frequency=1000:duration=1 -ar 44100 /tmp/test.wav
```

### Deployment Architecture

```
Production Setup (Recommended)

┌─────────────────────────────────────────────┐
│          Load Balancer / Nginx              │
└────────────────┬────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼────┐  ┌───▼────┐  ┌───▼────┐
│FastAPI │  │FastAPI │  │FastAPI │
│   1    │  │   2    │  │   3    │
└───┬────┘  └───┬────┘  └───┬────┘
    │            │            │
    └────────────┼────────────┘
                 │
         ┌───────▼────────┐
         │  NATS Cluster  │
         │   (3 nodes)    │
         └───────┬────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
┌───▼────┐  ┌───▼────┐  ┌───▼────┐
│Worker  │  │Worker  │  │Worker  │
│   1    │  │   2    │  │   N    │
└────────┘  └────────┘  └────────┘
    │            │            │
    └────────────┼────────────┘
                 │
         ┌───────┴────────┐
         │                │
    ┌────▼────┐     ┌────▼────┐
    │PostgreSQL│    │    S3   │
    │ Primary  │    │ Storage │
    └──────────┘    └─────────┘
```

## 🐛 Troubleshooting

### Jobs stuck in QUEUED
- Check NATS server is running: `nats-server -p 4223 -js`
- Verify workers are running: `docker-compose ps`
- Check worker logs: `docker-compose logs voice-processing-worker`

### High failure rate
- Review error messages in database
- Check API keys (OPENAI_API_KEY, ASSEMBLYAI_API_KEY, DATALAB_API_KEY)
- Verify network connectivity

### Slow processing
- Increase worker count in `docker-compose.yml`
- Check external API latency (AssemblyAI, OpenAI)
- Monitor database connection pool

## 📚 Additional Resources

- **API Documentation**: See main API docs
- **Database Schema**: See [DATABASE_SCHEMA.md](../DATABASE_SCHEMA.md)
- **Deployment Guide**: See [DEPLOYMENT.md](../DEPLOYMENT.md)
- **RAG System**: See [LlamaIndex-RAG.md](../LlamaIndex-RAG.md)

## 🤝 Contributing

When adding new job types or handlers:

1. Define job type in `shared/voice_processing/models.py`
2. Create handler in `workers/voice_processing/processors/`
3. Add routing in `worker.py`
4. Document in `JOB_TYPES_REFERENCE.md`
5. Update this README

## 📝 Version History

- **v2.0** (2025-10-23): Comprehensive job types documentation
  - Added JOB_TYPES_REFERENCE.md
  - Added WORKER_ARCHITECTURE.md
  - Updated README with quick navigation
  
- **v1.0**: Initial voice processing system
  - Voice extraction
  - Contamination-free processing
  - Speaker analysis

---

**Last Updated**: October 23, 2025  
**Maintained By**: Voice Processing Team
