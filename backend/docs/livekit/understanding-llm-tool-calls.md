# Understanding LLM Tool Calls in LiveKit Agents

This document provides a deep dive into how LLM tool calling works in the LiveKit Agents framework, from fundamental concepts to implementation details.

## Table of Contents

1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [Step 1: Defining Tools](#step-1-defining-tools)
4. [Step 2: Schema Generation](#step-2-schema-generation)
5. [Step 3: Managing Tools with ToolContext](#step-3-managing-tools-with-toolcontext)
6. [Step 4: Chat Context and Conversation History](#step-4-chat-context-and-conversation-history)
7. [Step 5: LLM Response Parsing](#step-5-llm-response-parsing)
8. [Step 6: Tool Execution](#step-6-tool-execution)
9. [Step 7: Creating Tool Output](#step-7-creating-tool-output)
10. [Step 8: Provider Format Conversion](#step-8-provider-format-conversion)
11. [Advanced Topics](#advanced-topics)
12. [Complete Flow Diagram](#complete-flow-diagram)
13. [API Reference](#api-reference)

---

## Overview

Tool calling (also known as function calling) allows LLMs to request the execution of predefined functions during a conversation. This enables AI agents to:

- Fetch real-time data (weather, stock prices, etc.)
- Interact with external APIs
- Perform actions (send emails, control devices, etc.)
- Access information not in their training data

### The High-Level Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        LLM TOOL CALLING FLOW                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. You define a function (e.g., get_weather)                                │
│  2. Function is converted to JSON schema that LLM understands                │
│  3. LLM decides to call the function and returns structured JSON             │
│  4. Your code executes the actual function                                   │
│  5. Result is sent back to LLM for it to generate a response                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Concepts

Before diving into implementation, here are the key abstractions:

| Concept | Class | Purpose |
|---------|-------|---------|
| **Tool Definition** | `@function_tool` | Decorator that wraps a Python function as an LLM-callable tool |
| **Tool Metadata** | `FunctionToolInfo` | Stores name, description, and flags for a tool |
| **Tool Wrapper** | `FunctionTool` | Holds the function reference and its metadata |
| **Tool Collection** | `ToolContext` | Manages multiple tools and converts them to provider formats |
| **Tool Request** | `FunctionCall` | Represents the LLM's request to call a specific tool |
| **Tool Result** | `FunctionCallOutput` | The result of executing a tool, sent back to the LLM |
| **Conversation** | `ChatContext` | Holds the full conversation history including tool interactions |

---

## Step 1: Defining Tools

### The `@function_tool` Decorator

The simplest way to create a tool is using the `@function_tool` decorator:

```python
from livekit.agents.llm import function_tool

@function_tool
async def get_weather(location: str, units: str = "celsius") -> str:
    """Get current weather for a location.
    
    Args:
        location: The city name to get weather for
        units: Temperature units - either 'celsius' or 'fahrenheit'
    
    Returns:
        A string describing the current weather
    """
    # Your implementation here
    weather_data = await fetch_weather_api(location, units)
    return f"{weather_data['condition']}, {weather_data['temp']}°{units[0].upper()}"
```

### What Happens Under the Hood

When you apply `@function_tool`, the decorator:

1. **Extracts the function name** from `func.__name__` (or you can override it)
2. **Parses the docstring** to get the description
3. **Analyzes type hints** to understand parameter types
4. **Creates a `FunctionTool` wrapper** that holds everything together

```python
# Simplified view of what the decorator does (from tool_context.py)
def deco_func(func: Callable) -> FunctionTool:
    from docstring_parser import parse_from_object

    docstring = parse_from_object(func)
    info = FunctionToolInfo(
        name=name or func.__name__,                    # "get_weather"
        description=description or docstring.description,  # From docstring
        flags=flags,
    )
    return FunctionTool(func, info)
```

### Decorator Options

You can customize the tool definition:

```python
# Custom name and description
@function_tool(
    name="fetch_weather_data",
    description="Retrieves current weather conditions for any city worldwide"
)
async def get_weather(location: str) -> str:
    ...

# With flags
from livekit.agents.llm import ToolFlag

@function_tool(flags=ToolFlag.IGNORE_ON_ENTER)
async def background_task() -> str:
    """This tool won't be offered when agent first enters."""
    ...
```

### Using Raw JSON Schema

For advanced cases (like MCP integration), you can provide your own schema:

```python
@function_tool(
    raw_schema={
        "name": "complex_query",
        "description": "Execute a complex database query",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100}
            },
            "required": ["query"]
        }
    }
)
async def complex_query(raw_arguments: dict[str, object]) -> str:
    # raw_arguments contains the parsed JSON
    query = raw_arguments["query"]
    limit = raw_arguments.get("limit", 10)
    ...
```

### Key Classes

```python
# Tool metadata (from tool_context.py)
@dataclass
class FunctionToolInfo:
    name: str              # Function name for LLM
    description: str | None  # What the function does
    flags: ToolFlag        # Special behavior flags

# The tool wrapper
class FunctionTool:
    """Wrapper for a function decorated with @function_tool"""
    
    @property
    def info(self) -> FunctionToolInfo:
        return self._info
    
    def __call__(self, *args, **kwargs):
        # Calls the underlying function
        return self._func(*args, **kwargs)
```

---

## Step 2: Schema Generation

LLMs don't understand Python code directly. They need a JSON Schema description of your function. Here's how the conversion works:

### The Transformation Pipeline

```
Python Function → Pydantic Model → JSON Schema → LLM-ready format
```

### Creating a Pydantic Model from Function Signature

The framework uses Python's `inspect` module and Pydantic to analyze your function:

```python
# Simplified from utils.py - function_arguments_to_pydantic_model()

def function_arguments_to_pydantic_model(func: Callable) -> type[BaseModel]:
    """Create a Pydantic model from a function's signature."""
    
    # 1. Get function signature and type hints
    signature = inspect.signature(func)
    type_hints = get_type_hints(func, include_extras=True)
    
    # 2. Parse docstring for parameter descriptions
    docstring = parse_from_object(func)
    param_docs = {p.arg_name: p.description for p in docstring.params}
    
    # 3. Build fields dictionary
    fields: dict[str, Any] = {}
    for param_name, param in signature.parameters.items():
        type_hint = type_hints[param_name]
        
        # Skip RunContext - it's injected automatically, not from LLM
        if is_context_type(type_hint):
            continue
        
        # Get default value
        default_value = param.default if param.default is not param.empty else ...
        
        # Create field with description from docstring
        field_info = Field(
            default=default_value,
            description=param_docs.get(param_name)
        )
        fields[param_name] = (type_hint, field_info)
    
    # 4. Create dynamic Pydantic model
    return create_model("GetWeatherArgs", **fields)
```

### Example Transformation

```python
# Your function:
async def get_weather(location: str, units: str = "celsius") -> str:
    """Get current weather for a location.
    
    Args:
        location: The city name
        units: Temperature units (celsius or fahrenheit)
    """
    ...

# Becomes equivalent to this Pydantic model:
class GetWeatherArgs(BaseModel):
    location: str = Field(description="The city name")
    units: str = Field(default="celsius", description="Temperature units...")
```

### Building OpenAI-Compatible Schema

```python
# From utils.py - build_strict_openai_schema()

def build_strict_openai_schema(function_tool: FunctionTool) -> dict[str, Any]:
    """Generate strict mode tool description for OpenAI."""
    model = function_arguments_to_pydantic_model(function_tool)
    info = function_tool.info
    schema = to_strict_json_schema(model)  # Pydantic → JSON Schema

    return {
        "type": "function",
        "function": {
            "name": info.name,
            "strict": True,
            "description": info.description or "",
            "parameters": schema,
        },
    }
```

### Final JSON Sent to LLM

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "strict": true,
    "description": "Get current weather for a location.",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
          "description": "The city name"
        },
        "units": {
          "type": ["string", "null"],
          "default": "celsius",
          "description": "Temperature units (celsius or fahrenheit)"
        }
      },
      "required": ["location", "units"],
      "additionalProperties": false
    }
  }
}
```

### Supported Type Hints

The schema generator supports various Python types:

| Python Type | JSON Schema Type |
|-------------|------------------|
| `str` | `{"type": "string"}` |
| `int` | `{"type": "integer"}` |
| `float` | `{"type": "number"}` |
| `bool` | `{"type": "boolean"}` |
| `list[str]` | `{"type": "array", "items": {"type": "string"}}` |
| `Optional[str]` | `{"type": ["string", "null"]}` |
| `Literal["a", "b"]` | `{"type": "string", "enum": ["a", "b"]}` |
| `BaseModel` subclass | Nested object schema |

---

## Step 3: Managing Tools with ToolContext

Tools are grouped together in a `ToolContext` for easy management:

```python
from livekit.agents.llm import ToolContext, function_tool

@function_tool
async def get_weather(location: str) -> str:
    """Get weather for a location."""
    ...

@function_tool
async def search_web(query: str) -> str:
    """Search the web for information."""
    ...

# Create a tool context with multiple tools
tool_ctx = ToolContext([get_weather, search_web])
```

### ToolContext API

```python
class ToolContext:
    """Stateless container for a set of AI functions"""
    
    def __init__(self, tools: Sequence[Tool | Toolset]) -> None:
        """Initialize with a list of tools or toolsets."""
        ...
    
    @property
    def function_tools(self) -> dict[str, FunctionTool | RawFunctionTool]:
        """Get all function tools as a name → tool mapping."""
        return self._fnc_tools_map.copy()
    
    @property
    def provider_tools(self) -> list[ProviderTool]:
        """Get tools provided by LLM providers (e.g., code interpreter)."""
        return self._provider_tools
    
    def flatten(self) -> list[Tool]:
        """Get all tools as a flat list."""
        ...
    
    def parse_function_tools(
        self, 
        format: Literal["openai", "google", "anthropic", "aws"],
        *,
        strict: bool = True
    ) -> list[dict[str, Any]]:
        """Convert tools to provider-specific schema format."""
        if format == "openai":
            return _provider_format.openai.to_fnc_ctx(self, strict=strict)
        elif format == "google":
            return _provider_format.google.to_fnc_ctx(self, ...)
        # ... other providers
```

### Using Toolsets

For organizing related tools, use `Toolset`:

```python
from livekit.agents.llm import Toolset, function_tool

class WeatherToolset(Toolset):
    @property
    def tools(self) -> list[Tool]:
        return [self.get_weather, self.get_forecast]
    
    @function_tool
    async def get_weather(self, location: str) -> str:
        """Get current weather."""
        ...
    
    @function_tool
    async def get_forecast(self, location: str, days: int = 5) -> str:
        """Get weather forecast."""
        ...

# Use in ToolContext
tool_ctx = ToolContext([WeatherToolset()])
```

---

## Step 4: Chat Context and Conversation History

The `ChatContext` holds the entire conversation, including messages, tool calls, and results:

### Core Classes

```python
# From chat_context.py

class ChatMessage(BaseModel):
    """A message in the conversation."""
    id: str
    type: Literal["message"] = "message"
    role: Literal["developer", "system", "user", "assistant"]
    content: list[str | ImageContent | AudioContent]
    interrupted: bool = False

class FunctionCall(BaseModel):
    """Represents the LLM's request to call a tool."""
    id: str                    # Internal ID: "item_abc123"
    type: Literal["function_call"] = "function_call"
    call_id: str               # LLM's ID: "call_xyz789"
    name: str                  # "get_weather"
    arguments: str             # '{"location": "Paris", "units": "celsius"}'
    group_id: str | None       # For parallel tool calls

class FunctionCallOutput(BaseModel):
    """The result of executing a tool."""
    id: str
    type: Literal["function_call_output"] = "function_call_output"
    call_id: str               # Must match FunctionCall.call_id
    name: str                  # "get_weather"
    output: str                # "Sunny, 22°C"
    is_error: bool             # True if execution failed

# Union type for all items
ChatItem = ChatMessage | FunctionCall | FunctionCallOutput | AgentHandoff
```

### ChatContext Usage

```python
from livekit.agents.llm import ChatContext

# Create a new context
chat_ctx = ChatContext()

# Add a system message
chat_ctx.add_message(role="system", content="You are a helpful assistant.")

# Add a user message
chat_ctx.add_message(role="user", content="What's the weather in Paris?")

# Access all items
for item in chat_ctx.items:
    print(f"{item.type}: {item}")

# Copy with filters
filtered = chat_ctx.copy(
    exclude_function_call=True,  # Remove tool calls
    exclude_instructions=True,   # Remove system/developer messages
)

# Convert to provider format
messages, _ = chat_ctx.to_provider_format("openai")
```

### Conversation Flow Example

Here's how a typical tool-calling conversation looks in `ChatContext`:

```python
chat_ctx.items = [
    ChatMessage(
        role="system",
        content=["You are a helpful weather assistant."]
    ),
    ChatMessage(
        role="user",
        content=["What's the weather in Paris?"]
    ),
    FunctionCall(
        call_id="call_abc123",
        name="get_weather",
        arguments='{"location": "Paris", "units": "celsius"}'
    ),
    FunctionCallOutput(
        call_id="call_abc123",
        name="get_weather",
        output="Sunny, 22°C",
        is_error=False
    ),
    ChatMessage(
        role="assistant",
        content=["The weather in Paris is currently sunny with a temperature of 22°C!"]
    ),
]
```

---

## Step 5: LLM Response Parsing

When the LLM decides to call a tool, it returns structured data that needs to be parsed.

### Response Classes

```python
# From llm.py

class FunctionToolCall(BaseModel):
    """Represents a tool call from the LLM response."""
    type: Literal["function"] = "function"
    name: str                  # "get_weather"
    arguments: str             # '{"location": "Paris"}'
    call_id: str               # "call_abc123"
    extra: dict[str, Any] | None = None  # Provider-specific data

class ChoiceDelta(BaseModel):
    """A chunk of the streaming response."""
    role: ChatRole | None = None
    content: str | None = None
    tool_calls: list[FunctionToolCall] = []

class ChatChunk(BaseModel):
    """Wrapper for streamed response chunks."""
    id: str
    delta: ChoiceDelta | None = None
    usage: CompletionUsage | None = None
```

### Processing Tool Calls in the Stream

The generation pipeline processes LLM output and extracts tool calls:

```python
# Simplified from generation.py - _llm_inference_task()

async def _llm_inference_task(node, chat_ctx, tool_ctx, model_settings, data):
    async for chunk in llm_node:
        if isinstance(chunk, ChatChunk):
            if chunk.delta and chunk.delta.tool_calls:
                for tool in chunk.delta.tool_calls:
                    if tool.type != "function":
                        continue
                    
                    # Create FunctionCall from LLM response
                    fnc_call = llm.FunctionCall(
                        id=f"{data.id}/fnc_{len(data.generated_functions)}",
                        call_id=tool.call_id,
                        name=tool.name,
                        arguments=tool.arguments,
                        extra=tool.extra or {},
                    )
                    
                    # Add to generated list and send to execution stream
                    data.generated_functions.append(fnc_call)
                    function_ch.send_nowait(fnc_call)
            
            # Also handle text content
            if chunk.delta and chunk.delta.content:
                data.generated_text += chunk.delta.content
                text_ch.send_nowait(chunk.delta.content)
```

---

## Step 6: Tool Execution

Once a tool call is parsed, it needs to be executed.

### The Execution Pipeline

```python
# Simplified from generation.py - _execute_tools_task()

async def _execute_tools_task(session, speech_handle, tool_ctx, function_stream, ...):
    async for fnc_call in function_stream:
        # 1. Find the tool by name
        function_tool = tool_ctx.function_tools.get(fnc_call.name)
        if function_tool is None:
            logger.warning(f"Unknown AI function: {fnc_call.name}")
            continue
        
        # 2. Prepare arguments
        try:
            fnc_args, fnc_kwargs = llm_utils.prepare_function_arguments(
                fnc=function_tool,
                json_arguments=fnc_call.arguments,
                call_ctx=RunContext(session, speech_handle, fnc_call),
            )
        except (ValidationError, ValueError) as e:
            # Invalid arguments - report error to LLM
            output = make_tool_output(fnc_call=fnc_call, output=None, exception=e)
            continue
        
        # 3. Execute the tool
        try:
            val = await function_tool(*fnc_args, **fnc_kwargs)
            output = make_tool_output(fnc_call=fnc_call, output=val, exception=None)
        except Exception as e:
            output = make_tool_output(fnc_call=fnc_call, output=None, exception=e)
```

### Argument Preparation Deep Dive

The `prepare_function_arguments` function converts JSON from the LLM into Python objects:

```python
# From utils.py

def prepare_function_arguments(
    *,
    fnc: FunctionTool | RawFunctionTool,
    json_arguments: str,
    call_ctx: RunContext | None = None,
) -> tuple[tuple, dict]:
    """Convert LLM JSON output to Python function arguments."""
    
    # 1. Parse JSON string
    args_dict = from_json(json_arguments)  # {"location": "Paris", "units": null}
    
    # 2. Handle FunctionTool (with Pydantic validation)
    if isinstance(fnc, FunctionTool):
        model_type = function_arguments_to_pydantic_model(fnc)
        
        # Handle null values - use default if available
        signature = inspect.signature(fnc)
        for param_name, param in signature.parameters.items():
            if args_dict.get(param_name) is None:
                if not _is_optional_type(type_hints[param_name]):
                    if param.default is not inspect.Parameter.empty:
                        args_dict[param_name] = param.default
        
        # Validate with Pydantic
        model = model_type.model_validate(args_dict)
        raw_fields = _shallow_model_dump(model)
    
    # 3. Handle RawFunctionTool (no validation)
    elif isinstance(fnc, RawFunctionTool):
        raw_fields = {"raw_arguments": args_dict}
    
    # 4. Inject RunContext if function expects it
    context_dict = {}
    for param_name, type_hint in type_hints.items():
        if is_context_type(type_hint) and call_ctx is not None:
            context_dict[param_name] = call_ctx
    
    # 5. Bind to function signature
    bound = signature.bind(**{**raw_fields, **context_dict})
    bound.apply_defaults()
    return bound.args, bound.kwargs
```

### Using RunContext in Tools

Tools can access session state via `RunContext`:

```python
from livekit.agents.voice.events import RunContext

@function_tool
async def get_user_name(ctx: RunContext) -> str:
    """Get the current user's name from session."""
    # Access the session
    session = ctx.session
    
    # Access the current speech handle
    speech = ctx.speech_handle
    
    # Access the function call itself
    call = ctx.function_call
    
    return session.user_name or "Unknown"
```

The `RunContext` is automatically injected - you don't pass it from the LLM.

---

## Step 7: Creating Tool Output

After execution, the result is packaged for the LLM:

```python
# From generation.py

@dataclass
class ToolExecutionOutput:
    fnc_call: llm.FunctionCall           # The original call
    fnc_call_out: llm.FunctionCallOutput | None  # The result (if any)
    agent_task: Agent | None             # For agent handoffs
    raw_output: Any                      # The raw Python return value
    raw_exception: BaseException | None  # Any exception that occurred
    reply_required: bool = True          # Should LLM respond?

def make_tool_output(
    *, 
    fnc_call: llm.FunctionCall, 
    output: Any, 
    exception: BaseException | None
) -> ToolExecutionOutput:
    """Create output from tool execution result."""
    
    # Handle ToolError - user-friendly message for LLM
    if isinstance(exception, ToolError):
        return ToolExecutionOutput(
            fnc_call=fnc_call,
            fnc_call_out=llm.FunctionCallOutput(
                call_id=fnc_call.call_id,
                name=fnc_call.name,
                output=exception.message,  # "Location not found"
                is_error=True,
            ),
            ...
        )
    
    # Handle StopResponse - don't send anything, stop response generation
    if isinstance(exception, StopResponse):
        return ToolExecutionOutput(
            fnc_call=fnc_call,
            fnc_call_out=None,  # No output to LLM
            ...
        )
    
    # Handle other exceptions - hide details from LLM
    if exception is not None:
        return ToolExecutionOutput(
            fnc_call=fnc_call,
            fnc_call_out=llm.FunctionCallOutput(
                call_id=fnc_call.call_id,
                name=fnc_call.name,
                output="An internal error occurred",
                is_error=True,
            ),
            ...
        )
    
    # Success - convert output to string
    return ToolExecutionOutput(
        fnc_call=fnc_call,
        fnc_call_out=llm.FunctionCallOutput(
            call_id=fnc_call.call_id,
            name=fnc_call.name,
            output=str(output),  # "Sunny, 22°C"
            is_error=False,
        ),
        ...
    )
```

### Error Handling Strategies

| Exception Type | Behavior | LLM Sees |
|---------------|----------|----------|
| `ToolError("message")` | Report error to LLM | The custom message |
| `StopResponse()` | Stop without response | Nothing (no tool output) |
| Other exceptions | Log and hide details | "An internal error occurred" |

Example usage:

```python
from livekit.agents.llm import ToolError, StopResponse

@function_tool
async def get_weather(location: str) -> str:
    """Get weather for a location."""
    
    if not location:
        # LLM will see this message and can try again
        raise ToolError("Please provide a location name")
    
    if location.lower() == "atlantis":
        # Silently stop - no response generated
        raise StopResponse()
    
    try:
        return await fetch_weather(location)
    except APIError:
        # LLM sees generic message, details logged server-side
        raise RuntimeError("Weather API failed")
```

---

## Step 8: Provider Format Conversion

Different LLM providers have different message formats. The framework handles conversion automatically.

### OpenAI Format

```python
# From _provider_format/openai.py

def to_chat_ctx(chat_ctx: llm.ChatContext) -> tuple[list[dict], None]:
    """Convert ChatContext to OpenAI message format."""
    messages = []
    
    for group in group_tool_calls(chat_ctx):
        # Messages become role/content dicts
        if group.message:
            msg = {"role": group.message.role, "content": group.message.text_content}
        else:
            msg = {"role": "assistant"}
        
        # Tool calls are added to assistant message
        if group.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.call_id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments}
                }
                for tc in group.tool_calls
            ]
        messages.append(msg)
        
        # Tool outputs become separate tool messages
        for output in group.tool_outputs:
            messages.append({
                "role": "tool",
                "tool_call_id": output.call_id,
                "content": output.output,
            })
    
    return messages, None
```

### Resulting OpenAI Format

```json
[
  {"role": "system", "content": "You are a helpful assistant."},
  {"role": "user", "content": "What's the weather in Paris?"},
  {
    "role": "assistant",
    "tool_calls": [
      {
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "get_weather",
          "arguments": "{\"location\": \"Paris\"}"
        }
      }
    ]
  },
  {
    "role": "tool",
    "tool_call_id": "call_abc123",
    "content": "Sunny, 22°C"
  },
  {"role": "assistant", "content": "The weather in Paris is sunny at 22°C!"}
]
```

### Tool Schema Format

```python
def to_fnc_ctx(tool_ctx: llm.ToolContext, *, strict: bool = True) -> list[dict]:
    """Convert ToolContext to OpenAI tools format."""
    schemas = []
    
    for tool in tool_ctx.function_tools.values():
        if isinstance(tool, llm.RawFunctionTool):
            schemas.append({
                "type": "function",
                "function": tool.info.raw_schema,
            })
        elif isinstance(tool, llm.FunctionTool):
            schema = (
                llm.utils.build_strict_openai_schema(tool) if strict
                else llm.utils.build_legacy_openai_schema(tool)
            )
            schemas.append(schema)
    
    return schemas
```

---

## Advanced Topics

### Parallel Tool Calls

LLMs can request multiple tools to be called simultaneously:

```python
# The LLM might return multiple tool calls
chunk.delta.tool_calls = [
    FunctionToolCall(call_id="call_1", name="get_weather", arguments='{"location":"Paris"}'),
    FunctionToolCall(call_id="call_2", name="get_weather", arguments='{"location":"London"}'),
]

# They share a group_id for proper ordering in chat context
fnc_call.group_id = "group_abc"  # Same for parallel calls
```

Both tools execute concurrently, and their results are grouped together when sent back to the LLM.

### Agent Handoffs

Tools can return an `Agent` to hand off to a different agent:

```python
from livekit.agents.voice import Agent

@function_tool
async def transfer_to_sales() -> Agent:
    """Transfer the conversation to the sales team."""
    return SalesAgent()  # Returns a new agent instance
```

The framework detects this and performs the handoff automatically.

### MCP (Model Context Protocol) Integration

MCP allows you to connect external tool servers to your agent. LiveKit provides `MCPServerHTTP` and `MCPServerStdio` classes for connecting to MCP servers:

```python
from livekit.agents import mcp, Agent, AgentSession

# HTTP-based MCP server (supports SSE and streamable HTTP transports)
mcp_server = mcp.MCPServerHTTP(
    url="http://localhost:8000/sse",
    # transport_type="sse",  # or "streamable_http" (auto-detected from URL)
    # allowed_tools=["tool1", "tool2"],  # optional: filter available tools
)

# Stdio-based MCP server (runs a local process)
mcp_server_stdio = mcp.MCPServerStdio(
    command="python",
    args=["my_mcp_server.py"],
)

# Use MCP servers with an Agent
class MyAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a helpful assistant.",
            mcp_servers=[mcp_server],
        )

# Or with an AgentSession
session = AgentSession(
    mcp_servers=[mcp_server],
)
```

MCP servers are initialized automatically when the agent starts. Each tool from the MCP server is wrapped as a `RawFunctionTool` (aliased as `MCPTool`) internally.

### Tool Choice Control

Control when tools can be used:

```python
from livekit.agents.llm import ToolChoice

# Let LLM decide
llm.chat(chat_ctx=ctx, tools=tools, tool_choice="auto")

# Force tool use
llm.chat(chat_ctx=ctx, tools=tools, tool_choice="required")

# Disable tools
llm.chat(chat_ctx=ctx, tools=tools, tool_choice="none")

# Force specific tool
llm.chat(chat_ctx=ctx, tools=tools, tool_choice={
    "type": "function",
    "function": {"name": "get_weather"}
})
```

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           COMPLETE TOOL CALL FLOW                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  1. DEFINITION                                                                  │
│     @function_tool                                                              │
│     async def get_weather(location: str) -> str:                                │
│         """Get weather."""  ──────────────────────────────┐                     │
│                                                           │                     │
│  2. SCHEMA GENERATION                                     ▼                     │
│     ToolContext.parse_function_tools("openai")                                  │
│     ┌──────────────────────────────────────────────────────┐                    │
│     │ {"type": "function", "function": {                   │                    │
│     │   "name": "get_weather",                             │                    │
│     │   "parameters": {"type": "object", "properties": {   │                    │
│     │     "location": {"type": "string"}                   │                    │
│     │   }}                                                 │                    │
│     │ }}                                                   │                    │
│     └──────────────────────────────────────────────────────┘                    │
│                              │                                                  │
│  3. LLM REQUEST              ▼                                                  │
│     llm.chat(chat_ctx, tools=[...])                                             │
│                              │                                                  │
│  4. LLM RESPONSE             ▼                                                  │
│     ChatChunk with delta.tool_calls = [                                         │
│       FunctionToolCall(call_id="call_1", name="get_weather",                    │
│                        arguments='{"location":"Paris"}')                        │
│     ]                        │                                                  │
│                              ▼                                                  │
│  5. PARSE & EXECUTE                                                             │
│     prepare_function_arguments(fnc, json_arguments)                             │
│     val = await get_weather(location="Paris")                                   │
│                              │                                                  │
│  6. CREATE OUTPUT            ▼                                                  │
│     FunctionCallOutput(call_id="call_1", output="Sunny, 22°C")                  │
│                              │                                                  │
│  7. ADD TO CHAT CONTEXT      ▼                                                  │
│     chat_ctx.items.append(fnc_call)                                             │
│     chat_ctx.items.append(fnc_call_output)                                      │
│                              │                                                  │
│  8. NEXT LLM CALL            ▼                                                  │
│     chat_ctx.to_provider_format("openai") → includes tool results               │
│     LLM generates: "The weather in Paris is sunny at 22°C!"                     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## API Reference

### Decorators

| Decorator | Description |
|-----------|-------------|
| `@function_tool` | Wrap a function as an LLM-callable tool |
| `@function_tool(name="...", description="...")` | With custom metadata |
| `@function_tool(raw_schema={...})` | With raw JSON schema |

### Classes

| Class | Description |
|-------|-------------|
| `FunctionTool` | Wrapper for decorated functions |
| `RawFunctionTool` | Wrapper for raw schema tools |
| `ToolContext` | Container for multiple tools |
| `Toolset` | Base class for grouping related tools |
| `FunctionCall` | LLM's request to call a tool |
| `FunctionCallOutput` | Result of tool execution |
| `ChatContext` | Conversation history container |
| `ChatMessage` | A message in the conversation |
| `RunContext` | Context available to tools during execution |

### Exceptions

| Exception | Description |
|-----------|-------------|
| `ToolError(message)` | Report error to LLM with custom message |
| `StopResponse()` | Stop without generating a response |

### Key Functions

| Function | Description |
|----------|-------------|
| `prepare_function_arguments()` | Convert JSON to Python args |
| `build_strict_openai_schema()` | Generate strict JSON schema |
| `function_arguments_to_pydantic_model()` | Create Pydantic model from function |

---

## See Also

- [LiveKit Agents Documentation](https://docs.livekit.io/agents/)
- [OpenAI Function Calling Guide](https://platform.openai.com/docs/guides/function-calling)
- [Pydantic Documentation](https://docs.pydantic.dev/)

