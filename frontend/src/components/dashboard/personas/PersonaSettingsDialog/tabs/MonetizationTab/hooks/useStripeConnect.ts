import {
  useStripeConnectOnboard,
  useStripeConnectDashboard,
} from "@/lib/queries/stripe";

/**
 * Hook to manage Stripe Connect actions
 * Provides handlers for onboarding and dashboard access
 */
export function useStripeConnect(personaId: string) {
  const connectStripe = useStripeConnectOnboard(personaId);
  const viewDashboard = useStripeConnectDashboard(personaId);

  const handleConnectStripe = () => {
    connectStripe.mutate();
  };

  const handleViewDashboard = () => {
    viewDashboard.mutate();
  };

  return {
    connectStripe,
    viewDashboard,
    handleConnectStripe,
    handleViewDashboard,
  };
}
