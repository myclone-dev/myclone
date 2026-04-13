# Voice Usage Limits Implementation

## Overview

This document describes the voice usage limits feature that tracks and limits voice conversation minutes for persona owners. The billing model is **owner-based**, meaning when anyone calls a persona, the **persona owner's** quota is consumed, not the caller's.

## Tier Limits

| Tier | Voice Minutes/Month |
|------|---------------------|
| Free (0) | 10 minutes |
| Pro (1) | 100 minutes |
| Business (2) | 400 minutes |
| Enterprise (3) | Unlimited (-1) |

## Architecture

### Key Concepts

1. **Owner-Based Billing**: When a visitor calls a persona, the persona owner pays for the voice minutes, not the caller
2. **Monthly Reset**: Usage resets at the beginning of each billing period
3. **Per-Persona Tracking**: Usage is tracked per persona for dashboard visibility
4. **Grace Period**: 30-second grace period after limit is reached for goodbyes

### Database Schema

#### `tier_plans` Table (Modified)
```sql
ALTER TABLE tier_plans ADD COLUMN max_voice_minutes_per_month INTEGER DEFAULT 10;
```

Values:
- tier 0 (Free): 10
- tier 1 (Pro): 100
- tier 2 (Business): 400
- tier 3 (Enterprise): -1 (unlimited)

#### `user_usage_cache` Table (Modified)
```sql
ALTER TABLE user_usage_cache ADD COLUMN voice_seconds_used BIGINT DEFAULT 0;
ALTER TABLE user_usage_cache ADD COLUMN voice_usage_reset_at TIMESTAMP;
```

#### `voice_sessions` Table (New)
```sql
CREATE TABLE voice_sessions (
    id UUID PRIMARY KEY,
    persona_id UUID NOT NULL REFERENCES personas(id),
    persona_owner_id UUID NOT NULL REFERENCES users(id),
    caller_session_token VARCHAR(255),
    room_name VARCHAR(255) NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMP,
    duration_seconds INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

Status values: `active`, `completed`, `limit_exceeded`, `disconnected`

## Services

### VoiceUsageService (`shared/services/voice_usage_service.py`)

Main service for managing voice usage limits and session tracking.

#### Methods

##### `check_owner_voice_limit(persona_id: UUID) -> Tuple[bool, int, int]`
Check if persona owner has remaining voice quota.

**Returns**: `(can_start, remaining_seconds, limit_seconds)`

**Logic**:
1. Get persona from database
2. Get owner's tier plan
3. If unlimited (-1), return True
4. Calculate remaining = limit - used
5. Return whether remaining > 0

##### `start_voice_session(persona_id: UUID, room_name: str, session_token: str) -> VoiceSession`
Start tracking a new voice session.

**Creates**:
- New `VoiceSession` record with `persona_owner_id` set to the persona's owner
- Links session to persona for per-persona tracking

##### `update_session_duration(session_id: UUID, duration_seconds: int) -> bool`
Update session duration during heartbeat.

**Returns**: `False` if owner's limit is exceeded (triggers disconnect)

**Logic**:
1. Update session's `duration_seconds`
2. Calculate owner's total usage
3. If usage exceeds limit, return False
4. Otherwise return True

##### `end_voice_session(session_id: UUID, final_duration_seconds: int)`
End a voice session and deduct from owner's quota.

**Actions**:
1. Update session with final duration and `ended_at`
2. Set status to `completed`
3. Add duration to owner's `voice_seconds_used` in `user_usage_cache`

##### `get_owner_voice_usage(user_id: UUID) -> Dict`
Get voice usage statistics for dashboard.

**Returns**:
```python
{
    "minutes_used": float,
    "minutes_limit": int,  # -1 for unlimited
    "percentage": float,
    "reset_date": datetime
}
```

##### `get_per_persona_usage(user_id: UUID) -> List[Dict]`
Get breakdown of voice usage by persona.

**Returns**:
```python
[
    {
        "persona_id": "uuid",
        "persona_name": "default",
        "display_name": "Rohan Sharma",
        "minutes_used": float
    }
]
```

## API Endpoints

### GET `/api/v1/tier/usage`

Returns comprehensive usage data including voice.

**Response** (voice section):
```json
{
  "voice": {
    "minutes_used": 3.8,
    "minutes_limit": 10,
    "percentage": 38.0,
    "reset_date": "2026-01-01T00:00:00Z",
    "per_persona": [
      {
        "persona_id": "uuid",
        "persona_name": "default",
        "display_name": "Rohan Sharma",
        "minutes_used": 3.8
      }
    ]
  }
}
```

### LiveKit Routes (`app/api/livekit_routes.py`)

#### POST `/api/v1/livekit/room` (Modified)

Before creating a room:
1. Check owner's voice quota via `check_owner_voice_limit()`
2. If quota exhausted, return 403:
```json
{
  "detail": "Voice limit exceeded",
  "voice_limit_exceeded": true
}
```
3. If quota available, create session and return `session_id`

#### POST `/api/v1/livekit/session/{session_id}/heartbeat` (New)

Called every 30 seconds during active call.

**Request**:
```json
{
  "duration_seconds": 180
}
```

**Response**:
```json
{
  "continue": true
}
```

Or if limit exceeded:
```json
{
  "continue": false,
  "reason": "voice_limit_exceeded"
}
```

#### POST `/api/v1/livekit/session/{session_id}/end` (New)

Called when voice session ends.

**Request**:
```json
{
  "final_duration_seconds": 245
}
```

### GET `/api/v1/personas/{persona_id}/conversations`

**Modified**: Now includes `voice_duration_seconds` in each conversation summary for voice conversations.

```json
{
  "conversations": [
    {
      "id": "uuid",
      "conversation_type": "voice",
      "voice_duration_seconds": 234,
      ...
    }
  ]
}
```

## Frontend Integration

### Navbar Voice Usage Indicator

Component: `VoiceUsageIndicator.tsx`

- Circular progress ring showing usage percentage
- Color-coded: amber (normal), orange (75%+), red (90%+), green (unlimited)
- Popover with detailed stats and link to usage page

### Usage Page

Two sections:
1. **Knowledge Library Limits**: Raw Text, Documents, Audio & Video, YouTube
2. **Voice Agent Usage**: Voice Chat with per-persona breakdown

### Conversation Cards

Voice conversations show duration badge (e.g., "3m 45s") next to the voice type badge.

## Flow Diagrams

### Starting a Voice Call

```
Visitor clicks "Start Voice Call"
        │
        ▼
