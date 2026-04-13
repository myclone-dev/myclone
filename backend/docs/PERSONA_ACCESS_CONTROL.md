# Persona Access Control Documentation

> **Feature Sponsor:** Luxury Institute
> **Implementation Date:** October 2024
> **Status:** ✅ Production Ready

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
  - [Public Visitor Flow](#public-visitor-flow)
  - [Dashboard Management](#dashboard-management)
- [Security Features](#security-features)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Persona Access Control feature enables users to create **private personas** that require email verification before access. This allows experts to control who can interact with specific personas while maintaining a seamless visitor experience.

### Key Features

✅ **Email-Based Access Control** - Visitors verify via OTP (One-Time Password)
✅ **Multi-Persona Support** - Each persona can have independent access rules
✅ **Global Visitor Management** - Centralized visitor whitelist per user
✅ **Flexible Assignment** - Visitors can be assigned to multiple personas
✅ **Persistent Sessions** - 14-day authentication cookies for verified visitors
✅ **Rate Limiting** - Protection against OTP spam (5 per hour)
✅ **Dashboard Management** - Full CRUD operations for visitor management

### Use Cases

1. **Premium Content Access** - Restrict access to exclusive personas
2. **Client Portal** - Private personas for specific clients
3. **Beta Testing** - Limited access for early testers
4. **Compliance** - Meet privacy/access requirements
5. **Lead Generation** - Collect verified emails before access

---

## Architecture

### Three-Tier Access Model

```
┌─────────────────────────────────────────────────────────────┐
│                      User (Expert)                          │
│  - Owns multiple personas                                   │
│  - Manages global visitor whitelist                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ owns
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Visitor Whitelist (Global)                 │
│  - Email, name, notes                                       │
│  - Created once, reused across personas                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ many-to-many
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Persona (Public/Private)                  │
│  - is_private flag                                          │
│  - Assigned visitors via junction table                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ accessed by
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Visitor (Public)                       │
│  - Requests OTP via email                                   │
│  - Verifies OTP, receives 14-day cookie                     │
└─────────────────────────────────────────────────────────────┘
```

### Component Breakdown

#### 1. **Database Layer** (Phase 1)
- **Tables**: `visitor_whitelist`, `persona_visitors`, `persona_access_otps`, `personas.is_private`
- **Models**: `shared/database/models/persona_access.py`
- **Repositories**:
  - `shared/database/repositories/persona_access_repository.py`
  - `shared/database/repositories/visitor_whitelist_repository.py`

#### 2. **Visitor Authentication Flow** (Phases 2-4)
- **OTP Service**: `app/services/otp_service.py` (Resend email integration)
- **Access Middleware**: `app/auth/persona_access.py` (cookie validation)
- **Public Routes**: `app/api/persona_access_routes.py` (OTP request/verify)

#### 3. **Dashboard Management** (Phase 5)
- **Management Routes**: `app/api/visitor_management_routes.py`
- **CRUD Operations**: Visitor whitelist + Persona assignments
- **Access Toggle**: Public/private persona switching

---

## Database Schema

### 1. `visitor_whitelist` (Global, User-Level)

Stores visitor information at the user level. Each visitor is created once and can be assigned to multiple personas.

```sql
CREATE TABLE visitor_whitelist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    notes TEXT,  -- User notes about this visitor
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_accessed_at TIMESTAMPTZ,  -- Most recent access to any persona

    CONSTRAINT uq_visitor_whitelist_user_email UNIQUE (user_id, email)
);

CREATE INDEX idx_visitor_whitelist_user ON visitor_whitelist(user_id);
CREATE INDEX idx_visitor_whitelist_email ON visitor_whitelist(user_id, email);
```

**Purpose:**
- Central repository of all verified visitors per user
- Enables visitor reuse across multiple personas
- Tracks visitor metadata (name, notes, last access)

### 2. `persona_visitors` (Junction Table, Many-to-Many)

Maps which visitors can access which personas.

```sql
CREATE TABLE persona_visitors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    visitor_id UUID NOT NULL REFERENCES visitor_whitelist(id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_persona_visitors_persona_visitor UNIQUE (persona_id, visitor_id)
);

CREATE INDEX idx_persona_visitors_persona ON persona_visitors(persona_id);
CREATE INDEX idx_persona_visitors_visitor ON persona_visitors(visitor_id);
```

**Purpose:**
- Flexible many-to-many relationship
- Same visitor can access multiple personas
- Same persona can have multiple visitors
- Enables bulk assignment operations

### 3. `persona_access_otps` (Temporary, 5-Minute Expiry)

Stores OTP codes for email verification.

```sql
CREATE TABLE persona_access_otps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id UUID NOT NULL REFERENCES personas(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    otp_code VARCHAR(6) NOT NULL,  -- 6-digit code
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,  -- 5 minutes from creation
    verified_at TIMESTAMPTZ,  -- NULL until verified
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,

    CONSTRAINT ck_persona_access_otps_max_attempts CHECK (attempts <= max_attempts)
);

CREATE INDEX idx_persona_access_otps_lookup ON persona_access_otps(persona_id, email, otp_code);
CREATE INDEX idx_persona_access_otps_expires ON persona_access_otps(expires_at);  -- For cleanup
```

**Purpose:**
- Temporary OTP storage (auto-deleted after 24 hours)
- Prevents brute-force attacks (max 3 attempts)
- Supports rate limiting (max 5 OTPs per hour)
- Indexed for fast lookup and cleanup

### 4. `personas.is_private` (Access Control Flag)

Added columns to existing `personas` table:

```sql
ALTER TABLE personas ADD COLUMN is_private BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE personas ADD COLUMN access_control_enabled_at TIMESTAMPTZ;
```

**Purpose:**
- `is_private`: Toggle between public/private access
- `access_control_enabled_at`: Audit trail for when access control was enabled

---

## API Endpoints

### Public Visitor Flow

#### 1. Request Access (Send OTP)

**Endpoint:** `POST /api/v1/personas/username/{username}/request-access`

**Query Parameters:**
- `persona_name` (optional): Persona name, defaults to `"default"`

**Request Body:**
```json
{
  "email": "visitor@example.com",
  "firstName": "John",  // Optional
  "lastName": "Doe"     // Optional
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Verification code sent to visitor@example.com. Please check your inbox."
}
```

**Response (429 Too Many Requests):**
```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

**Behavior:**
- Looks up persona by `username` and `persona_name`
- If persona is public (`is_private=false`), returns success immediately (no OTP needed)
- If persona is private, sends OTP email via Resend
- Stores visitor's `first_name` for later use
- Rate limit: Max 5 OTPs per hour per email/persona combination

**Email Template:**
- Subject: "Your verification code for {PersonaName}"
- Contains 6-digit OTP code
- Expires in 5 minutes
- Plain text + HTML versions

---

#### 2. Verify Access (Submit OTP)

**Endpoint:** `POST /api/v1/personas/username/{username}/verify-access`

**Query Parameters:**
- `persona_name` (optional): Persona name, defaults to `"default"`

**Request Body:**
```json
{
  "email": "visitor@example.com",
  "otpCode": "123456",
  "firstName": "John",  // Optional
  "lastName": "Doe"     // Optional
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Access granted! Welcome, John.",
  "visitorName": "John"
}
```

**Response Headers:**
```
Set-Cookie: myclone_visitor=<jwt_token>; Max-Age=1209600; HttpOnly; Secure; SameSite=Lax
```

**Response (401 Unauthorized):**
```json
{
  "detail": "Invalid OTP. 2 attempt(s) remaining."
}
```

**Behavior:**
1. Verifies OTP code (max 3 attempts)
2. Creates/updates visitor in `visitor_whitelist`
3. Assigns visitor to persona via `persona_visitors`
4. Sets 14-day authentication cookie (`myclone_visitor`)
5. Updates `last_accessed_at` timestamp
6. Returns visitor's display name (first name or email prefix)

**Cookie Details:**
- **Name:** `myclone_visitor`
- **Value:** JWT token with `visitor_id` and `persona_id`
- **Expiry:** 14 days (1,209,600 seconds)
- **Flags:** `HttpOnly` (XSS protection), `Secure` (HTTPS in production), `SameSite=Lax` (CSRF protection)
- **Scope:** Exact host only (no domain set for security)

---

### Dashboard Management

Protected routes requiring user authentication (`Authorization: Bearer <token>`).

#### 1. List All Visitors (User-Level)

**Endpoint:** `GET /api/v1/users/me/visitors`

**Query Parameters:** None (returns all visitors)

**Response (200 OK):**
```json
{
  "visitors": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "visitor@example.com",
      "firstName": "John",
      "lastName": "Doe",
      "notes": "VIP client",
      "createdAt": "2024-10-25T10:30:00Z",
      "lastAccessedAt": "2024-10-29T14:22:00Z",
      "assignedPersonaCount": 2
    }
  ],
  "total": 25
}
```

**Note:** `assignedPersonaCount` indicates how many personas this visitor is assigned to.

---

#### 2. Add Visitor Manually (User-Level)

**Endpoint:** `POST /api/v1/users/me/visitors`

**Request Body:**
```json
{
  "email": "newvisitor@example.com",
  "firstName": "Jane",
  "lastName": "Smith",
  "notes": "Beta tester"
}
```

**Response (201 Created):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "email": "newvisitor@example.com",
  "firstName": "Jane",
  "lastName": "Smith",
  "notes": "Beta tester",
  "createdAt": "2024-10-30T09:15:00Z",
  "lastAccessedAt": null,
  "assignedPersonaCount": 0
}
```

**Behavior:**
- Creates visitor in global `visitor_whitelist`
- Does NOT automatically assign to any persona
- Duplicate email returns 409 Conflict

---

#### 3. Update Visitor (User-Level)

**Endpoint:** `PATCH /api/v1/users/me/visitors/{visitor_id}`

**Request Body (All Optional):**
```json
{
  "firstName": "Jane Marie",
  "lastName": "Smith-Johnson",
  "notes": "Premium client - priority support"
}
```

**Response (200 OK):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "email": "newvisitor@example.com",
  "firstName": "Jane Marie",
  "lastName": "Smith-Johnson",
  "notes": "Premium client - priority support",
  "createdAt": "2024-10-30T09:15:00Z",
  "lastAccessedAt": null,
  "assignedPersonaCount": 2
}
```

---

#### 4. Remove Visitor (User-Level)

**Endpoint:** `DELETE /api/v1/users/me/visitors/{visitor_id}`

**Response (204 No Content):**
```
(Empty response body)
```

**Behavior:**
- Deletes visitor from `visitor_whitelist`
- CASCADE deletes all `persona_visitors` assignments
- Revokes all access immediately
- Returns HTTP 204 with no body (standard REST practice for DELETE)

---

#### 5. List Assigned Visitors (Persona-Level)

**Endpoint:** `GET /api/v1/personas/{persona_id}/visitors`

**Response (200 OK):**
```json
{
  "visitors": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "visitor@example.com",
      "firstName": "John",
      "lastName": "Doe",
      "addedAt": "2024-10-25T10:30:00Z",
      "lastAccessedAt": "2024-10-29T14:22:00Z"
    }
  ],
  "total": 5
}
```

---

#### 6. Bulk Assign Visitors (Persona-Level)

**Endpoint:** `POST /api/v1/personas/{persona_id}/visitors`

**Request Body:**
```json
{
  "visitorIds": [
    "550e8400-e29b-41d4-a716-446655440000",
    "770e8400-e29b-41d4-a716-446655440000"
  ]
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Successfully assigned 2 visitor(s) to persona",
  "assignedCount": 2
}
```

**Behavior:**
- Creates `persona_visitors` entries for each visitor
- Skips visitors already assigned (idempotent)
- `assignedCount` indicates only NEW assignments (excludes already-assigned visitors)

---

#### 7. Remove Visitor from Persona (Persona-Level)

**Endpoint:** `DELETE /api/v1/personas/{persona_id}/visitors/{visitor_id}`

**Response (204 No Content):**
```
(Empty response body)
```

**Behavior:**
- Deletes `persona_visitors` entry
- Visitor remains in global whitelist
- Can be reassigned later
- Returns HTTP 204 with no body (standard REST practice for DELETE)

---

#### 8. Toggle Access Control (Persona-Level)

**Endpoint:** `PATCH /api/v1/personas/{persona_id}/access-control`

**Request Body:**
```json
{
  "isPrivate": true
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Persona is now private. Access control enabled.",
  "personaId": "660e8400-e29b-41d4-a716-446655440000",
  "isPrivate": true,
  "accessControlEnabledAt": "2024-10-30T10:00:00Z"
}
```

**Behavior:**
- Updates `personas.is_private` flag
- Sets `access_control_enabled_at` timestamp when enabling
- Clears `access_control_enabled_at` when disabling
- Existing visitor assignments remain active

---

## Security Features

### 1. Cryptographically Secure OTP Generation

**Implementation:**
```python
import secrets

