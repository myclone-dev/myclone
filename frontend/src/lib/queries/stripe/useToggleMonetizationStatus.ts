import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { PersonaMonetizationResponse } from "./interface";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { getPersonaMonetizationQueryKey } from "./useGetPersonaMonetization";

/**
 * Toggle monetization status (enable/disable)
 * Lightweight operation - no Stripe API calls, just DB update
 */
const toggleMonetizationStatus = async (
  personaId: string,
  isActive: boolean,
): Promise<PersonaMonetizationResponse> => {
  const response = await api.patch<PersonaMonetizationResponse>(
    `/stripe/personas/${personaId}/monetization/status`,
    { is_active: isActive },
  );
  return response.data;
};

/**
 * Hook to toggle monetization status (enable/disable)
 * Faster than useUpdateMonetization for simple toggle operations
 * Requires JWT authentication and persona ownership
 *
 * Use this for toggle switches instead of PUT /monetization
 */
export const useToggleMonetizationStatus = (personaId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (isActive: boolean) => {
      trackDashboardOperation("persona_monetization_toggle", "started", {
        personaId,
        isActive,
      });

      try {
        const result = await toggleMonetizationStatus(personaId, isActive);

        trackDashboardOperation("persona_monetization_toggle", "success", {
          personaId,
          isActive: result.is_active,
          pricingModel: result.pricing_model,
          priceCents: result.price_cents,
        });

        return result;
      } catch (error) {
        trackDashboardOperation("persona_monetization_toggle", "error", {
          personaId,
          isActive,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data) => {
      // Update the cache with the toggled state
      queryClient.setQueryData<PersonaMonetizationResponse>(
        getPersonaMonetizationQueryKey(personaId),
        data,
      );

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
