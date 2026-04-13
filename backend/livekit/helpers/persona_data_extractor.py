"""
Persona Data Extractor - Unified persona data loading with metadata-first strategy

This module provides a high-level interface for extracting persona data,
automatically choosing the optimal strategy:
1. Use metadata from orchestrator (fast, no DB query)
2. Fall back to database loading if metadata not available

This abstraction simplifies the agent entrypoint and centralizes the loading logic.
"""

import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from livekit.agents import JobContext
from livekit.helpers.metadata_extractor import (
    convert_metadata_to_agent_format,
    extract_persona_metadata_from_job,
    extract_user_info_from_room,
)
from livekit.helpers.persona_loader import PersonaDataLoader
from shared.database.models.database import async_session_maker
from shared.database.repositories.workflow_repository import WorkflowRepository

logger = logging.getLogger(__name__)


async def fetch_tts_platform(voice_id: Optional[str]) -> Optional[str]:
    """
    Fetch the TTS platform for a given voice_id from voice_clone table.
    Returns 'elevenlabs', 'cartesia', or None if not found.
    """
    if not voice_id:
        logger.warning("⚠️ No voice_id provided to fetch_tts_platform, returning None")
        return None

    try:
        from sqlalchemy import select

        from shared.database.models.database import async_session_maker
        from shared.database.models.voice_clone import VoiceClone

        logger.info(f"🔍 Querying voice_clone table for voice_id: {voice_id}")

        async with async_session_maker() as db_session:
            stmt = select(VoiceClone.platform).where(VoiceClone.voice_id == voice_id)
            result = await db_session.execute(stmt)
            platform = result.scalar_one_or_none()

            if platform:
                logger.info(f"✅ Found TTS platform for voice_id '{voice_id}': {platform}")
            else:
                logger.warning(
                    f"⚠️ No platform found in voice_clone table for voice_id '{voice_id}'"
                )
                logger.warning("   This voice_id may not exist in the database or platform is NULL")

            return platform

    except Exception as e:
        logger.error(
            f"❌ Failed to fetch TTS platform for voice_id '{voice_id}': {e}", exc_info=True
        )
        return None


@dataclass
class PersonaDataResult:
    """Result of persona data extraction

    Contains all data needed to initialize a ModularPersonaAgent.
    """

    expert_username: str
    session_token: Optional[str]
    persona_info: Dict[str, Any]
    pattern_info: Dict[str, Any]
    persona_prompt: Optional[Any]  # Can be PersonaPrompt ORM object or namespace
    email_capture_settings: Dict[str, Any]  # Email capture configuration from persona
    calendar_config: Dict[str, Any]  # Calendar configuration from persona
    workflow_data: Optional[Dict[str, Any]]  # Active workflow data for this persona
    default_capture_enabled: bool  # Whether default lead capture (name/email/phone) is active
    content_mode_enabled: bool  # Whether content creation mode is enabled
    tts_platform: Optional[str]  # TTS platform ('elevenlabs', 'cartesia', or None)
    loaded_from_metadata: bool  # True if from metadata, False if from DB