otp_code = str(secrets.randbelow(900000) + 100000)  # 6-digit code
```

**Why:** Uses `secrets` module (CSPRNG) instead of `random` to prevent predictability.

**Location:** `shared/database/repositories/persona_access_repository.py:62`

---

### 2. Rate Limiting

**OTP Requests:**
- Max 5 OTPs per hour per email/persona combination
- Tracked in repository layer
- Returns 429 Too Many Requests if exceeded

**Implementation:**
```python
recent_count = await self.get_recent_otp_count(persona_id, email, hours=1)
if recent_count >= 5:
    raise ValueError("Rate limit exceeded. Please try again later.")
```

**Location:** `shared/database/repositories/persona_access_repository.py:50-58`

---

### 3. OTP Expiry & Attempt Limits

**Expiry:** 5 minutes from creation
**Max Attempts:** 3 tries per OTP
**Auto-Cleanup:** Expired OTPs deleted after 24 hours

**Verification Logic:**
```python
# Check expiry
if datetime.now(timezone.utc) > otp.expires_at:
    return False, "OTP has expired. Please request a new one."

# Check attempts
if otp.attempts >= otp.max_attempts:
    return False, "Maximum verification attempts reached. Please request a new OTP."

# Increment attempts
otp.attempts += 1

# Verify code
if otp.otp_code != otp_code:
    return False, f"Invalid OTP. {remaining} attempt(s) remaining."
