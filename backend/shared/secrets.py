"""
Shared secrets utility for handling environment variables and AWS Secrets Manager.

This module provides EXPLICIT methods to retrieve secrets. No magic auto-detection.

Usage patterns:
1. Plain env var (local dev): use get_env()
2. JSON secret (AWS Secrets Manager): use get_json_secret()

Developers must explicitly choose the right method based on how the secret is configured.
"""

import json
import os
from typing import Any


def get_env(key: str, default: str = "") -> str:
    """
    Get a plain environment variable.

    Use this for:
    - Local development (.env files)
    - Docker Compose environment variables
    - Any plain text environment variable

    Args:
        key: Environment variable name
        default: Default value if not found

    Returns:
        The environment variable value

    Example:
        get_env("POSTGRES_HOST", "localhost")
    """
    return os.getenv(key, default).strip()


def get_json_secret(env_var: str, json_key: str, default: str = "") -> str:
    """
    Get a value from a JSON-formatted secret.

    Use this when AWS Secrets Manager stores secrets as JSON.
    The environment variable will contain a JSON string like:
    '{"SENTRY_DSN":"https://...","OTHER_KEY":"value"}'

    Args:
        env_var: Environment variable name containing the JSON
        json_key: Key within the JSON to extract
        default: Default value if not found

    Returns:
        The extracted value from the JSON

    Example:
        # Secrets Manager has JSON: {"SENTRY_DSN":"https://...","PROJECT":"myapp"}
        # ECS injects it as env var SENTRY_SECRET='{"SENTRY_DSN":"https://...",...}'

        get_json_secret("SENTRY_SECRET", "SENTRY_DSN") -> "https://..."
        get_json_secret("SENTRY_SECRET", "PROJECT") -> "myapp"

        # For local dev with plain env vars, falls back to checking env_var directly
        # if env_var == json_key
    """
    raw_value = os.getenv(env_var, "").strip()

    if not raw_value:
        # Only log if it's a critical secret (not optional ones)
        # Reduce noise for optional secrets like AWS_SECRETS, SCRAPING_CONSUMER_SECRETS
        if env_var not in [
            "AWS_SECRETS",
            "SCRAPING_CONSUMER_SECRETS",
            "LIVEKIT_SECRETS",
            "ELEVENLABS_SECRETS",
            "SENTRY_DSN",
        ]:
            print(f"[get_json_secret] {env_var} not found in environment")
        return default

    try:
        secret_data: dict[str, Any] = json.loads(raw_value)
        raw_result = secret_data.get(json_key, default)
        result = str(raw_result).strip()  # Strip whitespace from extracted value
        return result
    except json.JSONDecodeError:
        # If it's not valid JSON, treat as plain text
        # This allows fallback for local dev where env vars are plain text, not JSON
        if env_var == json_key:
            # Expected local dev case: plain text env var
            return raw_value.strip()
        else:
            # Unexpected: we expected JSON with a key, but got invalid JSON
            return default


def get_env_or_raise(key: str) -> str:
    """
    Get a required plain environment variable, raising an error if not found.

    Args:
        key: Environment variable name

    Returns:
        The environment variable value

    Raises:
        ValueError: If the variable is not found or is empty

    Example:
        database_host = get_env_or_raise("POSTGRES_HOST")
    """
    value = get_env(key)
    if not value:
        raise ValueError(f"Required environment variable '{key}' is not set")
    return value