async def extract_persona_data(ctx: JobContext) -> PersonaDataResult:
    """Extract persona data using metadata-first strategy with DB fallback

    This function encapsulates the entire persona data loading logic:
    1. First, try to extract persona data from job metadata (orchestrator passes this)
    2. If metadata not available, fall back to database query

    This is the recommended way to load persona data in the agent entrypoint.

    Args:
        ctx: LiveKit job context containing potential metadata and room info

    Returns:
        PersonaResolutionResult containing all persona data and metadata

    Example:
        async def entrypoint(ctx: JobContext):
            # Simple one-liner to get all persona data
            result = await extract_persona_data(ctx)

            # Create agent with extracted data
            agent = ModularPersonaAgent(
                result.expert_username,
                result.persona_info,
                result.persona_prompt,
                result.pattern_info,
                ctx.room.name,
                ctx.room,
                result.session_token,
                ctx.proc.userdata["vad"],
                result.email_capture_settings,
            )
    """

    # Strategy 1: Try to use metadata from orchestrator (PREFERRED)
    dispatch_metadata = extract_persona_metadata_from_job(ctx)

    if dispatch_metadata:
        # ✅ Use metadata from orchestrator (NO DATABASE QUERY!)
        logger.info("🚀 Using persona data from dispatch metadata (no DB query)")

        expert_username = dispatch_metadata.persona_data.username
        session_token = dispatch_metadata.session_token

        # Convert Pydantic models to agent-compatible format
        persona_info, pattern_info, persona_prompt = convert_metadata_to_agent_format(
            dispatch_metadata
        )

        # Extract email capture settings from metadata
        email_capture_settings = {
            "enabled": dispatch_metadata.email_capture_enabled,
            "threshold": dispatch_metadata.email_capture_message_threshold,
            "require_fullname": dispatch_metadata.email_capture_require_fullname,
            "require_phone": dispatch_metadata.email_capture_require_phone,
            "completed": dispatch_metadata.email_capture_completed,
        }

        # Extract calendar settings from metadata
        calendar_config = {
            "enabled": dispatch_metadata.calendar_enabled,
            "url": dispatch_metadata.calendar_url,
            "display_name": dispatch_metadata.calendar_display_name,
        }

        logger.info(
            f"✅ [{expert_username}] Extracted from metadata: {persona_info.get('name', 'Unknown')}"
        )
        logger.info(
            f"📧 Email capture: {'enabled' if email_capture_settings['enabled'] else 'disabled'} (threshold: {email_capture_settings['threshold']}, completed: {email_capture_settings['completed']})"
        )
        logger.info(
            f"📅 Calendar: {'enabled' if calendar_config['enabled'] else 'disabled'} (url: {calendar_config['url'] or 'none'})"
        )

        # Extract workflow data from metadata (orchestrator passes this now)
        workflow_data = None
        if dispatch_metadata.workflow_id:
            workflow_data = {
                "workflow_id": dispatch_metadata.workflow_id,
                "title": dispatch_metadata.workflow_title,
                "workflow_type": dispatch_metadata.workflow_type,
                "opening_message": dispatch_metadata.workflow_opening_message,
                "workflow_objective": getattr(dispatch_metadata, "workflow_objective", None),
                "trigger_config": getattr(dispatch_metadata, "workflow_trigger_config", None),
                "result_config": dispatch_metadata.workflow_result_config,
            }

            # Add generic config fields (apply to any workflow type)
            agent_instructions = getattr(dispatch_metadata, "workflow_agent_instructions", None)
            if agent_instructions:
                workflow_data["agent_instructions"] = agent_instructions

            reference_data = getattr(dispatch_metadata, "workflow_reference_data", None)
            if reference_data:
                workflow_data["reference_data"] = reference_data

            response_mode = getattr(dispatch_metadata, "workflow_response_mode", None)
            if response_mode:
                workflow_data["response_mode"] = response_mode

            # Add type-specific configuration
            if dispatch_metadata.workflow_type == "conversational":
                # Conversational workflows: Extract field definitions (when orchestrator passes them)
                workflow_data.update(
                    {
                        "required_fields": getattr(
                            dispatch_metadata, "workflow_required_fields", []
                        ),
                        "optional_fields": getattr(
                            dispatch_metadata, "workflow_optional_fields", []
                        ),
                        "extraction_strategy": getattr(
                            dispatch_metadata, "workflow_extraction_strategy", {}
                        ),
                        "output_template": getattr(
                            dispatch_metadata, "workflow_output_template", {}
                        ),
                    }
                )
                logger.info(
                    f"📋 Extracted conversational workflow from metadata: {dispatch_metadata.workflow_title} "
                    f"({len(workflow_data.get('required_fields', []))} required fields, "
                    f"{len(workflow_data.get('optional_fields', []))} optional fields)"
                )
            else:
                # Linear workflows (simple/scored): Use steps array
                workflow_data["steps"] = dispatch_metadata.workflow_steps
                logger.info(
                    f"📋 Extracted linear workflow from metadata: {dispatch_metadata.workflow_title} "
                    f"({dispatch_metadata.workflow_type}, {len(dispatch_metadata.workflow_steps or [])} steps)"
                )

        # Fetch TTS platform based on voice_id
        voice_id = persona_info.get("voice_id")
        tts_platform = await fetch_tts_platform(voice_id) if voice_id else None

        return PersonaDataResult(
            expert_username=expert_username,
            session_token=session_token,
            persona_info=persona_info,
            pattern_info=pattern_info,
            persona_prompt=persona_prompt,
            email_capture_settings=email_capture_settings,
            calendar_config=calendar_config,
            workflow_data=workflow_data,
            default_capture_enabled=dispatch_metadata.default_capture_enabled,
            content_mode_enabled=dispatch_metadata.content_mode_enabled,
            tts_platform=tts_platform,
            loaded_from_metadata=True,
        )

    # Strategy 2: Fallback to database query (LEGACY)
    logger.warning("⚠️ No metadata in job context, falling back to database query")
    logger.warning("   This is slower and indicates the orchestrator didn't pass metadata")

    # Extract username and session_token using fallback methods
    expert_username, session_token = extract_user_info_from_room(ctx.room)

    logger.info(f"🚀 [{expert_username}] Session started in room: {ctx.room.name}")

    # Load persona and behavior patterns from database
    loader = PersonaDataLoader(expert_username=expert_username)
    persona_info, pattern_info, persona_prompt = await loader.load_all()

    logger.info(f"🎭 [{expert_username}] Extracted from DB: {persona_info.get('name', 'Unknown')}")

    # For DB fallback, provide default email capture settings (disabled)
    email_capture_settings = {
        "enabled": False,
        "threshold": 5,
        "require_fullname": True,
        "require_phone": False,
        "completed": False,
    }

    # For DB fallback, provide default calendar settings (disabled)
    calendar_config = {
        "enabled": False,
        "url": None,
        "display_name": None,
    }

    # Load active workflow for this persona (if exists)
    workflow_data = await _load_active_workflow(persona_info.get("id"))

    # Fetch TTS platform based on voice_id
    voice_id = persona_info.get("voice_id")
    tts_platform = await fetch_tts_platform(voice_id) if voice_id else None

    # In DB fallback, compute default_capture_enabled locally
    # (same logic as orchestrator: disabled if conversational workflow, email capture popup, or authenticated user)
    # NOTE: DB fallback doesn't have authenticated_user_id — cannot check auth status here.
    # This is acceptable since DB fallback is a legacy path rarely used.
    default_capture_enabled = True
    if workflow_data and workflow_data.get("workflow_type") == "conversational":
        default_capture_enabled = False
    if email_capture_settings.get("enabled"):
        default_capture_enabled = False

    return PersonaDataResult(
        expert_username=expert_username,
        session_token=session_token,
        persona_info=persona_info,
        pattern_info=pattern_info,
        persona_prompt=persona_prompt,
        email_capture_settings=email_capture_settings,
        calendar_config=calendar_config,
        workflow_data=workflow_data,
        default_capture_enabled=default_capture_enabled,
        content_mode_enabled=False,
        tts_platform=tts_platform,
        loaded_from_metadata=False,
    )


