# Email/Password Authentication

This document describes the email/password authentication system in Expert Clone, which complements the existing OAuth authentication (LinkedIn, Google).

## Overview

Expert Clone supports **multiple authentication methods per user**:
- **OAuth**: LinkedIn, Google (existing)
- **Email/Password**: Traditional email and password login (new)
- **Hybrid**: Users can have both OAuth and password authentication simultaneously

## Architecture

### Multi-Auth Design

The system uses a flexible multi-auth architecture where each authentication method is stored as a separate record in the `auth_details` table:

```
User (id: 123, email: "user@example.com")
  ├─ AuthDetail (auth_type: "linkedin_oauth", access_token: "...")
  └─ AuthDetail (auth_type: "password", hashed_password: "...")
```

**Key Features:**
- One `auth_details` row per authentication method
- `auth_type` field identifies the method: `linkedin_oauth`, `google_oauth`, or `password`
- Independent lockout tracking per method
- Users can login with any enabled authentication method

### Database Schema

**auth_details table:**
- `auth_type`: Authentication method identifier (required)
- `hashed_password`: Bcrypt hash (password auth only)
- `email_verified_at`: Email verification timestamp (password auth only)
- `password_reset_token`: Token for password reset or email verification
- `password_reset_expires`: Token expiration timestamp
- `failed_login_attempts`: Failed login counter (per auth method)
- `locked_until`: Account lockout timestamp

**Constraint:** Unique index on `(user_id, auth_type)` - one auth method per type per user

## Authentication Flows

### 1. New User Registration

**Flow:**
1. User provides email, password, and full name
2. System validates password strength
3. Password is hashed with bcrypt (12 rounds)
4. User record created with `email_confirmed=False`
5. AuthDetail created with `auth_type='password'`
6. Verification email sent with 24-hour token
7. User must verify email before login

**Endpoint:** `POST /api/v1/auth/register`

**Security:**
- Rate limited: 5 attempts per hour per IP
- Email enumeration prevention: Returns success even if email exists
- Bcrypt hashing: 12 rounds (configurable)
- Email verification required

### 2. Email Verification

**Flow:**
1. User clicks link in verification email
2. System validates token and expiration (24 hours)
3. `email_verified_at` timestamp set on AuthDetail
4. User's `email_confirmed` flag set to true
5. User automatically logged in with JWT token
6. Token cleared (single-use)

**Endpoint:** `GET /api/v1/auth/verify-email?token={token}`

### 3. Login with Email/Password

**Flow:**
1. User provides email (or username) and password
2. System finds user and password AuthDetail
3. Checks account lockout status
4. Checks email verification status
5. Verifies password with bcrypt
6. On success: Resets failed attempts, generates JWT, sets cookie
7. On failure: Increments attempts, locks after 5 failures (15 min)

**Endpoint:** `POST /api/v1/auth/login`

**Security:**
- Account lockout: 5 failures = 15 minute lockout
- Generic error messages: Prevents email/username enumeration
- HTTP-only cookie: Prevents XSS attacks
- Password verification in thread pool: Non-blocking bcrypt

### 4. Password Reset

**Flow:**
1. User requests password reset with email
2. System generates reset token (1 hour expiration)
3. Reset email sent with link
4. User clicks link, provides new password
5. System validates token and password strength
6. Password updated, token cleared
7. Confirmation email sent

**Endpoints:**
- `POST /api/v1/auth/forgot-password` - Request reset
- `POST /api/v1/auth/reset-password` - Complete reset

**Security:**
- Rate limited: 3 requests per hour per IP
- Generic messages: Returns success even if email doesn't exist
- Single-use tokens: Cleared after use
- Confirmation emails: Alert user of password changes

### 5. OAuth User Adding Password

**Flow:**
1. OAuth user (already logged in) calls set-password endpoint
2. System validates password strength
3. Creates new AuthDetail with `auth_type='password'`
4. Email verification inherited from OAuth (immediate)
5. Confirmation email sent
6. User can now login with either OAuth or email/password

**Endpoint:** `POST /api/v1/auth/set-password`

**Use Case:** OAuth users who want email/password as backup login method

## Security Features

### Password Security

**Requirements (configurable):**
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- Optional: Special character requirement

**Hashing:**
- Algorithm: bcrypt
- Rounds: 12 (configurable)
- Non-blocking: Runs in thread pool

### Account Protection

**Lockout System:**
- Persistent: Stored in database (survives restarts)
- Per-method: OAuth and password lockouts are independent
- Duration: 15 minutes (configurable)
- Threshold: 5 failed attempts (configurable)

