# Text Chat Usage Limits

This document describes the text chat usage limits feature, which enforces monthly message quotas for persona owners based on their subscription tier.

## Overview

Text chat usage is **charged to the persona owner**, not the visitor. When anyone chats with a persona (via the agent page or embedded widget), the owner's monthly quota is consumed.

## Tier Limits

| Tier ID | Tier Name | Messages/Month | Notes |
|---------|-----------|----------------|-------|
| 0 | Free | 500 | Default for new users |
| 1 | Pro | 10,000 | - |
| 2 | Business | 40,000 | - |
| 3 | Enterprise | Unlimited (-1) | No limit enforced |

## Architecture

### Billing Model

```
┌─────────────┐     sends message     ┌─────────────┐
│   Visitor   │ ──────────────────▶  │   Persona   │
└─────────────┘                       └─────────────┘
                                            │
                                            │ owned by
                                            ▼
                                      ┌─────────────┐
                                      │    Owner    │ ◀── quota consumed
                                      └─────────────┘
```

Unlike voice usage (which tracks sessions with duration), text usage uses a simple **counter approach**:
- Each message increments the owner's `text_messages_used` counter
- Counter resets automatically on the 1st of each month
- No per-session or per-persona breakdown needed

### Database Schema

**Migration:** `e4f5a6b7c8d9_add_text_usage_limits.py`

**`tier_plans` table:**
```sql
ALTER TABLE tier_plans ADD COLUMN max_text_messages_per_month INTEGER DEFAULT 500;

-- Set tier limits
UPDATE tier_plans SET max_text_messages_per_month = CASE
    WHEN id = 0 THEN 500     -- Free
    WHEN id = 1 THEN 10000   -- Pro
    WHEN id = 2 THEN 40000   -- Business
    WHEN id = 3 THEN -1      -- Enterprise (unlimited)
END;
```

**`user_usage_cache` table:**
```sql
ALTER TABLE user_usage_cache ADD COLUMN text_messages_used INTEGER DEFAULT 0;
ALTER TABLE user_usage_cache ADD COLUMN text_usage_reset_at TIMESTAMP WITH TIME ZONE;
```

## Service Implementation

### TextUsageService

Located at: `shared/services/text_usage_service.py`

```python
class TextUsageService:
    """Service for managing text chat usage limits based on persona owner's tier"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_owner_tier_limit(self, owner_id: UUID) -> Tuple[int, str]:
        """
        Get the text message limit for a persona owner based on their tier.
        Returns: (limit_messages, tier_name)
        limit_messages = -1 means unlimited
        """

    async def get_owner_usage(self, owner_id: UUID) -> Tuple[int, datetime]:
        """
        Get the current text usage for a persona owner.
        Returns: (used_messages, reset_at)
        """

    async def check_owner_text_limit(self, persona_id: UUID) -> Tuple[bool, int, int]:
        """
        Check if the persona owner has remaining text message quota.
        Args:
            persona_id: The persona being chatted with
        Returns:
            (can_send, remaining_messages, limit_messages)
            remaining_messages = -1 means unlimited
        """

    async def check_owner_text_limit_by_owner_id(self, owner_id: UUID) -> Tuple[bool, int, int]:
        """
        Check quota by owner ID directly (for dashboard/API use).
        """

    async def record_message(self, persona_id: UUID) -> None:
        """
        Record that a message was sent to a persona (increments owner's usage).
        """

    async def record_message_for_owner(self, owner_id: UUID) -> None:
        """
        Record a message directly for an owner (increments usage).
        Uses SELECT ... FOR UPDATE to prevent race conditions.
        """

    async def get_owner_text_usage(self, user_id: UUID) -> Dict:
        """
        Get text usage stats for a persona owner (for dashboard/API).
        Returns:
            {
                "messages_used": int,
                "messages_limit": int,  # -1 = unlimited
                "percentage": float,
                "reset_date": str | None,
                "tier_name": str
            }
        """
```

### Exception Class

```python
class TextLimitExceeded(Exception):
    """Raised when text usage limit is exceeded"""

    def __init__(self, message: str, used_messages: int = 0, limit_messages: int = 0):
        super().__init__(message)
        self.used_messages = used_messages
        self.limit_messages = limit_messages
```

## API Integration

### Stream Chat Endpoint

In `app/api/session_routes.py`:

