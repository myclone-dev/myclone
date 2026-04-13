# LiveKit Agent Architecture - Modular Implementation

**Last Updated**: 2026-01-28
**Status**: ✅ Production (Modular agent fully implemented)
**File**: `livekit/livekit_agent.py` (~650 lines)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Comparison](#architecture-comparison)
3. [Modular Components](#modular-components)
4. [Workflow System](#workflow-system)
5. [Request Flow](#request-flow)
6. [Implementation Details](#implementation-details)
7. [Testing & Debugging](#testing--debugging)

---

## Overview

### What is the LiveKit Agent?

The LiveKit agent is a **real-time AI voice/text assistant** that:
- 🎙️ **Supports Voice & Text**: LiveKit voice rooms OR text-only chat
- 🧠 **Uses RAG for Knowledge**: Retrieves persona-specific information from vector DB
- 📋 **Runs Workflows**: Linear (Q&A) and conversational (field extraction) workflows
- 🔧 **Provides Tools**: Internet search, URL fetching, calendar booking
- 📄 **Handles Documents**: Process PDF/Word/Excel/PowerPoint uploads mid-conversation
- 💬 **Captures Leads**: Email capture triggers after N messages

### Why Modular?

**Before Modular Refactor** (livekit_agent_retrieval.py):
- ❌ 2900+ lines in single file
- ❌ All logic in one PersonaRetrievalAgent class
- ❌ Hard to test, debug, or extend
- ❌ Frequent merge conflicts
- ❌ Difficult to understand workflow flow

**After Modular Refactor** (livekit_agent.py):
- ✅ ~700 lines in main agent file
- ✅ Composition pattern with 9 specialized handlers/managers
- ✅ Each handler has single responsibility
- ✅ Easy to test (mock individual handlers)
- ✅ Clear separation of concerns
- ✅ Reduced merge conflicts

---

## Architecture Comparison

### Before: Monolithic Agent

```
livekit_agent_retrieval.py (2900 lines)
└── PersonaRetrievalAgent
    ├── __init__() - 150 lines
    ├── llm_node() - 200 lines
    ├── _inject_rag_context() - 100 lines
    ├── start_assessment() - 100 lines
    ├── submit_workflow_answer() - 150 lines
    ├── _complete_workflow() - 80 lines
    ├── search_internet() - 50 lines
    ├── fetch_url() - 50 lines
    ├── send_calendar_link() - 30 lines
    ├── on_enter() - 50 lines
    ├── on_exit() - 100 lines
    ├── Email capture logic - 150 lines
    ├── Document processing - 200 lines
    ├── Conversation management - 100 lines
    └── ... 15+ more methods
```

### After: Modular Agent (Composition Pattern)

```
livekit/
├── livekit_agent.py (~650 lines) ⭐ MAIN AGENT
│   └── ModularPersonaAgent - Orchestrates handlers, thin tool wrappers
│
├── handlers/ ⭐ CORE HANDLERS
│   ├── session_context.py (~80 lines)
│   │   └── SessionContext - Conversation tracking, turn counting
│   │
│   ├── workflow/ ⭐ MODULAR WORKFLOW HANDLERS (split by type)
│   │   ├── __init__.py (~75 lines) - Factory function + exports
│   │   ├── base.py (~230 lines) - BaseWorkflowHandler (shared logic)
│   │   ├── linear_handler.py (~310 lines) - LinearWorkflowHandler (assessments)
│   │   └── conversational_handler.py (~360 lines) - ConversationalWorkflowHandler (lead capture)
│   │
│   ├── tool_handler.py (~190 lines)
│   │   └── ToolHandler - Function tools (search, fetch, calendar)
│   │
│   ├── document_handler.py (~300 lines)
│   │   └── DocumentHandler - PDF/Word/Excel processing
│   │
│   ├── email_capture_handler.py (~200 lines)
│   │   └── EmailCaptureHandler - Lead generation trigger
│   │
│   └── lifecycle_handler.py (~250 lines)
│       └── LifecycleHandler - on_enter, on_exit, greeting, citations
│
├── managers/ ⭐ CONTEXT MANAGERS
│   ├── prompt_manager.py (~220 lines)
│   │   └── PromptManager - System prompt building + workflow promotion
│   │
│   ├── rag_manager.py (~220 lines)
│   │   └── RAGManager - RAG context injection
│   │
│   └── conversation_manager.py (~200 lines)
│       └── ConversationManager - History management
│
├── constants/ ⭐ TOOL DOCSTRINGS
│   └── tool_docstrings.py (~100 lines) - Docstrings for @function_tool methods
│
└── utils/
    └── decorators.py (~36 lines) - @with_docstring decorator
```

---

## Modular Components

### 1. ModularPersonaAgent (Main Agent)

**File**: `livekit/livekit_agent.py`
**Lines**: ~700

**Responsibilities**:
- Initialize all handlers (composition)
- Register function tools (delegates to handlers)
- Orchestrate LLM pipeline (llm_node)
- Coordinate handler interactions

**Does NOT**:
- ❌ Handle workflow logic directly
- ❌ Implement tool logic
- ❌ Manage conversation history
- ❌ Build system prompts

**Key Methods**:
```python
class ModularPersonaAgent(Agent):
    def __init__(self, ...):
        # Initialize 9 handlers/managers via composition
        self.workflow_handler = WorkflowHandler(...)
        self.tool_handler = ToolHandler(...)
        self.session_context = SessionContext(...)
        self.document_handler = DocumentHandler(...)
        self.email_capture_handler = EmailCaptureHandler(...)
        self.lifecycle_handler = LifecycleHandler(...)
        self.prompt_manager = PromptManager(...)
        self.rag_manager = RAGManager(...)
        self.conversation_manager = ConversationManager(...)

    # Function tools delegate to handlers
    @function_tool
    async def start_assessment(self):
        return await self.workflow_handler.start_workflow()

    @function_tool
    async def submit_workflow_answer(self, answer: str):
        return await self.workflow_handler.submit_answer(answer)

    @function_tool
    async def capture_lead(self, user_message: str):
        # Conversational workflow extraction
        return await self.workflow_handler.process_conversational_message(...)

    async def llm_node(self, chat_ctx, tools, model_settings):
        # 1. Inject system prompt
        await self.prompt_manager.inject_system_prompt(chat_ctx)

        # 2. Inject conversation history
        self.conversation_manager.inject_conversation_history(chat_ctx)

        # 3. Inject workflow options (linear workflows)
        if self.workflow_handler.is_active:
            await self._inject_workflow_options(chat_ctx)

        # 4. RAG retrieval
        await self.rag_manager.inject_rag_context(chat_ctx)

        # 5. Yield LLM response
        async for chunk in super().llm_node(chat_ctx, tools, model_settings):
            yield chunk

        # 6. Update conversation history
        await self.conversation_manager.update_conversation_history(...)
```

---

### 2. Workflow Handlers (Modular)

**Directory**: `livekit/handlers/workflow/`
**Total Lines**: ~975 (split across 4 files)
**Responsibility**: ALL workflow logic, split by workflow type

#### Architecture: Factory + Inheritance Pattern

```python
# Factory function creates the right handler
def create_workflow_handler(workflow_data, persona_id, ...):
    if workflow_data is None:
        return None  # No workflow configured
    
    workflow_type = workflow_data.get("workflow_type", "simple")
    
    if workflow_type == "conversational":
        return ConversationalWorkflowHandler(...)
    else:
        return LinearWorkflowHandler(...)  # simple, scored
```

#### BaseWorkflowHandler (`base.py` ~230 lines)

Shared logic for both workflow types:

```python
class BaseWorkflowHandler:
    # Session management
    async def start_workflow(self, send_opening_message=True)
    async def _create_workflow_session()  # DB session creation
    
    # Validation
    def _validate_workflow_data()
    
    # Properties
    @property
    def is_active(self) -> bool
    @property
    def workflow_type(self) -> str
```

#### LinearWorkflowHandler (`linear_handler.py` ~310 lines)

For step-by-step Q&A assessments (simple/scored):

```python
class LinearWorkflowHandler(BaseWorkflowHandler):
    async def start_workflow(self, send_opening_message=True)
        # Ask first question via TTS/text
    
    async def submit_answer(self, answer: str)
        # Validate → Save → Ask next question OR complete
    
    async def _complete_workflow(self)
        # Calculate score, find category, show results
        # "🎉 Your score is 28. You're Growth Ready! ..."
```

**Flow**: User answers → LLM calls `submit_workflow_answer()` → System asks next question automatically

#### ConversationalWorkflowHandler (`conversational_handler.py` ~400 lines)

For natural language lead capture with batch field extraction:

```python
class ConversationalWorkflowHandler(BaseWorkflowHandler):
    async def start_workflow(self, send_opening_message=True)
        # Optionally send opening message
    
    async def store_extracted_fields(self, fields: dict[str, str])
        # LLM extracts ALL fields from message in ONE call
        # Stores atomically to prevent race conditions
        # Returns status: "Saved 3 fields. Still need: phone"
    
    async def complete_workflow(self, extracted_fields: dict)
        # Called after user confirms all fields
```

**Flow**: LLM calls `update_lead_fields('{"name": "...", "email": "..."}')` with ALL extracted fields → User confirms → LLM calls `confirm_lead_capture()`

**Why Batch?** When user says "I'm John, email john@email.com, need tax help", the LLM extracts all 3 fields in ONE call. This prevents race conditions that occurred with parallel single-field calls.

**State Management** (in BaseWorkflowHandler):
```python
    self._workflow_session_id: UUID        # Active session
    self._workflow_current_step: int       # Linear: current question index
    self._workflow_answers: Dict[str, Any] # Linear: answers for scoring
```

---

### 3. ToolHandler

**File**: `livekit/handlers/tool_handler.py`
**Lines**: 150
**Responsibility**: Function tools (search, fetch, calendar)

**Tools**:
```python
class ToolHandler:
    async def search_internet(self, query: str) -> str:
        # DuckDuckGo search via AsyncDDGS

    async def fetch_url(self, url: str) -> str:
        # Fetch webpage content (httpx)

    async def send_calendar_link(self) -> str:
        # Send booking link via LiveKit data channel
```

**Feature Flags**:
- `search_enabled`: Enable for specific users (SEARCH_ENABLED_USER_IDS)
- `calendar_enabled`: Enable if persona has `calendar_url` configured

---

### 4. SessionContext

**File**: `livekit/handlers/session_context.py`
**Lines**: 80
**Responsibility**: Conversation state tracking

**Tracks**:
```python
class SessionContext:
    session_id: str
    persona_id: UUID
    conversation_history: List[Dict[str, str]]  # [{"role": "user", "content": "..."}, ...]
    turn_count: int                             # User message count (for email capture)
    user_message_count: int                     # User-only messages (for email capture)
```

**Methods**:
```python
    def add_message(self, role: str, content: str):
        # Append to conversation_history

    def increment_turn(self):
        # Increment turn_count and user_message_count
```

---

### 5. DocumentHandler

**File**: `livekit/handlers/document_handler.py`
**Lines**: 300
**Responsibility**: Process uploaded documents mid-conversation

**Supports**:
- PDF, Word (.doc/.docx), Excel (.xls/.xlsx), PowerPoint (.ppt/.pptx)
- Images (.png/.jpg) with OCR
- URL uploads (fetch and process)

**Methods**:
```python
class DocumentHandler:
    async def process_upload(self, file_path: str, filename: str):
        # Detect type → Extract text → Add to conversation context
```

---

### 6. EmailCaptureHandler

**File**: `livekit/handlers/email_capture_handler.py`
**Lines**: 200
**Responsibility**: Trigger lead capture after N messages

**Logic**:
```python
class EmailCaptureHandler:
    async def check_and_trigger(self) -> bool:
        # If user_message_count >= trigger_after_n_messages:
        #     Ask for email
        #     Return False (disconnect after capture)
        # Else:
        #     Return True (continue conversation)
```

**Config**: `email_capture_settings` from persona

---

### 7. LifecycleHandler

**File**: `livekit/handlers/lifecycle_handler.py`
**Lines**: ~250
**Responsibility**: Agent lifecycle events and citation delivery

**Methods**:
```python
class LifecycleHandler:
    async def on_enter(self):
        # Send greeting + suggested questions

    async def on_exit(self, document_handler):
        # Cleanup: Close document processor, save conversation

    async def send_citations(self, sources: List[Dict], user_query: str):
        # Send RAG sources to frontend via LiveKit data channel
        # Called by RAGManager after context retrieval
```

**Citation Payload Structure** (sent to frontend):
```python
# Published to topic="citations" via room.local_participant.publish_data()
payload = {
    "type": "citations",
    "query": "user's question",
    "sources": [
        {
            "title": "Source Title",
            "source_url": "https://...",      # URL of source (if available)
            "content": "First 300 chars...",  # Preview of content
            "similarity": 0.65,               # Similarity/rerank score
            "source_type": "linkedin_post",   # Type: linkedin_post, linkedin_experience, twitter_post, website_page, document
            "raw_source": "linkedin_post",    # Raw source identifier
        },
        # ... up to 5 sources
    ]
}
```

**Frontend Integration** (CitationSource interface):
```typescript
// Frontend expects these exact field names
interface CitationSource {
  title: string;
  content: string;       // NOT "snippet"
  similarity: number;    // NOT "score"
  source_url?: string;   // NOT "url"
  source_type: string;
  raw_source: string;
}
```

**IMPORTANT**: Field names must match exactly. The backend was updated (Jan 2026) to use `source_url`, `content`, `similarity` instead of `url`, `snippet`, `score`.

**Voice vs Text Mode**:
- **Text Mode**: Frontend `TextChatHandler.tsx` handles citations correctly (checks `type === "voice_citations" || sources`)
- **Voice Mode**: Frontend `TranscriptionHandler.tsx` needs to accept `type: "citations"` (currently only checks `type === "voice_citations"`)

---

### 8. PromptManager

**File**: `livekit/managers/prompt_manager.py`
**Lines**: ~220
**Responsibility**: Build and inject system prompts with workflow promotion

**Key Features**:
- Uses `PromptTemplates.build_system_prompt_dynamic()` for proper voice/text mode handling
- Injects CRITICAL RESPONSE GUIDELINES to ensure LLM uses RAG context
- Supports `text_only_mode` parameter for voice vs text differences
- **Injects workflow promotion instructions** based on `trigger_config`

**Constructor**:
```python
class PromptManager:
    def __init__(
        self,
        persona_info: Dict[str, Any],
        persona_prompt_info: Optional[PersonaPromptMetadata] = None,
        workflow_data: Optional[Dict[str, Any]] = None,  # Includes trigger_config!
        text_only_mode: bool = False,  # Affects prompt building
    ):
```

**Methods**:
```python
class PromptManager:
    def build_system_prompt(self) -> str:
        # 1. Use PromptTemplates.build_system_prompt_dynamic() for proper formatting
        #    - Handles voice vs text mode differences (is_voice flag)
        #    - Applies persona-specific prompt template
        
        # 2. Add CRITICAL RESPONSE GUIDELINES (ensures LLM uses RAG context):
        """
        ⚠️ CRITICAL RESPONSE GUIDELINES:
        1. ONLY use information from:
           - The provided knowledge base/context
           - Retrieved documents and sources
           - Available function tools
           - Uploaded documents from the user
        2. NEVER fabricate, guess, or assume information
        3. If information is NOT in context, clearly state:
           "I don't have that information in my knowledge base."
        4. Always cite sources when available
        """
        
        # 3. Add memory awareness instructions
        
        # 4. Add workflow promotion instructions (if workflow configured)
        if self.workflow_data and self.workflow_data.get("workflow_objective"):
            trigger_config = self.workflow_data.get("trigger_config") or {}
            promotion_mode = trigger_config.get("promotion_mode", "contextual")
            # Builds proactive/contextual/reactive promotion prompt
            workflow_prompt = build_workflow_system_prompt(
                workflow_title=workflow_objective,
                promotion_mode=promotion_mode,  # "proactive", "contextual", "reactive"
                workflow_type=workflow_type,
                max_attempts=trigger_config.get("max_attempts", 3),
                cooldown_turns=trigger_config.get("cooldown_turns", 5),
            )

    async def inject_system_prompt(self, chat_ctx: ChatContext):
        # Build prompt and inject into chat_ctx.items[0]
```

**Workflow Promotion Modes** (from `trigger_config.promotion_mode`):

| Mode | Behavior |
|------|----------|
| `proactive` | Push workflow within 1-2 turns, introduce immediately after greeting |
| `contextual` | Wait for conversation to naturally align with workflow purpose |
| `reactive` | Only mention if user explicitly asks |

**CRITICAL**: The CRITICAL RESPONSE GUIDELINES are essential for RAG to work. Without them, the LLM may ignore retrieved context and generate generic responses.

---

### 9. RAGManager

**File**: `livekit/managers/rag_manager.py`
**Lines**: ~220
**Responsibility**: RAG context injection and citation delivery

**Process Flow**:
1. Extract user query from chat context
2. Retrieve relevant context from ContextPipeline (vector DB + reranker)
3. Get document context from session (uploaded files)
4. Combine both contexts
5. Send citations to frontend via LifecycleHandler
6. Inject combined context into chat as system message

**Methods**:
```python
class RAGManager:
    async def inject_rag_context(self, chat_ctx: ChatContext):
        # 1. Lazy load RAG system if needed
        if not self.rag_system:
            self.rag_system = get_rag_system()
        
        # 2. Extract user queries from chat context
        user_queries = []
        for item in reversed(chat_ctx.items):
            if item.role == "user":
                user_queries.insert(0, parse_message_text(item.text_content))
            elif item.role in ["assistant", "agent"]:
                break  # Stop at last assistant turn
        
        # 3. Call ContextPipeline for RAG retrieval
        context_result = await ContextPipeline(...).process(
            persona_id=str(self.persona_id),
            user_query=user_query,
            top_k=5,
            similarity_threshold=0.4,
            return_citations=True,
        )
        
        # 4. Get document context (uploaded files)
        document_context = self.session_context.get_document_context(max_chars=50000)
        
        # 5. Send citations to frontend
        await self.lifecycle_handler.send_citations(sources, user_query)
        
        # 6. Inject combined context into chat
        rag_msg = llm.ChatMessage(
            role="system",
            content=["Context information is below.\n-----\n{context}\n-----\n"]
        )
        chat_ctx.items.insert(insert_position, rag_msg)
```

**Context Insertion Position**: RAG context is inserted BEFORE the last user message so the LLM sees:
```
[system prompt] → [RAG context] → [user message]
```

---

### 10. ConversationManager

**File**: `livekit/managers/conversation_manager.py`
**Lines**: 200
**Responsibility**: Conversation history management

**Methods**:
```python
class ConversationManager:
    async def load_conversation_history(self):
        # Load from DB if session_token provided

    def inject_conversation_history(self, chat_ctx: ChatContext, max_messages=10):
        # Inject last N messages into chat_ctx

    async def update_conversation_history(self, chat_ctx, collected_response):
        # After LLM response, save to session_context
```

---

## Workflow System

### Workflow Types

#### 1. Linear Workflows (Simple/Scored)

**Characteristics**:
- Step-by-step Q&A
- Fixed question order
- User answers → LLM matches to options → Next question
- Completion: Score calculation + result category

**Example**: Business Growth Readiness Quiz
```json
{
  "workflow_type": "scored",
  "steps": [
    {
      "step_id": "q1",
      "step_type": "multiple_choice",
      "question_text": "Can you explain your business in one sentence?",
      "options": [
        {"label": "A", "text": "Not really", "score": 0},
        {"label": "B", "text": "Can describe it", "score": 1},
        {"label": "C", "text": "Yes but complex", "score": 2},
        {"label": "D", "text": "Absolutely clear", "score": 4}
      ]
    }
  ],
  "result_config": {
    "categories": [
      {
        "min_score": 0,
        "max_score": 12,
        "message": "You're in Survival Mode. Focus on..."
      },
      {
        "min_score": 13,
        "max_score": 24,
        "message": "You're Growth Ready! ..."
      }
    ]
  }
}
```

**Flow**:
```
1. User: "Yeah" (agrees to start)
   ↓
2. LLM calls: start_assessment()
   ↓
3. WorkflowHandler: Ask first question via TTS
   ↓
4. User: "AI startup helps with inbound"
   ↓
5. LLM calls: submit_workflow_answer(answer="Our AI startup...")
   ↓
6. WorkflowHandler: Match to option → Save answer → Ask next question
   ↓
7. Repeat steps 4-6 for all questions
   ↓
8. Last question answered → _complete_linear_workflow()
   ↓
9. Calculate score: total_score = sum(all answer scores)
   ↓
10. Find matching category (min_score <= total_score <= max_score)
   ↓
11. Output: "🎉 Your score is 28. You're Growth Ready! ..."
```

**CRITICAL**: LLM must call `submit_workflow_answer()` IMMEDIATELY after user answers:
- ❌ **DO NOT** generate explanatory text
- ❌ **DO NOT** ask follow-up questions
- ✅ **ONLY** call the function → System asks next question automatically

#### 2. Conversational Workflows (Field Extraction)

**Characteristics**:
- Natural dialogue (no rigid Q&A)
- LLM extracts fields organically
- Adapts to user's communication style
- Asks clarifying questions only when needed

**Example**: CPA Lead Capture
```json
{
  "workflow_type": "conversational",
  "required_fields": [
    {"field_id": "full_name", "label": "Full Name", "type": "text"},
    {"field_id": "email", "label": "Email", "type": "email"},
    {"field_id": "phone", "label": "Phone", "type": "phone"},
    {"field_id": "service_needed", "label": "Service Needed", "type": "text"}
  ]
}
```

**Flow** (using `update_lead_field` and `confirm_lead_capture` tools):
```
1. User: "hi"
   ↓
2. Agent: "Hi! I help with CPA services like tax prep. What brings you here?"
   (NO workflow started yet - just greeting)
   ↓
3. User: "I need help with quarterly taxes, my name is John"
   ↓
4. LLM calls: update_lead_field("contact_name", "John")
             update_lead_field("service_need", "quarterly taxes")
   ↓
5. ConversationalWorkflowHandler auto-starts if not active, stores fields
   ↓
6. Returns: "Fields stored. Remaining: contact_email, contact_phone"
   ↓
7. Agent: "Great John! What's your email and phone number?"
   ↓
8. User: "john@example.com, 555-1234"
   ↓
9. LLM calls: update_lead_field("contact_email", "john@example.com")
             update_lead_field("contact_phone", "555-1234")
   ↓
10. Returns: "AWAITING_CONFIRMATION" (all required fields collected)
    ↓
11. Agent: "Perfect! I have: John, john@example.com, 555-1234 for quarterly taxes. Is that correct?"
    ↓
12. User: "yes"
    ↓
13. LLM calls: confirm_lead_capture()
    ↓
14. ConversationalWorkflowHandler completes workflow → Status: "completed"
    ↓
15. Agent: "Awesome! I'm all set. What can I help you with for your taxes?"
```

**CRITICAL Tools**:
- `update_lead_field(field_id, value)` - LLM extracts ONE field at a time
- `confirm_lead_capture()` - Called ONLY after user confirms all fields

**Pattern**:
- ✅ LLM calls `update_lead_field()` for each extracted field
- ✅ Handler returns remaining fields or "AWAITING_CONFIRMATION"
- ✅ LLM asks for missing fields naturally
- ✅ When all fields collected, LLM asks user to confirm
- ✅ After confirmation, LLM calls `confirm_lead_capture()`

---

### Workflow Tool Filtering

**Problem**: If both linear tools (`start_assessment`, `submit_workflow_answer`) and conversational tools (`update_lead_field`, `confirm_lead_capture`) are available, LLM gets confused about which to call.

**Solution**: Filter tools based on workflow type in `__init__`:

```python
# livekit_agent.py lines 279-314
if self.workflow_handler:
    workflow_type = self.workflow_handler.workflow_type
    filtered_tools = []
    tools_to_remove = []

    for tool in self._tools:
        tool_name = tool.__name__

        if workflow_type == "conversational":
            # REMOVE linear tools
            if tool_name in ["start_assessment", "submit_workflow_answer"]:
                tools_to_remove.append(tool_name)
                continue

        elif workflow_type == "linear":
            # REMOVE conversational tools
            if tool_name in ["update_lead_field", "confirm_lead_capture"]:
                tools_to_remove.append(tool_name)
                continue

        filtered_tools.append(tool)

    self._tools = filtered_tools
```

**Result**:
- Linear workflow: Only `start_assessment()` and `submit_workflow_answer()` available
- Conversational workflow: Only `update_lead_field()` and `confirm_lead_capture()` available
- No workflow: All tools available
- No confusion!

---

## Request Flow

### Voice Mode Flow

```
1. Frontend: User clicks "Start Voice Call"
   ↓
2. POST /api/v1/livekit/connection-details
   ↓
3. livekit_routes.py:
   - Create room
   - Dispatch ModularPersonaAgent to room
   - Return connection details to frontend
   ↓
4. Frontend connects to LiveKit room
   ↓
5. Agent enters room → ModularPersonaAgent.on_enter()
   ↓
6. LifecycleHandler sends greeting + suggested questions
   ↓
7. User speaks → Deepgram STT → Text
   ↓
8. ModularPersonaAgent.llm_node(chat_ctx, tools, model_settings)
   ├─> PromptManager.inject_system_prompt()
   ├─> ConversationManager.inject_conversation_history()
   ├─> RAGManager.inject_rag_context()
   └─> LLM generates response (may call tools)
   ↓
9. LLM response → ElevenLabs TTS → Audio
   ↓
10. Agent speaks to user
   ↓
11. Repeat steps 7-10 until user disconnects
   ↓
12. User disconnects → Agent shutdown
   ↓
13. ModularPersonaAgent.on_exit()
    ├─> LifecycleHandler.on_exit()
    ├─> Save conversation to DB
    └─> Cleanup resources
```

### Text Mode Flow

```
1. Frontend: WebSocket connection to /api/v1/livekit/text-session
   ↓
2. livekit_routes.py (text_session_websocket):
   - Create text session
   - Initialize ModularPersonaAgent (text_only_mode=True)
   - No LiveKit room - direct WebSocket communication
   ↓
3. Agent initialization:
   - Skip TTS/STT initialization
   - Use room.local_participant.send_text() for output
   ↓
4. User sends message via WebSocket
   ↓
5. ModularPersonaAgent.llm_node(chat_ctx, tools, model_settings)
   (Same pipeline as voice)
   ↓
6. LLM response → Send via lk.chat topic
   ↓
7. Frontend receives text response
   ↓
8. Repeat steps 4-7
```

---

## Implementation Details

### Critical Fixes Made During Refactor

#### 1. Workflow Loop Fix (SOLVED)

**Problem**: LLM calling `submit_workflow_answer()` repeatedly without waiting for user.

**Root Cause**: Tool was returning question text → LLM thought it needed to answer it → Looped until function call limit.

**Fix** (workflow_handler.py:332, livekit_agent.py:676):
```python
# WorkflowHandler.submit_answer()
await self._ask_current_question()  # Ask next question via TTS
# Return None (don't return question text)

# ModularPersonaAgent.submit_workflow_answer()
await self.workflow_handler.submit_answer(answer)
return ""  # Empty string prevents LLM text generation
```

**Pattern**:
```
User answers → Validate → Save → Ask next question via TTS → Return empty → LLM waits for user
```

#### 2. Workflow Scoring Implementation (SOLVED)

**Problem**: Workflow completed without showing score/results.

**Root Cause**: `_complete_linear_workflow()` had `# TODO: Implement scoring` (line 412).

**Fix** (workflow_handler.py:410-462):
```python
async def _complete_linear_workflow(self):
    workflow_type = self.workflow_data.get("workflow_type", "simple")

    if workflow_type == "scored":
        # Calculate total score
        total_score = sum(
            a["score"] for a in self._workflow_answers.values()
            if a.get("score") is not None
        )

        # Find matching category
        categories = self.workflow_data.get("result_config", {}).get("categories", [])
        for category in categories:
            if category["min_score"] <= total_score <= category["max_score"]:
                matching_category = category
                break

        # Build result message
        result = f"🎉 Assessment complete! Your score is {total_score}. {matching_category['message']}"
    else:
        result = "🎉 Assessment complete! Thank you for your responses."

    await self._output_message(result, allow_interruptions=False)
```

**Also Added** (workflow_handler.py:387):
```python
# Store answers in memory for scoring
self._workflow_answers[step["step_id"]] = {"answer": answer, "score": score}
```

#### 3. RAG Context Being Ignored Fix (SOLVED - Jan 2026)

**Problem**: Modular agent was retrieving RAG context but LLM was ignoring it, responding with generic messages like "Hello! How can I assist you today?"

**Root Cause**: `PromptManager` was missing critical components that the legacy agent includes:
1. Not using `PromptTemplates.build_system_prompt_dynamic()` for proper prompt building
2. Missing "CRITICAL RESPONSE GUIDELINES" that instruct LLM to use RAG context
3. No memory awareness instructions

**Symptoms**:
- RAG context retrieved successfully (visible in logs)
- Citations generated and sent to frontend
- Token count reflected RAG being sent to OpenAI
- BUT LLM response was generic, not using knowledge base

**Fix** (prompt_manager.py):
```python
# Before (broken):
if self.persona_prompt_info:
    self._cached_system_prompt = self.persona_prompt_info.example_prompt  # Raw prompt only!

# After (fixed):
if self.persona_prompt_info:
    # Use PromptTemplates for proper dynamic prompt building
    self._cached_system_prompt = PromptTemplates.build_system_prompt_dynamic(
        self.persona_prompt_info,
        self.persona_info,
        is_voice=not self.text_only_mode,
    )

# Add CRITICAL RESPONSE GUIDELINES
self._cached_system_prompt += """
⚠️ CRITICAL RESPONSE GUIDELINES:
1. ONLY use information from:
   - The provided knowledge base/context
   - Retrieved documents and sources
2. NEVER fabricate, guess, or assume information not in your knowledge sources
3. If information is NOT in your context, clearly state:
   "I don't have that information in my knowledge base."
4. Always cite sources when available
"""

# Add memory awareness
self._cached_system_prompt += "\n\n🧠 CONVERSATION MEMORY:\n"
self._cached_system_prompt += "You have access to the full conversation history.\n"
```

**Key Insight**: The legacy agent (`livekit_agent_retrieval.py`) includes these guidelines in `_build_system_prompt()`. The modular agent was missing them, causing the LLM to ignore RAG context.

#### 4. Citation Field Mismatch Fix (SOLVED - Jan 2026)

**Problem**: Citations sent by backend but not displayed on frontend.

**Root Cause**: Backend was sending different field names than frontend expected:

| Backend Sent | Frontend Expected | 
|--------------|-------------------|
| `url` | `source_url` |
| `snippet` | `content` |
| `score` | `similarity` |
| *(missing)* | `raw_source` |

**Fix** (lifecycle_handler.py):
```python
# Before (broken):
formatted_sources.append({
    "title": source.get("title", "Untitled"),
    "url": source.get("source_url") or source.get("url", ""),
    "snippet": source.get("content", "")[:300],
    "score": source.get("similarity") or source.get("score", 0.0),
    "source_type": source.get("source_type", "document"),
})

# After (fixed):
formatted_sources.append({
    "title": source.get("title", "Untitled"),
    "source_url": source.get("source_url") or source.get("url", ""),
    "content": source.get("content", "")[:300],
    "similarity": source.get("similarity") or source.get("score", 0.0),
    "source_type": source.get("source_type", "document"),
    "raw_source": source.get("raw_source") or source.get("source_type", ""),
})
```

**Also Fixed**: Added `post_url` to URL extraction in `context_pipeline.py` and `llama_rag.py` for LinkedIn posts.

---

### Key Design Patterns

#### 1. Composition Over Inheritance

**Before**:
```python
class PersonaRetrievalAgent(Agent):
    # All logic in one class
    def start_assessment(self): ...
    def submit_workflow_answer(self): ...
    def search_internet(self): ...
    # ... 50+ methods
```

**After**:
```python
class ModularPersonaAgent(Agent):
    def __init__(self):
        self.workflow_handler = WorkflowHandler(...)
        self.tool_handler = ToolHandler(...)
        # ... 7 more handlers

    @function_tool
    async def start_assessment(self):
        return await self.workflow_handler.start_workflow()
```

**Benefits**:
- Single Responsibility Principle
- Easy to test (mock individual handlers)
- Clear boundaries between concerns

#### 2. Dependency Injection

Handlers receive dependencies via `__init__`:

```python
class WorkflowHandler:
    def __init__(
        self,
        workflow_data: Dict[str, Any],
        persona_id: UUID,
        output_callback: Callable,  # Injected!
        text_only_mode: bool,
    ):
        self._output_message = output_callback
```

**Benefits**:
- Testable (inject mocks)
- Flexible (swap implementations)

#### 3. Handler Delegation

Main agent delegates ALL logic to handlers:

```python
@function_tool
async def submit_workflow_answer(self, answer: str) -> str:
    await self.workflow_handler.submit_answer(answer)
    return ""
```

**Benefits**:
- Agent is thin orchestration layer
- Logic centralized in specialized handlers

---

## Testing & Debugging

### Unit Testing Handlers

```python
# Test WorkflowHandler in isolation
async def test_workflow_completion():
    # Mock output callback
    output_messages = []
    async def mock_output(msg, allow_interruptions):
        output_messages.append(msg)

    # Create handler
    handler = WorkflowHandler(
        workflow_data=test_workflow,
        persona_id=test_persona_id,
        output_callback=mock_output,
        text_only_mode=False,
    )

    # Start workflow
    await handler.start_workflow()
    assert handler.is_active

    # Submit answers
    await handler.submit_answer("A")
    await handler.submit_answer("B")

    # Check completion message
    assert "Assessment complete" in output_messages[-1]
```

### Integration Testing

```python
# Test full agent with mocked LiveKit
async def test_voice_workflow():
    agent = ModularPersonaAgent(
        persona_username="test-persona",
        workflow_data=test_workflow,
        ...
    )

    await agent.initialize()

    # Simulate user starting workflow
    await agent.start_assessment()

    # Simulate user answering
    await agent.submit_workflow_answer("A")
    await agent.submit_workflow_answer("B")

    # Verify workflow completed
    assert not agent.workflow_handler.is_active
```

### Debugging Tools

**1. Logs** (extensive logging throughout):
```python
logger.info(f"📝 Processing answer for step {self._workflow_current_step + 1}/{len(steps)}")
logger.info(f"📊 Total score: {total_score}")
```

**2. Print Statements** (temporary debugging):
```python
print(f"🚨 [LLM_NODE] METHOD CALLED! Tools: {len(tools)}\n", flush=True)
```

**3. Tool Filtering Debug** (livekit_agent.py:285-337):
```python
print(f"🚨 CHECKING WORKFLOW FILTERING: has_workflow={self.has_workflow}\n", flush=True)
print(f"🚨 Workflow type: {workflow_type}\n", flush=True)
print(f"🚨 Starting tool filtering loop over {len(self._tools)} tools...\n", flush=True)
```

---

## Summary

### Modular Agent Benefits

✅ **Maintainability**: 700-line main file vs 2900-line monolith
✅ **Testability**: Mock individual handlers
✅ **Readability**: Clear separation of concerns
✅ **Extensibility**: Add new handlers without touching existing code
✅ **Debuggability**: Easy to trace issues to specific handler
✅ **Collaboration**: Reduced merge conflicts

### File Map

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Main Agent | livekit/livekit_agent.py | 700 | Orchestration |
| Workflow Logic | livekit/handlers/workflow_handler.py | 465 | Linear + Conversational workflows |
| Tools | livekit/handlers/tool_handler.py | 150 | Search, fetch, calendar |
| Session Tracking | livekit/handlers/session_context.py | 80 | Conversation state |
| Documents | livekit/handlers/document_handler.py | 300 | PDF/Word/Excel processing |
| Email Capture | livekit/handlers/email_capture_handler.py | 200 | Lead generation |
| Lifecycle | livekit/handlers/lifecycle_handler.py | 150 | on_enter, on_exit |
| Prompts | livekit/managers/prompt_manager.py | 100 | System prompt building |
| RAG | livekit/managers/rag_manager.py | 150 | Context injection |
| Conversation | livekit/managers/conversation_manager.py | 200 | History management |

### Workflow Types Supported

| Type | Description | Tools | Completion |
|------|-------------|-------|------------|
| Linear (Simple) | Step-by-step Q&A | start_assessment, submit_workflow_answer | Generic thank you |
| Linear (Scored) | Step-by-step Q&A with scoring | start_assessment, submit_workflow_answer | Score + category message |
| Conversational | Organic field extraction | capture_lead | Summary of captured fields |

---

## References

- [LiveKit Agents Framework](https://docs.livekit.io/agents/)
- [LiveKit Function Tools](https://docs.livekit.io/agents/logic/tools/)
- [LiveKit Tasks](https://docs.livekit.io/agents/logic/tasks/)
- [LIVEKIT_TASKS_AND_TOOLS.md](./LIVEKIT_TASKS_AND_TOOLS.md) - Deep dive into tools vs tasks
- [LIVEKIT_RECORDING_ARCHITECTURE.md](./LIVEKIT_RECORDING_ARCHITECTURE.md) - Recording implementation
