"""UUID conversion utilities"""

from typing import Optional, Union
from uuid import UUID


def str_to_uuid(value: Union[str, UUID]) -> UUID:
    """
    Convert a string to UUID object.

    Args:
        value: String representation of UUID or UUID object

    Returns:
        UUID object

    Raises:
        ValueError: If string is not a valid UUID format
    """
    if isinstance(value, UUID):
        return value
    return UUID(value)


def uuid_to_str(value: Union[str, UUID]) -> str:
    """
    Convert UUID object to string.

    Args:
        value: UUID object or string representation

    Returns:
        String representation of UUID
    """
    if isinstance(value, str):
        return value
    return str(value)


def safe_str_to_uuid(value: Union[str, UUID, None]) -> Optional[UUID]:
    """
    Safely convert a string to UUID object, returning None on failure.

    This is useful when you need fault-tolerant UUID conversion that won't
    raise exceptions for invalid input.

    Args:
        value: String representation of UUID, UUID object, or None

    Returns:
        UUID object or None if conversion fails
    """
    if value is None:
        return None

    try:
        return str_to_uuid(value)
    except (ValueError, TypeError):
        return None
