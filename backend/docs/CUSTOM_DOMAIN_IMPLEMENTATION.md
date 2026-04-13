# Custom Domain Implementation (Backend)

This document describes the custom domain (white-label) feature backend implementation for MyClone.

## Overview

The custom domain feature allows users to serve their AI clone at their own domain (e.g., `chat.example.com` or `example.com`) instead of the default `myclone.is` domain.

**USER-LEVEL Routing:**

- `customdomain.com` → equivalent to `myclone.is/username` (shows all personas)
- `customdomain.com/persona_name` → equivalent to `myclone.is/username/persona_name`

## Database Schema

### custom_domains Table

```sql
CREATE TABLE custom_domains (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    domain TEXT NOT NULL UNIQUE,
    verification_records JSONB,
    routing_record JSONB,
    status domain_status NOT NULL DEFAULT 'pending',
    verified_at TIMESTAMPTZ,
    ssl_provisioned_at TIMESTAMPTZ,
    last_error TEXT,
    last_check_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### domain_status Enum

```sql
CREATE TYPE domain_status AS ENUM (
    'pending',    -- Domain added, awaiting DNS configuration
    'verifying',  -- DNS check in progress
    'verified',   -- DNS verified, SSL being provisioned
    'active',     -- Fully configured and serving traffic
    'failed',     -- Verification failed
    'expired'     -- Verification expired
);
```

## Files

### Model

**File:** `shared/database/models/custom_domain.py`

Defines the `CustomDomain` SQLAlchemy model with:

- `DomainStatus` enum for domain lifecycle states
- Relationships to User model (user-level, not persona-level)
- Helper properties: `is_active`, `is_verified`, `is_apex`
- `get_dns_instructions()` method for user-friendly DNS setup instructions

### Repository

**File:** `shared/database/repositories/custom_domain_repository.py`

CRUD operations:

- `create()` - Add new domain (user_id, domain, verification_records, routing_record)
- `get_by_id()` - Get by UUID
- `get_by_domain()` - Get by domain name
- `get_by_user_id()` - List user's domains
- `get_active_by_domain()` - Get active domain for routing (used by frontend middleware)
- `update_status()` - Update domain status
- `delete()` - Remove domain
- `domain_exists()` - Check if domain is already registered
- `get_domains_pending_verification()` - For background verification jobs

### Vercel Service

**File:** `shared/services/vercel_domain_service.py`

Integrates with Vercel's Domain API:

- `add_domain(domain)` - Register domain with Vercel project
- `verify_domain(domain)` - Check DNS verification status
- `remove_domain(domain)` - Remove from Vercel project
- `get_domain_config(domain)` - Get current domain configuration

### API Routes

**File:** `app/api/custom_domain_routes.py`

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/custom-domains` | GET | Required | List user's domains |
| `/api/v1/custom-domains` | POST | Required | Add new domain |
| `/api/v1/custom-domains/{id}` | GET | Required | Get domain details |
| `/api/v1/custom-domains/{id}/verify` | POST | Required | Verify DNS configuration |
| `/api/v1/custom-domains/{id}` | DELETE | Required | Remove domain |
| `/api/v1/custom-domains/lookup/{domain}` | GET | None | Public lookup for routing |

### Migration

**File:** `alembic/versions/d4e5f6g7h8i9_add_custom_domains_table.py`

Creates:

- `domain_status` enum type
- `custom_domains` table
- Indexes on `user_id`, `domain`, `status`
- Partial index on `user_id` where `status = 'active'`

## Environment Variables

Add to `.env`:

```bash
# Vercel Domain Integration (for custom domain white-labeling)
# Get token from: https://vercel.com/account/tokens
VERCEL_API_TOKEN=your_vercel_api_token_here
VERCEL_PROJECT_ID=your_vercel_project_id_here
VERCEL_TEAM_ID=your_vercel_team_id_here  # Optional, only for team projects
```

### Getting Vercel Credentials

1. **API Token:** https://vercel.com/account/tokens → Create new token
2. **Project ID:** Vercel Dashboard → Project → Settings → General → Project ID
3. **Team ID:** Team Settings → General → Team ID (only if using teams)

## API Response Formats

### CustomDomainResponse

```json
{
  "id": "uuid",
  "domain": "chat.example.com",
  "status": "pending|verifying|verified|active|failed|expired",
  "user_id": "uuid",
  "username": "johndoe",
  "verified": false,
  "ssl_ready": false,
  "verification_record": {
    "type": "TXT",
    "name": "_vercel",
    "value": "vc-domain-verify=...",
    "description": "Add this TXT record to verify domain ownership"
  },
  "routing_record": {
    "type": "A",
    "name": "@",
    "value": "76.76.21.21",
    "description": "Add this record to route traffic to your clone"
  },
  "last_error": null,
  "created_at": "2025-01-01T00:00:00Z",
  "verified_at": null
}
```

### Domain Lookup Response (for middleware)

**Success (HTTP 200):**
```json
{
  "domain": "chat.example.com",
  "user_id": "uuid",
  "username": "johndoe"
}
```

**Not Found (HTTP 404):**
```json
{
  "detail": "Domain not found or not active"
}
```

**Note:** The lookup endpoint returns HTTP 404 (not 200 with null) when:
- Domain is not registered in the system
- Domain status is not `active`
- Domain owner (user) not found

## User Flow

1. User adds domain in dashboard → POST `/api/v1/custom-domains`
2. Backend registers with Vercel → Returns DNS records
3. User adds DNS records at their registrar
4. User clicks "Verify" → POST `/api/v1/custom-domains/{id}/verify`
5. Backend checks with Vercel → Status: verified → active
6. Vercel auto-provisions SSL
7. Domain becomes active → Traffic routes to user's profile

## DNS Records

### Apex Domains (example.com)

```
Type: TXT
Name: _vercel
Value: vc-domain-verify=example.com,abc123...

Type: A
Name: @
Value: 76.76.21.21
```

### Subdomains (chat.example.com)

```
Type: TXT
Name: _vercel.chat
Value: vc-domain-verify=chat.example.com,abc123...

Type: CNAME
Name: chat
Value: cname.vercel-dns.com
```

## Error Handling

| Error Code | Scenario | Message |
|------------|----------|---------|
| 400 | Invalid domain format | "Invalid domain format. Example: chat.example.com" |
| 409 | Domain already registered | "This domain is already registered" |
| 409 | Domain in use on Vercel | "This domain is already in use by another project" |
| 503 | Vercel not configured | "Custom domain feature is not configured" |

## Running Migration

```bash
cd /home/rx/Desktop/rappo/digital-clone-poc
poetry run alembic upgrade head
```

To rollback:

```bash
poetry run alembic downgrade -1
```

## Related Files

- Frontend docs: `myclone-frontend/docs/CUSTOM_DOMAIN_IMPLEMENTATION.md`
- Frontend hooks: `myclone-frontend/src/lib/queries/users/useCustomDomains.ts`
- Frontend component: `myclone-frontend/src/components/dashboard/widgets/CustomDomainSection.tsx`
- Middleware routing: `myclone-frontend/middleware.ts`
