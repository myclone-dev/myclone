"""
Integration Tests for Confirmation Flow with process_workflow_response

Tests the specific scenario where:
1. User provides all required info
2. Bot shows confirmation summary
3. User says "Yep" or similar
4. Workflow should complete

This tests the actual tool docstring that tells the LLM to call
process_workflow_response for confirmation responses.

Requirements:
- OPENAI_API_KEY environment variable (or in .env file)
- Set LIVEKIT_EVALS_VERBOSE=1 for detailed output

Run with:
    LIVEKIT_EVALS_VERBOSE=1 poetry run pytest livekit/tests/integration/test_confirmation_flow.py -v -s
"""

import os
from typing import Any, Dict
from uuid import uuid4

import pytest
from dotenv import load_dotenv

load_dotenv()

# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY required for integration tests",
)


# ============================================================================
# Test Agent: Mirrors production process_workflow_response behavior
# ============================================================================


def create_confirmation_test_agent():
    """
    Create a test agent that uses process_workflow_response like production.

    This agent has the SAME tool signature and docstring as the production
    ModularPersonaAgent to verify the LLM calls it correctly.
    """
    from livekit.agents import Agent, function_tool
    from livekit.plugins import openai

    class ConfirmationTestAgent(Agent):
        """
        Test agent with process_workflow_response tool.

        Mirrors the production agent's tool to test LLM behavior.
        """

        def __init__(
            self,
            workflow_data: Dict[str, Any],
            persona_name: str = "Test CPA",
        ):
            self.workflow_data = workflow_data
            self.persona_name = persona_name

            # Track state
            self.captured_fields: Dict[str, Any] = {}
            self.workflow_status = "not_started"
            self.awaiting_confirmation = False
            self.process_workflow_response_calls: list = []  # Track all calls

            system_prompt = self._build_system_prompt()

            super().__init__(
                instructions=system_prompt,
                llm=openai.LLM(model="gpt-4o-mini", tool_choice="auto"),
            )

        def _build_system_prompt(self) -> str:
            """Build system prompt with workflow instructions."""
            required_fields = self.workflow_data.get("required_fields", [])

            required_desc = "\n".join(
                [f"  - {f['field_id']}: {f.get('label', f['field_id'])}" for f in required_fields]
            )

            return f"""You are {self.persona_name}, a Certified Public Accountant.

Your goal is to collect lead information through natural conversation.

REQUIRED FIELDS:
{required_desc}

WORKFLOW INSTRUCTIONS:
1. When user provides ANY contact info, call process_workflow_response with their message
2. When user CONFIRMS info ("yes", "yep", "correct"), call process_workflow_response
3. When user REJECTS info ("no", "wrong"), call process_workflow_response
4. The tool handles extraction, confirmation, and completion automatically

CRITICAL: You MUST call process_workflow_response for:
- Contact information (name, email, phone, service need)
- Confirmation responses ("yes", "yep", "yeah", "correct", "that's right")
- Rejection responses ("no", "wrong", "incorrect")

DO NOT respond to confirmations without calling the tool first!"""

        @function_tool
        async def process_workflow_response(self, user_message: str) -> str:
            """Process ANY user response during the lead capture workflow.

            Call this tool for ALL workflow-related responses:

            1. CONTACT INFORMATION - User provides name, email, phone, service need:
               - "Hi, I'm Sarah Chen, sarah@email.com, 415-555-0123"
               - "I need help with my taxes"
               - Any combination of contact details

            2. CONFIRMATION - User confirms their information is correct:
               - "Yes", "Yep", "Yeah", "Correct", "That's right", "Looks good", "Perfect"
               - After you showed them a summary of their info

            3. REJECTION/CORRECTION - User says info is wrong:
               - "No", "Wrong", "That's not right", "Incorrect"
               - Triggers correction flow so they can fix it

            This tool automatically:
            - Starts the workflow (if not already started)
            - Extracts contact information from messages
            - Handles confirmation → completes workflow
            - Handles rejection → enters correction mode
            - Asks only for missing required fields

            Args:
                user_message: User's full message (contact info, confirmation, or rejection)

            IMPORTANT: Call this for EVERY user message during lead capture, including
            simple confirmations like "yes" or "yep" - these complete the workflow!
            """
            # Track the call
            self.process_workflow_response_calls.append(user_message)

            # Simulate extraction/confirmation logic
            message_lower = user_message.lower().strip()

            # Check for confirmation
            confirmation_keywords = [
                "yes",
                "yep",
                "yeah",
                "correct",
                "right",
                "looks good",
                "perfect",
            ]
            is_confirmation = any(kw in message_lower for kw in confirmation_keywords)

            # Check for rejection
            rejection_keywords = ["no", "wrong", "incorrect", "not right"]
            is_rejection = any(kw in message_lower for kw in rejection_keywords)

            if self.awaiting_confirmation:
                if is_confirmation:
                    self.workflow_status = "completed"
                    self.awaiting_confirmation = False
                    return (
                        "✅ WORKFLOW COMPLETE - All information confirmed. Thank the user briefly."
                    )
                elif is_rejection:
                    self.workflow_status = "needs_correction"
                    self.awaiting_confirmation = False
                    return "User wants to correct something. Ask what needs to be fixed."

            # Extract fields from message (simplified)
            if "i'm " in message_lower or "my name is" in message_lower:
                self.captured_fields["contact_name"] = {"value": "extracted"}
            if "@" in message_lower:
                self.captured_fields["contact_email"] = {"value": "extracted"}
            if any(c.isdigit() for c in message_lower):
                # Rough phone detection
                digits = sum(1 for c in message_lower if c.isdigit())
                if digits >= 7:
                    self.captured_fields["contact_phone"] = {"value": "extracted"}
            if any(kw in message_lower for kw in ["tax", "help", "need", "service"]):
                self.captured_fields["service_need"] = {"value": "extracted"}

            # Check if all required fields captured
            required_ids = ["contact_name", "contact_email", "contact_phone", "service_need"]
            captured = [fid for fid in required_ids if fid in self.captured_fields]
            missing = [fid for fid in required_ids if fid not in self.captured_fields]

            if not missing:
                self.workflow_status = "awaiting_confirmation"
                self.awaiting_confirmation = True
                return (
                    "✅ All info collected! Show confirmation summary and ask: "
                    "'Does this look correct?' Then wait for user response."
                )
            else:
                return f"Captured {len(captured)}/4 fields. Still need: {', '.join(missing)}"

    return ConfirmationTestAgent


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def workflow_data():
    """CPA workflow configuration."""
    return {
        "workflow_id": str(uuid4()),
        "title": "CPA Lead Capture",
        "workflow_type": "conversational",
        "required_fields": [
            {"field_id": "contact_name", "label": "Full Name"},
            {"field_id": "contact_email", "label": "Email"},
            {"field_id": "contact_phone", "label": "Phone"},
            {"field_id": "service_need", "label": "Service Needed"},
        ],
    }


