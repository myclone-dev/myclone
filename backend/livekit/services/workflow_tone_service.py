"""
Workflow Tone Service

This service manages conversation tone presets for conversational workflows.
It provides consistent phrasing for acknowledgments, questions, confirmations,
and completion messages based on the configured tone.

WHY THIS EXISTS:
- Different businesses need different conversation styles
- A luxury CPA firm wants "concierge" (warm, appreciative)
- A high-volume lead gen wants "efficient" (minimal, fast)
- This allows per-workflow customization without code changes

HOW IT WORKS:
- Tone is configured in workflow_config.extraction_strategy.tone
- Handler calls this service to get tone-appropriate text
- All tone logic is centralized here for consistency

AVAILABLE TONES:
- concierge: White-glove premium service (warm, appreciative)
- professional: Friendly but efficient (default)
- casual: Relaxed, conversational
- efficient: Minimal, fast-paced

USAGE:
    tone_service = WorkflowToneService(workflow_data)

    # Get acknowledgment for when user provides info
    ack = tone_service.get_acknowledgment()  # "Got it, thank you."

    # Format a clarifying question
    q = tone_service.format_question(None, "email")  # "Could you tell me your email?"

    # Get confirmation intro
    intro = tone_service.get_confirmation_intro()  # "Perfect! Just to confirm —"
"""

from typing import Any, Dict, List, Optional


