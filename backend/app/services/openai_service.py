from openai import OpenAI


class OpenAIModelService:
    """
    A service class to interact with OpenAI Responses API.
    Allows setting model parameters, system prompt creation, and context-based queries.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1-2025-04-14",
        temperature: float = 0.7,
        max_tokens: int = 16384,
    ):
        """
        Initialize the OpenAIModelService.

        :param api_key: OpenAI API key
        :param model: The model to use (default: gpt-4.1-2025-04-14)
        :param temperature: Sampling temperature
        :param max_tokens: Maximum tokens for the response
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.system_prompt = None
        self.context = []

    def set_system_prompt(self, prompt: str):
        """
        Set the system prompt that guides the model's behavior.

        :param prompt: The system prompt string
        """
        self.system_prompt = prompt
        # Initialize context with system prompt
        self.context = [{"role": "system", "content": prompt}]

    def add_context(self, role: str, content: str):
        """
        Add a message to the context for conversation continuity.

        :param role: Role of the message, e.g., "user" or "assistant"
        :param content: The message content
        """
        self.context.append({"role": role, "content": content})

    def clear_context(self):
        """
        Clear the conversation context, retaining only system prompt if set.
        """
        self.context = (
            [{"role": "system", "content": self.system_prompt}] if self.system_prompt else []
        )

    def _build_responses_api_input(self) -> tuple[str | None, str]:
        """Builds system string and single text input from role-tagged context for the Responses API.

        Returns:
            (system, input_text)
        """
        system = None
        parts = []
        for msg in self.context:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                # Keep most recent system as dedicated system string
                system = content
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            else:  # user or any other
                parts.append(f"User: {content}")
        input_text = "\n\n".join(parts) if parts else ""
        return system, input_text

    def get_response(self, user_input: str) -> str:
        """
        Generate a response from the model based on the user input and context.

        :param user_input: User input string
        :return: Model's response string
        """
        # Add user message to context
        self.add_context("user", user_input)

        # Build the Responses API inputs
        system, input_text = self._build_responses_api_input()

        # Call the OpenAI Responses API
        response = self.client.responses.create(
            model=self.model,
            input=input_text,
            instructions=system,
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )

        # Extract assistant reply
        assistant_reply = getattr(response, "output_text", None) or ""

        # Add assistant reply to context
        self.add_context("assistant", assistant_reply)

        return assistant_reply

    def set_model(self, model_name: str):
        """
        Update the model being used by the service.

        :param model_name: New model name
        """
        self.model = model_name

    def set_parameters(self, temperature: float = None, max_tokens: int = None):
        """
        Update parameters for model generation.

        :param temperature: Sampling temperature
        :param max_tokens: Maximum tokens for the response
        """
        if temperature is not None:
            self.temperature = temperature
        if max_tokens is not None:
            self.max_tokens = max_tokens

    def generate_response_raw(
        self,
        user_input: str,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        """Generate a response from the model WITHOUT reading or mutating internal conversation context.

        This is a stateless / raw invocation helper:
          - Does NOT append the user_input to self.context
          - Does NOT append the model answer to self.context
          - Uses provided 'system' if passed, else falls back to self.system_prompt, else no instructions
          - Allows temporary override of temperature / max_tokens for this single call

        Args:
            user_input: The plain text to send as input (goes directly to Responses API 'input')
            system: Optional system instruction string (overrides stored system_prompt if provided)
            temperature: Optional one-off temperature override
            max_tokens: Optional one-off max output tokens override

        Returns:
            The raw OpenAI Responses API response object (not just output_text)
        """
        effective_system = system if system is not None else self.system_prompt
        effective_temperature = self.temperature if temperature is None else temperature
        effective_max_tokens = self.max_tokens if max_tokens is None else max_tokens

        response = self.client.responses.create(
            model=self.model,
            input=user_input,
            instructions=effective_system,
            temperature=effective_temperature,
            max_output_tokens=effective_max_tokens,
        )
        return response
