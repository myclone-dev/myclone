import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  CreditCard,
  CheckCircle,
  ExternalLink,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { PersonaMonetizationResponse } from "@/lib/queries/stripe";

interface StripeConnectCardProps {
  monetizationData: PersonaMonetizationResponse;
  onConnect: () => void;
  onViewDashboard: () => void;
  isConnecting: boolean;
  isLoadingDashboard: boolean;
}

/**
 * Stripe Connect card for creator payouts
 * Shows different states based on connection status
 */
export function StripeConnectCard({
  monetizationData,
  onConnect,
  onViewDashboard,
  isConnecting,
  isLoadingDashboard,
}: StripeConnectCardProps) {
  const isConnected = !!monetizationData.stripe_account_id;

  return (
    <Card
      className={cn(
        "border-2",
        isConnected
          ? "border-green-200 bg-green-50/30"
          : "border-amber-200 bg-amber-50/30",
      )}
    >
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <CreditCard className="size-4" />
          Receive Payouts via Stripe
        </CardTitle>
        <CardDescription>
          {isConnected
            ? "Your Stripe account is connected and ready to receive payments"
            : "Connect your Stripe account to receive payments from your paid persona"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isConnected ? (
          // CONNECTED STATE
          <>
            <div className="flex items-center gap-3 p-4 bg-green-100 border border-green-300 rounded-lg">
              <CheckCircle className="size-5 text-green-700 shrink-0" />
              <div>
                <p className="text-sm font-medium text-green-900">
                  ✓ Connected to Stripe
                </p>
                <p className="text-xs text-green-700">
                  Payments will be deposited to your connected bank account
                </p>
              </div>
            </div>

            <button
              onClick={onViewDashboard}
              disabled={isLoadingDashboard}
              className="w-full inline-flex items-center justify-center gap-2 rounded-md border border-input bg-background px-4 py-2 text-sm font-medium ring-offset-background transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
            >
              {isLoadingDashboard ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Loading...
                </>
              ) : (
                <>
                  <ExternalLink className="size-4" />
                  View Stripe Dashboard
                </>
              )}
            </button>

            <p className="text-xs text-muted-foreground">
              View earnings, payout history, and manage your bank account
            </p>
          </>
        ) : (
          // NOT CONNECTED STATE
          <>
            {/* Warning Banner - Merged inside card */}
            <div className="p-4 bg-red-50 border-2 border-red-200 rounded-lg">
              <div className="flex gap-3">
                <AlertCircle className="size-5 text-red-600 shrink-0" />
                <div className="space-y-1">
                  <p className="text-sm font-semibold text-red-900">
                    Action Required
                  </p>
                  <p className="text-sm text-red-800">
                    Connect your Stripe account to start accepting payments.
                    Without this, visitors cannot purchase access to your
                    persona.
                  </p>
                </div>
              </div>
            </div>

            <button
              onClick={onConnect}
              disabled={isConnecting}
              className="w-full inline-flex items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
            >
              {isConnecting ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Connecting...
                </>
              ) : (
                <>
                  <ExternalLink className="size-4" />
                  Connect Stripe Account
                </>
              )}
            </button>

            <p className="text-xs text-muted-foreground">
              You'll be redirected to Stripe to complete a quick onboarding
              process
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
