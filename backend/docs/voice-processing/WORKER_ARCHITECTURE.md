# Voice Processing Worker Architecture

## Overview

This document describes the internal architecture of the voice processing worker system, including job flow, handler responsibilities, and processing pipelines.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Voice Processing System                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
            ┌───────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐
            │   FastAPI    │ │    NATS    │ │ PostgreSQL │
            │   Backend    │ │  JetStream │ │  Database  │
            └───────┬──────┘ └─────┬──────┘ └─────┬──────┘
                    │               │               │
                    │        ┌──────▼──────┐        │
                    │        │   Worker    │        │
                    │        │   Pool      │        │
                    │        └──────┬──────┘        │
                    │               │               │
            ┌───────▼───────────────▼───────────────▼──────┐
            │         Voice Processing Workers (N)          │
            │                                                │
            │  ┌──────────────────────────────────────┐    │
            │  │  VoiceProcessingWorker Class         │    │
            │  │  - Job Queue Management              │    │
            │  │  - Progress Tracking                 │    │
            │  │  - Error Handling & Retry            │    │
            │  │  - Job Delegation                    │    │
            │  └──────────────┬───────────────────────┘    │
            │                 │                             │
            │     ┌───────────┼───────────┐                │
            │     │           │           │                │
            │  ┌──▼──┐   ┌───▼───┐   ┌──▼──┐             │
            │  │ PDF │   │YouTube│   │Audio│             │
            │  │Handler│ │Handler│   │Video│             │
            │  │     │   │       │   │Handler            │
            │  └─────┘   └───────┘   └─────┘             │
            └────────────────────────────────────────────┘
                    │               │               │
            ┌───────▼───────┐ ┌────▼────┐  ┌──────▼──────┐
            │  S3 Storage   │ │ OpenAI  │  │ AssemblyAI  │
            └───────────────┘ └─────────┘  └─────────────┘
```

## Worker Class Structure

### VoiceProcessingWorker

**Location**: `workers/voice_processing/worker.py`

**Responsibilities**:
- Initialize NATS connection and job service
- Subscribe to job queue with pull consumer
- Process job messages with retry logic
- Delegate to appropriate handlers
- Track job statistics and health

**Key Methods**:

```python
class VoiceProcessingWorker:
    async def initialize()                    # Setup NATS and job service
    async def start()                         # Start consuming from queue
    async def stop()                          # Graceful shutdown
    async def _process_job_message(msg)       # Handle individual job messages
    async def _process_job(job_data)          # Route to correct processor
    
    # Processing methods (delegate to handlers)
    async def _process_voice_extraction()     # Voice extraction job
    async def _process_pdf_parsing()          # PDF parsing job
    async def _process_audio_transcription()  # Audio transcription job
    async def _process_video_transcription()  # Video transcription job
    async def _process_youtube_ingestion()    # YouTube ingestion job
```

## Handler Architecture

### PDF Handler

**Location**: `workers/voice_processing/processors/pdf_handler.py`

**Functions**:
- `process_pdf_parsing()` - Main entry point
- `_download_pdf_from_s3()` - S3 download helper
- `_download_pdf_from_url()` - HTTP download helper
- `_validate_local_pdf()` - Local file validation
- `_ingest_pdf_chunks_to_rag()` - RAG ingestion

**Flow**:
```
Input (S3/URL/Local) 
    → Download/Validate 
    → Parse with Marker API 
    → Chunk Creation 
    → OpenAI Enrichment 
    → RAG Ingestion 
    → Response
```

**Dependencies**:
- `MarkdownPDFParser` - PDF to Markdown conversion
- `download_utils` - File download utilities
- `rag_ingestion` - RAG system integration

### YouTube Handler

**Location**: `workers/voice_processing/processors/youtube_handler.py`

**Functions**:
- `process_youtube_ingestion()` - Main entry point
- `_store_youtube_metadata()` - Database storage
- `_prepare_youtube_content_sources()` - Content preparation
- `_ingest_youtube_to_rag()` - RAG ingestion

**Flow**:
```
YouTube URL 
    → Extract Metadata 
    → Download Transcript 
    → Semantic Chunking 
    → OpenAI Enrichment (Summary + Keywords)
    → Store Video Metadata 
    → RAG Ingestion 
    → Link to Persona
