# Webhook Integration - Technical Specification

## Overview

Implement a generic webhook system that allows persona owners to receive real-time event notifications when specific actions occur (conversations finishing, payments, etc.). This enables integration with Zapier, Make, n8n, and custom backends.

**MVP Scope:** `conversation.finished` event for voice conversations only.

---

## Architecture

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Scope** | Persona-level | Conversations are persona-specific; each persona can have its own webhook destination |
| **Naming** | Generic "webhook" (not "zapier") | Supports any webhook consumer (Zapier, Make, n8n, custom backends) |
| **Multiple webhooks** | Single webhook URL per persona | Simplifies MVP; can migrate to multi-webhook table later if needed |
| **Event filtering** | Send all events (configurable via JSONB field) | User can filter events on their end; we populate `webhook_events` for future filtering |
| **Retry logic** | No retry (fire-and-forget) | Keep MVP simple; log failures to Sentry |
| **Delivery mode** | Asynchronous | Don't block conversation lifecycle; mirror email summary pattern |

---

## Database Schema Changes

### Table: `personas`

**New columns to add:**

```sql
ALTER TABLE personas ADD COLUMN webhook_enabled BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE personas ADD COLUMN webhook_url VARCHAR(500) NULL;
ALTER TABLE personas ADD COLUMN webhook_events JSONB DEFAULT '["conversation.finished"]'::jsonb;
ALTER TABLE personas ADD COLUMN webhook_secret VARCHAR(255) NULL;
```

**Column details:**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `webhook_enabled` | `BOOLEAN` | NOT NULL | `FALSE` | Master toggle for webhook delivery |
| `webhook_url` | `VARCHAR(500)` | NULL | `NULL` | HTTPS endpoint to POST events to |
| `webhook_events` | `JSONB` | NULL | `["conversation.finished"]` | Array of event types to send (future filtering) |
| `webhook_secret` | `VARCHAR(255)` | NULL | `NULL` | Optional secret for HMAC signature (unused in MVP, future-proofing) |

**Migration file:** `alembic/versions/xxx_add_webhook_to_personas.py`

---

## Event Structure

### Standard Event Envelope

All webhook events use consistent JSON structure:

```json
{
  "event": "conversation.finished",
  "timestamp": "2025-12-20T10:30:00Z",
  "persona": {
    "id": "uuid",
    "name": "Steve Jobs",
    "persona_name": "steve-jobs"
  },
  "data": {
    // Event-specific payload (see below)
  }
}
```

### Event: `conversation.finished`

**Trigger:** Voice conversation ends (LiveKit agent `on_exit()`)

**Payload structure:**

```json
{
  "event": "conversation.finished",
  "timestamp": "2025-12-20T10:30:00Z",
  "persona": {
    "id": "persona-uuid",
    "name": "Steve Jobs",
    "persona_name": "steve-jobs"
  },
  "data": {
    "conversation_id": "conv-uuid",
    "conversation_type": "voice",
    "started_at": "2025-12-20T09:45:00Z",
    "ended_at": "2025-12-20T10:00:00Z",
    "duration_seconds": 900,
    "message_count": 12,
    "messages": [
      {
        "role": "user",
        "content": "Hello, how are you?",
        "timestamp": "2025-12-20T09:45:00Z"
      },
      {
        "role": "assistant",
        "content": "I'm doing great! How can I help you today?",
        "timestamp": "2025-12-20T09:45:05Z"
      }
      // ... all messages
    ],
    "visitor": {
      "email": "visitor@example.com",    // Only if captured
      "fullname": "John Doe",            // Only if captured
      "phone": "+1234567890"             // Only if captured
    }
  }
}
```

**Data source:** Query `conversations` table and related `user_sessions` table (same as email summary)

**Visitor data rules:**
- Only include `visitor` object if email was captured (`email_provided=true` in session metadata)
- Skip anonymous emails (starting with `anon_`)

---

## Service Layer

### New File: `app/services/webhook_service.py`

**Class:** `WebhookService`

**Pattern:** Instance methods (stateful service, follows `EmailService` pattern)

**Dependencies:**
- HTTP client (aiohttp or httpx)
- Logger
- Sentry utils

**Methods:**

