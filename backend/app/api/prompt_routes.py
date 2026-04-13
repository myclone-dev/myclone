import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.prompt_template_routes import fetch_prompt_template
from app.services.openai_service import OpenAIModelService
from app.services.persona_prompt_history_service import PersonaPromptHistoryService
from app.services.prompt_defaults_service import PromptDefaultsService
from shared.config import settings
from shared.database.models.database import Persona, PersonaPrompt, async_session_maker
from shared.database.models.embeddings import VoyageLiteEmbedding
from shared.database.repositories.persona_repository import PersonaRepository
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.utils.conversions import str_to_uuid

# Import Langfuse
try:
    from langfuse import Langfuse

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    Langfuse = None


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/prompt", tags=["Prompt"])


class PromptRequest(BaseModel):
    """
    Request model for prompt operations.

    Attributes:
        persona_id (UUID): The persona's unique identifier
        template (str): Template type for the prompt (default: "basic")
        expertise (Optional[str]): Specific expertise area (default: "general")
        platform (str): Platform type for the prompt (default: "openai")
    """

    persona_id: UUID
    template: str = "basic"
    expertise: Optional[str] = "general"
    platform: str = "openai"


class PromptParamUpdate(BaseModel):
    """Request model for updating a single PersonaPrompt column."""

    persona_id: UUID
    field: str
    value: Any


class PersonaPromptResponse(BaseModel):
    id: Optional[UUID] = None
    persona_id: Optional[UUID] = None
    introduction: Optional[str] = None
    thinking_style: Optional[str] = None
    area_of_expertise: Optional[str] = None
    chat_objective: Optional[str] = None
    objective_response: Optional[str] = None
    example_responses: Optional[str] = None
    target_audience: Optional[str] = None
    prompt_template_id: Optional[UUID] = None
    example_prompt: Optional[str] = None
    is_dynamic: Optional[bool] = None
    is_active: Optional[bool] = None
    response_structure: Optional[str] = None
    conversation_flow: Optional[str] = None
    strict_guideline: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# -------------------- Helpers -------------------- #


async def get_db():
    """
    Database session dependency for FastAPI routes.

    Yields:
        AsyncSession: Database session for async operations
    """
    async with async_session_maker() as session:
        yield session


async def fetch_persona(
    session: AsyncSession, username: str, persona_name: str = "default"
) -> Optional[Persona]:
    """
    Fetch a persona by username from the database.

    Args:
        session (AsyncSession): Database session
        username (str): Username of the user (User.username)
        persona_name (str): Name of the persona (defaults to "default")

    Returns:
        Persona | None: Persona object if found, None otherwise
    """
    return await PersonaRepository.get_by_username_and_persona(session, username, persona_name)


async def fetch_content_chunks(session: AsyncSession, username: str, persona_name: str = "default"):
    """
    Fetch all embeddings (chunks) accessible by a persona.

    In the new architecture, embeddings are user-owned and shared across personas.
    Personas reference which sources to use via persona_data_sources table.

    Args:
        session (AsyncSession): Database session
        username (str): Username of the user (User.username)
        persona_name (str): Name of the persona (defaults to "default")

    Returns:
        tuple[Persona | None, list[VoyageLiteEmbedding] | None]: Tuple containing the persona and its accessible embeddings
    """
    from shared.rag.llama_rag import LlamaRAGSystem

    persona = await PersonaRepository.get_by_username_and_persona(session, username, persona_name)
    if not persona:
        return None, None

    # Get source_record_ids that this persona has access to
    rag_system = LlamaRAGSystem()
    source_record_ids = await rag_system.get_persona_source_record_ids(persona.id)

    if not source_record_ids:
        return persona, []

    # Fetch embeddings filtered by persona's accessible sources
    stmt = select(VoyageLiteEmbedding).where(
        VoyageLiteEmbedding.source_record_id.in_(source_record_ids)
    )
    result = await session.execute(stmt)
    return persona, result.scalars().all()


async def fetch_persona_prompt_active(session: AsyncSession, persona_id: UUID):
    """
    Fetch active persona prompt by persona_id.
    """
    stmt = select(PersonaPrompt).where(
        and_(PersonaPrompt.persona_id == persona_id, PersonaPrompt.is_active == True)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def fetch_persona_prompt_inactive(session: AsyncSession, persona_id: UUID):
    """
    Fetch inactive persona prompt by persona_id.
    """
    stmt = select(PersonaPrompt).where(
        and_(PersonaPrompt.persona_id == persona_id, PersonaPrompt.is_active == False)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def fetch_persona_prompt(session: AsyncSession, persona_id: UUID):
    """
    Fetch existing persona prompt by persona_id.

    Args:
        session (AsyncSession): Database session
        persona_id (UUID): UUID of the persona

    Returns:
        PersonaPrompt | None: Existing persona prompt if found, None otherwise
    """
    stmt = select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def call_openai_llm(name, role, description, raw_text, example):
    """
    Generate a customized prompt using OpenAI's Responses API via OpenAIModelService.

    Uses retry logic (max 3 attempts: initial + 2 retries) for transient failures like timeouts.
    Performs simple hallucination/quality checks; returns None if checks fail after retries.
    """
    logger = logging.getLogger(__name__)

    def _build_user_instruction():
        base = [
            "You are to craft a high‑quality persona prompt leveraging the provided persona profile and raw domain text.",
            "Return ONLY the prompt text. Do not add meta commentary.",
            "If information is missing, gracefully omit that section—do not fabricate facts.",
        ]
        profile_parts = [
            f"Name: {name}" if name else None,
            f"Role: {role}" if role else None,
            f"Description: {description}" if description else None,
        ]
        profile = "\n".join([p for p in profile_parts if p])
        return (
            "\n".join(base)
            + "\n\nPersona Profile:\n"
            + (profile or "(No additional profile details provided)")
            + "\n\nReference Example (Follow Template not background info):\n"
            + (example or "(No example provided)")
            + "\n\nRaw Knowledge Text (may contain duplicates / noise):\n"
            + (raw_text[:12000] if raw_text else "(No raw text)")
            + "\n\nProduce the final adapted prompt in the same format and Template as in Example above with given Persona Profile below without any explanation:"
        )

    def _is_low_quality(output: str) -> bool:
        if not output:
            return True
        cleaned = output.strip()
        if len(cleaned) < 40:
            return True
        hallucination_markers = [
            "As an AI language model",
            "I cannot access",
            "I don't have access to real-time",
            "Assistant:",
        ]
        if any(m.lower() in cleaned.lower() for m in hallucination_markers):
            return True
        if cleaned.count(name) > 6 and name:
            return True
        return False

    service = OpenAIModelService(api_key=settings.openai_api_key)
    service.set_system_prompt(
        "You transform structured persona data + raw knowledge into a clean, consolidated persona prompt for reference see example provided."
    )

    user_instruction = _build_user_instruction()

    attempts = 0
    max_attempts = 3
    backoff_seconds = 2
    last_error = None

    while attempts < max_attempts:
        attempts += 1
        try:
            loop = asyncio.get_event_loop()
            # Use raw stateless generation now
            raw_response = await loop.run_in_executor(
                None,
                lambda: service.generate_response_raw(
                    user_instruction,
                    system=None,  # use service.system_prompt
                    temperature=service.temperature,
                    max_tokens=service.max_tokens,
                ),
            )
            output = getattr(raw_response, "output_text", "")
            if _is_low_quality(output):
                logger.warning(
                    f"LLM output low quality on attempt {attempts} - will retry"
                    if attempts < max_attempts
                    else "Final attempt produced low quality output"
                )
                last_error = ValueError("Low quality / hallucination detected")
            else:
                return output.strip()
        except Exception as e:
            last_error = e
            logger.error(f"Prompt generation attempt {attempts} failed: {e}")
        if attempts < max_attempts:
            await asyncio.sleep(backoff_seconds * attempts)

    logger.error(
        f"Failed to generate acceptable prompt after {max_attempts} attempts: {last_error}"
    )
    return None


async def generate_conversation_flow_and_examples(
    introduction: str,
    area_of_expertise: str,
    thinking_style: str,
    chat_objective: str,
) -> tuple[str | None, str | None]:
    """
    Generate conversation flow and example conversations using OpenAI GPT-4o.

    Args:
        introduction: Persona introduction text
        area_of_expertise: Persona's area of expertise
        thinking_style: Persona's thinking style
        chat_objective: Chat objective to base conversation flow on

    Returns:
        Tuple of (conversation_flow, objective_response) or (None, None) if generation fails

    Conversation flow should be max 100 words, point-wise format.
    Example conversations should demonstrate the conversation flow in practice.
    """
    logger = logging.getLogger(__name__)

    system_prompt = """You are an expert at creating conversation flow frameworks and example conversations for AI personas.
You will be provided with persona details and a chat objective. Your task is to:

1. Create a point-wise conversation flow (max 100 words) that guides how the persona should conduct conversations
2. Create example conversations that demonstrate this flow in action

Be concise, actionable, and specific to the persona's expertise and chat objective."""

    user_prompt = f"""Based on the following persona details, create a conversation flow and example conversations:

## Persona Details

**Introduction:**
{introduction}

**Area of Expertise:**
{area_of_expertise}

**Thinking Style:**
{thinking_style}

**Chat Objective:**
{chat_objective}

## Reference Examples

### Example Chat Objective:
Provide consultancy for startup fund raise and investment

### Example Conversation Flow:
1. **Discover:** Start each new topic with one clarifying question.
2. **Clarify:** Ask concise follow-ups before advising.
3. **Reason Briefly:** Explain your thinking before giving guidance.
4. **Advise:** Give clear, actionable recommendations tied to the Chat Objective.
5. **Close:** End with a next step or reflection.
Maintain a one-on-one, conversational tone — curious, confident, and warm.

### Example Conversations:
### Example 1: Early Product
**Founder:** "AI tool for sales teams to auto-generate personalized outreach."
**AJ:** "Where are you in the build?"
**Founder:** "Live for three weeks. Twelve beta users, three paying $50/month."
**AJ:** "How'd you find them?"
**Founder:** "My network - former colleagues."
**AJ:** "Usage pattern?"
**Founder:** "Eight of twelve log in daily. Three paying customers have 100% daily usage."
**AJ:** "You can ship fast and you've got early usage signal. Problem is sample size and network dependency. Can you get 10 paying customers outside your circle? That's what I need to see."

---

### Example 2: Distribution Play
**Founder:** "Built 50k Twitter following on productivity. Made a tool my audience wanted."
**AJ:** "Engagement rate?"
**Founder:** "2-5% per tweet. 200k monthly impressions."
**AJ:** "How many followers using it?"
**Founder:** "250 users, 80 paying $5/month."
**AJ:** "That's 0.5% conversion. Why so low?"
**Founder:** "Soft-launched two weeks ago."
**AJ:** "If someone uses your tracker, how do friends find out?"
**Founder:** "They don't. It's single-player."
**AJ:** "You've got distribution but the product doesn't leverage it. Need share mechanics, leaderboards, Twitter integration. Fix that, then let's talk."

---

### Example 3: Passing - Too Early
**Founder:** "Building Uber for dog walking with AI matching."
**AJ:** "Where are you in the build?"
**Founder:** "Idea stage. Have Figma mocks. Raising to hire engineers."
**AJ:** "Are you technical?"
**Founder:** "No. Talking to some engineers about joining."
**AJ:** "This isn't investable. You're idea stage with no ability to execute. Find a technical co-founder who'll build for equity, not cash. Get a working product and five dog owners using it. Then think about raising. Honestly, dog walking is tough - low margins, high ops. I'd rethink the idea entirely."

## Your Task

Now, create:

1. **CONVERSATION_FLOW** (max 100 words, point-wise format similar to the example above)
2. **EXAMPLE_CONVERSATIONS** (2-3 example conversations demonstrating the flow, similar format to examples above)

Format your response EXACTLY as:

CONVERSATION_FLOW:
[Your conversation flow here - max 100 words, numbered points]

EXAMPLE_CONVERSATIONS:
[Your example conversations here - 2-3 examples with clear speaker labels and realistic dialogue]

Do not add any other text or commentary."""

    service = OpenAIModelService(api_key=settings.openai_api_key)
    service.set_system_prompt(system_prompt)

    attempts = 0
    max_attempts = 3
    backoff_seconds = 2

    while attempts < max_attempts:
        attempts += 1
        try:
            loop = asyncio.get_event_loop()
            raw_response = await loop.run_in_executor(
                None,
                lambda: service.generate_response_raw(
                    user_prompt,
                    system=system_prompt,
                    temperature=0.7,
                    max_tokens=2000,
                ),
            )
            output = getattr(raw_response, "output_text", "")

            if not output or len(output.strip()) < 50:
                logger.warning(f"Generation attempt {attempts} produced insufficient output")
                if attempts < max_attempts:
                    await asyncio.sleep(backoff_seconds * attempts)
                continue

            # Parse the output to extract conversation_flow and objective_response
            try:
                parts = output.split("EXAMPLE_CONVERSATIONS:")
                if len(parts) != 2:
                    raise ValueError("Missing EXAMPLE_CONVERSATIONS section")

                flow_part = parts[0].replace("CONVERSATION_FLOW:", "").strip()
                examples_part = parts[1].strip()

                if not flow_part or not examples_part:
                    raise ValueError("Empty conversation flow or examples")

                # Validate conversation flow length (should be ~100 words)
                flow_word_count = len(flow_part.split())
                if flow_word_count > 150:  # Allow some flexibility
                    logger.warning(
                        f"Conversation flow is {flow_word_count} words, exceeds 100 word target"
                    )

                logger.info(
                    f"Successfully generated conversation flow ({flow_word_count} words) and examples"
                )
                return flow_part, examples_part

            except ValueError as e:
                logger.warning(f"Failed to parse generation output on attempt {attempts}: {e}")
                capture_exception_with_context(
                    e,
                    extra={
                        "attempt": attempts,
                        "intro_length": len(introduction),
                        "chat_objective": chat_objective[:100],  # Truncate to avoid PII
                        "output_length": len(output) if output else 0,
                    },
                    tags={
                        "component": "prompt_generation",
                        "operation": "parse_conversation_flow",
                        "severity": "low",
                        "user_facing": "false",
                    },
                )
                if attempts < max_attempts:
                    await asyncio.sleep(backoff_seconds * attempts)
                continue

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "attempt": attempts,
                    "intro_length": len(introduction),
                    "chat_objective": chat_objective[:100],  # Truncate to avoid PII
                    "area_of_expertise": area_of_expertise[:100] if area_of_expertise else None,
                    "thinking_style_length": len(thinking_style) if thinking_style else 0,
                },
                tags={
                    "component": "prompt_generation",
                    "operation": "generate_conversation_flow",
                    "severity": "medium",
                    "user_facing": "true",
                },
            )
            logger.error(f"Generation attempt {attempts} failed: {e}")
            if attempts < max_attempts:
                await asyncio.sleep(backoff_seconds * attempts)

    # Log final failure with Sentry
    final_error = Exception(f"Failed to generate conversation flow after {max_attempts} attempts")
    capture_exception_with_context(
        final_error,
        extra={
            "max_attempts": max_attempts,
            "intro_length": len(introduction),
            "chat_objective": chat_objective[:100],  # Truncate to avoid PII
            "area_of_expertise": area_of_expertise[:100] if area_of_expertise else None,
        },
        tags={
            "component": "prompt_generation",
            "operation": "generate_conversation_flow_final_failure",
            "severity": "high",
            "user_facing": "true",
        },
    )
    logger.error(f"Failed to generate conversation flow after {max_attempts} attempts")
    return None, None


