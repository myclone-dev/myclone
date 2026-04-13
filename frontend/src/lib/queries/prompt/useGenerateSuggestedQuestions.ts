import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { api } from "@/lib/api/client";
import type { GenerateSuggestedQuestionsResponse } from "./interface";

/**
 * Generate suggested questions for a persona
 * POST /api/v1/prompt/personas/{persona_id}/suggested-questions
 */
const generateSuggestedQuestions = async (
  personaId: string,
  numQuestions: number = 5,
  forceRegenerate: boolean = false,
): Promise<GenerateSuggestedQuestionsResponse> => {
  const params = new URLSearchParams();
  params.append("num_questions", numQuestions.toString());
  params.append("force_regenerate", forceRegenerate.toString());

  const { data } = await api.post<GenerateSuggestedQuestionsResponse>(
    `/prompt/personas/${personaId}/suggested-questions?${params.toString()}`,
  );
  return data;
};

/**
 * Mutation hook to generate suggested questions
 */
export const useGenerateSuggestedQuestions = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      personaId,
      numQuestions = 5,
      forceRegenerate = false,
    }: {
      personaId: string;
      numQuestions?: number;
      forceRegenerate?: boolean;
    }) => generateSuggestedQuestions(personaId, numQuestions, forceRegenerate),
    onSuccess: (data) => {
      // Invalidate persona queries to refetch with new questions
      queryClient.invalidateQueries({
        queryKey: ["personas", data.persona_id],
      });
      queryClient.invalidateQueries({
        queryKey: ["user-personas"],
      });
    },
    onError: (error: Error) => {
      Sentry.captureException(error, {
        tags: { operation: "generate_suggested_questions" },
        contexts: { prompt: { error: error.message } },
      });
    },
  });
};

/**
 * Query key generator for caching
 */
export const getSuggestedQuestionsQueryKey = (personaId: string) => {
  return ["suggested-questions", personaId];
};