```python
class WebhookService:
    """Generic webhook delivery service for persona events"""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=10.0)
        self.logger = logging.getLogger(__name__)

    async def send_event(
        self,
        persona_id: UUID,
        event_type: str,
        event_data: dict
    ) -> bool:
        """
        Send webhook event to persona's configured webhook URL

        Returns:
            True if sent successfully, False if failed or webhook not enabled
        """
        pass

    async def _validate_webhook_url(self, url: str) -> bool:
        """Simple validation: must be HTTPS"""
        pass

    async def _build_payload(
        self,
        persona: Persona,
        event_type: str,
        event_data: dict
    ) -> dict:
        """Build standard event envelope"""
        pass

    async def _send_http_post(self, url: str, payload: dict) -> bool:
        """POST to webhook URL with timeout and error handling"""
        pass
```

**HTTP Request Details:**
- Method: `POST`
- Headers:
  - `Content-Type: application/json`
  - `User-Agent: ExpertClone/1.0`
- Timeout: 10 seconds
- Success: HTTP 200-299
- Failure: Any other status code, timeout, network error

**Error Handling:**
- Log all failures to Sentry with context:
  - `extra`: `persona_id`, `event_type`, `webhook_url`, `error_message`
  - `tags`: `component="webhook"`, `operation="send_event"`, `severity="medium"`, `user_facing="false"`
- Don't raise exceptions (fire-and-forget)
- Return boolean success/failure

---

## Integration Points

### Voice Conversations: LiveKit Agent

**File:** `livekit/livekit_agent_retrieval.py`

**Hook location:** `PersonaRetrievalAgent.on_exit()` method

**New method to add:**

```python
async def _send_webhook_event(self):
    """Send webhook event for conversation.finished

    Mirrors _send_voice_summary() pattern:
    - Check if webhook enabled for persona
    - Wait for conversation to be persisted (2 sec delay)
    - Build event payload from conversation data
    - Fire-and-forget webhook delivery
    - Log errors, don't block agent shutdown
    """
    pass
```

**Call from `on_exit()`:**

```python
async def on_exit(self):
    logger.info(f"🚪 [{self.persona_username}] Agent is closing - goodbye! 👋")

    # Send voice conversation summary email
    await self._send_voice_summary()

    # Send webhook event (NEW)
    await self._send_webhook_event()

    # Clean up active room from database
    # ...
```

**Data retrieval:**
- Query `conversations` table by `persona_id` + `session_id`
- Join `user_sessions` for visitor data (if `email_provided=true`)
- Include full `messages` JSONB array from conversation record

---

## API Changes

### Pydantic Schemas

**File:** `shared/schemas/knowledge_library.py`

**Update `PersonaUpdateWithKnowledge` (around line 333):**

```python
# Webhook Settings
webhook_enabled: Optional[bool] = Field(
    None, description="Whether webhook integration is enabled for this persona"
)
webhook_url: Optional[str] = Field(
    None, max_length=500, description="HTTPS webhook URL for receiving events"
)
webhook_events: Optional[List[str]] = Field(
    None, description="List of event types to send (e.g., ['conversation.finished'])"
)
webhook_secret: Optional[str] = Field(
    None, max_length=255, description="Optional secret for webhook signature verification (unused in MVP)"
)
```

**Update `PersonaWithKnowledgeResponse` (around line 397):**

```python
# Webhook Settings
webhook_enabled: bool = Field(
    default=False, description="Whether webhook integration is enabled"
)
webhook_url: Optional[str] = Field(
    default=None, description="Webhook URL"
)
webhook_events: Optional[List[str]] = Field(
    default=None, description="Events to send to webhook"
)
```

**Note:** Don't expose `webhook_secret` in response (security)

### API Endpoint Handler

**File:** `app/api/persona_knowledge_routes.py`

**Update `update_persona_with_knowledge()` handler (around line 543):**

```python
# Update webhook settings
if request.webhook_enabled is not None:
    persona.webhook_enabled = request.webhook_enabled
if request.webhook_url is not None:
    # Validate HTTPS URL
    if request.webhook_url and not request.webhook_url.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="Webhook URL must use HTTPS"
        )
    persona.webhook_url = request.webhook_url
if request.webhook_events is not None:
    persona.webhook_events = request.webhook_events
if request.webhook_secret is not None:
    persona.webhook_secret = request.webhook_secret
```

**Endpoint:** `PATCH /api/v1/personas/{persona_id}/with-knowledge`

**Request example:**

