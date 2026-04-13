/**
 * Email validation utility
 * Uses a robust regex pattern that matches common email formats
 * Should be kept in sync with backend validation rules
 */

/**
 * Email validation regex
 * Based on RFC 5322 simplified pattern
 * - Allows alphanumeric characters, dots, hyphens, underscores, and plus signs in local part
 * - Requires @ symbol
 * - Allows alphanumeric characters, dots, and hyphens in domain
 * - Requires at least one dot in domain with 2+ character TLD
 */
const EMAIL_REGEX = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

/**
 * Validates email format
 * @param email - Email address to validate
 * @returns true if email is valid, false otherwise
 */
export const isValidEmail = (email: string): boolean => {
  if (!email || typeof email !== "string") {
    return false;
  }

  const trimmedEmail = email.trim();

  // Check length constraints
  if (trimmedEmail.length === 0 || trimmedEmail.length > 254) {
    return false;
  }

  // Check format with regex
  if (!EMAIL_REGEX.test(trimmedEmail)) {
    return false;
  }

  // Additional validation: local part and domain part length
  const [localPart, domainPart] = trimmedEmail.split("@");

  if (!localPart || localPart.length > 64) {
    return false;
  }

  if (!domainPart || domainPart.length > 253) {
    return false;
  }

  // Check for consecutive dots
  if (trimmedEmail.includes("..")) {
    return false;
  }

  return true;
};

/**
 * Validates and normalizes email
 * @param email - Email address to validate and normalize
 * @returns Normalized email or null if invalid
 */
export const validateAndNormalizeEmail = (email: string): string | null => {
  const trimmedEmail = email.trim().toLowerCase();

  if (!isValidEmail(trimmedEmail)) {
    return null;
  }

  return trimmedEmail;
};
