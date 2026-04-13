# Username Validation Guide

## Overview

This document describes the username validation rules for the Expert Clone platform. Validation is enforced on **both frontend and backend** to ensure data integrity and security.

---

## Backend Implementation (✅ Complete)

### Location

- **File**: `app/api/user_routes.py`
- **Model**: `ExpertOnboardingRequest`
- **Validator**: `@field_validator("username")`
- **Availability Endpoint**: `GET /api/v1/users/check-username/{username}`

### Validation Rules

| Rule                 | Description                                        | Example                       |
| -------------------- | -------------------------------------------------- | ----------------------------- |
| **Length**           | 3-30 characters                                    | ✅ `john` ❌ `ab`             |
| **Characters**       | Alphanumeric only (letters and numbers)            | ✅ `johndoe123` ❌ `john_doe` |
| **No Spaces**        | No spaces allowed                                  | ✅ `johndoe` ❌ `john doe`    |
| **No Special Chars** | No underscore, hyphen, or other special characters | ✅ `johndoe` ❌ `john-doe`    |
| **Case**             | Case-insensitive (converted to lowercase)          | `JohnDoe` → `johndoe`         |
| **Reserved**         | Cannot use reserved words                          | ❌ `admin`, `api`, `support`  |

### Regex Pattern

```python
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9]{3,30}$")
```

**Breakdown**:

- `^` - Start of string
- `[a-zA-Z0-9]{3,30}` - 3 to 30 alphanumeric characters
- `$` - End of string
- **Simple and strict**: Only letters and numbers, no special characters

### Reserved Usernames

```python
RESERVED_USERNAMES = {
    "admin", "api", "auth", "about", "contact", "help", "support",
    "terms", "privacy", "login", "logout", "signup", "signin", "register",
    "dashboard", "settings", "profile", "account", "user", "users",
    "expert", "experts", "chat", "widget", "docs", "documentation",
    "blog", "pricing", "features", "public", "static", "assets",
    "me", "undefined", "null", "root", "system", "administrator",
}
```

**Why reserved?**

- **URL conflicts**: `/admin`, `/api`, `/dashboard` are system routes
- **Security**: Prevents impersonation of admin/system accounts
- **UX**: Avoids confusion with system pages

### Error Messages

The backend returns clear, actionable error messages:

1. **Reserved username**:

   ```
   Username 'admin' is reserved and cannot be used. Please choose a different username.
   ```

2. **Invalid format**:
   ```
   Username must be 3-30 characters and can only contain letters and numbers (no spaces or special characters).
   ```

---

## Username Availability Check API

### Endpoint

```
GET /api/v1/users/check-username/{username}
```

**Public endpoint** - No authentication required (for onboarding UX)

### Request

```bash
curl -X GET "http://localhost:8000/api/v1/users/check-username/johndoe"
```

### Response

**Available username**:

```json
{
  "username": "johndoe",
  "available": true,
  "reason": null
}
```

**Unavailable username (taken)**:

```json
{
  "username": "johndoe",
  "available": false,
  "reason": "Username is already taken"
}
```

**Unavailable username (reserved)**:

```json
{
  "username": "admin",
  "available": false,
  "reason": "Username 'admin' is reserved and cannot be used"
}
```

**Unavailable username (invalid format)**:

```json
{
  "username": "john.doe",
  "available": false,
  "reason": "Username can only contain letters and numbers (no spaces or special characters)"
}
```

### Use Cases

1. **Real-time validation** - Check as user types (with debounce)
2. **Pre-submit validation** - Verify before form submission
3. **Username suggestions** - Check if alternatives are available

---

## Frontend Implementation (TODO)

### Implementation Steps

#### 1. **Create Validation Utility** (Recommended)

Create a shared validation utility that mirrors the backend logic:

**File**: `frontend/src/utils/usernameValidation.ts` (or `.js`)

