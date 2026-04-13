"use client";

/**
 * TranscriptionHandler - LiveKit voice chat transcription handler component
 *
 * This component handles real-time voice chat communication with the backend agent
 * via LiveKit. It manages:
 * - Receiving agent text responses via TextStreamHandler (lk.chat topic only)
 * - Receiving metadata (citations, calendar URLs) via DataReceived
 * - Receiving user and agent transcription segments via TranscriptionReceived
 *
 * **Important:** To prevent duplicate messages, this handler:
 * - Only registers TextStreamHandler for "lk.chat" (not "lk.transcription")
 * - Skips "lk.chat" and "lk.transcription" in DataReceived handler
 *
 * @see docs/LIVEKIT_ARCHITECTURE.md for detailed architecture documentation
 */

import { useEffect, useRef, useCallback } from "react";
import { useRoomContext } from "@livekit/components-react";
import { RoomEvent, Participant } from "livekit-client";
import {
  LIVEKIT_TOPICS,
  isAgentTextTopic,
  createTextStreamHandler,
  formatCitations,
  type CitationSource,
  type FormattedCitation,
} from "@/lib/livekit";
import type {
  ContentOutputPayload,
  ContentOutputItem,
} from "@/types/contentOutput";
import type { AgentStatus } from "../chat/AgentStatusIndicator";

interface VoiceCitationData {
  type: "voice_citations" | "citations";
  sources: CitationSource[];
  user_query?: string;
  query?: string; // Backend may send "query" instead of "user_query"
  rewritten_query?: string;
  persona_id?: string;
  timestamp?: string;
  agent_name?: string;
}

interface TranscriptAttachment {
  id: string;
  filename: string;
  fileType: string;
  fileSize: number;
  extractionStatus?: string;
}

/** A single message in the voice chat transcript */
interface TranscriptMessage {
  id: string;
  text: string;
  speaker: "user" | "assistant";
  timestamp: number;
  isComplete: boolean;
  calendarUrl?: string;
  citations?: FormattedCitation[];
  attachments?: TranscriptAttachment[];
  contentOutput?: ContentOutputItem;
}

/** Props for the TranscriptionHandler component */
interface TranscriptionHandlerProps {
  /** State setter for the transcript messages array */
  setTranscriptMessages: React.Dispatch<
    React.SetStateAction<TranscriptMessage[]>
  >;
  /** Optional callback when structured content output is received from agent */
  onContentOutput?: (content: ContentOutputItem) => void;

  /** Optional callback when agent status changes (searching, fetching, generating, idle) */
  onAgentStatus?: (status: AgentStatus) => void;
}

/**
 * Type guard to validate citation data from backend
 * Accepts both "voice_citations" and "citations" types, or any object with valid sources array
 */
function isValidCitationData(data: unknown): data is VoiceCitationData {
  if (!data || typeof data !== "object") return false;

  const citationData = data as Partial<VoiceCitationData>;

  // Must have a sources array with at least one item
  if (
    !Array.isArray(citationData.sources) ||
    citationData.sources.length === 0
  ) {
    return false;
  }

  // Accept known types, or any data with valid sources (for forward compatibility)
  const hasValidType =
    citationData.type === "voice_citations" ||
    citationData.type === "citations";

  return hasValidType || citationData.sources.length > 0;
}

/**
 * TranscriptionHandler Component
 *
 * A data-only React component that handles LiveKit voice chat events.
 * Renders nothing - only manages event subscriptions and state updates.
 *
 * Handles three types of LiveKit events:
 * 1. TextStreamHandler (lk.chat) - Agent text responses
 * 2. DataReceived - Citations, calendar URLs, and other metadata
 * 3. TranscriptionReceived - Real-time speech transcription segments
 *
 * @example
 * ```tsx
 * const [messages, setMessages] = useState<TranscriptMessage[]>([]);
 *
 * <TranscriptionHandler setTranscriptMessages={setMessages} />
 * ```
 */
