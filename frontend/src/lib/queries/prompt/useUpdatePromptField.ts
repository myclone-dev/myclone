import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { api } from "@/lib/api/client";
import type {
  UpdatePromptFieldRequest,
  UpdatePromptFieldResponse,
} from "./interface";

/**
 * Update a single persona prompt field
 * PATCH /api/v1/prompt/update-prompt-parameter
 */
const updatePromptField = async (
  request: UpdatePromptFieldRequest,
): Promise<UpdatePromptFieldResponse> => {
  const { data } = await api.patch<UpdatePromptFieldResponse>(
    "/prompt/update-prompt-parameter",
    request,
  );
  return data;
};

/**
 * Mutation hook to update a single persona prompt field
 */
export const useUpdatePromptField = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updatePromptField,
    onSuccess: (data) => {
      // Invalidate persona queries to refetch updated data
      queryClient.invalidateQueries({
        queryKey: ["personas", data.persona_id],
      });
      queryClient.invalidateQueries({
        queryKey: ["user-personas"],
      });
    },
    onError: (error: Error) => {
      Sentry.captureException(error, {
        tags: { operation: "update_prompt_field" },
        contexts: { prompt: { error: error.message } },
      });
    },
  });
};

/**
 * Helper function to update multiple persona prompt fields in sequence
 * Use this during persona creation/onboarding to update all fields
 */
export const updateMultiplePromptFields = async (
  personaId: string,
  fields: Record<string, string | object>,
): Promise<void> => {
  for (const [field, value] of Object.entries(fields)) {
    await updatePromptField({
      persona_id: personaId,
      field,
      value,
    });
  }
};
