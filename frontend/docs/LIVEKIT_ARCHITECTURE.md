# LiveKit Chat Architecture

This document describes the LiveKit-based real-time communication architecture for both text and voice chat modes in the ConvoxAI application.

## Overview

Both text and voice chat modes use LiveKit for real-time communication with the backend agent. The architecture is unified around the `lk.chat` topic for agent text responses, with mode-specific handling for voice transcription.

## Data Flow Diagrams

### Text Chat Mode

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TEXT CHAT MODE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

 USER INPUT                        BACKEND AGENT                    FRONTEND
 ──────────                        ─────────────                    ────────

 ┌──────────┐    sendText()      ┌─────────────┐
 │  User    │ ────────────────►  │   Agent     │
 │  types   │   topic: lk.chat   │  (Python)   │
 │ message  │                    │             │
 └──────────┘                    └──────┬──────┘
                                        │
                                        │ send_text()
                                        │ topic: lk.chat
                                        ▼
                                 ┌─────────────┐
                                 │  LiveKit    │
                                 │   Room      │
                                 └──────┬──────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
              ▼                         ▼                         ▼
    ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
    │ TextStreamHandler│    │  DataReceived    │    │ TranscriptionRx  │
    │   (lk.chat)      │    │   (citations,    │    │   (segments)     │
    │                  │    │  document_status)│    │                  │
    │   ✅ HANDLES     │    │   ✅ HANDLES     │    │   ✅ HANDLES     │
    │   agent text     │    │   metadata only  │    │   STT segments   │
    └────────┬─────────┘    └──────────────────┘    └────────┬─────────┘
             │                                               │
             └───────────────────┬───────────────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │   onMessage()    │
                        │   callback       │
                        └────────┬─────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │   Chat UI        │
                        │   displays msg   │
                        └──────────────────┘
```

### Voice Chat Mode

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              VOICE CHAT MODE                                │
└─────────────────────────────────────────────────────────────────────────────┘

 USER SPEECH                       BACKEND AGENT                    FRONTEND
 ───────────                       ─────────────                    ────────

 ┌──────────┐                    ┌─────────────┐
 │  User    │   Audio Stream     │   LiveKit   │
 │ speaks   │ ────────────────►  │    STT      │
 │          │                    │             │
 └──────────┘                    └──────┬──────┘
                                        │
                                        │ Transcription
                                        ▼
                                 ┌─────────────┐
                                 │   Agent     │
                                 │  (Python)   │
                                 │             │
                                 └──────┬──────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │  send_text() │   │   TTS Audio  │   │  citations   │
            │ topic:lk.chat│   │   Stream     │   │ topic:citations
            └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
                   │                  │                  │
                   ▼                  ▼                  ▼
            ┌─────────────────────────────────────────────────┐
            │                  LiveKit Room                    │
            └─────────────────────────┬───────────────────────┘
                                      │
       ┌──────────────────────────────┼──────────────────────────────┐
       │                              │                              │
       ▼                              ▼                              ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ TextStreamHandler│       │  DataReceived    │       │TranscriptionRx   │
│   (lk.chat)      │       │                  │       │                  │
│                  │       │ ⏭️ SKIPS lk.chat │       │  ✅ HANDLES      │
│  ✅ HANDLES      │       │ ⏭️ SKIPS lk.trans│       │  user speech     │
│  agent text      │       │                  │       │  segments        │
│  response        │       │ ✅ HANDLES:      │       │                  │
│                  │       │  - citations     │       │                  │
│                  │       │  - calendar      │       │                  │
│                  │       │  - empty topic   │       │                  │
└────────┬─────────┘       └──────────────────┘       └────────┬─────────┘
         │                                                     │
         └─────────────────────┬───────────────────────────────┘
                               │
                               ▼
                      ┌──────────────────┐
                      │setTranscriptMsg()│
                      └────────┬─────────┘
                               │
                               ▼
                      ┌──────────────────┐
                      │  Transcript UI   │
                      └──────────────────┘
```

## LiveKit Topics

All topics are defined in `src/lib/livekit/constants.ts`.

| Topic              | Direction      | Handler             | Mode  | Description                     |
| ------------------ | -------------- | ------------------- | ----- | ------------------------------- |
| `lk.chat`          | Client → Agent | `sendText()`        | Text  | User sends text message         |
| `lk.chat`          | Agent → Client | `TextStreamHandler` | Both  | Agent text response             |
| `lk.transcription` | Agent → Client | `TextStreamHandler` | Both  | Alternative transcription topic |
| `citations`        | Agent → Client | `DataReceived`      | Both  | RAG citation sources            |
| `calendar`         | Agent → Client | `DataReceived`      | Voice | Calendar booking URL            |
| `document_status`  | Agent → Client | `DataReceived`      | Text  | PDF processing status           |
| `chat_error`       | Agent → Client | `DataReceived`      | Text  | Error messages (rate limit)     |
| `""` (empty)       | Agent → Client | `DataReceived`      | Both  | Fallback topic                  |

