import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { api } from "@/lib/api/client";
import type { PersonaDetails } from "../persona/interface";

/**
 * Update suggested questions for a persona
 * PATCH /api/v1/personas/{persona_id}/with-knowledge
 */
export interface UpdateSuggestedQuestionsRequest {
  persona_id: string;
  questions: string[];
}

const updateSuggestedQuestions = async (
  request: UpdateSuggestedQuestionsRequest,
): Promise<PersonaDetails> => {
  const { persona_id, questions } = request;
  const { data } = await api.patch<PersonaDetails>(
    `/personas/${persona_id}/with-knowledge`,
    { suggested_questions: questions },
  );
  return data;
};

/**
 * Mutation hook to update suggested questions for a persona
 */
export const useUpdateSuggestedQuestions = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateSuggestedQuestions,
    onSuccess: (data) => {
      // The PATCH endpoint returns PersonaResponse which has suggested_questions as a simple array
      // We need to format it to match GetSuggestedQuestionsResponse structure
      if (data.suggested_questions && data.suggested_questions.length > 0) {
        const cacheData = {
          status: "success",
          persona_id: data.id,
          suggested_questions: data.suggested_questions,
          generated_at: new Date().toISOString(),
          response_settings: {},
          from_cache: false,
          message: "Questions updated successfully",
        };

        queryClient.setQueryData(["suggested-questions", data.id], cacheData);
      }

      // Update the persona query cache with the new suggested_questions
      // This ensures the agent page immediately shows the updated questions
      queryClient.setQueriesData(
        { queryKey: ["persona"] },
        (oldData: unknown) => {
          if (
            oldData &&
            typeof oldData === "object" &&
            "id" in oldData &&
            oldData.id === data.id
          ) {
            return {
              ...oldData,
              suggested_questions: data.suggested_questions,
            };
          }
          return oldData;
        },
      );

      // Invalidate other related queries (but not suggested-questions to avoid refetching stale backend cache)
      queryClient.invalidateQueries({
        queryKey: ["personas", data.id],
      });
      queryClient.invalidateQueries({
        queryKey: ["user-personas"],
      });
    },
    onError: (error: Error) => {
      Sentry.captureException(error, {
        tags: { operation: "update_suggested_questions" },
        contexts: { prompt: { error: error.message } },
      });
    },
  });
};
