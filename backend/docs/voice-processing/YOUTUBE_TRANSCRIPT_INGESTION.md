# YouTube Transcript Ingestion Worker Documentation

## Overview

The YouTube Transcript Ingestion system provides automated extraction, transcription, and processing of YouTube videos for expert clone knowledge base ingestion. This system runs as part of the voice processing worker infrastructure and handles the complete pipeline from YouTube URL to chunked transcript data.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     YouTube Ingestion Pipeline                          │
├─────────────────┬──────────────────────┬──────────────────────────────┤
│   API Request   │   Worker Processing  │     Expert Clone API         │
│   (FastAPI)     │   (Docker Container) │     (Ingestion)              │
│                 │                       │                              │
│ YouTube URL     │ 1. Download Audio    │ POST /api/v1/ingestion/      │
│ Username        │ 2. Transcribe (AI)   │ process-youtube-transcript   │
│ Job Creation    │ 3. Chunk Text        │ Content Storage              │
│                 │ 4. Call API          │ Knowledge Base Update        │
└─────────────────┴──────────────────────┴──────────────────────────────┘
                           │
                           ↓
                  ┌────────────────┐
                  │  AssemblyAI    │
                  │  (Transcription│
                  │   Service)     │
                  └────────────────┘
```

## Components

### 1. YouTube Transcription Service
**Location**: `shared/services/youtube_transcription_service.py`

Core service that handles:
- YouTube video metadata extraction
- Audio-only download (MP3 format)
- AssemblyAI transcription integration
- Text chunking with intelligent boundaries
- Metadata enhancement

### 2. Voice Processing Worker
**Location**: `workers/voice_processing/worker.py`

Background worker that:
- Receives YouTube ingestion jobs via NATS
- Orchestrates the complete pipeline
- Handles job progress tracking
- Manages error handling and retries
- Calls expert-clone API for final ingestion

### 3. Job Management System
**Components**:
- **NATS JetStream**: Job queue and messaging
- **PostgreSQL**: Job state persistence
- **Progress Tracking**: Real-time status updates

## Configuration

### Environment Variables

```bash
# Required API Keys
ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here
EXPERT_CLONE_API_KEY=TUj3uRpqhqgwbUx4cd8Ywq6n8q8Y5hoUwLNkdaBJLQv6MLkPPS83bhSK1GVGQ

# API Configuration
API_BASE_URL=http://host.docker.internal:8000/api/v1

# YouTube Processing Settings
YOUTUBE_AUDIO_FORMAT=mp3
YOUTUBE_AUDIO_QUALITY=192

# Text Chunking Configuration
DEFAULT_CHUNK_SIZE=1000
DEFAULT_CHUNK_OVERLAP=200

# Infrastructure
NATS_URL=nats://host.docker.internal:4223
DATABASE_URL=postgresql+asyncpg://postgres:postgres@host.docker.internal:5433/expert-clone
```

### File Configuration
**Location**: `.env.worker` (for Docker containers)

## Quick Start

### 1. Prerequisites

```bash
# Ensure required services are running
docker ps | grep -E "(postgres|nats|voice-processing-worker)"

# Check API is accessible
curl -s http://localhost:8000/health
```

### 2. Submit YouTube Ingestion Job

```bash
# Via API endpoint
curl -X POST "http://localhost:8000/api/v1/voice-processing/ingest-youtube" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "username": "expert_username"
  }'
```

### 3. Monitor Job Progress

```bash
# Get job status
curl "http://localhost:8000/api/v1/voice-processing/jobs/{job_id}"

# Example response
{
  "job_id": "uuid",
  "status": "processing", 
  "stage": "transcript_extraction",
  "progress": 45,
  "message": "Transcribing audio with AssemblyAI..."
}
```

## Processing Pipeline

### Stage 1: Video Information Extraction
```python
# Extracts metadata without downloading video
video_info = {
    'title': 'Video Title',
    'duration': 1234,  # seconds
    'uploader': 'Channel Name',
    'upload_date': '20241007',
    'view_count': 50000,
    'description': 'Video description...',
    'video_id': 'YouTube_ID',
    'tags': ['tag1', 'tag2']
}
```

### Stage 2: Audio Download
- **Format**: MP3 (configurable via `YOUTUBE_AUDIO_FORMAT`)
- **Quality**: 192 kbps (configurable via `YOUTUBE_AUDIO_QUALITY`)
- **Engine**: yt-dlp with FFmpeg post-processing
- **Storage**: Temporary directory, cleaned after processing

```python
# yt-dlp configuration
ydl_opts = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': os.getenv('YOUTUBE_AUDIO_FORMAT', 'mp3'),
        'preferredquality': os.getenv('YOUTUBE_AUDIO_QUALITY', '192'),
    }]
}
```

### Stage 3: Transcription
- **Service**: AssemblyAI API
- **Features**: 
  - Automatic language detection
  - Punctuation and formatting
  - Speaker diarization (disabled for simplicity)
- **Polling**: 5-second intervals until completion

### Stage 4: Text Processing
- **Enhancement**: Metadata integration (title, description, channel)
- **Chunking**: Intelligent text segmentation
  - Size: 1000 characters (configurable via `DEFAULT_CHUNK_SIZE`)
  - Overlap: 200 characters (configurable via `DEFAULT_CHUNK_OVERLAP`)
  - Boundary detection: Sentence and paragraph breaks

### Stage 5: Expert Clone Integration
- **Endpoint**: `POST /api/v1/ingestion/process-youtube-transcript`
- **Payload**: Enhanced transcript with metadata
- **Result**: Content chunks stored in knowledge base

## Job States and Error Handling

### Job Statuses
- `queued`: Job submitted and waiting for worker
- `processing`: Worker actively processing the job
- `completed`: Successfully processed and ingested
- `failed`: Processing failed (see error details)

### Error Types
- `youtube_access_error`: Cannot access YouTube video
- `transcription_error`: AssemblyAI transcription failed
- `api_call_failed`: Expert-clone API call failed
- `processing_error`: General processing error

### Retry Logic
- **Max Retries**: 3 attempts
- **Retry Delay**: 60 seconds
- **Retryable Errors**: Network timeouts, temporary API failures
- **Non-retryable**: Invalid YouTube URLs, authentication failures

## API Integration

### Request Format
```json
{
  "username": "expert_username",
  "youtube_data": {
    "title": "Video Title",
    "description": "Video description...",
    "url": "https://www.youtube.com/watch?v=VIDEO_ID",
    "content": "Full transcript text...",
    "upload_date": "2024-10-07",
    "tags": ["tag1", "tag2"]
  }
}
```

### Response Format
```json
{
  "success": true,
  "message": "YouTube transcript processed successfully",
  "chunks_created": 25,
  "persona_id": "uuid",
  "username": "expert_username"
}
```

## Monitoring and Logging

### Worker Logs
```bash
# View worker logs
docker logs voice-processing-worker

