# Content Mode Architecture

> **Status**: Production
> **Last Updated**: 2026-02-20
> **Owner**: LiveKit Agent Team

## Overview

Content Mode allows personas to generate long-form content (blogs, LinkedIn posts, newsletters) during voice or text conversations. The core challenge: the voice LLM has strict brevity rules (25-40 words, no markdown) that conflict with long-form writing. Rather than fighting those constraints with prompt overrides, content generation happens in a **separate, isolated LLM call** with its own clean prompt.

## Key Design Decision: Why an Isolated LLM?

The voice pipeline's system prompt enforces short, spoken-style responses. Trying to make the same LLM produce an 800-word markdown blog while also obeying "keep responses under 40 words" creates conflicting instructions. The isolated approach gives us:

- **Clean separation** — the content writer LLM has zero brevity constraints
- **Independent prompt engineering** — we can optimize the writer prompt without affecting voice quality
- **Persona voice injection** — the writer gets persona style info, RAG context, and search results in a purpose-built prompt
- **No token budget competition** — the writer gets its own 4096-token budget

## Architecture

```
User: "Write me a blog about legal tech trends"
         |
         v
  ┌─────────────────────────────────────────┐
  │           VOICE LLM (gpt-4.1-mini)      │
  │  System prompt: brevity rules + content  │
  │  mode flow instructions                  │
  │                                          │
  │  1. Clarify: topic? audience? tone?      │
  │  2. Topic boundary check (expertise)     │
  │  3. search_internet(topic)               │
  │  4. generate_content(type, title,        │
  │     topic, audience, tone)               │
  └──────────────┬──────────────────────────┘
                 │
                 │  tool call
                 v
  ┌─────────────────────────────────────────┐
  │         ModularPersonaAgent              │
  │                                          │
  │  - Stores search result from step 3      │
  │    in _last_search_result                │
  │  - Passes it + tool args to              │
  │    ContentHandler.generate_content()     │
  └──────────────┬──────────────────────────┘
                 │
                 v
  ┌─────────────────────────────────────────┐
  │           ContentHandler                 │
  │                                          │
  │  1. Retrieve RAG context (topic query)   │
  │  2. Build CONTENT_WRITER_SYSTEM_PROMPT   │
  │     - Persona name, role, style          │
  │     - Blending rules                     │
  │     - Content-type structure             │
  │  3. Build user message                   │
  │     - Title, topic, audience, tone       │
  │     - RAG context (persona knowledge)    │
  │     - Search results (internet facts)    │
  │  4. Isolated LLM call (gpt-4.1-mini)    │
  │  5. Publish "writing" status to frontend │
  │  6. Collect full response                │
  │  7. Queue payload for frontend delivery  │
  │  8. Return confirmation to voice LLM     │
  └──────────────┬──────────────────────────┘
                 │
                 v
  ┌─────────────────────────────────────────┐
  │  Next llm_node turn (confirmation)       │
  │                                          │
  │  flush_pending_content() fires →         │
  │  Frontend receives content_output via    │
  │  data channel                            │
  │                                          │
  │  Voice LLM says: "Here's your blog!      │
  │  It's on your screen now."               │
  └─────────────────────────────────────────┘
```

## File Map

| File | Role |
|------|------|
| `livekit/constants/content_prompts.py` | Both prompt templates — `CONTENT_MODE_SYSTEM_PROMPT` (voice flow) and `CONTENT_WRITER_SYSTEM_PROMPT` (isolated writer) |
| `livekit/handlers/content_handler.py` | Isolated LLM call, RAG retrieval, payload queuing, status publishing |
| `livekit/constants/tool_docstrings.py` | `GENERATE_CONTENT_DOC` — tool description the voice LLM sees |
| `livekit/livekit_agent.py` | Tool wrappers, search result storage, ContentHandler wiring |
| `livekit/utils/status.py` | Shared `publish_agent_status()` utility |
| `livekit/managers/prompt_manager.py` | Appends `CONTENT_MODE_SYSTEM_PROMPT` to voice LLM's system prompt |

## The Two Prompts

There are two completely separate prompts. Understanding the distinction is critical.

### 1. `CONTENT_MODE_SYSTEM_PROMPT` (Voice LLM)

Appended to the voice LLM's system prompt when `content_mode_enabled=True`. Controls the **conversation flow** only:

- Step 1: Ask clarification (topic, audience, tone)
- Step 1b: Topic boundary check against persona expertise
- Step 2: Announce and call `search_internet`
- Step 3: Call `generate_content` with inputs (NOT the body)
- Step 4: Speak short confirmation

This prompt does **not** contain any content writing instructions. The voice LLM never writes the body.

### 2. `CONTENT_WRITER_SYSTEM_PROMPT` (Isolated Writer LLM)

Used only inside `ContentHandler._generate_content_body()`. This is a template with placeholders:

- `{persona_name}`, `{persona_role}` — identity
- `{persona_style_section}` — thinking style, expertise, example writing style (from `persona_prompt_info`)
- `{content_type_instructions}` — structure/length requirements per content type
- Blending rules: research facts + persona perspective
- Formatting rules: markdown, minimize bullets for blogs, prose for insights

## Content Types

