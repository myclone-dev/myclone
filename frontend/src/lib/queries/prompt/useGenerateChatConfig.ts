import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

export interface GenerateChatConfigRequest {
  persona_name: string;
  role: string;
  expertise: string;
  description?: string;
}

export interface GenerateChatConfigResponse {
  status: string;
  chat_objective?: string;
  target_audience?: string;
  message?: string;
}

/**
 * Generate chat objective and target audience using LLM
 * based on persona details from step 1 of persona creation.
 */
const generateChatConfig = async (
  data: GenerateChatConfigRequest,
): Promise<GenerateChatConfigResponse> => {
  const response = await api.post<GenerateChatConfigResponse>(
    "/prompt/generate-chat-config",
    data,
  );
  return response.data;
};

/**
 * Mutation hook for generating chat configuration (objective and target audience)
 * using LLM based on persona name, role, and expertise.
 *
 * @example
 * const { mutateAsync: generateConfig, isPending } = useGenerateChatConfig();
 *
 * const handleGenerate = async () => {
 *   const result = await generateConfig({
 *     persona_name: "Tech Advisor",
 *     role: "AI Consultant",
 *     expertise: "Deep learning, NLP, computer vision",
 *   });
 *   setChatObjective(result.chat_objective);
 *   setTargetAudience(result.target_audience);
 * };
 */
export const useGenerateChatConfig = () => {
  return useMutation({
    mutationFn: async (data: GenerateChatConfigRequest) => {
      trackDashboardOperation("chat_config_generate", "started", {
        persona_name: data.persona_name,
      });

      try {
        const result = await generateChatConfig(data);
        trackDashboardOperation("chat_config_generate", "success");
        return result;
      } catch (error) {
        trackDashboardOperation("chat_config_generate", "error", {
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onError: () => {
      // Error already tracked via trackDashboardOperation in mutationFn
    },
  });
};
