import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

interface ToggleSummaryEmailResponse {
  success: boolean;
  message: string;
  persona_id: string;
  send_summary_email_enabled: boolean;
}

interface ToggleSummaryEmailParams {
  personaId: string;
  enabled: boolean;
}

/**
 * Toggle conversation summary email setting
 * PATCH /api/v1/personas/{persona_id}/summary-email?enabled={boolean}
 */
const toggleSummaryEmail = async ({
  personaId,
  enabled,
}: ToggleSummaryEmailParams): Promise<ToggleSummaryEmailResponse> => {
  const { data } = await api.patch<ToggleSummaryEmailResponse>(
    `/personas/${personaId}/summary-email`,
    null,
    { params: { enabled } },
  );
  return data;
};

/**
 * Mutation hook to toggle conversation summary email setting
 * When enabled, summary emails are sent to persona owner after conversations end
 * When disabled, no summary emails are sent
 */
export const useToggleSummaryEmail = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (params: ToggleSummaryEmailParams) => {
      trackDashboardOperation("persona_update", "started", {
        personaId: params.personaId,
        setting: "send_summary_email_enabled",
        enabled: params.enabled,
      });
      try {
        const result = await toggleSummaryEmail(params);
        trackDashboardOperation("persona_update", "success", {
          personaId: params.personaId,
          setting: "send_summary_email_enabled",
          enabled: params.enabled,
        });
        return result;
      } catch (error) {
        trackDashboardOperation("persona_update", "error", {
          personaId: params.personaId,
          setting: "send_summary_email_enabled",
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (_, variables) => {
      // Invalidate personas list to reflect updated setting
      queryClient.invalidateQueries({
        queryKey: ["user-personas"],
      });
      // Invalidate specific persona query
      queryClient.invalidateQueries({
        queryKey: ["persona-by-id", variables.personaId],
      });
    },
  });
};
