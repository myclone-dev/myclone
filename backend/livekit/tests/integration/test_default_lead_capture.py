"""
Statistical Compliance Tests for Default Lead Capture

Runs N simulated conversations with diverse user behaviors and measures
what % of the time the LLM actually calls update_lead_fields.

The goal is to catch prompt regressions — if capture rate drops below
the threshold, the prompt needs fixing.

Requirements:
- OPENAI_API_KEY environment variable (or in .env file)
- Set LIVEKIT_EVALS_VERBOSE=1 for detailed output

Run with:
    LIVEKIT_EVALS_VERBOSE=1 poetry run pytest livekit/tests/integration/test_default_lead_capture.py -v -s

Run a single scenario category:
    poetry run pytest livekit/tests/integration/test_default_lead_capture.py::TestDefaultCaptureCompliance::test_volunteered_info_capture_rate -v -s
"""

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List

import pytest
from dotenv import load_dotenv

load_dotenv()

# Skip if no API key
pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY required for integration tests",
)

VERBOSE = os.getenv("LIVEKIT_EVALS_VERBOSE", "0") == "1"


# ============================================================================
# Scenario Definitions
# ============================================================================


@dataclass
class ConversationScenario:
    """A single simulated user conversation."""

    name: str
    # Each turn is a user message. The test sends them sequentially.
    turns: List[str]
    # Which fields we expect to be captured by end of conversation
    expected_fields: List[str]
    # Category for grouping in reports
    category: str


