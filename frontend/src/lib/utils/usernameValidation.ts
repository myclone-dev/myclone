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
