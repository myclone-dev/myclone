# Document Processing Implementation Summary

## Overview
Successfully implemented comprehensive document processing for PDF, audio, and video files with full CRUD operations including upload, refresh, delete, and duplicate detection.

## Recent Updates (October 2025)

### Critical Bug Fixes & Improvements

#### 1. **Embeddings Query Fixed - Use `source_record_id` Instead of Metadata**
- **Problem**: All embedding queries were using `metadata_->>'document_id'` which is unreliable as the metadata field doesn't always contain `document_id`
- **Solution**: Updated all functions to use `LlamaIndexEmbedding.source_record_id` column which directly links to documents
- **Impact**: More reliable embedding checks and deletions across all endpoints
- **Files Updated**:
  - `app/api/document_utils.py` - All utility functions now use `source_record_id`
  - `app/api/document_routes.py` - Delete endpoint uses `source_record_id`

#### 2. **Delete Endpoint Enhanced** (`DELETE /api/v1/documents/{document_id}`)
- **Added**: `user_id` parameter for ownership verification
- **Fixed**: No CASCADE DELETE exists in schema, so manual deletion is required
- **Implementation**:
  1. Verifies document exists and belongs to the specified user
  2. Queries embeddings using `source_record_id` (not metadata)
  3. Queries all PersonaDataSource entries (handles both "pdf" and "document" source types)
  4. Deletes all three entities in a single atomic transaction:
     - LlamaIndex embeddings (via `source_record_id`)
     - PersonaDataSource entries
     - Document record
  5. Proper rollback on any failure
- **Error Handling**: Returns 404 if document not found or doesn't belong to user

#### 3. **Refresh Endpoint Fixed** (`POST /api/v1/documents/refresh`)
- **Problem**: Combined WHERE clause made it impossible to distinguish "document not found" vs "wrong user"
- **Solution**: Separated checks for better error messages
- **Implementation**:
  1. First checks if document exists (by document_id only)
  2. Then verifies ownership (compares user_id)
  3. Returns specific HTTP status codes:
     - `404 NOT FOUND`: Document doesn't exist
     - `403 FORBIDDEN`: Document belongs to different user
- **Added**: Comprehensive logging at every step for debugging
- **Added**: Detailed metadata logging and traceback on errors

#### 4. **Document Utilities Standardized** (`app/api/document_utils.py`)
All utility functions now use `source_record_id`:
- `check_document_dependency()` - Uses ORM query with `LlamaIndexEmbedding.source_record_id`
- `cleanup_document_data()` - Uses SQLAlchemy delete statements with `source_record_id`
- `delete_document_embeddings()` - Uses `source_record_id` for reliable deletion

## What Was Implemented

### 1. Updated `/add` Endpoint (`app/api/document_routes.py`)
- **File Upload Support**: Accepts PDF, audio (.mp3, .wav, .m4a), and video (.mp4, .mov, .avi, .mkv) files
- **Duplicate Detection**: SHA-256 checksum-based duplicate detection per user
- **File Size Limit**: 100MB across all file types (configurable via `MAX_FILE_UPLOAD_SIZE`)
- **File Classification**: Automatically classifies uploaded files as 'pdf', 'audio', or 'video'
- **S3 Upload**: Uploads files to S3 with proper content types
- **Database Integration**: Creates Document entries and PersonaDataSource links
- **Job Queuing**: Queues appropriate processing jobs based on file type:
  - PDF → `publish_pdf_job`
  - Audio → `publish_audio_job`
  - Video → `publish_video_job`

### 2. Configuration Updates (`shared/config.py`)
- Added `max_file_upload_size` setting (100MB default)
- Maintains existing `max_pdf_file_size` for backward compatibility

### 3. Job Service Updates (`shared/voice_processing/job_service.py`)
- Updated `publish_audio_job()` to accept `persona_id` parameter
- Updated `publish_video_job()` to accept `persona_id` parameter
- Both methods now properly pass persona_id to workers for RAG ingestion

### 4. Worker Implementation (`workers/voice_processing/`)
Created new `audio_video_handlers.py` module with:

#### Audio Transcription Processing
- Downloads audio from S3 or URL
- Transcribes with AssemblyAI
- Creates smart chunks with timestamps (400-800 tokens, ~45s duration)
- Extracts start/end timestamps in seconds.milliseconds format
- Updates Document table with full unchunked transcript
- Ingests chunks into RAG using `ingest_pre_chunked_data`
- **Sets `source_record_id`**: Links embeddings to document via `source_record_id` column
- Stores chunk metadata including:
  - `start_time`, `end_time`, `duration`
  - `speakers` (if available from AssemblyAI)
  - `chunk_index`, `token_count`
- Cleans up temporary files after processing

#### Video Transcription Processing
- Downloads video from S3 or URL
- Extracts audio using FFmpeg
- Transcribes audio with AssemblyAI
- Creates smart chunks with timestamps (same as audio)
- Updates Document table with full unchunked transcript
- Ingests chunks into RAG with proper `source_type="video"`
- **Sets `source_record_id`**: Links embeddings to document via `source_record_id` column
- Cleans up both temporary video and audio files
- Stores chunk metadata with video source information

#### Helper Functions
- `update_document_content()`: Updates Document.content_text with full transcript
- `ingest_audio_video_chunks_to_rag()`: Ingests chunks into RAG system with proper metadata

### 5. Worker Integration (`workers/voice_processing/worker.py`)
- Imported audio/video handlers
- Updated `_process_audio_transcription()` to use new handler
- Updated `_process_video_transcription()` to use new handler
- Both methods properly handle S3 downloads and cleanup

## API Endpoints

### Upload Document
```bash
curl -X POST "http://localhost:8001/api/v1/documents/add" \
  -H "X-API-Key: your-api-key" \
  -F "user_id=123e4567-e89b-12d3-a456-426614174000" \
  -F "persona_name=default" \
  -F "force=false" \
  -F "file=@/path/to/document.pdf"
```

**Parameters**:
- `user_id` (required): UUID of the user uploading the document
- `persona_name` (optional): Defaults to "default"
- `force` (optional): Set to `true` to force re-upload even if document exists
- `file` (required): The file to upload

**Duplicate Detection**:
- Calculates SHA-256 checksum of file content
- Checks for existing document with same checksum for this user
- If found without `force=true`:
  - With embeddings: Returns existing document_id with message to use force mode
  - Without embeddings: Suggests using `/refresh` endpoint
- If `force=true`: Cleans up existing document, embeddings, and persona data sources, then re-processes

### Refresh Document Embeddings
```bash
curl -X POST "http://localhost:8001/api/v1/documents/refresh" \
  -H "X-API-Key: your-api-key" \
  -F "user_id=123e4567-e89b-12d3-a456-426614174000" \
  -F "document_id=789e0123-e89b-12d3-a456-426614174000"
```

**Parameters**:
- `user_id` (required): UUID of the user who owns the document
- `document_id` (required): UUID of the document to refresh

**Process**:
1. Verifies document exists
2. Verifies document belongs to the specified user (403 if mismatch)
3. Deletes existing embeddings (using `source_record_id`)
4. Re-queues processing job based on file type
5. Only commits if job successfully queued (rollback on failure)

**Error Responses**:
- `404 NOT FOUND`: Document doesn't exist
- `403 FORBIDDEN`: Document belongs to different user
- `400 BAD REQUEST`: Missing metadata or no persona data source
- `503 SERVICE UNAVAILABLE`: Queue service not available

### Delete Document
```bash
curl -X DELETE "http://localhost:8001/api/v1/documents/{document_id}?user_id={user_id}" \
  -H "X-API-Key: your-api-key"
```

**Parameters**:
- `document_id` (path): UUID of the document to delete
- `user_id` (query): UUID of the user who owns the document

**Process**:
1. Verifies document exists and belongs to user
2. Queries all related data using `source_record_id`:
   - PersonaDataSource entries (all source types)
   - LlamaIndex embeddings
3. Deletes everything in single transaction:
   - Embeddings first
   - PersonaDataSource entries
   - Document record
4. Rollback on any failure

**Response**:
```json
{
  "success": true,
  "message": "Document deleted successfully (including 2 data sources and 45 embeddings)",
  "document_id": "uuid-here"
}
```