@router.post("/create-prompt-for-persona")
async def create_prompt_for_persona(data: PromptRequest, db: AsyncSession = Depends(get_db)):
    """
    Create a new prompt for a persona using OpenAI LLM with versioning integration.

    Logic:
    1. First check for active prompt - if exists, return it
    2. If no active prompt, check for inactive prompt - if exists, reactivate and update
    3. If no prompt exists at all, create new one

    Note: Database constraint ensures only one active prompt per persona_id.
    """
    # Fetch persona directly by persona_id with user relationship
    from sqlalchemy.orm import selectinload

    persona_stmt = (
        select(Persona).options(selectinload(Persona.user)).where(Persona.id == data.persona_id)
    )
    persona_result = await db.execute(persona_stmt)
    persona = persona_result.scalar_one_or_none()

    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    # Get content chunks for the persona
    from shared.rag.llama_rag import LlamaRAGSystem

    rag_system = LlamaRAGSystem()
    source_record_ids = await rag_system.get_persona_source_record_ids(persona.id)

    content_chunks = []
    if source_record_ids:
        chunks_stmt = select(VoyageLiteEmbedding).where(
            VoyageLiteEmbedding.source_record_id.in_(source_record_ids)
        )
        chunks_result = await db.execute(chunks_stmt)
        content_chunks = chunks_result.scalars().all()

    # Step 1: Check for active prompt first
    active_prompt = await fetch_persona_prompt_active(db, persona.id)
    if active_prompt:
        return {
            "status": "success",
            "action": "existing",
            "persona_id": str(persona.id),
            "prompt": getattr(active_prompt, "example_prompt", None),
            "message": "Active prompt already exists for persona",
        }

    # Step 2: Check for inactive prompt
    inactive_prompt = await fetch_persona_prompt_inactive(db, persona.id)
    if inactive_prompt:
        # Reactivate and update the inactive prompt
        prompt_template = await fetch_prompt_template(
            db, data.template, data.expertise, data.platform
        )
        if not prompt_template:
            raise HTTPException(status_code=404, detail="Prompt template not found")

        # Get role and company with priority: Persona > User > LinkedIn
        role = persona.role  # Try Persona table first
        if not role and persona.user:
            role = persona.user.role  # Try User table if Persona.role is null

        company = None
        if persona.user:
            company = persona.user.company  # Get company from User table

        # LinkedIn repository removed; role/company come from user/persona fields only

        raw_text = " ".join([c.text for c in content_chunks]) if content_chunks else ""
        prompt = await call_openai_llm(
            persona.name, role or "Expert", persona.description, raw_text, prompt_template.example
        )
        if not prompt:
            raise HTTPException(status_code=500, detail="Failed to generate prompt")

        # Update the inactive prompt and reactivate
        inactive_prompt.is_active = True
        inactive_prompt.example_prompt = prompt
        inactive_prompt.prompt_template_id = prompt_template.id  # Store FK reference
        inactive_prompt.updated_at = datetime.now(timezone.utc)

        # Ensure introduction is populated
        if not inactive_prompt.introduction:
            introduction_text = (persona.description or prompt).strip()[:1000]
            if not introduction_text:
                introduction_text = "Auto-generated persona introduction"
            inactive_prompt.introduction = introduction_text

        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            # If constraint violation occurs during reactivation, an active prompt was created concurrently
            # Fetch and return the existing active prompt
            logger.warning(
                f"Constraint violation during reactivation for persona {persona.id}: {e}"
            )
            active_prompt = await fetch_persona_prompt_active(db, persona.id)
            if active_prompt:
                return {
                    "status": "success",
                    "action": "existing",
                    "persona_id": str(persona.id),
                    "prompt": getattr(active_prompt, "example_prompt", None),
                    "message": "Active prompt already exists for persona",
                }
            raise HTTPException(status_code=500, detail="Failed to create or reactivate prompt")

        return {
            "status": "success",
            "action": "reactivated",
            "persona_id": str(persona.id),
            "prompt": prompt,
            "message": "Inactive prompt reactivated and updated",
        }

    # Step 3: No prompt exists, create new one
    prompt_template = await fetch_prompt_template(db, data.template, data.expertise, data.platform)
    if not prompt_template:
        raise HTTPException(status_code=404, detail="Prompt template not found")

    # Get role and company with priority: Persona > User > LinkedIn
    role = persona.role  # Try Persona table first
    if not role and persona.user:
        role = persona.user.role  # Try User table if Persona.role is null

    company = None
    if persona.user:
        company = persona.user.company  # Get company from User table

    # LinkedIn repository removed; role/company come from user/persona fields only

    raw_text = " ".join([c.text for c in content_chunks]) if content_chunks else ""
    prompt = await call_openai_llm(
        persona.name, role or "Expert", persona.description, raw_text, prompt_template.example
    )
    if not prompt:
        raise HTTPException(status_code=500, detail="Failed to generate prompt")

    # Derive introduction: prefer existing persona.description, else first 1000 chars of generated prompt
    introduction_text = (persona.description or prompt).strip()[:1000]
    if not introduction_text:
        introduction_text = "Auto-generated persona introduction"

    persona_prompt = PersonaPrompt(
        persona_id=persona.id,
        introduction=introduction_text,
        example_prompt=prompt,
        prompt_template_id=prompt_template.id,  # Store FK reference
        is_active=True,
    )
    db.add(persona_prompt)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        # If constraint violation occurs, an active prompt was created concurrently
        # Fetch and return the existing active prompt
        logger.warning(f"Constraint violation during creation for persona {persona.id}: {e}")
        active_prompt = await fetch_persona_prompt_active(db, persona.id)
        if active_prompt:
            return {
                "status": "success",
                "action": "existing",
                "persona_id": str(persona.id),
                "prompt": getattr(active_prompt, "example_prompt", None),
                "message": "Active prompt already exists for persona",
            }
        raise HTTPException(status_code=500, detail="Failed to create prompt")

    return {
        "status": "success",
        "action": "created",
        "persona_id": str(persona.id),
        "prompt": prompt,
        "message": "Prompt created successfully",
    }


