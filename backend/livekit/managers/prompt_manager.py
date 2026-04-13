"""
Prompt Manager

Handles system prompt building and injection into chat context.

Responsibilities:
- Build cached system prompts from persona data
- Inject workflow objectives if present
- Inject system prompt into chat context

Created: 2026-01-25
"""

import logging
from typing import Any, Dict, Optional

from livekit.agents import llm
from shared.generation.prompts import (
    RULE_ANSWER_ONLY,
    RULE_ANSWER_ONLY_SHORT,
    RULE_STOP_ELABORATE,
    RULE_STOP_WHEN_DONE,
    RULE_TEXT_BREVITY,
    RULE_VOICE_BREVITY,
)
from shared.generation.workflow_promotion_prompts import (
    build_default_capture_system_prompt,
    build_workflow_system_prompt,
)
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.schemas.livekit import PersonaPromptMetadata

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Manages system prompt building and injection.

    Keeps prompts cached for performance and handles workflow integration.
    """

    def __init__(
        self,
        persona_info: Dict[str, Any],
        persona_prompt_info: Optional[PersonaPromptMetadata] = None,
        workflow_data: Optional[Dict[str, Any]] = None,
        text_only_mode: bool = False,
        default_capture_enabled: bool = False,
        content_mode_enabled: bool = False,
    ):
        """
        Initialize prompt manager.

        Args:
            persona_info: Persona information dict
            persona_prompt_info: Optional persona prompt metadata
            workflow_data: Optional workflow configuration
            text_only_mode: Whether agent is in text-only mode (affects prompt building)
            default_capture_enabled: Whether default lead capture is active (no workflow)
            content_mode_enabled: Whether content creation mode is active
        """
        self.persona_info = persona_info
        self.persona_prompt_info = persona_prompt_info
        self.workflow_data = workflow_data
        self.text_only_mode = text_only_mode
        self.default_capture_enabled = default_capture_enabled
        self.content_mode_enabled = content_mode_enabled

        # Cached system prompt (empty string initially, built on first use)
        self._cached_system_prompt: str = ""

        self.logger = logging.getLogger(__name__)

    async def build_system_prompt(self) -> str:
        """
        Build system prompt from persona data.

        Uses PromptTemplates for proper prompt building (same as legacy agent).

        Returns:
            System prompt string
        """
        try:
            from shared.generation.prompts import PromptTemplates

            if self.persona_prompt_info:
                # When a workflow is active: Replace chat_objective with workflow_objective
                # The workflow's purpose IS the chat objective, avoiding duplicate/conflicting objectives
                if self.workflow_data:
                    workflow_objective = self.workflow_data.get("workflow_objective")

                    if workflow_objective:
                        self.logger.info("🔄 Replacing chat_objective with workflow_objective")
                        self.persona_prompt_info.chat_objective = workflow_objective

                # Use PromptTemplates for proper dynamic prompt building
                # This ensures voice/text mode differences are handled
                # Note: PersonaPromptMetadata is structurally compatible with PersonaPrompt
                self._cached_system_prompt = PromptTemplates.build_system_prompt_dynamic(
                    self.persona_prompt_info,  # type: ignore[arg-type]
                    self.persona_info,
                    is_voice=not self.text_only_mode,
                )
            else:
                # Fallback: Generate basic prompt
                self._cached_system_prompt = (
                    f"You are {self.persona_info['name']}, {self.persona_info['role']}."
                )

            # Add current date awareness
            from datetime import datetime

            current_date = datetime.now().strftime("%B %d, %Y")
            self._cached_system_prompt += f"\n\n📅 Today's date is {current_date}. Always use this as your reference for the current year and time context.\n"

            # Add critical RAG usage instructions (same as legacy agent)
            self._cached_system_prompt += """

⚠️ CRITICAL RESPONSE GUIDELINES:
1. ONLY use information from:
   - The provided knowledge base/context
   - Retrieved documents and sources
   - Available function tools (search_internet, fetch_url, calendar, etc.)
   - Uploaded documents from the user

