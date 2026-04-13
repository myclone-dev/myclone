/**
 * Shared utilities for handling LiveKit text streams
 *
 * This module provides common functionality for parsing and handling
 * agent messages received via LiveKit's text stream API.
 */

import type { TextStreamReader } from "livekit-client";
import * as Sentry from "@sentry/nextjs";

/**
 * Raw message format from the agent
 */
export interface AgentMessage {
  /** The message content */
  message?: string;
  /** Whether this is the final message in a stream */
  is_final?: boolean;
  /** Alternative final flag */
  final?: boolean;
}

/**
 * Parsed agent message with normalized fields
 */
export interface ParsedAgentMessage {
  /** The message text content */
  text: string;
  /** Whether this message is complete/final */
  isFinal: boolean;
  /** Original raw message (if JSON parsing succeeded) */
  raw?: AgentMessage;
}

/**
 * Parse an agent message from raw string data
 *
 * Handles both JSON format ({ message: "...", is_final: true })
 * and plain text format.
 *
 * @param rawMessage - The raw message string from the agent
 * @returns Parsed message with text and final status
 *
 * @example
 * ```ts
 * // JSON format
 * parseAgentMessage('{"message": "Hello!", "is_final": true}')
 * // Returns: { text: "Hello!", isFinal: true, raw: { message: "Hello!", is_final: true } }
 *
 * // Plain text format
 * parseAgentMessage('Hello there!')
 * // Returns: { text: "Hello there!", isFinal: true }
 * ```
 */
export function parseAgentMessage(rawMessage: string): ParsedAgentMessage {
  // Try to parse as JSON first
  try {
    const messageData: AgentMessage = JSON.parse(rawMessage);
    if (messageData.message !== undefined) {
      return {
        text: messageData.message,
        isFinal: messageData.is_final ?? messageData.final ?? true,
        raw: messageData,
      };
    }
  } catch {
    // Not JSON, treat as plain text
  }

  // Return as plain text
  return {
    text: rawMessage,
    isFinal: true,
  };
}

/**
 * Citation source from RAG
 */
export interface CitationSource {
  title: string;
  content: string;
  similarity: number;
  source_url?: string;
  source_type: string;
  raw_source: string;
}

/**
 * Formatted citation for UI display
 */
export interface FormattedCitation {
  index: number;
  url: string;
  title: string;
  content?: string;
  raw_source?: string;
  source_type?: string;
}

/**
 * Format citation sources for UI display
 *
 * @param sources - Raw citation sources from RAG
 * @returns Formatted citations with index numbers
 */
export function formatCitations(
  sources: CitationSource[],
): FormattedCitation[] {
  return sources.map((c, idx) => ({
    index: idx + 1,
    url: c.source_url || "",
    title: c.title,
    content: c.content,
    raw_source: c.raw_source,
    source_type: c.source_type,
  }));
}

/**
 * Options for creating a text stream handler
 */
export interface TextStreamHandlerOptions {
  /**
   * Callback when a message is received
   * @param message - The parsed message
   * @param participantIdentity - Identity of the participant who sent the message
   */
  onMessage: (message: ParsedAgentMessage, participantIdentity: string) => void;

  /**
   * Optional callback for errors
   */
  onError?: (error: Error) => void;

  /**
   * Whether to log debug information (defaults to NODE_ENV === 'development')
   */
  debug?: boolean;

  /**
   * Label for debug logs
   */
  debugLabel?: string;

  /**
   * Whether to track errors in Sentry (defaults to true in production)
   */
  trackErrors?: boolean;
}

/**
 * Create a text stream handler function for LiveKit
 *
 * This creates a handler that can be passed to `room.registerTextStreamHandler()`.
 * It handles reading the stream and parsing the message.
 *
 * @param options - Handler configuration options
 * @returns A handler function for text streams
 *
 * @example
 * ```ts
 * const handler = createTextStreamHandler({
 *   onMessage: (message, identity) => {
 *     console.log(`Message from ${identity}:`, message.text);
 *   },
 *   debugLabel: 'MyHandler',
 * });
 *
 * room.registerTextStreamHandler('lk.chat', handler);
 * ```
 */
export function createTextStreamHandler(
  options: TextStreamHandlerOptions,
): (
  reader: TextStreamReader,
  participantInfo: { identity: string },
) => Promise<void> {
  const {
    onMessage,
    onError,
    debug = process.env.NODE_ENV === "development",
    debugLabel = "TextStream",
    trackErrors = process.env.NODE_ENV === "production",
  } = options;

  return async (
    reader: TextStreamReader,
    participantInfo: { identity: string },
  ) => {
    try {
      if (debug) {
        // eslint-disable-next-line no-console
        console.log(
          `📨 [${debugLabel}] Receiving from ${participantInfo.identity}`,
        );
      }

      // Read the full message from the stream
      const rawMessage = await reader.readAll();

      if (!rawMessage?.trim()) {
        return;
      }

      if (debug) {
        // eslint-disable-next-line no-console
        console.log(
          `🤖 [${debugLabel}] Message:`,
          rawMessage.substring(0, 100),
        );
      }

      // Parse the message
      const parsedMessage = parseAgentMessage(rawMessage);

      // Call the handler
      onMessage(parsedMessage, participantInfo.identity);
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));

      // Track in Sentry
      if (trackErrors) {
        Sentry.captureException(error, {
          tags: {
            component: "LiveKitTextStream",
            handler: debugLabel,
          },
          extra: {
            participantIdentity: participantInfo.identity,
          },
        });
      }

      if (onError) {
        onError(error);
      } else {
        console.error(`❌ [${debugLabel}] Error:`, error);
      }
    }
  };
}
