import { useMutation, useQueryClient } from "@tanstack/react-query";
import { env } from "@/env";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

/** Query key for voice clones list */
export const VOICE_CLONE_QUERY_KEY = "voice-clones" as const;

/**
 * Request payload for deleting a voice clone
 */
export interface DeleteVoiceCloneRequest {
  /** The unique identifier of the voice clone to delete */
  voice_id: string;
}

/**
 * Response from the unified voice clone deletion endpoint
 */
export interface DeleteVoiceCloneResponse {
  /** The ID of the deleted voice clone */
  voice_id: string;
  /** Platform the voice was deleted from (elevenlabs or cartesia) */
  platform: string;
  /** Status of the deletion operation: success or partial */
  status: string;
  /** Human-readable message about the deletion result */
  message: string;
  /** Whether voice was deleted from platform API */
  platform_deleted: boolean;
  /** Whether voice was deleted from database */
  database_deleted: boolean;
}

/**
 * Delete a voice clone using the unified DELETE endpoint.
 *
 * The backend automatically:
 * 1. Finds the voice clone in the database
 * 2. Detects the platform (elevenlabs or cartesia) from voice_clone.platform
 * 3. Routes to the appropriate service
 * 4. Deletes from the platform API
 * 5. Removes from database
 * 6. Clears persona references
 *
 * Endpoint: DELETE /api/v1/voice-clones/{voice_id}
 *
 * @param request - The deletion request containing voice_id
 * @returns Promise resolving to the deletion response
 * @throws Error if the deletion fails
 */
const deleteVoiceClone = async (
  request: DeleteVoiceCloneRequest,
): Promise<DeleteVoiceCloneResponse> => {
  const endpoint = `${env.NEXT_PUBLIC_API_URL}/voice-clones/${request.voice_id}`;

  const response = await fetch(endpoint, {
    method: "DELETE",
    credentials: "include",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      error.detail || error.message || "Failed to delete voice clone",
    );
  }

  return response.json();
};

/**
 * React Query mutation hook for deleting a voice clone.
 *
 * Uses the unified DELETE endpoint that automatically detects the platform
 * (elevenlabs or cartesia) and handles deletion from both the provider API
 * and database.
 *
 * This hook handles:
 * - Automatic platform detection (no need to specify provider)
 * - Automatic cache invalidation on success
 * - Sentry error monitoring
 *
 * @example
 * ```tsx
 * const { mutate: deleteVoiceClone, isPending } = useDeleteVoiceClone();
 *
 * const handleDelete = (voiceClone: VoiceClone) => {
 *   deleteVoiceClone(
 *     { voice_id: voiceClone.voice_id },
 *     {
 *       onSuccess: () => toast.success("Voice clone deleted"),
 *       onError: (error) => toast.error(error.message),
 *     }
 *   );
 * };
 * ```
 *
 * @returns TanStack Query mutation object with mutate, isPending, etc.
 */
export const useDeleteVoiceClone = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: DeleteVoiceCloneRequest) => {
      trackDashboardOperation("voice_clone_delete", "started", {
        voiceId: request.voice_id,
      });
      return deleteVoiceClone(request);
    },
    onSuccess: (data, variables) => {
      trackDashboardOperation("voice_clone_delete", "success", {
        voiceId: variables.voice_id,
        platform: data.platform,
      });
      // Invalidate voice clone list queries to refresh the UI
      queryClient.invalidateQueries({ queryKey: [VOICE_CLONE_QUERY_KEY] });
    },
    onError: (error: Error, variables) => {
      trackDashboardOperation("voice_clone_delete", "error", {
        voiceId: variables.voice_id,
        error: error.message,
      });
    },
  });
};
