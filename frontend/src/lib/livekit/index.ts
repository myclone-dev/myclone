/**
 * LiveKit utilities and constants
 *
 * This module provides shared utilities for LiveKit-based real-time communication
 * in both text and voice chat modes.
 *
 * @see docs/LIVEKIT_ARCHITECTURE.md for detailed architecture documentation
 */

export {
  LIVEKIT_TOPICS,
  AGENT_TEXT_TOPICS,
  METADATA_TOPICS,
  isAgentTextTopic,
  isMetadataTopic,
  type LiveKitTopic,
} from "./constants";

export {
  parseAgentMessage,
  createTextStreamHandler,
  formatCitations,
  type AgentMessage,
  type ParsedAgentMessage,
  type TextStreamHandlerOptions,
  type CitationSource,
  type FormattedCitation,
} from "./textStreamHandler";
