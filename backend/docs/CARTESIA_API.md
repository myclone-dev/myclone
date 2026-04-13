# Cartesia Voice Cloning API Endpoints

This document describes the new Cartesia voice cloning endpoints that mirror the ElevenLabs functionality.

## Overview

The Cartesia API endpoints provide instant voice cloning capabilities using the Cartesia API, similar to the existing ElevenLabs integration.

## Files Created

### 1. Service Layer
- **File**: `app/services/cartesia_service.py`
- **Purpose**: Business logic for Cartesia API integration
- **Key Features**:
  - File validation (WAV, MP3, M4A, FLAC, OGG)
  - Voice clone creation using Cartesia instant voice cloning
  - Get voice details
  - List all voices
  - Async HTTP client using httpx

### 2. API Layer
- **File**: `app/api/cartesia_api.py`
- **Purpose**: FastAPI endpoints for voice cloning operations
- **Key Features**:
  - S3 storage integration
  - Database persistence
  - Authentication (JWT for users, API key for operators)
  - Audio format conversion support

## API Endpoints

### Base Path: `/api/v1/cartesia`

### 1. Create Voice Clone (Upload Files)
```
POST /api/v1/cartesia/create_voice_clone
```

**Description**: Create a voice clone by uploading audio files directly

**Form Parameters**:
- `user_id` (UUID, required): User ID who owns this voice clone
- `name` (string, required): Name for the voice clone
- `description` (string, optional): Description for the voice
- `language` (string, optional): Language code (default: "en")
- `files` (List[File], required): Audio files (1-5 files, max 10MB each)

**Response**: `VoiceCloneResponse`
```json
{
  "voice_id": "string",
  "name": "string",
  "status": "success",
  "message": "Voice clone created successfully with N sample(s) stored in S3",
  "components": {
    "s3_upload": {"status": "success", "files_count": 3},
    "cartesia_api": {"status": "success", "voice_id": "abc123"},
    "database_save": {"status": "success"}
  }
}
```

### 2. Create Voice Clone from Paths (Internal)
```
POST /api/v1/cartesia/create_voice_clone_from_paths
```

**Description**: Create a voice clone from existing file paths (for internal use)

**Request Body**: `VoiceCloneFromPathsRequest`
```json
{
  "name": "string",
  "description": "string",
  "language": "en",
  "file_paths": ["path/to/file1.wav", "path/to/file2.wav"]
}
```

### 3. Create Voice Clone from S3 URIs
```
POST /api/v1/cartesia/create_voice_clone_from_s3
```

**Description**: Create a voice clone from S3 URIs (typically from voice processing job outputs)

**Authentication**:
- Users: JWT cookie (can only create voice clones for themselves)
- Operators: X-API-Key header (can create for any user)

**Request Body**: `VoiceCloneFromS3Request`
```json
{
  "user_id": "uuid",
  "name": "string",
  "description": "string",
  "language": "en",
  "s3_uris": [
    "s3://bucket/voice-processing/output/{user_id}/segment1.wav",
    "s3://bucket/voice-processing/output/{user_id}/segment2.wav"
  ],
  "source_job_id": "job-123-456"
}
```

**Workflow**:
1. Downloads voice segments from S3 (voice-processing/output/segments/...)
2. Copies to permanent storage (voiceclone/...)
3. Creates Cartesia voice clone
4. Saves metadata to database with audit trail

**Security**: Only allows access to user's own voice-processing outputs

### 4. Get User Voice Clones
```
GET /api/v1/cartesia/users/{user_id}/voice-clones
```

**Description**: Get all Cartesia voice clones for a user

**Authentication**:
- Users: JWT cookie (can only access their own voice clones)
- Operators: X-API-Key header (can access any user's voice clones)

**Response**: `List[VoiceCloneListItem]`
```json
[
  {
    "id": "uuid",
    "voice_id": "cartesia-voice-id",
    "name": "My Voice Clone",
    "description": "Description",
    "total_files": 3,
    "total_size_bytes": 5242880,
    "created_at": "2023-12-05T10:30:00Z"
  }
]
```

### 5. Health Check
```
GET /api/v1/cartesia/health
```

**Response**:
```json
{
  "status": "healthy",
  "message": "Cartesia service is ready"
}
```

## Key Differences from ElevenLabs

1. **Language Parameter**: Cartesia uses `language` instead of `remove_background_noise`
2. **Provider Tracking**: Database records include `"provider": "cartesia"` in settings
3. **API Implementation**: Uses httpx async client instead of ElevenLabs SDK
4. **File Formats**: Supports OGG in addition to WAV, MP3, M4A, FLAC

## Configuration

### Environment Variables

Add to your `.env` file:
```bash
CARTESIA_API_KEY=your_cartesia_api_key_here
```

### Settings

The Cartesia API key is configured in `shared/config.py`:
```python
cartesia_api_key: str = os.getenv("CARTESIA_API_KEY", "")
```

## Storage Structure

Voice clone files are stored in S3 with the following structure:
```
voiceclone/
  {user_id}/
    {timestamp}_{index}_{filename}.wav
```

## Database Schema

Voice clones are stored in the `voice_clones` table with:
- `voice_id`: Cartesia voice ID
- `settings`: JSON containing `{"provider": "cartesia", "language": "en", ...}`
- `sample_files`: JSON array of S3 file metadata

## Usage Examples

### Example 1: Upload Files Directly
```python
import httpx

files = [
    ("files", open("sample1.wav", "rb")),
    ("files", open("sample2.wav", "rb")),
]

data = {
    "user_id": "user-uuid-here",
    "name": "My Voice Clone",
    "language": "en",
}

response = httpx.post(
    "http://localhost:8000/api/v1/cartesia/create_voice_clone",
    data=data,
    files=files,
)
```

### Example 2: Create from S3 URIs
```python
import httpx

payload = {
    "user_id": "user-uuid-here",
    "name": "My Voice Clone",
    "language": "en",
    "s3_uris": [
        "s3://bucket/voice-processing/output/user-id/segment1.wav",
        "s3://bucket/voice-processing/output/user-id/segment2.wav",
    ],
    "source_job_id": "job-123",
}

response = httpx.post(
    "http://localhost:8000/api/v1/cartesia/create_voice_clone_from_s3",
    json=payload,
    headers={"X-API-Key": "your-api-key"},
)
```

## Error Handling

The API uses standard HTTP status codes:
- `200`: Success
- `400`: Bad request (validation errors)
- `403`: Forbidden (authorization errors)
- `500`: Internal server error

Partial success scenarios (e.g., voice created but DB save failed) return `207` Multi-Status with detailed component status.

## Integration with Main App

The Cartesia router is registered in `app/main.py`:
```python
from app.api import cartesia_api
app.include_router(cartesia_api.router)  # Cartesia voice cloning
```

## Testing

To test the endpoints:

1. Set the `CARTESIA_API_KEY` environment variable
2. Start the server: `make run-server`
3. Access the Swagger UI: `http://localhost:8000/docs`
4. Look for the "cartesia" tag in the API documentation

## Notes

- Maximum 5 files per voice clone
- Maximum 10MB per file
- Supported formats: WAV, MP3, M4A, FLAC, OGG
- Files are automatically converted to WAV if needed
- All S3 operations use server-side copy for efficiency
- Database saves are mandatory to prevent data inconsistency