```

**Location:** `shared/database/repositories/persona_access_repository.py:94-159`

---

### 4. JWT-Based Visitor Cookies

**Token Payload:**
```json
{
  "visitor_id": "550e8400-e29b-41d4-a716-446655440000",
  "persona_id": "660e8400-e29b-41d4-a716-446655440000",
  "exp": 1730000000,  // 14 days from issue
  "iat": 1728790400   // Issue timestamp
}
```

**Cookie Settings:**
```python
response.set_cookie(
    key="myclone_visitor",
    value=token,
    max_age=14 * 24 * 60 * 60,  # 14 days
    httponly=True,              # Prevents XSS
    secure=is_production,       # HTTPS only in production
    samesite="lax",             # CSRF protection
    # domain NOT set - exact host only
)
```

**Security Benefits:**
- `HttpOnly`: JavaScript cannot access token (XSS protection)
- `Secure`: HTTPS-only in production (MITM protection)
- `SameSite=Lax`: CSRF protection while allowing navigation
- No domain set: Cookie scoped to exact host (prevents leakage)

**Location:** `app/auth/persona_access.py:154-205`

---

### 5. Access Validation Middleware

**Dependency:** `check_persona_access()`

**Used in protected routes:**
```python
from app.auth.persona_access import check_persona_access

