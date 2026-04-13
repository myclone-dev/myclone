"""
Tool Docstrings for LiveKit Agent

These docstrings are used by @function_tool decorated methods.
They are injected dynamically to keep the main agent file lean.

The LLM uses these docstrings to understand when and how to call each tool.
"""

START_ASSESSMENT_DOC = """Start the step-by-step assessment workflow when user shows interest.

Call this function when:
- User agrees to take the assessment ("yes", "sure", "okay", "let's do it")
- User explicitly asks to take the quiz/assessment
- User's inquiry matches the workflow's purpose

How it works:
- Starts a step-by-step questionnaire
- Each question is asked sequentially by the system
- User answers, you call submit_workflow_answer() to process their response
- System automatically asks next question until complete

IMPORTANT:
- Only call this ONCE per conversation when user agrees
- The workflow handles the rest automatically
- DO NOT use for lead capture - that's a different workflow type
"""


def build_update_lead_field_doc(required_fields: list = None, optional_fields: list = None) -> str:
    """
    Build dynamic docstring for update_lead_fields tool based on workflow config.

    Args:
        required_fields: List of required field definitions from workflow config
        optional_fields: List of optional field definitions from workflow config

    Returns:
        Formatted docstring with actual field_ids from config
    """
    # Build field_id list from config
    all_fields = (required_fields or []) + (optional_fields or [])

    if all_fields:
        field_lines = []
        for f in all_fields:
            field_id = f.get("field_id", "unknown")
            label = f.get("label", field_id)
            field_lines.append(f'  - "{field_id}": {label}')
        fields_section = "VALID FIELD IDs (use as keys in the fields dict):\n" + "\n".join(
            field_lines
        )

        # Build examples showing batch usage with JSON strings
        examples = []
        if len(all_fields) >= 1:
            f1 = all_fields[0]
            examples.append(
                f"- User provides only {f1.get('label', f1['field_id']).lower()} "
                f"""-> update_lead_fields('{{"{f1["field_id"]}": "<value>"}}')"""
            )
        if len(all_fields) >= 2:
            f1 = all_fields[0]
            f2 = all_fields[1]
            examples.append(
                f"- User provides {f1.get('label', f1['field_id']).lower()} AND {f2.get('label', f2['field_id']).lower()} "
                f"""-> update_lead_fields('{{"{f1["field_id"]}": "<value1>", "{f2["field_id"]}": "<value2>"}}')"""
            )
        if len(all_fields) >= 3:
            f1, f2, f3 = all_fields[0], all_fields[1], all_fields[2]
            examples.append(
                f"- User provides 3+ fields in one message "
                f"""-> update_lead_fields('{{"{f1["field_id"]}": "...", "{f2["field_id"]}": "...", "{f3["field_id"]}": "..."}}')"""
            )
        examples_section = "Examples:\n" + "\n".join(examples)
    else:
        fields_section = "VALID FIELD IDs: Check workflow config for available fields"
        examples_section = """Examples:
- User provides one field -> update_lead_fields('{"field_id": "value"}')
- User provides multiple fields -> update_lead_fields('{"field1": "value1", "field2": "value2"}')"""

    return f"""Store one or more lead capture fields extracted from user's message.

WHEN TO CALL: IMMEDIATELY after the user states their name, email, or phone number.
This includes when YOU asked for it and they answered — not only when they volunteer it.
You MUST call this tool every time the user's message contains any contact information.

CRITICAL: If the user says their name, email, or phone in ANY form, call this tool RIGHT AWAY
before responding. Do NOT just acknowledge the info conversationally — you must SAVE it.

DECLINED FIELDS: If the user refuses to provide a field (says "no", "I'd rather not",
ignores the question), call this tool with the value "declined" for that field.
Example: update_lead_fields('{{"contact_phone": "declined"}}')

Extract ALL fields mentioned and pass them in a SINGLE call.

{fields_section}

Args:
    fields_json: JSON string mapping field_id to extracted value.
                 Example: '{{"contact_name": "John Smith", "contact_email": "john@email.com"}}'

Returns:
    Status message with remaining fields to collect

{examples_section}
"""


# Default docstring (used when no workflow config available)
UPDATE_LEAD_FIELD_DOC = build_update_lead_field_doc()

CONFIRM_LEAD_CAPTURE_DOC = """Confirm and complete lead capture after user confirms their information.

WHEN TO CALL:
- ONLY after update_lead_fields returns "AWAITING_CONFIRMATION"
- ONLY after user said YES/correct/confirmed to the confirmation question

DO NOT CALL IF: User said NO or wants changes - use update_lead_fields instead.

Returns:
    Success message confirming workflow is complete
"""

SUBMIT_WORKFLOW_ANSWER_DOC = """Submit the user's answer to the current workflow question.

WHEN TO CALL: User provides an answer to the current workflow question.

For multiple choice: Match user's natural language to option letter (A-D).
For text/number: Pass the user's answer exactly as stated.

Args:
    answer: Option letter (A-D) for multiple choice, or raw text for other types

Returns:
    Empty string (next question is asked automatically)

Examples:
- User describes situation matching option B -> submit_workflow_answer("B")
- User explicitly says "A" -> submit_workflow_answer("A")
- User gives vague answer -> Ask for clarification instead of calling this
"""

SEARCH_INTERNET_DOC = """Search the internet for current, real-time information.

WHEN TO USE:
- ONLY when the user explicitly confirms they want you to search (e.g., "yes", "sure", "go ahead", "look it up", "search for it").
- When the user directly asks you to "search", "look up", or "find" something.

IMPORTANT:
- Do NOT automatically search when the user mentions news or current events — respond naturally and offer to search if needed.
- Once the user confirms they want a search, you MUST call this tool IMMEDIATELY in the same turn. Do NOT say "I'll look it up" without actually calling this tool.

Args:
    query: Search query string

Returns:
    Search results with relevant information
"""

FETCH_URL_DOC = """Fetch content from a specific URL.

Args:
    url: The URL to fetch content from

Returns:
    Page content in text format
"""

SEND_CALENDAR_LINK_DOC = """Send calendar booking link to user.

Returns:
    Confirmation message that link was sent
"""

GENERATE_CONTENT_DOC = """Generate and deliver content (blog, LinkedIn post, newsletter) to the user's screen as a rich card.

YOU MUST CALL THIS TOOL whenever the user asks you to create content. Do not just talk about the content — call this tool to deliver it.

IMPORTANT: You must call `search_internet` FIRST with the topic, then call this tool AFTER search results come back. The tool will write the full content body for you — you only need to provide the inputs.

Args:
    content_type: Type of content. Must be one of: "blog", "linkedin_post", "newsletter"
    title: Title of the content piece
    topic: The topic to write about (e.g. "AI in healthcare", "remote work productivity tips")
    audience: Target audience (e.g. "startup founders", "HR professionals"). Optional but recommended.
    tone: Writing tone (e.g. "professional", "casual", "thought-leadership"). Optional but recommended.

Returns:
    Confirmation that content was delivered to the user's screen
"""
