import { useQuery } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { api } from "@/lib/api/client";
import type { PersonaPromptFields } from "./interface";

/**
 * Response from GET /api/v1/prompt/list-active-prompts
 */
interface ListActivePromptsResponse {
  status: string;
  persona_id: string;
  count: number;
  prompts: Array<{
    id: string;
    persona_id: string;
    introduction: string | null;
    area_of_expertise: string | null;
    thinking_style: string | null;
    chat_objective: string | null;
    objective_response: string | null;
    target_audience: string | null;
    response_structure: string | null;
    example_responses: string | null;
    example_prompt: string | null;
    is_dynamic: boolean;
    is_active: boolean;
    conversation_flow: string | null;
    strict_guideline: string | null;
    prompt_template_id: string | null;
    created_at: string;
    updated_at: string;
  }>;
  message: string;
}

/**
 * Fetch persona prompt prefill data from the default persona
 * GET /api/v1/prompt/list-active-prompts?persona_id={persona_id}
 */
const fetchPersonaPrefill = async (
  personaId: string,
): Promise<PersonaPromptFields | null> => {
  const { data } = await api.get<ListActivePromptsResponse>(
    `/prompt/list-active-prompts?persona_id=${personaId}`,
  );

  // Return first active prompt if available
  if (data.prompts && data.prompts.length > 0) {
    const prompt = data.prompts[0];

    // Parse response_structure if it's a JSON string
    let responseStructure = null;
    if (prompt.response_structure) {
      try {
        responseStructure = JSON.parse(prompt.response_structure);
      } catch (e) {
        Sentry.captureException(e, {
          tags: { operation: "persona_prefill_parse" },
          contexts: {
            prefill: {
              personaId,
              promptId: prompt.id,
              responseStructureLength: prompt.response_structure?.length,
            },
          },
        });
      }
    }

    return {
      introduction: prompt.introduction || "",
      area_of_expertise: prompt.area_of_expertise || "",
      chat_objective: prompt.chat_objective || "",
      objective_response: prompt.objective_response || "",
      thinking_style: prompt.thinking_style || "",
      target_audience: prompt.target_audience || "",
      response_structure: responseStructure,
      example_responses: prompt.example_responses || "",
      example_prompt: prompt.example_prompt || "",
      conversation_flow: prompt.conversation_flow || "",
      strict_guideline: prompt.strict_guideline || "",
      is_dynamic: prompt.is_dynamic || false,
    };
  }

  return null;
};

/**
 * Query key generator for caching
 */
export const getPersonaPrefillQueryKey = (personaId: string | null) => {
  return ["persona-prefill", personaId];
};

/**
 * Hook to fetch persona prompt prefill data
 * Uses the default persona's prompt configuration
 */
export const usePersonaPrefill = (
  personaId: string | null,
  options?: { enabled?: boolean },
) => {
  return useQuery({
    queryKey: getPersonaPrefillQueryKey(personaId),
    queryFn: () => {
      if (!personaId) throw new Error("Persona ID required");
      return fetchPersonaPrefill(personaId);
    },
    enabled: options?.enabled !== false && !!personaId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
