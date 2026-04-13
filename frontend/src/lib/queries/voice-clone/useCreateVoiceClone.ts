import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { api } from "@/lib/api/client";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import type {
  CreateVoiceCloneRequest,
  CreateVoiceCloneResponse,
  VoiceCloneProvider,
} from "./interface";

/**
 * Get the API endpoint path for voice clone creation based on provider
 */
const getVoiceCloneEndpoint = (provider: VoiceCloneProvider): string => {
  return provider === "cartesia"
    ? "/cartesia/create_voice_clone"
    : "/eleven_labs/create_voice_clone";
};

/**
 * Parse error message from axios error response
 * Handles various FastAPI error formats
 */
const parseErrorMessage = (error: AxiosError): string => {
  const data = error.response?.data as Record<string, unknown> | undefined;

  if (!data) {
    return error.message || "Failed to create voice clone";
  }

  // Handle different error formats from FastAPI
  if (typeof data.detail === "string") {
    return data.detail;
  }
  if (typeof data.message === "string") {
    return data.message;
  }
  if (data.detail && typeof data.detail === "object" && "msg" in data.detail) {
    return (data.detail as { msg: string }).msg;
  }
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((e: { msg?: string }) => e.msg)
      .filter(Boolean)
      .join(", ");
  }

  return "Failed to create voice clone";
};

/**
 * Create Voice Clone
 * Upload audio files and create a voice clone using instant voice cloning
 *
 * Provider selection:
 * - cartesia: For free tier users (tier_id = 0)
 * - elevenlabs: For paid tier users (tier_id >= 1)
 */
const createVoiceClone = async (
  request: CreateVoiceCloneRequest,
): Promise<CreateVoiceCloneResponse> => {
  const provider = request.provider ?? "elevenlabs";
  const formData = new FormData();

  // Append common form fields
  formData.append("user_id", request.user_id);
  formData.append("name", request.name);

  if (request.description) {
    formData.append("description", request.description);
  }

  // Provider-specific fields
  if (provider === "elevenlabs") {
    // Eleven Labs uses remove_background_noise (default: true)
    formData.append(
      "remove_background_noise",
      request.remove_background_noise !== false ? "true" : "false",
    );
  } else {
    // Cartesia uses language (default: "en")
    formData.append("language", request.language ?? "en");
  }

  // Append audio files
  request.files.forEach((file) => {
    formData.append("files", file);
  });

  const endpoint = getVoiceCloneEndpoint(provider);

  // Use axios api client - it handles auth, error tracking via Sentry, and 401 redirects
  // Note: axios will set Content-Type with boundary automatically for FormData
  const response = await api.post<CreateVoiceCloneResponse>(endpoint, formData);

  return response.data;
};

export const useCreateVoiceClone = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: CreateVoiceCloneRequest) => {
      trackDashboardOperation("voice_clone_create", "started", {
        name: request.name,
        provider: request.provider ?? "elevenlabs",
        filesCount: request.files.length,
      });
      try {
        const result = await createVoiceClone(request);
        trackDashboardOperation("voice_clone_create", "success", {
          name: request.name,
          voiceId: result.voice_id,
        });
        return result;
      } catch (error) {
        const message =
          error instanceof AxiosError
            ? parseErrorMessage(error)
            : error instanceof Error
              ? error.message
              : "Failed to create voice clone";
        trackDashboardOperation("voice_clone_create", "error", {
          name: request.name,
          error: message,
        });
        throw error;
      }
    },
    onSuccess: () => {
      // Invalidate voice clone list queries for both providers
      queryClient.invalidateQueries({ queryKey: ["voice-clones"] });
    },
    onError: () => {
      // Error already tracked via trackDashboardOperation in mutationFn
    },
  });
};