@router.get("/{username}/{persona_name}/chat")
async def chat(
    persona: Persona,
    visitor: Optional[VisitorWhitelist] = Depends(check_persona_access)
):
    # persona: Always populated (404 if not found)
    # visitor: None for public personas, VisitorWhitelist for private
    pass
```

**Validation Flow:**
1. Load persona from database
2. If public (`is_private=False`), allow immediately
3. If private, require valid `myclone_visitor` cookie
4. Verify JWT token signature and expiry
5. Check `visitor_id` and `persona_id` in token
6. Load visitor from database
7. Verify visitor is still on persona's allowlist
8. Update `last_accessed_at` timestamp
9. Return `(persona, visitor)` tuple

**Error Responses:**
- `404`: Persona not found
- `403`: Private persona, no/invalid cookie, not on allowlist, token expired

**Location:** `app/auth/persona_access.py:37-151`

---

### 6. Email Normalization

All email addresses are normalized to prevent bypasses:

```python
normalized_email = email.lower().strip()
```

**Prevents:**
- `John@Example.com` vs `john@example.com` (case mismatch)
- `john@example.com ` (trailing space)
- ` john@example.com` (leading space)

**Location:** Applied in all repository methods handling emails

---

### 7. Environment-Dependent Security

**Development:**
- `secure=False` (allows HTTP cookies)
- `ENVIRONMENT=development` (must be set explicitly)

**Production/Staging:**
- `secure=True` (requires HTTPS)
- `ENVIRONMENT=production` (default for safety)

```python
is_production = settings.environment.lower() in ["production", "staging"]

