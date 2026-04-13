"""
Validation utilities for user input

This module provides shared validation functions for:
- Username validation and normalization
- Persona name slugification and validation
"""

import re
from typing import Optional

# Reserved usernames that cannot be used (prevents URL conflicts and security issues)
RESERVED_USERNAMES = {
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
}

# Reserved persona names (extends username reserved list + persona-specific routes)
RESERVED_PERSONA_NAMES = RESERVED_USERNAMES | {
    "new",  # Routing conflict: /[username]/new
    "edit",  # Routing conflict: /[username]/edit
    "create",  # Routing conflict: /[username]/create
    "delete",  # Routing conflict: /[username]/delete
    "update",  # Routing conflict: /[username]/update
}

# Username validation: start with letter, 3-30 chars, allow letters/numbers/_/-
USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{2,29}$")

# Persona name validation regex:
# - 3-60 characters total (longer than username for descriptive names)
# - Lowercase alphanumeric + hyphens (URL-friendly)
# - No leading/trailing/consecutive hyphens
# - Pattern: ^[a-z0-9]+(-[a-z0-9]+)*$
#   - [a-z0-9]+ : Start with one or more alphanumeric
#   - (-[a-z0-9]+)* : Zero or more groups of (hyphen + alphanumeric)
#   - Result: No consecutive hyphens, no leading/trailing hyphens
PERSONA_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def validate_username_format(username: str) -> tuple[bool, Optional[str], str]:
    """
    Shared username validation function used across all authentication flows

    This ensures consistent validation logic across:
    - Email/password registration (RegisterRequest)
    - Expert onboarding (ExpertOnboardingRequest)
    - Username availability check endpoint

    Args:
        username: Raw username string to validate

    Returns:
        Tuple of (is_valid, error_message, normalized_username)
        - is_valid: True if username passes all validation checks
        - error_message: Human-readable error message if invalid, None if valid
        - normalized_username: Lowercase, stripped version of username

    Validation rules:
        1. Whitespace is stripped
        2. Converted to lowercase for consistency
        3. Cannot be whitespace-only or empty after stripping
        4. Must be 3-30 characters
        5. Must start with a letter (not number, underscore, or hyphen)
        6. Can contain letters, numbers, underscores, and hyphens
        7. Cannot be a reserved word

    Examples:
        "johndoe" → (True, None, "johndoe")
        "JohnDoe123" → (True, None, "johndoe123")
        "john_doe" → (True, None, "john_doe")
        "test-user" → (True, None, "test-user")
        "jo" → (False, "Username must be 3-30 characters...", "jo")
        "admin" → (False, "Username 'admin' is reserved...", "admin")
    """
    # Strip whitespace and convert to lowercase (normalized form)
    username_stripped = username.strip()
    username_lower = username_stripped.lower()

    # Check for empty/whitespace-only username
    if not username_stripped or username_stripped.isspace():
        return (
            False,
            "Username must be 3-30 characters, start with a letter, and can contain letters, numbers, underscores, and hyphens",
            username_lower,
        )

    # Length check - use normalized form for consistency
    if len(username_lower) < 3 or len(username_lower) > 30:
        return (
            False,
            "Username must be 3-30 characters, start with a letter, and can contain letters, numbers, underscores, and hyphens",
            username_lower,
        )

    # Check reserved usernames
    if username_lower in RESERVED_USERNAMES:
        return (
            False,
            f"Username '{username}' is reserved and cannot be used. Please choose a different username.",
            username_lower,
        )

    # Check format with regex - use normalized form for consistency
    if not USERNAME_PATTERN.match(username_lower):
        return (
            False,
            "Username must be 3-30 characters, start with a letter, and can contain letters, numbers, underscores, and hyphens",
            username_lower,
        )

    # Username is valid!
    return (True, None, username_lower)


