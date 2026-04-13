# Persona Creation Limits Implementation

This document describes the implementation of tier-based persona creation limits.

## Overview

Users are limited in the number of personas they can create based on their subscription tier. This prevents abuse and encourages upgrades for power users.

## Tier Limits Configuration

| Tier ID | Tier Name | max_personas | Price | Description |
|---------|-----------|--------------|-------|-------------|
| 0 | `free` | 1 | $0/mo | Free tier users |
| 1 | `pro` | 3 | $19/mo | Pro subscribers |
| 2 | `business` | 30 | $79/mo | Business subscribers |
| 3 | `enterprise` | -1 (unlimited) | Custom | Enterprise subscribers |

> Note: `-1` means unlimited personas

## Data Flow

```
User clicks "New Persona"
         │
         ▼
┌─────────────────────────────────────┐
│ Frontend: Check canCreatePersona()  │
│ Uses cached /tier/usage data        │
└─────────────────────────────────────┘
         │
         ▼ If allowed
┌─────────────────────────────────────┐
│ Frontend: Show CreatePersonaDialog  │
│ User fills form and submits         │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ API: POST /personas/with-knowledge  │
│ 1. Authorization check              │
│ 2. Persona limit check (NEW)        │
│ 3. Create persona                   │
│ 4. Attach knowledge sources         │
└─────────────────────────────────────┘
         │
         ▼ If limit exceeded
┌─────────────────────────────────────┐
│ HTTP 403 Response:                  │
│ {                                   │
│   "detail": "Persona limit reached" │
│   "error_code": "PERSONA_LIMIT_...",│
│   "current": 5,                     │
│   "limit": 5                        │
│ }                                   │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ Frontend: Show upgrade toast/modal  │
└─────────────────────────────────────┘
```

## Database Schema Changes

### tier_plans table

New column added:

```sql
ALTER TABLE tier_plans 
ADD COLUMN max_personas INTEGER NOT NULL DEFAULT 1 
COMMENT 'Max personas per user (-1 = unlimited)';
```

### Initial Values

```sql
UPDATE tier_plans SET max_personas = 1 WHERE id = 0;   -- free
UPDATE tier_plans SET max_personas = 3 WHERE id = 1;   -- pro
UPDATE tier_plans SET max_personas = 30 WHERE id = 2;  -- business
UPDATE tier_plans SET max_personas = -1 WHERE id = 3;  -- enterprise
```

## Backend Implementation

### Files Modified

1. **`shared/database/models/tier_plan.py`**
   - Add `max_personas` column to `TierPlan` model

2. **`shared/schemas/tier.py`**
   - Add `max_personas` field to `TierPlanResponse`

3. **`shared/services/tier_service.py`**
   - Add `check_persona_creation_allowed(user_id)` method
   - Add `_get_persona_count(user_id)` helper method
   - Update `get_user_tier_limits()` to include `max_personas`
   - Update `get_usage_stats()` to include persona usage section

4. **`app/api/persona_knowledge_routes.py`**
   - Add limit check before persona creation in `create_persona_with_knowledge()`

### TierService Methods

#### check_persona_creation_allowed(user_id)

```python
async def check_persona_creation_allowed(self, user_id: UUID) -> Tuple[bool, int]:
    """
    Check if user can create a new persona based on their tier limits.
    
    Args:
        user_id: User's UUID
        
    Returns:
        Tuple of (is_allowed, remaining_slots)
        
    Raises:
        TierLimitExceeded: If user has reached their persona limit
    """
    limits = await self.get_user_tier_limits(user_id)
    max_personas = limits.get("max_personas", 1)
    
    # -1 means unlimited
    if max_personas == -1:
        return True, -1
    
    current_count = await self._get_persona_count(user_id)
    
    if current_count >= max_personas:
        raise TierLimitExceeded(
            f"Persona limit reached ({max_personas} personas). "
            f"Upgrade your plan to create more personas.",
            limit_type="persona_count"
        )
    
    return True, max_personas - current_count
```

### API Response Format

#### Success (persona created)
```json
{
  "id": "uuid",
  "persona_name": "tech-advisor",
  "name": "Tech Advisor",
  ...
}
```

