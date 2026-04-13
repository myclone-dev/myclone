"""
Workflow Objective Generator - LLM-based generation of natural, persona-aligned objectives

This module generates conversational workflow objectives that guide the AI's behavior
during workflows. Objectives are contextual and match the persona's communication style.
"""

import logging
from typing import Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class WorkflowObjectiveGenerator:
    """Generate workflow objectives using LLM for natural, contextual results"""

    def __init__(self, api_key: Optional[str] = None):
        from shared.config import settings

        self.client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)

    async def generate_objective(
        self,
        workflow_data: dict,
        persona_style: Optional[str] = None,
        promotion_mode: Optional[str] = None,
    ) -> str:
        """
        Generate a workflow objective using LLM.

        Args:
            workflow_data: Workflow configuration (title, type, questions, categories, trigger_config)
            persona_style: Optional persona tone/style to match
            promotion_mode: Optional promotion mode ('proactive', 'contextual', 'reactive')
                          If not provided, defaults based on workflow_type

        Returns:
            Generated workflow objective string (2-3 sentences)
        """
        try:
            # Extract workflow details
            title = workflow_data.get("title", "assessment")
            workflow_type = workflow_data.get("workflow_type", "simple")
            steps = workflow_data.get("workflow_config", {}).get("steps", [])
            result_config = workflow_data.get("result_config", {})
            opening_message = workflow_data.get("opening_message")

            # Determine promotion mode (from parameter, trigger_config, or default)
            trigger_config = workflow_data.get("trigger_config") or {}
            if not promotion_mode:
                promotion_mode = trigger_config.get("promotion_mode")

            # Apply smart default if still not set: 'proactive' for scored, 'contextual' for simple
            if not promotion_mode:
                promotion_mode = "proactive" if workflow_type == "scored" else "contextual"
                logger.info(
                    f"📊 Auto-defaulted promotion_mode='{promotion_mode}' based on workflow_type='{workflow_type}'"
                )
            else:
                logger.info(f"🎯 Using explicit promotion_mode='{promotion_mode}'")

            # Extract max_attempts and cooldown_turns from trigger_config (with defaults)
            max_attempts = trigger_config.get("max_attempts", 3)
            cooldown_turns = trigger_config.get("cooldown_turns", 5)
            logger.info(
                f"⚙️ Trigger config: max_attempts={max_attempts}, cooldown_turns={cooldown_turns}"
            )

            # Build context about the workflow
            question_texts = [
                step.get("question_text", "") for step in steps[:5]
            ]  # First 5 for context
            question_count = len(steps)

            categories = []
            if workflow_type == "scored" and result_config:
                categories = [
                    {
                        "name": cat.get("name"),
                        "message": cat.get("message", "")[:100],  # First 100 chars
                    }
                    for cat in result_config.get("categories", [])
                ]

            # Build the prompt based on promotion mode
            prompt = self._build_generation_prompt(
                title=title,
                workflow_type=workflow_type,
                question_count=question_count,
                sample_questions=question_texts,
                categories=categories,
                opening_message=opening_message,
                persona_style=persona_style,
                promotion_mode=promotion_mode,
                max_attempts=max_attempts,
                cooldown_turns=cooldown_turns,
            )

            # Generate using OpenAI
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at creating concise, action-oriented objectives for AI assistants. Generate natural, conversational objectives that guide user interactions.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )

            objective = response.choices[0].message.content.strip()
            logger.info(f"✨ Generated workflow objective: {objective[:100]}...")

            return objective

        except Exception as e:
            logger.error(f"❌ Failed to generate workflow objective: {e}")
            # Fallback to simple template
            return self._fallback_objective(workflow_data)

    def _build_generation_prompt(
        self,
        title: str,
        workflow_type: str,
        question_count: int,
        sample_questions: list,
        categories: list,
        opening_message: Optional[str],
        persona_style: Optional[str],
        promotion_mode: str,
        max_attempts: int,
        cooldown_turns: int,
    ) -> str:
        """Build the LLM prompt for objective generation based on promotion mode"""

        # Common workflow details section
        prompt = f"""Generate a conversational workflow objective for an AI voice assistant.

**Workflow Details:**
- Title: "{title}"
- Type: {workflow_type}
- Question Count: {question_count}
- Promotion Mode: {promotion_mode}

**Sample Questions:**
{chr(10).join(f"- {q}" for q in sample_questions[:5])}
"""

        if opening_message:
            prompt += f"\n**Opening Message:**\n{opening_message}\n"

        if categories:
            prompt += "\n**Result Categories:**\n"
            for cat in categories:
                prompt += f"- {cat['name']}: {cat['message']}\n"

        if persona_style:
            prompt += f"\n**Persona Tone/Style:**\n{persona_style}\n"

        # Add mode-specific requirements and examples
        if promotion_mode == "proactive":
            prompt += self._get_proactive_requirements(max_attempts, cooldown_turns)
        elif promotion_mode == "reactive":
            prompt += self._get_reactive_requirements(max_attempts, cooldown_turns)
        else:  # contextual
            prompt += self._get_contextual_requirements(max_attempts, cooldown_turns)

        prompt += "\nGenerate the objective now:"

        return prompt

    def _get_proactive_requirements(self, max_attempts: int, cooldown_turns: int) -> str:
        """Requirements and examples for PROACTIVE promotion mode"""
        return f"""
**PROACTIVE MODE Requirements:**
1. Your PRIMARY goal is to guide users to take this workflow within the first 1-2 exchanges
2. Be DIRECT and IMMEDIATE - don't wait for perfect timing or user to mention related topics
3. Provide a clear script for introducing the workflow right after greeting
4. Explain the value proposition upfront (why take it now)
5. Keep it friendly but assertive - this is the main purpose of the interaction

**RE-SUGGESTION POLICY:**
- If user declines, support their questions normally
- Re-suggest up to {max_attempts} times when conversation touches related topics
- Wait at least {cooldown_turns} conversation turns between re-suggestions

**GOOD Example (Proactive):**
"Your PRIMARY goal is to guide users to take the Business Readiness Quiz within the first 1-2 exchanges. This 14-question assessment reveals their business maturity level and provides actionable insights.

Introduce it IMMEDIATELY after greeting - don't wait for them to ask or mention problems.

Example script: 'Before we dive in, I have a Business Readiness Quiz that can give you clarity on where your business stands. Want to take it? It's 14 quick questions and super insightful for pinpointing growth opportunities.'

If they decline, support their questions, but if they mention scaling, leadership, or team challenges, circle back: 'This is exactly why the quiz would help - want to give it a try?' Re-suggest up to {max_attempts} times with {cooldown_turns}+ turns between attempts.

TIMING: Mention the workflow by turn 2-3 maximum."

**BAD Example (too passive):**
"Help users with business growth. When they mention challenges, suggest the quiz."
"""

    def _get_contextual_requirements(self, max_attempts: int, cooldown_turns: int) -> str:
        """Requirements and examples for CONTEXTUAL promotion mode"""
        return f"""
**CONTEXTUAL MODE Requirements:**
1. Wait for conversation to naturally align with workflow purpose before mentioning
2. Use relevant topics as transition points to suggest the workflow
3. Explain how the workflow relates to what they just mentioned
4. Don't force it - if conversation doesn't touch related topics, that's okay
5. Keep it as a helpful suggestion, not a push

**RE-SUGGESTION POLICY:**
- If user declines but later discussion becomes relevant again, you may re-suggest
- Re-suggest up to {max_attempts} times total when contextually appropriate
- Wait at least {cooldown_turns} conversation turns between re-suggestions

**GOOD Example (Contextual):**
"Support users in exploring business growth strategies. When the conversation naturally touches on scaling challenges, leadership clarity, or team dynamics, introduce the Business Readiness Quiz as a helpful diagnostic tool.

Example transitions:
- If they mention growth struggles: 'This sounds like a perfect time for my Business Readiness Quiz - it'll help identify your biggest bottlenecks.'
- If they ask about scaling: 'Before we dive into strategies, want to take a quick quiz to assess where you're at? It's really insightful.'

Only suggest the workflow when contextually relevant - don't interrupt unrelated conversations. If they decline, you may re-suggest up to {max_attempts} times when topics align again (wait {cooldown_turns}+ turns between attempts)."

**BAD Example (too pushy):**
"Always mention the quiz within 2 turns regardless of what the user is talking about."
"""

    def _get_reactive_requirements(self, max_attempts: int, cooldown_turns: int) -> str:
        """Requirements and examples for REACTIVE promotion mode"""
        return f"""
**REACTIVE MODE Requirements:**
1. ONLY mention the workflow if user explicitly asks or indicates interest
2. Wait for user to initiate workflow-related questions
3. Keep it as an available tool but don't promote it proactively
4. Focus on answering their questions first, workflow is secondary
5. Treat it like a booking/scheduling tool - available when they need it

**RE-SUGGESTION POLICY:**
- Since this is reactive mode, re-suggestion rarely applies
- Only mention again if user asks about available tools/resources again
- Maximum {max_attempts} mentions total (if user repeatedly asks)
- Wait at least {cooldown_turns} turns between mentions if they ask multiple times

**GOOD Example (Reactive):**
"Support users with their business questions and provide helpful guidance. This workflow is available as a tool if users explicitly request it or ask what resources you have.

ONLY mention it if:
- User asks: 'What can you help me with?' or 'Do you have any tools?'
- User explicitly requests an assessment or evaluation

Otherwise, focus on answering their questions directly. The workflow is a background resource, not a primary goal.

Example response: 'I can answer questions about business growth, and I also have a Business Readiness Quiz if you'd like to assess your current state - but let's focus on what you came here for first.'"

**BAD Example (too proactive):**
"Actively guide users to take the quiz and mention it early in the conversation."
"""

    def _fallback_objective(self, workflow_data: dict) -> str:
        """Fallback to simple template if LLM fails"""
        title = workflow_data.get("title", "assessment")
        return (
            f"Guide users to complete the '{title}' when relevant to their questions. "
            f"Explain how it can help them gain insights into their situation."
        )


# Convenience function for API routes
async def generate_workflow_objective(
    workflow_data: dict,
    persona_style: Optional[str] = None,
    promotion_mode: Optional[str] = None,
) -> str:
    """Generate a workflow objective using LLM"""
    generator = WorkflowObjectiveGenerator()
    return await generator.generate_objective(workflow_data, persona_style, promotion_mode)