async def _load_active_workflow(persona_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Load active (published) workflow for a persona from database.

    Supports both linear workflows (simple/scored) and conversational workflows:
    - Linear workflows: Use "steps" array for step-by-step Q&A
    - Conversational workflows: Use field definitions for organic extraction

    Args:
        persona_id: UUID string of the persona

    Returns:
        Dictionary with workflow data or None if no active workflow exists
    """
    if not persona_id:
        return None

    try:
        async with async_session_maker() as session:
            workflow_repo = WorkflowRepository(session)

            # Get active workflows for this persona
            workflows = await workflow_repo.get_workflows_by_persona(
                persona_id=UUID(persona_id), active_only=True, limit=1
            )

            if not workflows:
                logger.info(f"📋 No active workflow found for persona {persona_id}")
                return None

            workflow = workflows[0]
            logger.info(
                f"📋 Loaded active workflow: {workflow.title} (ID: {workflow.id}, Type: {workflow.workflow_type})"
            )

            # Build base workflow data
            workflow_data = {
                "workflow_id": str(workflow.id),
                "title": workflow.title,
                "workflow_type": workflow.workflow_type,
                "opening_message": workflow.opening_message,
                "workflow_objective": workflow.workflow_objective,
                "trigger_config": workflow.trigger_config,
                "result_config": workflow.result_config or {},
            }

            # Extract generic config fields (apply to any workflow type)
            if workflow.workflow_config:
                agent_instructions = workflow.workflow_config.get("agent_instructions")
                if agent_instructions:
                    workflow_data["agent_instructions"] = agent_instructions
                    logger.info(
                        f"📋 Extracted agent_instructions from config ({len(agent_instructions)} chars)"
                    )

                reference_data = workflow.workflow_config.get("reference_data")
                if reference_data:
                    workflow_data["reference_data"] = reference_data
                    logger.info(
                        f"📋 Extracted reference_data from config ({len(reference_data)} chars)"
                    )

                response_mode = workflow.workflow_config.get("response_mode")
                if response_mode:
                    workflow_data["response_mode"] = response_mode
                    logger.info(f"📋 Extracted response_mode from config: {response_mode}")

            # Add type-specific configuration
            if workflow.workflow_type == "conversational":
                # Conversational workflows: Extract field definitions and strategy
                workflow_data.update(
                    {
                        "required_fields": workflow.workflow_config.get("required_fields", []),
                        "optional_fields": workflow.workflow_config.get("optional_fields", []),
                        "extraction_strategy": workflow.workflow_config.get(
                            "extraction_strategy", {}
                        ),
                        "output_template": workflow.output_template or {},
                    }
                )
                logger.info(
                    f"📋 Conversational workflow: {len(workflow_data['required_fields'])} required fields, "
                    f"{len(workflow_data['optional_fields'])} optional fields"
                )
            else:
                # Linear workflows (simple/scored): Use steps array
                workflow_data["steps"] = workflow.workflow_config.get("steps", [])
                logger.info(f"📋 Linear workflow: {len(workflow_data['steps'])} steps")

            return workflow_data

    except Exception as e:
        logger.error(f"❌ Failed to load workflow for persona {persona_id}: {e}", exc_info=True)
        return None