#### Error (limit reached)
```json
{
  "detail": "Persona limit reached (5 personas). Upgrade your plan to create more personas.",
  "error_code": "PERSONA_LIMIT_EXCEEDED",
  "current": 5,
  "limit": 5
}
```

HTTP Status: `403 Forbidden`

## Sentry Integration

All persona limit exceeded errors are logged to Sentry with proper context for monitoring and debugging:

```python
capture_exception_with_context(
    e,
    extra={
        "user_id": str(user_id),
        "requested_persona_name": request.persona_name,
        "current_persona_count": persona_count,
        "max_personas": max_personas,
        "tier_name": tier_name,
    },
    tags={
        "component": "persona_creation",
        "operation": "check_persona_limit",
        "severity": "low",
        "user_facing": "true",
    },
)
```

This allows filtering in Sentry dashboard by:
- Component: `persona_creation`
- Operation: `check_persona_limit`
- Severity: `low` (expected user behavior, not a bug)

## Frontend Implementation

### Files Modified

1. **`src/lib/queries/tier/interface.ts`**
   - Added `PersonaUsage` interface
   - Added `personas` field to `TierUsageResponse`
   - Added `max_personas` to `TierPlan`
   - Added `maxPersonas` to `TierLimits`

2. **`src/lib/queries/tier/useTierLimitCheck.ts`**
   - Added `canCreatePersona()` method returning `{ allowed, reason, current, limit }`
   - Updated `hasReachedLimit()` to support "personas" category
   - Updated return type interface

3. **`src/app/dashboard/personas/page.tsx`**
   - Import `useTierLimitCheck` hook
   - Show persona usage badge in header (e.g., "2/3 personas")
   - Show warning banner when limit is reached with "View Plans" link
   - Handle `PERSONA_LIMIT_EXCEEDED` error with specific toast message
   - Pass limit props to `CreatePersonaDialog`

4. **`src/components/dashboard/personas/CreatePersonaDialog.tsx`**
   - Added props: `canCreate`, `limitReason`, `currentCount`, `maxPersonas`
   - Show disabled button with badge when limit is reached
   - Show current/limit badge on create button

### Type Definitions

```typescript
interface TierUsageResponse {
  tier: string;
  // ... existing fields ...
  
  personas: {
    used: number;
    limit: number;    // -1 = unlimited
    percentage: number;
  };
}
```

### Hook Usage

```typescript
const { canCreatePersona, usage } = useTierLimitCheck();

// Check if creation allowed
const { allowed, reason } = canCreatePersona();
if (!allowed) {
  // Show upgrade prompt
}

// Display usage
<span>{usage?.personas.used} of {usage?.personas.limit} personas</span>
```

## Existing User Handling

Users who already have more personas than their tier allows (grandfathered):
- **Cannot create new personas** until they're under the limit
- **Existing personas remain active** and functional
- No forced deletion or downgrade

Example: If a free user somehow has 3 personas and free tier allows 1:
- They keep all 3 personas
- They cannot create persona #4
- If they delete 2, they still cannot create more (stays at 1)
- If they upgrade to Pro (5 limit), they can create 2 more

## Testing

### Manual Testing Steps

1. Create a user on free tier
2. Verify they can create 1 persona
3. Try to create a 2nd persona - should fail with 403
4. Upgrade user to Pro tier
5. Verify they can now create up to 5 personas

### API Testing

```bash
# Check current usage
GET /api/v1/tier/usage

# Try to create persona (should work if under limit)
POST /api/v1/personas/with-knowledge?user_id={uuid}

# Response when at limit
HTTP 403
{
  "detail": "Persona limit reached...",
  "error_code": "PERSONA_LIMIT_EXCEEDED"
}
```

## Migration Path

1. Run Alembic migration to add column and set initial values
2. Deploy backend changes
3. Deploy frontend changes
4. Verify in production

## Rollback Plan

If issues arise:
1. Revert frontend deployment
2. Revert backend deployment  
3. Run Alembic downgrade to remove column

The downgrade migration removes the `max_personas` column, reverting to unlimited persona creation.