### Get User Documents
```bash
curl -X GET "http://localhost:8001/api/v1/documents/{user_id}" \
  -H "X-API-Key: your-api-key"
```

### Check Document Embeddings
```bash
curl -X GET "http://localhost:8001/api/v1/documents/check-embeddings/{user_id}/{document_id}" \
  -H "X-API-Key: your-api-key"
```

### Supported File Types
- **PDF**: `.pdf`
- **Audio**: `.mp3`, `.wav`, `.m4a`
- **Video**: `.mp4`, `.mov`, `.avi`, `.mkv`

### Response Format
```json
{
  "success": true,
  "message": "AUDIO file uploaded and processing job queued successfully",
  "document_id": "uuid-here",
  "job_id": "uuid-here",
  "supports_enrichment": true
}
```

## Database Schema Notes

### No CASCADE DELETE Configured
- `PersonaDataSource.source_record_id` has NO foreign key to `documents.id`
- `LlamaIndexEmbedding.source_record_id` has NO foreign key to `documents.id`
- **Manual deletion required** for all related data
- All delete operations must be done in application code

### LlamaIndex Embeddings Table Structure
```sql
-- Embeddings are linked via source_record_id column (NOT metadata)
CREATE TABLE data_llamaindex_embeddings (
  id BIGSERIAL PRIMARY KEY,
  text TEXT NOT NULL,
  metadata_ JSONB,  -- Do NOT rely on this for document_id!
  node_id VARCHAR,
  embedding vector(1536),
  
  -- Custom columns for analytics
  user_id UUID,
  source_record_id UUID,  -- ✅ Use this to link to documents!
  source TEXT,
  source_type TEXT,
  posted_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE
);
```

**Important**: Always use `source_record_id` for querying/deleting embeddings, NOT `metadata_->>'document_id'`

## Processing Flow

### For Audio Files:
1. Upload to S3 → `s3://bucket/user-id/filename.mp3`
2. Calculate SHA-256 checksum for duplicate detection
3. Check for existing document (per user)
4. Create Document entry with metadata (including checksum)
5. Create PersonaDataSource with `source_type="document"`
6. Queue `AUDIO_TRANSCRIPTION` job
7. Worker downloads from S3
8. Transcribe with AssemblyAI (with speaker diarization)
9. Create smart chunks with timestamps
10. Update Document.content_text with full transcript
11. Ingest chunks into RAG with `source_record_id` set
12. Clean up temporary files

### For Video Files:
1. Upload to S3 → `s3://bucket/user-id/filename.mp4`
2. Calculate SHA-256 checksum for duplicate detection
3. Check for existing document (per user)
4. Create Document entry with metadata (including checksum)
5. Create PersonaDataSource with `source_type="document"`
6. Queue `VIDEO_TRANSCRIPTION` job
7. Worker downloads from S3
8. Extract audio with FFmpeg
9. Transcribe audio with AssemblyAI
10. Create smart chunks with timestamps
11. Update Document.content_text with full transcript
12. Ingest chunks into RAG with `source_type="video"` and `source_record_id` set
13. Clean up temporary video and audio files

### For PDF Files:
1. Upload to S3 → `s3://bucket/user-id/filename.pdf`
2. Calculate SHA-256 checksum for duplicate detection
3. Check for existing document (per user)
4. Create Document entry with metadata (including checksum)
5. Create PersonaDataSource with `source_type="pdf"`
6. Queue `PDF_PARSING` job
7. Worker processes with Marker API
8. Create enriched chunks
9. Ingest into RAG with `source_record_id` set
10. Clean up temporary files

## Chunk Metadata Structure

### Audio/Video Chunks Include:
- `document_id`: UUID of the document (in metadata_ JSONB)
- `user_id`: UUID of the user (in dedicated column)
- `persona_id`: UUID of the persona (in metadata_ JSONB)
- `source_record_id`: **Document UUID in dedicated column** ✅ PRIMARY LINK
- `chunk_index`: Sequential index
- `chunk_id`: Unique chunk identifier
- `start_time`: Start timestamp in seconds
- `end_time`: End timestamp in seconds
- `duration`: Duration in seconds
- `speakers`: Array of speaker labels (if available)
- `source_url`: Original S3 path
- `source`: "audio" or "video" (in dedicated column)
- `source_type`: "audio" or "video" (in dedicated column)

