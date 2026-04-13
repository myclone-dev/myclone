# Whitelabel Email Domains

This document describes the custom email domain feature that allows Enterprise tier users to send OTP verification emails from their own domain instead of `myclone.is`.

## Overview

When visitors interact with a persona that has email capture enabled, they receive OTP verification emails. By default, these emails come from the platform's default sender address. With custom email domains, persona owners can send these emails from their own branded domain (e.g., `hello@acme.com`).

## Feature Access

This feature is available to:
- **Enterprise tier** (tier_id = 3)

## Architecture

### Database Model

**Table: `custom_email_domains`**

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | Owner (FK to users) |
| domain | VARCHAR(255) | Email domain (e.g., 'acme.com') |
| from_email | VARCHAR(255) | Sender email (e.g., 'hello@acme.com') |
| from_name | VARCHAR(255) | Display name (e.g., 'Acme Support') |
| reply_to_email | VARCHAR(255) | Optional reply-to address |
| resend_domain_id | VARCHAR(255) | Domain ID from Resend API |
| status | ENUM | pending, verifying, verified, failed |
| dns_records | JSONB | DNS records for verification |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update time |
| verified_at | TIMESTAMP | When domain was verified |

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend                                 │
│  EmailDomainsSection.tsx → Profile Page (/dashboard/profile)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Routes                                  │
│  /users/me/email-domains (GET, POST)                            │
│  /users/me/email-domains/{id} (GET, PATCH, DELETE)              │
│  /users/me/email-domains/{id}/verify (POST)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 CustomEmailDomainService                         │
│  - create_domain() → Registers domain with Resend               │
│  - verify_domain() → Triggers DNS verification                  │
│  - get_sender_config() → Returns sender for a user              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Resend API                                  │
│  - Domains.create() → Returns DNS records                       │
│  - Domains.verify() → Checks DNS configuration                  │
│  - Domains.get() → Gets domain status                           │
└─────────────────────────────────────────────────────────────────┘
```

## API Endpoints

### List Email Domains
```
GET /api/v1/users/me/email-domains
Authorization: Bearer <token>

Response:
{
  "domains": [
    {
      "id": "uuid",
      "domain": "acme.com",
      "from_email": "hello@acme.com",
      "from_name": "Acme Support",
      "status": "verified",
      "dns_records": [...],
      "created_at": "2024-01-26T12:00:00Z",
      "verified_at": "2024-01-26T13:00:00Z"
    }
  ],
  "total": 1
}
```

### Add Email Domain
```
POST /api/v1/users/me/email-domains
Authorization: Bearer <token>
Content-Type: application/json

{
  "domain": "acme.com",
  "from_email": "hello@acme.com",
  "from_name": "Acme Support",  // optional
  "reply_to_email": "support@acme.com"  // optional
}

Response:
{
  "id": "uuid",
  "domain": "acme.com",
  "from_email": "hello@acme.com",
  "status": "pending",
  "dns_records": [
    {
      "type": "TXT",
      "name": "_dmarc.acme.com",
      "value": "v=DMARC1; p=none;",
      "status": "pending"
    },
    {
      "type": "TXT",
      "name": "resend._domainkey.acme.com",
      "value": "p=MIGfMA0GCS...",
      "status": "pending"
    }
  ]
}
```

### Verify Domain
```
POST /api/v1/users/me/email-domains/{domain_id}/verify
Authorization: Bearer <token>

Response:
{
  "id": "uuid",
  "domain": "acme.com",
  "status": "verified",  // or "verifying", "failed"
  "dns_records": [...]
}
```

### Delete Domain
```
DELETE /api/v1/users/me/email-domains/{domain_id}
Authorization: Bearer <token>

Response: 204 No Content
```

## DNS Configuration

Users must add the following DNS records to their domain:

1. **DKIM Record** (TXT)
   - Name: `resend._domainkey.yourdomain.com`
   - Value: Provided by Resend API

2. **SPF Record** (TXT)
   - Name: `yourdomain.com`
   - Value: `v=spf1 include:amazonses.com ~all`

3. **DMARC Record** (TXT) - Optional but recommended
   - Name: `_dmarc.yourdomain.com`
   - Value: `v=DMARC1; p=none;`

DNS propagation can take up to 48 hours.

## OTP Email Integration

When a visitor requests email verification:

1. `persona_access_routes.py` calls OTP service with `persona_owner_id`
2. `OTPService._get_sender_for_user()` looks up verified custom domain
3. If found, uses `custom_domain.sender_address` (e.g., "Acme Support <hello@acme.com>")
4. If not found, falls back to default sender address

```python
# In otp_service.py
if persona_owner_id:
    from_email = await self._get_sender_for_user(persona_owner_id)
else:
    from_email = self.from_email  # default sender
```

## File Structure

```
app/
├── api/
│   └── custom_email_domain_routes.py  # API endpoints
├── services/
│   └── custom_email_domain_service.py # Business logic + Resend integration
│   └── otp_service.py                 # Updated to use custom sender

shared/database/
├── models/
│   └── custom_email_domain.py         # SQLAlchemy model
├── repositories/
│   └── custom_email_domain_repository.py # Database operations

alembic/versions/
└── b426ae7098dd_create_custom_email_domains_table.py
```

## Environment Variables

No new environment variables required. Uses existing:
- `RESEND_API_KEY` - Resend API key for domain management
- `RESEND_FROM_EMAIL` - Default sender email (fallback)

## Validation Rules

1. **Domain format**: Must be a valid domain (e.g., `acme.com`)
2. **Blocked domains**: Cannot use free email providers (gmail.com, yahoo.com, etc.)
3. **Email must match domain**: `hello@acme.com` must end with `@acme.com`
4. **Limit**: 1 custom email domain per user

## Status Flow

```
pending → verifying → verified
                  └→ failed
```

- **pending**: Domain created, DNS records provided
- **verifying**: Verification triggered, checking DNS
- **verified**: DNS records confirmed, ready to send emails
- **failed**: DNS verification failed

## Error Handling

| Error | HTTP Status | Message |
|-------|-------------|---------|
| Not enterprise tier | 403 | "Custom email domains require an Enterprise plan" |
| Domain already exists | 400 | "Domain {domain} is already registered" |
| Invalid domain format | 400 | "Invalid domain format: {domain}" |
| Free email provider | 400 | "Cannot use free email provider domain: {domain}" |
| Domain limit reached | 400 | "You have reached the maximum number of custom email domains" |
| Domain not found | 404 | "Domain {id} not found" |

## Testing

To test the feature:

1. Ensure user has Enterprise tier subscription
2. Add a domain via POST /users/me/email-domains
3. Configure DNS records in your domain provider
4. Wait for DNS propagation (can take up to 48 hours)
5. Trigger verification via POST /users/me/email-domains/{id}/verify
6. Once verified, OTP emails will come from your custom domain