```json
{
  "webhook_enabled": true,
  "webhook_url": "https://hooks.zapier.com/hooks/catch/123456/abcdef/",
  "webhook_events": ["conversation.finished"]
}
```

**Response example:**

```json
{
  "id": "persona-uuid",
  "name": "Steve Jobs",
  "webhook_enabled": true,
  "webhook_url": "https://hooks.zapier.com/hooks/catch/123456/abcdef/",
  "webhook_events": ["conversation.finished"],
  // ... other persona fields
}
```

---

## Security & Validation

### URL Validation

**Requirements:**
- Must start with `https://`
- Maximum length: 500 characters
- Basic format check (valid URL structure)

**Implementation:**

```python
from urllib.parse import urlparse

def validate_webhook_url(url: str) -> bool:
    if not url.startswith("https://"):
        return False
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False
```

### Webhook Secret (Future)

**MVP:** Field added to schema, not used
**Future:** Generate HMAC-SHA256 signature of payload, send in `X-Webhook-Signature` header

---

## Error Handling & Monitoring

### Sentry Integration (Mandatory)

**All webhook delivery failures must be logged to Sentry:**

```python
from shared.monitoring.sentry_utils import capture_exception_with_context

try:
    response = await self.http_client.post(webhook_url, json=payload)
    # ...
except Exception as e:
    capture_exception_with_context(
        e,
        extra={
            "persona_id": str(persona_id),
            "event_type": event_type,
            "webhook_url": webhook_url,
            "payload_size": len(json.dumps(payload)),
        },
        tags={
            "component": "webhook",
            "operation": "send_event",
            "severity": "medium",
            "user_facing": "false",
        },
    )
    logger.error(f"Webhook delivery failed: {e}")
    return False
```

### Failure Scenarios

| Scenario | Handling |
|----------|----------|
| Webhook URL unreachable | Log to Sentry, return False |
| Webhook returns 4xx/5xx | Log to Sentry, return False |
| Request timeout (>10s) | Log to Sentry, return False |
| Invalid webhook URL | Skip delivery, log warning |
| Webhook disabled | Skip delivery silently |

**No retry logic:** Keep MVP simple, log failure, move on

**No user notification:** Persona owners won't be notified of delivery failures (can add later)

---

## Testing Strategy

### Manual Testing

**Setup:**
1. Create test persona with webhook enabled
2. Use Zapier "Catch Hook" trigger to get webhook URL
3. Configure persona with Zapier webhook URL
4. Start voice conversation with persona
5. End conversation (hang up)
6. Verify webhook payload received in Zapier

**Test cases:**
- ✅ Webhook enabled, valid URL → event delivered
- ✅ Webhook enabled, invalid URL → logged to Sentry, no crash
- ✅ Webhook disabled → no event sent
- ✅ Conversation with email capture → visitor data included
- ✅ Conversation without email capture → visitor object null/empty
- ✅ Webhook timeout → logged to Sentry, agent exits cleanly

### Development Testing (ngrok)

For local development without Zapier:

```bash
# Terminal 1: Start ngrok
ngrok http 3000

# Terminal 2: Simple webhook receiver
python -m http.server 3000

# Or use RequestBin, webhook.site, etc.
```

---

## Future Enhancements (Out of Scope for MVP)

### Additional Events

```
conversation.started
conversation.message_threshold
visitor.identified
payment.received
payment.failed
subscription.created
subscription.canceled
persona.created
persona.updated
data_source.added
data_source.failed
```

### Advanced Features

- Multiple webhooks per persona (separate table)
- Webhook delivery history/logs table
- Webhook signature verification (HMAC-SHA256)
- Webhook health monitoring (auto-disable after N failures)
- User notification of webhook failures
- Webhook testing endpoint (`POST /personas/{id}/test-webhook`)
- Event filtering UI (checkboxes for which events to send)
- Retry logic with exponential backoff
- Dead letter queue for failed deliveries

---

## Implementation Checklist

### Database
- [ ] Create Alembic migration adding 4 webhook columns to `personas` table
- [ ] Run migration in development
- [ ] Verify schema changes

### Pydantic Models
- [ ] Add webhook fields to `PersonaUpdateWithKnowledge` schema
- [ ] Add webhook fields to `PersonaWithKnowledgeResponse` schema
- [ ] Don't expose `webhook_secret` in response

