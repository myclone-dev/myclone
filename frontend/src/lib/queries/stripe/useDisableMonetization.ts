import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { DisableMonetizationResponse } from "./interface";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { getPersonaMonetizationQueryKey } from "./useGetPersonaMonetization";

/**
 * Disable monetization for a persona
 */
const disableMonetization = async (
  personaId: string,
): Promise<DisableMonetizationResponse> => {
  const response = await api.delete<DisableMonetizationResponse>(
    `/stripe/personas/${personaId}/monetization`,
  );
  return response.data;
};

/**
 * Hook to disable monetization for a persona
 * Requires JWT authentication and persona ownership
 * Note: Stripe product/price are preserved for historical data
 */
export const useDisableMonetization = (personaId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      trackDashboardOperation("persona_monetization_disable", "started", {
        personaId,
      });

      try {
        const result = await disableMonetization(personaId);

        trackDashboardOperation("persona_monetization_disable", "success", {
          personaId,
        });

        return result;
      } catch (error) {
        trackDashboardOperation("persona_monetization_disable", "error", {
          personaId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: () => {
      // Remove monetization from cache (set to null)
      queryClient.setQueryData(getPersonaMonetizationQueryKey(personaId), null);

      // Invalidate persona queries to update pricing badge
      queryClient.invalidateQueries({
        queryKey: ["persona", personaId],
      });
    },
    onError: () => {
      // Error already tracked via trackDashboardOperation in mutationFn
    },
  });
};