response.set_cookie(
    secure=is_production,  # Environment-dependent
    # ...
)
```

**Default:** `production` (secure by default)

**Location:** `app/auth/persona_access.py:183` and `shared/config.py:232`

---

## Configuration

### Environment Variables

Add to `.env` file:

```bash
# Resend Email Service (for OTP verification)
RESEND_API_KEY=re_your_api_key_here

# JWT Settings (shared with user authentication)
JWT_SECRET_KEY=your-secret-key-here  # Use: openssl rand -base64 32
JWT_ALGORITHM=HS256
JWT_EXPIRATION_DAYS=30

# Environment (affects cookie security)
ENVIRONMENT=production  # Options: development, staging, production
# NOTE: Defaults to "production" for security. Set to "development" for local testing.
```

### Dependencies

Add to `pyproject.toml`:

```toml
[tool.poetry.dependencies]
resend = "2.18.0"                              # Email service for OTP
pydantic = {extras = ["email"], version = "*"} # Email validation
```

Install:
```bash
poetry install
```

---

### Database Migrations

Apply migrations:

```bash
# Check current version
poetry run alembic current

# Apply all migrations
poetry run alembic upgrade head

# Verify
poetry run alembic history --verbose
```

**Migrations Applied:**
1. `272ec6abd141_add_persona_access_control_tables.py` - Creates tables
2. `4f2b493172de_merge_persona_access_control_and_tier_.py` - Merge migration

---

## Usage Examples

### Example 1: Enable Private Persona

**Step 1:** Toggle persona to private (Dashboard)

```bash
curl -X PATCH https://api.myclone.is/api/v1/personas/{persona_id}/access-control \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"isPrivate": true}'
```

**Step 2:** Add visitors to whitelist

```bash
curl -X POST https://api.myclone.is/api/v1/users/me/visitors \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "client@example.com",
    "firstName": "John",
    "lastName": "Client",
    "notes": "Premium client"
  }'
```

**Step 3:** Assign visitors to persona

```bash
curl -X POST https://api.myclone.is/api/v1/personas/{persona_id}/visitors \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "visitorIds": ["VISITOR_UUID_1", "VISITOR_UUID_2"]
  }'