export function TranscriptionHandler({
  setTranscriptMessages,
  onContentOutput,
  onAgentStatus,
}: TranscriptionHandlerProps) {
  const room = useRoomContext();
  const segmentsRef = useRef<Map<string, TranscriptMessage>>(new Map());

  // Use refs instead of state to avoid re-registration of handlers
  const pendingCitationsRef = useRef<CitationSource[]>([]);
  const pendingCalendarUrlRef = useRef<string | null>(null);
  const pendingContentOutputRef = useRef<ContentOutputItem | null>(null);
  const onContentOutputRef = useRef(onContentOutput);
  const onAgentStatusRef = useRef(onAgentStatus);

  useEffect(() => {
    onContentOutputRef.current = onContentOutput;
    onAgentStatusRef.current = onAgentStatus;
  }, [onContentOutput, onAgentStatus]);

  // Handle citation data from LiveKit
  const handleCitationData = useCallback((citationData: VoiceCitationData) => {
    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.log(
        "📚 [Citations] Received:",
        citationData.sources.length,
        "sources",
      );
    }
    pendingCitationsRef.current = citationData.sources;
  }, []);

  // Register text stream and data handlers
  useEffect(() => {
    if (!room) return;

    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.log("📝 [TranscriptionHandler] Registering text stream handlers");
    }

    // =========================================================================
    // TEXT STREAM HANDLER - Uses shared utility from @/lib/livekit
    // =========================================================================
    const textStreamHandler = createTextStreamHandler({
      debugLabel: "TranscriptionHandler",
      onMessage: (parsedMessage, _participantIdentity) => {
        if (!parsedMessage.text.trim()) return;

        // Get pending citations, calendar URL, and content output
        const citations =
          pendingCitationsRef.current.length > 0
            ? formatCitations(pendingCitationsRef.current)
            : undefined;
        const calendarUrl = pendingCalendarUrlRef.current || undefined;
        const contentOutput = pendingContentOutputRef.current || undefined;

        const transcriptMessage: TranscriptMessage = {
          id: `textstream_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
          text: parsedMessage.text.trim(),
          speaker: "assistant",
          timestamp: Date.now(),
          isComplete: parsedMessage.isFinal,
          citations,
          calendarUrl,
          contentOutput,
        };

        setTranscriptMessages((prev) => {
          const updated = [...prev, transcriptMessage].sort(
            (a, b) => a.timestamp - b.timestamp,
          );

          if (process.env.NODE_ENV === "development") {
            // eslint-disable-next-line no-console
            console.log("✅ [TranscriptionHandler TextStream] Added message:", {
              messageLength: parsedMessage.text.length,
              citations: pendingCitationsRef.current.length,
              totalMessages: updated.length,
            });
          }

          return updated;
        });

        // Clear pending data after use
        if (pendingCitationsRef.current.length > 0) {
          pendingCitationsRef.current = [];
        }
        if (pendingCalendarUrlRef.current) {
          pendingCalendarUrlRef.current = null;
        }
        if (pendingContentOutputRef.current) {
          pendingContentOutputRef.current = null;
        }
      },
      onError: (error) => {
        console.error("❌ [TranscriptionHandler TextStream] Error:", error);
      },
    });

    // Register handler for lk.chat topic only
    // Do NOT register lk.transcription here - that's handled by TranscriptionReceived event
    room.registerTextStreamHandler(LIVEKIT_TOPICS.CHAT, textStreamHandler);

    if (process.env.NODE_ENV === "development") {
      // eslint-disable-next-line no-console
      console.log(
        "✅ [TranscriptionHandler] Text stream handler registered for:",
        LIVEKIT_TOPICS.CHAT,
      );
    }

    // =========================================================================
    // DATA RECEIVED HANDLER - For metadata (citations, calendar, etc.)
    // =========================================================================
    const handleDataReceived = (
      data: Uint8Array,
      _participant: Participant | undefined,
      _kind: unknown,
      topic?: string,
    ) => {
      try {
        const decoder = new TextDecoder();

        // Handle calendar URL (plain text, NOT JSON!)
        if (topic === LIVEKIT_TOPICS.CALENDAR) {
          const calendarUrl = decoder.decode(data);
          pendingCalendarUrlRef.current = calendarUrl;
          return;
        }

        // Handle agent status updates (searching, fetching, generating, idle)
        if (topic === LIVEKIT_TOPICS.AGENT_STATUS) {
          const textData = decoder.decode(data);
          try {
            const statusData = JSON.parse(textData) as AgentStatus & {
              type?: string;
            };
            if (statusData.status) {
              onAgentStatusRef.current?.(statusData);
            }
          } catch {
            console.warn(
              "[TranscriptionHandler] Failed to parse agent status data",
            );
          }
          return;
        }

        // Handle content output from agent (blog posts, articles, etc.)
        // Stored in ref and attached to the next finalized assistant message (same pattern as calendar URL)
        if (topic === LIVEKIT_TOPICS.CONTENT_OUTPUT) {
          const textData = decoder.decode(data);
          try {
            const contentData = JSON.parse(textData) as ContentOutputPayload;
            if (
              contentData.type === "content_output" &&
              contentData.title &&
              contentData.body
            ) {
              if (process.env.NODE_ENV === "development") {
                // eslint-disable-next-line no-console
                console.log(
                  "📄 [TranscriptionHandler] Received content output:",
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
              // Also fire callback immediately so parent can attach to the last assistant message
              onContentOutputRef.current?.(item);
            }
          } catch {
            console.warn(
              "[TranscriptionHandler] Failed to parse content output",
            );
          }
          return;
        }

        // Skip agent text topics - they are handled by TextStreamHandler
        if (isAgentTextTopic(topic)) {
          if (process.env.NODE_ENV === "development") {
            // eslint-disable-next-line no-console
            console.log(
              `⏭️ [TranscriptionHandler] Skipping DataReceived for "${topic}" (handled by TextStreamHandler)`,
            );
          }
          return;
        }

        // Handle empty string topic '' (default when agent doesn't specify topic)
        if (topic === "") {
          const textData = decoder.decode(data);

          if (process.env.NODE_ENV === "development") {
            // eslint-disable-next-line no-console
            console.log(
              `📥 [TranscriptionHandler] Text from agent on empty topic:`,
              textData.substring(0, 100),
            );
          }

          // Try to parse as JSON first
          try {
            const messageData = JSON.parse(textData) as {
              message?: string;
              is_final?: boolean;
              final?: boolean;
            };
            if (messageData.message !== undefined) {
              const text = messageData.message;
              if (text.trim()) {
                const citations =
                  pendingCitationsRef.current.length > 0
                    ? formatCitations(pendingCitationsRef.current)
                    : undefined;

                const transcriptMessage: TranscriptMessage = {
                  id: `agent_text_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
                  text,
                  speaker: "assistant",
                  timestamp: Date.now(),
                  isComplete: messageData.is_final ?? messageData.final ?? true,
                  citations,
                  calendarUrl: pendingCalendarUrlRef.current || undefined,
                  contentOutput: pendingContentOutputRef.current || undefined,
                };

                setTranscriptMessages((prev) => {
                  const updated = [...prev, transcriptMessage].sort(
                    (a, b) => a.timestamp - b.timestamp,
                  );
                  return updated;
                });

                // Clear pending data
                if (pendingCitationsRef.current.length > 0) {
                  pendingCitationsRef.current = [];
                }
                if (pendingCalendarUrlRef.current) {
                  pendingCalendarUrlRef.current = null;
                }
                if (pendingContentOutputRef.current) {
                  pendingContentOutputRef.current = null;
                }
              }
              return;
            }
          } catch {
            // Not JSON, treat as plain text
          }

          // Handle plain text response from agent
          if (textData.trim()) {
            const citations =
              pendingCitationsRef.current.length > 0
                ? formatCitations(pendingCitationsRef.current)
                : undefined;

            const transcriptMessage: TranscriptMessage = {
              id: `agent_text_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`,
              text: textData.trim(),
              speaker: "assistant",
              timestamp: Date.now(),
              isComplete: true,
              citations,
              calendarUrl: pendingCalendarUrlRef.current || undefined,
              contentOutput: pendingContentOutputRef.current || undefined,
            };

            setTranscriptMessages((prev) => {
              const updated = [...prev, transcriptMessage].sort(
                (a, b) => a.timestamp - b.timestamp,
              );

              if (process.env.NODE_ENV === "development") {
                // eslint-disable-next-line no-console
                console.log(
                  "✅ [TranscriptionHandler] Added agent text message:",
                  {
                    messageLength: textData.length,
                    citations: pendingCitationsRef.current.length,
                    totalMessages: updated.length,
                  },
                );
              }

              return updated;
            });

            // Clear pending data
            if (pendingCitationsRef.current.length > 0) {
              pendingCitationsRef.current = [];
            }
            if (pendingCalendarUrlRef.current) {
              pendingCalendarUrlRef.current = null;
            }
            if (pendingContentOutputRef.current) {
              pendingContentOutputRef.current = null;
            }
          }
          return;
        }

        // Handle citations (JSON)
        if (topic === LIVEKIT_TOPICS.CITATIONS) {
          const textData = decoder.decode(data);
          const citationData = JSON.parse(textData);

          if (isValidCitationData(citationData)) {
            handleCitationData(citationData);
          } else {
            console.warn(
              "⚠️ Invalid citation data - missing sources array or invalid type:",
              citationData,
            );
          }
        } else {
          // Check if it's actually citation data without proper topic
          try {
            const decoded = decoder.decode(data);
            const parsedData = JSON.parse(decoded);

            // Use type guard to validate - no string matching needed
            if (isValidCitationData(parsedData)) {
              handleCitationData(parsedData);
            }
          } catch {
            // Not valid JSON or not citation data, ignore
          }
        }
      } catch (error) {
        console.error("❌ Error parsing LiveKit data:", error);
      }
    };

    room.on(RoomEvent.DataReceived, handleDataReceived);

    return () => {
      room.off(RoomEvent.DataReceived, handleDataReceived);
      room.unregisterTextStreamHandler(LIVEKIT_TOPICS.CHAT);

      if (process.env.NODE_ENV === "development") {
        // eslint-disable-next-line no-console
        console.log(
          "🔇 [TranscriptionHandler] Unregistered text stream handler:",
          LIVEKIT_TOPICS.CHAT,
        );
      }
    };
  }, [room, handleCitationData, setTranscriptMessages]);

  // Handle transcription events (real-time speech-to-text)
  useEffect(() => {
    if (!room) return;

    const handleTranscriptionReceived = (
      segments: Array<{
        id: string;
        text: string;
        final?: boolean;
        firstReceivedTime?: number;
      }>,
      participant?: Participant,
    ) => {
      let hasChanges = false;

      segments.forEach((segment) => {
        // Use participant.isLocal to detect speaker
        const speaker = participant?.isLocal ? "user" : "assistant";

        // Check if this is a new segment or text has changed
        const existing = segmentsRef.current.get(segment.id);

        // Compare trimmed text to ignore trailing whitespace changes
        const trimmedOldText = existing?.text.trim() || "";
        const trimmedNewText = segment.text.trim();
        const meaningfulTextChange = trimmedOldText !== trimmedNewText;
        const finalChanged = existing?.isComplete !== (segment.final ?? false);

        // Attach pending citations to assistant messages
        const citations: FormattedCitation[] =
          speaker === "assistant" && pendingCitationsRef.current.length > 0
            ? formatCitations(pendingCitationsRef.current)
            : (existing?.citations ?? []);

        // Attach pending calendar URL to assistant messages
        const calendarUrl =
          speaker === "assistant" && pendingCalendarUrlRef.current
            ? pendingCalendarUrlRef.current
            : existing?.calendarUrl;

        // Attach pending content output to assistant messages
        const contentOutput =
          speaker === "assistant" && pendingContentOutputRef.current
            ? pendingContentOutputRef.current
            : existing?.contentOutput;

        const message: TranscriptMessage = {
          id: segment.id || Date.now().toString(),
          text: segment.text,
          speaker,
          timestamp: segment.firstReceivedTime || Date.now(),
          isComplete: segment.final ?? false,
          calendarUrl,
          citations,
          contentOutput,
        };

        // Only update if: new segment, meaningful text change, or finalized
        if (!existing || meaningfulTextChange || finalChanged) {
          if (process.env.NODE_ENV === "development") {
            if (!existing) {
              // eslint-disable-next-line no-console
              console.log(
                `${participant?.isLocal ? "👤" : "🤖"} [${speaker.toUpperCase()}] NEW:`,
                {
                  id: segment.id,
                  text: message.text.substring(0, 50),
                  isLocal: participant?.isLocal,
                  citations: citations.length,
                },
              );
            } else if (meaningfulTextChange) {
              // eslint-disable-next-line no-console
              console.log(
                `${participant?.isLocal ? "👤" : "🤖"} [${speaker.toUpperCase()}] TEXT CHANGE:`,
                {
                  id: segment.id,
                  oldText: trimmedOldText.substring(0, 50),
                  newText: trimmedNewText.substring(0, 50),
                  isLocal: participant?.isLocal,
                },
              );
            } else if (finalChanged) {
              // eslint-disable-next-line no-console
              console.log(
                `${participant?.isLocal ? "👤" : "🤖"} [${speaker.toUpperCase()}] FINALIZED:`,
                {
                  id: segment.id,
                  text: message.text.substring(0, 50),
                  isLocal: participant?.isLocal,
                },
              );
            }
          }

          segmentsRef.current.set(message.id, message);
          hasChanges = true;

          // Clear pending citations after attaching to assistant message
          if (
            speaker === "assistant" &&
            pendingCitationsRef.current.length > 0
          ) {
            pendingCitationsRef.current = [];
          }

          // Clear pending calendar URL after attaching to assistant message
          if (speaker === "assistant" && pendingCalendarUrlRef.current) {
            pendingCalendarUrlRef.current = null;
          }

          // Clear pending content output after attaching to assistant message
          if (speaker === "assistant" && pendingContentOutputRef.current) {
            pendingContentOutputRef.current = null;
          }
        }
      });

      // Only update state if there were actual changes
      if (hasChanges) {
        const transcriptionMessages = Array.from(
          segmentsRef.current.values(),
        ).sort((a, b) => a.timestamp - b.timestamp);

        // Merge with existing messages, preserving manually added ones (uploads, etc.)
        setTranscriptMessages((prevMessages) => {
          // Keep messages that are NOT from transcription (e.g., upload messages)
          const manualMessages = prevMessages.filter(
            (msg) => msg.id.startsWith("upload_") || msg.attachments?.length,
          );

          // Combine transcription messages with manual messages
          const allMessages = [
            ...transcriptionMessages,
            ...manualMessages,
          ].sort((a, b) => a.timestamp - b.timestamp);

          if (process.env.NODE_ENV === "development") {
            // eslint-disable-next-line no-console
            console.log("✅ [TranscriptionReceived] Updating UI:", {
              transcriptionMessages: transcriptionMessages.length,
              manualMessages: manualMessages.length,
              totalMessages: allMessages.length,
            });
          }

          return allMessages;
        });
      }
    };

    room.on(RoomEvent.TranscriptionReceived, handleTranscriptionReceived);

    return () => {
      room.off(RoomEvent.TranscriptionReceived, handleTranscriptionReceived);
    };
  }, [room, setTranscriptMessages]);

  return null; // This is a data-only component
}
