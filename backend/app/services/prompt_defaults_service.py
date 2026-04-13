"""
Prompt Defaults Service

This module provides default values for prompt template fields and persona prompt fields.
These defaults are used across the application when creating or updating prompts without
explicit values provided.

All defaults are centralized here to ensure consistency across:
- PromptTemplate creation
- PersonaPrompt creation
- AdvancedPromptCreator
- API endpoints
"""

import json
from typing import Dict, List

# Default response structure constant
DEFAULT_RESPONSE_STRUCTURE: List[Dict[str, str]] = [
    {"response_structure": '{"response_length":"explanatory","creativity":"adaptive"}'}
]


class PromptDefaultsService:
    """
    Service class providing default values for prompt-related fields.

    This class is independent and can be used across the application without
    any dependencies on other services or heavy components.
    """

    @staticmethod
    def get_default_thinking_style() -> str:
        """
        Get default thinking style for personas.

        Returns:
            str: Default thinking style description
        """
        return "Thoughtful and analytical approach with focus on practical solutions."

    @staticmethod
    def get_default_chat_objective() -> str:
        """
        Get default chat objective for persona interactions.

        Returns:
            str: Default chat objective description
        """
        return """
To provide expert-level insights and guidance based on the persona's areas of expertise,
maintaining their authentic communication style while delivering valuable, actionable advice
to users seeking professional knowledge and mentorship.
        """.strip()

    @staticmethod
    def get_default_objective_response() -> str:
        """
        Get default objective response guidelines.

        Returns:
            str: Default objective response guidelines
        """
        return """
Responses should be informative, engaging, and tailored to the user's level of understanding.
Focus on practical applications, real-world examples, and actionable insights that reflect
the persona's expertise and experience in their field.
        """.strip()

    @staticmethod
    def get_default_response_structure() -> str:
        """
        Get default response structure as JSON string.

        Returns:
            str: JSON string containing default response structure
        """
        return json.dumps(DEFAULT_RESPONSE_STRUCTURE)

    @staticmethod
    def get_default_conversation_flow() -> str:
        """
        Get default conversation flow pattern.

        Returns:
            str: Default conversation flow description
        """
        return """
GREETING: Warm, professional acknowledgment
LISTENING: Understand user's needs and context
EXPERTISE: Share relevant knowledge and insights
GUIDANCE: Provide actionable advice and recommendations
ENGAGEMENT: Encourage questions and continued interaction
CLOSURE: Summarize key points and offer ongoing support
        """.strip()

    @staticmethod
    def get_default_strict_guideline() -> str:
        """
        Get default strict guidelines for persona behavior.

        Returns:
            str: Default strict guidelines as numbered list
        """
        return """
1. Stay within the persona's area of expertise
2. Maintain the persona's authentic communication style
3. Provide accurate, evidence-based information
4. Acknowledge limitations when appropriate
5. Redirect off-topic questions gracefully
6. Avoid speculation beyond expertise
7. Maintain professional and ethical standards
        """.strip()

    @staticmethod
    def get_all_defaults() -> Dict[str, str]:
        """
        Get all default values as a dictionary.

        Useful for bulk operations or when multiple defaults are needed.

        Returns:
            Dict[str, str]: Dictionary containing all default values
        """
        return {
            "thinking_style": PromptDefaultsService.get_default_thinking_style(),
            "chat_objective": PromptDefaultsService.get_default_chat_objective(),
            "objective_response": PromptDefaultsService.get_default_objective_response(),
            "response_structure": PromptDefaultsService.get_default_response_structure(),
            "conversation_flow": PromptDefaultsService.get_default_conversation_flow(),
            "strict_guideline": PromptDefaultsService.get_default_strict_guideline(),
        }

    @staticmethod
    def apply_defaults(data: Dict[str, str], fields: List[str] = None) -> Dict[str, str]:
        """
        Apply default values to a dictionary for any missing fields.

        Args:
            data: Dictionary with potentially missing fields
            fields: Optional list of field names to apply defaults for.
                   If None, applies all defaults.

        Returns:
            Dict[str, str]: Dictionary with defaults applied for missing fields

        Example:
            >>> data = {"thinking_style": "Custom style"}
            >>> result = PromptDefaultsService.apply_defaults(data)
            >>> # result will have custom thinking_style and default values for other fields
        """
        defaults = PromptDefaultsService.get_all_defaults()

        # If specific fields are requested, filter defaults
        if fields:
            defaults = {k: v for k, v in defaults.items() if k in fields}

        # Apply defaults only for missing or None values
        for key, default_value in defaults.items():
            if key not in data or data[key] is None:
                data[key] = default_value

        return data

    @staticmethod
    def get_default_for_field(field_name: str) -> str:
        """
        Get default value for a specific field by name.

        Args:
            field_name: Name of the field to get default for

        Returns:
            str: Default value for the field

        Raises:
            ValueError: If field_name is not a recognized field
        """
        defaults_map = {
            "thinking_style": PromptDefaultsService.get_default_thinking_style,
            "chat_objective": PromptDefaultsService.get_default_chat_objective,
            "objective_response": PromptDefaultsService.get_default_objective_response,
            "response_structure": PromptDefaultsService.get_default_response_structure,
            "conversation_flow": PromptDefaultsService.get_default_conversation_flow,
            "strict_guideline": PromptDefaultsService.get_default_strict_guideline,
        }

        if field_name not in defaults_map:
            raise ValueError(
                f"Unknown field '{field_name}'. "
                f"Valid fields are: {', '.join(defaults_map.keys())}"
            )

        return defaults_map[field_name]()