| Type | Target Length | Structure |
|------|-------------|-----------|
| `blog` | 800-1500 words | Hook intro, 3-5 sections with H2 headings, conclusion with CTA |
| `linkedin_post` | 150-300 words | Opening hook, personal story, key takeaway, hashtags |
| `newsletter` | 400-800 words | Subject line, intro, main sections, key takeaways, sign-off |

## Data Flow: What the Isolated LLM Receives

The writer LLM gets two distinct context blocks in its user message:

```
--- PERSONA KNOWLEDGE BASE (use for opinions, experiences, unique angles) ---
[RAG chunks retrieved using topic as query — persona's own content]

--- RESEARCH RESULTS (use for facts, stats, recent developments) ---
[Internet search results from search_internet tool call]
```

The blending rules in the system prompt instruct the LLM how to combine these:
- **Research** provides facts, dates, names, statistics
- **Knowledge base** provides opinions, frameworks, personal experiences
- **Persona voice** drives structure and framing

## Search Result Passthrough (Option A)

The voice LLM calls `search_internet` → results return to chat context. We need those results in the isolated LLM. The mechanism:

1. `search_internet` tool wrapper stores raw result in `self._last_search_result`
2. `generate_content` tool wrapper reads `self._last_search_result`, clears it, passes as `search_context`
3. ContentHandler includes it in the user message to the isolated LLM

Important: the `_last_search_result` stores the **clean** search result. The "NEXT STEP" instruction appended to the voice LLM's return value is added *after* the store (Python string immutability ensures no contamination).

## Topic Boundary Check

Content mode includes a guardrail: if the requested topic falls outside the persona's defined expertise, the voice LLM should decline and suggest alternatives. This is enforced at the prompt level in `CONTENT_MODE_SYSTEM_PROMPT` step 1b.

The persona's `area_of_expertise` (visible in the voice LLM's system prompt) is the reference. This field is generated by `_analyze_expertise()` which prioritizes user-defined `role` and `expertise` from the personas table over scraped LinkedIn data.

## Frontend Integration

### Status Events

ContentHandler publishes status events via data channel on topic `agent_status`:

| Status | When | Message |
|--------|------|---------|
| `"writing"` | Isolated LLM starts generating | `"Writing your blog..."` |
| `"idle"` | Generation complete (success or error) | — |

These use the same mechanism as ToolHandler's `"searching"` and `"fetching"` statuses, via the shared `publish_agent_status()` utility.

### Content Delivery

Content is delivered via data channel on topic `content_output`:

```json
{
  "type": "content_output",
  "content_type": "blog",
  "title": "The Future of Legal Tech",
  "body": "## Introduction\n\nMarkdown content here...",
  "persona_name": "Jane Smith",
  "persona_role": "Attorney"
}
```

**Timing**: Content is queued in `_pending_content` during the tool call, then flushed at the **start of the next `llm_node` turn** (the confirmation turn). This means the content card appears on screen right as the agent starts speaking "Here's your blog!"

### Pending Content Guard

Only one content piece can be pending at a time. If `generate_content` is called while a previous piece hasn't been flushed yet, a `ToolError` is raised. This prevents silent overwrites.

## Enabling Content Mode

Content mode is controlled per-persona via the `content_mode_enabled` boolean on the personas table. When enabled:

1. `PromptManager` appends `CONTENT_MODE_SYSTEM_PROMPT` to the voice system prompt
2. `ContentHandler` is instantiated with persona info, prompt info, persona_id, and RAG system
3. The `generate_content` tool is registered (filtered out when content mode is off)
4. `search_internet` is force-enabled (content always needs research)

## Expertise Alignment

A critical dependency: the `area_of_expertise` field in `persona_prompts` must reflect the user's intended expertise, not just scraped data. The `_analyze_expertise()` method in `advanced_prompt_creator.py` handles this:

- Reads `persona.role` and `persona.expertise` from the personas table (user-defined)
- Uses these as **source of truth** in the OpenAI analysis prompt
- LinkedIn data is supplementary — only used to add depth within the user-defined domain
- If scraped data conflicts (e.g. LinkedIn shows software dev, user says Attorney), scraped data is ignored

This ensures the topic boundary check and the content writer's persona voice are grounded in the correct expertise.

## Common Issues & Debugging

**Content returns 0 chars**: Check that the LLM streaming response is parsed correctly. LiveKit's `openai.LLM.chat()` yields `ChatChunk` objects — use `chunk.delta.content`, NOT `chunk.choices[0].delta.content`.

**No RAG context in content**: Verify `content_handler.rag_system` is not None. It's set to None initially and updated via `update_rag_system()` after async init in `livekit_agent.py`.

**Topic boundary not enforced**: The check is prompt-level. If the persona's `area_of_expertise` is wrong (e.g. shows tech skills for an Attorney), the LLM may rationalize past the boundary. Fix the expertise data by regenerating the persona prompt.

**Content not showing on frontend**: Check that `flush_pending_content()` is called in `llm_node`. Verify the frontend handles the `content_output` data channel topic.

**"Pending content" error**: The voice LLM tried to call `generate_content` twice before the first piece was flushed. This is rare — usually means the voice LLM retried after a transient error.