**Rate Limiting:**
- IP-based: slowapi library
- Registration: 5 per hour
- Password reset: 3 per hour
- Verification resend: 3 per hour

### Token Security

**Email Verification:**
- Format: UUID4 (cryptographically secure)
- Expiration: 24 hours
- Single-use: Cleared after verification
- Stored hashed: In password_reset_token field

**Password Reset:**
- Format: UUID4
- Expiration: 1 hour
- Single-use: Cleared after use
- Generic responses: Prevent email enumeration

**JWT Tokens:**
- HTTP-only cookies: Prevents XSS
- Expiration: 30 days (configurable)
- Algorithm: HS256
- Secure flag in production

### Email Enumeration Prevention

All endpoints return generic success messages that don't reveal whether email exists:
- Registration: "Check your email" (even if email exists)
- Password reset: "If account exists, email sent"
- Resend verification: "Email sent" (even if not found)

## API Endpoints Reference

### Public Endpoints

| Endpoint | Method | Purpose | Rate Limit |
|----------|--------|---------|------------|
| `/api/v1/auth/register` | POST | Create new account | 5/hour |
| `/api/v1/auth/login` | POST | Login with password | None |
| `/api/v1/auth/verify-email` | GET | Verify email address | None |
| `/api/v1/auth/forgot-password` | POST | Request password reset | 3/hour |
| `/api/v1/auth/reset-password` | POST | Reset password | None |
| `/api/v1/auth/resend-verification` | POST | Resend verification email | 3/hour |

### Protected Endpoints

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/api/v1/auth/set-password` | POST | OAuth user adds password | JWT Cookie |

## Configuration

### Environment Variables

```bash
# Password Security
PASSWORD_MIN_LENGTH=8
PASSWORD_REQUIRE_UPPERCASE=true
PASSWORD_REQUIRE_LOWERCASE=true
PASSWORD_REQUIRE_NUMBER=true
PASSWORD_REQUIRE_SPECIAL=false
BCRYPT_ROUNDS=12

# Account Security
MAX_FAILED_LOGIN_ATTEMPTS=5
ACCOUNT_LOCKOUT_DURATION_MINUTES=15

# Email Verification
EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS=24

# Password Reset
PASSWORD_RESET_TOKEN_EXPIRY_HOURS=1

# JWT Configuration
JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_DAYS=30

# Frontend URLs (for email links)
FRONTEND_URL=https://app.myclone.is
COOKIE_DOMAIN=myclone.is