@pytest.fixture
def test_agent_class():
    """Get the test agent class."""
    return create_confirmation_test_agent()


# ============================================================================
# Confirmation Flow Tests
# ============================================================================


class TestConfirmationWithProcessWorkflowResponse:
    """Tests for confirmation flow using process_workflow_response tool."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_llm_calls_tool_for_yep_confirmation(self, test_agent_class, workflow_data):
        """
        CRITICAL TEST: LLM should call process_workflow_response when user says 'Yep'.

        This is the exact bug we're fixing - the LLM was NOT calling the tool
        for simple confirmations like "Yep".
        """
        from livekit.agents import AgentSession
        from livekit.plugins import openai

        agent = test_agent_class(
            workflow_data=workflow_data,
            persona_name="Sarah Johnson",
        )

        async with AgentSession(
            llm=openai.LLM(model="gpt-4o-mini"),
        ) as session:
            await session.start(agent)

            # Turn 1: Provide all required info
            await session.run(
                user_input="Hi, I'm John Smith, john@example.com, 555-123-4567, and I need tax help"
            )

            print(f"\n[Turn 1] Tool calls: {agent.process_workflow_response_calls}")
            print(f"[Turn 1] Status: {agent.workflow_status}")
            print(f"[Turn 1] Awaiting confirmation: {agent.awaiting_confirmation}")

            # Should have called tool and be awaiting confirmation
            assert (
                len(agent.process_workflow_response_calls) >= 1
            ), "LLM should have called process_workflow_response for contact info"
            assert (
                agent.awaiting_confirmation
            ), "Should be awaiting confirmation after all fields captured"

            # Turn 2: User confirms with "Yep"
            await session.run(user_input="Yep")

            print(f"\n[Turn 2 - 'Yep'] Tool calls: {agent.process_workflow_response_calls}")
            print(f"[Turn 2 - 'Yep'] Status: {agent.workflow_status}")

            # THIS IS THE KEY ASSERTION - LLM must call tool for "Yep"
            # Check that "Yep" was passed to the tool
            yep_calls = [c for c in agent.process_workflow_response_calls if "yep" in c.lower()]
            assert len(yep_calls) >= 1, (
                f"LLM MUST call process_workflow_response for 'Yep' confirmation! "
                f"Calls were: {agent.process_workflow_response_calls}"
            )

            # Workflow should be completed
            assert (
                agent.workflow_status == "completed"
            ), f"Workflow should be completed after confirmation. Status: {agent.workflow_status}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_llm_calls_tool_for_yes_confirmation(self, test_agent_class, workflow_data):
        """LLM should call process_workflow_response when user says 'Yes'."""
        from livekit.agents import AgentSession
        from livekit.plugins import openai

        agent = test_agent_class(
            workflow_data=workflow_data,
            persona_name="Sarah Johnson",
        )

        async with AgentSession(
            llm=openai.LLM(model="gpt-4o-mini"),
        ) as session:
            await session.start(agent)

            # Turn 1: Provide all required info
            await session.run(
                user_input="I'm Jane Doe, jane@test.com, 555-987-6543, need bookkeeping help"
            )

            assert agent.awaiting_confirmation, "Should be awaiting confirmation"

            # Turn 2: User confirms with "Yes"
            await session.run(user_input="Yes")

            print(f"\n[Confirmation 'Yes'] Tool calls: {agent.process_workflow_response_calls}")
            print(f"[Confirmation 'Yes'] Status: {agent.workflow_status}")

            # Check that "Yes" was passed to the tool
            yes_calls = [c for c in agent.process_workflow_response_calls if "yes" in c.lower()]
            assert len(yes_calls) >= 1, (
                f"LLM should call process_workflow_response for 'Yes'! "
                f"Calls: {agent.process_workflow_response_calls}"
            )

            assert agent.workflow_status == "completed"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_llm_calls_tool_for_thats_correct(self, test_agent_class, workflow_data):
        """LLM should call process_workflow_response for 'That's correct'."""
        from livekit.agents import AgentSession
        from livekit.plugins import openai

        agent = test_agent_class(
            workflow_data=workflow_data,
            persona_name="Sarah Johnson",
        )

        async with AgentSession(
            llm=openai.LLM(model="gpt-4o-mini"),
        ) as session:
            await session.start(agent)

            await session.run(
                user_input="Hi I'm Bob, bob@company.com, 555-111-2222, tax planning help"
            )

            assert agent.awaiting_confirmation

            await session.run(user_input="That's correct")

            print(
                f"\n[Confirmation 'That's correct'] Calls: {agent.process_workflow_response_calls}"
            )

            correct_calls = [
                c for c in agent.process_workflow_response_calls if "correct" in c.lower()
            ]
            assert (
                len(correct_calls) >= 1
            ), "LLM should call process_workflow_response for 'That's correct'!"
            assert agent.workflow_status == "completed"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_llm_calls_tool_for_rejection(self, test_agent_class, workflow_data):
        """LLM should call process_workflow_response when user says 'No, that's wrong'."""
        from livekit.agents import AgentSession
        from livekit.plugins import openai

        agent = test_agent_class(
            workflow_data=workflow_data,
            persona_name="Sarah Johnson",
        )

        async with AgentSession(
            llm=openai.LLM(model="gpt-4o-mini"),
        ) as session:
            await session.start(agent)

            await session.run(user_input="I'm Alice, alice@email.com, 555-333-4444, filing help")

            assert agent.awaiting_confirmation

            await session.run(user_input="No, that's wrong")

            print(f"\n[Rejection] Tool calls: {agent.process_workflow_response_calls}")
            print(f"[Rejection] Status: {agent.workflow_status}")

            wrong_calls = [c for c in agent.process_workflow_response_calls if "wrong" in c.lower()]
            assert len(wrong_calls) >= 1, "LLM should call process_workflow_response for rejection!"
            assert agent.workflow_status == "needs_correction"


