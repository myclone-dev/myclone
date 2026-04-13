"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

/**
 * Stripe Connect Onboarding - Incomplete Redirect
 * Shown when creator closes onboarding without completing
 *
 * Flow:
 * 1. Creator starts Stripe onboarding but doesn't complete it
 * 2. Stripe redirects here with incomplete status
 * 3. Show warning toast
 * 4. Redirect to dashboard profile after 1.5 seconds
 */
export default function StripeConnectRefreshPage() {
  const router = useRouter();

  useEffect(() => {
    // Track incomplete onboarding
    trackDashboardOperation("stripe_connect_refresh", "started", {
      redirectPath: window.location.pathname,
    });

    // Show warning toast
    toast.warning("Stripe setup incomplete", {
      description: "Please complete your Stripe setup to receive payments",
      duration: 5000,
    });

    // Redirect to profile/dashboard after 1.5 seconds
    const timeout = setTimeout(() => {
      router.push("/dashboard/profile");
    }, 1500);

    return () => clearTimeout(timeout);
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <div className="text-center space-y-4 p-8">
        <div className="text-6xl mb-4">⚠️</div>
        <h1 className="text-2xl font-semibold text-foreground">
          Setup Incomplete
        </h1>
        <p className="text-muted-foreground">
          Complete your Stripe setup to start receiving payments
        </p>
        <p className="text-sm text-muted-foreground">Redirecting...</p>
      </div>
    </div>
  );
}