2. NEVER fabricate, guess, or assume information not in your knowledge sources
3. If information is NOT in your context or knowledge base, clearly state:
   "I don't have that information in my knowledge base. Would you like me to search for it?"
4. DO NOT claim capabilities, features, or facts that aren't explicitly in your sources
5. When uncertain, ask clarifying questions or offer to search for information
6. Always cite sources when available and base responses strictly on provided context
"""

            # Add memory awareness
            self._cached_system_prompt += "\n\n🧠 CONVERSATION MEMORY:\n"
            self._cached_system_prompt += (
                "You have access to the full conversation history from this session.\n"
            )

            # Add language instruction
            persona_language = self.persona_info.get("language", "auto")
            if persona_language and persona_language != "auto":
                from shared.config import settings

                language_name = settings.language_names.get(persona_language, persona_language)
                self._cached_system_prompt += f"""
🌐 LANGUAGE INSTRUCTION:
You MUST always respond in {language_name} ({persona_language}). This is mandatory.
- ALL your responses must be in {language_name}, regardless of what language the user writes in.
- Do NOT switch to English or any other language unless the user explicitly asks you to.
- This applies to greetings, answers, follow-up questions, and all other communication.
"""
                self.logger.info(
                    f"🌐 Language instruction added: {language_name} ({persona_language})"
                )
            else:
                # Auto mode: detect and match the user's language
                self._cached_system_prompt += """
