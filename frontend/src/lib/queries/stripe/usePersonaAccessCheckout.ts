import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  CreatePersonaCheckoutRequest,
  CreatePersonaCheckoutResponse,
} from "./interface";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

/**
 * Create Stripe checkout session for persona access purchase
 */
const createPersonaAccessCheckout = async (
  request: CreatePersonaCheckoutRequest,
): Promise<CreatePersonaCheckoutResponse> => {
  const response = await api.post<CreatePersonaCheckoutResponse>(
    "/stripe/checkout/persona-access",
    request,
  );
  return response.data;
};

/**
 * Hook to create Stripe checkout session for purchasing persona access
 * Requires JWT authentication
 *
 * Usage:
 * ```tsx
 * const { mutate: purchaseAccess, isPending } = usePersonaAccessCheckout();
 *
 * const handlePurchase = () => {
 *   purchaseAccess({
 *     persona_id: personaId,
 *     success_url: `${window.location.origin}/persona/${personaId}/chat`,
 *     cancel_url: `${window.location.origin}/persona/${personaId}`,
 *   }, {
 *     onSuccess: (data) => {
 *       window.location.href = data.checkout_url; // Redirect to Stripe
 *     },
 *   });
 * };
 * ```
 */
export const usePersonaAccessCheckout = () => {
  return useMutation({
    mutationFn: async (request: CreatePersonaCheckoutRequest) => {
      trackDashboardOperation("persona_access_purchase", "started", {
        personaId: request.persona_id,
      });

      try {
        const result = await createPersonaAccessCheckout(request);

        trackDashboardOperation("persona_access_purchase", "success", {
          personaId: request.persona_id,
          sessionId: result.session_id,
        });

        return result;
      } catch (error) {
        trackDashboardOperation("persona_access_purchase", "error", {
          personaId: request.persona_id,
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
