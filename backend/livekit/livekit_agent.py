"""
Modular LiveKit Agent - Clean Architecture

This is the production LiveKit agent using composition pattern (~500 lines).

Key Architecture:
- WorkflowHandler: All workflow logic (linear + conversational)
- ToolHandler: All function tools (search, fetch, calendar)
- SessionContext: Conversation tracking
- Main agent: Orchestration only, delegates to handlers

Created: 2026-01-25
"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional
from uuid import UUID

from livekit.agents import Agent, function_tool, llm
from livekit.agents.voice.agent import ModelSettings
from livekit.plugins import cartesia, deepgram, elevenlabs, openai

# Import our modular handlers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from livekit.constants import (
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
from livekit.handlers import (
    ContentHandler,
    DefaultCaptureHandler,
    DocumentHandler,
    EmailCaptureHandler,
    LifecycleHandler,
    SessionContext,
    ToolHandler,
    create_workflow_handler,
)
from livekit.managers import ConversationManager, PromptManager, RAGManager
from livekit.utils import with_docstring
from shared.config import settings
from shared.monitoring.sentry_utils import capture_exception_with_context
from shared.schemas.livekit import PersonaPromptMetadata

logger = logging.getLogger(__name__)


class ModularPersonaAgent(Agent):
    """Clean, modular LiveKit agent using composition pattern.

    Architecture:
    - Delegates workflows to WorkflowHandler
    - Delegates tools to ToolHandler
    - Uses SessionContext for conversation tracking
    - Main agent focuses on LLM orchestration only

    Supports both Voice and Text modes with unified pipeline.
    """

    def __init__(
        self,
        persona_username: str,
        persona_info: Dict[str, Any],
        persona_prompt_info: Optional[PersonaPromptMetadata],
        patterns_info: Dict[str, Any],
        room_name: str,
        room: Any = None,
        session_token: Optional[str] = None,
        prewarmed_vad: Any = None,
        email_capture_settings: Optional[Dict[str, Any]] = None,
        calendar_config: Optional[Dict[str, Any]] = None,
        workflow_data: Optional[Dict[str, Any]] = None,
        default_capture_enabled: bool = True,
        content_mode_enabled: bool = False,
        tts_platform: Optional[str] = None,
        text_only_mode: bool = False,
        owner_user_id: Optional[str] = None,
    ):
        """Initialize modular agent with handlers."""

        # Basic setup
        self.persona_username = persona_username
        self.persona_info = persona_info
        self.persona_prompt_info = persona_prompt_info
        self.room_name = room_name
        self.room = room
        self.session_token = session_token
        self.persona_id = UUID(persona_info.get("id"))
        self.text_only_mode = text_only_mode
        self.owner_user_id = owner_user_id
        self.tts_platform = tts_platform

        # RAG system
        self.rag_system = None

        # Store workflow availability for conditional tool registration
        self.has_workflow = workflow_data is not None
        self.workflow_data = workflow_data

        # Default capture: controlled by orchestrator signal
        # Enabled when no conversational workflow is active (orchestrator computes this)
        self.has_default_capture = default_capture_enabled
        self.has_content_mode = content_mode_enabled

        # NOTE: Agent session is managed by parent Agent class
        # Access via self.session property (set automatically by AgentSession.start())

        logger.info("=" * 60)
        logger.info(f"🎨 [MODULAR AGENT] Initializing: {persona_username}")
        logger.info(f"🎨 [MODULAR AGENT] Mode: {'Text-Only' if text_only_mode else 'Voice'}")
        logger.info(f"🎨 [MODULAR AGENT] Owner: {owner_user_id}")
        logger.info("=" * 60)

        # ===================================================================
        # Initialize Modular Handlers (Composition Pattern)
        # ===================================================================

        # 1. WorkflowHandler - All workflow logic (factory creates appropriate handler)
        self.workflow_handler = create_workflow_handler(
            workflow_data=workflow_data,
            persona_id=self.persona_id,
            output_callback=self._output_message,
            text_only_mode=text_only_mode,
            session_token=session_token,
        )
        if self.workflow_handler:
            logger.info(f"✅ [MODULAR] {type(self.workflow_handler).__name__} initialized")
        else:
            logger.info("✅ [MODULAR] No workflow configured")

        # Build dynamic docstring for update_lead_field based on workflow or default capture
        # Try to update function tool info if available, otherwise update __doc__
        if self.has_default_capture:
            # Default capture takes priority for docstring — it defines the 3 fields
            # (name, email, phone) that the LLM needs to know about.
            # This applies even when a scored/linear workflow is also active.
            from livekit.handlers.default_capture_handler import DEFAULT_CAPTURE_FIELDS

            dynamic_doc = build_update_lead_field_doc(DEFAULT_CAPTURE_FIELDS, [])
            try:
                # Try to access _info attribute (livekit-agents 1.3.12+)
                self.update_lead_fields._info.description = dynamic_doc
            except AttributeError:
                # Fallback: update __doc__ directly
                self.update_lead_fields.__doc__ = dynamic_doc
            logger.info("✅ [MODULAR] Dynamic docstring built for default capture (3 fields)")
        elif workflow_data:
            # Conversational workflow with its own fields
            required_fields = workflow_data.get("required_fields", [])
            optional_fields = workflow_data.get("optional_fields", [])
            dynamic_doc = build_update_lead_field_doc(required_fields, optional_fields)
            try:
                # Try to access _info attribute (livekit-agents 1.3.12+)
                self.update_lead_fields._info.description = dynamic_doc
            except AttributeError:
                # Fallback: update __doc__ directly
                self.update_lead_fields.__doc__ = dynamic_doc
            logger.info(
                f"✅ [MODULAR] Dynamic docstring built with {len(required_fields)} required, "
                f"{len(optional_fields)} optional fields"
            )

        # 2. ToolHandler - All function tools
        # Content mode always needs search for research before drafting
        search_enabled = bool(settings.brave_search_api_key) or self.has_content_mode
        calendar_enabled = calendar_config.get("enabled", False) if calendar_config else False

        self.tool_handler = ToolHandler(
            room=room,
            search_enabled=search_enabled,
            calendar_enabled=calendar_enabled,
            calendar_url=calendar_config.get("url") if calendar_config else None,
            calendar_display_name=calendar_config.get("display_name") if calendar_config else None,
        )
        logger.info("✅ [MODULAR] ToolHandler initialized")

        # 3. SessionContext - Conversation tracking
        self.session_context = SessionContext(session_token or "default", self.persona_id)
        logger.info("✅ [MODULAR] SessionContext initialized")

        # 4. DocumentHandler - Document upload and processing
        self.document_handler = DocumentHandler(
            persona_id=self.persona_id,
            session_token=session_token or "default",
            room=room,
            session_context=self.session_context,
            text_only_mode=text_only_mode,
            output_callback=self._output_message,
        )
        logger.info("✅ [MODULAR] DocumentHandler initialized")

        # 5. EmailCaptureHandler - Lead generation
        self.email_capture_handler = EmailCaptureHandler(
            persona_id=self.persona_id,
            room=room,
            email_capture_settings=email_capture_settings,
        )
        logger.info("✅ [MODULAR] EmailCaptureHandler initialized")

        # 5b. DefaultCaptureHandler - Always-on basic lead capture (name, email, phone)
        if self.has_default_capture:
            self.default_capture_handler = DefaultCaptureHandler(
                persona_id=self.persona_id,
                room=room,
                session_token=session_token,
            )
            logger.info("✅ [MODULAR] DefaultCaptureHandler initialized")
        else:
            self.default_capture_handler = None
            logger.info(
                "✅ [MODULAR] DefaultCaptureHandler skipped (conversational workflow handles capture)"
            )

        # 6. LifecycleHandler - Agent lifecycle events
        self.lifecycle_handler = LifecycleHandler(
            persona_id=self.persona_id,
            persona_info=persona_info,
            room=room,
            room_name=room_name,
        )
        logger.info("✅ [MODULAR] LifecycleHandler initialized")

        # 6b. ContentHandler - Content creation (when content_mode_enabled)
        if self.has_content_mode:
            self.content_handler = ContentHandler(
                room=room,
                persona_info=persona_info,
                persona_prompt_info=persona_prompt_info,
                persona_id=self.persona_id,
                rag_system=self.rag_system,  # None initially, updated after async init
            )
            logger.info("✅ [MODULAR] ContentHandler initialized")
        else:
            self.content_handler = None

        # Store last search result for passing to content generation
        self._last_search_result: str = ""

        # ===================================================================
        # Initialize Context Managers
        # ===================================================================

        # 7. PromptManager - System prompt building
        self.prompt_manager = PromptManager(
            persona_info=persona_info,
            persona_prompt_info=persona_prompt_info,
            workflow_data=workflow_data,
            text_only_mode=text_only_mode,
            default_capture_enabled=self.has_default_capture,
            content_mode_enabled=self.has_content_mode,
        )
        logger.info("✅ [MODULAR] PromptManager initialized")

        # 8. RAGManager - RAG context injection
        self.rag_manager = RAGManager(
            persona_id=self.persona_id,
            session_context=self.session_context,
            lifecycle_handler=self.lifecycle_handler,
            rag_system=self.rag_system,
        )
        logger.info("✅ [MODULAR] RAGManager initialized")

        # 9. ConversationManager - Conversation history
        self.conversation_manager = ConversationManager(
            session_context=self.session_context,
            email_capture_handler=self.email_capture_handler,
            persona_id=self.persona_id,
            session_token=session_token,
            text_only_mode=text_only_mode,
        )
        logger.info("✅ [MODULAR] ConversationManager initialized")

        # ===================================================================
        # Initialize TTS/STT/Agent
        # ===================================================================

        # Get language
        persona_language = persona_info.get("language", "auto")

        # Get voice ID
        voice_id = persona_info.get("voice_id")
        if not voice_id:
            tts_platform = "cartesia"
            voice_id = settings.cartesia_voice_id
            logger.info(f"🎙️ Using default Cartesia voice: {voice_id}")

        # Guard: tts_platform should not be None
        if not tts_platform:
            tts_platform = "cartesia"  # Default to cartesia
            logger.info("🎙️ TTS platform not specified, defaulting to Cartesia")

        # Initialize TTS/STT (skip in text-only mode)
        tts_instance = None
        stt_instance = None
        if not text_only_mode:
            tts_instance = self._initialize_tts(tts_platform, voice_id, persona_language)
            stt_instance = self._initialize_stt(persona_language)

        # Initialize Agent
        init_args = {
            "instructions": f"You are {persona_info['name']}, {persona_info['role']}.",
            "llm": openai.LLM(
                model="gpt-4.1-mini",
                tool_choice="auto",
                parallel_tool_calls=False,
                max_completion_tokens=4096,
            ),
        }

        if not text_only_mode:
            init_args["vad"] = prewarmed_vad
            if stt_instance:
                init_args["stt"] = stt_instance
            if tts_instance:
                init_args["tts"] = tts_instance

        super().__init__(**init_args)

        # Log which function tools are registered (safely)
        tool_methods = []
        for name in dir(self):
            try:
                attr = getattr(self, name)
                # LiveKit marks function tools with __livekit_tool_info attribute
                if callable(attr) and (
                    hasattr(attr, "__livekit_tool_info") or hasattr(attr, "__livekit_raw_tool_info")
                ):
                    tool_methods.append(name)
            except (RuntimeError, AttributeError):
                # Skip properties that require activity context
                pass

        logger.info(f"🔧 [MODULAR AGENT] Registered @function_tool methods: {tool_methods}")
        logger.info(f"🔧 [MODULAR AGENT] Total tools: {len(tool_methods)}")

        # CRITICAL: Filter tools based on workflow type to prevent LLM confusion
        # The parent Agent class discovered ALL tools, but we need to expose only relevant ones
        filtered_tools = []
        tools_to_remove = []

        if self.workflow_handler:
            workflow_type = self.workflow_handler.workflow_type
            logger.info(f"🔧 [MODULAR AGENT] Workflow type: {workflow_type}")

            for tool in self._tools:
                tool_name = tool.__name__ if hasattr(tool, "__name__") else str(tool)

                if workflow_type == "conversational":
                    # Conversational: REMOVE linear tools
                    if tool_name in ["start_assessment", "submit_workflow_answer"]:
                        tools_to_remove.append(tool_name)
                        continue
                elif workflow_type in ("linear", "scored", "simple"):
                    # Linear/scored: REMOVE conversational-only tools
                    # But KEEP update_lead_fields when default capture is enabled
                    if tool_name == "confirm_lead_capture":
                        tools_to_remove.append(tool_name)
                        continue
                    if tool_name == "update_lead_fields" and not self.has_default_capture:
                        tools_to_remove.append(tool_name)
                        continue

                filtered_tools.append(tool)

        elif self.has_default_capture:
            # No workflow but default capture: KEEP update_lead_fields, REMOVE workflow-only tools
            logger.info("🔧 [MODULAR AGENT] Default capture mode — filtering tools")

            for tool in self._tools:
                tool_name = tool.__name__ if hasattr(tool, "__name__") else str(tool)

                if tool_name in [
                    "start_assessment",
                    "submit_workflow_answer",
                    "confirm_lead_capture",
                ]:
                    tools_to_remove.append(tool_name)
                    continue

                filtered_tools.append(tool)

        else:
            # No workflow and no capture — remove all workflow/capture tools
            logger.info(
                "🔧 [MODULAR AGENT] No workflow or capture — filtering capture/workflow tools"
            )
            for tool in self._tools:
                tool_name = tool.__name__ if hasattr(tool, "__name__") else str(tool)
                if tool_name in [
                    "start_assessment",
                    "submit_workflow_answer",
                    "update_lead_fields",
                    "confirm_lead_capture",
                ]:
                    tools_to_remove.append(tool_name)
                    continue
                filtered_tools.append(tool)

        # Filter out content tool when content mode is not enabled
        if not self.has_content_mode:
            pre_count = len(filtered_tools)
            filtered_tools = [
                tool
                for tool in filtered_tools
                if (tool.__name__ if hasattr(tool, "__name__") else str(tool)) != "generate_content"
            ]
            if len(filtered_tools) < pre_count:
                tools_to_remove.append("generate_content")

        self._tools = filtered_tools
        if tools_to_remove:
            logger.info(f"🔧 [MODULAR AGENT] Removed tools: {tools_to_remove}")
        logger.info(
            f"🔧 [MODULAR AGENT] Final tool count: {len(self._tools)} "
            f"(removed {len(tools_to_remove)})"
        )

        logger.info("🎨 [MODULAR AGENT] Initialization complete!")

    async def initialize(self):
        """
        Async initialization - load RAG system and conversation history.

        Must be called after agent construction to complete setup.
        """
        logger.info("🔄 [MODULAR AGENT] Starting async initialization...")

        # 1. Initialize RAG system
        try:
            from shared.rag.rag_singleton import get_rag_system

            self.rag_system = await get_rag_system()  # ← Must await async function!
            self.rag_manager.update_rag_system(self.rag_system)
            if self.content_handler:
                self.content_handler.update_rag_system(self.rag_system)
            logger.info("✅ RAG system initialized")
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "persona_username": self.persona_username,
                },
                tags={
                    "component": "livekit_agent",
                    "operation": "initialize_rag",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            logger.error(f"❌ Failed to initialize RAG: {e}", exc_info=True)

        # 2. Load conversation history from database (if session_token provided)
        try:
            await self.conversation_manager.load_conversation_history()
            logger.info("✅ Conversation history loaded")
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "session_token": self.session_token,
                },
                tags={
                    "component": "livekit_agent",
                    "operation": "load_conversation_history",
                    "severity": "medium",
                    "user_facing": "false",
                },
            )
            logger.error(f"❌ Failed to load conversation history: {e}", exc_info=True)

        logger.info("✅ [MODULAR AGENT] Async initialization complete!")

    @staticmethod
    def _build_localized_greeting(name: str, role: str, language: str) -> str:
        """Build a greeting in the appropriate language using templates."""
        greeting_templates = {
            "en": "Hey! I'm {name}{role_part}. How can I help you today?",
            "hi": "नमस्ते! मैं {name} हूँ{role_part}। मैं आज आपकी कैसे मदद कर सकता हूँ?",
            "es": "¡Hola! Soy {name}{role_part}. ¿En qué puedo ayudarte hoy?",
            "fr": "Bonjour ! Je suis {name}{role_part}. Comment puis-je vous aider aujourd'hui ?",
            "zh": "你好！我是{name}{role_part}。今天我能帮你什么？",
            "de": "Hallo! Ich bin {name}{role_part}. Wie kann ich Ihnen heute helfen?",
            "ar": "مرحبًا! أنا {name}{role_part}. كيف يمكنني مساعدتك اليوم؟",
            "it": "Ciao! Sono {name}{role_part}. Come posso aiutarti oggi?",
            "sv": "Hej! Jag är {name}{role_part}. Hur kan jag hjälpa dig idag?",
            "ja": "こんにちは！{name}です{role_part}。今日はどのようにお手伝いできますか？",
            "pt": "Olá! Eu sou {name}{role_part}. Como posso ajudá-lo hoje?",
            "nl": "Hallo! Ik ben {name}{role_part}. Hoe kan ik je vandaag helpen?",
            "ko": "안녕하세요! 저는 {name}입니다{role_part}. 오늘 어떻게 도와드릴까요?",
            "pl": "Cześć! Jestem {name}{role_part}. Jak mogę Ci dziś pomóc?",
            "el": "Γεια σας! Είμαι ο/η {name}{role_part}. Πώς μπορώ να σας βοηθήσω σήμερα;",
            "cs": "Ahoj! Jsem {name}{role_part}. Jak vám mohu dnes pomoci?",
        }

        # Build role part based on language
        role_part = f", {role}" if role else ""

        template = greeting_templates.get(language, greeting_templates["en"])
        return template.format(name=name, role_part=role_part)

    def _initialize_tts(self, tts_platform: str, voice_id: str, language: str):
        """Initialize TTS based on platform."""
        try:
            if tts_platform == "cartesia":
                if language == "auto":
                    cartesia_language = None
                else:
                    cartesia_language = settings.cartesia_language_map.get(language, "en")
                logger.info(f"🎙️ Cartesia TTS: {cartesia_language or 'auto-detect'}")
                return cartesia.TTS(voice=voice_id, language=cartesia_language, model="sonic-3")
            else:
                if language != "auto":
                    logger.info("🎙️ ElevenLabs TTS: multilingual")
                    return elevenlabs.TTS(voice_id=voice_id, model="eleven_multilingual_v2")
                else:
                    logger.info("🎙️ ElevenLabs TTS: multilingual (auto)")
                    return elevenlabs.TTS(voice_id=voice_id, model="eleven_multilingual_v2")
        except Exception as e:
            logger.warning(f"⚠️ TTS init failed: {e}")
            return None

    def _initialize_stt(self, language: str):
        """Initialize STT with language support."""
        try:
            language_map = {
                "auto": "multi",
                "en": "en-US",
                "hi": "hi",
                "es": "es",
                "fr": "fr",
                "zh": "zh",
                "de": "de",
                "ar": "ar",
                "sv": "sv",
            }
            deepgram_language = language_map.get(language, "multi")
            logger.info(f"🎤 Deepgram STT: {deepgram_language}")
            return deepgram.STT(language=deepgram_language, model="nova-3")
        except Exception as e:
            logger.warning(f"⚠️ STT init failed: {e}")
            return deepgram.STT()

    # =========================================================================
    # Function Tools - Thin wrappers that delegate to handlers
    # Docstrings are injected from constants/tool_docstrings.py
    # =========================================================================

    @function_tool
    @with_docstring(START_ASSESSMENT_DOC)
    async def start_assessment(self) -> None:
        if not self.workflow_handler:
            return
        if self.workflow_handler.workflow_type == "conversational":
            return
        logger.info("🔧 [TOOL] start_assessment() -> LinearHandler")
        return await self.workflow_handler.start_workflow()

    @function_tool
    @with_docstring(UPDATE_LEAD_FIELD_DOC)
    async def update_lead_fields(self, fields_json: str) -> str:
        """Store one or more lead capture fields. Pass fields as JSON object string."""
        import json

        # Parse the JSON string into a dict
        try:
            fields = json.loads(fields_json)
            if not isinstance(fields, dict):
                return 'Error: fields_json must be a JSON object like {"field_id": "value"}'
        except json.JSONDecodeError as e:
            return f'Error: Invalid JSON - {e}. Use format: {{"field_id": "value"}}'

        # Route to appropriate handler
        # Priority: default capture > conversational workflow
        # (when both exist, e.g. scored/linear workflow + default capture,
        #  the default capture handler owns update_lead_fields)
        if self.has_default_capture and self.default_capture_handler:
            # Default capture for basic contact info (handles late arrivals after completion too)
            logger.info(
                f"🔧 [TOOL] update_lead_fields({list(fields.keys())}) -> DefaultCaptureHandler"
            )
            return await self.default_capture_handler.store_extracted_fields(fields)

        if self.has_workflow and self.workflow_handler:
            # Conversational workflow handles its own fields
            if self.workflow_handler.workflow_type != "conversational":
                return "This tool is for conversational workflows. Use submit_workflow_answer for linear."
            logger.info(
                f"🔧 [TOOL] update_lead_fields({list(fields.keys())}) -> ConversationalHandler"
            )
            if not self.workflow_handler.is_active:
                await self.workflow_handler.start_workflow(send_opening_message=False)
            return await self.workflow_handler.store_extracted_fields(fields)

        return "No lead capture configured."

    @function_tool
    @with_docstring(CONFIRM_LEAD_CAPTURE_DOC)
    async def confirm_lead_capture(self) -> str:
        logger.info("🔧 [TOOL] confirm_lead_capture() -> ConversationalHandler")
        if not self.has_workflow or not self.workflow_handler:
            return "No workflow configured."
        if not self.workflow_handler.is_active:
            return "No active workflow session to confirm."
        from shared.database.models.database import async_session_maker
        from shared.database.repositories.workflow_repository import WorkflowRepository

        async with async_session_maker() as session:
            workflow_repo = WorkflowRepository(session)
            workflow_session = await workflow_repo.get_session_by_id(
                self.workflow_handler._workflow_session_id
            )
            extracted_fields = workflow_session.extracted_fields or {} if workflow_session else {}
        return await self.workflow_handler.complete_workflow(extracted_fields)

    @function_tool
    @with_docstring(SUBMIT_WORKFLOW_ANSWER_DOC)
    async def submit_workflow_answer(self, answer: str) -> str:
        if not self.workflow_handler:
            return ""
        if self.workflow_handler.workflow_type == "conversational":
            return "This tool is for linear workflows. Use update_lead_fields for conversational."
        logger.info(f"🔧 [TOOL] submit_workflow_answer('{answer}') -> LinearHandler")
        await self.workflow_handler.submit_answer(answer)
        return ""

    @function_tool
    @with_docstring(SEARCH_INTERNET_DOC)
    async def search_internet(self, query: str) -> str:
        logger.info(f"🔧 [TOOL] search_internet('{query}') -> ToolHandler")
        result = await self.tool_handler.search_internet(query)
        # Store search results for content generation (Option A from plan)
        if self.has_content_mode:
            self._last_search_result = result
            result += (
                "\n\n⚠️ NEXT STEP: You MUST now call the `generate_content` tool with "
                "content_type, title, topic, audience, and tone. "
                "The tool will write the full content body for you — do NOT draft it yourself. "
                "Do NOT speak the content aloud — deliver it via the tool."
            )
        return result

    @function_tool
    @with_docstring(FETCH_URL_DOC)
    async def fetch_url(self, url: str) -> str:
        logger.info(f"🔧 [TOOL] fetch_url('{url}') -> delegating to ToolHandler")
        return await self.tool_handler.fetch_url(url)

    @function_tool
    @with_docstring(SEND_CALENDAR_LINK_DOC)
    async def send_calendar_link(self) -> str:
        logger.info("🔧 [TOOL] send_calendar_link() -> ToolHandler")
        return await self.tool_handler.send_calendar_link()

    @function_tool
    @with_docstring(GENERATE_CONTENT_DOC)
    async def generate_content(
        self, content_type: str, title: str, topic: str, audience: str = "", tone: str = ""
    ) -> str:
        logger.info(
            f"🔧 [TOOL] generate_content(type={content_type}, topic={topic[:50]}) -> ContentHandler"
        )
        if not self.content_handler:
            return "Content creation is not enabled for this persona."
        # Pass stored search results automatically (Option A)
        search_context = self._last_search_result
        self._last_search_result = ""  # Clear after use
        return await self.content_handler.generate_content(
            content_type=content_type,
            title=title,
            topic=topic,
            audience=audience,
            tone=tone,
            search_context=search_context,
        )

    # =========================================================================
    # LLM Pipeline
    # =========================================================================

    async def llm_node(
        self,
        chat_ctx: llm.ChatContext,
        tools: list[llm.FunctionTool],
        model_settings: ModelSettings,
    ):
        """Core LLM processing with RAG, workflows, and conversation history."""

        # Log which tools are available to LLM
        # In livekit-agents 1.3.12+, FunctionTool stores name in tool.info.name
        tool_names = [tool.info.name if hasattr(tool, "info") else str(tool) for tool in tools]
        logger.info(f"🔧 [LLM NODE] Available tools ({len(tools)}): {tool_names}")

        # Flush any pending content from a previous tool-call turn.
        # This publishes the blog card at the START of the confirmation turn
        # (when the LLM is about to say "Here's your blog!").
        if self.content_handler:
            await self.content_handler.flush_pending_content()

        try:
            # 1. Inject system prompt via PromptManager
            await self.prompt_manager.inject_system_prompt(chat_ctx)

            # 2. Inject conversation history via ConversationManager
            # History provides conversational continuity (tone, greetings, persona context).
            # Field awareness (what's captured vs missing) is handled by the tool response
            # from store_extracted_fields — it includes a full snapshot of captured values,
            # so the LLM never needs to replay old messages to know what was collected.
            self.conversation_manager.inject_conversation_history(chat_ctx, max_messages=10)

            # 3. Inject workflow options for linear workflows
            if (
                self.workflow_handler
                and self.workflow_handler.is_active
                and self.workflow_handler.workflow_type != "conversational"
            ):
                await self._inject_workflow_options(chat_ctx)

            # 4. RAG retrieval (skip for ALL active workflows — menu/rules are in reference_data)
            if not (self.workflow_handler and self.workflow_handler.is_active):
                await self.rag_manager.inject_rag_context(chat_ctx)

        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "workflow_active": (
                        self.workflow_handler.is_active if self.workflow_handler else False
                    ),
                    "workflow_type": (
                        self.workflow_handler.workflow_type if self.workflow_handler else None
                    ),
                    "num_tools": len(tools),
                },
                tags={
                    "component": "livekit_agent",
                    "operation": "llm_node_setup",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            logger.error(f"Error in llm_node setup: {e}", exc_info=True)

        # Yield LLM response chunks
        collected_response = []
        async for chunk in super().llm_node(chat_ctx, tools, model_settings):
            if hasattr(chunk, "content") and chunk.content:
                collected_response.append(chunk.content)
            yield chunk

        # After LLM completes: Update conversation history
        await self.conversation_manager.update_conversation_history(chat_ctx, collected_response)

    async def _inject_workflow_options(self, chat_ctx: llm.ChatContext):
        """Inject current workflow question options into context for LINEAR workflows.

        This is CRITICAL for semantic matching - without this, the LLM doesn't know
        what options A, B, C, D mean and can't match natural language answers!
        """
        if not self.workflow_data or not self.workflow_handler:
            return

        steps = self.workflow_data.get("steps", [])
        current_step = getattr(self.workflow_handler, "_workflow_current_step", None)

        if current_step is None or current_step >= len(steps):
            return

        step = steps[current_step]

        # Only inject for multiple choice questions
        if step.get("step_type") == "multiple_choice" and step.get("options"):
            options_context = f"""