# Follow logs in real-time
docker logs -f voice-processing-worker
```

### Job Monitoring
```bash
# List all jobs
GET /api/v1/voice-processing/jobs

# Get specific job details
GET /api/v1/voice-processing/jobs/{job_id}

# Job progress tracking
{
  "stage": "transcript_extraction",
  "percentage": 75,
  "message": "Transcription completed, processing chunks...",
  "details": {
    "video_duration": 1234,
    "transcript_length": 15000
  }
}
```

## Performance Considerations

### Video Duration Limits
- **Recommended**: Under 60 minutes for optimal processing
- **Maximum**: No hard limit, but longer videos require more processing time
- **Transcription Time**: Approximately 10-20% of video duration

### Resource Usage
- **Memory**: ~500MB per concurrent job
- **Storage**: Temporary audio files (~1MB per minute of video)
- **Network**: Download bandwidth for audio extraction

### Optimization Tips
1. **Batch Processing**: Submit multiple jobs but monitor resource usage
2. **Quality Settings**: Lower `YOUTUBE_AUDIO_QUALITY` for faster processing
3. **Chunk Size**: Adjust `DEFAULT_CHUNK_SIZE` based on content type

## Troubleshooting

### Common Issues

#### 1. "All connection attempts failed"
```bash
# Check API endpoint accessibility from worker
docker exec voice-processing-worker curl http://host.docker.internal:8000/health

# Verify environment variables
docker exec voice-processing-worker env | grep API_BASE_URL
```

#### 2. "AssemblyAI transcription failed"
```bash
# Verify API key
docker exec voice-processing-worker env | grep ASSEMBLYAI_API_KEY

# Check AssemblyAI service status
curl -H "authorization: YOUR_KEY" https://api.assemblyai.com/v2/transcript
```

#### 3. "YouTube video unavailable"
```bash
# Test video accessibility
docker exec voice-processing-worker python -c "
import yt_dlp
ydl = yt_dlp.YoutubeDL({'quiet': True})
info = ydl.extract_info('YOUR_URL', download=False)
print(f'Title: {info.get(\"title\", \"N/A\")}')
"
```

### Debug Commands

```bash
# Access worker container
docker exec -it voice-processing-worker bash

# Test YouTube extraction
python -c "
from shared.services.youtube_transcription_service import YouTubeTranscriptionService
import asyncio
service = YouTubeTranscriptionService()
# Test video info extraction
"

# Check NATS connectivity
python -c "
import nats
import asyncio
async def test():
    nc = await nats.connect('nats://host.docker.internal:4223')
    print('NATS connected successfully')
    await nc.close()
asyncio.run(test())
"
```

## Development

### Local Development Setup
```bash
# Start dependencies
docker-compose -f docker-compose.local.yml up postgres nats -d

# Run worker locally (outside Docker)
cd workers/voice_processing
python -m worker

# Set environment variables
export ASSEMBLYAI_API_KEY=your_key
export API_BASE_URL=http://localhost:8000/api/v1
export NATS_URL=nats://localhost:4223
```

### Testing
```bash
# Test YouTube URL processing
curl -X POST "http://localhost:8000/api/v1/voice-processing/ingest-youtube" \
  -H "Content-Type: application/json" \
  -d '{
    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "username": "test_user"
  }'
```

## Security Considerations

### API Security
- **Authentication**: Bearer token required for API access
- **Rate Limiting**: Implement based on usage patterns
- **Input Validation**: YouTube URL validation and sanitization

### Data Privacy
- **Temporary Storage**: Audio files deleted after processing
- **Transcript Security**: Processed through secure AssemblyAI API
- **Access Control**: User-specific content isolation

### Environment Security
- **API Keys**: Stored as environment variables, not in code
- **Network Isolation**: Worker communicates via internal Docker network
- **Container Security**: Non-root user execution

## Maintenance

### Regular Tasks
1. **Log Rotation**: Monitor and rotate worker logs
2. **Failed Job Cleanup**: Clean up failed job artifacts
3. **API Key Rotation**: Update AssemblyAI and expert-clone API keys
4. **Performance Monitoring**: Track processing times and success rates

### Scaling
- **Horizontal**: Increase worker replicas in docker-compose
- **Vertical**: Adjust container resource limits
- **Queue Management**: Monitor NATS queue depth and processing rates

---

## Related Documentation
- [Voice Processing System Overview](README.md)
- [Docker Deployment Guide](VOICE_PROCESSING_DEPLOYMENT_SUMMARY.md)
- [API Documentation](../API_DOCUMENTATION.md)
- [Worker Configuration](../../workers/voice_processing/README.md)
