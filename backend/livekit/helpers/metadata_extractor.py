"""
Metadata Extraction - Helper functions for extracting data from LiveKit contexts

This module provides utilities to extract persona metadata and user information
from LiveKit job contexts and room participants.
"""

import json
import logging
import os
import sys
from typing import Any, Dict, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from livekit.agents import JobContext
from shared.schemas.livekit import LiveKitDispatchMetadata, PersonaPromptMetadata

logger = logging.getLogger(__name__)


def extract_persona_metadata_from_job(
    ctx: JobContext,
) -> Optional[LiveKitDispatchMetadata]:
    """Extract persona metadata from LiveKit job context

    This is the NEW approach - metadata is passed from the orchestrator,
    so we don't need to query the database.

    The orchestrator loads all persona data (info, patterns, prompts) from
    the database and serializes it as JSON in the dispatch metadata.
    This function deserializes that metadata back into a Pydantic model.

    Args:
        ctx: LiveKit job context containing dispatch metadata

    Returns:
        LiveKitDispatchMetadata if found and valid, None otherwise

    Example:
        metadata = extract_persona_metadata_from_job(ctx)
        if metadata:
            persona_name = metadata.persona_data.name
            patterns = metadata.patterns
    """
    try:
        # LiveKit stores dispatch metadata in ctx.job.metadata
        if hasattr(ctx, "job") and hasattr(ctx.job, "metadata") and ctx.job.metadata:
            metadata_json = ctx.job.metadata
            logger.info(f"📦 Found metadata in job context ({len(metadata_json)} bytes)")

            metadata = LiveKitDispatchMetadata.model_validate_json(metadata_json)

            logger.info("✅ Successfully parsed persona metadata from job")
            logger.info(
                f"   - Persona: {metadata.persona_data.name} ({metadata.persona_data.username})"
            )
            logger.info(f"   - Patterns: {len(metadata.patterns)} types")
            logger.info(f"   - Prompt: {'Yes' if metadata.persona_prompt else 'No'}")

            return metadata

    except Exception as e:
        logger.warning(f"⚠️ Failed to extract metadata from job: {e}")

    return None


def extract_user_info_from_room(room) -> Tuple[str, Optional[str]]:
    """Extract username and session_token from room participants

    Uses multiple fallback methods to ensure username can be extracted:
    1. Participant metadata (primary method)
    2. Room name parsing (fallback 1)
    3. Environment variable (fallback 2)

    Args:
        room: LiveKit Room object containing participant information

    Returns:
        Tuple of (expert_username, session_token)
        session_token may be None if not provided

    Raises:
        ValueError: If username cannot be extracted from any source

    Example:
        username, token = extract_user_info_from_room(ctx.room)
    """
    expert_username = None
    session_token = None

    # Method 1: Extract from participant metadata (primary)
    if room.remote_participants:
        for participant_id, participant in room.remote_participants.items():
            if participant.metadata:
                try:
                    metadata = json.loads(participant.metadata)

                    # Get username from metadata
                    if not expert_username:
                        expert_username = metadata.get("expert_username")
                        if expert_username:
                            logger.info(
                                f"✅ Found username in participant metadata: {expert_username}"
                            )

                    # Get session token from metadata
                    if not session_token:
                        session_token = metadata.get("session_token")
                        if session_token:
                            logger.info(f"🎫 Found session token: {session_token[:8]}...")

                except json.JSONDecodeError:
                    continue

    # Method 2: Fallback to room name parsing
    if not expert_username:
        try:
            room_parts = room.name.split("_")
            if len(room_parts) >= 3 and room_parts[0] == "voice" and room_parts[1] == "assistant":
                expert_username = room_parts[2]
                logger.info(f"🏷️ Fallback: extracted username from room name: {expert_username}")
            else:
                logger.warning(f"⚠️ Room name format unexpected: {room.name}")
        except Exception as e:
            logger.error(f"❌ Failed to parse room name: {e}")

    # Method 3: Final fallback to environment variable
    if not expert_username:
        expert_username = os.getenv("USERNAME")
        if not expert_username:
            logger.error(
                "❌ Cannot determine username: no metadata, room parsing failed, and no USERNAME env var set"
            )
            raise ValueError("Unable to extract username from any source")
        logger.warning(f"⚙️ Final fallback: using environment username: {expert_username}")

    return expert_username, session_token


def convert_metadata_to_agent_format(
    metadata: LiveKitDispatchMetadata,
) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[PersonaPromptMetadata]]:
    """Convert Pydantic metadata models to format expected by ModularPersonaAgent

    Args:
        metadata: LiveKitDispatchMetadata from orchestrator

    Returns:
        Tuple of (persona_info_dict, patterns_dict, persona_prompt_pydantic)
    """
    persona_info = {
        "id": metadata.persona_data.id,
        "name": metadata.persona_data.name,
        "user_fullname": metadata.persona_data.user_fullname,
        "role": metadata.persona_data.role,
        "company": metadata.persona_data.company,
        "description": metadata.persona_data.description,
        "voice_id": metadata.persona_data.voice_id,
        "language": metadata.persona_data.language or "auto",  # Default to auto if None
        "greeting_message": metadata.persona_data.greeting_message,
        "suggested_questions": metadata.suggested_questions,
    }

    patterns_dict = metadata.patterns
    persona_prompt = metadata.persona_prompt

    return persona_info, patterns_dict, persona_prompt
