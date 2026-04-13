"""
LiveKit Worker Entrypoint

Contains all worker lifecycle functions:
- prewarm(): Prewarm VAD for reduced latency
- entrypoint(): Main worker entrypoint with agent initialization and lifecycle management
- main(): Main function with signal handlers and CLI setup

This file is the entry point for the LiveKit worker process.
It handles all the infrastructure setup while delegating agent logic to ModularPersonaAgent.

Created: 2026-01-25
"""

import logging
import os
import signal
import sys
import threading
import time

from dotenv import load_dotenv

from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli

# Import modular agent
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from livekit.livekit_agent import ModularPersonaAgent
from shared.config import settings

logger = logging.getLogger(__name__)

# =========================================================================
# Threading Exception Hook (for graceful IPC cleanup during shutdown)
# =========================================================================

_original_threading_excepthook = threading.excepthook


def custom_threading_excepthook(args):
    """Handle threading exceptions gracefully, especially IPC cleanup errors"""
    if isinstance(args.exc_value, AttributeError) and "recv" in str(args.exc_value):
        logger.debug(
            f"IPC cleanup race condition detected (expected during shutdown): {args.exc_value}"
        )
    else:
        logger.error(
            f"Exception in thread {args.thread.name}: {args.exc_type.__name__}: {args.exc_value}",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        _original_threading_excepthook(args)


threading.excepthook = custom_threading_excepthook


# =========================================================================
# Worker Functions
# =========================================================================


def prewarm(proc):
    """Prewarm VAD for reduced latency."""
    from livekit.plugins import silero

    # Configure VAD with reduced sensitivity to avoid background noise
    # - activation_threshold: 0.6 (up from default 0.5) - requires higher confidence
    # - min_speech_duration: 0.3s (up from default 0.25s) - longer duration required
    # - min_silence_duration: 0.8s (down from 2.0s) - faster turn detection for voice agents
    proc.userdata["vad"] = silero.VAD.load(
        activation_threshold=0.6,
        min_speech_duration=0.3,
        min_silence_duration=0.8,
    )
    logger.info("✅ Prewarmed VAD")


async def entrypoint(ctx: JobContext):
    """Worker entrypoint - initialize and start agent with full lifecycle management."""
    import asyncio
    import json

    from livekit.agents import AgentSession, metrics
    from livekit.agents.voice import MetricsCollectedEvent, room_io
    from livekit.helpers import extract_persona_data
    from livekit.langfuse_integration import setup_langfuse

    logger.info("🚀 [MODULAR WORKER] Starting job...")

    try:
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        logger.info(f"🏠 Connected to room: {ctx.room.name}")

        # Setup Langfuse tracing
        try:
            trace_provider = setup_langfuse(metadata={"langfuse.session.id": ctx.room.name})
            logger.info("✅ Langfuse tracing enabled")
        except Exception as e:
            logger.error(f"Failed to initialize Langfuse: {e}")
            trace_provider = None

        # Wait for participant if needed
        if len(ctx.room.remote_participants) == 0:
            participant = await ctx.wait_for_participant()
            if not participant:
                raise TimeoutError("No participant joined")

        # Extract persona data from room metadata
        persona_data = await extract_persona_data(ctx)

        if not persona_data:
            logger.error("❌ Failed to extract persona data")
            return

        # Detect text-only mode and owner ID
        text_only_mode = False
        owner_user_id = None
        if ctx.room.remote_participants:
            participant = list(ctx.room.remote_participants.values())[0]
            if participant.metadata:
                try:
                    metadata = json.loads(participant.metadata)
                    text_only_mode = metadata.get("text_only_mode", False)
                    owner_user_id = metadata.get("owner_id")
                except json.JSONDecodeError:
                    pass

        # Create modular agent
        agent = ModularPersonaAgent(
            persona_username=persona_data.expert_username,
            persona_info=persona_data.persona_info,
            persona_prompt_info=persona_data.persona_prompt,
            patterns_info=persona_data.pattern_info,
            room_name=ctx.room.name,
            room=ctx.room,
            session_token=persona_data.session_token,
            prewarmed_vad=ctx.proc.userdata.get("vad"),
            email_capture_settings=persona_data.email_capture_settings,
            calendar_config=persona_data.calendar_config,
            workflow_data=persona_data.workflow_data,
            default_capture_enabled=persona_data.default_capture_enabled,
            content_mode_enabled=persona_data.content_mode_enabled,
            tts_platform=persona_data.tts_platform,
            text_only_mode=text_only_mode,
            owner_user_id=owner_user_id,
        )

        # Initialize agent (async setup: RAG + conversation history)
        await agent.initialize()

        # ===================================================================
        # Define Shutdown Callbacks (order matters!)
        # ===================================================================

        async def end_session_callback():
            """End voice or text session when agent shuts down."""
            try:
                from datetime import datetime, timezone

                from shared.database.models.database import async_session_maker
                from shared.database.models.voice_session import VoiceSessionStatus
                from shared.services.voice_session_orchestrator import VoiceSessionOrchestrator

                session_type = "text" if agent.text_only_mode else "voice"
                logger.info(f"🛑 Ending {session_type} session for room: {ctx.room.name}")

                async with async_session_maker() as db_session:
                    async with VoiceSessionOrchestrator(db_session) as orchestrator:
                        if agent.text_only_mode:
                            # TEXT MODE: End text session and record message count
                            text_session = await orchestrator.get_text_session_by_room(
                                ctx.room.name
                            )

                            if text_session and not text_session.ended_at:
                                await orchestrator.end_text_session(
                                    session_id=text_session.id,
                                    final_message_count=agent.email_capture_handler._message_count,
                                )
                                await db_session.commit()
                                logger.info(
                                    f"✅ Text session ended: {text_session.id}, "
                                    f"messages: {agent.email_capture_handler._message_count}"
                                )
                        else:
                            # VOICE MODE: End voice session
                            voice_session = await orchestrator.usage_service.get_session_by_room(
                                ctx.room.name
                            )

                            if voice_session and voice_session.status == VoiceSessionStatus.ACTIVE:
                                duration_seconds = int(
                                    (
                                        datetime.now(timezone.utc) - voice_session.started_at
                                    ).total_seconds()
                                )

                                await orchestrator.end_session(
                                    session_id=voice_session.id,
                                    final_duration_seconds=duration_seconds,
                                )
                                await db_session.commit()
                                logger.info(
                                    f"✅ Voice session ended: {voice_session.id}, duration: {duration_seconds}s"
                                )

            except Exception as e:
                session_type = "text" if agent.text_only_mode else "voice"
                logger.error(
                    f"Failed to end {session_type} session in shutdown callback: {e}", exc_info=True
                )

                # Capture in Sentry for monitoring
                from shared.monitoring.sentry_utils import capture_exception_with_context

                capture_exception_with_context(
                    e,
                    extra={
                        "room_name": ctx.room.name if ctx.room else None,
                        "session_type": session_type,
                        "message_count": (
                            agent.email_capture_handler._message_count
                            if agent.text_only_mode
                            else None
                        ),
                    },
                    tags={
                        "component": "livekit_agent",
                        "operation": "end_session_callback",
                        "severity": "high",
                        "user_facing": "false",
                    },
                )

        async def save_conversation_and_send_summary():
            """Save conversation to DB and send summary email."""
            try:
                from app.services.conversation_service import ConversationService

                conversation_type = "text" if agent.text_only_mode else "voice"

                # Save conversation to database
                conversation_history = agent.conversation_manager.get_conversation_history()
                logger.info(
                    f"💾 Saving {conversation_type} conversation: {len(conversation_history)} messages"
                )

                # Guard: session_token is required for saving
                if not agent.session_token:
                    logger.info("⏭️  Skipping conversation save - no session token")
                    return

                # Collect any captured lead data from DefaultCaptureHandler
                captured_lead_data = None
                if (
                    hasattr(agent, "default_capture_handler")
                    and agent.default_capture_handler
                    and agent.default_capture_handler.captured_fields
                ):
                    captured_lead_data = agent.default_capture_handler.captured_fields
                    logger.info(
                        f"📋 DefaultCaptureHandler has data for backfill: "
                        f"{list(captured_lead_data.keys())}"
                    )

                conversation_id = await ConversationService.save_livekit_conversation(
                    persona_id=agent.persona_id,
                    session_token=agent.session_token,
                    conversation_history=conversation_history,
                    conversation_type=conversation_type,
                    captured_lead_data=captured_lead_data,
                )

                if not conversation_id:
                    logger.info(
                        "⏭️  Skipping summary email and webhook - conversation not saved (0 messages or error)"
                    )
                    return

                logger.info(f"✅ {conversation_type.capitalize()} conversation saved")

                # Link workflow session to conversation (conversation_id is NULL at creation time)
                if (
                    hasattr(agent, "workflow_handler")
                    and agent.workflow_handler
                    and agent.workflow_handler._workflow_session_id
                ):
                    try:
                        from shared.database.models.database import async_session_maker
                        from shared.database.repositories.workflow_repository import (
                            WorkflowRepository,
                        )

                        async with async_session_maker() as db_session:
                            workflow_repo = WorkflowRepository(db_session)
                            await workflow_repo.update_session_conversation_id(
                                session_id=agent.workflow_handler._workflow_session_id,
                                conversation_id=conversation_id,
                            )
                        logger.info(
                            f"✅ Linked workflow session {agent.workflow_handler._workflow_session_id} "
                            f"to conversation {conversation_id}"
                        )
                    except Exception as e:
                        logger.error(f"⚠️ Failed to link workflow session to conversation: {e}")
                        from shared.monitoring.sentry_utils import capture_exception_with_context

                        capture_exception_with_context(
                            e,
                            extra={
                                "workflow_session_id": str(
                                    agent.workflow_handler._workflow_session_id
                                ),
                                "conversation_id": str(conversation_id),
                            },
                            tags={
                                "component": "livekit_agent",
                                "operation": "link_workflow_to_conversation",
                                "severity": "medium",
                                "user_facing": "false",
                            },
                        )

                # Collect workflow data for handoff
                wf_session_id = None
                wf_extracted_fields = None
                wf_context = None
                wf_is_active = False
                if hasattr(agent, "workflow_handler") and agent.workflow_handler:
                    wf_session_id = agent.workflow_handler._workflow_session_id
                    wf_is_active = agent.workflow_handler.is_active
                    if agent.workflow_handler.workflow_data:
                        wf_context = {
                            "template_name": agent.workflow_handler.workflow_data.get("title"),
                            "scoring_rules": agent.workflow_handler.workflow_data.get(
                                "output_template", {}
                            ).get("scoring_rules"),
                            "output_config": {
                                k: v
                                for k, v in agent.workflow_handler.workflow_data.get(
                                    "output_template", {}
                                ).items()
                                if k != "scoring_rules"
                            },
                        }

                # Hand off slow post-processing (AI summary, email, webhook, scoring)
                # to the FastAPI backend so this agent process can exit immediately.
                try:
                    import httpx

                    # Use internal URL — agent subprocess runs in the same container
                    # as FastAPI (port 8001). API_BASE_URL is the external/public URL
                    # which doesn't work from within the container.
                    api_base_url = os.getenv("INTERNAL_API_URL", "http://127.0.0.1:8001")
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        resp = await client.post(
                            f"{api_base_url}/api/v1/internal/conversation-postprocess",
                            json={
                                "persona_id": str(agent.persona_id),
                                "session_token": agent.session_token,
                                "conversation_id": str(conversation_id),
                                "conversation_type": conversation_type,
                                "conversation_history": conversation_history,
                                "persona_name": agent.persona_info.get("name", ""),
                                "workflow_session_id": (
                                    str(wf_session_id) if wf_session_id else None
                                ),
                                "workflow_extracted_fields": wf_extracted_fields,
                                "workflow_context": wf_context,
                                "workflow_is_active": wf_is_active,
                                "captured_lead_data": captured_lead_data,
                            },
                        )
                        logger.info(
                            f"✅ Handed off post-processing to backend (status={resp.status_code})"
                        )
                except Exception as e:
                    logger.error(f"⚠️ Failed to hand off post-processing: {e}")
                    from shared.monitoring.sentry_utils import (
                        capture_exception_with_context,
                    )

                    capture_exception_with_context(
                        e,
                        extra={
                            "persona_id": str(agent.persona_id),
                            "conversation_id": str(conversation_id),
                        },
                        tags={
                            "component": "livekit_entrypoint",
                            "operation": "postprocess_handoff",
                            "severity": "high",
                            "user_facing": "false",
                        },
                    )

            except Exception as e:
                logger.error(f"Error during save_conversation_and_send_summary: {e}", exc_info=True)
                from shared.monitoring.sentry_utils import capture_exception_with_context

                capture_exception_with_context(
                    e,
                    extra={
                        "persona_id": str(agent.persona_id),
                        "session_token": agent.session_token,
                    },
                    tags={
                        "component": "livekit_entrypoint",
                        "operation": "save_conversation_and_send_summary",
                        "severity": "high",
                        "user_facing": "false",
                    },
                )

        async def flush_trace():
            """Flush Langfuse telemetry."""
            if trace_provider:
                trace_provider.force_flush()
                logger.info("✅ Flushed Langfuse traces")

        async def cleanup_agent():
            """Final cleanup."""
            try:
                logger.info("🧹 Running shutdown cleanup...")
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error during cleanup: {e}")

        # Register shutdown callbacks (order matters!)
        ctx.add_shutdown_callback(end_session_callback)  # 1. Stop recording + update usage
        ctx.add_shutdown_callback(save_conversation_and_send_summary)  # 2. Save chat history
        ctx.add_shutdown_callback(flush_trace)  # 3. Flush telemetry
        ctx.add_shutdown_callback(cleanup_agent)  # 4. Final cleanup

        # ===================================================================
        # Setup Agent Session and Event Handlers
        # ===================================================================

        session = AgentSession()

        @session.on("metrics_collected")
        def _on_metrics_collected(ev: MetricsCollectedEvent):
            """Log metrics when collected."""
            metrics.log_metrics(ev.metrics)

        # STT/TTS/LLM error + session close capture (Sentry)
        session.on("error", agent.lifecycle_handler.on_agent_error)
        session.on("close", agent.lifecycle_handler.on_session_close)

        @session.on("conversation_item_added")
        def _on_conversation_item_added(ev):
            """Count messages and add to conversation history (both voice and text modes)."""
            try:
                item = ev.item
                if hasattr(item, "role") and hasattr(item, "text_content"):
                    content = item.text_content or ""
                    if not content:
                        return

                    # Parse JSON-wrapped messages from frontend (text-only mode)
                    import json

                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict) and "message" in parsed:
                            content = parsed["message"].strip()
                    except (json.JSONDecodeError, ValueError, TypeError):
                        content = content.strip()

                    # Count user messages
                    if item.role == "user":
                        agent.email_capture_handler.increment_message_count()
                        logger.info(
                            f"📊 [MESSAGE_COUNTER] User message added - "
                            f"Count: {agent.email_capture_handler._message_count}"
                        )

                        # Add to conversation history with deduplication
                        history = agent.conversation_manager._conversation_history
                        # Check if this user message already exists
                        if not any(
                            msg.get("role") == "user" and msg.get("content") == content
                            for msg in history
                        ):
                            history.append({"role": "user", "content": content})

                    # Check email capture AFTER agent responds (on assistant messages)
                    elif item.role == "assistant":
                        # Add to conversation history with deduplication
                        history = agent.conversation_manager._conversation_history
                        # Check if this assistant message already exists
                        if not any(
                            msg.get("role") == "assistant" and msg.get("content") == content
                            for msg in history
                        ):
                            history.append({"role": "assistant", "content": content})

                        # Trigger email capture check asynchronously (works for both voice and text)
                        async def check_email_capture_async():
                            try:
                                can_continue = await agent.email_capture_handler.check_and_trigger()
                                if not can_continue:
                                    # User declined email capture - disconnect
                                    logger.info(
                                        "❌ User declined email capture - disconnecting room"
                                    )
                                    await ctx.room.disconnect()
                            except Exception as e:
                                logger.error(f"❌ Error checking email capture: {e}", exc_info=True)

                        # Schedule async task
                        asyncio.create_task(check_email_capture_async())

            except Exception as e:
                logger.error(f"❌ Error in conversation_item_added handler: {e}")

        # Configure room options based on mode
        if text_only_mode:
            room_options = room_io.RoomOptions(
                audio_input=False,
                audio_output=False,
                text_input=True,  # Enable text input from lk.chat
                text_output=True,  # Enable text output via lk.transcription.final
            )
            logger.info("📝 Configured RoomOptions for text-only mode")
        else:
            room_options = room_io.RoomOptions(
                audio_input=True,
                audio_output=True,
                text_input=True,  # Also enable text for hybrid mode
                text_output=True,
            )
            logger.info("🎙️ Configured RoomOptions for voice mode")

        # Data channel handler for document uploads
        @ctx.room.on("data_received")
        def on_data_received(data_packet):
            """Handle document uploads via data channel."""
            try:
                data_str = data_packet.data.decode("utf-8")
                data_json = json.loads(data_str)
                msg_type = data_json.get("type", "text")

                # Only handle document uploads via data channel
                if msg_type == "document_upload":
                    asyncio.create_task(agent.document_handler.handle_document_upload(data_json))
                    logger.info("📄 Document upload received via data channel")
                else:
                    logger.debug(f"Ignoring non-document data message: {msg_type}")

            except json.JSONDecodeError:
                logger.debug("Non-JSON data received, ignoring")
            except Exception as e:
                logger.error(f"Error handling data message: {e}")

        # Start the agent session
        try:
            await session.start(
                agent=agent,
                room=ctx.room,
                room_options=room_options,
            )

            # NOTE: agent.session is automatically set by session.start()
            # No need to manually assign it - it's a read-only property

            logger.info(
                f"✅ [{persona_data.expert_username}] Agent ready "
                f"({'Text-Only' if text_only_mode else 'Voice'} mode)"
            )

        except Exception as session_error:
            logger.error(f"Session error: {session_error}")
            import traceback

            logger.error(traceback.format_exc())
            try:
                await agent.on_exit()
            except Exception as cleanup_error:
                logger.error(f"Cleanup error: {cleanup_error}")
            raise

    except Exception as e:
        logger.error(f"Critical error in entrypoint: {e}")
        import traceback

        logger.error(traceback.format_exc())
        from shared.monitoring.sentry_utils import capture_exception_with_context

        capture_exception_with_context(
            e,
            extra={
                "room_name": ctx.room.name if ctx.room else None,
                "job_id": ctx.job.id if hasattr(ctx, "job") else None,
            },
            tags={"component": "livekit_agent", "operation": "entrypoint"},
        )
        raise


