import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

export interface CreatePersonaPromptRequest {
  persona_id: string;
  introduction?: string;
  thinking_style?: string;
  area_of_expertise?: string;
  chat_objective?: string;
  objective_response?: string;
  example_responses?: string;
  target_audience?: string;
  prompt_template_id?: string;
  example_prompt?: string;
  response_structure?: string;
  conversation_flow?: string;
}

export interface CreatePersonaPromptResponse {
  id: string;
  persona_id: string;
  version: number;
  message: string;
}

/**
 * Create a new PersonaPrompt record
 * POST /api/v1/prompt/persona-prompts
 */
const createPersonaPrompt = async (
  request: CreatePersonaPromptRequest,
): Promise<CreatePersonaPromptResponse> => {
  const { data } = await api.post<CreatePersonaPromptResponse>(
    "/prompt/persona-prompts",
    request,
  );
  return data;
};

/**
 * Mutation hook to create a PersonaPrompt
 */
export const useCreatePersonaPrompt = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: CreatePersonaPromptRequest) => {
      trackDashboardOperation("persona_create", "started", {
        personaId: request.persona_id,
      });
      try {
        const result = await createPersonaPrompt(request);
        trackDashboardOperation("persona_create", "success", {
          personaId: request.persona_id,
          promptId: result.id,
        });
        return result;
      } catch (error) {
        trackDashboardOperation("persona_create", "error", {
          personaId: request.persona_id,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data) => {
      // Invalidate persona queries
      queryClient.invalidateQueries({
        queryKey: ["personas", data.persona_id],
      });
      queryClient.invalidateQueries({
        queryKey: ["user-personas"],
      });
    },
    onError: () => {
      // Error already tracked via trackDashboardOperation in mutationFn
    },
  });
};
