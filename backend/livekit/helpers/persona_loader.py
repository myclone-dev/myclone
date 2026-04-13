"""
Persona Data Loader - Handles loading persona data from database

This module provides database-based persona loading functionality.
Used as a fallback when metadata is not available from the orchestrator.
"""

import logging
import os
import sys
from typing import Any, Dict, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from sqlalchemy import select

from shared.database.models.database import Pattern, PersonaPrompt, async_session_maker
from shared.database.repositories.persona_repository import PersonaRepository
from shared.schemas.livekit import PersonaPromptMetadata

logger = logging.getLogger(__name__)


class PersonaDataLoader:
    """Handles persona data loading from database

    This class encapsulates all database queries needed to load
    persona information, patterns, and prompts.

    Usage:
        loader = PersonaDataLoader(expert_username="janesmith")
        persona_info, patterns, prompt = await loader.load_all()
    """

    def __init__(self, expert_username: str, persona_name: str = "default"):
        """Initialize loader with username

        Args:
            expert_username: Username of the user (User.username)
            persona_name: Name of the persona (defaults to "default")
        """
        self.persona_username = expert_username
        self.persona_name = persona_name
        self.persona_prompt = None
        self.persona_info = {}
        self.patterns_info = {}
        self._persona_loaded = False
        self._persona_loaded_prompt = False

    async def get_persona(self) -> Dict[str, Any]:
        """Load persona information from database

        Returns:
            Dict containing persona fields: id, name, role, company, description, voice_id
            Note: role and company are queried from linkedin_experiences (is_current=true)

        Raises:
            ValueError: If persona not found in database
        """
        async with async_session_maker() as session:
            persona = await PersonaRepository.get_by_username_and_persona(
                session, self.persona_username, self.persona_name
            )

            if not persona:
                logger.error(
                    f"❌ Persona not found in database: {self.persona_username} (persona: {self.persona_name})"
                )
                raise ValueError(
                    f"Persona not found: {self.persona_username} (persona: {self.persona_name})"
                )

            # LinkedIn repository removed; role/company come from user/persona fields only
            role, company = None, None

            self._persona_loaded = True
            self.persona_info = {
                "id": str(persona.id),
                "name": persona.name,
                "user_fullname": persona.user.fullname if persona.user else None,
                "role": role or "Expert",  # Fallback if no current job
                "company": company or "Independent",  # Fallback if no current job
                "description": persona.description or "A knowledgeable expert",
                "voice_id": persona.voice_id,
                "language": persona.language or "auto",  # Default to auto if NULL
            }

            return self.persona_info

    async def get_persona_prompt(self) -> Optional[PersonaPrompt]:
        """Retrieve persona prompt configuration from database

        Loads the PersonaPrompt associated with this persona's ID.
        Falls back gracefully if no prompt exists in the database.

        Returns:
            PersonaPrompt: The persona prompt object if found
            None: If no prompt exists for this persona

        Raises:
            ValueError: If persona has not been loaded yet
        """
        if not self._persona_loaded:
            await self.get_persona()

        if not self.persona_info.get("id"):
            raise ValueError(f"Persona not found: {self.persona_username}")

        try:
            from shared.utils.conversions import str_to_uuid

            persona_id = str_to_uuid(self.persona_info["id"])

            async with async_session_maker() as session:
                stmt = select(PersonaPrompt).where(
                    PersonaPrompt.persona_id == persona_id, PersonaPrompt.is_active == True
                )
                result = await session.execute(stmt)
                persona_prompt = result.scalar_one_or_none()

                if not persona_prompt:
                    logger.info(f"ℹ️ No persona prompt found for persona_id: {persona_id}")
                    self.persona_prompt = None
                else:
                    self._persona_loaded_prompt = True
                    self.persona_prompt = persona_prompt

        except Exception as e:
            logger.error(f"Error getting persona prompt: {e}")
            self.persona_prompt = None

        return self.persona_prompt

    async def get_patterns(self) -> Dict[str, Any]:
        """Load behavior patterns for the persona

        Returns:
            Dict mapping pattern_type to pattern_data

        Raises:
            ValueError: If persona has not been loaded yet
        """
        if not self._persona_loaded:
            await self.get_persona()

        if not self.persona_info.get("id"):
            raise ValueError(f"Persona not found: {self.persona_username}")

        persona_id = self.persona_info["id"]

        try:
            async with async_session_maker() as session:
                stmt = select(Pattern).where(Pattern.persona_id == persona_id)
                result = await session.execute(stmt)
                patterns = result.scalars().all()

                for pattern in patterns:
                    self.patterns_info[pattern.pattern_type] = pattern.pattern_data

                return self.patterns_info

        except Exception as e:
            logger.error(f"Error getting patterns: {e}")
            return {}

    async def load_all(
        self,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Optional[PersonaPromptMetadata]]:
        """Load all persona data in one call

        Convenience method that loads persona info, patterns, and prompt
        in sequence with a single method call.

        Returns:
            Tuple of (persona_info_dict, patterns_dict, persona_prompt_pydantic)
        """
        persona_info = await self.get_persona()
        patterns_info = await self.get_patterns()
        persona_prompt_orm = await self.get_persona_prompt()

        persona_prompt_pydantic = None
        if persona_prompt_orm:
            persona_prompt_pydantic = PersonaPromptMetadata.model_validate(persona_prompt_orm)

        logger.info(f"✅ Loaded all data for persona: {self.persona_username}")
        logger.info(f"   - Name: {persona_info.get('name')}")
        logger.info(f"   - Patterns: {len(patterns_info)} types")
        logger.info(f"   - Prompt: {'Yes' if persona_prompt_pydantic else 'No'}")

        return persona_info, patterns_info, persona_prompt_pydantic