```

---

### Example 2: Visitor Access Flow (Public)

**Step 1:** Request OTP

```bash
curl -X POST 'https://api.myclone.is/api/v1/personas/username/johndoe/request-access?persona_name=default' \
  -H "Content-Type: application/json" \
  -d '{
    "email": "visitor@example.com",
    "firstName": "Jane"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Verification code sent to visitor@example.com. Please check your inbox."
}
```

**Step 2:** Visitor receives email with OTP (e.g., `123456`)

**Step 3:** Verify OTP

```bash
curl -X POST 'https://api.myclone.is/api/v1/personas/username/johndoe/verify-access?persona_name=default' \
  -H "Content-Type: application/json" \
  -d '{
    "email": "visitor@example.com",
    "otpCode": "123456"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Access granted! Welcome, Jane.",
  "visitorName": "Jane"
}
```

**Cookie Set:** `myclone_visitor=<jwt_token>; Max-Age=1209600; HttpOnly; Secure; SameSite=Lax`

**Step 4:** Access persona (cookie included automatically)

```bash
curl https://api.myclone.is/api/v1/chat/johndoe/default \
  -H "Cookie: myclone_visitor=<jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'
```

---

### Example 3: Bulk Visitor Management

**Scenario:** Add 10 beta testers to 3 different personas

**Step 1:** Add all visitors to global whitelist

```python
import requests

visitors = [
    {"email": f"tester{i}@example.com", "firstName": f"Tester{i}", "notes": "Beta tester"}
    for i in range(1, 11)
]

for visitor in visitors:
    response = requests.post(
        "https://api.myclone.is/api/v1/users/me/visitors",
        headers={"Authorization": f"Bearer {token}"},
        json=visitor
    )
    print(f"Added: {visitor['email']}")
```

**Step 2:** Bulk assign to each persona

```python
# Get visitor IDs
response = requests.get(
    "https://api.myclone.is/api/v1/users/me/visitors",
    headers={"Authorization": f"Bearer {token}"}
)
visitor_ids = [v["id"] for v in response.json()["visitors"]]

# Assign to 3 personas
persona_ids = ["PERSONA_1_UUID", "PERSONA_2_UUID", "PERSONA_3_UUID"]

for persona_id in persona_ids:
    requests.post(
        f"https://api.myclone.is/api/v1/personas/{persona_id}/visitors",
        headers={"Authorization": f"Bearer {token}"},
        json={"visitorIds": visitor_ids}
    )
    print(f"Assigned {len(visitor_ids)} visitors to {persona_id}")