## Key Features

1. **Smart Chunking**: Uses AssemblyAI utterances for natural segment boundaries
2. **Timestamp Preservation**: Stores start/end timestamps for each chunk
3. **Speaker Diarization**: Captures speaker information when available
4. **RAG Integration**: Uses `ingest_pre_chunked_data` to preserve chunk boundaries
5. **Document Updates**: Stores full unchunked transcript in Document.content_text
6. **Cleanup**: Automatically deletes temporary files after processing
7. **Error Handling**: Proper error handling with retry logic and rollback
8. **Progress Tracking**: Real-time progress updates via NATS
9. **Duplicate Detection**: SHA-256 checksum-based per-user duplicate prevention
10. **Reliable Queries**: All embedding queries use `source_record_id` not metadata
11. **Atomic Operations**: All multi-table operations use transactions with rollback
12. **Ownership Verification**: All endpoints verify user ownership before operations

## Environment Variables Required

```bash
# AssemblyAI for transcription
ASSEMBLYAI_API_KEY=your-assemblyai-key

# S3 for file storage
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
USER_DATA_BUCKET=myclone-user-data-production

# File upload limits
MAX_FILE_UPLOAD_SIZE=104857600  # 100MB in bytes
MAX_PDF_FILE_SIZE=104857600     # 100MB in bytes
```

## Testing

### Test Audio Upload
```bash
curl -X POST "http://localhost:8001/api/v1/documents/add" \
  -H "X-API-Key: your-api-key" \
  -F "user_id=your-user-uuid" \
  -F "persona_name=default" \
  -F "file=@test_audio.mp3"
```

### Test Video Upload
```bash
curl -X POST "http://localhost:8001/api/v1/documents/add" \
  -H "X-API-Key: your-api-key" \
  -F "user_id=your-user-uuid" \
  -F "persona_name=default" \
  -F "file=@test_video.mp4"
```

### Test Duplicate Detection
```bash
# Upload same file twice
curl -X POST "http://localhost:8001/api/v1/documents/add" \
  -H "X-API-Key: your-api-key" \
  -F "user_id=your-user-uuid" \
  -F "persona_name=default" \
  -F "file=@test_audio.mp3"

# Should return message about existing document
```

### Test Force Re-upload
```bash
curl -X POST "http://localhost:8001/api/v1/documents/add" \
  -H "X-API-Key: your-api-key" \
  -F "user_id=your-user-uuid" \
  -F "persona_name=default" \
  -F "force=true" \
  -F "file=@test_audio.mp3"
```

### Test Refresh Endpoint
```bash
curl -X POST "http://localhost:8001/api/v1/documents/refresh" \
  -H "X-API-Key: your-api-key" \
  -F "user_id=your-user-uuid" \
  -F "document_id=document-uuid"
```

### Test Delete Endpoint
```bash
curl -X DELETE "http://localhost:8001/api/v1/documents/document-uuid?user_id=your-user-uuid" \
  -H "X-API-Key: your-api-key"
```

## Implementation Notes

1. **FFmpeg Required**: Video processing requires FFmpeg to be installed on worker machines
2. **AssemblyAI API**: Audio/video transcription uses AssemblyAI (not OpenAI Whisper)
3. **Temporary Files**: All temporary files are stored in worker's local filesystem and cleaned up after processing
4. **Async Processing**: All file operations are async to prevent blocking
5. **S3 Downloads**: Workers download files from S3 to temporary locations for processing
6. **Persona Linking**: Documents are automatically linked to personas via PersonaDataSource
7. **source_record_id is King**: Always use `source_record_id` column for embedding queries, never rely on `metadata_` JSONB
8. **No CASCADE**: All deletion must be manual - no database-level cascade delete configured
9. **Transaction Safety**: All multi-table operations wrapped in transactions with proper rollback
10. **Comprehensive Logging**: Detailed logging at every step for debugging and monitoring

## Common Issues & Solutions

