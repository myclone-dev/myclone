"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

/**
 * Stripe Connect Onboarding - Success Redirect
 * Shown when creator successfully completes Stripe onboarding
 *
 * Flow:
 * 1. Creator completes Stripe onboarding
 * 2. Stripe redirects here with success status
 * 3. Show success toast
 * 4. Redirect to dashboard profile after 1.5 seconds
 */
export default function StripeConnectCompletePage() {
  const router = useRouter();

  useEffect(() => {
    // Track successful completion
    trackDashboardOperation("stripe_connect_complete", "success", {
      redirectPath: window.location.pathname,
    });

    // Show success toast
    toast.success("Stripe account connected successfully!", {
      description: "You can now receive payments from your paid persona",
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
        <div className="text-6xl mb-4">✅</div>
        <h1 className="text-2xl font-semibold text-foreground">
          Connected Successfully!
        </h1>
        <p className="text-muted-foreground">
          Your Stripe account is now connected
        </p>
        <p className="text-sm text-muted-foreground">
          Redirecting to dashboard...
        </p>
      </div>
    </div>
  );
}