Frontend: POST /livekit/room
        │
        ▼
Backend: Get persona owner
        │
        ▼
Backend: check_owner_voice_limit(persona_id)
        │
        ├─── Quota Available ───┐
        │                       ▼
        │               Create VoiceSession
        │                       │
        │                       ▼
        │               Create LiveKit room
        │                       │
        │                       ▼
        │               Return room token + session_id
        │
        └─── Quota Exhausted ───┐
                                ▼
                        Return 403
                                │
                                ▼
                Frontend: Show VoiceLimitExceeded
```

### During Active Call

```
Every 30 seconds:
        │
        ▼
Frontend: POST /session/{id}/heartbeat
        │
        ▼
Backend: update_session_duration()
        │
        ├─── Under Limit ───┐
        │                   ▼
        │           Return {continue: true}
        │
        └─── Over Limit ───┐
                           ▼
                   Return {continue: false}
                           │
                           ▼
                Frontend: Gracefully disconnect
                           │
                           ▼
                Show "Voice session ended"
```

### Ending a Call

```
User hangs up OR limit exceeded
        │
        ▼
Frontend: POST /session/{id}/end
        │
        ▼
Backend: end_voice_session()
        │
        ├── Update session.ended_at
        ├── Update session.duration_seconds
        ├── Update session.status = 'completed'
        └── Add to owner's voice_seconds_used
```

## Edge Cases

### Mid-Call Limit Reached
- Heartbeat returns `{continue: false}`
- Frontend gracefully disconnects with 30-second grace period
- User sees "Voice session ended" message
- Option to continue with text chat

### Network Disconnect
- Backend cleanup job runs every 15 minutes
- Sessions with no heartbeat for 15+ minutes are marked as `disconnected`
- Duration is estimated from last known heartbeat

### Multiple Personas
- All personas owned by user share the same quota
- Per-persona breakdown shows contribution of each

### Concurrent Calls
- Multiple simultaneous calls all count toward owner's quota
- Each session tracked independently
- Total calculated as sum of all active sessions

### Monthly Reset
- `voice_usage_reset_at` tracks next reset date
- On first API call after reset date:
  - `voice_seconds_used` set to 0
  - `voice_usage_reset_at` set to next month

## Migration

### Running the Migration

```bash
cd digital-clone-poc
alembic upgrade head
```

### Seeding Tier Limits

If tier_plans don't have voice limits set:

```sql
UPDATE tier_plans SET max_voice_minutes_per_month = 10 WHERE tier = 0;
UPDATE tier_plans SET max_voice_minutes_per_month = 100 WHERE tier = 1;
UPDATE tier_plans SET max_voice_minutes_per_month = 400 WHERE tier = 2;
UPDATE tier_plans SET max_voice_minutes_per_month = -1 WHERE tier = 3;
```

## Testing

### Manual Testing

1. **Check quota before call**:
```bash
curl -X GET "http://localhost:8000/api/v1/tier/usage" \
  -H "Authorization: Bearer $TOKEN"
```

2. **Start voice session** (should succeed if quota available):
```bash
curl -X POST "http://localhost:8000/api/v1/livekit/room" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"persona_id": "uuid"}'
```

3. **Test limit exceeded** (set usage to max, then try to start):
```sql
UPDATE user_usage_cache
SET voice_seconds_used = 600
WHERE user_id = 'uuid';
```

Then try to start a call - should return 403.

## Monitoring

### Key Metrics to Track

- Total voice minutes consumed per day/week/month
- Number of limit-exceeded events
- Average session duration
- Sessions per persona
- Concurrent sessions peak

### Sentry Events

The following events are tracked:
- `voice_session_start`: When a session begins
- `voice_session_end`: When a session ends
- `voice_limit_exceeded`: When user hits their limit
- `voice_limit_warning`: When user reaches 75%/90% thresholds
