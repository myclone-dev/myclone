import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { GetSuggestedQuestionsResponse } from "./interface";

/**
 * Fetch cached suggested questions for a persona
 * GET /api/v1/prompt/personas/{persona_id}/suggested-questions
 * Returns 200 if cached questions exist, 404 if no cache exists
 * Performance: <50ms (no LLM call), Cost: $0
 */
const fetchSuggestedQuestions = async (
  personaId: string,
): Promise<GetSuggestedQuestionsResponse | null> => {
  try {
    const { data } = await api.get<GetSuggestedQuestionsResponse>(
      `/prompt/personas/${personaId}/suggested-questions`,
    );
    return data;
  } catch (error) {
    // Return null if no cache exists (404) instead of throwing
    if (error && typeof error === "object" && "response" in error) {
      const axiosError = error as { response?: { status?: number } };
      if (axiosError.response?.status === 404) {
        return null;
      }
    }
    throw error;
  }
};

/**
 * Query key generator for caching
 */
export const getSuggestedQuestionsQueryKey = (personaId: string | null) => {
  return ["suggested-questions", personaId];
};

/**
 * Hook to fetch cached suggested questions for a persona
 * Returns null if no cache exists (404 response)
 */
export const useGetSuggestedQuestions = (
  personaId: string | null,
  options?: { enabled?: boolean },
) => {
  return useQuery({
    queryKey: getSuggestedQuestionsQueryKey(personaId),
    queryFn: () => {
      if (!personaId) throw new Error("Persona ID required");
      return fetchSuggestedQuestions(personaId);
    },
    enabled: options?.enabled !== false && !!personaId,
    staleTime: 0, // Always fetch fresh data (no caching)
    retry: false, // Don't retry on 404
  });
};
