"""
Shared constants for the application.
"""

# LiveKit constants (used in voice_session_orchestrator.py)
from .livekit_constants import RECORDING_ALLOWED_USER_IDS, is_recording_allowed_for_user

# Only export what's actually being imported in the codebase
# Source type constants (used in ingestion_routes.py)
from .source_constants import (
    ALL_SOURCE_TYPES,
    SOURCE_TYPE_LINKEDIN,
    SOURCE_TYPE_PDF,
    SOURCE_TYPE_TWITTER,
    SOURCE_TYPE_WEBSITE,
)

__all__ = [
    # Source type constants (ingestion_routes.py)
    "ALL_SOURCE_TYPES",
    "SOURCE_TYPE_LINKEDIN",
    "SOURCE_TYPE_PDF",
    "SOURCE_TYPE_TWITTER",
    "SOURCE_TYPE_WEBSITE",
    # LiveKit constants (voice_session_orchestrator.py)
    "RECORDING_ALLOWED_USER_IDS",
    "is_recording_allowed_for_user",
]
