import { useMutation } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { api } from "@/lib/api/client";
import type {
  SaveVoiceTranscriptRequest,
  SaveVoiceTranscriptResponse,
} from "./interface";

interface SaveVoiceTranscriptParams {
  username: string;
  personaName?: string;
  data: SaveVoiceTranscriptRequest;
  widgetToken?: string;
}

/**
 * Save voice transcript to backend
 * Now uses api client - interceptor handles authentication automatically
 */
const saveVoiceTranscript = async ({
  username,
  personaName = "default",
  data,
  widgetToken: _widgetToken, // Kept for backward compatibility but not used (interceptor handles auth)
}: SaveVoiceTranscriptParams): Promise<SaveVoiceTranscriptResponse> => {
  const { data: response } = await api.post<SaveVoiceTranscriptResponse>(
    `/personas/username/${username}/save-voice-transcript?persona_name=${personaName}`,
    data,
  );
  return response;
};

/**
 * Hook to save voice transcript
 */
export function useSaveVoiceTranscript() {
  return useMutation({
    mutationFn: saveVoiceTranscript,
    onError: (error) => {
      Sentry.captureException(error, {
        tags: { operation: "save_voice_transcript" },
        contexts: {
          voice: {
            error: error instanceof Error ? error.message : "Unknown error",
          },
        },
      });
    },
  });
}
