"""
Agent Status Publishing Utility

Shared helper for publishing agent status events to the frontend via data channel.
Used by ToolHandler, ContentHandler, and any handler that needs to show
loading/status indicators on the frontend.
"""

import json
import logging

logger = logging.getLogger(__name__)


async def publish_agent_status(room, status: str, message: str = "") -> None:
    """Publish agent status event to frontend via data channel.

    Args:
        room: LiveKit room instance (must have local_participant.publish_data)
        status: Status key (e.g. "searching", "writing", "fetching", "idle")
        message: Optional human-readable message (e.g. "Writing your blog...")
    """
    try:
        payload = {"type": "agent_status", "status": status}
        if message:
            payload["message"] = message
        await room.local_participant.publish_data(
            payload=json.dumps(payload).encode("utf-8"),
            topic="agent_status",
            reliable=True,
        )
    except Exception as e:
        logger.warning(f"⚠️ Failed to publish agent status: {e}")