@router.put("/update-prompt-for-persona")
async def update_prompt_for_persona(data: PromptRequest, db: AsyncSession = Depends(get_db)):
    """
    Update an existing prompt for a persona using OpenAI LLM with versioning integration.

    Logic:
    1. Check for active prompt first - if found, archive to history and update
    2. If no active prompt found, return 404
    """
    # Fetch persona directly by persona_id with user relationship
    from sqlalchemy.orm import selectinload

    persona_stmt = (
        select(Persona).options(selectinload(Persona.user)).where(Persona.id == data.persona_id)
    )
    persona_result = await db.execute(persona_stmt)
    persona = persona_result.scalar_one_or_none()

    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    # Get content chunks for the persona
    from shared.rag.llama_rag import LlamaRAGSystem

    rag_system = LlamaRAGSystem()
    source_record_ids = await rag_system.get_persona_source_record_ids(persona.id)

    content_chunks = []
    if source_record_ids:
        chunks_stmt = select(VoyageLiteEmbedding).where(
            VoyageLiteEmbedding.source_record_id.in_(source_record_ids)
        )
        chunks_result = await db.execute(chunks_stmt)
        content_chunks = chunks_result.scalars().all()

    # Check for active prompt first
    active_prompt = await fetch_persona_prompt_active(db, persona.id)
    if not active_prompt:
        raise HTTPException(status_code=404, detail="No active persona prompt found")

    # Archive current version to history before updating
    try:
        # Use versioning service to archive current and update
        update_data = {
            "example_prompt": None,
            "prompt_template_id": None,
        }  # Will be set after generation

        # Generate new prompt first
        prompt_template = await fetch_prompt_template(
            db, data.template, data.expertise, data.platform
        )
        if not prompt_template:
            raise HTTPException(status_code=404, detail="Prompt template not found")

        # Get role and company with priority: Persona > User > LinkedIn
        role = persona.role  # Try Persona table first
        if not role and persona.user:
            role = persona.user.role  # Try User table if Persona.role is null

        company = None
        if persona.user:
            company = persona.user.company  # Get company from User table

        # LinkedIn repository removed; role/company come from user/persona fields only

        raw_text = " ".join([c.text for c in content_chunks]) if content_chunks else ""
        prompt = await call_openai_llm(
            persona.name, role or "Expert", persona.description, raw_text, prompt_template.example
        )
        if not prompt:
            raise HTTPException(status_code=500, detail="Failed to generate prompt")

        # Update the data with new prompt and template ID
        update_data["example_prompt"] = prompt
        update_data["prompt_template_id"] = prompt_template.id  # Store FK reference

        # Archive current version and update with versioning
        (
            updated_prompt,
            history_entry,
        ) = await PersonaPromptHistoryService.update_persona_prompt_with_versioning(
            db, persona.id, update_data
        )

        # Ensure introduction is populated
        if not updated_prompt.introduction:
            intro_candidate = (persona.description or prompt).strip()[:1000]
            updated_prompt.introduction = intro_candidate or "Auto-generated persona introduction"

        await db.commit()

        return {
            "status": "success",
            "action": "updated",
            "persona_id": str(persona.id),
            "prompt": prompt,
            "archived_version": history_entry.version,
            "message": "Prompt updated successfully with versioning",
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating prompt with versioning: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating prompt: {str(e)}")


@router.delete("/delete-prompt-for-persona")
async def delete_prompt_for_persona(persona_id: str, db: AsyncSession = Depends(get_db)):
    """
    Delete all persona prompts for a given persona_id.

    Behavior:
    - If multiple prompts exist (shouldn't happen due to unique constraint, but handles edge cases):
      1. Archive ALL prompts to history table with 'DELETE' operation
      2. Keep the latest prompt (by created_at) as inactive in main table
      3. Remove all other prompts from main table
    - If single prompt exists:
      1. Archive to history with 'DELETE' operation
      2. Set is_active = False (soft delete)
    - Returns 404 if no prompts found
    """
    # Convert persona_id string to UUID
    try:
        persona_id_uuid = str_to_uuid(persona_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid persona_id format")

    # Fetch ALL prompts for this persona_id (both active and inactive)
    stmt = (
        select(PersonaPrompt)
        .where(PersonaPrompt.persona_id == persona_id_uuid)
        .order_by(PersonaPrompt.created_at.desc())
    )

    result = await db.execute(stmt)
    all_prompts = result.scalars().all()

    if not all_prompts:
        raise HTTPException(status_code=404, detail="No persona prompts found for this persona_id")

    try:
        # Archive all prompts to history
        archived_versions = []
        for prompt in all_prompts:
            history_entry = await PersonaPromptHistoryService._archive_current_version(
                db, prompt, "DELETE"
            )
            archived_versions.append(history_entry.version)

        # Keep the latest (first in ordered list) as inactive
        latest_prompt = all_prompts[0]
        latest_prompt.is_active = False
        latest_prompt.updated_at = datetime.now(timezone.utc)

        # Hard delete all other prompts from main table
        prompts_deleted = 0
        for prompt in all_prompts[1:]:
            await db.delete(prompt)
            prompts_deleted += 1

        await db.commit()

        message = (
            f"Archived {len(all_prompts)} prompt(s) to history. Latest prompt set to inactive."
        )
        if prompts_deleted > 0:
            message += f" Removed {prompts_deleted} older prompt(s) from main table."

        return {
            "status": "success",
            "action": "deleted",
            "persona_id": persona_id,
            "total_prompts_found": len(all_prompts),
            "prompts_archived": len(archived_versions),
            "prompts_deleted_from_main": prompts_deleted,
            "latest_prompt_kept_inactive": str(latest_prompt.id),
            "archived_versions": archived_versions,
            "message": message,
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete prompts for persona {persona_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete prompts: {e}")


@router.delete("/delete-prompt-by-id")
async def delete_prompt_by_id(prompt_id: str, db: AsyncSession = Depends(get_db)):
    """
    Delete/archive a specific persona prompt by its prompt ID.

    Behavior:
    - Archives the prompt to history table with 'DELETE' operation
    - Sets is_active = False (soft delete)
    - Keeps the record in main table as inactive
    - Returns 404 if prompt not found

    This endpoint is useful for:
    - Deleting a specific prompt when you know its ID
    - Admin operations on specific prompts
    - Cleaning up individual prompts
    """
    # Convert prompt_id string to UUID
    try:
        prompt_id_uuid = str_to_uuid(prompt_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid prompt_id format")

    # Fetch the specific prompt by its ID
    stmt = select(PersonaPrompt).where(PersonaPrompt.id == prompt_id_uuid)
    result = await db.execute(stmt)
    prompt = result.scalar_one_or_none()

    if not prompt:
        raise HTTPException(
            status_code=404, detail=f"Persona prompt with ID '{prompt_id}' not found"
        )

    # Check if already inactive
    if not prompt.is_active:
        return {
            "status": "success",
            "action": "already_inactive",
            "prompt_id": prompt_id,
            "persona_id": str(prompt.persona_id),
            "message": "Persona prompt is already inactive",
        }

    try:
        # Archive current version with DELETE operation
        history_entry = await PersonaPromptHistoryService._archive_current_version(
            db, prompt, "DELETE"
        )

        # Set to inactive (soft delete)
        prompt.is_active = False
        prompt.updated_at = datetime.now(timezone.utc)

        await db.commit()

        return {
            "status": "success",
            "action": "deleted",
            "prompt_id": prompt_id,
            "persona_id": str(prompt.persona_id),
            "archived_version": history_entry.version,
            "operation": history_entry.operation,
            "message": "Persona prompt archived to history and set to inactive",
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete prompt {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete prompt: {e}")


@router.patch("/update-prompt-parameter")
async def update_prompt_parameter(data: PromptParamUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update a single parameter (column) of an existing active persona prompt.

    Archives current state to history (operation='UPDATE') using the history service before applying changes.
    """
    allowed_fields = {
        "introduction",
        "thinking_style",
        "area_of_expertise",
        "chat_objective",
        "objective_response",
        "example_responses",
        "target_audience",
        "prompt_template_id",
        "example_prompt",
        "response_structure",
        "conversation_flow",
        "strict_guideline",
    }

    field = data.field.strip()
    if field not in allowed_fields:
        raise HTTPException(
            status_code=400, detail=f"Field '{field}' is not allowed to be updated here"
        )

    # Convert value to proper string format
    # For dict/list values, serialize to JSON string; for other values, use str()
    if data.value is None:
        value_str = None
    elif isinstance(data.value, (dict, list)):
        try:
            value_str = json.dumps(data.value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid value for field '{field}': value must be JSON-serializable",
            )
    else:
        value_str = str(data.value)

    try:
        (
            updated_prompt,
            history_entry,
        ) = await PersonaPromptHistoryService.update_persona_prompt_with_versioning(
            db, data.persona_id, {field: value_str}
        )
        await db.commit()
        return {
            "status": "success",
            "action": "field_updated",
            "persona_id": str(data.persona_id),
            "field": field,
            "value": getattr(updated_prompt, field),
            "archived_version": history_entry.version,
            "message": f"Field '{field}' updated successfully (version archived)",
        }
    except ValueError:
        await db.rollback()
        raise HTTPException(status_code=404, detail="Active persona prompt not found")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update field: {e}")


@router.get("/list-active-prompts", response_model=dict)
async def list_active_prompts(
    persona_id: str, include_inactive: bool = False, db: AsyncSession = Depends(get_db)
):
    """List persona prompts for a persona_id.

    By default only active prompts are returned. If include_inactive=true, returns all (active + inactive) versions.
    This supports future multi-version scenarios after removing the unique constraint on persona_id.
    """
    # Convert persona_id string to UUID
    try:
        persona_id_uuid = str_to_uuid(persona_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid persona_id format")

    stmt = select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id_uuid)
    if not include_inactive:
        stmt = stmt.where(PersonaPrompt.is_active == True)
    stmt = stmt.order_by(
        PersonaPrompt.is_active.desc(), PersonaPrompt.updated_at.desc(), PersonaPrompt.id.desc()
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    prompts = [PersonaPromptResponse.model_validate(r).model_dump() for r in rows]
    return {
        "status": "success",
        "persona_id": persona_id,
        "count": len(prompts),
        "prompts": prompts,
        "message": (
            "Fetched active persona prompts"
            if not include_inactive
            else "Fetched persona prompts (all versions)"
        ),
    }


# -------------------- Persona Prompt History & Versioning Models -------------------- #


class PersonaPromptCreateRequest(BaseModel):
    """Request model for creating a new persona prompt with versioning"""

    persona_id: UUID = Field(..., description="UUID of the persona")
    introduction: str = Field(..., description="Introduction text")
    thinking_style: Optional[str] = Field(None, description="Thinking style description")
    area_of_expertise: Optional[str] = Field(None, description="Area of expertise")
    chat_objective: Optional[str] = Field(None, description="Chat objective")
    objective_response: Optional[str] = Field(None, description="Objective response")
    example_responses: Optional[str] = Field(None, description="Example responses")
    target_audience: Optional[str] = Field(None, description="Target audience")
    prompt_template_id: Optional[UUID] = Field(
        None, description="ID of prompt template used to generate this prompt"
    )
    example_prompt: Optional[str] = Field(None, description="Example prompt")
    is_dynamic: bool = Field(False, description="Is dynamic prompt")
    response_structure: Optional[str] = Field(None, description="Response structure")
    conversation_flow: Optional[str] = Field(None, description="Conversation flow")
    strict_guideline: Optional[str] = Field(
        None, description="Strict guidelines for persona behavior"
    )


class PersonaPromptUpdateRequest(BaseModel):
    """Request model for updating a persona prompt with versioning"""

    introduction: Optional[str] = Field(None, description="Introduction text")
    thinking_style: Optional[str] = Field(None, description="Thinking style description")
    area_of_expertise: Optional[str] = Field(None, description="Area of expertise")
    chat_objective: Optional[str] = Field(None, description="Chat objective")
    objective_response: Optional[str] = Field(None, description="Objective response")
    example_responses: Optional[str] = Field(None, description="Example responses")
    target_audience: Optional[str] = Field(None, description="Target audience")
    prompt_template_id: Optional[UUID] = Field(
        None, description="ID of prompt template used to generate this prompt"
    )
    example_prompt: Optional[str] = Field(None, description="Example prompt")
    is_dynamic: Optional[bool] = Field(None, description="Is dynamic prompt")
    response_structure: Optional[str] = Field(None, description="Response structure")
    conversation_flow: Optional[str] = Field(None, description="Conversation flow")
    strict_guideline: Optional[str] = Field(
        None, description="Strict guidelines for persona behavior"
    )


class HistoryEntryResponse(BaseModel):
    """Response model for history entry"""

    id: int
    original_id: int
    persona_id: UUID
    version: int
    operation: str
    created_at: (
        datetime  # When this history entry was created (i.e., when the version was archived)
    )
    introduction: str
    thinking_style: Optional[str]
    area_of_expertise: Optional[str]
    chat_objective: Optional[str]
    objective_response: Optional[str]
    example_responses: Optional[str]
    target_audience: Optional[str]
    prompt_template_id: Optional[UUID]
    example_prompt: Optional[str]
    is_dynamic: bool
    is_active: bool
    response_structure: Optional[str]
    conversation_flow: Optional[str]
    strict_guideline: Optional[str]
    updated_at: Optional[datetime]


class VersionMetadataResponse(BaseModel):
    """Response model for version metadata"""

    version: int
    operation: str
    changed_at: datetime  # For backward compatibility, maps to created_at in DB
    is_current: bool


class ComparisonResponse(BaseModel):
    """Response model for version comparison"""

    persona_id: UUID
    version_1: int
    version_2: int
    differences: Dict[str, Any]
    identical: bool


# -------------------- Persona Prompt History & Versioning Endpoints -------------------- #


@router.post("/persona-prompts", response_model=PersonaPromptResponse)
async def create_persona_prompt_with_versioning(
    request: PersonaPromptCreateRequest, db: AsyncSession = Depends(get_db)
):
    """
    Create a new persona prompt (Version 1) with versioning support.
    No history entry is created for initial creation.
    """
    try:
        # Convert persona_id string to UUID
        try:
            persona_id_uuid = str_to_uuid(request.persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        # Check if persona_id already has a prompt
        result = await db.execute(
            select(PersonaPrompt).where(PersonaPrompt.persona_id == persona_id_uuid)
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Persona with id '{request.persona_id}' already has a prompt",
            )

        # Create new persona prompt
        new_prompt = PersonaPrompt(
            persona_id=persona_id_uuid,
            introduction=request.introduction,
            thinking_style=request.thinking_style,
            area_of_expertise=request.area_of_expertise,
            chat_objective=request.chat_objective,
            objective_response=request.objective_response,
            example_responses=request.example_responses,
            target_audience=request.target_audience,
            prompt_template_id=request.prompt_template_id,
            example_prompt=request.example_prompt,
            is_dynamic=request.is_dynamic,
            is_active=True,
            response_structure=request.response_structure,
            conversation_flow=request.conversation_flow,
            strict_guideline=request.strict_guideline,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(new_prompt)
        await db.commit()
        await db.refresh(new_prompt)

        logger.info(f"Created new persona prompt for persona_id '{request.persona_id}' (Version 1)")
        return PersonaPromptResponse(**new_prompt.__dict__)

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating persona prompt: {e}")
        raise HTTPException(
            status_code=500, detail="Error creating persona prompt. Please contact support."
        )


@router.put("/persona-prompts/{persona_id}", response_model=PersonaPromptResponse)
async def update_persona_prompt_with_versioning(
    persona_id: str, request: PersonaPromptUpdateRequest, db: AsyncSession = Depends(get_db)
):
    """
    Update a persona prompt with automatic versioning.
    Archives old version to history table before updating.
    """
    try:
        # Convert persona_id string to UUID
        try:
            persona_id_uuid = str_to_uuid(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        # Prepare update data (only non-None values)
        update_data = {k: v for k, v in request.model_dump().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")

        # Update with versioning
        (
            updated_prompt,
            history_entry,
        ) = await PersonaPromptHistoryService.update_persona_prompt_with_versioning(
            db, persona_id_uuid, update_data
        )

        await db.commit()
        await db.refresh(updated_prompt)

        logger.info(
            f"Updated persona prompt for persona_id '{persona_id}' - archived version {history_entry.version}"
        )
        return PersonaPromptResponse(**updated_prompt.__dict__)

    except ValueError as ve:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating persona prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating persona prompt: {str(e)}")


@router.get("/persona-prompts/{persona_id}", response_model=PersonaPromptResponse)
async def get_active_persona_prompt_versioned(persona_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get the current active version of a persona prompt.
    Returns only the latest version from main table.
    """
    try:
        # Convert persona_id string to UUID
        try:
            persona_id_uuid = str_to_uuid(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        result = await db.execute(
            select(PersonaPrompt).where(
                and_(PersonaPrompt.persona_id == persona_id_uuid, PersonaPrompt.is_active == True)
            )
        )
        prompt = result.scalar_one_or_none()

        if not prompt:
            raise HTTPException(
                status_code=404,
                detail=f"Active PersonaPrompt not found for persona_id: {persona_id}",
            )

        return PersonaPromptResponse(**prompt.__dict__)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching persona prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching persona prompt: {str(e)}")


@router.get("/persona-prompts/{persona_id}/history", response_model=List[HistoryEntryResponse])
async def get_persona_prompt_history(
    persona_id: str, limit: Optional[int] = None, db: AsyncSession = Depends(get_db)
):
    """
    Get all historical versions (excluding current version).
    Returns past versions from history table ordered by version descending.
    """
    try:
        # Convert persona_id string to UUID
        try:
            persona_id_uuid = str_to_uuid(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        history_records = await PersonaPromptHistoryService.get_persona_prompt_history(
            db, persona_id_uuid, limit
        )

        return [HistoryEntryResponse(**record.__dict__) for record in history_records]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching persona prompt history: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching persona prompt history: {str(e)}"
        )


@router.get("/persona-prompts/{persona_id}/timeline")
async def get_complete_timeline(persona_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get complete timeline: history + current version combined.
    Shows complete version history including active version.
    """
    try:
        # Convert persona_id string to UUID
        try:
            persona_id_uuid = str_to_uuid(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        timeline = await PersonaPromptHistoryService.get_complete_timeline(db, persona_id_uuid)
        return {"persona_id": persona_id, "timeline": timeline, "total_versions": len(timeline)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching persona prompt timeline: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching persona prompt timeline: {str(e)}"
        )


@router.get("/persona-prompts/{persona_id}/history/{version}", response_model=HistoryEntryResponse)
async def get_specific_historical_version(
    persona_id: str, version: int, db: AsyncSession = Depends(get_db)
):
    """
    Get a specific historical version from history table.
    Error if requesting current version (not in history).
    """
    try:
        # Convert persona_id string to UUID
        try:
            persona_id_uuid = str_to_uuid(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        history_record = await PersonaPromptHistoryService.get_specific_version(
            db, persona_id_uuid, version
        )

        if not history_record:
            raise HTTPException(
                status_code=404, detail=f"Version {version} not found for persona_id '{persona_id}'"
            )

        return HistoryEntryResponse(**history_record.__dict__)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching specific version: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching specific version: {str(e)}")


@router.get("/persona-prompts/{persona_id}/compare", response_model=ComparisonResponse)
async def compare_versions(
    persona_id: str, from_version: int, to_version: int, db: AsyncSession = Depends(get_db)
):
    """
    Compare two versions and return differences.
    Use 0 to represent current version.
    """
    try:
        # Convert persona_id string to UUID
        try:
            persona_id_uuid = str_to_uuid(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        comparison = await PersonaPromptHistoryService.compare_versions(
            db, persona_id_uuid, from_version, to_version
        )

        return ComparisonResponse(**comparison)

    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error comparing versions: {e}")
        raise HTTPException(status_code=500, detail=f"Error comparing versions: {str(e)}")


@router.post(
    "/persona-prompts/{persona_id}/restore/{version}", response_model=PersonaPromptResponse
)
async def restore_previous_version(
    persona_id: str, version: int, db: AsyncSession = Depends(get_db)
):
    """
    Restore a previous version as current.
    Archives current version to history first, then restores specified version.
    """
    try:
        # Convert persona_id string to UUID
        try:
            persona_id_uuid = str_to_uuid(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        restored_prompt, archive_entry = await PersonaPromptHistoryService.restore_version(
            db, persona_id_uuid, version
        )

        await db.commit()
        await db.refresh(restored_prompt)

        logger.info(f"Restored persona prompt for persona_id '{persona_id}' to version {version}")
        return PersonaPromptResponse(**restored_prompt.__dict__)

    except HTTPException:
        await db.rollback()
        raise
    except ValueError as ve:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        await db.rollback()
        logger.error(f"Error restoring version: {e}")
        raise HTTPException(status_code=500, detail=f"Error restoring version: {str(e)}")


@router.get("/persona-prompts/{persona_id}/versions", response_model=List[VersionMetadataResponse])
async def list_version_metadata(persona_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get version metadata list: historical versions + current version info.
    Includes version number, operation, and timestamp without full content.
    """
    try:
        # Convert persona_id string to UUID
        try:
            persona_id_uuid = str_to_uuid(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        metadata = await PersonaPromptHistoryService.get_version_metadata(db, persona_id_uuid)
        return [VersionMetadataResponse(**meta) for meta in metadata]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching version metadata: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching version metadata: {str(e)}")


@router.get("/persona-prompts/{persona_id}/history/count")
async def get_history_count(persona_id: str, db: AsyncSession = Depends(get_db)):
    """
    Get count of historical versions for a persona.
    Quick check for how many times prompt was modified.
    """
    try:
        # Convert persona_id string to UUID
        try:
            persona_id_uuid = str_to_uuid(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        count = await PersonaPromptHistoryService.get_history_count(db, persona_id_uuid)

        return {
            "persona_id": persona_id,
            "history_count": count,
            "total_versions": count + 1,  # +1 for current version
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching history count: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching history count: {str(e)}")


@router.get("/persona-prompts-all")
async def list_all_persona_prompts_versioned(
    include_inactive: bool = False, db: AsyncSession = Depends(get_db)
):
    """
    List all persona prompts (current versions only).
    Optional inclusion of inactive prompts.
    """
    try:
        query = select(PersonaPrompt)

        if not include_inactive:
            query = query.where(PersonaPrompt.is_active == True)

        query = query.order_by(PersonaPrompt.updated_at.desc())

        result = await db.execute(query)
        prompts = result.scalars().all()

        return {
            "total_found": len(prompts),
            "include_inactive": include_inactive,
            "persona_prompts": [PersonaPromptResponse(**prompt.__dict__) for prompt in prompts],
        }

    except Exception as e:
        logger.error(f"Error listing persona prompts: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing persona prompts: {str(e)}")


class ChangeIsDynamicRequest(BaseModel):
    persona_id: UUID
    is_dynamic: bool

    model_config = {"populate_by_name": True}


class CreateConversationFlowRequest(BaseModel):
    """Request model for creating conversation flow and example conversations."""

    user_id: UUID = Field(..., description="UUID of the user (for ownership validation)")
    persona_id: UUID = Field(..., description="UUID of the persona")
    chat_objective: str = Field(..., description="Chat objective to base conversation flow on")


class CreateConversationFlowResponse(BaseModel):
    """Response model for conversation flow creation."""

    status: str
    persona_id: str
    chat_objective: str
    conversation_flow: str
    objective_response: str
    message: str


class CreateAdvancedPromptRequest(BaseModel):
    """Request model for creating advanced prompt."""

    persona_id: UUID = Field(..., description="UUID of the persona")
    user_id: UUID = Field(..., description="UUID of the user (for ownership validation)")
    db_update: bool = Field(
        True, description="Whether to update PersonaPrompt table (default: True)"
    )
    sample_questions: Optional[List[str]] = Field(
        None, description="Optional list of sample questions for example responses"
    )
    template: str = Field("basic", description="Template type for the prompt (default: 'basic')")
    template_expertise: Optional[str] = Field(
        "general", description="Specific expertise area (default: 'general')"
    )
    platform: str = Field("openai", description="Platform type for the prompt (default: 'openai')")
    chat_objective: Optional[str] = Field(
        None, description="Chat objective for conversation flow generation"
    )
    response_structure: Optional[str] = Field(
        None, description="Custom response structure (JSON string or text)"
    )
    role: Optional[str] = Field(
        None,
        description="Professional role to save in Persona table (also enhances conversation flow context)",
    )
    expertise: Optional[str] = Field(None, description="Expertise area to save in Persona table")
    description: Optional[str] = Field(None, description="Description to save in Persona table")
    strict_guidelines: Optional[str] = Field(
        None, description="Custom strict guidelines for persona behavior (if None, uses default)"
    )
    target_audience: Optional[str] = Field(None, description="Target audience for the persona")


class CreateAdvancedPromptResponse(BaseModel):
    """Response model for advanced prompt creation."""

    status: str
    persona_id: str
    user_id: str
    introduction: str
    expertise_primary: List[str]
    expertise_secondary: List[str]
    communication_style: Dict[str, Any]
    example_responses_count: int
    db_updated: bool
    strict_guidelines: str
    message: str


@router.post("/create-advanced-prompt", response_model=CreateAdvancedPromptResponse)
async def create_advanced_prompt(
    req: CreateAdvancedPromptRequest, db: AsyncSession = Depends(get_db)
):
    """
    Create an advanced prompt for a persona using the new table architecture.

    This endpoint generates:
    - Introduction (from LinkedIn basic info and experiences)
    - Expertise areas (from LinkedIn data)
    - Communication style (from LinkedIn posts, Twitter, documents, websites)
    - Example responses (based on style and expertise)
    - Example prompt (using OpenAI LLM with role from request or LinkedIn, and raw content chunks)
    - Conversation flow and objective response (if chat_objective provided)

    When db_update=True:
    - Generates example_prompt using role from request parameter or LinkedIn repository
    - If PersonaPrompt exists: Archives current version to PersonaPromptHistory with 'UPDATE' operation, then updates
    - If PersonaPrompt doesn't exist: Creates new PersonaPrompt record (no history entry for new records)
    - All changes are committed atomically

    Args:
        req: Request containing:
            - persona_id: UUID of the persona
            - user_id: UUID of the user (for ownership validation)
            - db_update: Whether to update PersonaPrompt table (default: True)
            - sample_questions: Optional list of sample questions for example responses
            - template: Template type for the prompt (default: 'basic')
            - expertise: Specific expertise area (default: 'general')
            - platform: Platform type for the prompt (default: 'openai')
            - chat_objective: Optional chat objective for conversation flow generation.
                             If provided, generates custom conversation_flow and objective_response.
                             If null, uses default values.
            - response_structure: Optional custom response structure (JSON string or text).
                                 If null, uses default response structure.
            - role: Optional professional role to save in Persona table and enhance conversation flow context
            - expertise: Optional expertise area to save in Persona table
            - description: Optional description to save in Persona table
        db: Database session

    Returns:
        CreateAdvancedPromptResponse with generated content and status

    Raises:
        HTTPException 404: If persona not found or user not authorized
        HTTPException 500: If generation fails
    """
    from shared.rag.advanced_prompt_creator import AdvancedPromptCreator

    logger.info(f"Creating advanced prompt for persona {req.persona_id}, user {req.user_id}")

    try:
        # Initialize the Advanced Prompt Creator
        creator = AdvancedPromptCreator()

        # Verify persona exists and user has access (with user relationship)
        from sqlalchemy.orm import selectinload

        persona_stmt = (
            select(Persona)
            .options(selectinload(Persona.user))
            .where(Persona.id == req.persona_id, Persona.user_id == req.user_id)
        )
        persona_result = await db.execute(persona_stmt)
        persona = persona_result.scalar_one_or_none()

        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"Persona {req.persona_id} not found or not owned by user {req.user_id}",
            )

        # Generate all components WITHOUT db_update first (we'll handle DB updates with versioning)
        logger.info("Generating introduction...")
        introduction = await creator._generate_introduction(
            db=db, persona_id=req.persona_id, user_id=req.user_id, db_update=False
        )

        logger.info("Analyzing expertise...")
        expertise = await creator._analyze_expertise(
            db=db, persona_id=req.persona_id, user_id=req.user_id, db_update=False
        )

        logger.info("Analyzing communication style...")
        comm_style = await creator._analyze_communication_style(
            db=db, persona_id=req.persona_id, user_id=req.user_id, db_update=False
        )

        logger.info("Generating example responses...")
        example_responses = await creator._generate_example_responses(
            db=db,
            persona_id=req.persona_id,
            expertise=expertise,
            communication_style=comm_style,
            questions=req.sample_questions,
            user_id=req.user_id,
            db_update=False,
        )

        # Initialize strict_guideline (will be set properly if db_update is True)
        strict_guideline = (
            req.strict_guidelines
            if req.strict_guidelines
            else PromptDefaultsService.get_default_strict_guideline()
        )

        # Generate example prompt using call_openai_llm
        logger.info("Generating example prompt...")
        example_prompt = None
        if req.db_update:
            # Get role from request parameter or use priority: Persona > User > LinkedIn
            prompt_role = req.role
            company = None

            if not prompt_role:
                # Priority: Persona > User > LinkedIn
                prompt_role = persona.role  # Try Persona table first
                if not prompt_role and persona.user:
                    prompt_role = persona.user.role  # Try User table if Persona.role is null

                if persona.user:
                    company = persona.user.company  # Get company from User table

                # LinkedIn repository removed; role/company come from user/persona fields only

            # Get description from request parameter or persona
            prompt_description = req.description if req.description else persona.description

            # Get content chunks for RAW text
            from shared.rag.llama_rag import LlamaRAGSystem

            rag_system = LlamaRAGSystem()
            source_record_ids = await rag_system.get_persona_source_record_ids(persona.id)

            content_chunks = []
            if source_record_ids:
                chunks_stmt = select(VoyageLiteEmbedding).where(
                    VoyageLiteEmbedding.source_record_id.in_(source_record_ids)
                )
                chunks_result = await db.execute(chunks_stmt)
                content_chunks = chunks_result.scalars().all()

            raw_text = " ".join([c.text for c in content_chunks]) if content_chunks else ""

            # Fetch prompt template for example
            prompt_template = await fetch_prompt_template(
                db, req.template, req.template_expertise, req.platform
            )
            template_example = prompt_template.example if prompt_template else ""

            # Generate example prompt
            example_prompt = await call_openai_llm(
                persona.name,
                prompt_role or "Expert",
                prompt_description,
                raw_text,
                template_example,
            )

            if not example_prompt:
                logger.warning("Failed to generate example prompt, will be set to None")

        # If db_update is True, archive current version to history and update PersonaPrompt
        if req.db_update:
            logger.info("DB update requested - archiving to history and updating PersonaPrompt...")

            # Fetch prompt template based on request parameters
            prompt_template = await fetch_prompt_template(
                db, req.template, req.template_expertise, req.platform
            )
            prompt_template_id = prompt_template.id if prompt_template else None

            if not prompt_template:
                logger.warning(
                    f"Prompt template not found for template='{req.template}', "
                    f"expertise='{req.template_expertise}', platform='{req.platform}'. "
                    f"Continuing without template reference."
                )

            # Format the data for PersonaPrompt table
            area_of_expertise = creator._format_expertise_areas(expertise)
            combined_thinking_style = creator._combine_communication_styles(comm_style)
            example_responses_markdown = creator._format_example_responses(example_responses)

            # Handle chat_objective and conversation flow
            if req.chat_objective:
                # Generate conversation flow and objective_response based on chat_objective
                logger.info("Generating conversation flow based on provided chat_objective...")

                # Enhance introduction with role if provided
                introduction_for_flow = introduction
                if req.role:
                    introduction_for_flow = f"{introduction}\n\nCurrent Role: {req.role}"

                (
                    conversation_flow,
                    objective_response,
                ) = await generate_conversation_flow_and_examples(
                    introduction=introduction_for_flow,
                    area_of_expertise=area_of_expertise,
                    thinking_style=combined_thinking_style,
                    chat_objective=req.chat_objective,
                )
                chat_objective = req.chat_objective

                if not conversation_flow or not objective_response:
                    logger.warning("Failed to generate conversation flow, using defaults")
                    conversation_flow = creator._get_default_conversation_flow(prompt_template)
                    objective_response = creator._get_default_objective_response(prompt_template)
            else:
                # Use default values when chat_objective is not provided
                # First check prompt_template, then fall back to service defaults
                chat_objective = creator._get_default_chat_objective(prompt_template)
                objective_response = creator._get_default_objective_response(prompt_template)
                conversation_flow = creator._get_default_conversation_flow(prompt_template)

            # Handle response_structure
            if req.response_structure:
                response_structure = req.response_structure
            else:
                response_structure = creator._get_default_response_structure(prompt_template)

            # Update persona fields if provided
            persona_updated = False
            if req.role:
                logger.info(f"Updating persona role to: {req.role}")
                persona.role = req.role
                persona_updated = True

            if req.expertise:
                logger.info(f"Updating persona expertise to: {req.expertise}")
                persona.expertise = req.expertise
                persona_updated = True

            if req.description:
                logger.info("Updating persona description...")
                persona.description = req.description
                persona_updated = True

            if persona_updated:
                persona.updated_at = datetime.now(timezone.utc)

            # Check if PersonaPrompt exists
            prompt_stmt = select(PersonaPrompt).where(PersonaPrompt.persona_id == req.persona_id)
            prompt_result = await db.execute(prompt_stmt)
            existing_prompt = prompt_result.scalar_one_or_none()

            if existing_prompt:
                # Archive current version to history with 'UPDATE' operation, then update
                logger.info(
                    f"Archiving existing PersonaPrompt to history for persona {req.persona_id}..."
                )

                update_data = {
                    "introduction": introduction,
                    "area_of_expertise": area_of_expertise,
                    "thinking_style": combined_thinking_style,
                    "example_responses": example_responses_markdown,
                    "example_prompt": example_prompt,
                    "prompt_template_id": prompt_template_id,
                    "chat_objective": chat_objective,
                    "objective_response": objective_response,
                    "response_structure": response_structure,
                    "conversation_flow": conversation_flow,
                    "strict_guideline": strict_guideline,
                    "target_audience": req.target_audience,
                }

                # Use versioning service to archive and update
                (
                    updated_prompt,
                    history_entry,
                ) = await PersonaPromptHistoryService.update_persona_prompt_with_versioning(
                    db, req.persona_id, update_data
                )

                logger.info(
                    f"PersonaPrompt updated and archived to history version {history_entry.version}"
                )
            else:
                # Create new PersonaPrompt entry (no history entry for new records)
                logger.info(f"Creating new PersonaPrompt for persona {req.persona_id}...")

                new_prompt = PersonaPrompt(
                    persona_id=req.persona_id,
                    introduction=introduction,
                    area_of_expertise=area_of_expertise,
                    thinking_style=combined_thinking_style,
                    example_responses=example_responses_markdown,
                    example_prompt=example_prompt,
                    prompt_template_id=prompt_template_id,
                    chat_objective=chat_objective,
                    objective_response=objective_response,
                    response_structure=response_structure,
                    conversation_flow=conversation_flow,
                    strict_guideline=strict_guideline,
                    target_audience=req.target_audience,
                    is_active=True,
                    is_dynamic=False,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )

                db.add(new_prompt)
                logger.info(f"New PersonaPrompt created for persona {req.persona_id}")

            # Commit all changes
            await db.commit()
            logger.info("Database changes committed successfully")

        logger.info(f"Advanced prompt created successfully for persona {req.persona_id}")

        # Build response
        return CreateAdvancedPromptResponse(
            status="success",
            persona_id=str(req.persona_id),
            user_id=str(req.user_id),
            introduction=introduction,
            expertise_primary=expertise.primary,
            expertise_secondary=expertise.secondary,
            communication_style={
                "thinking_style": comm_style.thinking_style,
                "speaking_style": comm_style.speaking_style,
                "writing_style": comm_style.writing_style,
                "catch_phrases": comm_style.catch_phrases,
                "transition_words": comm_style.transition_words,
                "tone_characteristics": comm_style.tone_characteristics,
            },
            example_responses_count=len(example_responses),
            db_updated=req.db_update,
            strict_guidelines=(
                strict_guideline
                if req.db_update
                else PromptDefaultsService.get_default_strict_guideline()
            ),
            message=f"Advanced prompt created successfully. DB {'updated with versioning' if req.db_update else 'not updated'}.",
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ValueError as e:
        logger.error(f"Validation error creating advanced prompt: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating advanced prompt: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create advanced prompt: {str(e)}")


@router.post("/change-is-dynamic")
async def change_is_dynamic(req: ChangeIsDynamicRequest, db: AsyncSession = Depends(get_db)):
    """
    Toggle is_dynamic flag for a persona prompt without creating a history entry.
    This does not create or update version history by design.
    """
    # Convert persona_id string to UUID
    try:
        persona_id_uuid = str_to_uuid(req.persona_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid persona_id format")

    prompt = await fetch_persona_prompt(db, persona_id_uuid)
    if not prompt:
        raise HTTPException(status_code=404, detail="Persona prompt not found")
    prompt.is_dynamic = bool(req.is_dynamic)
    prompt.updated_at = datetime.utcnow()
    await db.commit()
    return {
        "status": "success",
        "action": "is_dynamic_changed",
        "persona_id": req.persona_id,
        "is_dynamic": prompt.is_dynamic,
    }


@router.post("/create-conversation-flow", response_model=CreateConversationFlowResponse)
async def create_conversation_flow(
    req: CreateConversationFlowRequest, db: AsyncSession = Depends(get_db)
):
    """
    Create conversation flow and example conversations for a persona based on chat objective.

    This endpoint:
    1. Fetches the persona and validates ownership
    2. Retrieves persona prompt with introduction, area_of_expertise, and thinking_style
    3. Calls OpenAI GPT-4o to generate:
       - Conversation flow (max 100 words, point-wise format)
       - Example conversations (2-3 examples demonstrating the flow)
    4. Saves chat_objective, conversation_flow, and objective_response to PersonaPrompt table
    5. All operations are in a single database transaction with rollback on error

    Args:
        req: Request containing user_id, persona_id, and chat_objective
        db: Database session

    Returns:
        CreateConversationFlowResponse with generated content and status

    Raises:
        HTTPException 400: If persona_id or user_id is invalid
        HTTPException 403: If user doesn't own the persona
        HTTPException 404: If persona or persona prompt not found
        HTTPException 500: If generation fails
    """
    logger.info(
        f"Creating conversation flow for persona {req.persona_id}, user {req.user_id}, objective: {req.chat_objective[:50]}..."
    )

    try:
        # Convert UUIDs
        try:
            persona_id_uuid = str_to_uuid(req.persona_id)
            user_id_uuid = str_to_uuid(req.user_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid UUID format: {str(e)}")

        # Fetch persona and validate ownership
        persona_stmt = select(Persona).where(Persona.id == persona_id_uuid)
        persona_result = await db.execute(persona_stmt)
        persona = persona_result.scalar_one_or_none()

        if not persona:
            raise HTTPException(status_code=404, detail="Persona not found")

        if persona.user_id != user_id_uuid:
            raise HTTPException(status_code=403, detail="User does not have access to this persona")

        # Fetch persona prompt with row-level lock to prevent race conditions
        # This ensures no concurrent updates can modify the prompt while we're generating content
        prompt_stmt = (
            select(PersonaPrompt)
            .where(
                and_(PersonaPrompt.persona_id == persona_id_uuid, PersonaPrompt.is_active == True)
            )
            .with_for_update()  # Lock row until transaction completes
        )
        prompt_result = await db.execute(prompt_stmt)
        prompt = prompt_result.scalar_one_or_none()

        if not prompt:
            raise HTTPException(
                status_code=404,
                detail="Persona prompt not found. Please create a prompt first using /create-prompt-for-persona",
            )

        # Validate required fields
        if not prompt.introduction:
            raise HTTPException(
                status_code=400,
                detail="Persona prompt missing 'introduction'. Please update the prompt first.",
            )

        # Get fields (use defaults if missing)
        introduction = prompt.introduction
        area_of_expertise = prompt.area_of_expertise or "General expertise"
        thinking_style = prompt.thinking_style or "Analytical and thoughtful"

        logger.info(
            f"Generating conversation flow with: intro={len(introduction)} chars, expertise={area_of_expertise[:50]}, style={thinking_style[:50]}"
        )

        # Generate conversation flow and examples using OpenAI
        conversation_flow, objective_response = await generate_conversation_flow_and_examples(
            introduction=introduction,
            area_of_expertise=area_of_expertise,
            thinking_style=thinking_style,
            chat_objective=req.chat_objective,
        )

        if not conversation_flow or not objective_response:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate conversation flow and examples. Please try again.",
            )

        # Update PersonaPrompt with new fields in a single transaction
        prompt.chat_objective = req.chat_objective
        prompt.conversation_flow = conversation_flow
        prompt.objective_response = objective_response
        prompt.updated_at = datetime.now(timezone.utc)

        # Commit transaction
        await db.commit()
        await db.refresh(prompt)

        logger.info(
            f"Successfully created conversation flow for persona {req.persona_id}. Flow: {len(conversation_flow)} chars, Examples: {len(objective_response)} chars"
        )

        return CreateConversationFlowResponse(
            status="success",
            persona_id=str(req.persona_id),
            chat_objective=req.chat_objective,
            conversation_flow=conversation_flow,
            objective_response=objective_response,
            message="Conversation flow and example conversations created successfully",
        )

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        capture_exception_with_context(
            e,
            extra={
                "persona_id": str(req.persona_id),
                "user_id": str(req.user_id),
                "chat_objective_length": len(req.chat_objective),
                "chat_objective_preview": req.chat_objective[:100],  # Truncate to avoid PII
            },
            tags={
                "component": "prompt_generation",
                "operation": "create_conversation_flow_endpoint",
                "severity": "high",
                "user_facing": "true",
            },
        )
        logger.error(f"Error creating conversation flow: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create conversation flow: {str(e)}")


# -------------------- Suggested Questions Generation -------------------- #


async def generate_suggested_questions_with_llm(
    persona_prompt: PersonaPrompt,
    persona: Persona,
    role: Optional[str],
    company: Optional[str],
    num_questions: int = 5,
) -> List[str]:
    """
    Generate suggested starter questions using OpenAI based on persona prompt fields.

    Uses all persona_prompt fields:
    - introduction: Persona background
    - area_of_expertise: Domain focus
    - chat_objective: Conversation goal
    - objective_response: Strategy for engagement
    - thinking_style: Communication style
    - target_audience: Who they talk to
    - response_structure: Response preferences (for temperature)

    Args:
        persona_prompt: PersonaPrompt with all configuration fields
        persona: Persona model with basic info
        role: Current professional role
        company: Current company
        num_questions: Number of questions to generate (1-10)

    Returns:
        List of suggested question strings
    """
    # Parse response_structure for temperature
    response_structure = {}
    if persona_prompt.response_structure:
        try:
            response_structure = json.loads(persona_prompt.response_structure)
        except Exception as e:
            logger.warning(f"Failed to parse response_structure: {e}")
            response_structure = {}

    # Map creativity to temperature
    creativity = response_structure.get("creativity", "adaptive")
    temperature = {"strict": 0.3, "adaptive": 0.7, "creative": 0.9}.get(creativity, 0.7)

    # Build LLM prompt
    llm_prompt = f"""You are helping generate suggested starter questions for a digital persona chat interface.

## Persona Profile

**Name:** {persona.name}
**Role:** {role or "Expert"}
{f"**Company:** {company}" if company else ""}
**Introduction:** {persona_prompt.introduction}

**Area of Expertise:** {persona_prompt.area_of_expertise or "General knowledge"}

**Chat Objective:** {persona_prompt.chat_objective or "Engage in helpful conversations"}

**Target Audience:** {persona_prompt.target_audience or "General audience"}

**Communication Style:** {persona_prompt.thinking_style or "Professional and approachable"}

**Objective Response Strategy:**
{persona_prompt.objective_response or "Respond naturally and authentically based on user needs"}

**Response Preferences:**
- Length: {response_structure.get("response_length", "intelligent")}
- Creativity: {response_structure.get("creativity", "adaptive")}

## Critical: Perspective Rule

These suggested questions will be shown as clickable buttons in the chat UI for VISITORS to start a conversation. They must be written from the VISITOR's perspective — things a visitor would naturally type or say when they first arrive.

**Determine the persona type to get the perspective right:**

- **Knowledge/Expert persona** (teacher, coach, thought leader): The visitor wants to LEARN from the persona. Generate questions the visitor would ASK the expert.
  - Example: "How did you get started in machine learning?"

- **Service/Intake persona** (intake specialist, dispatcher, screener, qualifier, consultant): The visitor HAS A PROBLEM and needs help. Generate things the visitor would SAY to describe their situation or ask about the service.
  - Example: "My AC just stopped working and it's 95 degrees outside"
  - Example: "I was in a car accident and need legal help"
  - Example: "I need help with my business taxes"

Look at the Chat Objective and Role above to determine which type this persona is. If the objective mentions words like "intake", "qualify", "triage", "screen", "capture", "diagnose", "schedule", "dispatch", "assess", "gather information", or "assist users with their problems" — this is a service/intake persona and questions should be from the visitor describing their situation.

## Task

Generate {num_questions} suggested starter questions that:

1. **Written from visitor's perspective**: Things a VISITOR would type to start a conversation (NOT questions the persona would ask the visitor)
2. **Align with expertise**: Relevant to {persona_prompt.area_of_expertise or "the persona's field"}
3. **Support chat objective**: Lead toward {persona_prompt.chat_objective or "meaningful engagement"}
4. **Follow strategy**: Enable the objective response strategy described above
5. **Match audience**: Appropriate for {persona_prompt.target_audience or "general audience"}
6. **Vary in specificity**: Mix broad opening statements with specific scenarios
7. **Be inviting**: Natural, conversational, engaging

## Guidelines

- Keep questions/statements concise (8-15 words)
- Make them clickable/actionable
- Write them as things a real visitor would actually type
- For service personas: include a mix of urgent and routine scenarios
- For knowledge personas: include a mix of beginner and advanced questions
- Avoid yes/no questions or closed statements
- Focus on starting meaningful conversations

## Output Format

Return ONLY a JSON array of strings, no additional text:
["Starter 1", "Starter 2", "Starter 3", ...]

## Examples

For a Machine Learning expert (knowledge persona — visitor asks questions):
["How did you get started in machine learning?", "What's the most common ML mistake you see?", "Can you explain transformers in simple terms?"]

For a Sales coach (knowledge persona — visitor asks questions):
["What's your approach to handling objections?", "How do you build trust with new clients?", "What's the biggest sales mistake people make?"]

For an HVAC Dispatcher (service persona — visitor describes their problem):
["My AC just stopped working and it's 95 degrees", "I need to schedule a maintenance tune-up", "My furnace is making a weird grinding noise"]

For a Personal Injury Intake Specialist (service persona — visitor describes their situation):
["I was in a car accident and need legal help", "I got hurt at work — what are my options?", "How do I know if I have a case?"]

For a CPA Screener (service persona — visitor describes their need):
["I need help with my business taxes", "Looking for a CPA for my S-Corp", "My taxes are complicated — investments and rental properties"]
"""

    # Call OpenAI
    service = OpenAIModelService(api_key=settings.openai_api_key)
    service.set_system_prompt(
        "You are a helpful assistant that generates engaging starter questions for chat interfaces. "
        "Always return valid JSON arrays without any markdown formatting or explanations."
    )

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: service.generate_response_raw(
                llm_prompt, temperature=temperature, max_tokens=500
            ),
        )

        output = getattr(response, "output_text", "")

        # Parse JSON response
        # Remove markdown code blocks if present
        output = output.strip()
        if output.startswith("```"):
            lines = output.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Remove last line (```)
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            output = "\n".join(lines)
        output = output.strip()

        questions = json.loads(output)

        if isinstance(questions, list) and len(questions) > 0:
            # Return only requested number of questions
            return [str(q) for q in questions[:num_questions]]
        else:
            raise ValueError("Invalid response format")

    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "persona_id": str(persona.id),
                "num_questions": num_questions,
                "role": role,
                "company": company,
            },
            tags={
                "component": "suggested_questions",
                "operation": "llm_generation",
                "severity": "medium",
                "user_facing": "false",
            },
        )
        logger.error(f"Failed to generate suggested questions: {e}")
        # Fallback generic questions based on expertise
        expertise = persona_prompt.area_of_expertise or "your field"
        fallback = [
            f"How did you get started in {expertise}?",
            f"What's the most important thing someone should know about {expertise}?",
            f"What's a common misconception about {expertise}?",
            "What's the most interesting project you've worked on?",
            "What advice would you give someone starting out?",
        ]
        return fallback[:num_questions]


class SuggestedQuestionsResponse(BaseModel):
    """Response model for suggested questions generation"""

    status: str
    persona_id: UUID
    suggested_questions: List[str]
    generated_at: datetime
    response_settings: Dict[str, Any]
    from_cache: bool
    message: str


@router.get("/personas/{persona_id}/suggested-questions", response_model=SuggestedQuestionsResponse)
async def get_suggested_questions_endpoint(
    persona_id: str,
    num_questions: Optional[int] = Query(
        default=None, ge=1, le=20, description="Number of questions to return (default: all)"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Get cached suggested questions for a persona.

    This endpoint only returns cached questions from the database.
    If no cached questions exist, it returns 404.

    **Use this endpoint when:**
    - You want to fetch existing questions without triggering LLM generation
    - You're displaying questions on page load
    - You want to check if questions exist before deciding to generate

    **Use POST endpoint when:**
    - You want to generate questions if they don't exist
    - You want to force regeneration with new parameters

    **Parameters:**
    - persona_id: UUID of the persona
    - num_questions: Optional number of questions to return (1-20, default: all questions)

    **Returns:**
    - All cached suggested questions with metadata (or limited if num_questions specified)
    - 404 if no cached questions exist
    """
    try:
        # Convert persona_id to UUID
        try:
            persona_id_uuid = str_to_uuid(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        # Get persona with cached questions
        persona_stmt = select(Persona).where(Persona.id == persona_id_uuid)
        persona_result = await db.execute(persona_stmt)
        persona = persona_result.scalar_one_or_none()

        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona not found: {persona_id}")

        # Check if cached questions exist
        if not persona.suggested_questions:
            raise HTTPException(
                status_code=404,
                detail=f"No cached suggested questions found for persona: {persona_id}. Use POST to generate new questions.",
            )

        cached = persona.suggested_questions
        if not isinstance(cached, dict) or "questions" not in cached:
            raise HTTPException(
                status_code=404,
                detail="Invalid cached questions format. Use POST to regenerate.",
            )

        # Return cached questions (all questions if num_questions is None, otherwise limit)
        all_questions = cached["questions"]
        questions = all_questions[:num_questions] if num_questions else all_questions
        logger.info(
            f"Retrieved {len(questions)} cached suggested questions for persona {persona_id} (total available: {len(all_questions)})"
        )

        return SuggestedQuestionsResponse(
            status="success",
            persona_id=persona_id_uuid,
            suggested_questions=questions,
            generated_at=cached.get("generated_at", datetime.now(timezone.utc)),
            response_settings=cached.get("response_settings", {}),
            from_cache=True,
            message=f"Retrieved {len(questions)} cached suggested questions",
        )

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "persona_id": str(persona_id),
                "num_questions": num_questions,
            },
            tags={
                "component": "suggested_questions",
                "operation": "fetch_cached",
                "severity": "low",
                "user_facing": "true",
            },
        )
        logger.error(f"Error fetching cached suggested questions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch suggested questions: {str(e)}"
        )


@router.post(
    "/personas/{persona_id}/suggested-questions", response_model=SuggestedQuestionsResponse
)
async def generate_suggested_questions_endpoint(
    persona_id: str,
    num_questions: int = Query(
        default=5, ge=1, le=10, description="Number of questions to generate"
    ),
    force_regenerate: bool = Query(default=False, description="Force regeneration even if cached"),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate persona-specific suggested questions using LLM.

    This endpoint analyzes the persona's prompt configuration including:
    - Area of expertise
    - Chat objective
    - Objective response strategy
    - Introduction/background
    - Thinking/communication style
    - Target audience
    - Response structure preferences

    Returns a list of contextually relevant starter questions for the chat UI.

    **Caching Strategy:**
    - First request: Generates via LLM and stores in personas.suggested_questions
    - Subsequent requests: Returns cached version (fast)
    - Use force_regenerate=true to refresh cache

    **Parameters:**
    - persona_id: UUID of the persona
    - num_questions: Number of questions to generate (1-10, default: 5)
    - force_regenerate: Force regeneration even if cached (default: false)

    **Returns:**
    - List of suggested questions with generation metadata
    """
    try:
        # Convert persona_id to UUID
        try:
            persona_id_uuid = str_to_uuid(persona_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        # Get persona with user relationship
        from sqlalchemy.orm import selectinload

        persona_stmt = (
            select(Persona).options(selectinload(Persona.user)).where(Persona.id == persona_id_uuid)
        )
        persona_result = await db.execute(persona_stmt)
        persona = persona_result.scalar_one_or_none()

        if not persona:
            raise HTTPException(status_code=404, detail=f"Persona not found: {persona_id}")

        # Check cache first (if not forcing regeneration)
        if not force_regenerate and persona.suggested_questions:
            cached = persona.suggested_questions
            if isinstance(cached, dict) and "questions" in cached:
                logger.info(f"Returning cached suggested questions for persona {persona_id}")
                return SuggestedQuestionsResponse(
                    status="success",
                    persona_id=persona_id_uuid,
                    suggested_questions=cached["questions"][:num_questions],
                    generated_at=cached.get("generated_at", datetime.now(timezone.utc)),
                    response_settings=cached.get("response_settings", {}),
                    from_cache=True,
                    message=f"Returned {len(cached['questions'][:num_questions])} cached suggested questions",
                )

        # Get active persona prompt for generation
        persona_prompt = await fetch_persona_prompt_active(db, persona_id_uuid)

        if not persona_prompt:
            raise HTTPException(
                status_code=404, detail=f"No active persona prompt found for persona: {persona_id}"
            )

        # Get current role and company with priority: Persona > User > LinkedIn
        role = persona.role  # Try Persona table first
        if not role and persona.user:
            role = persona.user.role  # Try User table if Persona.role is null

        company = None
        if persona.user:
            company = persona.user.company  # Get company from User table

        # LinkedIn repository removed; role/company come from user/persona fields only

        # Generate questions using LLM
        logger.info(f"Generating {num_questions} suggested questions for persona {persona_id}")
        questions = await generate_suggested_questions_with_llm(
            persona_prompt, persona, role, company, num_questions
        )

        # Parse response_structure for metadata
        response_settings = {}
        if persona_prompt.response_structure:
            try:
                response_settings = json.loads(persona_prompt.response_structure)
            except Exception:
                pass

        # Store in personas.suggested_questions (cache)
        persona.suggested_questions = {
            "questions": questions,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "response_settings": response_settings,
        }
        await db.commit()

        logger.info(
            f"Successfully generated and cached {len(questions)} questions for persona {persona_id}"
        )

        return SuggestedQuestionsResponse(
            status="success",
            persona_id=persona_id_uuid,
            suggested_questions=questions,
            generated_at=datetime.now(timezone.utc),
            response_settings=response_settings,
            from_cache=False,
            message=f"Generated {len(questions)} suggested questions",
        )

    except HTTPException:
        raise
    except Exception as e:
        capture_exception_with_context(
            e,
            extra={
                "persona_id": str(persona_id),
                "num_questions": num_questions,
                "force_regenerate": force_regenerate,
            },
            tags={
                "component": "suggested_questions",
                "operation": "endpoint_generation",
                "severity": "medium",
                "user_facing": "true",
            },
        )
        logger.error(f"Error generating suggested questions: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate suggested questions: {str(e)}"
        )


# -------------------- Chat Config Generation -------------------- #


class GenerateChatConfigRequest(BaseModel):
    """Request model for generating chat objective and target audience using LLM."""

    persona_name: str = Field(..., description="Name of the persona")
    role: str = Field(..., description="Professional role/title")
    expertise: str = Field(..., description="Areas of expertise")
    description: Optional[str] = Field(None, description="Optional persona description")


class GenerateChatConfigResponse(BaseModel):
    """Response model for generated chat configuration."""

    status: str
    chat_objective: str
    target_audience: str
    message: str


@router.post("/generate-chat-config", response_model=GenerateChatConfigResponse)
async def generate_chat_config(request: GenerateChatConfigRequest):
    """
    Generate chat objective and target audience using LLM based on persona details.

    This endpoint takes basic persona information (name, role, expertise) and uses
    an LLM to generate appropriate chat_objective and target_audience values for
    persona creation.

    Args:
        request: GenerateChatConfigRequest with persona details

    Returns:
        GenerateChatConfigResponse with generated chat_objective and target_audience
    """
    # expertise_generation_service has been removed
    raise HTTPException(
        status_code=501,
        detail="Chat config generation is not available in this version.",
    )
