/**
 * Expert voice chat type definitions
 */

/**
 * Room configuration for LiveKit sessions
 * - For voice mode: include agents array
 * - For text mode: include text_only_mode: true
 */
export interface RoomConfig {
  agents?: Array<{ agent_name: string }>;
  text_only_mode?: boolean;
}

export interface VoiceSessionRequest {
  expert_username: string;
  persona_name?: string;
  session_token: string;
  widget_token?: string;
  room_config?: RoomConfig;
}

export interface VoiceSessionResponse {
  serverUrl: string;
  roomName: string;
  participantName: string;
  participantToken: string;
  session_id?: string; // Voice session ID for heartbeat/tracking
}

/**
 * Voice limit exceeded error response (403)
 */
export interface VoiceLimitExceededError {
  voice_limit_exceeded: true;
  message: string;
  used_minutes: number;
  limit_minutes: number;
}

/**
 * Heartbeat request/response for tracking session duration
 */
export interface VoiceHeartbeatRequest {
  duration_seconds: number;
}

export interface VoiceHeartbeatResponse {
  continue_session: boolean;
  reason?: string;
}

/**
 * Save voice transcript types
 */
export interface TranscriptMessage {
  speaker: "user" | "assistant" | "agent";
  text: string;
  timestamp: string; // ISO 8601 format
  isComplete: boolean;
}

export interface SaveVoiceTranscriptRequest {
  session_token: string;
  transcript_messages: TranscriptMessage[];
}

export interface SaveVoiceTranscriptResponse {
  success: boolean;
  message: string;
  session_token: string;
  conversation_type: "voice";
}
