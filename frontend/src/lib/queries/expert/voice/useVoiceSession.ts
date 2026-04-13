import { useMutation } from "@tanstack/react-query";
import { trackLiveKitEvent } from "@/lib/monitoring/sentry";
import { env } from "@/env";
import { api } from "@/lib/api/client";
import type {
  VoiceSessionRequest,
  VoiceSessionResponse,
  VoiceLimitExceededError,
  VoiceHeartbeatResponse,
} from "./interface";

/**
 * Runtime validation for VoiceLimitExceededError response
 * Ensures API response matches expected shape before casting
 */
function isValidVoiceLimitExceededResponse(
  data: unknown,
): data is VoiceLimitExceededError {
  if (typeof data !== "object" || data === null) {
    return false;
  }

  const obj = data as Record<string, unknown>;

  return (
    obj.voice_limit_exceeded === true &&
    typeof obj.message === "string" &&
    typeof obj.used_minutes === "number" &&
    typeof obj.limit_minutes === "number"
  );
}

/**
 * Custom error class for voice limit exceeded
 */
export class VoiceLimitExceededAPIError extends Error {
  public readonly limitExceeded = true;
  public readonly usedMinutes: number;
  public readonly limitMinutes: number;

  constructor(data: VoiceLimitExceededError) {
    super(data.message);
    this.name = "VoiceLimitExceededError";
    this.usedMinutes = data.used_minutes;
    this.limitMinutes = data.limit_minutes;
  }
}

/**
 * Type guard to check if error is voice limit exceeded
 */
export function isVoiceLimitExceededError(
  error: unknown,
): error is VoiceLimitExceededAPIError {
  return error instanceof VoiceLimitExceededAPIError;
}

/**
 * Initialize voice session for LiveKit with session token
 */
const initializeVoiceSession = async (
  request: VoiceSessionRequest,
): Promise<VoiceSessionResponse> => {
  const url = `${env.NEXT_PUBLIC_API_URL}/livekit/connection-details`;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };

  const body = {
    expert_username: request.expert_username,
    persona_name: request.persona_name,
    session_token: request.session_token,
    widget_token: request.widget_token,
    room_config: request.room_config || {
      agents: [{ agent_name: request.expert_username }],
    },
  };

  const response = await fetch(url, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorText = await response.text();
    let error;
    try {
      error = JSON.parse(errorText);
    } catch {
      error = { detail: errorText || "Failed to get connection details" };
    }

    // Check for voice limit exceeded (403) with runtime validation
    if (
      response.status === 403 &&
      isValidVoiceLimitExceededResponse(error.detail)
    ) {
      throw new VoiceLimitExceededAPIError(error.detail);
    }

    throw new Error(error.detail || "Failed to get connection details");
  }

  return response.json();
};

/**
 * Hook to initialize voice chat session with LiveKit
 */
export function useInitVoiceSession() {
  return useMutation({
    mutationFn: initializeVoiceSession,
    onError: (error) => {
      trackLiveKitEvent("connection_error", {
        error: error instanceof Error ? error.message : "Unknown error",
        operation: "voice_session_init",
        isLimitExceeded: isVoiceLimitExceededError(error),
      });
    },
  });
}

/**
 * Send heartbeat to update session duration and check if should continue
 * Now uses api client - interceptor handles authentication automatically
 */
const sendHeartbeat = async ({
  sessionId,
  durationSeconds,
}: {
  sessionId: string;
  durationSeconds: number;
}): Promise<VoiceHeartbeatResponse> => {
  const { data } = await api.post<VoiceHeartbeatResponse>(
    `/livekit/session/${sessionId}/heartbeat`,
    { duration_seconds: durationSeconds },
  );
  return data;
};

/**
 * Hook for sending voice session heartbeats
 */
export function useVoiceHeartbeat() {
  return useMutation({
    mutationFn: sendHeartbeat,
  });
}
