"""
Conversation Summary Service - Generates AI-powered summaries of conversations
"""

import logging
from typing import Dict, List, Optional

import httpx
from openai import AsyncOpenAI

from shared.config import settings

logger = logging.getLogger(__name__)


class ConversationSummaryService:
    """Service for generating AI-powered conversation summaries"""

    def __init__(self, api_key: str | None = None):
        """
        Initialize the conversation summary service.

        Args:
            api_key: Optional OpenAI API key. If not provided, uses settings.
        """
        self.api_key = api_key or settings.openai_api_key
        self.logger = logging.getLogger(__name__)

        # Create custom HTTP client with relaxed settings
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=30.0, read=60.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            follow_redirects=True,
            verify=True,
        )

        self.client = AsyncOpenAI(
            api_key=self.api_key, timeout=60.0, max_retries=3, http_client=http_client
        )
        self.model = settings.llm_model

    async def generate_summary(
        self,
        messages: List[Dict],
        conversation_type: str = "text",
        persona_name: Optional[str] = None,
        max_tokens: int = 300,
    ) -> Dict[str, str]:
        """
        Generate an AI-powered summary of a conversation.

        Args:
            messages: List of conversation messages with role and content
            conversation_type: Type of conversation ('text' or 'voice')
            persona_name: Optional name of the persona involved
            max_tokens: Maximum tokens for the summary

        Returns:
            Dict with summary, key_topics, and sentiment
        """
        try:
            if not messages or len(messages) == 0:
                return {
                    "summary": "No messages in this conversation.",
                    "key_topics": "N/A",
                    "sentiment": "neutral",
                }

            # Format conversation for summarization
            conversation_text = self._format_messages(messages, persona_name)

            # Build the prompt for summarization
            system_prompt = self._build_system_prompt(conversation_type)
            user_prompt = self._build_user_prompt(conversation_text, len(messages))

            # Generate summary using OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,  # Lower temperature for more focused summaries
                max_tokens=max_tokens,
            )

            summary_text = response.choices[0].message.content.strip()

            # Parse the structured response
            parsed = self._parse_summary_response(summary_text)

            self.logger.info(
                f"Generated summary for conversation with {len(messages)} messages "
                f"(type: {conversation_type})"
            )

            return parsed

        except Exception as e:
            self.logger.error(f"Error generating conversation summary: {e}")
            # Return a fallback summary
            return {
                "summary": "Unable to generate summary at this time.",
                "key_topics": "Error",
                "sentiment": "neutral",
            }

    async def generate_structured_summary(
        self,
        messages: List[Dict],
        conversation_type: str = "text",
        persona_name: Optional[str] = None,
        max_tokens: int = 800,
    ) -> Dict:
        """
        Generate a structured AI-powered summary optimized for email notifications.

        This generates a concise, actionable summary with:
        - Synopsis: Brief 2-3 sentence overview
        - Key details: Contact info, requirements, context shared
        - Questions & Answers: Key Q&A pairs from the conversation
        - Follow-up: Urgency level, next steps, action items

        Args:
            messages: List of conversation messages with role and content
            conversation_type: Type of conversation ('text' or 'voice')
            persona_name: Optional name of the persona involved
            max_tokens: Maximum tokens for the summary

        Returns:
            Dict with structured summary data
        """
        try:
            if not messages or len(messages) == 0:
                return self._get_empty_structured_summary()

            # Format conversation for summarization
            conversation_text = self._format_messages(messages, persona_name)

            # Build the structured prompt
            system_prompt = self._build_structured_system_prompt(conversation_type)
            user_prompt = self._build_structured_user_prompt(conversation_text, len(messages))

            # Generate summary using OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=max_tokens,
            )

            summary_text = response.choices[0].message.content.strip()

            # Parse the structured JSON response
            parsed = self._parse_structured_summary_response(summary_text)

            self.logger.info(
                f"Generated structured summary for conversation with {len(messages)} messages "
                f"(type: {conversation_type})"
            )

            return parsed

        except Exception as e:
            self.logger.error(f"Error generating structured conversation summary: {e}")
            return self._get_empty_structured_summary()

    def _build_structured_system_prompt(self, conversation_type: str) -> str:
        """Build system prompt for structured summarization"""
        conv_type_desc = "voice call" if conversation_type == "voice" else "text chat"

        return f"""You are an expert conversation analyst. Analyze this {conv_type_desc} and extract a structured summary for the business owner to quickly understand what was discussed and follow up with the visitor.

Your response MUST be valid JSON with this exact structure:
{{
  "synopsis": "2-3 sentence overview of what was discussed and the outcome",
  "key_topics": ["topic1", "topic2", "topic3"],
  "key_details": {{
    "visitor_intent": "What the visitor was looking for or trying to accomplish",
    "requirements": ["Specific need or requirement mentioned"],
    "context_shared": ["Any background info the visitor shared about themselves"]
  }},
  "questions_answers": [
    {{"question": "Key question the visitor asked", "answer": "Summary of the response given"}}
  ],
  "follow_up": {{
    "urgency": "high/medium/low based on visitor's needs",
    "next_steps": ["Suggested action item for follow-up"],
    "notes": "Any important notes for the business owner"
  }},
  "sentiment": "positive/neutral/negative/mixed"
}}

Guidelines:
- Be concise and actionable - this is for quick business follow-up
- Focus on what matters for sales/support follow-up
- Extract only 2-4 most important Q&A pairs
- Identify urgency based on visitor's tone and explicit needs
- If information is not available, use empty arrays or "Not specified"
- Return ONLY valid JSON, no markdown or extra text"""

    def _build_structured_user_prompt(self, conversation_text: str, message_count: int) -> str:
        """Build user prompt for structured summarization"""
        return f"""Analyze this conversation ({message_count} messages) and provide a structured JSON summary:

{conversation_text}

Return ONLY valid JSON matching the required structure."""

    def _parse_structured_summary_response(self, response_text: str) -> Dict:
        """Parse structured JSON summary response from LLM"""
        import json

        try:
            # Try to extract JSON from the response
            # Handle case where LLM might wrap in markdown code blocks
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            parsed = json.loads(text)

            # Validate and ensure required fields exist
            return {
                "synopsis": parsed.get("synopsis", "No summary available."),
                "key_topics": parsed.get("key_topics", []),
                "key_details": parsed.get("key_details", {}),
                "questions_answers": parsed.get("questions_answers", []),
                "follow_up": parsed.get("follow_up", {}),
                "sentiment": parsed.get("sentiment", "neutral"),
            }

        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse structured summary JSON: {e}")
            # Fallback: try to extract what we can from text
            return self._get_empty_structured_summary()

    def _get_empty_structured_summary(self) -> Dict:
        """Return empty structured summary as fallback"""
        return {
            "synopsis": "Unable to generate summary.",
            "key_topics": [],
            "key_details": {},
            "questions_answers": [],
            "follow_up": {},
            "sentiment": "neutral",
        }

    def _format_messages(self, messages: List[Dict], persona_name: Optional[str]) -> str:
        """Format conversation messages into readable text"""
        formatted_lines = []

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            # Skip empty messages
            if not content or not content.strip():
                continue

            # Format role name
            if role == "user":
                speaker = "Visitor"
            elif role == "assistant":
                speaker = persona_name if persona_name else "Assistant"
            else:
                speaker = role.capitalize()

            formatted_lines.append(f"{speaker}: {content}")

        return "\n".join(formatted_lines)

    def _build_system_prompt(self, conversation_type: str) -> str:
        """Build system prompt for summarization"""
        conv_type_desc = "voice call" if conversation_type == "voice" else "text chat"

        return f"""You are an expert conversation analyst. Your task is to analyze {conv_type_desc} conversations and provide concise, insightful summaries.

Your response MUST follow this exact format:

SUMMARY: [2-3 sentence summary of the conversation]

KEY_TOPICS: [Comma-separated list of 3-5 main topics discussed]

SENTIMENT: [overall sentiment: positive/neutral/negative/mixed]

Be objective, concise, and focus on the most important aspects of the conversation."""

    def _build_user_prompt(self, conversation_text: str, message_count: int) -> str:
        """Build user prompt with conversation context"""
        return f"""Analyze this conversation ({message_count} messages) and provide a structured summary:

{conversation_text}

Remember to follow the exact format:
SUMMARY: ...
KEY_TOPICS: ...
SENTIMENT: ..."""

    def _parse_summary_response(self, response_text: str) -> Dict[str, str]:
        """Parse structured summary response from LLM"""
        lines = response_text.strip().split("\n")

        summary = ""
        key_topics = ""
        sentiment = "neutral"

        for line in lines:
            line = line.strip()
            if line.startswith("SUMMARY:"):
                summary = line.replace("SUMMARY:", "").strip()
            elif line.startswith("KEY_TOPICS:"):
                key_topics = line.replace("KEY_TOPICS:", "").strip()
            elif line.startswith("SENTIMENT:"):
                sentiment = line.replace("SENTIMENT:", "").strip().lower()

        # Fallback if parsing fails
        if not summary:
            summary = response_text[:200] + "..." if len(response_text) > 200 else response_text

        # Validate sentiment
        valid_sentiments = ["positive", "neutral", "negative", "mixed"]
        if sentiment not in valid_sentiments:
            sentiment = "neutral"

        return {"summary": summary, "key_topics": key_topics, "sentiment": sentiment}

    async def generate_title(self, messages: List[Dict], max_length: int = 50) -> str:
        """
        Generate a short title for the conversation.

        Args:
            messages: List of conversation messages
            max_length: Maximum length for the title

        Returns:
            Short conversation title
        """
        try:
            if not messages or len(messages) == 0:
                return "Empty Conversation"

            # Get first user message as context
            first_user_msg = next(
                (msg.get("content", "") for msg in messages if msg.get("role") == "user"), ""
            )

            if not first_user_msg:
                return "Conversation"

            # Simple prompt for title generation
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Generate a short, descriptive title (max 5-7 words) for this conversation. Only return the title, nothing else.",
                    },
                    {"role": "user", "content": f"First message: {first_user_msg[:200]}"},
                ],
                temperature=0.3,
                max_tokens=20,
            )

            title = response.choices[0].message.content.strip()

            # Clean up the title
            title = title.strip('"').strip("'").strip()

            # Truncate if too long
            if len(title) > max_length:
                title = title[: max_length - 3] + "..."

            return title

        except Exception as e:
            self.logger.error(f"Error generating conversation title: {e}")
            return "Conversation"
