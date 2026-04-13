"""
LiveKit Agent Constants

Contains tool docstrings and other constants used by the agent.
"""

from .tool_docstrings import (
    CONFIRM_LEAD_CAPTURE_DOC,
    FETCH_URL_DOC,
    GENERATE_CONTENT_DOC,
    SEARCH_INTERNET_DOC,
    SEND_CALENDAR_LINK_DOC,
    START_ASSESSMENT_DOC,
    SUBMIT_WORKFLOW_ANSWER_DOC,
    UPDATE_LEAD_FIELD_DOC,
    build_update_lead_field_doc,
)

__all__ = [
    "START_ASSESSMENT_DOC",
    "UPDATE_LEAD_FIELD_DOC",
    "CONFIRM_LEAD_CAPTURE_DOC",
    "SUBMIT_WORKFLOW_ANSWER_DOC",
    "SEARCH_INTERNET_DOC",
    "FETCH_URL_DOC",
    "SEND_CALENDAR_LINK_DOC",
    "GENERATE_CONTENT_DOC",
    "build_update_lead_field_doc",
]