## Frontend Components

### Text Chat Mode

**File:** `src/components/expert/text/TextChatHandler.tsx`

```typescript
// Event handlers registered:
registerTextStreamHandler("lk.chat"); // Agent text responses
registerTextStreamHandler("lk.transcription"); // Agent text responses
DataReceived; // citations, document_status, chat_error
TranscriptionReceived; // STT segments (if any)
```

### Voice Chat Mode

**File:** `src/components/expert/voice/TranscriptionHandler.tsx`

```typescript
// Event handlers registered:
registerTextStreamHandler("lk.chat"); // Agent text responses (PRIMARY)
DataReceived; // citations, calendar, empty topic
// ⏭️ SKIPS lk.chat, lk.transcription
TranscriptionReceived; // User speech + Agent speech segments
```

## Message Format

### Agent Text Response

The agent sends messages in JSON format:

```json
{
  "message": "Hello! How can I help you?",
  "is_final": true
}
```

Or plain text (fallback):

```
Hello! How can I help you?
```

### Citations

```json
{
  "type": "voice_citations",
  "sources": [
    {
      "title": "Document Title",
      "content": "Relevant excerpt...",
      "similarity": 0.85,
      "source_url": "https://...",
      "source_type": "document",
      "raw_source": "pdf:document.pdf"
    }
  ],
  "user_query": "What is...",
  "persona_id": "abc123"
}
```

## Duplicate Message Prevention

In voice mode, the same message can be received through multiple channels:

- `registerTextStreamHandler("lk.chat")`
- `DataReceived` event with topic `"lk.chat"`

To prevent duplicates, the `TranscriptionHandler` (voice mode) **skips** `lk.chat` and `lk.transcription` topics in the `DataReceived` handler, letting `TextStreamHandler` handle them exclusively.

```typescript
// In TranscriptionHandler.tsx DataReceived handler:
if (topic === "lk.transcription" || topic === "lk.chat") {
  // Skip - handled by registerTextStreamHandler
  return;
}
```

## Shared Utilities

### Constants

```typescript
import { LIVEKIT_TOPICS, isAgentTextTopic } from "@/lib/livekit";

// Use constants instead of magic strings
room.registerTextStreamHandler(LIVEKIT_TOPICS.CHAT, handler);

// Check topic type
if (isAgentTextTopic(topic)) {
  // Skip in DataReceived - handled by TextStreamHandler
  return;
}
```

### Text Stream Handler

```typescript
import { createTextStreamHandler, parseAgentMessage } from "@/lib/livekit";

// Create a handler with automatic parsing
const handler = createTextStreamHandler({
  onMessage: (message, identity) => {
    console.log(`${identity}: ${message.text}`);
  },
  debugLabel: "MyHandler",
});

room.registerTextStreamHandler("lk.chat", handler);
```

## Backend Integration

The backend agent (Python) sends messages using LiveKit's `send_text()`:

```python
# In livekit_agent_retrieval.py
await self.room.local_participant.send_text(
    text=json.dumps({"message": response, "is_final": True}),
    topic="lk.chat",
)
```

Citations are sent separately:

```python
await self.room.local_participant.publish_data(
    payload=json.dumps(citation_data).encode(),
    topic="citations",
)
```

## Debugging

Enable debug logging by checking the browser console in development mode. Look for these prefixes:

- `📨 [TextStream]` - Text stream handler receiving
- `🤖 [TextStream]` - Agent message content
- `📥 [DataReceived]` - Data received events
- `⏭️ [TranscriptionHandler]` - Skipped duplicate topics
- `📚 [Citations]` - Citation data received
- `✅ [TranscriptionReceived]` - Transcription segments

## Troubleshooting

### Duplicate Messages

If you see duplicate messages in voice chat:

1. Check that `TranscriptionHandler` is skipping `lk.chat` and `lk.transcription` in `DataReceived`
2. Verify only `registerTextStreamHandler("lk.chat")` is registered (not both `lk.chat` and `lk.transcription`)

### Messages Not Appearing

1. Check browser console for `📨 [TextStream]` logs
2. Verify the room is connected
3. Check the backend is sending on `lk.chat` topic
4. Ensure `registerTextStreamHandler` is registered

### Citations Not Appearing

1. Check for `📚 [Citations]` logs
2. Verify citations are sent on `citations` topic (not `lk.chat`)
3. Check `pendingCitations` state is being set
