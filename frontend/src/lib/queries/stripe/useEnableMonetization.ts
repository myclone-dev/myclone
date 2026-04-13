import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  EnableMonetizationRequest,
  PersonaMonetizationResponse,
} from "./interface";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { getPersonaMonetizationQueryKey } from "./useGetPersonaMonetization";

/**
 * Enable monetization for a persona
 */
const enableMonetization = async (
  personaId: string,
  request: EnableMonetizationRequest,
): Promise<PersonaMonetizationResponse> => {
  const response = await api.post<PersonaMonetizationResponse>(
    `/stripe/personas/${personaId}/monetization`,
    request,
  );
  return response.data;
};

/**
 * Hook to enable monetization for a persona
 * Requires JWT authentication and persona ownership
 */
export const useEnableMonetization = (personaId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: EnableMonetizationRequest) => {
      trackDashboardOperation("persona_monetization_enable", "started", {
        personaId,
        pricingModel: request.pricing_model,
        priceCents: request.price_cents,
      });

      try {
        const result = await enableMonetization(personaId, request);

        trackDashboardOperation("persona_monetization_enable", "success", {
          personaId,
          pricingModel: result.pricing_model,
          priceCents: result.price_cents,
          stripeProductId: result.stripe_product_id,
          stripePriceId: result.stripe_price_id,
        });

        return result;
      } catch (error) {
        trackDashboardOperation("persona_monetization_enable", "error", {
          personaId,
          pricingModel: request.pricing_model,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data) => {
      // Update the cache with the new monetization settings
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
