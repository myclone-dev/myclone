# Inactivity Timeout for Text Chat Sessions

## Overview

This document describes the inactivity timeout feature implemented for text chat sessions to prevent unnecessary LiveKit billing from idle connections.

## Problem Statement

When users open the text chat, a LiveKit connection is automatically established. If users:

- Leave the chat tab open in the background
- Switch to other browser tabs
- Become inactive without explicitly closing the chat

The LiveKit session remains active, accumulating usage costs even though no actual conversation is happening.

## Solution

Implement a client-side inactivity timeout system that:

1. Monitors user activity
2. Shows a warning after 60 seconds of inactivity
3. Automatically disconnects after an additional 30 seconds if no response
4. Allows manual session ending via a dedicated button
5. Provides clear UI feedback for all states
6. Enables easy reconnection while preserving message history

## Architecture

### State Flow Diagram

```
                                    ┌─────────────────┐
                                    │   DISCONNECTED  │
                                    │  (Initial/Error)│
                                    └────────┬────────┘
                                             │
                                             │ Auto-connect on mount
                                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                            CONNECTED                                  │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    Activity Monitoring                           │ │
│  │                                                                  │ │
│  │   User Actions (reset timer):                                    │ │
│  │   • Typing in input                                              │ │
│  │   • Sending message                                              │ │
│  │   • Clicking in chat area                                        │ │
│  │   • Uploading attachment                                         │ │
│  │   • Clicking suggested questions                                 │ │
│  │   • Pressing any key                                             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
└───────────────────────────┬───────────────────────────────┬──────────┘
                            │                               │
                            │ 60s inactivity                │ User clicks
                            │                               │ "End Session"
                            ▼                               │
              ┌─────────────────────────┐                   │
              │    WARNING_SHOWN        │                   │
              │                         │                   │
              │  "Are you still there?" │                   │
              │  Countdown: 30s → 0s    │                   │
              │                         │                   │
              │  [I'm still here]       │                   │
              └───────────┬─────────────┘                   │
                          │                                 │
         ┌────────────────┼────────────────┐                │
         │                │                │                │
         │ User activity  │ Countdown = 0  │                │
         │                │                │                │
         ▼                ▼                │                │
    CONNECTED     ┌──────────────────┐     │                │
    (reset)       │  DISCONNECTED    │◄────┴────────────────┘
                  │  (Inactivity)    │
                  │                  │
                  │  "Session        │
                  │   Disconnected"  │
                  │                  │
                  │  [Reconnect]     │
                  └────────┬─────────┘
                           │
                           │ User clicks "Reconnect"
                           ▼
                      CONNECTING
                           │
                           ▼
                      CONNECTED
```

### Component Hierarchy

```
ExpertTextChat
├── RoomContext.Provider
│   └── TooltipProvider
│       │
│       ├── TextChatHandler (handles LiveKit data events)
│       │
│       └── Chat Container (onClick={recordActivity}, onKeyDown={recordActivity})
│           │
│           ├── EndSessionButton ────────────────────────────┐
│           │   (Position: absolute top-3 right-3)           │
│           │   (Shows when connected, not disconnected)     │
│           │                                                │
│           ├── InactivityWarning ◄──────────────────────────┤
│           │   (Overlay with countdown timer)               │
│           │   (z-index: 50)                                │
│           │                                                │
│           ├── SessionDisconnected ◄────────────────────────┘
│           │   (Full overlay when disconnected)
│           │   (z-index: 50)
│           │
│           ├── Connection Status Overlay
│           │   (Shows during initial connection)
│           │
│           ├── TextLimitExceeded (existing)
│           │
│           ├── Error Banner (existing)
│           │
│           ├── Email Prompt (existing)
│           │
│           ├── Conversation
│           │   └── Messages...
│           │
│           └── ChatInput
│               (onChange includes recordActivity)
```

## Files Created/Modified

### New Files

| File                                                 | Purpose                                                   |
| ---------------------------------------------------- | --------------------------------------------------------- |
| `src/hooks/useInactivityTimeout.ts`                  | Core hook for inactivity detection and timeout management |
| `src/components/expert/chat/InactivityWarning.tsx`   | Warning overlay with countdown timer                      |
| `src/components/expert/chat/SessionDisconnected.tsx` | Disconnection overlay with reconnect option               |
| `src/components/expert/chat/EndSessionButton.tsx`    | Manual session end button with confirmation               |

### Modified Files

| File                                            | Changes                                                              |
| ----------------------------------------------- | -------------------------------------------------------------------- |
| `src/components/expert/text/ExpertTextChat.tsx` | Integrated inactivity timeout, added overlays and end session button |
| `src/lib/monitoring/sentry.ts`                  | Added new event types for inactivity tracking                        |

## Configuration

### Timeout Values

Defined as constants in `ExpertTextChat.tsx`:

```typescript
const INACTIVITY_TIMEOUT_MS = 60000; // 1 minute - time before showing warning
const WARNING_COUNTDOWN_MS = 30000; // 30 seconds - warning countdown duration
```

### Sentry Events

New events tracked for monitoring:

| Event                             | Trigger                       | Data                        |
| --------------------------------- | ----------------------------- | --------------------------- |
| `inactivity_warning_shown`        | Warning overlay appears       | username, personaName, mode |
| `inactivity_warning_dismissed`    | User dismisses warning        | remainingSeconds            |
| `session_disconnected_inactivity` | Auto-disconnect after timeout | username, personaName, mode |
| `session_ended_manual`            | User clicks "End Session"     | username, personaName, mode |
| `session_reconnect_attempt`       | User clicks "Reconnect"       | previousReason              |
| `session_reconnect_success`       | Reconnection successful       | username, personaName       |

## Usage

### useInactivityTimeout Hook

```typescript
import { useInactivityTimeout } from "@/hooks/useInactivityTimeout";

const {
  showWarning, // boolean - whether to show warning UI
  remainingSeconds, // number - countdown seconds remaining
  dismissWarning, // () => void - call when user dismisses
  recordActivity, // () => void - call on any user activity
  isDisconnectedDueToInactivity, // boolean
  resetInactivityState, // () => void - call before reconnecting
} = useInactivityTimeout({
  inactivityMs: 60000, // Time before warning (default: 60s)
  warningMs: 30000, // Warning duration (default: 30s)
  onDisconnect: handleDisconnect, // Called when timeout expires
  enabled: isConnected, // Only active when connected
  trackingContext: {
    // For Sentry tracking
    username,
    personaName,
    mode: "text",
  },
});
```

### Activity Recording

Activities that reset the inactivity timer:

```typescript
// Automatically tracked via onClick/onKeyDown on container
<div onClick={recordActivity} onKeyDown={recordActivity}>

// Manually tracked in handlers
const handleInputChange = (value: string) => {
  setInputMessage(value);
  recordActivity(); // User is typing
};

const handleSendMessage = async () => {
  recordActivity(); // User sent a message
  // ... send logic
};

const handleAttachmentUploaded = (attachment) => {
  recordActivity(); // User uploaded file
  // ... upload logic
};
```

## UI Components

### InactivityWarning

Centered modal overlay with:

- Pulsing clock icon
- "Are you still there?" heading
- Large countdown number (30, 29, 28...)
- "I'm still here" button
- Hint text about clicking anywhere to dismiss
- Keyboard event listener (any key dismisses)

### SessionDisconnected

Full overlay with:

- Icon based on disconnect reason (inactivity/manual/error)
- Appropriate title and description
- "Reconnect" button with loading state
- "Messages saved" indicator

### EndSessionButton

Small icon button (power icon) with:

- Tooltip on hover: "End session"
- Confirmation dialog before disconnect
- Positioned top-right of chat container

## Responsive Design

All components are responsive:

| Component           | Mobile                               | Desktop                             |
| ------------------- | ------------------------------------ | ----------------------------------- |
| InactivityWarning   | Smaller padding (p-4), smaller fonts | Regular padding (p-8), normal fonts |
| SessionDisconnected | Full width with margins              | Centered with max-width             |
| EndSessionButton    | 32x32px touch target                 | Same, with hover tooltip            |

## Testing Considerations

### Manual Testing Checklist

1. **Inactivity Flow**
   - [ ] Open text chat, wait 60s → Warning appears
   - [ ] Wait another 30s → Auto-disconnect
   - [ ] Verify messages are preserved
   - [ ] Click Reconnect → Connection restored

2. **Activity Reset**
   - [ ] Type in input → Timer resets
   - [ ] Send message → Timer resets
   - [ ] Click in chat area → Timer resets
   - [ ] During warning, click "I'm still here" → Warning dismisses

3. **Manual End Session**
   - [ ] Click end session button → Confirmation appears
   - [ ] Confirm → Session ends
   - [ ] Messages preserved
   - [ ] Can reconnect

4. **Edge Cases**
   - [ ] Warning showing + page visibility change
   - [ ] Warning showing + user sends message
   - [ ] Multiple rapid activity events
   - [ ] Reconnect during streaming response

### Sentry Monitoring

After deployment, monitor these metrics:

- `inactivity_warning_shown` count vs `session_disconnected_inactivity` count
- Average `remainingSeconds` when warning is dismissed
- `session_reconnect_attempt` success rate

## Future Considerations

### Voice Chat

The same inactivity pattern could be applied to voice chat, though it's less critical because:

- Voice requires explicit user action to start
- Voice has heartbeat tracking for billing
- Voice activity (speaking) is inherently "active"

### Configurable Timeouts

Consider making timeout values configurable per-persona or via widget config:

```typescript
interface PersonaConfig {
  inactivityTimeoutMs?: number;
  warningDurationMs?: number;
  enableInactivityTimeout?: boolean;
}
```

### Backend Notification

Optionally notify the backend when sessions end due to inactivity for analytics:

```typescript
await api.post("/sessions/inactivity-disconnect", {
  sessionToken,
  reason: "inactivity",
  lastActivityTimestamp,
});
```

## Changelog

### v1.0.1 (Timer Fix)

- Fixed timer not working due to stale closures in useCallback dependencies
- Consolidated all config values into a single `configRef` to avoid recreating callbacks
- Removed circular dependency between `startInactivityTimer` and `recordActivity`
- Timer now properly resets on each user activity

### v1.0.0 (Initial Implementation)

- Added `useInactivityTimeout` hook
- Added `InactivityWarning` component
- Added `SessionDisconnected` component
- Added `EndSessionButton` component
- Integrated into `ExpertTextChat`
- Added Sentry tracking for all inactivity events
- Documentation created
