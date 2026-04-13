# LiveKit Agent Optimization Research

## Overview

Research findings from LiveKit's official `python-agents-examples` repository to optimize our lead capture workflow, which currently suffers from **4-6 second latency per turn** due to dual LLM calls.

## Current Performance Problem

```
User speaks -> STT -> Main LLM (2s, 5400 tokens) -> decides "call capture_lead"
                                                           |
                                              Field Extraction LLM (1.5-3.5s)
                                                           |
                                              Main LLM responds (1s)
```

**Total: 4-6 seconds per turn during lead capture**

### Root Causes:
1. **Huge prompt size**: 5400+ tokens with verbose workflow instructions
2. **Sequential dual LLM calls**: Main LLM then Field Extraction LLM
3. **Redundant processing**: Main LLM decides to call tool, then extraction LLM extracts

---

## Key Patterns from LiveKit Examples

### Pattern 1: AgentTask for Structured Data Collection (MOST RELEVANT)

**Source**: `doheny-surf-desk/tasks/phone_task.py`

```python
class PhoneTask(AgentTask[PhoneResult]):
    """Task to collect phone number with confirmation."""
    
    def __init__(self):
        super().__init__(
            instructions="""You are collecting the customer's phone number.
            Ask for it naturally. When they provide it:
            1. Call record_phone() 
            2. Read it back following the reading guidelines
            3. Ask for confirmation
            4. When they confirm, call confirm_phone()"""
        )
    
    async def on_enter(self) -> None:
        await self.session.generate_reply(instructions="Ask for their phone number.")
    
    @function_tool()
    async def record_phone(self, phone: str, ctx: RunContext) -> str:
        # Validate and record
        self._phone = phone
        return f"Phone recorded. Read it back and ask 'Is that correct?'"
    
    @function_tool()
    async def confirm_phone(self, ctx: RunContext) -> str:
        self._confirmed = True
        self.complete(PhoneResult(phone=self._phone))  # ENDS TASK
```

**Key Insight**: Tasks have their own focused instructions (~100 tokens) vs our 5400-token prompt.

### Pattern 2: TaskGroup for Sequential Collection

**Source**: `doheny-surf-desk/agents/intake_agent.py`

```python
async def on_enter(self) -> None:
    task_group = TaskGroup()
    
    task_group.add(lambda: NameTask(), id="name_task")
    task_group.add(lambda: PhoneTask(), id="phone_task")
    task_group.add(lambda: EmailTask(), id="email_task")
    
    results = await task_group
    
    # Update userdata from task results
    userdata = self.session.userdata
    userdata.name = results.task_results["name_task"].name
    userdata.phone = results.task_results["phone_task"].phone
```

**Key Insight**: Each field gets its own lightweight task instead of one massive coordinator.

### Pattern 3: Observer Agent for Parallel Monitoring (GUARDRAILS)

**Source**: `doheny-surf-desk/agents/observer_agent.py`

```python
class ObserverAgent:
    """Parallel observer that monitors conversations for safety/compliance."""
    
    def __init__(self, session, llm):
        self.session = session
        self._setup_listeners()
    
    def _setup_listeners(self):
        @self.session.on("conversation_item_added")
        def conversation_item_added(event: ConversationItemAddedEvent):
            if event.item.role != "user":
                return
            # Process in background
            asyncio.create_task(self._evaluate_with_llm())
    
    async def _send_guardrail_hint(self, hint: str):
        """Inject hint into active agent's context."""
        current_agent = self.session.current_agent
        ctx_copy = current_agent.chat_ctx.copy()
        ctx_copy.add_message(role="system", content=hint)
        await current_agent.update_chat_ctx(ctx_copy)
```

**Key Insight**: Observer runs in PARALLEL (background) and injects context when needed.

### Pattern 4: Pipeline Node Overrides

**Source**: `replacing_llm_output.py`, `short_replies_only.py`

```python
class SimpleAgent(Agent):
    async def llm_node(self, chat_ctx, tools, model_settings=None):
        """Override LLM output processing."""
        async def process_stream():
            async with self._llm.chat(chat_ctx=chat_ctx, tools=tools) as stream:
                async for chunk in stream:
                    # Modify chunk before passing to TTS
                    processed = chunk.replace("<think>", "")
                    yield processed
        return process_stream()
    
    async def tts_node(self, text: AsyncIterable[str], model_settings):
        """Override TTS processing - can interrupt if too long."""
        async def process_text():
            chunk_count = 0
            async for chunk in text:
                chunk_count += 1
                if chunk_count > MAX_CHUNKS:
                    self.session.interrupt()
                    self.session.say("That will take too long.")
                    break
                yield chunk
        return Agent.default.tts_node(self, process_text(), model_settings)
```

**Key Insight**: Can intercept and modify LLM output before TTS, or intercept user input before LLM.

### Pattern 5: Form Agent with Single LLM + Tools

**Source**: `nova-sonic/form_agent.py`

```python
class FormFillerAgent(Agent):
    @function_tool
    async def collect_experience(self, current_role: str, company: str, years: str):
        """Collect candidate's professional experience."""
        # LLM extracts ALL fields in ONE call via tool parameters
        userdata.personal_info.occupation = current_role
        userdata.personal_info.company = company
        # Update frontend
        await userdata.send_form_update_to_frontend("updateMultipleFields", {
            "fields": {"currentRole": current_role, "company": company}
        })
        return json.dumps({"status": "success", "data": form_data})
```

**Key Insight**: The LLM extracts fields directly via tool parameters. NO separate extraction step.

### Pattern 6: Typed Tool Parameters with Enums

**Source**: `drive-thru/agent.py`