### Issue: "Document not found" but document exists
- **Cause**: User ID mismatch
- **Solution**: Check that the `user_id` parameter matches the document's owner
- **Fixed In**: Refresh endpoint now returns `403 FORBIDDEN` with clear message

### Issue: Embeddings not being deleted
- **Cause**: Using `metadata_->>'document_id'` which may be null/missing
- **Solution**: Use `source_record_id` column instead
- **Fixed In**: All functions now use `source_record_id`

### Issue: Orphaned embeddings after document deletion
- **Cause**: No CASCADE DELETE configured in database
- **Solution**: Delete endpoint manually deletes embeddings using `source_record_id`
- **Fixed In**: Delete endpoint now handles all related data

### Issue: Transaction rollback leaves partial data
- **Cause**: Not wrapping operations in proper transaction
- **Solution**: Use session.commit() only after ALL operations succeed
- **Fixed In**: All endpoints use try/except with rollback

## Future Enhancements

1. Add support for more audio formats (AAC, FLAC, OGG)
2. Add support for more video formats (AVI, MKV improvements)
3. Implement video frame analysis for visual content
4. Add subtitle/caption extraction from videos
5. Support for multi-language transcription
6. Add confidence scores from AssemblyAI to metadata
7. Implement transcript correction/editing API
8. Add batch upload support
9. Implement document versioning
10. Add CASCADE DELETE at database level for cleaner architecture

## Files Changed

### Recent Updates (October 2025)
1. `/app/api/document_utils.py` - **UPDATED**: All functions use `source_record_id`
2. `/app/api/document_routes.py` - **UPDATED**: Delete endpoint with user verification, refresh endpoint with separated checks

### Original Implementation
1. `/app/api/document_routes.py` - Added complete `/add` endpoint
2. `/shared/config.py` - Added max_file_upload_size setting
3. `/shared/voice_processing/job_service.py` - Updated audio/video job methods
4. `/workers/voice_processing/audio_video_handlers.py` - NEW: Complete audio/video processing
5. `/workers/voice_processing/worker.py` - Integrated new handlers

## Validation Checklist

### Core Features
- [x] File type validation (PDF, audio, video)
- [x] File size validation (100MB limit)
- [x] S3 upload with proper content types
- [x] Document table creation
- [x] PersonaDataSource linking
- [x] Job queuing with persona_id
- [x] AssemblyAI transcription
- [x] Smart chunking with timestamps
- [x] Document content_text updates
- [x] RAG ingestion with metadata
- [x] Temporary file cleanup
- [x] Error handling and retries

### CRUD Operations
- [x] Create (upload) with duplicate detection
- [x] Read (list user documents)
- [x] Update (refresh embeddings)
- [x] Delete (with cascading cleanup)

### Data Integrity
- [x] Use source_record_id for all embedding queries
- [x] Manual deletion of all related data
- [x] Transaction safety with rollback
- [x] User ownership verification
- [x] Atomic multi-table operations

### Error Handling
- [x] Specific error messages (404 vs 403)
- [x] Comprehensive logging
- [x] Traceback on errors
- [x] Rollback on failures
- [x] Cleanup on errors

## Architecture Decisions

### Why `source_record_id` Over `metadata_->>'document_id'`?
1. **Reliability**: Dedicated column vs JSONB field that may not be populated
2. **Performance**: Indexed column vs JSONB extraction
3. **Type Safety**: UUID column vs string extraction with casting
4. **Consistency**: All LlamaIndex tables use `source_record_id` pattern

### Why No CASCADE DELETE?
1. **Generic FK**: `source_record_id` is a generic foreign key pattern used across multiple source types
2. **Flexibility**: Allows different cleanup strategies per source type
3. **Control**: Application-level control over deletion order and logging
4. **Safety**: Prevents accidental cascading deletes

### Why Manual Transaction Management?
1. **Multi-Step Operations**: Delete operations span multiple tables
2. **Conditional Logic**: Different paths based on what exists
3. **Error Recovery**: Ability to rollback on job queue failures
4. **Logging**: Log each step before committing

---

**Last Updated**: October 26, 2025
**Status**: Production Ready ✅
**Breaking Changes**: None (all changes are improvements to existing functionality)
