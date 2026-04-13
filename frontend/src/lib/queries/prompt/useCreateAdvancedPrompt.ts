import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { api } from "@/lib/api/client";

/**
 * Request for POST /api/v1/prompt/create-advanced-prompt
 */
export interface CreateAdvancedPromptRequest {
  persona_id: string;
  user_id: string;
  db_update: boolean;
  sample_questions: string[];
  template: string;
  template_expertise: string;
  platform: string;
  chat_objective: string;
  response_structure: string;
  role: string;
  expertise: string;
  description: string;
  target_audience?: string;
}

/**
 * Response from POST /api/v1/prompt/create-advanced-prompt
 */
interface CreateAdvancedPromptResponse {
  status: string;
  persona_id: string;
  user_id: string;
  introduction: string;
  expertise_primary: string[];
  expertise_secondary: string[];
  communication_style: {
    thinking_style: string;
    speaking_style: string;
    writing_style: string;
    catch_phrases: string[];
    transition_words: string[];
    tone_characteristics: string[];
  };
  example_responses_count: number;
  db_updated: boolean;
  message: string;
}

/**
 * Generate advanced prompt using AI from user's knowledge sources
 * POST /api/v1/prompt/create-advanced-prompt
 */
const createAdvancedPrompt = async (
  params: CreateAdvancedPromptRequest,
): Promise<CreateAdvancedPromptResponse> => {
  const { data } = await api.post<CreateAdvancedPromptResponse>(
    "/prompt/create-advanced-prompt",
    params,
  );
  return data;
};

/**
 * Mutation hook to generate advanced prompt
 * This analyzes LinkedIn data, documents, tweets, and website content
 * to generate introduction, expertise, communication style, and examples
 */
export const useCreateAdvancedPrompt = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: createAdvancedPrompt,
    onSuccess: (data) => {
      // Invalidate prefill cache to refetch with new data
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
        tags: { operation: "create_advanced_prompt" },
        contexts: { prompt: { error: error.message } },
      });
    },
  });
};
