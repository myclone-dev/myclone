import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  UpdateMonetizationRequest,
  PersonaMonetizationResponse,
} from "./interface";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { getPersonaMonetizationQueryKey } from "./useGetPersonaMonetization";

/**
 * Update monetization settings for a persona
 */
const updateMonetization = async (
  personaId: string,
  request: UpdateMonetizationRequest,
): Promise<PersonaMonetizationResponse> => {
  const response = await api.put<PersonaMonetizationResponse>(
    `/stripe/personas/${personaId}/monetization`,
    request,
  );
  return response.data;
};

/**
 * Hook to update monetization settings for a persona
 * Requires JWT authentication and persona ownership
 * Note: Changing price creates a NEW Stripe price (old price preserved for existing subscriptions)
 */
export const useUpdateMonetization = (personaId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: UpdateMonetizationRequest) => {
      trackDashboardOperation("persona_monetization_update", "started", {
        personaId,
        updateFields: Object.keys(request),
      });

      try {
        const result = await updateMonetization(personaId, request);

        trackDashboardOperation("persona_monetization_update", "success", {
          personaId,
          pricingModel: result.pricing_model,
          priceCents: result.price_cents,
          isActive: result.is_active,
          stripePriceId: result.stripe_price_id,
        });

        return result;
      } catch (error) {
        trackDashboardOperation("persona_monetization_update", "error", {
          personaId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data) => {
      // Update the cache with the updated monetization settings
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