🌐 LANGUAGE INSTRUCTION:
- Detect the language the user is speaking or writing in and respond in that SAME language.
- If the user switches languages, follow their lead and switch too.
- Default to English if you cannot determine the user's language.
"""
                self.logger.info("🌐 Language instruction added: auto-detect")

            # Apply flexible response mode if set in workflow config.
            # This relaxes brevity and "answer only what's asked" rules so the
            # agent can upsell, show price breakdowns, and follow workflow
            # instructions that require longer or proactive responses.
            # Must run BEFORE the workflow prompt is appended so the base-prompt
            # rules are already relaxed when the LLM reads the workflow section.
            if self.workflow_data:
                response_mode = self.workflow_data.get("response_mode")
                if response_mode == "flexible":
                    self._cached_system_prompt = self._apply_flexible_mode(
                        self._cached_system_prompt
                    )
                    self.logger.info("🔧 Applied flexible response mode — brevity rules relaxed")

            # Add workflow objective if present
            if self.workflow_data:
                workflow_objective = self.workflow_data.get("workflow_objective")
                if workflow_objective:
                    # Extract workflow type and trigger config
                    workflow_type = self.workflow_data.get("workflow_type", "linear")
                    trigger_config = self.workflow_data.get("trigger_config") or {}
                    promotion_mode = trigger_config.get("promotion_mode", "contextual")
                    max_attempts = trigger_config.get("max_attempts", 3)
                    cooldown_turns = trigger_config.get("cooldown_turns", 5)

                    self.logger.info(
                        f"🔧 [PROMPT] Workflow: type={workflow_type}, promotion_mode={promotion_mode}"
                    )

                    # Get fields and extraction strategy for conversational workflows
                    required_fields = self.workflow_data.get("required_fields", [])
                    optional_fields = self.workflow_data.get("optional_fields", [])
                    extraction_strategy = self.workflow_data.get("extraction_strategy", {})

                    workflow_prompt = build_workflow_system_prompt(
                        workflow_title=self.workflow_data.get("title", workflow_objective),
                        promotion_mode=promotion_mode,
                        workflow_type=workflow_type,
                        max_attempts=max_attempts,
                        cooldown_turns=cooldown_turns,
                        required_fields=required_fields,
                        optional_fields=optional_fields,
                        workflow_objective=workflow_objective,
                        extraction_strategy=extraction_strategy,
                    )

                    # Inject reference_data and agent_instructions into the workflow
                    # prompt block (high-attention zone).
                    workflow_prompt += self._build_config_suffix()

                    self._cached_system_prompt = (
                        f"{self._cached_system_prompt}\n\n{workflow_prompt}"
                    )
                    self.logger.info(
                        f"✅ Added workflow objective to system prompt (type: {workflow_type})"
                    )

                # Fallback: inject reference_data and agent_instructions even when
                # workflow_objective is missing (e.g., workflow has data but no objective).
                if not workflow_objective:
                    self._cached_system_prompt += self._build_config_suffix()

            # Add default capture instructions if capture is enabled
            # This works alongside linear workflows (assessments/quizzes) since they
            # don't capture contact info. Only conversational workflows handle their
            # own capture, and those are already excluded via default_capture_enabled=False.
            if self.default_capture_enabled:
                self._cached_system_prompt = self._apply_capture_prompt_modifications(
                    self._cached_system_prompt
                )
                self.logger.info("✅ Added default lead capture instructions to system prompt")

            # Add content creation instructions if content mode is enabled
            if self.content_mode_enabled:
                from livekit.constants.content_prompts import CONTENT_MODE_SYSTEM_PROMPT

                self._cached_system_prompt += CONTENT_MODE_SYSTEM_PROMPT
                self.logger.info("✅ Added content mode instructions to system prompt")

            self.logger.info(f"✅ System prompt built ({len(self._cached_system_prompt)} chars)")

            return self._cached_system_prompt

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_name": self.persona_info.get("name"),
                    "has_workflow": bool(self.workflow_data),
                    "workflow_type": (
                        self.workflow_data.get("workflow_type") if self.workflow_data else None
                    ),
                },
                tags={
                    "component": "prompt_manager",
                    "operation": "build_system_prompt",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            self.logger.error(f"❌ Failed to build system prompt: {e}", exc_info=True)
            self._cached_system_prompt = f"You are {self.persona_info['name']}."
            return self._cached_system_prompt

    async def inject_system_prompt(self, chat_ctx: llm.ChatContext):
        """
        Inject system prompt into chat context.

        Args:
            chat_ctx: LiveKit chat context
        """
        try:
            # Build if not cached
            if not self._cached_system_prompt:
                await self.build_system_prompt()

            # Inject into chat context
            system_msg = chat_ctx.items[0] if chat_ctx.items else None
            if isinstance(system_msg, llm.ChatMessage) and system_msg.role == "system":
                system_msg.content = [self._cached_system_prompt]
            else:
                chat_ctx.items.insert(
                    0, llm.ChatMessage(role="system", content=[self._cached_system_prompt])
                )

            self.logger.debug("✅ Injected system prompt into chat context")

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_name": self.persona_info.get("name"),
                    "has_cached_prompt": bool(self._cached_system_prompt),
                    "prompt_length": (
                        len(self._cached_system_prompt) if self._cached_system_prompt else 0
                    ),
                },
                tags={
                    "component": "prompt_manager",
                    "operation": "inject_system_prompt",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            self.logger.error(f"❌ Failed to inject system prompt: {e}", exc_info=True)

    def _apply_capture_prompt_modifications(self, prompt: str) -> str:
        """
        Apply default capture modifications to the system prompt.

        This method handles three things:
        1. Inserts a secondary objective note after the Chat Objective section
           so the LLM is aware of capture early in the prompt (high attention zone)
        2. Replaces conflicting behavioral rules with capture-aware versions
           (uses constants from shared.generation.prompts for safe matching)
        3. Appends the full capture instructions at the end as a detailed reference

        All modifications are done here in prompt_manager to keep the shared
        prompt template (PromptTemplates) clean and capture-agnostic.
        """
        # 1. Insert secondary objective note after Chat Objective (before Core Behavior)
        capture_objective_note = (
            "\n\n**Secondary Objective — Lead Capture (MANDATORY):**\n"
            "You MUST capture the visitor's name, email, and phone number during this conversation.\n"
            "- For the first 2 exchanges, focus on being helpful and building rapport.\n"
            "- On your 3rd response, you MUST ask for their name. Do NOT skip this.\n"
            "- After getting their name, ask for email. Then phone.\n"
            "- Use the `update_lead_fields` tool to save each piece of info as you get it.\n"
            "- If the visitor volunteers any contact info at ANY point, capture it immediately.\n"
            "- Do NOT let the conversation go past 3 exchanges without having asked for contact info.\n"
            "- **CRITICAL**: If the visitor says 'yes' to a consultation or next steps, you MUST\n"
            "  collect name/email/phone BEFORE confirming any booking. Do NOT skip this.\n"
            "- ONE QUESTION PER RESPONSE: When asking for contact info, it must be the ONLY question.\n"
            "  Do NOT ask a topic question AND a contact info question in the same response.\n"
            "- IF THE VISITOR IGNORES YOUR ASK: Do NOT move on. Hard gate — re-ask before answering.\n"
            "- See full instructions under '📋 DEFAULT LEAD CAPTURE ACTIVE' below."
        )

        core_behavior_marker = "## 2. Core Behavior"
        if core_behavior_marker in prompt:
            prompt = prompt.replace(
                core_behavior_marker,
                f"{capture_objective_note}\n\n{core_behavior_marker}",
            )

        # 2. Replace conflicting behavioral rules with capture-aware versions.
        # Uses constants from shared.generation.prompts — if the template changes,
        # the constants change too, so these replacements stay in sync.
        # NOTE: Full replacements, not parenthetical additions. The original rules
        # are stated with heavy emphasis (bold, caps, repeated) and weak exceptions
        # get ignored by the LLM. We must match that emphasis level.
        rule_replacements = [
            (
                RULE_ANSWER_ONLY,
                "**Answer what is asked AND proactively collect contact info** — see Lead Capture objective above",
            ),
            (
                RULE_STOP_WHEN_DONE,
                "**After answering, weave in a natural ask for contact info** if you haven't collected name/email/phone yet",
            ),
            (
                RULE_ANSWER_ONLY_SHORT,
                "**Answer what's asked, AND ask for contact info** per the Lead Capture objective — this is mandatory",
            ),
            (
                RULE_VOICE_BREVITY,
                "Target 25-50 words — you may go slightly longer when asking for contact info.",
            ),
            (
                RULE_TEXT_BREVITY,
                "Target 50-100 words — you may go slightly longer when asking for contact info.",
            ),
            (
                RULE_STOP_ELABORATE,
                "After answering, weave in contact info collection if not yet captured — don't skip this",
            ),
        ]

        replacements_applied = 0
        for original, replacement in rule_replacements:
            new_prompt = prompt.replace(original, replacement)
            if new_prompt != prompt:
                replacements_applied += 1
            else:
                self.logger.warning(
                    f"⚠️ Rule replacement had no effect — prompt template may have changed. "
                    f"Rule: {original[:50]}..."
                )
            prompt = new_prompt

        self.logger.info(
            f"🔄 Applied {replacements_applied}/{len(rule_replacements)} capture rule replacements"
        )

        # 3. Append full capture instructions at the end as detailed reference
        default_capture_prompt = build_default_capture_system_prompt()
        prompt = f"{prompt}\n\n{default_capture_prompt}"

        return prompt

    def _build_config_suffix(self) -> str:
        """
        Build the reference_data + agent_instructions suffix from workflow config.

        Returns a string to append to the prompt. Empty string if neither field exists.
        Single source of truth — called from both the workflow_objective path and
        the no-objective fallback path.

        SECURITY NOTE: reference_data and agent_instructions are injected verbatim
        into the system prompt. These fields are currently admin-only (set via
        workflow_config JSON in the database). If these are ever exposed to
        user-editable inputs, they MUST be sanitized to prevent prompt injection.
        """
        suffix = ""

        reference_data = self.workflow_data.get("reference_data") if self.workflow_data else None
        if reference_data:
            suffix += f"\n\n📚 REFERENCE DATA:\n\n{reference_data}"
            self.logger.info(f"✅ Added reference_data to prompt ({len(reference_data)} chars)")

        agent_instructions = (
            self.workflow_data.get("agent_instructions") if self.workflow_data else None
        )
        if agent_instructions:
            suffix += (
                f"\n\n⚠️ THE FOLLOWING RULES OVERRIDE ALL PRIOR "
                f"BEHAVIORAL RULES FOR THIS WORKFLOW SESSION. "
                f"If any earlier instruction conflicts with these "
                f"rules (e.g., 'answer only what is asked', 'stop "
                f"when done', 'no unsolicited advice'), THESE RULES "
                f"TAKE PRECEDENCE.\n\n{agent_instructions}"
            )
            self.logger.info(
                f"✅ Added agent_instructions to prompt ({len(agent_instructions)} chars)"
            )

        return suffix

    def _apply_flexible_mode(self, prompt: str) -> str:
        """
        Relax brevity and 'answer-only' rules in the base persona prompt.

        Called when workflow_config contains response_mode="flexible".
        Replaces strict rules with workflow-friendly versions that allow:
        - Longer responses (price breakdowns, order summaries)
        - Proactive suggestions (upselling, recommendations)
        - Following workflow-specific instructions even when they conflict
          with the default "answer only what is asked" behavior.

        Uses the same constants as _apply_capture_prompt_modifications
        to ensure replacements stay in sync with the prompt template.
        """
        rule_replacements = [
            (
                RULE_ANSWER_ONLY,
                "**Answer what is asked, AND proactively follow your workflow instructions** "
                "— upselling, suggesting items, and showing price breakdowns are all expected",
            ),
            (
                RULE_STOP_WHEN_DONE,
                "**After answering, follow your workflow's next step** "
                "— suggest drinks, sides, or desserts if the workflow calls for it",
            ),
            (
                RULE_ANSWER_ONLY_SHORT,
                "**Answer what's asked, AND follow your workflow instructions** "
                "— proactive suggestions and detailed confirmations are expected",
            ),
            (
                RULE_VOICE_BREVITY,
                "Target 25-60 words for most responses. "
                "You may go longer for order confirmations, price breakdowns, "
                "or when listing menu options — clarity beats brevity.",
            ),
            (
                RULE_TEXT_BREVITY,
                "Target 50-120 words for most responses. "
                "You may go longer for order confirmations, price breakdowns, "
                "or when listing menu options — clarity beats brevity.",
            ),
            (
                RULE_STOP_ELABORATE,
                "After answering, follow your workflow's next step "
                "— don't stop short if the workflow has more to do",
            ),
        ]

        replacements_applied = 0
        for original, replacement in rule_replacements:
            new_prompt = prompt.replace(original, replacement)
            if new_prompt != prompt:
                replacements_applied += 1
            else:
                self.logger.warning(
                    f"⚠️ Flexible mode rule replacement had no effect — "
                    f"prompt template may have changed. Rule: {original[:50]}..."
                )
            prompt = new_prompt

        if replacements_applied == 0:
            self.logger.warning(
                "⚠️ Flexible mode: no rules were replaced — " "base prompt rules may have changed"
            )
        else:
            self.logger.info(
                f"🔧 Flexible mode: replaced {replacements_applied}/{len(rule_replacements)} rules"
            )

        return prompt

    def update_workflow_data(self, workflow_data: Optional[Dict[str, Any]]):
        """
        Update workflow data and invalidate cache.

        Args:
            workflow_data: New workflow configuration
        """
        self.workflow_data = workflow_data
        self._cached_system_prompt = ""  # Invalidate cache
        self.logger.info("🔄 Workflow data updated, prompt cache invalidated")
