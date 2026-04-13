import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { StripeConnectOnboardResponse } from "./interface";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

/**
 * Initiate Stripe Connect onboarding for a persona
 * Creates a Stripe Connect account and returns onboarding URL
 */
const initiateOnboarding = async (
  personaId: string,
): Promise<StripeConnectOnboardResponse> => {
  const response = await api.post<StripeConnectOnboardResponse>(
    `/stripe/personas/${personaId}/connect/onboard`,
  );
  return response.data;
};

/**
 * Hook to initiate Stripe Connect onboarding
 *
 * @param personaId - The persona ID to connect Stripe account for
 * @returns Mutation hook that initiates onboarding and redirects to Stripe
 *
 * @example
 * ```tsx
 * const connectStripe = useStripeConnectOnboard(personaId);
 *
 * const handleConnect = () => {
 *   connectStripe.mutate();
 * };
 *
 * <Button onClick={handleConnect} disabled={connectStripe.isPending}>
 *   {connectStripe.isPending ? "Connecting..." : "Connect Stripe Account"}
 * </Button>
 * ```
 */
export const useStripeConnectOnboard = (personaId: string) => {
  return useMutation({
    mutationFn: async () => {
      trackDashboardOperation("stripe_connect_onboard", "started", {
        personaId,
      });

      try {
        const result = await initiateOnboarding(personaId);

        trackDashboardOperation("stripe_connect_onboard", "success", {
          personaId,
          accountId: result.account_id,
        });

        return result;
      } catch (error) {
        trackDashboardOperation("stripe_connect_onboard", "error", {
          personaId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data) => {
      // Redirect to Stripe onboarding
      window.location.href = data.onboarding_url;
    },
  });
};