```typescript
/**
 * Username validation utility
 * Mirrors backend validation in app/api/user_routes.py
 */

// Reserved usernames (same as backend)
const RESERVED_USERNAMES = new Set([
  "admin",
  "api",
  "auth",
  "about",
  "contact",
  "help",
  "support",
  "terms",
  "privacy",
  "login",
  "logout",
  "signup",
  "signin",
  "register",
  "dashboard",
  "settings",
  "profile",
  "account",
  "user",
  "users",
  "expert",
  "experts",
  "chat",
  "widget",
  "docs",
  "documentation",
  "blog",
  "pricing",
  "features",
  "public",
  "static",
  "assets",
  "me",
  "undefined",
  "null",
  "root",
  "system",
  "administrator",
]);

// Username regex (same as backend) - Alphanumeric only
const USERNAME_PATTERN = /^[a-zA-Z0-9]{3,30}$/;

export interface UsernameValidationResult {
  isValid: boolean;
  error?: string;
  processedUsername?: string;
}

/**
 * Validate username according to platform rules
 *
 * @param username - The username to validate
 * @returns Validation result with error message if invalid
 */
export function validateUsername(username: string): UsernameValidationResult {
  // Strip whitespace
  const trimmed = username.trim();

  // Length check
  if (trimmed.length < 3) {
    return {
      isValid: false,
      error: "Username must be at least 3 characters long",
    };
  }

  if (trimmed.length > 30) {
    return {
      isValid: false,
      error: "Username must be at most 30 characters long",
    };
  }

  // Convert to lowercase
  const lowercased = trimmed.toLowerCase();

  // Check reserved usernames
  if (RESERVED_USERNAMES.has(lowercased)) {
    return {
      isValid: false,
      error: `Username "${trimmed}" is reserved and cannot be used. Please choose a different username.`,
    };
  }

  // Check format with regex (alphanumeric only)
  if (!USERNAME_PATTERN.test(trimmed)) {
    return {
      isValid: false,
      error:
        "Username can only contain letters and numbers (no spaces or special characters).",
    };
  }

  return {
    isValid: true,
    processedUsername: lowercased,
  };
}

/**
 * Check if a username is available (format validation only)
 * Backend will still check database uniqueness
 *
 * @param username - The username to check
 * @returns True if format is valid, false otherwise
 */
export function isUsernameFormatValid(username: string): boolean {
  return validateUsername(username).isValid;
}
```

#### 2. **API Integration Function**

Create a function to call the availability check endpoint:

**File**: `frontend/src/api/usernameApi.ts`

```typescript
/**
 * Check if a username is available via API
 *
 * @param username - The username to check
 * @returns Promise with availability result
 */
export async function checkUsernameAvailability(username: string): Promise<{
  available: boolean;
  reason?: string;
}> {
  try {
    const response = await fetch(
      `/api/v1/users/check-username/${encodeURIComponent(username)}`
    );

    if (!response.ok) {
      throw new Error("Failed to check username availability");
    }

    const data = await response.json();
    return {
      available: data.available,
      reason: data.reason,
    };
  } catch (error) {
    console.error("Username availability check failed:", error);
    // Return unavailable on error (fail-safe)
    return {
      available: false,
      reason: "Unable to check availability. Please try again.",
    };
  }
}
```

#### 3. **React Hook with API Check (Recommended)**

Create a custom React hook for real-time validation WITH backend check:

**File**: `frontend/src/hooks/useUsernameValidation.ts`

```typescript
import { useState, useEffect } from "react";
import { validateUsername } from "@/utils/usernameValidation";
import { checkUsernameAvailability } from "@/api/usernameApi";

export interface UsernameValidationState {
  isValid: boolean;
  isChecking: boolean;
  error?: string;
}

export function useUsernameValidation(username: string, debounceMs = 500) {
  const [state, setState] = useState<UsernameValidationState>({
    isValid: false,
    isChecking: false,
  });

  useEffect(() => {
    // Don't validate empty string
    if (!username || username.trim().length === 0) {
      setState({ isValid: false, isChecking: false });
      return;
    }

    // First, validate format locally (instant feedback)
    const formatValidation = validateUsername(username);
    if (!formatValidation.isValid) {
      setState({
        isValid: false,
        isChecking: false,
        error: formatValidation.error,
      });
      return;
    }

    // Format is valid, now check availability with backend (debounced)
    setState({ isValid: false, isChecking: true });

    const timeoutId = setTimeout(async () => {
      try {
        const result = await checkUsernameAvailability(username);

        setState({
          isValid: result.available,
          isChecking: false,
          error: result.reason,
        });
      } catch (error) {
        setState({
          isValid: false,
          isChecking: false,
          error: "Unable to check availability",
        });
      }
    }, debounceMs);

    // Cleanup timeout on unmount or username change
    return () => clearTimeout(timeoutId);
  }, [username, debounceMs]);

  return state;
}
```