```

---

## Troubleshooting

### Issue 1: OTP Emails Not Sending

**Symptoms:**
- Request succeeds but no email received
- Logs show email sending errors

**Solutions:**

1. **Check Resend API key:**
   ```bash
   # Verify environment variable is set
   echo $RESEND_API_KEY

   # Should start with: re_
   ```

2. **Check Resend domain verification:**
   - Log in to [Resend Dashboard](https://resend.com/domains)
   - Verify sending domain is verified (DNS records configured)

3. **Check email template rendering:**
   ```python
   # Test email generation
   from app.services.otp_service import OTPService
   service = OTPService()
   html = service._generate_html_email("123456", "John", "Test Persona")
   print(html)  # Should contain valid HTML
   ```

4. **Check Resend logs:**
   - View delivery logs in Resend dashboard
   - Look for bounce/rejection reasons

---

### Issue 2: Cookie Not Set/Persisted

**Symptoms:**
- Verify endpoint succeeds but cookie not saved
- Browser doesn't send cookie on subsequent requests

**Solutions:**

1. **Check HTTPS in production:**
   ```bash
   # Verify environment setting
   echo $ENVIRONMENT

   # If production/staging, must use HTTPS
   # If development, HTTP is allowed
   ```

2. **Check cookie domain scope:**
   ```python
   # Cookies are scoped to exact host by default
   # app.myclone.is cookie won't work on api.myclone.is

   # To share cookies across subdomains (less secure):
   response.set_cookie(domain=".myclone.is", ...)
   ```

3. **Check browser settings:**
   - Ensure cookies are enabled
   - Check for third-party cookie restrictions
   - Use browser dev tools → Application → Cookies

4. **Check SameSite attribute:**
   - `SameSite=Lax` allows navigation but blocks CSRF
   - Cross-origin requests may need `SameSite=None; Secure`

---

### Issue 3: Visitor Removed But Still Has Access

**Symptoms:**
- Visitor deleted from dashboard
- Visitor can still access persona with old cookie

**Solutions:**

1. **Cookie is still valid (14-day expiry):**
   ```python
   # JWT tokens persist until expiry, even if visitor deleted
   # Middleware checks allowlist on every request

   # Solution: Access validation will fail when:
   # 1. Visitor not found in database
   # 2. Visitor not assigned to persona
   ```

2. **Clear visitor cookies (user action):**
   ```javascript
   // Client-side cookie deletion
   document.cookie = "myclone_visitor=; Max-Age=0; path=/";
   ```

3. **Verify middleware is applied:**
   ```python
   # Protected routes must use Depends(check_persona_access)
   @router.get("/{username}/chat")
   async def chat(
       persona: Persona,
       visitor: Optional[VisitorWhitelist] = Depends(check_persona_access)
   ):
       pass
   ```

---

### Issue 4: Rate Limit Not Working

**Symptoms:**
- Can send more than 5 OTPs per hour
- No rate limit errors

**Solutions:**

1. **Check repository implementation:**
   ```python
   # Verify rate limiting is called before OTP creation
   recent_count = await self.get_recent_otp_count(persona_id, email, hours=1)
   if recent_count >= 5:
       raise ValueError("Rate limit exceeded")
   ```

2. **Check time window:**
   ```python
   # Rate limit is per 1-hour rolling window
   # OTPs created 61 minutes ago don't count

   # Debug: Check OTP timestamps
   stmt = select(PersonaAccessOTP).where(
       PersonaAccessOTP.persona_id == persona_id,
       PersonaAccessOTP.email == email,
       PersonaAccessOTP.created_at >= cutoff_time
   )
   ```

3. **Check error handling:**
   ```python
   # Ensure ValueError is caught and returned as 429
   try:
       await otp_service.send_otp_email(...)
   except ValueError as e:
       if "rate limit" in str(e).lower():
           raise HTTPException(status_code=429, detail=str(e))
   ```

---

### Issue 5: OTP Expired Immediately

**Symptoms:**
- OTP verification fails with "OTP has expired"
- OTP was just sent seconds ago

**Solutions:**

1. **Check server timezone:**
   ```python
   # All timestamps must use UTC
   from datetime import datetime, timezone

   # Correct:
   expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

   # Incorrect (uses local time):
   expires_at = datetime.now() + timedelta(minutes=5)
   ```

2. **Check database timezone:**
   ```sql
   -- PostgreSQL should store TIMESTAMPTZ (timezone-aware)
   SELECT column_name, data_type
   FROM information_schema.columns
   WHERE table_name = 'persona_access_otps'
     AND column_name = 'expires_at';

   -- Should show: timestamptz or timestamp with time zone
   ```

3. **Check expiry calculation:**
   ```python
   # Debug: Print OTP details
   print(f"Created: {otp.created_at}")
   print(f"Expires: {otp.expires_at}")
   print(f"Now: {datetime.now(timezone.utc)}")
   print(f"Expired: {datetime.now(timezone.utc) > otp.expires_at}")
   ```

---

### Issue 6: Cannot Toggle Persona to Private

**Symptoms:**
- PATCH request succeeds but `is_private` stays `false`
- No error returned

**Solutions:**

1. **Check request body:**
   ```bash
   # Correct (camelCase):
   curl -X PATCH /personas/{id}/access-control \
     -d '{"isPrivate": true}'

   # Incorrect (snake_case won't match Pydantic alias):
   curl -X PATCH /personas/{id}/access-control \
     -d '{"is_private": true}'
   ```

2. **Check Pydantic model:**
   ```python
   # Model should have alias configuration
   class AccessControlToggleRequest(BaseModel):
       is_private: bool = Field(..., alias="isPrivate")

       class Config:
           populate_by_name = True  # Accept both formats
   ```

3. **Check database commit:**
   ```python
   # Ensure changes are committed
   persona.is_private = request.is_private
   session.add(persona)
   await session.commit()  # Don't forget this!
   await session.refresh(persona)
   ```

---

## Performance Considerations

### Database Indexes

All critical queries are indexed:

```sql
-- Fast visitor lookup by user and email
CREATE INDEX idx_visitor_whitelist_email ON visitor_whitelist(user_id, email);

