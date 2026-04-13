/**
 * Password Validation Utilities
 * Matches backend validation requirements
 */

export interface PasswordValidationResult {
  isValid: boolean;
  error: string | null;
}

/**
 * Validate password strength
 * Requirements:
 * - Minimum 8 characters
 * - At least one uppercase letter
 * - At least one lowercase letter
 * - At least one number
 *
 * @param password - The password to validate
 * @returns Validation result with error message
 */
export function validatePassword(password: string): PasswordValidationResult {
  // Check minimum length
  if (password.length < 8) {
    return {
      isValid: false,
      error: "Password must be at least 8 characters long.",
    };
  }

  // Check for uppercase letter
  if (!/[A-Z]/.test(password)) {
    return {
      isValid: false,
      error: "Password must contain at least one uppercase letter.",
    };
  }

  // Check for lowercase letter
  if (!/[a-z]/.test(password)) {
    return {
      isValid: false,
      error: "Password must contain at least one lowercase letter.",
    };
  }

  // Check for number
  if (!/[0-9]/.test(password)) {
    return {
      isValid: false,
      error: "Password must contain at least one number.",
    };
  }

  // All checks passed
  return {
    isValid: true,
    error: null,
  };
}

/**
 * Get password strength level
 * @param password - The password to check
 * @returns Strength level: weak, medium, strong
 */
export function getPasswordStrength(
  password: string,
): "weak" | "medium" | "strong" {
  const validation = validatePassword(password);

  if (!validation.isValid) {
    return "weak";
  }

  // Check for special characters and length
  const hasSpecialChar = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password);
  const hasGoodLength = password.length >= 12;

  if (hasSpecialChar && hasGoodLength) {
    return "strong";
  }

  if (hasSpecialChar || hasGoodLength) {
    return "medium";
  }

  return "medium";
}