```

**Dependencies**:
- `YouTubeVideoExtractor` - Video metadata and transcript extraction
- RAG system - Embedding generation and storage
- PostgreSQL - Video and persona metadata

### Audio/Video Handlers

**Location**: `workers/voice_processing/processors/audio_video_handlers.py`

**Functions**:
- `process_audio_transcription()` - Audio transcription
- `process_video_transcription()` - Video transcription

**Flow (Audio)**:
```
Audio File 
    → Upload to AssemblyAI 
    → Poll for Completion 
    → Retrieve Transcript 
    → Semantic Chunking 
    → RAG Ingestion
```

**Flow (Video)**:
```
Video File 
    → Extract Audio (FFmpeg) 
    → Upload to AssemblyAI 
    → Poll for Completion 
    → Retrieve Transcript 
    → Semantic Chunking 
    → RAG Ingestion
```

### Download Utilities

**Location**: `workers/voice_processing/processors/download_utils.py`

**Functions**:
- `download_document_from_url()` - Generic document downloader
- `_update_document_metadata()` - Database metadata updates

**Features**:
- AWS signed URL support
- Progress logging for large files
- Retry logic for transient errors
- Automatic filename sanitization

## Job Processing Flow

### 1. Job Submission

```
Client Request
    ↓
FastAPI Endpoint
    ↓
Create JobRequest Object
    ↓
Store in PostgreSQL (status: PENDING)
    ↓
Publish to NATS Queue
    ↓
Return job_id to Client
```

### 2. Job Consumption

```
NATS JetStream
    ↓
Worker fetches message (batch=1)
    ↓
Parse job data
    ↓
Check for duplicates (PostgreSQL)
    ↓
Update status: PROCESSING
    ↓
Create ProgressTracker
    ↓
Route to appropriate handler
```

### 3. Job Processing

Each job type follows this pattern:

```
Handler Entry Point
    ↓
Stage 1: Validation (0-10%)
    - Validate input
    - Check API keys
    - Setup directories
    ↓
Stage 2: Download/Extract (10-30%)
    - Download from source
    - Validate format
    - Extract content
    ↓
Stage 3: Primary Processing (30-70%)
    - Job-specific processing
    - Generate outputs
    - Quality checks
    ↓
Stage 4: Enrichment (70-85%)
    - AI enhancement
    - Metadata generation
    - Summarization
    ↓
Stage 5: Storage/Ingestion (85-98%)
    - Upload to S3
    - Store in database
    - RAG ingestion
    ↓
Stage 6: Cleanup (98-100%)
    - Remove temp files
    - Finalize status
    - Return result
```

### 4. Job Completion

```
Handler returns JobResult
    ↓
Worker calls job_service.complete_job()
    ↓
Update PostgreSQL:
    - status: COMPLETED
    - result: JobResult JSON
    - completed_at: timestamp
    ↓
ACK NATS message
    ↓
Update scraping_jobs (if applicable)
    ↓
Job complete
```

### 5. Error Handling

```
Exception raised
    ↓
Is VoiceProcessingError?
    ↓
Check if retryable:
    - Network errors (HTTP 429, 5xx)
    - Timeouts
    - Rate limits
    ↓
If retryable && attempts < 3:
    - NAK message (60s delay)
    - Update job progress
    - NATS will redeliver
    ↓
Else (permanent failure):
    - Call job_service.fail_job()
    - Update PostgreSQL
    - ACK message
    - Job failed
```

## Progress Tracking System

### ProgressTracker Class

**Location**: `workers/voice_processing/utils/progress.py`

**Responsibilities**:
- Track current stage
- Calculate percentage
- Generate status messages
- Callback to worker

**Usage Pattern**:

```python
progress_tracker = ProgressTracker(
    callback=lambda update: self._update_progress_sync(job_id, update)
)

# Start a stage
progress_tracker.start_stage(ProcessingStage.VALIDATION, "Validating input")

# Update within stage
progress_tracker.update_progress(15, "Downloaded 50% of file")

# Complete stage
progress_tracker.complete_stage("Validation complete")
```

### Progress Flow

```
Handler calls progress_tracker.start_stage()
    ↓
