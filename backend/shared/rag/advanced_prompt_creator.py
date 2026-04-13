"""
Advanced Prompt Creation System

This module provides comprehensive persona prompt generation capabilities by analyzing
various data sources (LinkedIn, Twitter, YouTube transcripts) to create detailed
persona introductions, expertise areas, communication styles, and example responses.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.openai_service import OpenAIModelService
from app.services.persona_prompt_history_service import PersonaPromptHistoryService
from app.services.prompt_defaults_service import PromptDefaultsService
from shared.config import settings
from shared.database.models.database import Persona, PersonaPrompt
from shared.database.models.embeddings import VoyageLiteEmbedding
from shared.database.models.persona_data_source import PersonaDataSource
from shared.monitoring.sentry_utils import capture_exception_with_context

logger = logging.getLogger(__name__)


def smart_truncate(text: str, max_length: int, warn_on_truncate: bool = True) -> str:
    """
    Truncate text at sentence boundary to avoid cutting mid-sentence.

    Args:
        text: Text to truncate
        max_length: Maximum character length
        warn_on_truncate: Whether to log a warning when truncation occurs

    Returns:
        Truncated text, preferably at a sentence boundary
    """
    if len(text) <= max_length:
        return text

    # Truncate to max length first
    truncated = text[:max_length]

    # Try to find the last sentence boundary (period followed by space or end)
    last_period = truncated.rfind(". ")

    # Only use sentence boundary if it's reasonably close to the limit (within 20%)
    if last_period > max_length * 0.8:
        result = truncated[: last_period + 1]
    else:
        # If no good sentence boundary, try other punctuation
        last_punct = max(
            truncated.rfind("! "),
            truncated.rfind("? "),
            truncated.rfind(".\n"),
        )
        if last_punct > max_length * 0.8:
            result = truncated[: last_punct + 1]
        else:
            # Last resort: truncate and add ellipsis (ensuring we stay within max_length)
            if max_length > 3:
                result = truncated[: max_length - 3].rstrip() + "..."
            else:
                result = truncated

    if warn_on_truncate:
        chars_lost = len(text) - len(result)
        logger.warning(
            f"Content truncated: {chars_lost} characters lost "
            f"({len(text)} -> {len(result)}). "
            f"Original length exceeded {max_length} character limit."
        )

    return result


@dataclass
class PersonaInfo:
    """Container for basic persona information"""

    name: str
    role: Optional[str]
    description: Optional[str]
    linkedin_info: Optional[str]


@dataclass
class ExpertiseArea:
    """Container for expertise classification"""

    primary: List[str]
    secondary: List[str]


@dataclass
class CommunicationStyle:
    """Container for communication and writing style analysis"""

    thinking_style: str
    speaking_style: str
    writing_style: str
    catch_phrases: List[str]
    transition_words: List[str]
    tone_characteristics: List[str]


@dataclass
class AdvancedPromptResult:
    """Complete result of advanced prompt creation"""

    introduction: str
    expertise: ExpertiseArea
    communication_style: CommunicationStyle
    example_responses: List[Dict[str, str]]
    raw_data_summary: Dict[str, int]


class AdvancedPromptCreator:
    """
    Advanced prompt creation system that analyzes persona data sources
    to generate comprehensive persona prompts using OpenAI GPT models.

    Follows Pattern 2: Stateful Services (Instance Methods) from CLAUDE.md
    - Maintains state (API key, OpenAI service, logger)
    - Initializes dependencies once in __init__
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Advanced Prompt Creator.

        Args:
            api_key: OpenAI API key. If not provided, uses settings.openai_api_key
        """
        # Initialize state - following CLAUDE.md Pattern 2
        self.api_key = api_key or settings.openai_api_key
        self.logger = logging.getLogger(__name__)
        self.openai_service = OpenAIModelService(api_key=self.api_key)

        # Configure service once during initialization
        if hasattr(self.openai_service, "set_model"):
            self.openai_service.set_model("gpt-4o-mini")
        if hasattr(self.openai_service, "set_temperature"):
            self.openai_service.set_temperature(0.4)  # Lower temp for more consistent prompts
        if hasattr(self.openai_service, "set_max_tokens"):
            self.openai_service.set_max_tokens(2000)

    async def create_advanced_prompt(
        self,
        db: AsyncSession,
        persona_id: UUID,
        sample_questions: Optional[List[str]] = None,
        user_id: Optional[UUID] = None,
    ) -> AdvancedPromptResult:
        """
        Create a comprehensive advanced prompt for a persona.

        Args:
            db: Database session
            persona_id: UUID of the persona
            sample_questions: Optional list of questions for example responses
            user_id: Optional UUID of the user (for ownership validation)

        Returns:
            AdvancedPromptResult containing all generated components

        Raises:
            ValueError: If persona not found, insufficient data, or unauthorized access
            Exception: For OpenAI API or processing errors
        """
        self.logger.info(f"Starting advanced prompt creation for persona {persona_id}")

        # Step 1: Generate each component using the updated methods
        self.logger.info("Generating persona introduction...")
        introduction = await self._generate_introduction(db, persona_id, user_id, db_update=False)

        self.logger.info("Analyzing area of expertise...")
        expertise = await self._analyze_expertise(db, persona_id, user_id, db_update=False)

        self.logger.info("Analyzing communication style...")
        communication_style = await self._analyze_communication_style(
            db, persona_id, user_id, db_update=False
        )

        self.logger.info("Generating example responses...")
        example_responses = await self._generate_example_responses(
            db,
            persona_id,
            expertise,
            communication_style,
            sample_questions or self._get_default_questions(),
            user_id,
            db_update=False,
        )

        # Step 2: Compile results
        result = AdvancedPromptResult(
            introduction=introduction,
            expertise=expertise,
            communication_style=communication_style,
            example_responses=example_responses,
            raw_data_summary={
                "linkedin": 1,
                "twitter": 1,
                "website": 1,
                "documents": 1,
            },
        )

        self.logger.info(f"Advanced prompt creation completed for persona {persona_id}")
        return result

    async def _fetch_persona_info(
        self, db: AsyncSession, persona_id: UUID, user_id: Optional[UUID] = None
    ) -> Optional[PersonaInfo]:
        """Fetch basic persona information from database with optional user ownership validation."""
        try:
            # Build query with user_id validation if provided
            if user_id is not None:
                stmt = select(Persona).where(
                    Persona.id == persona_id,
                    Persona.user_id == user_id,  # Security: validate ownership
                )
            else:
                stmt = select(Persona).where(Persona.id == persona_id)

            result = await db.execute(stmt)
            persona = result.scalar_one_or_none()

            if not persona:
                return None

            return PersonaInfo(
                name=persona.name or "Unknown",
                role=getattr(persona, "role", None),  # Use getattr since role may not exist
                description=persona.description,
                linkedin_info=getattr(persona, "linkedin_info", None),
            )
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"persona_id": str(persona_id)},
                tags={"component": "advanced_prompt_creator", "operation": "fetch_persona_info"},
            )
            self.logger.error(f"Error fetching persona info: {e}")
            return None

    async def _fetch_persona_data_sources(
        self, db: AsyncSession, persona_id: UUID
    ) -> List[Dict[str, Any]]:
        """Fetch all data sources associated with the persona."""
        try:
            stmt = select(PersonaDataSource).where(PersonaDataSource.persona_id == persona_id)
            result = await db.execute(stmt)
            data_sources = result.scalars().all()

            return [
                {
                    "id": ds.id,
                    "source_record_id": ds.source_record_id,
                    "source_type": ds.source_type,
                    "metadata": ds.metadata or {},
                }
                for ds in data_sources
            ]
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"persona_id": str(persona_id)},
                tags={
                    "component": "advanced_prompt_creator",
                    "operation": "fetch_persona_data_sources",
                },
            )
            self.logger.error(f"Error fetching persona data sources: {e}")
            return []

    async def _fetch_content_by_source_type(
        self, db: AsyncSession, data_sources: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Fetch and categorize content by source type."""
        content_by_type = {"linkedin": [], "twitter": [], "youtube": [], "other": []}

        try:
            # Extract source_record_ids
            source_record_ids = [ds["source_record_id"] for ds in data_sources]

            if not source_record_ids:
                return content_by_type

            # Fetch embeddings content
            stmt = select(VoyageLiteEmbedding).where(
                VoyageLiteEmbedding.source_record_id.in_(source_record_ids)
            )
            result = await db.execute(stmt)
            embeddings = result.scalars().all()

            # Create mapping of source_record_id to source_type
            source_type_mapping = {
                ds["source_record_id"]: ds["source_type"].lower() for ds in data_sources
            }

            # Categorize content by source type
            for embedding in embeddings:
                text = embedding.text or ""
                if len(text.strip()) < 10:  # Skip very short texts
                    continue

                source_type = source_type_mapping.get(embedding.source_record_id, "other")

                # Map source types to our categories
                if "linkedin" in source_type:
                    content_by_type["linkedin"].append(text)
                elif "twitter" in source_type or "tweet" in source_type:
                    content_by_type["twitter"].append(text)
                elif "youtube" in source_type or "video" in source_type:
                    content_by_type["youtube"].append(text)
                else:
                    content_by_type["other"].append(text)

            self.logger.info(
                f"Content categorized: {[(k, len(v)) for k, v in content_by_type.items()]}"
            )
            return content_by_type

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"data_sources_count": len(data_sources)},
                tags={
                    "component": "advanced_prompt_creator",
                    "operation": "fetch_content_by_source_type",
                },
            )
            self.logger.error(f"Error fetching content by source type: {e}")
            return content_by_type

    async def _generate_introduction(
        self,
        db: AsyncSession,
        persona_id: UUID,
        user_id: Optional[UUID] = None,
        db_update: bool = False,
    ) -> str:
        """
        Generate persona introduction using LinkedIn basic info and experiences.

        Args:
            db: Database session
            persona_id: UUID of the persona
            user_id: Optional UUID of the user (for ownership validation)
            db_update: If True, update PersonaPrompt table with generated introduction

        Returns:
            str: Generated introduction text (100 words, concise)
        """
        self.logger.info(f"Generating introduction for persona {persona_id}")

        # Fetch persona with optional user ownership validation
        if user_id is not None:
            stmt = select(Persona).where(Persona.id == persona_id, Persona.user_id == user_id)
        else:
            stmt = select(Persona).where(Persona.id == persona_id)

        result = await db.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            if user_id is not None:
                raise ValueError(
                    f"Persona with ID {persona_id} not found or not owned by user {user_id}"
                )
            raise ValueError(f"Persona with ID {persona_id} not found")

        # LinkedIn tables have been removed; use empty defaults
        linkedin_summary = ""
        linkedin_headline = ""
        experience_text = ""

        # Generate introduction using OpenAI
        system_prompt = """You are an expert persona profiler. Create a short, concise professional introduction
        based on LinkedIn data. The introduction should be engaging, professional, and capture their essence."""

        user_prompt = f"""
        Create a professional introduction for this persona:

        Name: {persona.name}
        LinkedIn Headline: {linkedin_headline}
        LinkedIn Summary: {linkedin_summary}

        Professional Experience:
        {experience_text if experience_text else "No experience data available"}

        Requirements:
        1. EXACTLY 100 words maximum
        2. Professional yet engaging tone
        3. Highlight key strengths and current role
        4. Make it sound authentic and human
        5. Focus on most relevant and recent experience

        Format: Return only the introduction text, no additional commentary.
        """

        try:
            self.openai_service.set_system_prompt(system_prompt)
            loop = asyncio.get_event_loop()

            response = await loop.run_in_executor(
                None,
                lambda: self.openai_service.generate_response_raw(
                    user_prompt, system=system_prompt, temperature=0.3, max_tokens=300
                ),
            )

            introduction = getattr(response, "output_text", "").strip()

            # Update PersonaPrompt table if requested
            if db_update:
                await self._update_persona_prompt_field(
                    db, persona_id, "introduction", introduction
                )

            logger.info(f"Introduction generated for persona {persona_id}")
            return introduction

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"persona_id": str(persona_id), "user_id": str(user_id) if user_id else None},
                tags={
                    "component": "advanced_prompt_creator",
                    "operation": "_generate_introduction",
                    "severity": "medium",
                },
            )
            self.logger.error(f"Error generating introduction: {e}")
            raise Exception(f"Failed to generate introduction: {str(e)}")

    async def _analyze_expertise(
        self,
        db: AsyncSession,
        persona_id: UUID,
        user_id: Optional[UUID] = None,
        db_update: bool = False,
    ) -> ExpertiseArea:
        """
        Analyze and return expertise areas from LinkedIn data.

        Args:
            db: Database session
            persona_id: UUID of the persona
            user_id: Optional UUID of the user (for ownership validation)
            db_update: If True, update PersonaPrompt table with generated expertise

        Returns:
            ExpertiseArea: Object containing primary and secondary expertise areas (5-6 total)
        """
        self.logger.info(f"Analyzing expertise for persona {persona_id}")

        # Fetch persona with optional user ownership validation
        if user_id is not None:
            stmt = select(Persona).where(Persona.id == persona_id, Persona.user_id == user_id)
        else:
            stmt = select(Persona).where(Persona.id == persona_id)

        result = await db.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            if user_id is not None:
                raise ValueError(
                    f"Persona with ID {persona_id} not found or not owned by user {user_id}"
                )
            raise ValueError(f"Persona with ID {persona_id} not found")

        # LinkedIn tables have been removed; use empty defaults
        linkedin_info = None
        experiences = []

        # Build context for OpenAI
        linkedin_summary = linkedin_info.summary if linkedin_info and linkedin_info.summary else ""
        linkedin_headline = (
            linkedin_info.headline if linkedin_info and linkedin_info.headline else ""
        )

        experience_text = ""
        for exp in experiences:
            current_marker = " (Current)" if exp.is_current else ""
            exp_desc = exp.description if exp.description else ""
            experience_text += f"- {exp.title} at {exp.company}{current_marker}: {exp_desc}\n"

        # Get user-defined role and expertise from the persona record
        user_defined_role = persona.role or ""
        user_defined_expertise = persona.expertise or ""

        # Analyze expertise using OpenAI
        system_prompt = """You are an expert analyst specializing in identifying professional expertise.
        Analyze the provided information to determine 5-6 areas of expertise."""

        # Build the prompt — prioritize user-defined fields over scraped data
        user_defined_section = ""
        if user_defined_role or user_defined_expertise:
            user_defined_section = f"""
        USER-DEFINED PROFESSIONAL IDENTITY (THIS IS THE SOURCE OF TRUTH):
        Role: {user_defined_role}
        Expertise Areas: {user_defined_expertise}

        CRITICAL: The user has explicitly defined their role and expertise above.
        These MUST be the foundation of your analysis. The LinkedIn data below is
        supplementary — use it ONLY to add depth or specificity to the user-defined
        expertise areas. If the LinkedIn data shows skills in a DIFFERENT domain
        (e.g. LinkedIn shows software development but user defined themselves as
        an Attorney), IGNORE the conflicting LinkedIn skills entirely and focus
        on the user-defined expertise.
        """

        user_prompt = f"""
        Identify areas of expertise for this professional:
        {user_defined_section}
        SUPPLEMENTARY DATA (LinkedIn — use only if aligned with user-defined identity):
        LinkedIn Headline: {linkedin_headline}
        LinkedIn Summary: {linkedin_summary}

        Professional Experience:
        {experience_text if experience_text else "No experience data available"}

        Requirements:
        1. Identify EXACTLY 5-6 total areas of expertise
        2. Prioritize the user-defined role and expertise above all else
        3. Use LinkedIn data only to add specificity within the user-defined domain
        4. Use specific, professional terminology
        5. NEVER include expertise areas that conflict with the user-defined role

        Format your response EXACTLY as a simple list:
        - [expertise area 1]
        - [expertise area 2]
        - [expertise area 3]
        - [expertise area 4]
        - [expertise area 5]
        - [expertise area 6]
        """

        try:
            self.openai_service.set_system_prompt(system_prompt)
            loop = asyncio.get_event_loop()

            response = await loop.run_in_executor(
                None,
                lambda: self.openai_service.generate_response_raw(
                    user_prompt, system=system_prompt, temperature=0.5, max_tokens=400
                ),
            )

            response_text = getattr(response, "output_text", "").strip()

            # Parse the response to extract expertise areas
            expertise_list = []
            for line in response_text.split("\n"):
                line = line.strip()
                if line.startswith("-"):
                    item = line.lstrip("-").strip()
                    if item:
                        expertise_list.append(item)

            # Split into primary (first 2-3) and secondary (rest)
            if not expertise_list:
                expertise_list = ["General Business", "Communication", "Leadership"]

            # Ensure we have 5-6 items
            while len(expertise_list) < 5:
                expertise_list.append("Professional Development")

            expertise_list = expertise_list[:6]  # Limit to 6

            primary_count = min(3, len(expertise_list) // 2)

            expertise = ExpertiseArea(
                primary=expertise_list[:primary_count], secondary=expertise_list[primary_count:]
            )

            # Update PersonaPrompt table if requested
            if db_update:
                area_of_expertise = self._format_expertise_areas(expertise)
                await self._update_persona_prompt_field(
                    db, persona_id, "area_of_expertise", area_of_expertise
                )

            self.logger.info(f"Expertise analyzed for persona {persona_id}")
            return expertise

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"persona_id": str(persona_id), "user_id": str(user_id) if user_id else None},
                tags={
                    "component": "advanced_prompt_creator",
                    "operation": "_analyze_expertise",
                    "severity": "medium",
                },
            )
            self.logger.error(f"Error analyzing expertise: {e}")
            raise Exception(f"Failed to analyze expertise: {str(e)}")

    def _parse_expertise_response(self, response_text: str) -> ExpertiseArea:
        """Parse the structured expertise response from OpenAI."""
        primary = []
        secondary = []

        current_section = None
        lines = response_text.split("\n")

        for line in lines:
            line = line.strip()
            if "PRIMARY:" in line.upper():
                current_section = "primary"
                continue
            elif "SECONDARY:" in line.upper():
                current_section = "secondary"
                continue
            elif line.startswith("-") and current_section:
                expertise = line.lstrip("-").strip()
                if expertise and current_section == "primary":
                    primary.append(expertise)
                elif expertise and current_section == "secondary":
                    secondary.append(expertise)

        # Ensure we have at least some expertise areas
        if not primary:
            primary = ["Professional Excellence"]
        if not secondary:
            secondary = ["Communication", "Problem Solving"]

        return ExpertiseArea(primary=primary, secondary=secondary)

    async def _analyze_communication_style(
        self,
        db: AsyncSession,
        persona_id: UUID,
        user_id: Optional[UUID] = None,
        db_update: bool = False,
    ) -> CommunicationStyle:
        """
        Extract complete communication style from LinkedIn posts, Twitter posts, website content, and documents.
        Picks only 10 rows from each table and top 500 words from each row.

        Args:
            db: Database session
            persona_id: UUID of the persona
            user_id: Optional UUID of the user (for ownership validation)
            db_update: If True, update PersonaPrompt table with generated communication style

        Returns:
            CommunicationStyle: Object containing all communication style components (max 250 words)
        """
        from shared.database.models.document import Document

        self.logger.info(f"Analyzing communication style for persona {persona_id}")

        # Fetch persona with optional user ownership validation
        if user_id is not None:
            stmt = select(Persona).where(Persona.id == persona_id, Persona.user_id == user_id)
        else:
            stmt = select(Persona).where(Persona.id == persona_id)

        result = await db.execute(stmt)
        persona = result.scalar_one_or_none()

        if not persona:
            if user_id is not None:
                raise ValueError(
                    f"Persona with ID {persona_id} not found or not owned by user {user_id}"
                )
            raise ValueError(f"Persona with ID {persona_id} not found")

        user_id_for_query = persona.user_id

        # LinkedIn, Twitter, and Website tables have been removed
        linkedin_content = []
        twitter_content = []
        website_content = []

        # Fetch documents (limit 10, top 500 words each)
        documents_stmt = (
            select(Document)
            .where(Document.user_id == user_id_for_query)
            .order_by(Document.uploaded_at.desc())
            .limit(10)
        )
        documents_result = await db.execute(documents_stmt)
        documents = documents_result.scalars().all()

        document_content = []
        for doc in documents:
            if doc.content_text:
                words = doc.content_text.split()[:500]
                document_content.append(" ".join(words))

        # Combine all content for analysis
        all_content_parts = []

        if linkedin_content:
            all_content_parts.append("LINKEDIN POSTS:\n" + "\n\n".join(linkedin_content[:10]))

        if twitter_content:
            all_content_parts.append("TWITTER POSTS:\n" + "\n\n".join(twitter_content[:10]))

        if website_content:
            all_content_parts.append("WEBSITE CONTENT:\n" + "\n\n".join(website_content[:10]))

        if document_content:
            all_content_parts.append("DOCUMENTS:\n" + "\n\n".join(document_content[:10]))

        if not all_content_parts:
            logger.warning(f"No content found for persona {persona_id}, using defaults")
            return self._get_default_communication_style()

        content_text = "\n\n---\n\n".join(all_content_parts)
        # Limit total content to avoid token limits
        content_text = smart_truncate(content_text, 15000)

        # Analyze communication style using OpenAI
        system_prompt = """You are a communication style analyst. Analyze the provided content to extract
        detailed insights about communication patterns. BE CONCISE - your entire response must be under 250 words total."""

        user_prompt = f"""
        Analyze the communication style from this content:

        {content_text}

        Extract and analyze (TOTAL OUTPUT MUST BE UNDER 250 WORDS):
        1. Thinking style: How they process and organize ideas
        2. Speaking style: How they verbally express themselves
        3. Writing style: Their written communication patterns
        4. Catch phrases: 3-5 recurring expressions
        5. Transition words: 5-8 commonly used connectors
        6. Key characteristics: 3-5 traits

        Format your response EXACTLY and CONCISELY as:
        THINKING_STYLE:
        [1 sentence describing how they think and process information]

        SPEAKING_STYLE:
        [1 sentence describing their verbal communication patterns]

        WRITING_STYLE:
        [1 sentence describing their written communication approach]

        CATCH_PHRASES:
        - [phrase 1]
        - [phrase 2]
        - [phrase 3]

        TRANSITION_WORDS:
        - [word 1]
        - [word 2]
        - [word 3]
        - [word 4]
        - [word 5]

        CHARACTERISTICS:
        - [trait 1]
        - [trait 2]
        - [trait 3]
        """

        try:
            self.openai_service.set_system_prompt(system_prompt)
            loop = asyncio.get_event_loop()

            response = await loop.run_in_executor(
                None,
                lambda: self.openai_service.generate_response_raw(
                    user_prompt, system=system_prompt, temperature=0.5, max_tokens=500
                ),
            )

            response_text = getattr(response, "output_text", "").strip()

            # Parse the response
            thinking_style = ""
            speaking_style = ""
            writing_style = ""
            catch_phrases = []
            transition_words = []
            characteristics = []

            current_section = None
            thinking_lines = []
            speaking_lines = []
            writing_lines = []

            for line in response_text.split("\n"):
                line = line.strip()

                if "THINKING_STYLE:" in line.upper():
                    current_section = "thinking"
                    thinking_lines = []
                elif "SPEAKING_STYLE:" in line.upper():
                    if current_section == "thinking":
                        thinking_style = " ".join(thinking_lines)
                    current_section = "speaking"
                    speaking_lines = []
                elif "WRITING_STYLE:" in line.upper():
                    if current_section == "speaking":
                        speaking_style = " ".join(speaking_lines)
                    current_section = "writing"
                    writing_lines = []
                elif "CATCH_PHRASES:" in line.upper():
                    if current_section == "writing":
                        writing_style = " ".join(writing_lines)
                    current_section = "catch_phrases"
                elif "TRANSITION_WORDS:" in line.upper():
                    current_section = "transition_words"
                elif "CHARACTERISTICS:" in line.upper():
                    current_section = "characteristics"
                elif line.startswith("-"):
                    item = line.lstrip("-").strip()
                    if item:
                        if current_section == "catch_phrases":
                            catch_phrases.append(item)
                        elif current_section == "transition_words":
                            transition_words.append(item)
                        elif current_section == "characteristics":
                            characteristics.append(item)
                elif current_section == "thinking" and line:
                    thinking_lines.append(line)
                elif current_section == "speaking" and line:
                    speaking_lines.append(line)
                elif current_section == "writing" and line:
                    writing_lines.append(line)

            # Handle last section
            if current_section == "thinking" and thinking_lines:
                thinking_style = " ".join(thinking_lines)
            elif current_section == "speaking" and speaking_lines:
                speaking_style = " ".join(speaking_lines)
            elif current_section == "writing" and writing_lines:
                writing_style = " ".join(writing_lines)

            # Ensure defaults if parsing failed
            if not thinking_style:
                thinking_style = "Analytical and structured approach to problem-solving."
            if not speaking_style:
                speaking_style = "Clear and engaging verbal communication."
            if not writing_style:
                writing_style = "Professional and concise written expression."
            if not catch_phrases:
                catch_phrases = ["Let's dive in", "The key point", "Here's the thing"]
            if not transition_words:
                transition_words = [
                    "However",
                    "Additionally",
                    "Furthermore",
                    "Meanwhile",
                    "In fact",
                ]
            if not characteristics:
                characteristics = ["Professional", "Engaging", "Authentic"]

            communication_style = CommunicationStyle(
                thinking_style=thinking_style,
                speaking_style=speaking_style,
                writing_style=writing_style,
                catch_phrases=catch_phrases[:5],
                transition_words=transition_words[:8],
                tone_characteristics=characteristics[:5],
            )

            # Update PersonaPrompt table if requested
            if db_update:
                combined_style = self._combine_communication_styles(communication_style)
                await self._update_persona_prompt_field(
                    db, persona_id, "thinking_style", combined_style
                )

            logger.info(f"Communication style analyzed for persona {persona_id}")
            return communication_style

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"persona_id": str(persona_id), "user_id": str(user_id) if user_id else None},
                tags={
                    "component": "advanced_prompt_creator",
                    "operation": "_analyze_communication_style",
                    "severity": "medium",
                },
            )
            logger.error(f"Error analyzing communication style: {e}")
            raise Exception(f"Failed to analyze communication style: {str(e)}")

    def _parse_communication_style_response(self, response_text: str) -> CommunicationStyle:
        """Parse the structured communication style response from OpenAI."""
        thinking_style = ""
        speaking_style = ""
        writing_style = ""
        catch_phrases = []
        transition_words = []
        tone_characteristics = []

        current_section = None
        current_text = []

        lines = response_text.split("\n")

        for line in lines:
            line = line.strip()

            if "THINKING_STYLE:" in line.upper():
                current_section = "thinking"
                current_text = []
            elif "SPEAKING_STYLE:" in line.upper():
                if current_section == "thinking":
                    thinking_style = " ".join(current_text)
                current_section = "speaking"
                current_text = []
            elif "WRITING_STYLE:" in line.upper():
                if current_section == "speaking":
                    speaking_style = " ".join(current_text)
                current_section = "writing"
                current_text = []
            elif "CATCH_PHRASES:" in line.upper():
                if current_section == "writing":
                    writing_style = " ".join(current_text)
                current_section = "catch_phrases"
            elif "TRANSITION_WORDS:" in line.upper():
                current_section = "transition_words"
            elif "TONE_CHARACTERISTICS:" in line.upper():
                current_section = "tone_characteristics"
            elif line.startswith("-") and current_section:
                item = line.lstrip("-").strip()
                if item:
                    if current_section == "catch_phrases":
                        catch_phrases.append(item)
                    elif current_section == "transition_words":
                        transition_words.append(item)
                    elif current_section == "tone_characteristics":
                        tone_characteristics.append(item)
            elif current_section in ["thinking", "speaking", "writing"] and line:
                current_text.append(line)

        # Handle last section
        if current_section == "writing" and current_text:
            writing_style = " ".join(current_text)

        return CommunicationStyle(
            thinking_style=thinking_style
            or "Analytical and systematic approach to problem-solving.",
            speaking_style=speaking_style
            or "Clear, professional communication with engaging delivery.",
            writing_style=writing_style
            or "Structured and informative writing with professional tone.",
            catch_phrases=catch_phrases
            or ["Let's dive in", "The key point is", "Here's the thing"],
            transition_words=transition_words
            or ["However", "Additionally", "Furthermore", "In fact", "Moreover"],
            tone_characteristics=tone_characteristics or ["Professional", "Engaging", "Authentic"],
        )

    def _get_default_communication_style(self) -> CommunicationStyle:
        """Return default communication style when analysis fails."""
        return CommunicationStyle(
            thinking_style="Thoughtful and analytical approach with focus on practical solutions.",
            speaking_style="Clear, confident communication with engaging and professional delivery.",
            writing_style="Well-structured content with professional tone and accessible language.",
            catch_phrases=[
                "Let's explore this",
                "The key insight here",
                "What's important to note",
            ],
            transition_words=["However", "Additionally", "Furthermore", "Meanwhile", "In contrast"],
            tone_characteristics=["Professional", "Engaging", "Authentic", "Solution-focused"],
        )

    async def _generate_example_responses(
        self,
        db: AsyncSession,
        persona_id: UUID,
        expertise: ExpertiseArea,
        communication_style: CommunicationStyle,
        questions: Optional[List[str]] = None,
        user_id: Optional[UUID] = None,
        db_update: bool = False,
    ) -> List[Dict[str, str]]:
        """
        Generate example response patterns in markdown format based on persona style and expertise.
        Generates conversational examples showing GOOD vs BAD responses, scope boundaries, and handling patterns.

        Args:
            db: Database session
            persona_id: UUID of the persona
            expertise: ExpertiseArea object with primary and secondary expertise
            communication_style: CommunicationStyle object
            questions: Optional list of questions (defaults to standard questions)
            user_id: Optional UUID of the user (for ownership validation)
            db_update: If True, update PersonaPrompt table with generated responses

        Returns:
            List containing a single dict with the example response pattern in markdown format
        """
        self.logger.info(f"Generating example response patterns for persona {persona_id}")

        # Fetch persona info
        persona_info = await self._fetch_persona_info(db, persona_id, user_id)
        if not persona_info:
            raise ValueError(f"Persona with ID {persona_id} not found")

        # Get user_id from persona to fetch LinkedIn info
        persona_stmt = select(Persona).where(Persona.id == persona_id)
        persona_result = await db.execute(persona_stmt)
        persona = persona_result.scalar_one_or_none()

        if not persona:
            raise ValueError(f"Persona with ID {persona_id} not found")

        # LinkedIn tables have been removed; use default headline
        linkedin_headline = "Professional"

        # Get persona introduction for context
        persona_prompt_stmt = select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id)
        persona_prompt_result = await db.execute(persona_prompt_stmt)
        persona_prompt = persona_prompt_result.scalar_one_or_none()

        introduction = (
            persona_prompt.introduction if persona_prompt and persona_prompt.introduction else ""
        )

        system_prompt = f"""You are an expert at creating conversational AI guidelines. Generate example response patterns
        that demonstrate how {persona_info.name} should interact with users - showing good vs bad examples, scope boundaries,
        and handling different scenarios in a human-like, conversational manner."""

        # Create persona context
        persona_context = f"""
        PERSONA: {persona_info.name}
        ROLE: {linkedin_headline}
        INTRODUCTION: {introduction}

        PRIMARY EXPERTISE: {', '.join(expertise.primary)}
        SECONDARY EXPERTISE: {', '.join(expertise.secondary)}

        THINKING STYLE: {communication_style.thinking_style}
        SPEAKING STYLE: {communication_style.speaking_style}
        WRITING STYLE: {communication_style.writing_style}

        CATCH PHRASES: {', '.join(communication_style.catch_phrases)}
        TRANSITION WORDS: {', '.join(communication_style.transition_words)}
        TONE: {', '.join(communication_style.tone_characteristics)}
        """

        user_prompt = f"""
        {persona_context}

        Create comprehensive example response patterns for {persona_info.name} in markdown format.
        Adapt the following structure to their specific expertise and communication style:

        Generate examples that show:
        1. **BAD (Generic)** vs **GOOD (Human-like)** responses - at least 2 examples
        2. **In Scope** topics (what they should discuss based on their expertise)
        3. **Out of Scope** topics (what to politely refuse and redirect)
        4. **On-Topic** vs **Off-Topic** handling examples
        5. **Knowledge Gap** handling (when they don't have verified information)

        CRITICAL REQUIREMENTS:
        - Make examples CONVERSATIONAL and NATURAL - avoid robotic list-making
        - BAD examples should be generic, formal, list-heavy
        - GOOD examples should be warm, engaging, question-asking, human-like
        - Base in-scope topics strictly on: {', '.join(expertise.primary + expertise.secondary)}
        - Use their communication style: {communication_style.speaking_style}
        - Incorporate their catch phrases where natural: {', '.join(communication_style.catch_phrases[:3])}
        - Keep responses authentic to their voice and tone

        Format EXACTLY as markdown like this structure:

        **BAD (Generic):** "[Generic, formal response about their field]"

        **GOOD (Human-like):** "[Conversational, warm, question-asking response]"

        **BAD (List-heavy):** "[Formal list of questions or requirements]"

        **GOOD (Conversational):** "[Natural, engaging way to gather same information]"

        **In Scope:** [List their actual areas of expertise - be specific to their background]

        **Out of Scope - Refuse Politely:**
        - [Topic 1 outside their expertise]
        - [Topic 2 outside their expertise]
        - [Topic 3 outside their expertise]

        **Redirect:** "[How they politely redirect back to their expertise]"

        **If Completely Off-Topic:** "[How they handle totally irrelevant questions]"

        **On-Topic:**
          User: "[Example on-topic question]"
          You: "[Natural, engaging response]"

        **Off-Topic:**
          User: "[Example off-topic question]"
          You: "[Polite redirect response]"

        **Knowledge Gap:**
          User: "[Question where they may not have current info]"
          You: "[Honest response about knowledge limits + value-add]"

        RETURN ONLY THE MARKDOWN - NO ADDITIONAL COMMENTARY.
        """

        try:
            self.openai_service.set_system_prompt(system_prompt)
            loop = asyncio.get_event_loop()

            response = await loop.run_in_executor(
                None,
                lambda: self.openai_service.generate_response_raw(
                    user_prompt,
                    system=system_prompt,
                    temperature=0.3,  # Lower temperature for stable, consistent examples
                    max_tokens=1500,
                ),
            )

            response_text = getattr(response, "output_text", "").strip()

            # Return as a single example response pattern
            example_responses = [{"type": "response_pattern", "content": response_text}]

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"persona_id": str(persona_id)},
                tags={
                    "component": "advanced_prompt_creator",
                    "operation": "_generate_example_responses",
                    "severity": "medium",
                },
            )
            self.logger.error(f"Error generating example response patterns: {e}")

            # Fallback default pattern
            example_responses = [
                {
                    "type": "response_pattern",
                    "content": self._get_default_example_pattern(expertise, communication_style),
                }
            ]

        # Update PersonaPrompt table if requested
        if db_update:
            example_responses_markdown = self._format_example_responses(example_responses)
            await self._update_persona_prompt_field(
                db, persona_id, "example_responses", example_responses_markdown
            )

        return example_responses

    def _get_default_example_pattern(
        self, expertise: ExpertiseArea, communication_style: CommunicationStyle
    ) -> str:
        """
        Generate a default example response pattern when AI generation fails.

        Args:
            expertise: ExpertiseArea object
            communication_style: CommunicationStyle object

        Returns:
            str: Default markdown-formatted example pattern
        """
        primary_area = expertise.primary[0] if expertise.primary else "your field"

        pattern = f"""**BAD (Generic):** "Here are the key areas in {primary_area}: best practices, common challenges, and strategic approaches. Let's discuss each one."

**GOOD (Human-like):** "Before we dive in - what's your current experience with {primary_area}? That'll help me tailor this to where you are."

**BAD (List-heavy):** "To help you I need: 1) Your background 2) Current challenges 3) Goals 4) Timeline 5) Resources available."

**GOOD (Conversational):** "Tell me about what you're working on. What's the biggest challenge you're facing right now?"

**In Scope:** {', '.join(expertise.primary)}, {', '.join(expertise.secondary[:2])}

**Out of Scope - Refuse Politely:**
- Detailed technical implementation outside my expertise
- Specific product recommendations without context
- Services or consulting during initial conversation
- Topics unrelated to my areas of expertise

**Redirect:** "That's outside my area. Let's focus on {primary_area} - what specific challenges can I help you with there?"

**If Completely Off-Topic:** "That's not my area of expertise. I focus on {primary_area}. What questions do you have about that?"

**On-Topic:**
  User: "How can I improve my approach to {primary_area}?"
  You: "Let's start with what's working - what results are you seeing now?"

**Off-Topic:**
  User: "What's your take on [unrelated topic]?"
  You: "That's outside my expertise - I focus on {primary_area}. But if you're thinking about how that relates to your work, I can help with that."

**Knowledge Gap:**
  User: "What's the best tool for X in 2025?"
  You: "I don't have verified current info on specific tools. But here's how I evaluate solutions - want to use that framework together?"
"""
        return pattern

    def _get_default_questions(self) -> List[str]:
        """Return default questions for example responses."""
        return [
            "What's your approach to solving complex problems in your field?",
            "Can you share a key insight from your experience?",
            "What advice would you give to someone starting in your industry?",
            "How do you stay current with trends and developments?",
            "What's the most important skill for success in your area?",
        ]

    async def _update_persona_prompt_field(
        self, db: AsyncSession, persona_id: UUID, field_name: str, field_value: str
    ) -> None:
        """
        Update a specific field in the PersonaPrompt table.

        Args:
            db: Database session
            persona_id: UUID of the persona
            field_name: Name of the field to update
            field_value: Value to set for the field
        """
        try:
            # Fetch existing PersonaPrompt
            stmt = select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id)
            result = await db.execute(stmt)
            prompt_entry = result.scalar_one_or_none()

            if prompt_entry:
                # Update the field
                setattr(prompt_entry, field_name, field_value)
                prompt_entry.updated_at = datetime.now(timezone.utc)
                db.add(prompt_entry)
                await db.commit()
                self.logger.info(f"Updated PersonaPrompt.{field_name} for persona {persona_id}")
            else:
                # Create new PersonaPrompt entry with this field
                new_prompt = PersonaPrompt(
                    persona_id=persona_id,
                    is_active=True,
                    is_dynamic=False,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                setattr(new_prompt, field_name, field_value)
                db.add(new_prompt)
                await db.commit()
                self.logger.info(
                    f"Created PersonaPrompt with {field_name} for persona {persona_id}"
                )

        except Exception as e:
            await db.rollback()
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(persona_id),
                    "field_name": field_name,
                },
                tags={
                    "component": "advanced_prompt_creator",
                    "operation": "_update_persona_prompt_field",
                },
            )
            self.logger.error(f"Error updating PersonaPrompt field {field_name}: {e}")
            raise

    async def generate_formatted_prompt(
        self,
        db: AsyncSession,
        persona_id: UUID,
        sample_questions: Optional[List[str]] = None,
        template_format: str = "comprehensive",
    ) -> str:
        """
        Generate a complete formatted prompt ready for use.

        Args:
            db: Database session
            persona_id: UUID of the persona
            sample_questions: Optional custom questions
            template_format: Format style ("comprehensive", "concise", "structured")

        Returns:
            Formatted prompt string ready for use
        """
        result = await self.create_advanced_prompt(db, persona_id, sample_questions)

        if template_format == "comprehensive":
            return self._format_comprehensive_prompt(result)
        elif template_format == "concise":
            return self._format_concise_prompt(result)
        else:
            return self._format_structured_prompt(result)

    def _format_comprehensive_prompt(self, result: AdvancedPromptResult) -> str:
        """Format as comprehensive detailed prompt."""
        return f"""
# PERSONA PROFILE

## Introduction
{result.introduction}

## Areas of Expertise

### Primary Expertise
{chr(10).join(f"• {area}" for area in result.expertise.primary)}

### Secondary Expertise
{chr(10).join(f"• {area}" for area in result.expertise.secondary)}

## Communication Style

### Thinking Style
{result.communication_style.thinking_style}

### Speaking Style
{result.communication_style.speaking_style}

### Writing Style
{result.communication_style.writing_style}

### Characteristic Expressions
**Catch Phrases:** {', '.join(result.communication_style.catch_phrases)}
**Transition Words:** {', '.join(result.communication_style.transition_words)}
**Tone Characteristics:** {', '.join(result.communication_style.tone_characteristics)}

## Example Responses

{chr(10).join(f"**Q: {ex['question']}**{chr(10)}{ex['response']}{chr(10)}" for ex in result.example_responses)}

---
*Generated from {sum(result.raw_data_summary.values())} content pieces across {len(result.raw_data_summary)} data sources.*
        """.strip()

    def _format_concise_prompt(self, result: AdvancedPromptResult) -> str:
        """Format as concise prompt."""
        expertise_text = ", ".join(result.expertise.primary[:3])

        return f"""
You are a {expertise_text} expert with the following characteristics:

{result.introduction}

Communication Style: {result.communication_style.thinking_style} {result.communication_style.speaking_style}

Key Phrases: {', '.join(result.communication_style.catch_phrases[:3])}

Respond with expertise in: {', '.join(result.expertise.primary + result.expertise.secondary[:2])}
        """.strip()

    def _format_structured_prompt(self, result: AdvancedPromptResult) -> str:
        """Format as structured prompt with clear sections."""
        return f"""
ROLE: Expert in {', '.join(result.expertise.primary)}

BACKGROUND: {result.introduction}

EXPERTISE:
- Primary: {', '.join(result.expertise.primary)}
- Secondary: {', '.join(result.expertise.secondary)}

COMMUNICATION APPROACH:
- Thinking: {result.communication_style.thinking_style}
- Style: {result.communication_style.speaking_style}
- Tone: {', '.join(result.communication_style.tone_characteristics)}

RESPONSE GUIDELINES:
- Use phrases like: {', '.join(result.communication_style.catch_phrases)}
- Connect ideas with: {', '.join(result.communication_style.transition_words[:3])}
- Maintain professional yet engaging tone
- Draw from expertise areas when relevant

EXAMPLE INTERACTIONS:
{chr(10).join(f"Q: {ex['question']}{chr(10)}A: {smart_truncate(ex['response'], 200, warn_on_truncate=False)}...{chr(10)}" for ex in result.example_responses[:3])}
        """.strip()

    async def ingest_advanced_prompt_data(
        self,
        db: AsyncSession,
        persona_id: UUID,
        prompt_data: AdvancedPromptResult,
        version: int = 1,
    ) -> bool:
        """
        Ingest advanced prompt data into the PersonaPrompt table with versioning support.

        Args:
            db: Database session
            persona_id: UUID of the persona
            prompt_data: AdvancedPromptResult containing prompt data
            version: Version number for the prompt data

        Returns:
            bool: True if ingestion was successful, False otherwise

        Raises:
            Exception: For database or processing errors
        """
        try:
            self.logger.info(
                f"Ingesting advanced prompt data for persona {persona_id}, version {version}"
            )

            # Create or update PersonaPrompt entry
            stmt = select(PersonaPrompt).where(
                PersonaPrompt.persona_id == persona_id, PersonaPrompt.version == version
            )
            result = await db.execute(stmt)
            prompt_entry = result.scalar_one_or_none()

            if prompt_entry:
                # Update existing entry
                prompt_entry.introduction = prompt_data.introduction
                prompt_entry.expertise_primary = ", ".join(prompt_data.expertise.primary)
                prompt_entry.expertise_secondary = ", ".join(prompt_data.expertise.secondary)
                prompt_entry.communication_style = prompt_data.communication_style.thinking_style
                prompt_entry.example_responses = str(prompt_data.example_responses)
                prompt_entry.raw_data_summary = str(prompt_data.raw_data_summary)
                prompt_entry.updated_at = datetime.now(timezone.utc)

                db.add(prompt_entry)
                self.logger.info(
                    f"Updated PersonaPrompt for persona {persona_id}, version {version}"
                )
            else:
                # Create new entry
                new_prompt_entry = PersonaPrompt(
                    persona_id=persona_id,
                    version=version,
                    introduction=prompt_data.introduction,
                    expertise_primary=", ".join(prompt_data.expertise.primary),
                    expertise_secondary=", ".join(prompt_data.expertise.secondary),
                    communication_style=prompt_data.communication_style.thinking_style,
                    example_responses=str(prompt_data.example_responses),
                    raw_data_summary=str(prompt_data.raw_data_summary),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )

                db.add(new_prompt_entry)
                self.logger.info(
                    f"Inserted new PersonaPrompt for persona {persona_id}, version {version}"
                )

            await db.commit()
            return True

        except Exception as e:
            await db.rollback()
            capture_exception_with_context(
                e,
                extra={"persona_id": str(persona_id), "version": version},
                tags={
                    "component": "advanced_prompt_creator",
                    "operation": "ingest_advanced_prompt_data",
                    "severity": "high",
                },
            )
            self.logger.error(f"Error ingesting advanced prompt data: {e}")
            raise

    async def ingest_to_persona_prompt_table(
        self,
        db: AsyncSession,
        persona_id: UUID,
        sample_questions: Optional[List[str]] = None,
        predefined_values: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate advanced pCIGA Designrompt data and ingest it into the PersonaPrompt table.

        Args:
            db: Database session
            persona_id: UUID of the persona
            sample_questions: Optional custom questions for example responses
            predefined_values: Optional predefined values for chat_objective, objective_response, etc.

        Returns:
            Dict containing operation status and details

        Raises:
            ValueError: If persona not found
            Exception: For processing or database errors
        """
        self.logger.info(f"Starting advanced prompt ingestion for persona {persona_id}")

        try:
            # Step 1: Generate advanced prompt data
            prompt_result = await self.create_advanced_prompt(db, persona_id, sample_questions)

            # Step 2: Check if PersonaPrompt already exists
            stmt = select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id)
            result = await db.execute(stmt)
            existing_prompt = result.scalar_one_or_none()

            # Step 3: Prepare data for ingestion
            # Combine thinking, speaking, and writing styles into thinking_style column
            combined_thinking_style = self._combine_communication_styles(
                prompt_result.communication_style
            )

            # Format area of expertise (primary + secondary)
            area_of_expertise = self._format_expertise_areas(prompt_result.expertise)

            # Format example responses as markdown text
            example_responses_markdown = self._format_example_responses(
                prompt_result.example_responses
            )

            # Get predefined values or defaults (with prompt_template fallback)
            predefined = predefined_values or {}
            prompt_template = predefined.get("prompt_template", None)

            chat_objective = predefined.get(
                "chat_objective", self._get_default_chat_objective(prompt_template)
            )
            objective_response = predefined.get(
                "objective_response", self._get_default_objective_response(prompt_template)
            )
            response_structure = predefined.get(
                "response_structure", self._get_default_response_structure(prompt_template)
            )
            conversation_flow = predefined.get(
                "conversation_flow", self._get_default_conversation_flow(prompt_template)
            )
            strict_guideline = predefined.get(
                "strict_guideline", self._get_default_strict_guideline(prompt_template)
            )

            # Step 4: Handle update vs create with versioning
            if existing_prompt:
                # Archive current version to history before updating
                self.logger.info(f"Updating existing PersonaPrompt for persona {persona_id}")

                # Use PersonaPromptHistoryService for versioning
                update_data = {
                    "introduction": prompt_result.introduction,
                    "area_of_expertise": area_of_expertise,
                    "thinking_style": combined_thinking_style,
                    "example_responses": example_responses_markdown,
                    "chat_objective": chat_objective,
                    "objective_response": objective_response,
                    "response_structure": response_structure,
                    "conversation_flow": conversation_flow,
                    "strict_guideline": strict_guideline,
                }

                updated_prompt, history_entry = (
                    await PersonaPromptHistoryService.update_persona_prompt_with_versioning(
                        db, persona_id, update_data
                    )
                )

                operation = "updated"
                archived_version = history_entry.version if history_entry else None

            else:
                # Create new PersonaPrompt entry
                self.logger.info(f"Creating new PersonaPrompt for persona {persona_id}")

                new_prompt = PersonaPrompt(
                    persona_id=persona_id,
                    introduction=prompt_result.introduction,
                    area_of_expertise=area_of_expertise,
                    thinking_style=combined_thinking_style,
                    example_responses=example_responses_markdown,
                    chat_objective=chat_objective,
                    objective_response=objective_response,
                    response_structure=response_structure,
                    conversation_flow=conversation_flow,
                    strict_guideline=strict_guideline,
                    is_active=True,
                    is_dynamic=False,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )

                db.add(new_prompt)
                operation = "created"
                archived_version = None

            # Step 5: Commit changes
            await db.commit()

            # Step 6: Prepare response
            response_data = {
                "status": "success",
                "operation": operation,
                "persona_id": str(persona_id),
                "archived_version": archived_version,
                "data_summary": {
                    "introduction_length": len(prompt_result.introduction),
                    "primary_expertise_count": len(prompt_result.expertise.primary),
                    "secondary_expertise_count": len(prompt_result.expertise.secondary),
                    "example_responses_count": len(prompt_result.example_responses),
                    "content_sources_analyzed": sum(prompt_result.raw_data_summary.values()),
                    "source_types": list(prompt_result.raw_data_summary.keys()),
                },
                "generated_data": {
                    "introduction": (
                        smart_truncate(prompt_result.introduction, 200, warn_on_truncate=False)
                        + "..."
                        if len(prompt_result.introduction) > 200
                        else prompt_result.introduction
                    ),
                    "expertise_areas": (
                        smart_truncate(area_of_expertise, 200, warn_on_truncate=False) + "..."
                        if len(area_of_expertise) > 200
                        else area_of_expertise
                    ),
                    "communication_style_preview": (
                        smart_truncate(combined_thinking_style, 200, warn_on_truncate=False) + "..."
                        if len(combined_thinking_style) > 200
                        else combined_thinking_style
                    ),
                    "example_responses_count": len(prompt_result.example_responses),
                },
            }

            self.logger.info(f"Successfully {operation} PersonaPrompt for persona {persona_id}")
            return response_data

        except ValueError as ve:
            self.logger.error(f"ValueError in prompt ingestion: {ve}")
            raise ve
        except Exception as e:
            await db.rollback()
            capture_exception_with_context(
                e,
                extra={"persona_id": str(persona_id)},
                tags={
                    "component": "advanced_prompt_creator",
                    "operation": "ingest_advanced_prompt_data_with_history",
                    "severity": "high",
                },
            )
            self.logger.error(f"Error ingesting advanced prompt data: {e}")
            raise Exception(f"Failed to ingest prompt data: {str(e)}")

    def _combine_communication_styles(self, communication_style: CommunicationStyle) -> str:
        """Combine thinking, speaking, and writing styles into a single string."""
        combined = f"""
THINKING STYLE:
{communication_style.thinking_style}

SPEAKING STYLE:
{communication_style.speaking_style}

WRITING STYLE:
{communication_style.writing_style}

CHARACTERISTIC EXPRESSIONS:
Catch Phrases: {', '.join(communication_style.catch_phrases)}
Transition Words: {', '.join(communication_style.transition_words)}
Tone Characteristics: {', '.join(communication_style.tone_characteristics)}
        """.strip()

        return combined

    def _format_expertise_areas(self, expertise: ExpertiseArea) -> str:
        """Format expertise areas into a structured string."""
        formatted = f"""
PRIMARY EXPERTISE:
{chr(10).join(f"• {area}" for area in expertise.primary)}

SECONDARY EXPERTISE:
{chr(10).join(f"• {area}" for area in expertise.secondary)}
        """.strip()

        return formatted

    def _format_example_responses(self, example_responses: List[Dict[str, str]]) -> str:
        """
        Format example responses as markdown text.
        Supports both new format (type/content) and legacy format (question/response).

        Returns:
            str: Markdown-formatted text ready for direct use in prompts
        """
        try:
            # Check if it's the new response pattern format
            if example_responses and example_responses[0].get("type") == "response_pattern":
                # New format: return the markdown content directly
                return example_responses[0].get("content", "")

            # Legacy format: convert Q&A pairs to markdown
            markdown_parts = []
            for i, response in enumerate(example_responses, 1):
                question = response.get("question", "")
                answer = response.get("response", "")

                markdown_parts.append(f"**Example {i}:**\n\n")
                markdown_parts.append(f"User: {question}\n\n")
                markdown_parts.append(f"Response: {answer}\n\n")
                markdown_parts.append("---\n\n")

            return "".join(markdown_parts).strip()

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={"responses_count": len(example_responses) if example_responses else 0},
                tags={
                    "component": "advanced_prompt_creator",
                    "operation": "format_example_responses",
                },
            )
            self.logger.error(f"Error formatting example responses: {e}")
            return "Error: Failed to format example responses"

    def _get_default_chat_objective(self, prompt_template=None) -> str:
        """
        Get default chat objective.
        First checks prompt_template, then falls back to PromptDefaultsService.

        Args:
            prompt_template: Optional PromptTemplate object to check for value

        Returns:
            Chat objective string
        """
        if prompt_template and prompt_template.chat_objective:
            return prompt_template.chat_objective
        return PromptDefaultsService.get_default_chat_objective()

    def _get_default_objective_response(self, prompt_template=None) -> str:
        """
        Get default objective response.
        First checks prompt_template, then falls back to PromptDefaultsService.

        Args:
            prompt_template: Optional PromptTemplate object to check for value

        Returns:
            Objective response string
        """
        if prompt_template and prompt_template.objective_response:
            return prompt_template.objective_response
        return PromptDefaultsService.get_default_objective_response()

    def _get_default_response_structure(self, prompt_template=None) -> str:
        """
        Get default response structure.
        First checks prompt_template, then falls back to PromptDefaultsService.

        Args:
            prompt_template: Optional PromptTemplate object to check for value

        Returns:
            Response structure string
        """
        if prompt_template and prompt_template.response_structure:
            return prompt_template.response_structure
        return PromptDefaultsService.get_default_response_structure()

    def _get_default_conversation_flow(self, prompt_template=None) -> str:
        """
        Get default conversation flow.
        First checks prompt_template, then falls back to PromptDefaultsService.

        Args:
            prompt_template: Optional PromptTemplate object to check for value

        Returns:
            Conversation flow string
        """
        if prompt_template and prompt_template.conversation_flow:
            return prompt_template.conversation_flow
        return PromptDefaultsService.get_default_conversation_flow()

    def _get_default_strict_guideline(self, prompt_template=None) -> str:
        """
        Get default strict guideline.
        First checks prompt_template, then falls back to PromptDefaultsService.

        Args:
            prompt_template: Optional PromptTemplate object to check for value

        Returns:
            Strict guideline string
        """
        if prompt_template and prompt_template.strict_guideline:
            return prompt_template.strict_guideline
        return PromptDefaultsService.get_default_strict_guideline()

    async def create_and_ingest_advanced_prompt(
        self,
        db: AsyncSession,
        persona_id: UUID,
        sample_questions: Optional[List[str]] = None,
        predefined_values: Optional[Dict[str, str]] = None,
        auto_commit: bool = True,
    ) -> Dict[str, Any]:
        """
        One-step method to create advanced prompt and ingest into PersonaPrompt table.

        This is the main entry point for generating and storing advanced persona prompts.

        Args:
            db: Database session
            persona_id: UUID of the persona
            sample_questions: Optional custom questions for example responses
            predefined_values: Optional predefined values for chat_objective, etc.
            auto_commit: Whether to auto-commit the transaction

        Returns:
            Dict containing operation status, data summary, and generated content preview

        Example:
            creator = AdvancedPromptCreator()
            result = await creator.create_and_ingest_advanced_prompt(
                db=db_session,
                persona_id=persona_uuid,
                sample_questions=[
                    "What's your leadership philosophy?",
                    "How do you approach innovation?"
                ],
                predefined_values={
                    "chat_objective": "Custom chat objective",
                    "response_structure": "Custom response structure"
                }
            )
        """
        try:
            # Validate persona exists
            stmt = select(Persona).where(Persona.id == persona_id)
            result = await db.execute(stmt)
            persona = result.scalar_one_or_none()

            if not persona:
                raise ValueError(f"Persona with ID {persona_id} not found")

            # Generate and ingest
            result = await self.ingest_to_persona_prompt_table(
                db, persona_id, sample_questions, predefined_values
            )

            if not auto_commit:
                # If auto_commit is False, caller is responsible for committing
                self.logger.info("Skipping auto-commit, caller must commit transaction")

            return result

        except Exception as e:
            if auto_commit:
                await db.rollback()
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(persona_id),
                    "auto_commit": auto_commit,
                    "has_sample_questions": sample_questions is not None,
                },
                tags={
                    "component": "advanced_prompt_creator",
                    "operation": "create_and_ingest_advanced_prompt",
                    "severity": "high",
                },
            )
            self.logger.error(f"Error in create_and_ingest_advanced_prompt: {e}")
            raise e

    # ========== Individual Component Generation Methods ==========
    # These methods allow generating specific components without full prompt creation

    async def get_persona_introduction_only(
        self,
        db: AsyncSession,
        persona_id: UUID,
        user_id: Optional[UUID] = None,
        db_update: bool = False,
    ) -> str:
        """
        Generate only the persona introduction using LinkedIn data.

        This is more efficient than calling create_advanced_prompt when you only need
        the introduction component.

        Args:
            db: Database session
            persona_id: UUID of the persona
            user_id: Optional UUID of the user (for ownership validation)
            db_update: If True, update PersonaPrompt table with generated introduction

        Returns:
            str: Generated introduction text (100 words, concise)

        Raises:
            ValueError: If persona not found or unauthorized access
        """
        return await self._generate_introduction(db, persona_id, user_id, db_update)

    async def get_persona_expertise_only(
        self,
        db: AsyncSession,
        persona_id: UUID,
        user_id: Optional[UUID] = None,
        db_update: bool = False,
    ) -> ExpertiseArea:
        """
        Analyze and return only the expertise areas from LinkedIn/social data.

        This is more efficient than calling create_advanced_prompt when you only need
        the expertise analysis.

        Args:
            db: Database session
            persona_id: UUID of the persona
            user_id: Optional UUID of the user (for ownership validation)
            db_update: If True, update PersonaPrompt table with generated expertise

        Returns:
            ExpertiseArea: Object containing primary and secondary expertise areas (5-6 total)

        Raises:
            ValueError: If persona not found or unauthorized access
        """
        return await self._analyze_expertise(db, persona_id, user_id, db_update)

    async def get_persona_thinking_style_only(
        self, db: AsyncSession, persona_id: UUID, user_id: Optional[UUID] = None
    ) -> str:
        """
        Extract only the thinking style from persona's content.

        This is more efficient than calling create_advanced_prompt when you only need
        the thinking style component.

        Args:
            db: Database session
            persona_id: UUID of the persona
            user_id: Optional UUID of the user (for ownership validation)

        Returns:
            str: Thinking style description

        Raises:
            ValueError: If persona not found or unauthorized access
        """
        self.logger.info(f"Analyzing thinking style only for persona {persona_id}")

        # Analyze communication style
        communication_style = await self._analyze_communication_style(
            db, persona_id, user_id, db_update=False
        )

        self.logger.info(f"Thinking style analyzed for persona {persona_id}")
        return communication_style.thinking_style

    async def get_persona_writing_style_only(
        self, db: AsyncSession, persona_id: UUID, user_id: Optional[UUID] = None
    ) -> str:
        """
        Extract only the writing style from persona's content.

        This is more efficient than calling create_advanced_prompt when you only need
        the writing style component.

        Args:
            db: Database session
            persona_id: UUID of the persona
            user_id: Optional UUID of the user (for ownership validation)

        Returns:
            str: Writing style description

        Raises:
            ValueError: If persona not found or unauthorized access
        """
        self.logger.info(f"Analyzing writing style only for persona {persona_id}")

        # Analyze communication style
        communication_style = await self._analyze_communication_style(
            db, persona_id, user_id, db_update=False
        )

        self.logger.info(f"Writing style analyzed for persona {persona_id}")
        return communication_style.writing_style

    async def get_full_communication_style_only(
        self,
        db: AsyncSession,
        persona_id: UUID,
        user_id: Optional[UUID] = None,
        db_update: bool = False,
    ) -> CommunicationStyle:
        """
        Extract complete communication style (thinking, speaking, writing) from persona's content.

        Use this when you need all style components but not the full prompt.

        Args:
            db: Database session
            persona_id: UUID of the persona
            user_id: Optional UUID of the user (for ownership validation)
            db_update: If True, update PersonaPrompt table with generated communication style

        Returns:
            CommunicationStyle: Object containing all communication style components (max 250 words)

        Raises:
            ValueError: If persona not found or unauthorized access
        """
        return await self._analyze_communication_style(db, persona_id, user_id, db_update)