```python
@router.post("/personas/username/{username}/stream-chat")
async def stream_chat(
    username: str,
    request: TrackedChatRequest,
    session: AsyncSession = Depends(get_session),
    auth_result: dict = Depends(require_jwt_or_api_key),
):
    # ... session lookup ...

    # Check text usage limit before allowing message
    text_usage_service = TextUsageService(session)
    can_send, remaining, limit = await text_usage_service.check_owner_text_limit(
        persona_id=user_session.persona_id
    )

    if not can_send:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "text_limit_exceeded",
                "message": f"Monthly text chat limit reached ({limit} messages)",
                "messages_used": limit - remaining if limit > 0 else 0,
                "messages_limit": limit,
            },
        )

    # ... process message ...

    # Record the message after successful save
    await text_usage_service.record_message(persona_id=user_session.persona_id)
```

### Error Response Format

When limit is exceeded, the API returns:

```json
HTTP 429 Too Many Requests

{
  "detail": {
    "error": "text_limit_exceeded",
    "message": "Monthly text chat limit reached (500 messages)",
    "messages_used": 500,
    "messages_limit": 500
  }
}
```

### Usage Stats Endpoint

The tier service includes text usage in the stats response:

```python
# In shared/services/tier_service.py

async def get_usage_stats(self, user_id: UUID) -> Dict:
    # ... other usage stats ...

    # Get text usage
    text_usage_service = TextUsageService(self.db)
    text_stats = await text_usage_service.get_owner_text_usage(user_id)

    return {
        "tier": tier_name,
        # ... other stats ...
        "text": {
            "messages_used": text_stats["messages_used"],
            "messages_limit": text_stats["messages_limit"],
            "percentage": text_stats["percentage"],
            "reset_date": text_stats["reset_date"],
        },
    }
```

## Monthly Reset Logic

Usage resets automatically on the 1st of each month:

```python
async def get_owner_usage(self, owner_id: UUID) -> Tuple[int, datetime]:
    # Get usage cache
    query = select(UserUsageCache).where(UserUsageCache.user_id == owner_id)
    result = await self.db.execute(query)
    usage_cache = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    if not usage_cache:
        # Create with reset date set to next month's 1st
        reset_at = (now + relativedelta(months=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        usage_cache = UserUsageCache(
            user_id=owner_id,
            text_messages_used=0,
            text_usage_reset_at=reset_at,
        )
        self.db.add(usage_cache)
        await self.db.flush()
        return 0, reset_at

    # Check if we need to reset (past reset date)
    if usage_cache.text_usage_reset_at and now >= usage_cache.text_usage_reset_at:
        # Reset usage and set new reset date
        usage_cache.text_messages_used = 0
        usage_cache.text_usage_reset_at = (now + relativedelta(months=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        usage_cache.last_updated_at = now
        await self.db.flush()
        return 0, usage_cache.text_usage_reset_at

    return usage_cache.text_messages_used, usage_cache.text_usage_reset_at
```

## Concurrency Handling

The `record_message_for_owner` method uses `SELECT ... FOR UPDATE` to prevent race conditions:

```python
async def record_message_for_owner(self, owner_id: UUID) -> None:
    now = datetime.now(timezone.utc)

    # Get or create usage cache with lock
    query = select(UserUsageCache).where(UserUsageCache.user_id == owner_id).with_for_update()
    result = await self.db.execute(query)
    usage_cache = result.scalar_one_or_none()

    if usage_cache:
        # Check if we need to reset first
        if usage_cache.text_usage_reset_at and now >= usage_cache.text_usage_reset_at:
            usage_cache.text_messages_used = 1  # Reset and count this message
            usage_cache.text_usage_reset_at = (now + relativedelta(months=1)).replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
        else:
            usage_cache.text_messages_used += 1

        usage_cache.last_updated_at = now
    else:
        # Create cache if doesn't exist
        reset_at = (now + relativedelta(months=1)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        usage_cache = UserUsageCache(
            user_id=owner_id,
            text_messages_used=1,
            text_usage_reset_at=reset_at,
        )
        self.db.add(usage_cache)

    await self.db.flush()
```

## Monitoring & Sentry Integration

### Limit Exceeded Events