def main():
    """Main function with signal handlers."""
    load_dotenv()

    from shared.monitoring.sentry_utils import init_sentry

    worker_id = os.getenv("WORKER_PORT", "8080")
    init_sentry(
        component="livekit_agent",
        worker_id=f"agent-{worker_id}",
        custom_tags={"agent_name": settings.livekit_agent_name, "process_type": "subprocess"},
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Pre-set our module loggers to INFO before the SDK's cli.run_app() calls
    # _silence_noisy_loggers(), which sets the "livekit" parent logger to WARN.
    # That silencing only applies if a logger's level is NOTSET, so by explicitly
    # setting INFO here, our loggers are protected and their logs won't be dropped
    # when the child process sends them back to the main process via LogQueueListener.
    for _name in [
        "livekit.livekit_agent",
        "livekit.handlers",
        "livekit.managers",
        "livekit.services",
        "livekit.helpers",
    ]:
        logging.getLogger(_name).setLevel(logging.INFO)

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        time.sleep(0.2)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGUSR1, signal_handler)

    worker_port = int(os.getenv("WORKER_PORT", "8080"))
    logger.info(f"Starting modular LiveKit agent on port {worker_port}")

    worker_options = WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
        agent_name=settings.livekit_agent_name,
        port=worker_port,
        shutdown_process_timeout=10.0,  # Fast DB writes + httpx handoff only
    )

    try:
        cli.run_app(worker_options)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
