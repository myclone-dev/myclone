# Session Time Limits for Visitors

## Overview

This feature allows persona creators to configure session time limits for visitors interacting with their AI personas. When enabled, visitors will have a limited amount of time per session to interact with the persona, with a configurable warning before the session ends.

## Use Cases

- **Freemium models**: Limit free visitor interactions to encourage upgrades
- **Demo restrictions**: Provide timed demos for potential customers
- **Resource management**: Control AI usage per visitor session
- **Engagement optimization**: Encourage focused conversations

## Database Schema

Three new columns were added to the `personas` table:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `session_time_limit_enabled` | Boolean | `false` | Whether time limits are enforced for visitors |
| `session_time_limit_minutes` | Integer | `30` | Maximum session duration (range: 1-120 minutes) |
| `session_time_limit_warning_minutes` | Integer | `2` | Minutes before limit to show warning (range: 1-10 minutes) |

### Migration

Migration file: `alembic/versions/d402ba7fae6c_add_session_time_limit_to_personas.py`

```bash
# Run migration
make migrate

# Or manually
docker exec myclone_api /app/.venv/bin/alembic upgrade head

# Rollback if needed
make migrate-rollback
```

## API

### Persona Model Fields

The session time limit fields are included in the `PersonaBase`, `PersonaUpdate`, and `PersonaResponse` Pydantic models:

```python
# PersonaBase
session_time_limit_enabled: bool = Field(default=False)
session_time_limit_minutes: int = Field(default=30, ge=1, le=120)
session_time_limit_warning_minutes: int = Field(default=2, ge=1, le=10)

# PersonaUpdate (optional for partial updates)
session_time_limit_enabled: Optional[bool] = None
session_time_limit_minutes: Optional[int] = Field(None, ge=1, le=120)
session_time_limit_warning_minutes: Optional[int] = Field(None, ge=1, le=10)
```

### Update Persona Settings

```bash
# Enable session time limit with 15 minute limit and 2 minute warning
curl -X PATCH /api/v1/personas/{persona_id} \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "session_time_limit_enabled": true,
    "session_time_limit_minutes": 15,
    "session_time_limit_warning_minutes": 2
  }'
```

### Get Persona Settings

```bash
# Response includes session time limit fields
curl /api/v1/personas/{persona_id} \
  -H "Authorization: Bearer {token}"

# Response:
{
  "id": "...",
  "name": "My Persona",
  "session_time_limit_enabled": true,
  "session_time_limit_minutes": 15,
  "session_time_limit_warning_minutes": 2,
  ...
}
```

## Frontend Integration

### Settings UI

Creators can configure session time limits in the Persona Settings Dialog under the "Session" tab:

- **Enable toggle**: Turn session time limits on/off
- **Duration selector**: Choose session duration (1-120 minutes)
- **Warning time selector**: Choose when to show warning (1-10 minutes before limit)

Location: `src/components/dashboard/personas/PersonaSettingsDialog/tabs/SessionLimitTab/`

### Chat Interface

The chat interface handles session time limits with:

1. **useSessionTimeLimit hook**: Tracks total session time (not inactivity)
2. **SessionTimeLimitWarning component**: Shows countdown warning before session ends
3. **SessionTimeLimitExceeded component**: Shown when limit is reached, allows starting new session

Location:
- Hook: `src/hooks/useSessionTimeLimit.ts`
- Components: `src/components/expert/chat/SessionTimeLimitWarning.tsx`, `src/components/expert/chat/SessionTimeLimitExceeded.tsx`

### Key Differences from Inactivity Timeout

| Feature | Inactivity Timeout | Session Time Limit |
|---------|-------------------|-------------------|
| Resets on activity | Yes | No |
| Tracks | Time since last activity | Total session time |
| Purpose | Disconnect idle users | Limit total interaction time |
| Warning behavior | "Are you still there?" | "Session ending soon" |

## Sentry Tracking

The following events are tracked for analytics:

### Frontend Events (via `trackLiveKitEvent`)

| Event | Description |
|-------|-------------|
| `session_time_limit_warning_shown` | Warning overlay displayed |
| `session_time_limit_warning_dismissed` | User acknowledged warning |
| `session_time_limit_reached` | Session ended due to time limit |
| `session_new_after_time_limit` | User started new session after limit |

All events include metadata:
- `username`: Expert's username
- `personaName`: Persona name (if applicable)
- `mode`: "text" or "voice"
- `limitMinutes`: Configured time limit (where applicable)
- `remainingSeconds`: Seconds remaining when warning shown

## Configuration Defaults

```typescript
// From src/components/dashboard/personas/PersonaSettingsDialog/utils/constants.ts
export const MIN_SESSION_LIMIT_MINUTES = 1;
export const MAX_SESSION_LIMIT_MINUTES = 120;
export const DEFAULT_SESSION_LIMIT_MINUTES = 30;
export const MIN_SESSION_WARNING_MINUTES = 1;
export const MAX_SESSION_WARNING_MINUTES = 10;
export const DEFAULT_SESSION_WARNING_MINUTES = 2;
```

## Widget/Embed Support

Session time limits are fully supported in the widget/embed mode:

- Settings are passed from persona to `ExpertChatInterface`
- Works in both bubble mode and inline mode
- Same warning and exceeded UI as main chat

## Testing

### Manual Testing Steps

1. Create/edit a persona and enable session time limits
2. Set a short duration (e.g., 2 minutes) and warning (1 minute) for testing
3. Open the persona chat as a visitor
4. Wait for warning to appear (1 minute before limit)
5. Verify warning can be dismissed
6. Wait for session to end
7. Verify "Session Time Limit Exceeded" UI appears
8. Click "Start New Session" and verify new session works

### Verification Queries

```sql
-- Check if columns exist
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'personas'
AND column_name LIKE 'session_time_limit%';

-- Check persona settings
SELECT id, name, session_time_limit_enabled,
       session_time_limit_minutes,
       session_time_limit_warning_minutes
FROM personas
WHERE session_time_limit_enabled = true;
```

## File Changes Summary

### Backend

| File | Change |
|------|--------|
| `alembic/versions/d402ba7fae6c_*.py` | Migration to add columns |
| `shared/database/models/database.py` | ORM model fields |
| `shared/database/models/persona.py` | Pydantic model fields |

### Frontend

| File | Change |
|------|--------|
| `src/lib/queries/persona/interface.ts` | TypeScript interface |
| `src/components/dashboard/personas/PersonaSettingsDialog/types.ts` | Settings types |
| `src/components/dashboard/personas/PersonaSettingsDialog/utils/constants.ts` | Constants |
| `src/components/dashboard/personas/PersonaSettingsDialog/tabs/SessionLimitTab/` | Settings tab UI |
| `src/hooks/useSessionTimeLimit.ts` | Timer hook |
| `src/components/expert/chat/SessionTimeLimitWarning.tsx` | Warning component |
| `src/components/expert/chat/SessionTimeLimitExceeded.tsx` | Exceeded component |
| `src/components/expert/text/ExpertTextChat.tsx` | Integration |
| `src/lib/monitoring/sentry.ts` | Event tracking types |

## Future Enhancements

- [ ] Add session time limit support for voice chat (`ExpertVoiceChat.tsx`)
- [ ] Track session duration analytics per persona
- [ ] Add tier-based default limits
- [ ] Implement per-visitor session tracking (across multiple visits)
