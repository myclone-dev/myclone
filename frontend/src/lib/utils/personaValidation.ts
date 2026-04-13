/**
 * Persona Name Validation Utilities
 * Matches backend validation logic
 */

const RESERVED_NAMES = [
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
  "new",
  "edit",
  "create",
  "delete",
  "update",
  "default",
];

export interface PersonaNameValidationResult {
  isValid: boolean;
  error: string | null;
  slug: string;
}

/**
 * Validate persona name with frontend checks matching backend logic
 *
 * @param name - The persona name to validate
 * @returns Validation result with slug and error message
 */
export function validatePersonaName(name: string): PersonaNameValidationResult {
  // Step 1: Slugify
  let slug = name.toLowerCase().trim();
  slug = slug.replace(/[^\w\s-]/g, "");
  slug = slug.replace(/[-\s_]+/g, "-");
  slug = slug.replace(/^-+|-+$/g, "");

  // Step 2: Validate length
  if (slug.length < 3) {
    return {
      isValid: false,
      error: "Persona name too short. Must be at least 3 characters.",
      slug: slug,
    };
  }

  if (slug.length > 60) {
    return {
      isValid: false,
      error: "Persona name too long. Must be 60 characters or less.",
      slug: slug,
    };
  }

  // Step 3: Check reserved names
  if (RESERVED_NAMES.includes(slug)) {
    return {
      isValid: false,
      error: `Persona name '${slug}' is reserved. Please choose a different name.`,
      slug: slug,
    };
  }

  // Step 4: Pattern validation
  const PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;
  if (!PATTERN.test(slug)) {
    return {
      isValid: false,
      error:
        "Invalid format. Use only letters, numbers, and hyphens (no consecutive hyphens).",
      slug: slug,
    };
  }

  // Step 5: Must start with letter
  if (!/^[a-z]/.test(slug)) {
    return {
      isValid: false,
      error: `Persona name must start with a letter, not a number. Try 'persona-${slug}' instead.`,
      slug: slug,
    };
  }

  // All checks passed
  return {
    isValid: true,
    error: null,
    slug: slug,
  };
}