ProgressTracker creates JobProgress object
    ↓
Calls callback (synchronous wrapper)
    ↓
_update_progress_sync() schedules async update
    ↓
_update_progress() calls job_service
    ↓
JobService publishes to NATS
    ↓
JobService updates PostgreSQL
    ↓
Client can query current progress
```

## Database Schema

### voice_processing_jobs Table

```sql
CREATE TABLE voice_processing_jobs (
    id UUID PRIMARY KEY,
    job_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) NOT NULL,
    job_type VARCHAR(100) NOT NULL,
    
    -- Request data
    request_data JSONB NOT NULL,
    
    -- Processing state
    current_stage VARCHAR(100),
    progress_percentage INTEGER DEFAULT 0,
    worker_id VARCHAR(255),
    
    -- Results and errors
    result JSONB,
    error_code VARCHAR(100),
    error_message TEXT,
    error_suggestions JSONB,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    updated_at TIMESTAMP,
    
    -- Foreign keys
    user_id UUID REFERENCES users(id),
    persona_id UUID REFERENCES personas(id)
);

-- Indexes
CREATE INDEX idx_jobs_status ON voice_processing_jobs(status);
CREATE INDEX idx_jobs_user ON voice_processing_jobs(user_id);
CREATE INDEX idx_jobs_created ON voice_processing_jobs(created_at DESC);
```

### Related Tables

**youtube_videos**: Stores YouTube video metadata
**persona_data_sources**: Links content to personas
**documents**: Tracks uploaded documents
**scraping_jobs**: Related scraping tasks

## Configuration

### Environment Variables

```bash
# NATS Configuration
NATS_URL=nats://localhost:4222

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db

# API Keys
DATALAB_API_KEY=xxx              # Marker API for PDF parsing
OPENAI_API_KEY=xxx               # Embeddings and enrichment
ASSEMBLYAI_API_KEY=xxx           # Audio/video transcription

# S3 Storage
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_S3_BUCKET=voice-processing

# Processing Limits
MAX_FILE_SIZE_MB=100
CHUNK_SIZE=1000
OVERLAP=200
```

### Worker Configuration

**docker-compose.yml**:
```yaml
voice-processing-worker:
  build: ./docker/Dockerfile.voice-processing
  deploy:
    replicas: 2                    # Number of workers
  environment:
    NATS_URL: nats://nats:4222
    DATABASE_URL: ${DATABASE_URL}
```

### NATS Consumer Configuration

```python
consumer_config = ConsumerConfig(
    durable_name="voice_workers",     # Shared consumer
    max_deliver=3,                    # Max retry attempts
    ack_wait=300,                     # 5 min ACK timeout
    max_ack_pending=10,              # Concurrent jobs per worker
)
```

## Scalability Considerations

### Horizontal Scaling

**Workers**: Scale from 1 to N instances
- Each worker processes 1 job at a time
- NATS distributes work automatically
- No coordination needed between workers

**Database**: PostgreSQL handles concurrent updates
- Row-level locking for job status
- Optimistic concurrency for progress updates
- Connection pooling via SQLAlchemy

**Storage**: S3 provides unlimited capacity
- No local storage constraints
- Direct upload from workers
- Cross-region replication available

### Performance Tuning

**Batch Processing**:
```python
# Fetch multiple messages if needed
messages = await subscription.fetch(batch=5, timeout=1)
```

**Connection Pooling**:
```python
# SQLAlchemy async engine with pool
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
)
```

**Rate Limiting**:
- AssemblyAI: ~100 concurrent transcriptions
- OpenAI: Rate limits vary by tier
- Marker API: Check DataLab limits

### Monitoring

**Worker Stats**:
```python
stats = worker.get_stats()
# Returns:
# - worker_id
# - uptime_seconds
# - jobs_processed
# - jobs_succeeded
# - jobs_failed
# - success_rate
# - jobs_per_minute
```

**System Health**:
```bash
# Check API health
curl http://localhost:8001/api/v1/voice-processing/health

# Check NATS connection
curl http://localhost:8001/api/v1/voice-processing/stats
```

**Database Queries**:
```sql
-- Jobs by status
SELECT status, COUNT(*) 
FROM voice_processing_jobs 
GROUP BY status;

