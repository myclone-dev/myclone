# Voice Processing Job Types Reference

## Overview

The voice processing worker supports 7 different job types, each with specific request formats, processing stages, and response structures. This document provides comprehensive details for each job type.

## Table of Contents

1. [VOICE_EXTRACTION](#1-voice_extraction)
2. [TRANSCRIPT_EXTRACTION](#2-transcript_extraction)
3. [COMBINED_PROCESSING](#3-combined_processing)
4. [PDF_PARSING](#4-pdf_parsing)
5. [AUDIO_TRANSCRIPTION](#5-audio_transcription)
6. [VIDEO_TRANSCRIPTION](#6-video_transcription)
7. [YOUTUBE_INGESTION](#7-youtube_ingestion)

---

## 1. VOICE_EXTRACTION

Extracts high-quality voice samples from audio/video files or YouTube URLs for voice cloning purposes.

### Request Format

```json
{
  "job_type": "VOICE_EXTRACTION",
  "input_source": "https://youtube.com/watch?v=xyz OR s3://bucket/file.mp4 OR /path/to/file.mp4",
  "user_id": "uuid-string",
  "output_format": "wav",
  "profile": "elevenlabs",
  "multiple_segments": false,
  "max_segments": 3,
  "normalize_audio": false,
  "start_time": 10,
  "end_time": 70,
  "priority": "normal"
}
```

### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `job_type` | string | Yes | - | Must be "VOICE_EXTRACTION" |
| `input_source` | string | Yes | - | YouTube URL, S3 URI, or local file path |
| `user_id` | UUID | No | null | User identifier for job tracking |
| `output_format` | string | No | "wav" | Output audio format (wav, mp3, m4a) |
| `profile` | string | No | "elevenlabs" | Processing profile (elevenlabs, generic) |
| `multiple_segments` | boolean | No | false | Extract multiple segments vs single file |
| `max_segments` | integer | No | 3 | Maximum number of segments to extract |
| `normalize_audio` | boolean | No | false | Apply audio normalization |
| `start_time` | integer | No | null | Start time in seconds for extraction |
| `end_time` | integer | No | null | End time in seconds for extraction |
| `priority` | string | No | "normal" | Job priority (low, normal, high, urgent) |

### Processing Stages

#### Stage 1: Validation (0-5%)
- Validates input source format
- Checks file accessibility
- Validates time range parameters

#### Stage 2: Download/Extract (5-30%)
- **S3 Source**: Downloads file from S3 to temp directory
- **YouTube Source**: Downloads video and extracts audio using yt-dlp
- **Local File**: Validates file existence and format

#### Stage 3: Audio Processing (30-70%)
- **Audio Files** (.wav, .mp3, .m4a): Converts format if needed
- **Video Files**: Extracts audio track using FFmpeg
- Applies time range extraction if specified (start_time/end_time)
- Audio specs: 44.1kHz, 16-bit, mono

#### Stage 4: Segmentation (70-90%) - If `multiple_segments=true`
- Analyzes audio quality using RMS energy
- Selects best quality segments
- Enforces 9MB file size limit (for ElevenLabs compatibility)
- Target duration: ~60-107 seconds per segment
- Outputs multiple segment files

#### Stage 5: Upload to S3 (90-95%)
- Uploads processed files to S3
- Generates S3 URIs for each file
- Updates job result with S3 locations

#### Stage 6: Cleanup (95-100%)
- Removes temporary files
- Finalizes job status

### Response Format

```json
{
  "success": true,
  "processing_time_seconds": 45.3,
  "input_info": {
    "source": "youtube",
    "url": "https://youtube.com/watch?v=xyz",
    "title": "Video Title",
    "duration": 300,
    "channel": "Channel Name"
  },
  "voice_files": [
    {
      "file_path": "s3://bucket/voice-processing/job_abc123/segments/segment_1.wav",
      "duration": 60.5,
      "quality_score": 0.75,
      "start_time": 120,
      "end_time": 180.5
    },
    {
      "file_path": "s3://bucket/voice-processing/job_abc123/segments/segment_2.wav",
      "duration": 58.3,
      "quality_score": 0.68,
      "start_time": 200,
      "end_time": 258.3
    }
  ],
  "voice_quality_score": 0.715
}
```

### Error Responses

```json
{
  "success": false,
  "processing_time_seconds": 12.5,
  "input_info": {
    "source": "youtube",
    "url": "https://youtube.com/watch?v=xyz"
  },
  "error_code": "download_failed",
  "error_message": "Failed to download video: HTTP 404 - Not Found",
  "error_suggestions": [
    "Check if video URL is correct and accessible",
    "Verify video is not private or age-restricted",
    "Try again later if YouTube is experiencing issues"
  ]
}
```

### Use Cases

- Extract voice samples for ElevenLabs voice cloning
- Create audio snippets from long videos
- Extract specific time ranges from interviews/podcasts
- Process multiple quality samples from a single source

---

## 2. TRANSCRIPT_EXTRACTION

**Status**: Not yet implemented (placeholder)

Extracts text transcripts from audio/video files using speech-to-text services.

### Request Format

```json
{
  "job_type": "TRANSCRIPT_EXTRACTION",
  "input_source": "https://youtube.com/watch?v=xyz",
  "user_id": "uuid-string",
  "transcript_language": "en",
  "include_timestamps": true
}
```

### Response Format

```json
{
  "success": false,
  "processing_time_seconds": 1.0,
  "input_info": {
    "source": "https://youtube.com/watch?v=xyz"
  },
  "error_code": "not_implemented",
  "error_message": "Transcript extraction not yet implemented",
  "error_suggestions": [
    "Use voice extraction for now",
    "Check back later for transcript support"
  ]
}
```

---

## 3. COMBINED_PROCESSING

Combines voice extraction and transcript extraction in a single job.

### Request Format

```json
{
  "job_type": "COMBINED_PROCESSING",
  "input_source": "https://youtube.com/watch?v=xyz",
  "user_id": "uuid-string",
  "output_format": "wav",
  "profile": "elevenlabs",
  "multiple_segments": true,
  "max_segments": 3,
  "transcript_language": "en",
  "include_timestamps": true
}
```

### Processing Stages

Currently delegates to `VOICE_EXTRACTION` job type. Full combined processing will be implemented in the future.

### Response Format

Same as `VOICE_EXTRACTION` response format.

---

## 4. PDF_PARSING

Parses PDF documents, extracts text/images, chunks content, and ingests into RAG system for persona knowledge.

### Request Format

```json
{
  "job_type": "PDF_PARSING",
  "input_source": "s3://bucket/document.pdf OR https://example.com/document.pdf",
  "user_id": "uuid-string",
  "persona_id": "uuid-string",
  "chunk_size": 1000,
  "overlap": 200,
  "enhance_images": false,
  "metadata": {
    "document_id": "uuid-string",
    "title": "Document Title",
    "enable_vector_creation": true
  }
}
```

### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `job_type` | string | Yes | - | Must be "PDF_PARSING" |
| `input_source` | string | Yes | - | S3 URI, HTTP URL, or local file path |
| `user_id` | UUID | Yes | - | User who owns the document |
| `persona_id` | UUID | No | null | Persona to associate chunks with (uses default if null) |
| `chunk_size` | integer | No | 1000 | Target words per chunk |
| `overlap` | integer | No | 200 | Word overlap between chunks |
| `enhance_images` | boolean | No | false | Use AI to enhance image descriptions |
| `metadata.document_id` | UUID | No | null | Document record ID for linking |
| `metadata.enable_vector_creation` | boolean | No | true | Create embeddings for chunks |

### Processing Stages

#### Stage 1: Validation (0-10%)
- Validates PDF source
- Checks API keys (DATALAB_API_KEY, OPENAI_API_KEY)
- Creates output directory

#### Stage 2: Download (10-20%) - If remote source
- **S3 Source**: Downloads from S3 to temp file
- **HTTP Source**: Downloads from URL using aiohttp
- Updates document metadata in database

#### Stage 3: PDF Parsing (20-60%)
- Converts PDF to Markdown using Marker API (DataLab)
- Extracts text, tables, and images
- Generates image descriptions if `enhance_images=true`
- Caches parsed results for reuse

#### Stage 4: Chunk Creation (60-80%)
- Splits Markdown into semantic chunks
- Applies overlap between chunks
- Generates metadata for each chunk:
  - Word count
  - Character count
  - Page numbers
  - Section headings
  - Image references

#### Stage 5: RAG Ingestion (80-98%)
- Ensures persona exists (creates default if needed)
- Creates PersonaDataSource link
- Generates embeddings using OpenAI
- Stores chunks in vector database
- Associates chunks with persona

#### Stage 6: Cleanup (98-100%)
- Removes temporary files
- Finalizes job status

### Response Format

```json
{
  "success": true,
  "processing_time_seconds": 125.7,
  "input_info": {
    "source": "s3",
    "s3_path": "s3://bucket/document.pdf",
    "file_size": 2458624
  },
  "pdf_chunks": [
    {
      "chunk_id": "chunk_1",
      "text": "Introduction to Machine Learning...",
      "word_count": 1050,
      "character_count": 6523,
      "page_numbers": [1, 2],
      "section": "Introduction",
      "has_images": true,
      "metadata": {
        "headings": ["Chapter 1", "Introduction"],
        "image_count": 2
      }
    }
  ],
  "pdf_stats": {
    "total_chunks": 45,
    "total_words": 47250,
    "total_characters": 289430,
    "average_chunk_size": 1050,
    "persona_id": "uuid-string",
    "user_id": "uuid-string"
  }
}
```

### Error Responses

```json
{
  "success": false,
  "processing_time_seconds": 8.2,
  "input_info": {
    "source": "url",
    "url": "https://example.com/document.pdf"
  },
  "error_code": "download_failed",
  "error_message": "Failed to download document: HTTP 404 - Not Found",
  "error_suggestions": [
    "Check if PDF URL is correct and accessible",
    "Verify file is not password protected",
    "Try uploading the file directly instead"
  ]
}
```

### Use Cases

- Import research papers into persona knowledge base
- Process legal documents for AI assistant training
- Extract structured data from reports and manuals
- Build knowledge bases from technical documentation

---

## 5. AUDIO_TRANSCRIPTION

Transcribes audio files using AssemblyAI, creates timestamped chunks, and ingests into RAG system.

### Request Format

```json
{
  "job_type": "AUDIO_TRANSCRIPTION",
  "input_source": "s3://bucket/audio.mp3 OR https://example.com/audio.mp3",
  "user_id": "uuid-string",
  "persona_id": "uuid-string",
  "chunk_size": 800,
  "overlap": 100,
  "metadata": {
    "title": "Podcast Episode 1",
    "enable_vector_creation": true
  }
}
```

### Processing Stages

#### Stage 1: Validation (0-10%)
- Validates audio source
- Checks AssemblyAI API key
- Validates file format

#### Stage 2: Download (10-20%) - If remote source
- Downloads audio file to temp directory
- Validates audio format (supported: mp3, wav, m4a, etc.)

#### Stage 3: Transcription (20-70%)
- Uploads audio to AssemblyAI
- Polls for transcription completion
- Retrieves timestamped transcript with word-level details

#### Stage 4: Chunking (70-85%)
- Splits transcript into semantic chunks based on timestamps
- Target: ~800 words per chunk with 100-word overlap
- Preserves speaker labels and timestamps
- Creates metadata for each chunk

#### Stage 5: RAG Ingestion (85-98%)
- Generates embeddings for transcript chunks
- Stores in vector database
- Associates with persona for RAG retrieval

#### Stage 6: Cleanup (98-100%)
- Removes temporary files
- Finalizes job status

### Response Format

```json
{
  "success": true,
  "processing_time_seconds": 89.4,
  "input_info": {
    "source": "s3",
    "s3_uri": "s3://bucket/audio.mp3",
    "file_size": 15728640,
    "duration": 1825.5
  },
  "transcript_text": "Full transcript text...",
  "transcript_segments": [
    {
      "chunk_index": 0,
      "start_time": 0.0,
      "end_time": 245.3,
      "text": "Welcome to the podcast...",
      "word_count": 810,
      "speaker": "Speaker A"
    },
    {
      "chunk_index": 1,
      "start_time": 225.3,
      "end_time": 468.7,
      "text": "Today we're discussing...",
      "word_count": 798,
      "speaker": "Speaker A"
    }
  ],
  "stats": {
    "total_chunks": 8,
    "total_words": 6420,
    "duration_seconds": 1825.5,
    "chunks_ingested": 8
  }
}
```

### Use Cases

- Transcribe podcast episodes for searchability
- Convert interviews into text for analysis
- Create searchable audio archives
- Build voice-based knowledge bases

---

## 6. VIDEO_TRANSCRIPTION

Extracts audio from video files, transcribes using AssemblyAI, and ingests into RAG system.

### Request Format

```json
{
  "job_type": "VIDEO_TRANSCRIPTION",
  "input_source": "s3://bucket/video.mp4 OR https://example.com/video.mp4",
  "user_id": "uuid-string",
  "persona_id": "uuid-string",
  "chunk_size": 800,
  "overlap": 100,
  "metadata": {
    "title": "Lecture Recording",
    "enable_vector_creation": true
  }
}
```

### Processing Stages

#### Stage 1: Validation (0-10%)
- Validates video source
- Checks FFmpeg availability
- Validates file format

#### Stage 2: Download (10-20%) - If remote source
- Downloads video file to temp directory

#### Stage 3: Audio Extraction (20-40%)
- Extracts audio track using FFmpeg
- Converts to compatible format (WAV, 16kHz)
- Validates audio extraction success

#### Stage 4: Transcription (40-75%)
- Uploads audio to AssemblyAI
- Polls for transcription completion
- Retrieves timestamped transcript

#### Stage 5: Chunking (75-85%)
- Splits transcript into semantic chunks
- Preserves video timestamps for reference
- Creates searchable segments

#### Stage 6: RAG Ingestion (85-98%)
- Generates embeddings for chunks
- Stores in vector database
- Links to persona knowledge base

#### Stage 7: Cleanup (98-100%)
- Removes temporary video and audio files
- Finalizes job status

### Response Format

```json
{
  "success": true,
  "processing_time_seconds": 142.8,
  "input_info": {
    "source": "s3",
    "s3_uri": "s3://bucket/video.mp4",
    "file_size": 52428800,
    "duration": 2145.0,
    "video_format": "mp4"
  },
  "transcript_text": "Full transcript text...",
  "transcript_segments": [
    {
      "chunk_index": 0,
      "start_time": 0.0,
      "end_time": 312.5,
      "text": "Welcome to today's lecture...",
      "word_count": 825,
      "timestamp_reference": "00:00:00 - 00:05:12"
    }
  ],
  "stats": {
    "total_chunks": 12,
    "total_words": 9840,
    "duration_seconds": 2145.0,
    "chunks_ingested": 12,
    "audio_extracted": true
  }
}
```

### Use Cases

- Transcribe lecture videos for students
- Create searchable video archives
- Extract content from webinars and presentations
- Build video-based knowledge repositories

---

## 7. YOUTUBE_INGESTION

Downloads YouTube videos, extracts transcripts (with OpenAI enrichment), and ingests into RAG system for persona training.

### Request Format

```json
{
  "job_type": "YOUTUBE_INGESTION",
  "input_source": "https://youtube.com/watch?v=xyz",
  "user_id": "uuid-string",
  "persona_id": "uuid-string",
  "metadata": {
    "min_chunk_tokens": 400,
    "max_chunk_tokens": 800,
    "target_chunk_duration": 45.0,
    "keep_audio": false
  }
}
```

### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `job_type` | string | Yes | - | Must be "YOUTUBE_INGESTION" |
| `input_source` | string | Yes | - | YouTube video URL |
| `user_id` | UUID | Yes | - | User identifier (required) |
| `persona_id` | UUID | No | null | Persona ID (uses default if null) |
| `metadata.min_chunk_tokens` | integer | No | 400 | Minimum tokens per chunk |
| `metadata.max_chunk_tokens` | integer | No | 800 | Maximum tokens per chunk |
| `metadata.target_chunk_duration` | float | No | 45.0 | Target duration in seconds per chunk |
| `metadata.keep_audio` | boolean | No | false | Keep downloaded audio file |

### Processing Stages

#### Stage 1: Validation (0-10%)
- Validates YouTube URL format
- Checks user_id is provided
- Initializes YouTube extractor

#### Stage 2: Video Metadata Extraction (10-30%)
- Extracts video metadata (title, channel, duration, views)
- Downloads video transcript (auto-generated or manual)
- Validates transcript availability

#### Stage 3: Transcript Processing (30-50%)
- Chunks transcript into semantic segments
- Target: 400-800 tokens per chunk
- Preserves timestamps for each chunk

#### Stage 4: OpenAI Enrichment (50-70%)
- Generates summaries for each chunk using GPT-4
- Extracts keywords and topics
- Enhances chunk metadata with AI-generated insights
- Rate-limited to avoid API throttling

#### Stage 5: Database Storage (70-80%)
- Stores video metadata in `youtube_videos` table
- Creates or retrieves persona record
- Links video to persona via `persona_data_sources`

#### Stage 6: RAG Ingestion (80-98%)
- Prepares content sources with enriched metadata
- Generates embeddings using OpenAI
- Stores chunks in vector database
- Associates with persona for retrieval

#### Stage 7: Cleanup (98-100%)
- Removes temporary audio files (if keep_audio=false)
- Finalizes job status

### Response Format

```json
{
  "success": true,
  "processing_time_seconds": 156.3,
  "input_info": {
    "source": "youtube",
    "video_id": "xyz123",
    "title": "Introduction to Machine Learning",
    "channel": "Tech Education",
    "duration": 1845,
    "view_count": 125430,
    "url": "https://youtube.com/watch?v=xyz123"
  },
  "transcript_text": "Processed 45 chunks with 45 embeddings created",
  "transcript_segments": [
    {
      "chunk_index": 0,
      "start_time": 0.0,
      "end_time": 48.5,
      "text_preview": "Welcome to this comprehensive guide on machine learning...",
      "token_count": 456,
      "summary": "Introduction to machine learning course objectives and overview",
      "keywords": ["machine learning", "AI", "introduction"]
    },
    {
      "chunk_index": 1,
      "start_time": 45.2,
      "end_time": 94.8,
      "text_preview": "Let's start with the fundamentals of supervised learning...",
      "token_count": 498,
      "summary": "Explanation of supervised learning concepts and applications",
      "keywords": ["supervised learning", "training data", "algorithms"]
    }
  ]
}
```

### Error Responses

```json
{
  "success": false,
  "processing_time_seconds": 15.2,
  "input_info": {
    "source": "youtube",
    "url": "https://youtube.com/watch?v=xyz"
  },
  "error_code": "youtube_ingestion_error",
  "error_message": "Video does not have English transcripts or captions available",
  "error_suggestions": [
    "Check YouTube URL is valid and accessible",
    "Ensure video has English transcripts or captions",
    "Verify OpenAI API key is configured for summary generation",
    "Verify AssemblyAI API key is configured if no transcript available",
    "Try again later"
  ]
}
```

### Use Cases

- Import educational YouTube content into AI tutor personas
- Build knowledge bases from tutorial videos
- Create searchable archives of video content
- Train personas with specific domain knowledge from videos

---

## Common Processing Patterns

### Error Handling

All job types implement consistent error handling:

1. **Retryable Errors**: Network issues, API rate limits (HTTP 429, 500-504)
   - Automatically retried up to 3 times with 60-second delays
   - Job status shows retry attempt count

2. **Permanent Errors**: Invalid input, missing files (HTTP 404, 400)
   - Job marked as failed immediately
   - Detailed error message with suggestions provided

3. **Timeout Handling**: Long-running operations
   - AssemblyAI transcription: 1-hour timeout
   - File downloads: 1-hour timeout
   - Processing stages track progress regularly

### Progress Tracking

All jobs report progress through standardized stages:
- Each stage has a percentage range (e.g., Download: 10-20%)
- Real-time updates via NATS and PostgreSQL
- Detailed stage messages for user feedback

### File Management

- **Temporary Files**: Created in `/app/voice_processing/temp/`
- **Output Files**: Stored in S3 with job-specific paths
- **Cleanup**: All temporary files removed after job completion
- **Persistence**: Only S3 URIs stored in database results

### Database State

All jobs maintain state in PostgreSQL `voice_processing_jobs` table:
- `status`: Current job status (pending, processing, completed, failed)
- `current_stage`: Current processing stage name
- `progress_percentage`: 0-100 completion percentage
- `result`: JSON object with job-specific output
- `error_message`: Error details if job failed

---

## API Integration

### Creating Jobs

```bash
# Create a job via API
curl -X POST http://localhost:8001/api/v1/voice-processing/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "YOUTUBE_INGESTION",
    "input_source": "https://youtube.com/watch?v=xyz",
    "user_id": "uuid-string",
    "persona_id": "uuid-string"
  }'
```

### Checking Job Status

```bash
# Get job status and progress
curl http://localhost:8001/api/v1/voice-processing/jobs/{job_id}

# Response includes:
# - status: Current job status
# - current_stage: Active processing stage
# - progress_percentage: 0-100
# - result: Final output (when completed)
# - error_message: Error details (if failed)
```

### Monitoring Progress

```bash
# Get real-time progress updates
curl http://localhost:8001/api/v1/voice-processing/jobs/{job_id}/progress

# Returns:
# - stage: Current ProcessingStage
# - percentage: Progress within stage
# - message: Human-readable status message
# - details: Stage-specific metadata
```

---

## Performance Considerations

### Processing Times (Approximate)

| Job Type | Typical Duration | Factors |
|----------|------------------|---------|
| VOICE_EXTRACTION | 30-120s | Video length, download speed |
| PDF_PARSING | 60-300s | PDF size, page count, image count |
| AUDIO_TRANSCRIPTION | 45-180s | Audio length, transcription queue |
| VIDEO_TRANSCRIPTION | 60-240s | Video size, audio extraction time |
| YOUTUBE_INGESTION | 90-360s | Video length, OpenAI API latency |

### Resource Usage

- **CPU**: FFmpeg processing, audio analysis
- **Memory**: Video buffering, transcript processing
- **Network**: S3 uploads, API calls (AssemblyAI, OpenAI)
- **Storage**: Temporary files deleted after processing

### Scaling

- Workers can be scaled horizontally (2-10+ instances)
- NATS queue ensures work distribution
- PostgreSQL handles concurrent job updates
- S3 provides unlimited output storage

---

## Troubleshooting

### Common Issues by Job Type

#### VOICE_EXTRACTION
- **File too large**: Use time range extraction or multiple segments
- **Quality too low**: Check source audio quality, try different segments
- **Download failed**: Verify URL accessibility, check network

#### PDF_PARSING
- **Parsing timeout**: Large PDFs may need more processing time
- **Missing text**: Scanned PDFs require OCR (handled by Marker API)
- **API errors**: Check DATALAB_API_KEY and OPENAI_API_KEY

#### AUDIO/VIDEO_TRANSCRIPTION
- **No transcription**: Check AssemblyAI API key and quota
- **Poor accuracy**: Audio quality affects transcription quality
- **Timeout**: Very long files may need chunking

#### YOUTUBE_INGESTION
- **No transcript**: Video must have captions/transcript available
- **Rate limited**: OpenAI API has rate limits for enrichment
- **Download failed**: Check video accessibility and region restrictions

### Debug Steps

1. **Check Worker Logs**:
   ```bash
   docker-compose logs -f voice-processing-worker
   ```

2. **Verify API Keys**:
   - DATALAB_API_KEY (PDF parsing)
   - OPENAI_API_KEY (embeddings, enrichment)
   - ASSEMBLYAI_API_KEY (transcription)

3. **Check NATS Connection**:
   ```bash
   curl http://localhost:8001/api/v1/voice-processing/health
   ```

4. **Review Job Details**:
   ```bash
   curl http://localhost:8001/api/v1/voice-processing/jobs/{job_id}
   ```

---

## Version History

- **v1.0** (2025-10-23): Initial comprehensive documentation
  - All 7 job types documented
  - Processing stages detailed
  - Error handling patterns established
  - API integration examples provided