# --- Category 1: Volunteered Info (user provides contact info unprompted) ---
VOLUNTEERED_SCENARIOS = [
    ConversationScenario(
        name="name_email_phone_upfront",
        turns=[
            "Hi, I'm John Smith. My email is john@test.com and my phone is 555-1234. I need help with a car accident."
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="volunteered",
    ),
    ConversationScenario(
        name="name_and_email_first_message",
        turns=[
            "Hey there, I'm Sarah Connor, my email is sarah@skynet.com. I was in a rear-end collision.",
            "My phone is 310-555-9876.",
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="volunteered",
    ),
    ConversationScenario(
        name="name_only_intro",
        turns=[
            "Hi, I'm Michael Chen. I slipped and fell at a grocery store last week.",
            "Sure, my email is mchen@outlook.com",
            "You can reach me at 415-222-3344",
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="volunteered",
    ),
    ConversationScenario(
        name="casual_name_drop",
        turns=[
            "Hi there, this is David. I got hurt at work and I'm not sure what to do.",
            "David Martinez. Email is dmartinez@yahoo.com",
            "Phone number is 832-555-6789",
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="volunteered",
    ),
    ConversationScenario(
        name="email_first_then_name",
        turns=[
            "Can I reach someone about a medical malpractice case? My email is jenny.wu@gmail.com",
            "Oh sorry, my name is Jenny Wu.",
            "And my number is 650-111-2233",
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="volunteered",
    ),
    ConversationScenario(
        name="all_info_scattered_naturally",
        turns=[
            "Hey, I need some advice about a car accident.",
            "My name's Robert Lee by the way.",
            "You can email me at robert.lee@company.com",
            "Best number to reach me is 512-333-4455",
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="volunteered",
    ),
    ConversationScenario(
        name="verbose_intro_with_all_info",
        turns=[
            "Hello! My name is Priya Sharma and I'm looking for legal help after a car accident. "
            "I can be reached at priya.sharma@email.com or 408-777-8899. What are my options?"
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="volunteered",
    ),
    ConversationScenario(
        name="name_in_greeting_email_later",
        turns=[
            "Good morning, this is Angela Torres. I have a question about a workplace injury.",
            "What kind of compensation could I get for a back injury at work?",
            "My email is angela.torres@hotmail.com and phone is 773-555-1122",
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="volunteered",
    ),
    ConversationScenario(
        name="informal_spoken_style_email",
        turns=[
            "Hey I'm Jake and my email is jake at gmail dot com. I got hit by a truck.",
            "My phone number is five five five zero one two three",
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="volunteered",
    ),
    ConversationScenario(
        name="business_context_all_info",
        turns=[
            "Hi, I'm Maria Gonzalez from ABC Construction. We had a workplace accident. "
            "Email me at maria@abcconstruction.com, phone 305-444-5566."
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="volunteered",
    ),
]

# --- Category 2: Proactive Capture (user never volunteers, agent must ask) ---
PROACTIVE_SCENARIOS = [
    ConversationScenario(
        name="just_questions_no_info",
        turns=[
            "What should I do after a car accident?",
            "How long do I have to file a claim?",
            "What kind of compensation can I get?",
            "That's really helpful, thank you.",
            "Sure, I'm Tom Bradley. Email is tom@test.com, phone 555-0001.",
        ],
        expected_fields=["contact_name"],
        category="proactive",
    ),
    ConversationScenario(
        name="vague_and_evasive",
        turns=[
            "Hi, I have a legal question.",
            "It's about an accident.",
            "Yeah it happened last month.",
            "I'm just looking for general info right now.",
            "Ok fine, my name is Lisa Wang.",
        ],
        expected_fields=["contact_name"],
        category="proactive",
    ),
    ConversationScenario(
        name="topic_focused_no_personal",
        turns=[
            "Can you tell me about personal injury law?",
            "What's the statute of limitations in California?",
            "And what about comparative negligence?",
            "Thanks, that's very helpful.",
            "I'm Kevin Park, email kevin.park@test.com",
        ],
        expected_fields=["contact_name"],
        category="proactive",
    ),
    ConversationScenario(
        name="chatty_but_no_info",
        turns=[
            "Hey, how's it going?",
            "I heard you guys handle injury cases.",
            "My friend recommended you actually.",
            "Yeah she had a great experience.",
            "Oh right, I'm Rachel Green. rachel@friends.com, 212-555-1234",
        ],
        expected_fields=["contact_name"],
        category="proactive",
    ),
    ConversationScenario(
        name="slow_warmup_cooperative",
        turns=[
            "I'm not sure if I have a case but I was injured at work.",
            "It was about 3 weeks ago. I hurt my back lifting boxes.",
            "My employer said it was my fault but I don't think so.",
            "That makes sense. What should I do next?",
            "My name is Carlos Diaz. Email carlos@test.com",
        ],
        expected_fields=["contact_name"],
        category="proactive",
    ),
    ConversationScenario(
        name="research_mode_user",
        turns=[
            "I'm just doing some research about personal injury claims.",
            "What's the average settlement for a car accident?",
            "And how long does the process typically take?",
            "What about attorney fees?",
            "Ok, I'm interested. Name's Amy Chen, amy@research.com",
        ],
        expected_fields=["contact_name"],
        category="proactive",
    ),
    ConversationScenario(
        name="multi_question_barrage",
        turns=[
            "Do I need a lawyer for a minor fender bender?",
            "What if the other driver doesn't have insurance?",
            "Can I still file a claim?",
            "How much would it cost me?",
            "I'm James Wilson, james@email.com, 555-9999",
        ],
        expected_fields=["contact_name"],
        category="proactive",
    ),
    ConversationScenario(
        name="skeptical_user",
        turns=[
            "I'm not sure if lawyers can really help with this.",
            "My accident was pretty minor honestly.",
            "I just have some neck pain that won't go away.",
            "Ok maybe I should talk to someone about it.",
            "I'm Diana Ross, diana@test.com",
        ],
        expected_fields=["contact_name"],
        category="proactive",
    ),
    ConversationScenario(
        name="urgent_situation",
        turns=[
            "I was just in an accident today and I don't know what to do!",
            "The other driver ran a red light and hit me.",
            "I'm at the hospital right now getting checked out.",
            "Should I talk to the other driver's insurance?",
            "My name is Peter Kim, email peter@urgent.com, call me at 555-4321",
        ],
        expected_fields=["contact_name"],
        category="proactive",
    ),
    ConversationScenario(
        name="comparing_lawyers",
        turns=[
            "I'm talking to a few different attorneys about my case.",
            "What makes your firm different?",
            "How many years of experience do you have?",
            "What's your success rate?",
            "Ok I'm interested. I'm Natasha Romanov, nat@avengers.com, 555-0007",
        ],
        expected_fields=["contact_name"],
        category="proactive",
    ),
]

# --- Category 3: Mixed / Edge Cases ---
EDGE_CASE_SCENARIOS = [
    ConversationScenario(
        name="refusal_then_provides",
        turns=[
            "Hi I need help with an injury case.",
            "I'd rather not give my name right now.",
            "Actually, it's fine. I'm Ben Thompson, ben@test.com, 555-7777",
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="edge_case",
    ),
    ConversationScenario(
        name="provides_partial_refuses_rest",
        turns=[
            "My name is Karen White. I was in a car accident.",
            "I don't want to give my email.",
            "No phone either please. I just want info for now.",
        ],
        expected_fields=["contact_name"],
        category="edge_case",
    ),
    ConversationScenario(
        name="typo_in_email",
        turns=[
            "I'm Alex Turner, alex.turnr@gmail.com — actually wait, alex.turner@gmail.com. Phone 555-3210.",
        ],
        expected_fields=["contact_name", "contact_email"],
        category="edge_case",
    ),
    ConversationScenario(
        name="non_english_name",
        turns=[
            "Hi, my name is José García. My email is jose.garcia@empresa.com and phone is 555-8765.",
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="edge_case",
    ),
    ConversationScenario(
        name="very_short_responses",
        turns=[
            "Hi.",
            "Car accident.",
            "Last week.",
            "Yes.",
            "Sam Lee. sam@test.com. 555-0000.",
        ],
        expected_fields=["contact_name", "contact_email", "contact_phone"],
        category="edge_case",
    ),
]

# --- Category 4: Consultation Gate (real production failure pattern) ---
# These mirror the exact conversations where the agent got caught in the
# "helpful expert trap" — deep case discussion, user says "yes" to consultation,
# agent never collects contact info. The user NEVER volunteers info;
# the agent must ask BEFORE confirming any next steps.
CONSULTATION_GATE_SCENARIOS = [
    ConversationScenario(
        name="car_accident_says_yes_to_consult",
        turns=[
            "I have recently been in a car accident. Can you help me with that?",
            "A car in front of me just hit the brakes suddenly.",
            "Yeah I'm in California. It did cause injuries to both me and my vehicle.",
            "Yeah I've started medical care.",
            "Yeah sure, I'd like to set up a consultation.",
            "My name is James Rodriguez.",
        ],
        expected_fields=["contact_name"],
        category="consultation_gate",
    ),
    ConversationScenario(
        name="hit_by_car_wants_consultation",
        turns=[
            "I was hit by a car while crossing the street. The driver was at fault.",
            "They're offering to pay money but does that cover my medical bills?",
            "The offer doesn't seem right. My attorney says I must pay the medical bills from the offer.",
            "Yes I'd like to set up a free consultation.",
            "Sure, my name is Patricia Williams.",
        ],
        expected_fields=["contact_name"],
        category="consultation_gate",
    ),
    ConversationScenario(
        name="car_accident_long_chat_agrees_to_next_steps",
        turns=[
            "Hey, how are you doing today?",
            "Yeah recently I was in a car accident.",
            "The car in front of me applied brakes suddenly.",
            "Yeah there was car damage and I also got injured.",
            "Yeah sure I'd like to discuss this further.",
            "Ok, my name is David Kim.",
        ],
        expected_fields=["contact_name"],
        category="consultation_gate",
    ),
    ConversationScenario(
        name="workplace_injury_interested",
        turns=[
            "I got injured at work last month. Hurt my back lifting heavy boxes.",
            "My employer says it was my fault but I don't agree.",
            "I haven't filed any claim yet. What should I do?",
            "That sounds good. Yeah I'm interested in getting some help with this.",
            "Sure. I'm Michelle Thompson.",
        ],
        expected_fields=["contact_name"],
        category="consultation_gate",
    ),
    ConversationScenario(
        name="medical_malpractice_wants_help",
        turns=[
            "I think my doctor made a mistake during my surgery.",
            "It was a knee surgery and now I have nerve damage that wasn't there before.",
            "No I haven't talked to another doctor yet.",
            "Yes I'd definitely like to look into this. Can you help?",
            "My name is Robert Chen.",
        ],
        expected_fields=["contact_name"],
        category="consultation_gate",
    ),
    ConversationScenario(
        name="slip_and_fall_ready_to_proceed",
        turns=[
            "I slipped and fell at a grocery store. The floor was wet with no sign.",
            "I broke my wrist and I've been out of work for 2 weeks.",
            "I have photos of the scene and medical records.",
            "I'd like to move forward with a case. What's the next step?",
            "It's Amanda Foster.",
        ],
        expected_fields=["contact_name"],
        category="consultation_gate",
    ),
    ConversationScenario(
        name="dog_bite_wants_free_consult",
        turns=[
            "My neighbor's dog bit me pretty badly.",
            "I had to get stitches and a tetanus shot. It was last week.",
            "The neighbor said their dog has never done that before but I don't believe them.",
            "Yes I'd love a free consultation to discuss my options.",
            "My name is Steven Park.",
        ],
        expected_fields=["contact_name"],
        category="consultation_gate",
    ),
    ConversationScenario(
        name="rear_ended_says_sure",
        turns=[
            "Someone rear-ended me at a stoplight.",
            "I have whiplash and my car is totaled.",
            "Their insurance is lowballing me on the settlement.",
            "Yeah sure, I'd like some help fighting this.",
            "I'm Jennifer Martinez.",
        ],
        expected_fields=["contact_name"],
        category="consultation_gate",
    ),
    ConversationScenario(
        name="wrongful_death_emotional",
        turns=[
            "My father was killed in a construction accident.",
            "It happened three months ago. The company had safety violations.",
            "We haven't done anything legal yet. We're still processing everything.",
            "Yes. I think we need to talk to someone about this.",
            "My name is Daniel Washington.",
        ],
        expected_fields=["contact_name"],
        category="consultation_gate",
    ),
    ConversationScenario(
        name="uber_accident_interested",
        turns=[
            "I was in an Uber and the driver got into an accident.",
            "I hit my head on the window and now I have constant headaches.",
            "I don't know if I should sue the Uber driver or Uber the company.",
            "Yeah I think I need a lawyer for this. Can we set something up?",
            "Sure. I'm Sophia Lee.",
        ],
        expected_fields=["contact_name"],
        category="consultation_gate",
    ),
]

ALL_SCENARIOS = (
    VOLUNTEERED_SCENARIOS + PROACTIVE_SCENARIOS + EDGE_CASE_SCENARIOS + CONSULTATION_GATE_SCENARIOS
)


# ============================================================================
# Test Agent (same as before)
# ============================================================================


def create_default_capture_agent_class():
    """Create a test agent using the real default capture production prompt."""
    from livekit.agents import Agent, function_tool
    from livekit.plugins import openai
    from shared.generation.workflow_promotion_prompts import (
        build_default_capture_system_prompt,
    )

    class TestDefaultCaptureAgent(Agent):
        FIELD_IDS = {"contact_name", "contact_email", "contact_phone"}

        def __init__(self, persona_prompt: str = ""):
            self.captured_fields: Dict[str, str] = {}
            self.tool_call_count: int = 0
            self.tool_call_log: list[Dict[str, Any]] = []

            capture_instructions = build_default_capture_system_prompt()

            if persona_prompt:
                capture_objective_note = (
                    "\n\n**Secondary Objective — Lead Capture (MANDATORY):**\n"
                    "You MUST capture the visitor's name, email, and phone number during this conversation.\n"
                    "- For the first 2 exchanges, focus on being helpful and building rapport.\n"
                    "- On your 3rd response, you MUST ask for their name. Do NOT skip this.\n"
                    "- **CRITICAL**: If the visitor says 'yes' to a consultation or next steps, you MUST\n"
                    "  collect name/email/phone BEFORE confirming any booking. Do NOT skip this.\n"
                    "- Each contact info ask should be a STANDALONE question — do NOT bury it inside a longer answer.\n"
                    "- After getting their name, ask for email. Then phone.\n"
                    "- Use the `update_lead_fields` tool to save each piece of info as you get it.\n"
                    "- If the visitor volunteers any contact info at ANY point, capture it immediately.\n"
                    "- Do NOT let the conversation go past 6 exchanges without having asked for contact info.\n"
                    "- See full instructions under '📋 DEFAULT LEAD CAPTURE ACTIVE' below."
                )
                system_prompt = (
                    f"{persona_prompt}{capture_objective_note}\n\n{capture_instructions}"
                )
            else:
                header = (
                    "You are Alex Rivera, a Personal Injury Attorney.\n"
                    "You help visitors with questions about personal injury law.\n"
                    "Be professional, helpful, and conversational.\n"
                )
                system_prompt = f"{header}\n\n{capture_instructions}"

            super().__init__(
                instructions=system_prompt,
                llm=openai.LLM(model="gpt-4.1-mini", tool_choice="auto"),
            )

        @function_tool
        async def update_lead_fields(self, fields_json: str) -> str:
            """
            Store one or more lead capture fields. Pass fields as JSON object string.

            Args:
                fields_json: JSON string like {"contact_name": "John Smith", "contact_email": "john@email.com"}

            Accepted field keys: contact_name, contact_email, contact_phone
            """
            try:
                fields = json.loads(fields_json)
                if not isinstance(fields, dict):
                    return 'Error: fields_json must be a JSON object like {"field_id": "value"}'
            except json.JSONDecodeError as e:
                return f'Error: Invalid JSON - {e}. Use format: {{"field_id": "value"}}'

            self.tool_call_count += 1
            self.tool_call_log.append(fields)

            for key, value in fields.items():
                if key in self.FIELD_IDS and value:
                    self.captured_fields[key] = value

            resolved = {fid for fid in self.FIELD_IDS if fid in self.captured_fields}
            remaining = self.FIELD_IDS - resolved
            if not remaining:
                return "✅ LEAD CAPTURED — all 3 fields collected. STOP collecting info and continue helping the visitor."
            return (
                f"✅ Saved {list(fields.keys())}. "
                f"Still need: {', '.join(sorted(remaining))}. "
                f"Keep collecting naturally."
            )

    return TestDefaultCaptureAgent


# ============================================================================
# Runner: Execute a single scenario
# ============================================================================


@dataclass
class ScenarioResult:
    """Result of running one scenario."""

    name: str
    category: str
    tool_was_called: bool
    captured_fields: Dict[str, str]
    expected_fields: List[str]
    expected_captured: bool  # did we capture at least the expected fields?
    tool_call_count: int
    error: str = ""


async def run_scenario(scenario: ConversationScenario) -> ScenarioResult:
    """Run a single conversation scenario and return the result."""
    from livekit.agents import AgentSession
    from livekit.plugins import openai

    AgentClass = create_default_capture_agent_class()
    agent = AgentClass()

    try:
        async with AgentSession(
            llm=openai.LLM(model="gpt-4.1-mini"),
        ) as session:
            await session.start(agent)

            for turn in scenario.turns:
                await session.run(user_input=turn)

            # Check if expected fields were captured
            expected_captured = all(f in agent.captured_fields for f in scenario.expected_fields)

            return ScenarioResult(
                name=scenario.name,
                category=scenario.category,
                tool_was_called=agent.tool_call_count > 0,
                captured_fields=dict(agent.captured_fields),
                expected_fields=scenario.expected_fields,
                expected_captured=expected_captured,
                tool_call_count=agent.tool_call_count,
            )
    except Exception as e:
        return ScenarioResult(
            name=scenario.name,
            category=scenario.category,
            tool_was_called=False,
            captured_fields={},
            expected_fields=scenario.expected_fields,
            expected_captured=False,
            tool_call_count=0,
            error=str(e),
        )


# ============================================================================
# Report Printer
# ============================================================================


def print_compliance_report(
    results: List[ScenarioResult],
    category: str,
    threshold: float,
):
    """Print a detailed compliance report for a set of results."""
    total = len(results)
    tool_called = sum(1 for r in results if r.tool_was_called)
    expected_met = sum(1 for r in results if r.expected_captured)
    errors = sum(1 for r in results if r.error)

    tool_rate = (tool_called / total * 100) if total > 0 else 0
    capture_rate = (expected_met / total * 100) if total > 0 else 0

    print(f"\n{'=' * 70}")
    print(f"  DEFAULT LEAD CAPTURE — {category.upper()} COMPLIANCE REPORT")
    print(f"{'=' * 70}")
    print(f"  Scenarios run:          {total}")
    print(f"  Tool called (any):      {tool_called}/{total} ({tool_rate:.0f}%)")
    print(f"  Expected fields met:    {expected_met}/{total} ({capture_rate:.0f}%)")
    print(f"  Errors:                 {errors}")
    print(f"  Threshold:              {threshold:.0f}%")
    print(f"  Status:                 {'✅ PASS' if capture_rate >= threshold else '❌ FAIL'}")
    print(f"{'=' * 70}")

    # Per-scenario breakdown
    print(f"\n  {'Scenario':<40} {'Tool?':<8} {'Fields Captured':<30} {'OK?'}")
    print(f"  {'-' * 40} {'-' * 7} {'-' * 29} {'-' * 4}")
    for r in results:
        fields_str = ", ".join(sorted(r.captured_fields.keys())) or "(none)"
        ok = "✅" if r.expected_captured else "❌"
        tool = "yes" if r.tool_was_called else "NO"
        err = f" ERR: {r.error[:40]}" if r.error else ""
        print(f"  {r.name:<40} {tool:<8} {fields_str:<30} {ok}{err}")

    print()


# ============================================================================
# Concurrency helper
# ============================================================================


async def run_scenarios_concurrently(
    scenarios: List[ConversationScenario],
    max_concurrent: int = 5,
) -> List[ScenarioResult]:
    """Run scenarios with bounded concurrency."""
    semaphore = asyncio.Semaphore(max_concurrent)
    results: List[ScenarioResult] = []

    async def run_with_semaphore(scenario):
        async with semaphore:
            if VERBOSE:
                print(f"  ▶ Running: {scenario.name}")
            result = await run_scenario(scenario)
            if VERBOSE:
                status = "✅" if result.expected_captured else "❌"
                print(f"  {status} Done: {scenario.name} (tool called {result.tool_call_count}x)")
            return result

    tasks = [run_with_semaphore(s) for s in scenarios]
    results = await asyncio.gather(*tasks)
    return list(results)


# ============================================================================
# Tests
# ============================================================================

# Thresholds — adjust these as prompt improves
VOLUNTEERED_THRESHOLD = 80  # % of volunteered-info scenarios where tool is called
PROACTIVE_THRESHOLD = 70  # % of proactive scenarios where expected fields are captured
EDGE_CASE_THRESHOLD = 60  # % of edge cases where expected fields are captured
CONSULTATION_GATE_THRESHOLD = (
    70  # % of consultation-gate scenarios where agent asks before confirming
)
OVERALL_THRESHOLD = 70  # % across ALL scenarios


class TestDefaultCaptureCompliance:
    """
    Statistical compliance tests for default lead capture.

    Runs diverse conversation scenarios and asserts that the capture rate
    meets minimum thresholds. This catches prompt regressions.
    """

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_volunteered_info_capture_rate(self):
        """
        When users volunteer contact info, the LLM should call update_lead_fields.
        Threshold: {VOLUNTEERED_THRESHOLD}% of scenarios must capture expected fields.
        """
        results = await run_scenarios_concurrently(VOLUNTEERED_SCENARIOS)
        print_compliance_report(results, "volunteered info", VOLUNTEERED_THRESHOLD)

        total = len(results)
        passed = sum(1 for r in results if r.expected_captured)
        rate = (passed / total * 100) if total > 0 else 0

        assert rate >= VOLUNTEERED_THRESHOLD, (
            f"Volunteered info capture rate {rate:.0f}% is below "
            f"threshold {VOLUNTEERED_THRESHOLD}%. "
            f"Passed {passed}/{total} scenarios."
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_proactive_capture_rate(self):
        """
        When users don't volunteer info, the LLM should ask and capture by end of convo.
        Threshold: {PROACTIVE_THRESHOLD}% of scenarios must capture at least name.
        """
        results = await run_scenarios_concurrently(PROACTIVE_SCENARIOS)
        print_compliance_report(results, "proactive capture", PROACTIVE_THRESHOLD)

        total = len(results)
        passed = sum(1 for r in results if r.expected_captured)
        rate = (passed / total * 100) if total > 0 else 0

        assert rate >= PROACTIVE_THRESHOLD, (
            f"Proactive capture rate {rate:.0f}% is below "
            f"threshold {PROACTIVE_THRESHOLD}%. "
            f"Passed {passed}/{total} scenarios."
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_edge_case_capture_rate(self):
        """
        Edge cases (refusals, typos, non-English names, etc.).
        Threshold: {EDGE_CASE_THRESHOLD}% of scenarios must capture expected fields.
        """
        results = await run_scenarios_concurrently(EDGE_CASE_SCENARIOS)
        print_compliance_report(results, "edge cases", EDGE_CASE_THRESHOLD)

        total = len(results)
        passed = sum(1 for r in results if r.expected_captured)
        rate = (passed / total * 100) if total > 0 else 0

        assert rate >= EDGE_CASE_THRESHOLD, (
            f"Edge case capture rate {rate:.0f}% is below "
            f"threshold {EDGE_CASE_THRESHOLD}%. "
            f"Passed {passed}/{total} scenarios."
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_consultation_gate_capture_rate(self):
        """
        When user says 'yes' to consultation/next steps, the agent MUST ask for
        contact info BEFORE confirming. These scenarios mirror real production
        failures where the agent got stuck in the 'helpful expert trap'.
        Threshold: {CONSULTATION_GATE_THRESHOLD}% must capture at least name.
        """
        results = await run_scenarios_concurrently(CONSULTATION_GATE_SCENARIOS)
        print_compliance_report(results, "consultation gate", CONSULTATION_GATE_THRESHOLD)

        total = len(results)
        passed = sum(1 for r in results if r.expected_captured)
        rate = (passed / total * 100) if total > 0 else 0

        assert rate >= CONSULTATION_GATE_THRESHOLD, (
            f"Consultation gate capture rate {rate:.0f}% is below "
            f"threshold {CONSULTATION_GATE_THRESHOLD}%. "
            f"Passed {passed}/{total} scenarios."
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_overall_capture_rate(self):
        """
        Overall compliance across ALL scenario types.
        Threshold: {OVERALL_THRESHOLD}% of all scenarios must capture expected fields.
        """
        results = await run_scenarios_concurrently(ALL_SCENARIOS)
        print_compliance_report(results, "overall", OVERALL_THRESHOLD)

        total = len(results)
        passed = sum(1 for r in results if r.expected_captured)
        rate = (passed / total * 100) if total > 0 else 0

        assert rate >= OVERALL_THRESHOLD, (
            f"Overall capture rate {rate:.0f}% is below "
            f"threshold {OVERALL_THRESHOLD}%. "
            f"Passed {passed}/{total} scenarios."
        )