🚨 WORKFLOW MODE ACTIVE - Step {current_step + 1}/{len(steps)}

📝 CURRENT QUESTION OPTIONS:
"""
            for opt in step["options"]:
                label = opt.get("label", "")
                text = opt.get("text", "")
                options_context += f"  {label}: {text}\n"

            options_context += """
⚠️ MANDATORY: You MUST call submit_workflow_answer with the matched option letter.
Match the user's natural language answer to the closest option above.
DO NOT ask follow-up questions. DO NOT provide commentary. ONLY call the function.
"""

            # Use "system" role so these instructions don't get saved to conversation history
            chat_ctx.items.append(llm.ChatMessage(role="system", content=[options_context]))
            logger.info(f"📋 Injected workflow options into context for step {current_step + 1}")

    async def _output_message(self, message: str, allow_interruptions: bool = True):
        """Output message in text or voice mode."""
        try:
            if self.text_only_mode:
                # Text mode: Send to lk.chat stream (transcription channel)
                if self.room:
                    await self.room.local_participant.send_text(
                        text=message,
                        topic="lk.chat",  # Agent output chat stream
                    )
                    logger.info(f"📤 [TEXT] Sent message: {message[:100]}...")
            else:
                # Voice mode: Use session.say() which handles TTS
                if hasattr(self, "session") and self.session is not None:
                    await self.session.say(message, allow_interruptions=allow_interruptions)
                    logger.info(f"🗣️ [VOICE] Speaking: {message[:100]}...")
                else:
                    logger.warning(f"⚠️ Session not available, cannot speak: {message[:100]}...")
        except Exception as e:
            capture_exception_with_context(
                e,
                extra={
                    "persona_id": str(self.persona_id),
                    "text_only_mode": self.text_only_mode,
                    "message_preview": message[:200],
                },
                tags={
                    "component": "livekit_agent",
                    "operation": "output_message",
                    "severity": "high",
                    "user_facing": "true",
                },
            )
            logger.error(f"❌ Failed to output message: {e}", exc_info=True)

    # =========================================================================
    # Lifecycle Methods
    # =========================================================================

    async def on_enter(self):
        """Called when agent enters the room - send greeting and suggested questions."""
        # Send suggested questions (handled by lifecycle handler)
        await self.lifecycle_handler.send_suggested_questions()

        # Skip greeting in text mode
        if self.text_only_mode:
            logger.info("📝 Text mode: skipping greeting message, using suggested questions only")
            return

        # Greeting: two paths based on whether a custom greeting exists
        custom_greeting = self.persona_info.get("greeting_message")
        language = self.persona_info.get("language", "auto")

        if custom_greeting:
            # DB greeting exists — speak it as-is (persona owner wrote it in their language)
            greeting = custom_greeting
        else:
            # No custom greeting — build a localized greeting using templates
            name = self.persona_info.get("user_fullname") or self.persona_info.get(
                "name", "your AI assistant"
            )
            role = self.persona_info.get("role", "")
            greeting = self._build_localized_greeting(name, role, language)

        logger.info(f"🗣️ Speaking greeting (language={language}): {greeting[:80]}...")
        await self.session.say(greeting, allow_interruptions=True)

    async def on_user_turn_completed(self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage):
        """Called BEFORE LLM generates response - check email capture."""
        user_query = new_message.text_content or ""
        if not user_query.strip():
            await super().on_user_turn_completed(turn_ctx, new_message)
            return

        # Check if email capture should be triggered
        can_continue = await self.email_capture_handler.check_and_trigger()
        if not can_continue:
            # User declined email capture - disconnect
            await self.room.disconnect()
            return

        await super().on_user_turn_completed(turn_ctx, new_message)

    async def on_exit(self):
        """Called when agent exits the room - cleanup resources."""
        await self.lifecycle_handler.on_exit(document_handler=self.document_handler)
        await super().on_exit()
