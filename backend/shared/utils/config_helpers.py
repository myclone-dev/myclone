"""
Configuration helper utilities for processing environment variables.
"""

import json


def extract_from_json_or_plain(value: str, json_key: str) -> str:
    """
    Generic helper to extract value from JSON format or plain text.

    Handles two scenarios:
    - AWS Production: ENV_VAR={"KEY":"value"} (from Secrets Manager)
    - Local Dev: ENV_VAR=value (plain text from .env)

    Args:
        value: Raw value from environment variable
        json_key: Key to extract from JSON (if value is JSON)

    Returns:
        Extracted and stripped value

    Example:
        # AWS: ENCRYPTION_KEY={"ENCRYPTION_KEY":"abc123"}
        extract_from_json_or_plain('{"ENCRYPTION_KEY":"abc123"}', "ENCRYPTION_KEY")
        # Returns: "abc123"

        # Local: ENCRYPTION_KEY=abc123
        extract_from_json_or_plain('abc123', "ENCRYPTION_KEY")
        # Returns: "abc123"
    """
    if not value:
        return ""

    # If it looks like JSON, try to parse and extract
    if value.strip().startswith("{"):
        try:
            secret_data = json.loads(value)
            if isinstance(secret_data, dict) and json_key in secret_data:
                return str(secret_data[json_key]).strip()
        except (json.JSONDecodeError, ValueError):
            # Not valid JSON, fall through to plain text
            pass

    # Plain text format (local dev) or JSON parse failed
    return value.strip()