-- Average processing time
SELECT 
    job_type,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_seconds
FROM voice_processing_jobs
WHERE status = 'completed'
GROUP BY job_type;

-- Failed jobs with errors
SELECT job_id, error_code, error_message
FROM voice_processing_jobs
WHERE status = 'failed'
ORDER BY created_at DESC
LIMIT 10;
```

## Error Recovery

### Retry Strategy

**Transient Errors** (retried automatically):
- Network timeouts
- HTTP 429 (Rate Limited)
- HTTP 500-504 (Server errors)
- Database connection errors

**Permanent Errors** (fail immediately):
- HTTP 404 (Not Found)
- HTTP 400 (Bad Request)
- Invalid file format
- Missing API keys
- Validation errors

### Manual Recovery

```bash
# Retry a failed job
curl -X POST http://localhost:8001/api/v1/voice-processing/jobs/{job_id}/retry

# Cancel a stuck job
curl -X DELETE http://localhost:8001/api/v1/voice-processing/jobs/{job_id}

# Restart worker
docker-compose restart voice-processing-worker
```

### Data Recovery

**From S3**:
```python
# Retrieve processed files
s3_uri = job.result['voice_files'][0]['file_path']
# s3://bucket/voice-processing/job_abc123/segments/file.wav
```

**From Database**:
```sql
-- Get all completed jobs for user
SELECT job_id, result
FROM voice_processing_jobs
WHERE user_id = 'uuid' 
  AND status = 'completed'
ORDER BY completed_at DESC;
```

## Best Practices

### Job Submission

1. **Validate inputs** before submitting jobs
2. **Set appropriate priorities** for urgent jobs
3. **Include metadata** for better tracking
4. **Use webhooks** for async notifications

### Handler Development

1. **Use progress tracking** for user feedback
2. **Implement proper error handling** with VoiceProcessingError
3. **Clean up resources** in finally blocks
4. **Log important events** for debugging
5. **Use async operations** for I/O-bound tasks

### Resource Management

1. **Delete temp files** after processing
2. **Stream large files** instead of loading in memory
3. **Use connection pooling** for databases
4. **Implement timeouts** for external APIs
5. **Monitor disk usage** on workers

### Testing

1. **Unit test handlers** independently
2. **Integration test** with NATS and PostgreSQL
3. **Load test** with multiple workers
4. **Test error scenarios** and retry logic
5. **Monitor memory usage** during processing

## Troubleshooting Guide

### Common Issues

**Jobs stuck in PENDING**:
- Check NATS connection
- Verify workers are running
- Check worker logs for errors

**High failure rate**:
- Review error messages in database
- Check API key validity
- Verify network connectivity
- Monitor rate limits

**Slow processing**:
- Check worker count
- Monitor CPU/memory usage
- Review database connection pool
- Check external API latency

**Memory leaks**:
- Verify temp file cleanup
- Check for unclosed connections
- Monitor worker restart frequency
- Review large file handling

### Debug Commands

```bash
# Check worker logs
docker-compose logs -f voice-processing-worker

# Check NATS queue depth
nats stream info VOICE_JOBS

# Check database connections
SELECT COUNT(*) FROM pg_stat_activity 
WHERE application_name LIKE '%voice%';

# Monitor worker resources
docker stats voice-processing-worker

# Review recent errors
SELECT error_code, COUNT(*) as count
FROM voice_processing_jobs
WHERE status = 'failed'
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY error_code;
```

## Future Enhancements

### Planned Features

1. **Batch Processing**: Process multiple files in one job
2. **Webhook Notifications**: Real-time job completion alerts
3. **Priority Queues**: Separate queues for different priorities
4. **Caching**: Cache transcripts and embeddings
5. **Job Scheduling**: Schedule jobs for future execution

### Performance Improvements

1. **Parallel Processing**: Process segments in parallel
2. **Streaming Uploads**: Stream to S3 during processing
3. **Local Caching**: Cache frequently accessed files
4. **Database Sharding**: Distribute job data across DBs
5. **CDN Integration**: Serve output files via CDN

---