#### 4. **Form Component Integration**

Example integration with a form using the hook (React + TypeScript):

```tsx
import React, { useState } from "react";
import { useUsernameValidation } from "@/hooks/useUsernameValidation";

export function OnboardingForm() {
  const [username, setUsername] = useState("");
  const validation = useUsernameValidation(username); // Uses debounced API check

  const handleUsernameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUsername(e.target.value);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Don't submit if username is invalid or still checking
    if (!validation.isValid || validation.isChecking) {
      return;
    }

    // Submit to backend
    try {
      const response = await fetch("/api/v1/users/expert/onboarding", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include", // Include auth cookie
        body: JSON.stringify({
          username: username.toLowerCase(), // Send lowercased
          // ... other fields (linkedinUrl, etc.)
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        // Handle error (e.g., show toast)
        console.error("Onboarding failed:", error);
      } else {
        // Success! Redirect to dashboard
        window.location.href = "/dashboard";
      }
    } catch (error) {
      console.error("Network error:", error);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label htmlFor="username">Username</label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={handleUsernameChange}
          placeholder="johndoe"
          minLength={3}
          maxLength={30}
          pattern="[a-zA-Z0-9]{3,30}"
          required
          aria-invalid={!validation.isValid && username.length > 0}
          aria-describedby="username-error username-help"
        />

        {/* Show checking indicator */}
        {validation.isChecking && (
          <p className="info">
            <span className="spinner" /> Checking availability...
          </p>
        )}

        {/* Show error message */}
        {validation.error && !validation.isChecking && (
          <p id="username-error" className="error">
            {validation.error}
          </p>
        )}

        {/* Show success message */}
        {validation.isValid &&
          !validation.isChecking &&
          username.length > 0 && (
            <p className="success">✓ Username is available!</p>
          )}

        <p id="username-help" className="help-text">
          3-30 characters. Letters and numbers only.
        </p>
      </div>

      <button
        type="submit"
        disabled={!validation.isValid || validation.isChecking}
      >
        {validation.isChecking ? "Checking..." : "Continue"}
      </button>
    </form>
  );
}
```

#### 5. **HTML5 Validation Attributes**

For basic browser-level validation, add these attributes to the input:

```html
<input
  type="text"
  name="username"
  minlength="3"
  maxlength="30"
  pattern="[a-zA-Z0-9]{3,30}"
  required
  title="Username must be 3-30 characters and can only contain letters and numbers."
/>
```

**Note**: HTML5 validation is NOT sufficient on its own (can be bypassed), but provides good UX.

---

## Best Practices

### ✅ DO:

1. **Validate on both frontend and backend** - Never trust client-side validation alone
2. **Show real-time feedback** - Validate as user types (with debounce if needed)
3. **Provide clear error messages** - Tell users exactly what's wrong
4. **Show examples** - Provide placeholder text like "johndoe"
5. **Convert to lowercase early** - Show users what their username will look like
6. **Trim whitespace** - Remove leading/trailing spaces automatically
7. **Check reserved words** - Prevent URL conflicts early

### ❌ DON'T:

1. **Don't skip backend validation** - Frontend validation can be bypassed
2. **Don't allow special characters** - Alphanumeric only (no underscore, hyphen, etc.)
3. **Don't make max length too long** - 30 chars is reasonable for URLs
4. **Don't use case-sensitive usernames** - Causes confusion (John vs john)
5. **Don't forget to check database uniqueness** - Frontend validation is format only

---

## Testing

### Backend Tests

Run the provided test script:

```bash
python3 test_username_validation_simple.py
```

### Frontend Tests (Recommended)

Create unit tests for your validation utility:

