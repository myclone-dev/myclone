"use client";

/**
 * TextChatHandler - LiveKit text chat message handler component
 *
 * This component handles real-time text chat communication with the backend agent
 * via LiveKit. It manages:
 * - Receiving agent text responses via TextStreamHandler (lk.chat topic)
 * - Receiving metadata (citations, document status, errors) via DataReceived
 * - Receiving transcription segments via TranscriptionReceived
 *
 * @see docs/LIVEKIT_ARCHITECTURE.md for detailed architecture documentation
 */

import { useEffect, useCallback, useRef } from "react";
import { useRoomContext } from "@livekit/components-react";
import { RoomEvent, Participant } from "livekit-client";
import type { MessageSource } from "@/types/expert";
import type {
  DocumentStatusMessage,
  TextLimitExceededMessage,
} from "@/lib/queries/expert/chat";
import {
  LIVEKIT_TOPICS,
  createTextStreamHandler,
  type CitationSource,
} from "@/lib/livekit";
import type {
  ContentOutputPayload,
  ContentOutputItem,
} from "@/types/contentOutput";
import type { AgentStatus } from "../chat/AgentStatusIndicator";

/**
 * Maps a source_type string to a MessageSource type category
 * @param sourceType - The raw source type string from the backend
 * @returns The categorized source type
 */
function mapSourceType(
  sourceType: string | undefined,
): "social_media" | "website" | "document" | "other" {
  if (!sourceType) return "other";
  const lowerType = sourceType.toLowerCase();
  if (
    lowerType.includes("twitter") ||
    lowerType.includes("linkedin") ||
    lowerType.includes("social")
  ) {
    return "social_media";
  }
  if (lowerType.includes("website") || lowerType.includes("url")) {
    return "website";
  }
  if (
    lowerType.includes("document") ||
    lowerType.includes("pdf") ||
    lowerType.includes("file")
  ) {
    return "document";
  }
  return "other";
}

/**
 * Convert citation sources to MessageSource format
 */
function citationsToMessageSources(
  citations: CitationSource[],
): MessageSource[] {
  return citations.map((c) => ({
    source: c.raw_source || c.source_type,
    title: c.title,
    content: c.content,
    source_url: c.source_url || "",
    type: mapSourceType(c.source_type),
    similarity: c.similarity,
  }));
}

/** Suggested questions message from agent */
interface SuggestedQuestionsMessage {
  type: "suggested_questions";
  questions: string[];
  persona_id: string;
}

/** Props for the TextChatHandler component */
interface TextChatHandlerProps {
  /**
   * Callback when an agent message is received
   * @param content - The message text content
   * @param isFinal - Whether this is the final/complete message
   * @param sources - Optional citation sources from RAG
   * @param calendarUrl - Optional calendar booking URL
   * @param contentOutput - Optional structured content output (blog, article, etc.)
   */
  onMessage: (
    content: string,
    isFinal: boolean,
    sources?: MessageSource[],
    calendarUrl?: string,
    contentOutput?: ContentOutputItem,
  ) => void;

  /** Callback when the agent finishes streaming a response */
  onStreamComplete: () => void;

  /** Optional callback for document processing status updates */
  onDocumentStatus?: (status: DocumentStatusMessage) => void;

  /** Optional callback when text limit is exceeded */
  onTextLimitExceeded?: (data: TextLimitExceededMessage) => void;

  /** Optional callback when suggested questions are received from agent */
  onSuggestedQuestions?: (questions: string[]) => void;

  /** Optional callback when structured content output is received from agent */
  onContentOutput?: (content: ContentOutputItem) => void;

  /** Optional callback when agent status changes (searching, fetching, generating, idle) */
  onAgentStatus?: (status: AgentStatus) => void;
}

/**
 * TextChatHandler Component
 *
 * A data-only React component that handles LiveKit text chat events.
 * Renders nothing - only manages event subscriptions and callbacks.
 *
 * @example
 * ```tsx
 * <TextChatHandler
 *   onMessage={(content, isFinal, sources) => {
 *     setMessages(prev => [...prev, { content, sources }]);
 *   }}
 *   onStreamComplete={() => setIsStreaming(false)}
 * />
 * ```
 */
