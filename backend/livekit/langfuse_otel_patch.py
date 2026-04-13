"""
Monkey patch for LiveKit v1.3.6 to enable input message tracking in Langfuse

⚠️ TEMPORARY FIX - Remove this file when upgrading to LiveKit v1.3.7+

Background:
-----------
LiveKit v1.3.6 does NOT send input message events to Langfuse, only output messages.
The fix was added in commit 51c2870b (Dec 5, 2025) but is not in any released version yet.

This monkey patch backports the missing functionality by:
1. Converting chat context to OpenTelemetry events (_chat_ctx_to_otel_events)
2. Injecting these events into the llm_request span before the main task runs

When to remove:
---------------
- When LiveKit releases v1.3.7 or v1.4.0 (which will include the fix)
- Check release notes for "OTEL chat message events" or commit 51c2870b
- Simply delete this file and remove the import from entrypoint.py

Reference:
----------
- Deep dive doc: LIVEKIT_LANGFUSE_OTEL_DEEP_DIVE.md
- Original commit: https://github.com/livekit/agents/commit/51c2870b
"""

import json
import logging

from opentelemetry.util.types import Attributes

from livekit.agents import llm

logger = logging.getLogger(__name__)


def _chat_ctx_to_otel_events(chat_ctx: llm.ChatContext) -> list[tuple[str, Attributes]]:
    """Convert chat context to OpenTelemetry events for Langfuse

    This enables Langfuse to see input messages in the conversation.
    Without this, only output messages are visible in Langfuse UI.

    Args:
        chat_ctx: LiveKit ChatContext object with conversation history

    Returns:
        List of (event_name, attributes) tuples for OTEL span events
    """
    # OpenTelemetry semantic convention event names
    EVENT_GEN_AI_SYSTEM_MESSAGE = "gen_ai.system.message"
    EVENT_GEN_AI_USER_MESSAGE = "gen_ai.user.message"
    EVENT_GEN_AI_ASSISTANT_MESSAGE = "gen_ai.assistant.message"
    EVENT_GEN_AI_TOOL_MESSAGE = "gen_ai.tool.message"

    role_to_event = {
        "system": EVENT_GEN_AI_SYSTEM_MESSAGE,
        "user": EVENT_GEN_AI_USER_MESSAGE,
        "assistant": EVENT_GEN_AI_ASSISTANT_MESSAGE,
    }

    events: list[tuple[str, Attributes]] = []

    for item in chat_ctx.items:
        # Handle regular chat messages (system, user, assistant)
        if item.type == "message":
            event_name = role_to_event.get(item.role)
            if event_name:
                events.append((event_name, {"content": item.text_content or ""}))

        # Handle function calls (tool invocations from LLM)
        elif item.type == "function_call":
            events.append(
                (
                    EVENT_GEN_AI_ASSISTANT_MESSAGE,
                    {
                        "role": "assistant",
                        "tool_calls": [
                            json.dumps(
                                {
                                    "function": {"name": item.name, "arguments": item.arguments},
                                    "id": item.call_id,
                                    "type": "function",
                                }
                            )
                        ],
                    },
                )
            )

        # Handle function outputs (tool execution results)
        elif item.type == "function_call_output":
            events.append(
                (
                    EVENT_GEN_AI_TOOL_MESSAGE,
                    {"content": item.output, "name": item.name, "id": item.call_id},
                )
            )

    return events


def apply_langfuse_input_patch():
    """Monkey patch LLMStream._main_task to add input message events to llm_request span

    This wraps the _main_task method to inject chat context as OTEL events
    into the llm_request span created by _traceable_main_task.

    The patch adds input message events (system, user, assistant messages) to the
    llm_request span so Langfuse can display the full conversation history.

    Without this patch (v1.3.6):
    - ❌ Input messages do NOT appear in Langfuse (only custom lk.chat_ctx attribute)
    - ✅ Output messages work via gen_ai.choice event

    With this patch:
    - ✅ Input messages appear in Langfuse via gen_ai.* events
    - ✅ Full conversation history visible in Langfuse UI
    """
    from livekit.agents.llm.llm import LLMStream

    # Save original _main_task
    original_main_task = LLMStream._main_task

    async def patched_main_task(self):
        """Patched version that injects input events before calling original _main_task"""
        # Get the current span (created by _traceable_main_task)
        from opentelemetry import trace as otel_trace

        current_span = otel_trace.get_current_span()

        # 🔥 INJECT INPUT EVENTS HERE (the missing piece in v1.3.6!)
        # This runs BEFORE the span attributes are set
        try:
            events = _chat_ctx_to_otel_events(self._chat_ctx)
            for name, attributes in events:
                current_span.add_event(name, attributes)
            logger.debug(f"📨 Added {len(events)} input message events to llm_request span")
        except Exception as e:
            logger.error(f"❌ Failed to add input message events: {e}", exc_info=True)

        # Continue with original _main_task (sets span and calls _run)
        return await original_main_task(self)

    # Replace _main_task method
    LLMStream._main_task = patched_main_task
    logger.info(
        "✅ Applied Langfuse OTEL patch: LLMStream._main_task now sends input message events"
    )
    logger.info("   ⚠️  Remove livekit/langfuse_otel_patch.py when upgrading to LiveKit v1.3.7+")