```typescript
import { validateUsername } from "@/utils/usernameValidation";

describe("validateUsername", () => {
  it("accepts valid usernames", () => {
    expect(validateUsername("john").isValid).toBe(true);
    expect(validateUsername("johndoe").isValid).toBe(true);
    expect(validateUsername("johndoe123").isValid).toBe(true);
  });

  it("rejects invalid usernames", () => {
    expect(validateUsername("ab").isValid).toBe(false); // Too short
    expect(validateUsername("john_doe").isValid).toBe(false); // Underscore not allowed
    expect(validateUsername("john-doe").isValid).toBe(false); // Hyphen not allowed
    expect(validateUsername("john.doe").isValid).toBe(false); // Period not allowed
    expect(validateUsername("admin").isValid).toBe(false); // Reserved
  });

  it("converts to lowercase", () => {
    const result = validateUsername("JohnDoe");
    expect(result.processedUsername).toBe("johndoe");
  });
});
```

---

## Example Usernames

### ✅ Valid

- `john`
- `johndoe`
- `john123`
- `johndoe123`
- `user2024`
- `testuser`
- `abc123xyz`

### ❌ Invalid

| Username                               | Reason                            |
| -------------------------------------- | --------------------------------- |
| `ab`                                   | Too short (< 3 chars)             |
| `this_is_a_very_long_username_exceeds` | Too long (> 30 chars)             |
| `john_doe`                             | Contains underscore (not allowed) |
| `john-doe`                             | Contains hyphen (not allowed)     |
| `john.doe`                             | Contains period (not allowed)     |
| `john@doe`                             | Contains @ symbol                 |
| `john doe`                             | Contains space                    |
| `_johndoe`                             | Starts with special character     |
| `johndoe_`                             | Ends with special character       |
| `admin`                                | Reserved word                     |
| `api`                                  | Reserved word                     |

---

## API Error Handling

### Backend Error Response Format

When validation fails, the backend returns a 422 Unprocessable Entity error:

```json
{
  "detail": [
    {
      "type": "value_error",
      "loc": ["body", "username"],
      "msg": "Username must be 3-30 characters, start and end with a letter or number, and can only contain letters, numbers, underscores, and hyphens.",
      "input": "invalid_username_",
      "ctx": {
        "error": {}
      }
    }
  ]
}
```

### Frontend Error Handling

```typescript
try {
  const response = await fetch('/api/v1/users/expert/onboarding', {
    method: 'POST',
    body: JSON.stringify({ username, ... }),
  });

  if (!response.ok) {
    const error = await response.json();

    // Extract username validation error
    const usernameError = error.detail?.find(
      (err) => err.loc.includes('username')
    );

    if (usernameError) {
      setUsernameError(usernameError.msg);
    }
  }
} catch (error) {
  console.error('Onboarding failed:', error);
}
```

---

## Migration Notes

### Existing Users

Users who already have usernames that don't meet the new criteria (e.g., contain underscores or hyphens):

- **Keep existing usernames** - Don't break existing URLs
- **Apply validation only to new signups and username changes**
- Consider a migration script if needed (only if alphanumeric-only is critical)

**Note**: Since this is a new feature, you likely don't have existing users with non-compliant usernames yet.

---

## Summary

| Aspect            | Implementation                                                |
| ----------------- | ------------------------------------------------------------- |
| **Backend**       | ✅ Complete - Pydantic validator in `ExpertOnboardingRequest` |
| **Frontend**      | ⏳ TODO - Add validation utility + form integration           |
| **Length**        | 3-30 characters                                               |
| **Allowed**       | Letters and numbers only (alphanumeric)                       |
| **Special Chars** | ❌ Not allowed (no underscore, hyphen, etc.)                  |
| **Case**          | Case-insensitive (lowercase)                                  |
| **Reserved**      | 31 reserved words blocked                                     |
| **Tests**         | ✅ Backend tests passing (25/25)                              |

---

## Questions?

If you have questions about username validation:

1. Check this document first
2. Review backend implementation: `app/api/user_routes.py`
3. Check existing examples: Twitter username validation in `app/api/scraping_routes.py`
