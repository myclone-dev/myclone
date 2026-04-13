# LiveKit Tasks and Tools - Complete Reference

**Last Updated**: 2026-01-26
**Sources**:
- https://docs.livekit.io/agents/logic/tasks/
- https://docs.livekit.io/agents/logic/tools/

---

## Table of Contents

1. [Function Tools](#function-tools)
2. [Tasks](#tasks)
3. [Key Differences](#key-differences-tasks-vs-tools)
4. [When to Use What](#when-to-use-what)

---

## Function Tools

### What Are Function Tools?

Function tools are **methods that the LLM can invoke** during conversation. They extend the agent's capabilities beyond text generation by allowing the agent to:

- Call external APIs
- Execute code
- Retrieve data (RAG)
- Generate speech via `session.say()` or `session.generate_reply()`
- Transfer control to another agent
- Access/store session data

### How Function Tools Work

1. **Developer defines tool**: Use `@function_tool()` decorator on async methods in your Agent class
2. **LLM sees tool**: Tool name, description, and parameters are passed to LLM in schema
3. **LLM decides to invoke**: Based on conversation, LLM outputs tool call
4. **Framework executes**: LiveKit agents framework executes the function
5. **Result returned to LLM**: Function return value is added to conversation context
6. **LLM continues**: LLM uses result to generate next response

### Defining Function Tools in Python

```python
from livekit.agents import function_tool, Agent, RunContext

class MyAgent(Agent):
    @function_tool()
    async def lookup_weather(
        self,
        context: RunContext,
        location: str,
    ) -> dict[str, Any]:
        """Look up weather information for a given location.

        Args:
            location: The location to look up weather information for.
        """
        # Function implementation
        return {"weather": "sunny", "temperature_f": 70}
```

**Key Points:**
- Docstring becomes tool description for LLM
- Args section documents parameters (LLM sees these)
- Return value goes back to LLM
- `context: RunContext` is optional - provides session access

### Function Tools in Agent Class

When you define `@function_tool()` methods in your Agent class, they are **automatically available to the LLM** throughout the entire agent session.

**Example: Agent with multiple tools**
```python
class MyAgent(Agent):
    @function_tool()
    async def search_web(self, query: str) -> str:
        """Search the web for information."""
        return search_results

    @function_tool()
    async def book_meeting(self, time: str, duration: int) -> str:
        """Book a meeting at specified time."""
        return confirmation
```

The LLM can invoke `search_web` or `book_meeting` at any time during conversation based on user input.

---

## Tasks

### What Are Tasks?

Tasks are **focused, reusable units that perform a specific objective and return a typed result**. They are **discrete operations** with:

- Their own instructions (separate from main agent)
- Their own function tools (scoped to the task)
- A defined completion point (`self.complete(result)`)
- A typed return value

**Key Concept**: Tasks **take control of the session** until they complete. The main agent's LLM is paused while the task runs.

### How Tasks Work

#### 1. Task Structure

```python
from livekit.agents import AgentTask, function_tool

class CollectConsent(AgentTask[bool]):  # Generic type = return type
    def __init__(self, chat_ctx=None):
        super().__init__(
            instructions="Get explicit consent to record this conversation.",
            chat_ctx=chat_ctx
        )

    async def on_enter(self) -> None:
        """Called when task starts - initiate conversation"""
        await self.session.generate_reply(
            instructions="Ask the user for permission to record."
        )

    @function_tool()
    async def consent_given(self) -> None:
        """User grants consent to record."""
        self.complete(True)  # Complete task with result

    @function_tool()
    async def consent_denied(self) -> None:
        """User declines consent to record."""
        self.complete(False)  # Complete task with result
```

#### 2. Task Invocation

**Tasks MUST be explicitly created by the developer** - they are NOT exposed as LLM-callable tools.

```python
class MyAgent(Agent):
    async def on_enter(self) -> None:
        # Explicitly create and await task
        user_consented = await CollectConsent(chat_ctx=self.chat_ctx)

        if user_consented:
            await self.session.say("Great! Starting recording...")
        else:
            await self.session.say("Understood, I won't record.")
```

**Key Points:**
- Task instantiation happens in agent code (lifecycle hooks, methods, etc.)
- Task runs automatically when created ("run automatically when it's created")
- You await the task to get typed result
- Task blocks until `self.complete()` is called

#### 3. Task Lifecycle

```
Developer code: task = CollectConsent(chat_ctx=self.chat_ctx)
    ↓
Task __init__: Set instructions, chat_ctx
    ↓
Task starts: Session control transfers to task
    ↓
Task on_enter(): Initial agent output
    ↓
User responds
    ↓
Task's LLM processes with task's instructions
    ↓
Task's LLM invokes task's @function_tool methods
    ↓
Tool calls self.complete(result)
    ↓
Task returns result
    ↓
Session control returns to agent
    ↓
Developer code: result = await task completes
```

### Function Tools INSIDE Tasks

Tasks define their own `@function_tool()` methods that are **scoped to the task**.

**Critical Difference:**
- Agent-level tools: Available throughout entire session
- Task-level tools: Only available while task is running

```python
class GetEmailTask(AgentTask[str]):
    @function_tool()
    async def email_captured(self, email: str) -> None:
        """Call when user provides email address."""
        self.complete(email)  # Task completes with email
```

The LLM **inside the task** can invoke `email_captured` tool. Once the task completes, this tool is no longer available.

### Task Groups

For multi-step workflows, use `TaskGroup`:

```python
from livekit.agents import TaskGroup

task_group = TaskGroup(chat_ctx=self.chat_ctx)
task_group.add(lambda: GetNameTask(), id="get_name")
task_group.add(lambda: GetEmailTask(), id="get_email")
task_group.add(lambda: GetPhoneTask(), id="get_phone")

results = await task_group  # Returns dict[str, Any]

name = results["get_name"]
email = results["get_email"]
phone = results["get_phone"]
```

**TaskGroup Features:**
- Executes tasks in order
- Shares conversation context across tasks
- Allows users to return to earlier steps for corrections
- Summarizes all collected data when complete

---

## Key Differences: Tasks vs Tools

| Aspect | Function Tools | Tasks |
|--------|---------------|-------|
| **Purpose** | Extend agent capabilities | Discrete objective with completion |
| **Invocation** | LLM decides when to call | Developer explicitly creates |
| **Scope** | Available throughout session | Takes control until complete |
| **Instructions** | Uses agent's main instructions | Has own instructions |
| **Tools** | Agent-level tools | Task-level tools (scoped) |
| **Return Value** | Goes back to LLM context | Typed result to calling code |
| **Control Flow** | Non-blocking (LLM continues) | Blocking (session paused) |
| **Use Case** | "Do something mid-conversation" | "Complete this entire workflow" |

### Visual Comparison

**Function Tool Flow:**
```
User: "What's the weather in NYC?"
    ↓
LLM: [Invokes lookup_weather tool]
    ↓
Tool: Returns weather data
    ↓
LLM: "It's sunny and 70°F in NYC"
    ↓
[Session continues normally]
```

**Task Flow:**
```
Developer: task = GetEmailTask()
    ↓
[Session control transfers to task]
    ↓
Task LLM: "Could I get your email address?"
User: "sarah@example.com"
    ↓
Task LLM: [Invokes email_captured tool]
    ↓
email_captured: self.complete("sarah@example.com")
    ↓
[Session control returns to developer code]
    ↓
Developer: email = await task  # Gets "sarah@example.com"
```

---

## When to Use What

### Use Function Tools When:

- ✅ Agent needs to perform actions **during** conversation
- ✅ Action is **triggered by user request** ("search for X", "book Y")
- ✅ Agent should **continue conversation** after action
- ✅ Action is **stateless** or doesn't require multi-turn dialogue
- ✅ You want **LLM to decide** when to invoke

**Examples:**
- Web search
- API lookups
- Calendar booking
- URL fetching
- Simple calculations

### Use Tasks When:

- ✅ You need **multi-turn dialogue** to complete objective
- ✅ Objective requires **collecting multiple pieces of information**
- ✅ You need **typed result** back to calling code
- ✅ You want **separate instructions** from main agent
- ✅ Task should **block** until completion
- ✅ **Developer controls** when to start (not LLM)

**Examples:**
- Lead capture (name, email, phone)
- Consent collection
- User onboarding flows
- Multi-step forms
- Guided wizards

### Hybrid Approach

You can combine both:

```python
class MyAgent(Agent):
    # Function tool - LLM can invoke anytime
    @function_tool()
    async def search_web(self, query: str) -> str:
        """Search the web."""
        return results

    async def on_enter(self) -> None:
        # Task - developer explicitly starts
        email = await GetEmailTask(chat_ctx=self.chat_ctx)

        # Use collected data
        await self.session.say(f"Thanks! I've saved {email}")

        # Session continues - LLM can now use search_web tool
```

---

## Prebuilt Tasks

LiveKit provides ready-made tasks:

- **GetEmailTask**: Collect email address
- **GetAddressTask**: Collect physical address
- **GetDtmfTask**: Collect DTMF (phone keypad) input
- **WarmTransferTask**: Transfer call to another agent

These follow the same pattern and can be used immediately.

---

## Important Notes

### Task Instantiation

⚠️ **Tasks must be created within an active Agent context**

```python
# ✅ CORRECT - inside agent lifecycle
class MyAgent(Agent):
    async def on_enter(self) -> None:
        result = await MyTask(chat_ctx=self.chat_ctx)

# ❌ WRONG - outside agent context
task = MyTask()  # Will fail - no active agent session
```

### Tool Naming

- Tool names come from function name: `lookup_weather` → `lookup_weather` tool
- Docstring becomes tool description
- Parameter names and types define tool schema

### Task Control

Once a task starts:
- Main agent's LLM is **paused**
- Task's instructions take precedence
- Only task's tools are available
- Session resumes when `self.complete()` is called

### Conversation Context

- Tasks receive `chat_ctx` parameter with conversation history
- TaskGroup shares context across all tasks
- Task's conversation is part of overall session history

---

## Summary

**Function Tools** = LLM-invokable actions that extend agent capabilities mid-conversation
**Tasks** = Developer-invoked discrete workflows with their own instructions and completion

Choose based on **who controls invocation** (LLM vs developer) and **whether you need a result** (continuation vs completion).