```python
@function_tool
async def order_combo_meal(
    ctx: RunContext[Userdata],
    meal_id: Annotated[
        str,
        Field(
            description="The ID of the combo meal",
            json_schema_extra={"enum": list(available_combo_ids)},  # CONSTRAINED
        ),
    ],
    drink_size: Literal["M", "L", "null"] | None,  # CONSTRAINED
):
    """LLM is forced to extract structured data in one call."""
```

**Key Insight**: Using enums and Literal types forces the LLM to extract structured data correctly.

---

## Optimization Strategies

### Strategy A: Replace Dual LLM with Single Tool Call (RECOMMENDED)

**Current Flow (Slow)**:
```
User: "john@gmail.com" 
  -> Main LLM (2s): "I'll capture that" + calls capture_lead tool
  -> Field Extraction LLM (1.5s): extracts {email: "john@gmail.com"}
  -> Main LLM responds (1s)
Total: 4.5s
```

**Optimized Flow**:
```
User: "john@gmail.com"
  -> Main LLM (2s): extracts directly via tool params + responds
Total: 2s (55% reduction)
```

**Implementation**:
```python
@function_tool
async def update_lead_fields(
    ctx: RunContext,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    service_interest: str | None = None,
):
    """Update lead capture fields. Only pass fields the user just provided."""
    # LLM extracts fields directly - no separate extraction LLM
    if email:
        workflow_state.extracted_data["email"] = email
    if phone:
        workflow_state.extracted_data["phone"] = phone
    # ...
    return f"Captured: {fields_updated}. Ask for remaining fields."
```

### Strategy B: AgentTask Architecture (CLEAN REWRITE)

Replace `ConversationalWorkflowCoordinator` with TaskGroup:

```python
class LeadCaptureTask(AgentTask[LeadResult]):
    def __init__(self, required_fields: list[str]):
        self.required_fields = required_fields
        super().__init__(
            instructions=f"""Collect lead information: {required_fields}.
            Ask naturally, confirm spellings for email/phone."""
        )
    
    @function_tool()
    async def record_field(self, field_name: str, value: str):
        self.collected[field_name] = value
        remaining = [f for f in self.required_fields if f not in self.collected]
        if not remaining:
            self.complete(LeadResult(data=self.collected))
        return f"Recorded {field_name}. Remaining: {remaining}"
```

**Benefits**:
- ~100 token instructions (vs 5400)
- Single purpose, focused agent
- Built-in completion semantics

### Strategy C: Parallel Field Extraction (Observer Pattern)

Run field extraction in PARALLEL with main LLM response:

```python
class LeadExtractionObserver:
    def __init__(self, session, workflow_state):
        self.session = session
        self.workflow_state = workflow_state
        
        @session.on("conversation_item_added")
        def on_user_message(event):
            if event.item.role == "user":
                # Extract fields in background (doesn't block response)
                asyncio.create_task(self._extract_fields(event.item.content))
    
    async def _extract_fields(self, text: str):
        # Simple regex for email/phone (no LLM needed)
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        if email_match:
            self.workflow_state.extracted_data["email"] = email_match.group()
        
        # Or use fast LLM for complex extraction
        # This runs WHILE main LLM is responding
```

### Strategy D: Reduce Prompt Size (QUICK WIN)

Current: `shared/generation/workflow_promotion_prompts.py` has 140+ lines of verbose instructions.

**Optimization**:
```python
# Before: 5400 tokens
WORKFLOW_INSTRUCTIONS = """
When lead capture is active, you must collect information...
[140 lines of detailed instructions]
"""

# After: ~500 tokens
WORKFLOW_INSTRUCTIONS = """
Lead capture is active. Collect: {fields}.
Rules: Confirm email/phone spellings. One field at a time.
Call update_lead_fields(field_name, value) when user provides info.
"""
```

---

## Recommended Implementation Plan

### Phase 1: Quick Wins (1 hour)
1. **Reduce workflow prompt size** from 5400 to ~500 tokens
2. **Add regex pre-extraction** for obvious emails/phones (no LLM needed)

### Phase 2: Single Tool Extraction (2-3 hours)
1. Replace `capture_lead` tool with `update_lead_fields` that accepts individual fields
2. Remove `WorkflowFieldExtractor` class (extraction happens in tool params)
3. Update prompt to guide LLM on when to call the tool

### Phase 3: AgentTask Architecture (4-6 hours, optional)
1. Create `LeadCaptureTask` class
2. Integrate with modular agent using `session.update_agent()`
3. Clean separation between main conversation and lead capture

---

## Expected Performance Improvements

| Optimization | Reduction | New Total |
|-------------|-----------|-----------|
| Reduce prompt (5400 -> 500 tokens) | ~0.8s | 3.7s |
| Single tool extraction | ~1.5s | 2.2s |
| Regex pre-extraction | ~0.3s | 1.9s |
| **Combined** | **~2.6s** | **~2s** |

---

## Files to Modify

| File | Changes |
|------|---------|
| `shared/generation/workflow_promotion_prompts.py` | Reduce prompt size |
| `livekit/services/workflow_field_extractor.py` | Remove or simplify |
| `livekit/handlers/workflow_handler.py` | Update tool to accept field params |
| `livekit/livekit_agent.py` | Modify `capture_lead` tool signature |
| `livekit/services/conversational_workflow_coordinator.py` | Simplify coordination |

---

## References

- `python-agents-examples/docs/examples/survey_caller/` - Simple data collection
- `python-agents-examples/complex-agents/doheny-surf-desk/` - TaskGroup, Observer
- `python-agents-examples/complex-agents/nova-sonic/form_agent.py` - Form filling
- `python-agents-examples/complex-agents/drive-thru/` - Fast ordering with typed tools
- `python-agents-examples/docs/examples/replacing_llm_output/` - Pipeline interception
