# Document Duplicate Detection & Refresh Strategy

## Overview
This document outlines the implementation of checksum-based duplicate detection for document uploads and the refresh functionality for regenerating embeddings.

## Features Implemented

### 1. Checksum-Based Duplicate Detection
- **SHA-256 checksum** calculated for every uploaded file
- Stored in `document_metadata` JSONB field as `checksum`
- Generated column `checksum` in documents table for efficient querying
- Index on `(user_id, checksum)` for fast duplicate lookups

### 2. Three-Tier Validation
When a document is uploaded:
1. **Calculate checksum** of file content
2. **Check if document exists** by checksum + user_id
3. **Validate embeddings** exist in `data_llamaindex_embeddings` table

### 3. Upload Scenarios

#### Scenario 1: Document & Embeddings Both Exist
**Response:**
```json
{
  "success": false,
  "message": "Document already exists with embeddings. Use force=true to re-upload and re-process. Document ID: {id}",
  "document_id": "uuid",
  "supports_enrichment": true
}
```
**Action:** User should use `force=true` parameter to re-upload

#### Scenario 2: Document Exists but Embeddings Missing
**Response:**
```json
{
  "success": false,
  "message": "Document exists but embeddings are missing. Use the /refresh endpoint to regenerate embeddings. Document ID: {id}",
  "document_id": "uuid",
  "supports_enrichment": true
}
```
**Action:** User should call `/refresh` endpoint with document_id

#### Scenario 3: Force Mode Enabled
When `force=true`:
1. Delete existing embeddings from `data_llamaindex_embeddings`
2. Delete `persona_data_source` entries
3. Delete document record
4. Re-upload file to S3
5. Create fresh document entry
6. Queue new processing job

### 4. Refresh Endpoint

**Endpoint:** `POST /api/v1/documents/refresh`

**Parameters:**
- `user_id` (UUID): User who owns the document
- `document_id` (UUID): Document to refresh

**Process:**
1. Validate document exists and belongs to user
2. Delete all embeddings for this document from `data_llamaindex_embeddings`
3. Re-queue processing job using existing S3 file
4. Supports PDF, audio, and video files

## Database Changes

### Migration: `a1f2b3c4d5e6_add_checksum_to_documents.py`

**Up Migration:**
```sql
-- Add checksum as generated column
ALTER TABLE documents 
ADD COLUMN checksum TEXT 
GENERATED ALWAYS AS (metadata_->>'checksum') STORED;

-- Create index for efficient duplicate detection
CREATE INDEX idx_documents_checksum_user 
ON documents (user_id, checksum) 
WHERE checksum IS NOT NULL;
```

**Down Migration:**
```sql
DROP INDEX idx_documents_checksum_user;
ALTER TABLE documents DROP COLUMN checksum;
```

### Document Model Changes
Added generated column to `Document` model:
```python
checksum: Mapped[Optional[str]] = mapped_column(
    Text,
    Computed("metadata_->>'checksum'", persisted=True),
    comment="SHA-256 checksum of file content for duplicate detection",
)
```

## API Changes

### `/api/v1/documents/add` Endpoint

**New Parameters:**
- `force` (bool, default=False): Force re-upload even if document exists

**Updated Flow:**
1. Read file content
2. Calculate SHA-256 checksum
3. Check for duplicates
4. Handle based on scenario (see above)
5. Upload to S3 (if proceeding)
6. Store checksum in metadata
7. Queue processing job

### `/api/v1/documents/refresh` Endpoint (NEW)

**Parameters:**
- `user_id` (UUID, required): User UUID
- `document_id` (UUID, required): Document UUID to refresh

**Process:**
1. Validate document ownership
2. Delete existing embeddings
3. Re-queue processing job with existing S3 file

## Utility Functions

### `document_utils.py`

#### `calculate_file_checksum(content: bytes) -> str`
Calculates SHA-256 hash of file content.

#### `check_document_dependency(session, user_id, checksum) -> Tuple[Optional[Document], bool]`
Returns:
- `Document`: Existing document or None
- `bool`: True if embeddings exist in `data_llamaindex_embeddings`

#### `cleanup_document_data(session, document_id, persona_id=None)`
Deletes:
- Embeddings from `data_llamaindex_embeddings`
- `persona_data_source` entries
- Document record

#### `delete_document_embeddings(session, document_id) -> int`
Deletes embeddings and returns count deleted.

## Usage Examples

### Upload New Document
```bash
curl -X POST "http://localhost:8000/api/v1/documents/add" \
  -H "x-api-key: your-api-key" \
  -F "user_id=123e4567-e89b-12d3-a456-426614174000" \
  -F "persona_name=default" \
  -F "file=@document.pdf"
```

### Upload with Force (Re-upload)
```bash
curl -X POST "http://localhost:8000/api/v1/documents/add" \
  -H "x-api-key: your-api-key" \
  -F "user_id=123e4567-e89b-12d3-a456-426614174000" \
  -F "persona_name=default" \
  -F "force=true" \
  -F "file=@document.pdf"
```

### Refresh Embeddings
```bash
curl -X POST "http://localhost:8000/api/v1/documents/refresh" \
  -H "x-api-key: your-api-key" \
  -F "user_id=123e4567-e89b-12d3-a456-426614174000" \
  -F "document_id=789e0123-e89b-12d3-a456-426614174000"
```

## Benefits

1. **Prevents Duplicate Uploads**: Automatically detects identical files by content
2. **Efficient Storage**: No duplicate files in S3
3. **Cost Savings**: Avoid re-processing same content
4. **User Control**: `force` parameter for intentional re-uploads
5. **Self-Service Recovery**: `/refresh` endpoint for fixing missing embeddings
6. **Fast Lookups**: Index on checksum enables O(1) duplicate detection

## Implementation Details

### Checksum Storage Strategy
- **Metadata Field**: Checksum stored in `document_metadata` JSONB as `{"checksum": "sha256..."}`
- **Generated Column**: `checksum` column auto-populated from JSONB
- **Benefits**: No schema migration for existing data, automatic extraction

### Embeddings Detection
Query checks `data_llamaindex_embeddings` table:
```sql
SELECT EXISTS(
    SELECT 1 FROM data_llamaindex_embeddings 
    WHERE metadata_->>'document_id' = :doc_id
)
```

### Cleanup Strategy
When force mode or refresh:
1. Delete embeddings by `metadata_->>'document_id'`
2. Delete persona data sources by `source_record_id`
3. Delete document record (cascade deletes handled by DB)

## Files Changed

1. **Migration**: `alembic/versions/a1f2b3c4d5e6_add_checksum_to_documents.py`
2. **Model**: `shared/database/models/document.py`
3. **Utils**: `app/api/document_utils.py` (new file)
4. **Routes**: `app/api/document_routes.py`

## Testing Recommendations

1. **Test duplicate detection**: Upload same file twice
2. **Test force mode**: Upload with force=true
3. **Test refresh**: Call refresh on document with/without embeddings
4. **Test different file types**: PDF, MP3, MP4, etc.
5. **Test error cases**: Invalid user_id, missing document, etc.

## Future Enhancements

1. **Batch refresh**: Refresh embeddings for multiple documents
2. **Checksum history**: Track all checksums for audit
3. **Partial match**: Detect similar (but not identical) documents
4. **Background cleanup**: Periodically clean orphaned embeddings

