import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { StripeConnectDashboardResponse } from "./interface";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

/**
 * Get Stripe Dashboard login link for a persona's connected account
 */
const getDashboardLink = async (
  personaId: string,
): Promise<StripeConnectDashboardResponse> => {
  const response = await api.get<StripeConnectDashboardResponse>(
    `/stripe/personas/${personaId}/connect/dashboard`,
  );
  return response.data;
};

/**
 * Hook to get Stripe Dashboard link
 *
 * @param personaId - The persona ID with connected Stripe account
 * @returns Mutation hook that gets dashboard link and opens it in new tab
 *
 * @example
 * ```tsx
 * const viewDashboard = useStripeConnectDashboard(personaId);
 *
 * const handleViewDashboard = () => {
 *   viewDashboard.mutate();
 * };
 *
 * <Button onClick={handleViewDashboard} disabled={viewDashboard.isPending}>
 *   {viewDashboard.isPending ? "Loading..." : "View Stripe Dashboard"}
 * </Button>
 * ```
 */
export const useStripeConnectDashboard = (personaId: string) => {
  return useMutation({
    mutationFn: async () => {
      trackDashboardOperation("stripe_connect_dashboard", "started", {
        personaId,
      });

      try {
        const result = await getDashboardLink(personaId);

        trackDashboardOperation("stripe_connect_dashboard", "success", {
          personaId,
        });

        return result;
      } catch (error) {
        trackDashboardOperation("stripe_connect_dashboard", "error", {
          personaId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data) => {
      // Open dashboard in new tab
      window.open(data.dashboard_url, "_blank");
    },
  });
};