export function TextChatHandler({
  onMessage,
  onStreamComplete,
  onDocumentStatus,
  onTextLimitExceeded,
  onSuggestedQuestions,
  onContentOutput,
  onAgentStatus,
}: TextChatHandlerProps) {
  const room = useRoomContext();

  // Use refs to avoid re-registration when these change
  const pendingCitationsRef = useRef<CitationSource[]>([]);
  const pendingCalendarUrlRef = useRef<string | null>(null);
  const pendingContentOutputRef = useRef<ContentOutputItem | null>(null);
  const accumulatedContentRef = useRef<string>("");
  const messageTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Stable refs for callbacks to avoid re-registration
  const onMessageRef = useRef(onMessage);
  const onStreamCompleteRef = useRef(onStreamComplete);
  const onDocumentStatusRef = useRef(onDocumentStatus);
  const onSuggestedQuestionsRef = useRef(onSuggestedQuestions);
  const onTextLimitExceededRef = useRef(onTextLimitExceeded);
  const onContentOutputRef = useRef(onContentOutput);
  const onAgentStatusRef = useRef(onAgentStatus);

  // Keep refs updated
  useEffect(() => {
    onMessageRef.current = onMessage;
    onStreamCompleteRef.current = onStreamComplete;
    onDocumentStatusRef.current = onDocumentStatus;
    onTextLimitExceededRef.current = onTextLimitExceeded;
    onSuggestedQuestionsRef.current = onSuggestedQuestions;
    onContentOutputRef.current = onContentOutput;
    onAgentStatusRef.current = onAgentStatus;
  }, [
    onMessage,
    onStreamComplete,
    onDocumentStatus,
    onTextLimitExceeded,
    onSuggestedQuestions,
    onContentOutput,
    onAgentStatus,
  ]);

  // Helper to finalize message after timeout (for backends that don't send is_final)
  const scheduleFinalization = useCallback((content: string) => {
    // Clear any existing timeout
    if (messageTimeoutRef.current) {
      clearTimeout(messageTimeoutRef.current);
    }

    // Set a timeout to finalize the message if no more data comes
    messageTimeoutRef.current = setTimeout(() => {
      if (process.env.NODE_ENV === "development") {
        console.log("🏁 [TextChat] Finalizing message after timeout");
      }
      // Read citations and calendar URL at finalization time (not when scheduled)
      const sources =
        pendingCitationsRef.current.length > 0
          ? citationsToMessageSources(pendingCitationsRef.current)
          : undefined;
      const calendarUrl = pendingCalendarUrlRef.current || undefined;

      if (process.env.NODE_ENV === "development" && sources) {
        console.log(
          "📚 [TextChat] Attaching",
          sources.length,
          "citations at finalization",
        );
      }

      if (process.env.NODE_ENV === "development" && calendarUrl) {
        console.log("📅 [TextChat] Attaching calendar URL at finalization");
      }

      const contentOutput = pendingContentOutputRef.current || undefined;

      onMessageRef.current(content, true, sources, calendarUrl, contentOutput);
      accumulatedContentRef.current = "";
      pendingCitationsRef.current = [];
      pendingCalendarUrlRef.current = null;
      pendingContentOutputRef.current = null;
      onStreamCompleteRef.current();
      messageTimeoutRef.current = null;
    }, 1500); // 1.5 second timeout
  }, []);

  // DataReceived handler for metadata and fallback messages
  const handleDataReceived = useCallback(
    (
      data: Uint8Array,
      _participant: Participant | undefined,
      _kind: unknown,
      topic?: string,
    ) => {
      try {
        const decoder = new TextDecoder();
        const textData = decoder.decode(data);

        // Handle citations
        if (topic === LIVEKIT_TOPICS.CITATIONS) {
          try {
            const citationData = JSON.parse(textData) as {
              type?: string;
              sources?: CitationSource[];
            };
            if (
              citationData.type === "voice_citations" ||
              citationData.sources
            ) {
              pendingCitationsRef.current = citationData.sources || [];
              if (process.env.NODE_ENV === "development") {
                console.log(
                  "📚 [TextChat] Received citations:",
                  pendingCitationsRef.current.length,
                );
              }
            }
          } catch {
            console.warn("Failed to parse citation data");
          }
          return;
        }

        // Handle calendar URL (plain text, NOT JSON!)
        if (topic === LIVEKIT_TOPICS.CALENDAR) {
          const calendarUrl = textData.trim();
          pendingCalendarUrlRef.current = calendarUrl;
          if (process.env.NODE_ENV === "development") {
            console.log("📅 [TextChat] Received calendar URL:", calendarUrl);
          }
          return;
        }

        // Handle document status updates from agent
        if (topic === LIVEKIT_TOPICS.DOCUMENT_STATUS) {
          try {
            const statusData = JSON.parse(textData) as DocumentStatusMessage;
            if (process.env.NODE_ENV === "development") {
              console.log(
                "📄 [TextChat] Received document status:",
                statusData,
              );
            }
            onDocumentStatusRef.current?.(statusData);
          } catch {
            console.warn("Failed to parse document status data");
          }
          return;
        }

        // Handle chat errors (text limit exceeded, etc.)
        if (topic === LIVEKIT_TOPICS.CHAT_ERROR) {
          try {
            const errorData = JSON.parse(textData) as { type?: string };
            if (errorData.type === "text_limit_exceeded") {
              if (process.env.NODE_ENV === "development") {
                console.log("⚠️ [TextChat] Text limit exceeded:", errorData);
              }
              onTextLimitExceededRef.current?.(
                errorData as TextLimitExceededMessage,
              );
            }
          } catch {
            console.warn("Failed to parse chat error data");
          }
          return;
        }

        // Handle suggested questions from agent
        if (topic === LIVEKIT_TOPICS.SUGGESTED_QUESTIONS) {
          try {
            const suggestedData = JSON.parse(
              textData,
            ) as SuggestedQuestionsMessage;
            if (
              suggestedData.type === "suggested_questions" &&
              suggestedData.questions
            ) {
              if (process.env.NODE_ENV === "development") {
                console.log(
                  "💡 [TextChat] Received suggested questions:",
                  suggestedData.questions.length,
                );
              }
              onSuggestedQuestionsRef.current?.(suggestedData.questions);
            }
          } catch {
            console.warn("Failed to parse suggested questions data");
          }
          return;
        }

        // Handle content output from agent (blog posts, articles, etc.)
        // Stored in ref and attached to the next finalized assistant message (same pattern as calendar URL)
        if (topic === LIVEKIT_TOPICS.CONTENT_OUTPUT) {
          try {
            const contentData = JSON.parse(textData) as ContentOutputPayload;
            if (
              contentData.type === "content_output" &&
              contentData.title &&
              contentData.body
            ) {
              if (process.env.NODE_ENV === "development") {
                console.log(
                  "📄 [TextChat] Received content output:",
                  contentData.title,
                );
              }
              const item: ContentOutputItem = {
                id: `content_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
                content_type: contentData.content_type,
                title: contentData.title,
                body: contentData.body,
                persona_name: contentData.persona_name,
                persona_role: contentData.persona_role,
                receivedAt: Date.now(),
              };
              pendingContentOutputRef.current = item;
              // Also fire callback immediately so parent can attach to the last expert message
              onContentOutputRef.current?.(item);
            }
          } catch {
            console.warn("Failed to parse content output data");
          }
          return;
        }

        // Handle agent status updates (searching, fetching, generating, idle)
        if (topic === LIVEKIT_TOPICS.AGENT_STATUS) {
          try {
            const statusData = JSON.parse(textData) as AgentStatus & {
              type?: string;
            };
            if (statusData.status) {
              onAgentStatusRef.current?.(statusData);
            }
          } catch {
            console.warn("Failed to parse agent status data");
          }
          return;
        }

        // Handle chat messages from agent on various topics
        // Note: lk.chat and lk.transcription are primarily handled by TextStreamHandler,
        // but DataReceived may also receive them for fallback/compatibility
        if (
          topic === LIVEKIT_TOPICS.CHAT ||
          topic === LIVEKIT_TOPICS.TRANSCRIPTION ||
          topic === LIVEKIT_TOPICS.LEGACY_CHAT ||
          topic === "" ||
          !topic
        ) {
          if (process.env.NODE_ENV === "development") {
            console.log(
              `📥 [LISTEN Topic: "${topic || "undefined"}"] DataReceived for chat`,
            );
          }
          try {
            const messageData = JSON.parse(textData) as {
              message?: string;
              is_final?: boolean;
              final?: boolean;
              type?: string;
              chunk?: string;
              sources?: CitationSource[];
            };

            // Handle different message formats from backend
            if (messageData.message !== undefined) {
              // Format: { message: "content" } or { message: "content", is_final: true }
              const content = messageData.message;
              const isFinal =
                messageData.is_final ?? messageData.final ?? false;

              // Accumulate content for streaming
              accumulatedContentRef.current = content;

              // Convert pending citations to MessageSource format
              const sources =
                pendingCitationsRef.current.length > 0
                  ? citationsToMessageSources(pendingCitationsRef.current)
                  : undefined;
              const calendarUrl = pendingCalendarUrlRef.current || undefined;

              if (process.env.NODE_ENV === "development") {
                console.log(
                  `🤖 [TextChat] Agent ${isFinal ? "FINAL" : "STREAMING"}:`,
                  content.substring(0, 100),
                );
              }

              const contentOutput = isFinal
                ? pendingContentOutputRef.current || undefined
                : undefined;

              onMessageRef.current(
                content,
                isFinal,
                sources,
                calendarUrl,
                contentOutput,
              );

              if (isFinal) {
                // Clear accumulated content, citations, calendar URL, and content output after final message
                accumulatedContentRef.current = "";
                pendingCitationsRef.current = [];
                pendingCalendarUrlRef.current = null;
                pendingContentOutputRef.current = null;
                onStreamCompleteRef.current();
                // Clear any pending timeout
                if (messageTimeoutRef.current) {
                  clearTimeout(messageTimeoutRef.current);
                  messageTimeoutRef.current = null;
                }
              } else {
                // Schedule finalization in case backend doesn't send is_final
                scheduleFinalization(content);
              }
            } else if (messageData.type === "content") {
              // SSE-style format: { type: "content", chunk: "..." }
              accumulatedContentRef.current += messageData.chunk || "";
              onMessageRef.current(accumulatedContentRef.current, false);
            } else if (messageData.type === "complete") {
              // SSE-style format: { type: "complete" }
              const sources =
                pendingCitationsRef.current.length > 0
                  ? citationsToMessageSources(pendingCitationsRef.current)
                  : undefined;
              const calendarUrl = pendingCalendarUrlRef.current || undefined;
              const contentOutput =
                pendingContentOutputRef.current || undefined;

              onMessageRef.current(
                accumulatedContentRef.current,
                true,
                sources,
                calendarUrl,
                contentOutput,
              );
              accumulatedContentRef.current = "";
              pendingCitationsRef.current = [];
              pendingCalendarUrlRef.current = null;
              pendingContentOutputRef.current = null;
              onStreamCompleteRef.current();
            } else if (messageData.type === "sources" && messageData.sources) {
              // SSE-style format: { type: "sources", sources: [...] }
              pendingCitationsRef.current = messageData.sources;
            } else if (typeof messageData === "string") {
              // Plain text message
              accumulatedContentRef.current = messageData;
              onMessageRef.current(messageData, true);
              onStreamCompleteRef.current();
            }
          } catch {
            // If not JSON, treat as plain text
            const content = textData;
            if (content.trim()) {
              if (process.env.NODE_ENV === "development") {
                console.log(
                  "🤖 [TextChat] Agent (plain text):",
                  content.substring(0, 100),
                );
              }
              onMessageRef.current(content, true);
              onStreamCompleteRef.current();
            }
          }
        }

        // Also check for voice_citations in raw data (fallback)
        if (textData.includes("voice_citations")) {
          try {
            const citationData = JSON.parse(textData) as {
              type?: string;
              sources?: CitationSource[];
            };
            if (citationData.type === "voice_citations") {
              pendingCitationsRef.current = citationData.sources || [];
            }
          } catch {
            // Not valid JSON, ignore
          }
        }
      } catch (error) {
        console.error("❌ [TextChat] Error processing data:", error);
      }
    },
    [scheduleFinalization],
  );

  // Main effect for registering handlers
  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      console.log(
        "🔌 [TextChatHandler] Room state:",
        room?.state,
        "Room:",
        !!room,
      );
      console.log(
        "📋 [TextChatHandler] Architecture:",
        "\n  • Input:  Client sendText('lk.chat') → Agent",
        "\n  • Output: Agent sendText('lk.chat' or 'lk.transcription' or '') → TextStreamHandler",
        "\n  • Listening for topics: lk.chat, lk.transcription, chat, '' (empty), undefined",
      );
    }

    if (!room) return;

    if (process.env.NODE_ENV === "development") {
      console.log("🎧 [TextChatHandler] Attaching DataReceived listener");
      console.log("📝 [TextChatHandler] Registering text stream handlers");
    }

    // =========================================================================
    // TEXT STREAM HANDLER - Uses shared utility from @/lib/livekit
    // =========================================================================
    const textStreamHandler = createTextStreamHandler({
      debugLabel: "TextChatHandler",
      onMessage: (parsedMessage, _participantIdentity) => {
        const content = parsedMessage.text;
        const isFinal = parsedMessage.isFinal;

        // Get citations and calendar URL if available
        const sources =
          isFinal && pendingCitationsRef.current.length > 0
            ? citationsToMessageSources(pendingCitationsRef.current)
            : undefined;
        const calendarUrl =
          isFinal && pendingCalendarUrlRef.current
            ? pendingCalendarUrlRef.current
            : undefined;
        const contentOutput =
          isFinal && pendingContentOutputRef.current
            ? pendingContentOutputRef.current
            : undefined;

        onMessageRef.current(
          content,
          isFinal,
          sources,
          calendarUrl,
          contentOutput,
        );

        if (isFinal) {
          accumulatedContentRef.current = "";
          pendingCitationsRef.current = [];
          pendingCalendarUrlRef.current = null;
          pendingContentOutputRef.current = null;
          onStreamCompleteRef.current();
        }
      },
      onError: (error) => {
        console.error("❌ [TextStream] Error reading stream:", error);
      },
    });

    // Register handlers for different topics agent might use
    room.registerTextStreamHandler(LIVEKIT_TOPICS.CHAT, textStreamHandler);
    room.registerTextStreamHandler(
      LIVEKIT_TOPICS.TRANSCRIPTION,
      textStreamHandler,
    );

    if (process.env.NODE_ENV === "development") {
      console.log(
        "✅ [TextChatHandler] Text stream handlers registered for:",
        LIVEKIT_TOPICS.CHAT,
        LIVEKIT_TOPICS.TRANSCRIPTION,
      );
    }

    room.on(RoomEvent.DataReceived, handleDataReceived);

    return () => {
      if (process.env.NODE_ENV === "development") {
        console.log("🔇 [TextChatHandler] Removing DataReceived listener");
        console.log("🔇 [TextChatHandler] Unregistering text stream handlers");
      }
      room.off(RoomEvent.DataReceived, handleDataReceived);
      room.unregisterTextStreamHandler(LIVEKIT_TOPICS.CHAT);
      room.unregisterTextStreamHandler(LIVEKIT_TOPICS.TRANSCRIPTION);
      // Clear timeout on unmount
      if (messageTimeoutRef.current) {
        clearTimeout(messageTimeoutRef.current);
      }
    };
  }, [room, handleDataReceived]);

  // Handle TranscriptionReceived events (like voice agent)
  useEffect(() => {
    if (!room) return;

    const handleTranscriptionReceived = (
      segments: Array<{
        id: string;
        text: string;
        final?: boolean;
      }>,
      participant?: Participant,
    ) => {
      // Only process assistant (non-local) transcriptions
      if (participant?.isLocal) return;

      segments.forEach((segment) => {
        const isFinal = segment.final ?? false;
        const content = segment.text;

        if (process.env.NODE_ENV === "development") {
          console.log(
            `📥 [LISTEN Event: TranscriptionReceived] ${isFinal ? "FINAL" : "STREAMING"}:`,
            content.substring(0, 50),
          );
        }

        // Convert pending citations, calendar URL, and content output to message format
        const sources =
          isFinal && pendingCitationsRef.current.length > 0
            ? citationsToMessageSources(pendingCitationsRef.current)
            : undefined;
        const calendarUrl =
          isFinal && pendingCalendarUrlRef.current
            ? pendingCalendarUrlRef.current
            : undefined;
        const contentOutput =
          isFinal && pendingContentOutputRef.current
            ? pendingContentOutputRef.current
            : undefined;

        onMessageRef.current(
          content,
          isFinal,
          sources,
          calendarUrl,
          contentOutput,
        );

        if (isFinal) {
          accumulatedContentRef.current = "";
          pendingCitationsRef.current = [];
          pendingCalendarUrlRef.current = null;
          pendingContentOutputRef.current = null;
          onStreamCompleteRef.current();
        }
      });
    };

    if (process.env.NODE_ENV === "development") {
      console.log(
        "🎧 [TextChatHandler] Attaching TranscriptionReceived listener",
      );
    }

    room.on(RoomEvent.TranscriptionReceived, handleTranscriptionReceived);

    return () => {
      if (process.env.NODE_ENV === "development") {
        console.log(
          "🔇 [TextChatHandler] Removing TranscriptionReceived listener",
        );
      }
      room.off(RoomEvent.TranscriptionReceived, handleTranscriptionReceived);
    };
  }, [room]);

  return null; // This is a data-only component
}