class TestEdgeCaseConfirmations:
    """Edge case tests for various confirmation phrasings."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_looks_good_confirmation(self, test_agent_class, workflow_data):
        """'Looks good' should trigger confirmation."""
        from livekit.agents import AgentSession
        from livekit.plugins import openai

        agent = test_agent_class(workflow_data=workflow_data)

        async with AgentSession(llm=openai.LLM(model="gpt-4o-mini")) as session:
            await session.start(agent)
            await session.run(user_input="Tom, tom@test.com, 555-444-5555, quarterly taxes")
            await session.run(user_input="Looks good!")

            looks_good_calls = [
                c for c in agent.process_workflow_response_calls if "looks good" in c.lower()
            ]
            assert len(looks_good_calls) >= 1 or agent.workflow_status == "completed"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_perfect_confirmation(self, test_agent_class, workflow_data):
        """'Perfect' should trigger confirmation."""
        from livekit.agents import AgentSession
        from livekit.plugins import openai

        agent = test_agent_class(workflow_data=workflow_data)

        async with AgentSession(llm=openai.LLM(model="gpt-4o-mini")) as session:
            await session.start(agent)
            await session.run(user_input="Lisa, lisa@test.com, 555-666-7777, tax advice")
            await session.run(user_input="Perfect!")

            perfect_calls = [
                c for c in agent.process_workflow_response_calls if "perfect" in c.lower()
            ]
            assert len(perfect_calls) >= 1 or agent.workflow_status == "completed"