def slugify_persona_name(name: str) -> str:
    """
    Convert persona display name to URL-safe slug

    This function transforms user-provided persona names into URL-friendly slugs
    that can be safely used in routes like /[username]/[persona_name]

    Transformation rules:
        1. Convert to lowercase
        2. Remove special characters (keep alphanumeric and spaces/hyphens)
        3. Replace spaces and consecutive hyphens with single hyphen
        4. Remove leading/trailing hyphens
        5. Validate length (3-60 chars)
        6. Validate against reserved names
        7. Validate pattern (no consecutive/leading/trailing hyphens)
        8. Validate starts with letter (not number)

    Args:
        name: User-provided persona display name

    Returns:
        URL-safe slug (lowercase, alphanumeric + hyphens)

    Raises:
        ValueError: If name is invalid, too short/long, reserved, or starts with number

    Examples:
        "Engineer Persona" → "engineer-persona"
        "Sales & Marketing!" → "sales-marketing"
        "Tech Advisor 2024" → "tech-advisor-2024"
        "My   Multiple    Spaces" → "my-multiple-spaces"
        "default" → ValueError (reserved)
        "666 Persona" → ValueError (starts with number)
        "2024 Sales" → ValueError (starts with number)
    """
    # Lowercase and strip whitespace
    slug = name.lower().strip()

    # Remove special characters except alphanumeric, spaces, and hyphens
    slug = re.sub(r"[^\w\s-]", "", slug)

    # Replace spaces and multiple hyphens/underscores with single hyphen
    slug = re.sub(r"[-\s_]+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Validate length (3-60 characters for SEO and readability)
    if len(slug) < 3:
        raise ValueError(
            f"Persona name too short. Must be at least 3 characters (got: '{slug}' from '{name}')"
        )

    if len(slug) > 60:
        raise ValueError(
            f"Persona name too long. Must be 60 characters or less (got: {len(slug)} from '{name}')"
        )

    # Check reserved names (case-insensitive check)
    if slug in RESERVED_PERSONA_NAMES:
        raise ValueError(
            f"Persona name '{slug}' is reserved and cannot be used. Please choose a different name."
        )

    # Validate pattern (alphanumeric + hyphens, no consecutive/leading/trailing hyphens)
    if not PERSONA_NAME_PATTERN.match(slug):
        raise ValueError(
            f"Invalid persona name format: '{slug}'. Use only letters, numbers, and hyphens (no consecutive hyphens)."
        )

    # Require slug to start with a letter (industry standard, better SEO, clearer distinction from IDs)
    if not slug[0].isalpha():
        raise ValueError(
            f"Persona name must start with a letter, not a number (got: '{slug}' from '{name}'). "
            f"Try rearranging: e.g., 'persona-{slug}' or move letters to the front."
        )

    return slug


def validate_persona_name_format(name: str) -> tuple[bool, Optional[str], str]:
    """
    Validate and slugify persona name

    Similar to validate_username_format but for persona names with slugification.

    Args:
        name: User-provided persona display name

    Returns:
        Tuple of (is_valid, error_message, slugified_name)
        - is_valid: True if name is valid after slugification
        - error_message: Human-readable error message if invalid, None if valid
        - slugified_name: URL-safe slug (lowercase, alphanumeric + hyphens)

    Examples:
        "Engineer Persona" → (True, None, "engineer-persona")
        "ab" → (False, "Persona name too short...", "ab")
        "default" → (False, "Persona name 'default' is reserved...", "default")
    """
    try:
        slug = slugify_persona_name(name)
        return (True, None, slug)
    except ValueError as e:
        # Return error message and best-effort slug (may be invalid)
        best_effort_slug = name.lower().strip()
        best_effort_slug = re.sub(r"[^\w\s-]", "", best_effort_slug)
        best_effort_slug = re.sub(r"[-\s_]+", "-", best_effort_slug)
        best_effort_slug = best_effort_slug.strip("-")
        return (False, str(e), best_effort_slug)