class WorkflowToneService:
    """
    Service for managing conversation tone in workflows.

    Provides tone-appropriate phrasing for all workflow interactions.
    Configured via extraction_strategy.tone in workflow config.
    """

    # =========================================================================
    # Tone Presets
    # =========================================================================
    # Each preset defines the "personality" of the conversation.
    # Add new presets here to support additional conversation styles.

    TONE_PRESETS: Dict[str, Dict[str, Any]] = {
        "concierge": {
            # White-glove, premium service feel
            # Best for: High-value clients, luxury services, wealth management
            "acknowledgments": [
                "Wonderful, thank you so much!",
                "That's great, I really appreciate you sharing that.",
                "Thank you, that's very helpful!",
            ],
            "question_prefix": "May I ask",
            "confirmation_intro": "I just want to make sure I have everything correct —",
            "completion_message": "Thank you so much! We'll be in touch with you very soon.",
        },
        "professional": {
            # Friendly but efficient (default)
            # Best for: Most business contexts, B2B services
            "acknowledgments": [
                "Got it, thank you.",
                "Thanks for that.",
                "Noted, thanks.",
            ],
            "question_prefix": "Could you tell me",
            "confirmation_intro": "Perfect! Just to confirm —",
            "completion_message": "Thanks! We'll reach out to you shortly.",
        },
        "casual": {
            # Relaxed, conversational
            # Best for: Informal businesses, creative industries, startups
            "acknowledgments": [
                "Got it!",
                "Cool, thanks!",
                "Awesome!",
            ],
            "question_prefix": "What's",
            "confirmation_intro": "Okay so",
            "completion_message": "You're all set! We'll be in touch soon.",
        },
        "efficient": {
            # Minimal, fast-paced (high-volume)
            # Best for: High-volume lead capture, quick transactions
            "acknowledgments": [
                "Noted.",
                "Got it.",
                "Thanks.",
            ],
            "question_prefix": "",  # Direct questions, no prefix
            "confirmation_intro": "Confirming:",
            "completion_message": "Done. We'll follow up.",
        },
    }

    def __init__(self, workflow_data: Optional[Dict[str, Any]] = None):
        """
        Initialize tone service with workflow configuration.

        Args:
            workflow_data: Workflow configuration containing extraction_strategy.tone
        """
        self.workflow_data = workflow_data
        self._tone = self._extract_tone()

    def _extract_tone(self) -> str:
        """Extract tone from workflow config, defaulting to 'professional'."""
        if not self.workflow_data:
            return "professional"
        extraction_strategy = self.workflow_data.get("extraction_strategy", {})
        return extraction_strategy.get("tone", "professional")

    @property
    def tone(self) -> str:
        """Current tone setting."""
        return self._tone

    def get_tone_config(self, tone: Optional[str] = None) -> Dict[str, Any]:
        """
        Get full configuration for a tone preset.

        Args:
            tone: Tone name (uses configured tone if None)

        Returns:
            Dict with acknowledgments, question_prefix, confirmation_intro, etc.
        """
        tone = tone or self._tone
        return self.TONE_PRESETS.get(tone, self.TONE_PRESETS["professional"])

    # =========================================================================
    # Acknowledgments
    # =========================================================================
    # Used when the user provides information and we want to acknowledge it.

    def get_acknowledgment(self, tone: Optional[str] = None) -> str:
        """
        Get an acknowledgment phrase for when user provides info.

        Args:
            tone: Tone name (uses configured tone if None)

        Returns:
            Acknowledgment like "Got it, thank you." or "Wonderful!"

        Example:
            User: "My email is john@example.com"
            Bot: "{acknowledgment} And what's your phone number?"
        """
        config = self.get_tone_config(tone)
        # Return first one for consistency (could randomize for variety)
        return config["acknowledgments"][0]

    def get_all_acknowledgments(self, tone: Optional[str] = None) -> List[str]:
        """
        Get all acknowledgment options for a tone (for variety).

        Args:
            tone: Tone name (uses configured tone if None)

        Returns:
            List of acknowledgment phrases
        """
        config = self.get_tone_config(tone)
        return config["acknowledgments"]

    # =========================================================================
    # Question Formatting
    # =========================================================================
    # Used when asking clarifying questions for missing fields.

    def format_question(
        self,
        base_question: Optional[str],
        field_label: str,
        tone: Optional[str] = None,
    ) -> str:
        """
        Format a clarifying question with tone-appropriate prefix.

        If a custom base_question is provided (from field config), use it as-is.
        Otherwise, generate a question using the tone's prefix.

        Args:
            base_question: Custom question from field config (may be None)
            field_label: Field label for fallback (e.g., "Email", "Phone")
            tone: Tone name (uses configured tone if None)

        Returns:
            Formatted question string

        Examples:
            # Concierge tone, no custom question:
            format_question(None, "email", "concierge")
            # Returns: "May I ask what your email is?"

            # Efficient tone, no custom question:
            format_question(None, "email", "efficient")
            # Returns: "Email?"

            # Custom question always used as-is:
            format_question("What email can we reach you at?", "email", "efficient")
            # Returns: "What email can we reach you at?"
        """
        if base_question:
            # Custom question from field config - use as-is
            return base_question

        config = self.get_tone_config(tone)
        prefix = config.get("question_prefix", "Could you tell me")

        if prefix:
            return f"{prefix} your {field_label.lower()}?"
        else:
            # Efficient tone - direct question, just the field name
            return f"{field_label}?"

    # =========================================================================
    # Confirmation Flow
    # =========================================================================
    # Used when all fields are captured and we're confirming with the user.

    def get_confirmation_intro(self, tone: Optional[str] = None) -> str:
        """
        Get the intro phrase for confirmation summary.

        Args:
            tone: Tone name (uses configured tone if None)

        Returns:
            Confirmation intro like "Perfect! Just to confirm —"

        Example:
            "{intro}
            - Name: John Smith
            - Email: john@example.com
            Is that correct?"
        """
        config = self.get_tone_config(tone)
        return config.get("confirmation_intro", "Just to confirm —")

    def build_confirmation_summary(
        self,
        extracted_fields: Dict[str, Any],
        required_fields: List[Dict[str, Any]],
        required_field_ids: List[str],
        tone: Optional[str] = None,
    ) -> str:
        """
        Build a confirmation summary with tone-appropriate intro.

        Args:
            extracted_fields: Dict of field_id -> {value, confidence, ...}
            required_fields: List of required field definitions
            required_field_ids: List of required field IDs (for ordering)
            tone: Tone name (uses configured tone if None)

        Returns:
            Formatted confirmation summary string
        """
        intro = self.get_confirmation_intro(tone)

        summary_parts = []
        for fid in required_field_ids:
            if fid in extracted_fields:
                # Find label from field definitions
                label = next(
                    (f["label"] for f in required_fields if f["field_id"] == fid),
                    fid,
                )
                value = extracted_fields[fid].get("value", "N/A")
                summary_parts.append(f"- {label}: {value}")

        summary_text = "\n".join(summary_parts)
        return f"{intro}\n{summary_text}"

    # =========================================================================
    # Completion Messages
    # =========================================================================
    # Used when workflow is complete.

    def get_completion_message(self, tone: Optional[str] = None) -> str:
        """
        Get the completion/thank-you message for workflow end.

        Args:
            tone: Tone name (uses configured tone if None)

        Returns:
            Completion message like "Thanks! We'll reach out shortly."
        """
        config = self.get_tone_config(tone)
        return config.get("completion_message", "Thanks! We'll reach out to you shortly.")