### Service Layer
- [ ] Create `app/services/webhook_service.py`
- [ ] Implement `WebhookService` class
- [ ] Add URL validation
- [ ] Add payload builder
- [ ] Add HTTP POST with timeout
- [ ] Add Sentry error logging

### LiveKit Integration
- [ ] Add `_send_webhook_event()` method to `PersonaRetrievalAgent`
- [ ] Call from `on_exit()` after email summary
- [ ] Query conversation + messages from database
- [ ] Query visitor data from `user_sessions`
- [ ] Build event payload
- [ ] Fire-and-forget webhook delivery

### API Endpoint
- [ ] Update `update_persona_with_knowledge()` handler in `persona_knowledge_routes.py`
- [ ] Add webhook field updates (enabled, url, events, secret)
- [ ] Add HTTPS URL validation
- [ ] Test with Postman/curl

### Testing
- [ ] Manual test with Zapier catch hook
- [ ] Test with email capture enabled
- [ ] Test with email capture disabled
- [ ] Test webhook disabled (no event sent)
- [ ] Test invalid URL (Sentry log, no crash)
- [ ] Test timeout scenario
- [ ] Verify agent exits cleanly after webhook send

### Documentation
- [ ] Update API documentation with webhook fields
- [ ] Add webhook setup guide (how to use with Zapier)
- [ ] Update CLAUDE.md if needed

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `alembic/versions/xxx_add_webhook_to_personas.py` | **CREATE** | Database migration |
| `app/services/webhook_service.py` | **CREATE** | Webhook delivery service |
| `shared/schemas/knowledge_library.py` | **MODIFY** | Add webhook fields to schemas |
| `shared/database/models/database.py` | **MODIFY** | ORM model (auto-generated by Alembic) |
| `app/api/persona_knowledge_routes.py` | **MODIFY** | Add webhook update logic to PATCH handler |
| `livekit/livekit_agent_retrieval.py` | **MODIFY** | Add `_send_webhook_event()` + call from `on_exit()` |

**Estimated lines of code:** ~250-300 lines across all files

---

## Example: Complete Webhook Flow

**Scenario:** User configures Zapier webhook for persona "Steve Jobs"

```
1. User → PATCH /api/v1/personas/{id}/with-knowledge
   Body: {
     "webhook_enabled": true,
     "webhook_url": "https://hooks.zapier.com/hooks/catch/123/abc"
   }

2. Database: personas.webhook_enabled = true, webhook_url = "..."

3. Visitor starts voice conversation with Steve Jobs persona

4. Visitor talks for 15 minutes, exchanges 12 messages

5. Visitor hangs up → LiveKit agent on_exit() triggered

6. Agent:
   - Waits 2 seconds (conversation persisted)
   - Calls _send_webhook_event()

7. WebhookService:
   - Queries conversation from DB (persona_id + session_id)
   - Queries visitor data from user_sessions (if email captured)
   - Builds event payload:
     {
       "event": "conversation.finished",
       "timestamp": "...",
       "persona": { "id": "...", "name": "Steve Jobs", ... },
       "data": {
         "conversation_id": "...",
         "messages": [ ... 12 messages ... ],
         "visitor": { "email": "...", "fullname": "..." }
       }
     }
   - POSTs to https://hooks.zapier.com/hooks/catch/123/abc
   - Returns success/failure (logged, not blocking)

8. Zapier receives webhook → triggers workflow (log to Sheets, send Slack, etc.)

9. Agent continues shutdown (clean up room, exit)
```

---

## Non-Goals (MVP)

- ❌ Chat conversation webhooks (voice only for MVP)
- ❌ Webhook retry logic
- ❌ Webhook delivery history
- ❌ Webhook signature verification
- ❌ Multiple webhooks per persona
- ❌ Webhook test endpoint
- ❌ User notification of failures
- ❌ Event filtering UI (send all events by default)
- ❌ Other event types (payment, visitor.identified, etc.)

---

## Success Criteria

✅ Persona owners can configure webhook URL via API
✅ `conversation.finished` event is sent when voice conversation ends
✅ Event payload includes full conversation + messages
✅ Visitor data included if email was captured
✅ Webhook failures logged to Sentry (don't crash agent)
✅ HTTPS validation prevents insecure URLs
✅ Manual test with Zapier catch hook succeeds

---

**Spec Version:** 1.0
**Date:** 2025-12-20
**Author:** Claude (with contributor)