-- Fast persona assignment lookup
CREATE INDEX idx_persona_visitors_persona ON persona_visitors(persona_id);

-- Fast OTP verification
CREATE INDEX idx_persona_access_otps_lookup ON persona_access_otps(persona_id, email, otp_code);

-- Fast OTP cleanup
CREATE INDEX idx_persona_access_otps_expires ON persona_access_otps(expires_at);
```

---

### OTP Cleanup Job

Expired OTPs should be cleaned up regularly:

```python
# Background job (run every 6 hours)
from shared.database.repositories.persona_access_repository import get_persona_access_repository

async def cleanup_expired_otps():
    repo = get_persona_access_repository()
    deleted = await repo.cleanup_expired_otps(hours_old=24)
    print(f"Cleaned up {deleted} expired OTPs")
```

**Cron Schedule:**
```bash
# Add to crontab
0 */6 * * * /path/to/cleanup_script.sh  # Every 6 hours
```

---

### Connection Pooling

Database connections are pooled via SQLAlchemy:

```python
# shared/database/models/database.py
engine = create_async_engine(
    get_database_url(),
    echo=False,
    pool_size=10,        # Max 10 concurrent connections
    max_overflow=20,     # Allow 20 overflow connections
    pool_pre_ping=True   # Verify connections before use
)
```

---

## Migration Guide

### Migrating Existing Personas

If you have existing personas and want to enable access control:

**Step 1:** Apply migrations

```bash
poetry run alembic upgrade head
```

**Step 2:** All existing personas default to public (`is_private=false`)

**Step 3:** Enable access control per persona as needed

```bash
# Via API
curl -X PATCH /api/v1/personas/{persona_id}/access-control \
  -H "Authorization: Bearer TOKEN" \
  -d '{"isPrivate": true}'

# Or via SQL
UPDATE personas
SET is_private = true,
    access_control_enabled_at = NOW()
WHERE id = 'PERSONA_UUID';
```

**Step 4:** Add visitors to whitelist and assign to personas

---

## Future Enhancements

Potential features for future releases:

1. **Email Templates Customization** - Allow users to customize OTP email branding
2. **Access Analytics** - Track visitor access patterns and engagement
3. **Temporary Access Links** - Generate time-limited access links (bypass OTP)
4. **IP Whitelisting** - Allow access from specific IP ranges
5. **SSO Integration** - Enterprise SSO for visitor authentication
6. **Webhook Notifications** - Notify on new visitor requests
7. **Access Expiry** - Set expiry dates for visitor access
8. **Multi-Factor Authentication** - Additional security layer beyond OTP
9. **Visitor Groups** - Organize visitors into groups for bulk management
10. **API Keys for Programmatic Access** - Allow API access without cookies

---

## Support

For questions or issues:

- **Documentation:** This file + [README.md](../README.md)
- **Code References:**
  - Database: `shared/database/models/persona_access.py`
  - Routes: `app/api/persona_access_routes.py`, `app/api/visitor_management_routes.py`
  - Services: `app/services/otp_service.py`, `app/auth/persona_access.py`
  - Repositories: `shared/database/repositories/persona_access_repository.py`
- **Issues:** Create GitHub issue with `[Access Control]` prefix

---

## Changelog

### v1.0.0 (October 2024)

**Initial Release**

- ✅ Database schema with three-table architecture
- ✅ OTP-based email verification via Resend
- ✅ JWT-based visitor authentication (14-day cookies)
- ✅ Public visitor access flow (request + verify endpoints)
- ✅ Dashboard management (visitor CRUD + assignments)
- ✅ Access control toggle (public/private personas)
- ✅ Rate limiting (5 OTPs per hour)
- ✅ Security hardening (CSPRNG, cookie flags, email normalization)
- ✅ Multi-persona support (persona_name parameter)
- ✅ Environment-dependent cookie security

---

**Feature Sponsor:** Luxury Institute
**Implementation Team:** MyClone Development Team
**Last Updated:** October 30, 2024
