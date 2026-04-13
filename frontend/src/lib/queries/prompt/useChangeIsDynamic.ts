import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { api } from "@/lib/api/client";

/**
 * Request for POST /api/v1/prompt/change-is-dynamic
 */
export interface ChangeIsDynamicRequest {
  persona_id: string;
  is_dynamic: boolean;
}

/**
 * Response from POST /api/v1/prompt/change-is-dynamic
 */
export interface ChangeIsDynamicResponse {
  status: string;
  action: string;
  persona_id: string;
  is_dynamic: boolean;
}

/**
 * Toggle is_dynamic field for a persona
 * POST /api/v1/prompt/change-is-dynamic
 */
const changeIsDynamic = async (
  request: ChangeIsDynamicRequest,
): Promise<ChangeIsDynamicResponse> => {
  const { data } = await api.post<ChangeIsDynamicResponse>(
    "/prompt/change-is-dynamic",
    request,
  );
  return data;
};

/**
 * Mutation hook to toggle is_dynamic field
 * This endpoint exists to toggle is_dynamic without creating version history
 */
export const useChangeIsDynamic = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: changeIsDynamic,
    onSuccess: (data) => {
      // Invalidate prefill cache to refetch with updated is_dynamic
      queryClient.invalidateQueries({
        queryKey: ["persona-prefill", data.persona_id],
      });
      // Invalidate persona queries
      queryClient.invalidateQueries({
        queryKey: ["personas", data.persona_id],
      });
      queryClient.invalidateQueries({
        queryKey: ["user-personas"],
      });
    },
    onError: (error: Error) => {
      Sentry.captureException(error, {
        tags: { operation: "change_is_dynamic" },
        contexts: { prompt: { error: error.message } },
      });
    },
  });
};