# Email Service
RESEND_API_KEY=your_resend_api_key
RESEND_FROM_EMAIL=noreply@myclone.is
```

### Defaults

All security settings have sensible defaults:
- Password: Min 8 chars, uppercase + lowercase + number
- Lockout: 5 failures, 15 minute duration
- Email verification: 24 hour token
- Password reset: 1 hour token
- JWT: 30 day expiration

## Use Cases

### 1. New User Signs Up

**Scenario:** First-time user creates account

**Steps:**
1. User registers at `/register` with email and password
2. Verification email sent
3. User clicks verification link
4. Email verified, user auto-logged in
5. User can now access protected resources

### 2. Existing OAuth User Adds Password

**Scenario:** LinkedIn user wants email/password as backup

**Steps:**
1. User logged in via LinkedIn OAuth
2. User calls `/set-password` with new password
3. Password AuthDetail created (email already verified)
4. User receives confirmation email
5. User can now login with either LinkedIn or email/password

**Benefits:**
- Backup login method if OAuth provider is down
- No need to re-verify email (inherited from OAuth)
- Independent lockout tracking (OAuth failures don't affect password login)

### 3. User Forgets Password

**Scenario:** User can't remember password

**Steps:**
1. User requests reset at `/forgot-password`
2. Reset email sent with 1-hour token
3. User clicks link, provides new password
4. Password updated, confirmation email sent
5. User can login with new password

### 4. Suspicious Activity Lockout

**Scenario:** Attacker tries to brute force account

**Steps:**
1. Attacker makes 5 failed login attempts
2. Account locked for 15 minutes
3. Legitimate user receives no notification (security)
4. After 15 minutes, lockout expires automatically
5. User can login normally

## Email Templates

### Verification Email
- Subject: "Verify your MyClone email address"
- Link: `{FRONTEND_URL}/verify-email?token={token}`
- Expiration: 24 hours

### Password Reset Email
- Subject: "Reset your MyClone password"
- Link: `{FRONTEND_URL}/reset-password?token={token}`
- Expiration: 1 hour

### Password Changed Email
- Subject: "Your MyClone password was changed"
- Alert: If user didn't make change, contact support
- No action required (notification only)

### Password Set Email (OAuth users)
- Subject: "Password authentication added to your MyClone account"
- Confirmation: User can now login with email/password
- Alert: If user didn't make change, contact support

## Implementation Details

### Services

**PasswordService** (`app/services/password_service.py`)
- Password hashing and verification (bcrypt)
- Password strength validation
- Non-blocking operations (thread pool)

**EmailVerificationService** (`app/services/email_verification_service.py`)
- Token generation (UUID4)
- Verification email sending
- Resend verification email

**PasswordResetService** (`app/services/password_reset_service.py`)
- Reset token generation
- Password reset email sending
- Password changed confirmation email
- Password set confirmation email (OAuth users)

**AuthRateLimitingService** (`app/services/auth_rate_limiting_service.py`)
- Failed login tracking (PostgreSQL)
- Account lockout management
- Lockout status checking

### Repository Methods

**UserRepository** (`shared/database/repositories/user_repository.py`)
- `get_password_auth()` - Get password AuthDetail for user
- `create_password_auth()` - Create password AuthDetail
- `get_auth_by_reset_token()` - Find auth by token
- `create_user()` - Create user with email_confirmed flag

## Testing Checklist

### Registration Flow
- [ ] User can register with email and password
- [ ] Weak passwords are rejected
- [ ] Verification email is sent
- [ ] Duplicate email returns generic success (no enumeration)
- [ ] Rate limiting works (5/hour)

### Email Verification
- [ ] Valid token verifies email and auto-logs in
- [ ] Expired token returns error
- [ ] Invalid token returns error
- [ ] Token is single-use (can't be reused)

### Login Flow
- [ ] User can login with email and password
- [ ] User can login with username and password
- [ ] Unverified email prevents login
- [ ] Wrong password increments failed attempts
- [ ] 5 failures lock account for 15 minutes
- [ ] Lockout expires after 15 minutes
- [ ] JWT cookie is set on success

### Password Reset Flow
- [ ] User can request password reset
- [ ] Reset email is sent
- [ ] Valid token allows password reset
- [ ] Expired token returns error
- [ ] Token is single-use
- [ ] Weak new password is rejected
- [ ] Confirmation email is sent after reset

### OAuth + Password Flow
- [ ] OAuth user can add password
- [ ] Email verification inherited from OAuth
- [ ] Duplicate password auth returns 409
- [ ] Confirmation email is sent
- [ ] User can login with both methods

## Migration from OAuth-Only

Existing OAuth users automatically support password authentication:
1. Database migration adds password fields to `auth_details`
2. Existing OAuth records keep `auth_type='linkedin_oauth'` or `'google_oauth'`
3. Users can call `/set-password` to add password auth
4. No data loss or downtime

## Troubleshooting

### Email Not Received
- Check Resend API key is configured
- Check spam/junk folder
- Use `/resend-verification` endpoint (rate limited: 3/hour)
- Check Resend dashboard for delivery status

### Account Locked
- Wait 15 minutes for automatic unlock
- No manual unlock endpoint (security feature)
- User can still use OAuth if enabled

### Password Reset Not Working
- Token expires after 1 hour
- Request new reset if token expired
- Check email for correct reset link
- Token is single-use (can't reuse)

### JWT Cookie Not Set
- Check `secure` flag in production (HTTPS required)
- Check `cookie_domain` setting matches frontend
- Check `samesite` attribute (should be "lax")
- Browser may block third-party cookies

## Related Documentation

- [LinkedIn OAuth Flow](LINKEDIN_OAUTH_FLOW.md) - OAuth authentication
- [API Documentation](API_DOCUMENTATION.md) - Complete API reference
- [README](../README.md) - Project overview and setup

## Security Considerations

### Production Checklist
- [ ] Use strong `JWT_SECRET_KEY` (min 32 bytes)
- [ ] Enable HTTPS in production (required for secure cookies)
- [ ] Configure `COOKIE_DOMAIN` correctly
- [ ] Use strong `BCRYPT_ROUNDS` (12 recommended)
- [ ] Configure email service properly (Resend)
- [ ] Monitor failed login attempts (Sentry integration)
- [ ] Review rate limits for your use case
- [ ] Test password strength requirements

### Known Limitations
- Account lockout is per-method (OAuth and password independent)
- No password history (users can reuse old passwords)
- No password expiration policy
- No multi-factor authentication (MFA) yet
- No session revocation (JWT tokens valid until expiry)

## Future Enhancements

Potential improvements for future versions:
- Multi-factor authentication (MFA/2FA)
- Password history tracking
- Password expiration policies
- Session management and revocation
- Magic link authentication
- Passkey/WebAuthn support
- Remember device functionality
- Login notification emails