```python
from shared.monitoring.sentry_utils import capture_message

if not can_send:
    logger.warning(
        f"Text limit exceeded for owner {owner_id}. "
        f"Used: {used_messages}, Limit: {limit_messages}"
    )
    # Track in Sentry
    capture_message(
        f"Text limit exceeded for owner {owner_id}",
        level="warning",
        tags={
            "event_type": "text_limit_exceeded",
            "persona_id": str(persona_id),
            "owner_id": str(owner_id),
        },
        extra={
            "used_messages": used_messages,
            "limit_messages": limit_messages,
            "percentage": (
                round(used_messages / limit_messages * 100, 1) if limit_messages > 0 else 0
            ),
        },
    )
```

### Breadcrumbs

```python
from shared.monitoring.sentry_utils import add_breadcrumb

# Track message recorded
add_breadcrumb(
    message=f"Text message recorded for owner {owner_id}",
    category="text_usage",
    level="info",
    data={
        "owner_id": str(owner_id),
        "total_messages": usage_cache.text_messages_used,
    },
)
```

## Model Updates

### TierPlan Model

```python
# In shared/database/models/tier_plan.py

class TierPlan(Base):
    __tablename__ = "tier_plans"

    # ... existing fields ...

    # Text chat limits (monthly)
    max_text_messages_per_month = Column(Integer, default=500)  # -1 = unlimited
```

### UserUsageCache Model

```python
# In shared/database/models/tier_plan.py

class UserUsageCache(Base):
    __tablename__ = "user_usage_cache"

    # ... existing fields ...

    # Text chat usage
    text_messages_used = Column(Integer, default=0)
    text_usage_reset_at = Column(DateTime(timezone=True), nullable=True)
```

## Comparison: Text vs Voice Usage

| Aspect | Text Usage | Voice Usage |
|--------|------------|-------------|
| Unit | Messages | Minutes |
| Tracking | Counter in `user_usage_cache` | Sessions in `voice_sessions` table |
| Billing | Per message sent | Per minute of voice time |
| Granularity | Aggregate only | Per-session breakdown available |
| Reset | Monthly (1st) | Monthly (1st) |
| Concurrency | `SELECT ... FOR UPDATE` | Session-based with heartbeats |

## File Reference

| File | Description |
|------|-------------|
| `shared/services/text_usage_service.py` | Main service class |
| `shared/database/models/tier_plan.py` | Model definitions |
| `app/api/session_routes.py` | API endpoint integration |
| `shared/services/tier_service.py` | Usage stats aggregation |
| `shared/monitoring/sentry_utils.py` | Monitoring utilities |
| `alembic/versions/e4f5a6b7c8d9_add_text_usage_limits.py` | Database migration |

## Testing

### Manual Testing

1. Send messages until limit is reached
2. Verify 429 response with correct error format
3. Check usage counter increments in database
4. Verify monthly reset works

### Database Queries

```sql
-- Check current usage for a user
SELECT text_messages_used, text_usage_reset_at
FROM user_usage_cache
WHERE user_id = 'owner-uuid';

-- Check tier limit
SELECT id, tier_name, max_text_messages_per_month
FROM tier_plans;

-- Manually reset usage for testing
UPDATE user_usage_cache
SET text_messages_used = 0,
    text_usage_reset_at = NOW() + INTERVAL '1 month'
WHERE user_id = 'owner-uuid';

-- Manually trigger reset by setting past date
UPDATE user_usage_cache
SET text_usage_reset_at = '2024-01-01'
WHERE user_id = 'owner-uuid';
```

### API Testing

```bash
# Get usage stats
curl -X GET "http://localhost:8000/api/v1/tier/usage" \
  -H "Authorization: Bearer $TOKEN"

# Send message (will fail if limit exceeded)
curl -X POST "http://localhost:8000/api/v1/personas/username/rohan/stream-chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "session_token": "..."}'
```

## Migration

To apply the migration:

```bash
# Check current head
alembic heads

# Apply migration
alembic upgrade head

# Verify columns exist
psql -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'tier_plans' AND column_name = 'max_text_messages_per_month';"
psql -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'user_usage_cache' AND column_name = 'text_messages_used';"
```

## Rollback

If needed, rollback the migration:

```bash
# Rollback to previous version
alembic downgrade d3e148d9e454

# This will:
# - Remove max_text_messages_per_month from tier_plans
# - Remove text_messages_used and text_usage_reset_at from user_usage_cache
```
