# Automatic HTTP Error Capture in Sentry

## Overview

Sentry automatically captures HTTP errors **without requiring manual `capture_exception_with_context()` calls** in every endpoint. This is done via FastAPI integration's `failed_request_status_codes` configuration.

## What Gets Captured Automatically

✅ **422 Unprocessable Entity**
- Voice upload failures (ElevenLabs API errors)
- Payment processing errors (Stripe integration issues)
- Persona creation failures
- License activation errors
- Any validation/processing error that could be our fault

✅ **500-599 Server Errors**
- Internal server errors
- Database failures
- Unhandled exceptions
- Service unavailability

## Configuration

Located in: `shared/monitoring/sentry_utils.py`

```python
FastApiIntegration(
    transaction_style="endpoint",
    failed_request_status_codes={422, *range(500, 600)},  # Auto-capture 422 + 5xx
)
```

## What Gets Tagged

Every captured HTTP error automatically includes:

| Tag | Example | Purpose |
|-----|---------|---------|
| `http_status` | `"422"`, `"500"` | Filter by status code |
| `error_type` | `"validation_error"`, `"server_error"` | Group by error category |
| `severity` | `"high"`, `"medium"`, `"low"` | Priority triage |
| `component` | `"api"` | Which service (api/worker) |
| `endpoint` | `"/api/v1/voice/upload"` | Which API endpoint |

## What NOT to Capture

❌ **404 Not Found** - Usually user typos or deleted resources
❌ **400 Bad Request** - User sent malformed data
❌ **401/403 Unauthorized** - Expected authentication failures

If you need to capture these, add them to `failed_request_status_codes`:

```python
failed_request_status_codes={404, 422, *range(500, 600)}  # Also capture 404s
```

## Example Sentry Queries

**All voice upload errors:**
```
endpoint:"/api/v1/voice/upload"
```

**All 422 errors:**
```
http_status:"422"
```

**High severity only:**
```
severity:"high"
```

**All validation errors:**
```
error_type:"validation_error"
```

## When to Use Manual Capture

You still need `capture_exception_with_context()` for:

1. **Background jobs/workers** - Not HTTP requests, so auto-capture doesn't apply
2. **Warning-level issues** - Not errors but worth tracking
3. **Rich context in HTTP errors** - When you need business context for debugging
   - Auto-capture gives you URL/method/headers/request body (HTTP context)
   - Manual capture adds user_id, persona_id, file_id, etc. (business context)
   - **Critical for debugging**: Knowing which user/resource caused the error

### Example 1: Background Job (Always Manual)
```python
try:
    result = await background_job()
except Exception as e:
    capture_exception_with_context(
        e,
        extra={"job_id": str(job_id), "user_id": str(user_id)},
        tags={"component": "worker", "job_type": "scraping"}
    )
    raise
```

### Example 2: HTTP Error With Rich Context (Recommended for Critical Endpoints)
```python
# ❌ Auto-capture only (basic HTTP context)
try:
    await upload_voice(file)
except VoiceProcessingError as e:
    raise HTTPException(status_code=422, detail=str(e))
# Sentry gets: URL, method, headers, but NOT user_id or voice_id

# ✅ Manual capture first (business context + HTTP context)
try:
    await upload_voice(file)
except VoiceProcessingError as e:
    capture_exception_with_context(
        e,
        extra={
            "user_id": str(user_id),
            "voice_id": str(voice_id),
            "file_name": file.filename,
            "file_size": file.size,
        },
        tags={
            "component": "voice_processing",
            "operation": "upload",
            "severity": "medium",
            "user_facing": "true",
        },
    )
    raise HTTPException(status_code=422, detail=str(e)) from e
# Sentry gets: URL, method, headers, PLUS user_id, voice_id, file details
```

### When to Add Manual Capture to HTTP Errors

✅ **Always add for:**
- Payment/subscription operations (user_id, subscription_id, amount)
- Voice processing (user_id, voice_id, file details)
- Persona operations (user_id, persona_id)
- Data ingestion (user_id, source, record count)

❌ **Skip manual capture for:**
- Simple validation errors (auto-capture is enough)
- List/read operations (no state change)
- Low-criticality endpoints

## Testing

To test if it works:

1. **Trigger a 422 error** (e.g., upload invalid file to voice endpoint)
2. **Check Sentry dashboard** within 1-2 minutes
3. **Verify tags** are present (http_status, error_type, endpoint)

## Benefits

✅ **Zero manual work** - No need to add Sentry calls to every endpoint
✅ **Automatic context** - URL, method, headers, request body captured
✅ **Consistent tagging** - All errors tagged uniformly
✅ **Easy filtering** - Find errors by status code, endpoint, severity
✅ **No missed errors** - Can't forget to add Sentry capture

## Adjusting Capture Rules

If you want to change what gets captured:

**Capture only 500 errors:**
```python
failed_request_status_codes={*range(500, 600)}
```

**Capture 404s too:**
```python
failed_request_status_codes={404, 422, *range(500, 600)}
```

**Capture all 4xx and 5xx:**
```python
failed_request_status_codes={*range(400, 600)}
```

**Disable automatic capture (not recommended):**
```python
failed_request_status_codes=set()  # Empty set = nothing captured
```
