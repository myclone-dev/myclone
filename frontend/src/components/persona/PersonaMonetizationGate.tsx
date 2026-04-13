"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  DollarSign,
  Lock,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";
import {
  useGetPersonaMonetization,
  useCheckPersonaAccess,
  usePersonaAccessCheckout,
  formatPrice,
  formatPricingModel,
} from "@/lib/queries/stripe";
import { OTPWizard } from "@/components/expert/chat/OTPWizard";

interface PersonaMonetizationGateProps {
  personaId: string;
  personaName: string; // URL slug (e.g., "jane-doe")
  personaUsername: string;
  personaDisplayName?: string; // Display name (e.g., "Jane Doe")
  children: React.ReactNode;
}

/**
 * Gate component that checks if user has purchased access to a monetized persona
 * Shows purchase UI if access is required, otherwise renders children (chat interface)
 */
export function PersonaMonetizationGate({
  personaId,
  personaName,
  personaUsername,
  personaDisplayName,
  children,
}: PersonaMonetizationGateProps) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [showOTPWizard, setShowOTPWizard] = useState(false);
  const [otpCompleted, setOtpCompleted] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);

  // Check if persona has monetization enabled
  const { data: monetization, isLoading: pricingLoading } =
    useGetPersonaMonetization(personaId);

  // Check if current user has access
  // Note: We always make this call if monetization exists. Backend will check JWT cookie.
  // If no cookie (unauthenticated), backend returns 401 and we handle gracefully.
  const {
    data: accessData,
    isLoading: accessLoading,
    refetch: refetchAccess,
  } = useCheckPersonaAccess(personaId, {
    enabled: !!monetization, // Call API if monetization exists (backend checks cookie)
  });

  // Purchase mutation
  const { mutate: createCheckout, isPending: checkoutPending } =
    usePersonaAccessCheckout();

  const initiateCheckout = useCallback(() => {
    setIsProcessing(true);

    createCheckout(
      {
        persona_id: personaId,
        success_url: `${window.location.origin}/${personaUsername}/${personaName}/payment/success`,
        cancel_url: `${window.location.origin}/${personaUsername}/${personaName}`,
      },
      {
        onSuccess: (data) => {
          // Validate checkout URL exists
          if (!data.checkout_url) {
            setIsProcessing(false);
            setShowSuccessModal(false);
            toast.error("Failed to get checkout URL", {
              description: "Please try again or contact support.",
            });
            return;
          }

          // Redirect to Stripe checkout
          window.location.href = data.checkout_url;
        },
        onError: (error: Error) => {
          setIsProcessing(false);
          setShowSuccessModal(false); // Hide success modal on error

          // Check for auth error - show OTP wizard instead of redirecting
          if (
            error.message.includes("401") ||
            error.message.includes("Unauthorized")
          ) {
            setShowOTPWizard(true);
            return;
          }

          toast.error("Failed to start checkout", {
            description: error.message,
          });
        },
      },
    );
  }, [createCheckout, personaId, personaUsername, personaName]);

  const handlePurchase = () => {
    initiateCheckout();
  };

  const handleOTPComplete = () => {
    // User authenticated successfully - close OTP wizard
    setShowOTPWizard(false);

    // Trigger access refetch with new JWT cookie
    refetchAccess();

    // Set flag to handle checkout after refetch completes
    setOtpCompleted(true);
  };

  // Wait for access refetch to complete after OTP, then decide what to do
  useEffect(() => {
    // Only run if OTP just completed AND access check is done loading AND we have data
    if (otpCompleted && !accessLoading && accessData !== undefined) {
      // Reset flag
      setOtpCompleted(false);

      // Check if user has access
      if (accessData.has_access) {
        // User has access (e.g., they're the owner) - just show toast
        toast.success("Welcome back! You have access to this persona.");
      } else {
        // User doesn't have access - show success modal and initiate Stripe checkout
        setShowSuccessModal(true);
        initiateCheckout();
      }
    }
  }, [otpCompleted, accessLoading, accessData, initiateCheckout]);

  // Loading states
  if (pricingLoading || accessLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-muted rounded" />
          <div className="h-4 w-64 bg-muted rounded" />
        </div>
      </div>
    );
  }

  // No monetization or monetization disabled - show chat
  if (
    !monetization ||
    !monetization.is_active ||
    monetization.pricing_model === "free"
  ) {
    return <>{children}</>;
  }

  // User has access - show chat
  if (accessData?.has_access) {
    return <>{children}</>;
  }

  // User doesn't have access - show purchase UI
  const priceDisplay = formatPrice(
    monetization.price_cents,
    monetization.currency,
  );
  const modelDisplay = formatPricingModel(monetization.pricing_model);

  return (
    <div className="max-w-2xl mx-auto py-8">
      <Card className="p-8 space-y-6 border-amber-200 bg-gradient-to-br from-white to-amber-50/30">
        {/* Header */}
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <div className="relative">
              <div className="absolute inset-0 bg-amber-400/20 blur-xl rounded-full" />
              <div className="relative bg-gradient-to-br from-amber-400 to-orange-500 p-4 rounded-full">
                <Lock className="w-8 h-8 text-white" />
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <h2 className="text-3xl font-bold text-gray-900">
              Premium Access Required
            </h2>
            <p className="text-gray-600">
              Get unlimited access to chat with{" "}
              {personaDisplayName || personaName}
            </p>
          </div>
        </div>

        {/* Pricing Info */}
        <div className="bg-white border border-amber-200 rounded-lg p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-sm text-gray-600">Pricing Model</p>
              <p className="text-lg font-semibold text-gray-900">
                {modelDisplay}
              </p>
            </div>
            <Badge className="bg-amber-100 text-amber-800 border-amber-300 text-lg px-4 py-2">
              <DollarSign className="w-4 h-4 mr-1" />
              {priceDisplay}
            </Badge>
          </div>

          {monetization.access_duration_days && (
            <div className="text-sm text-gray-600">
              Access Duration: {monetization.access_duration_days} days
            </div>
          )}
        </div>

        {/* Features */}
        <div className="space-y-3">
          <p className="text-sm font-medium text-gray-700">What you get:</p>
          <ul className="space-y-2">
            {[
              "Unlimited text conversations",
              "AI-powered responses",
              "Instant access after payment",
              "Secure payment via Stripe",
            ].map((feature, index) => (
              <li
                key={index}
                className="flex items-center gap-2 text-sm text-gray-600"
              >
                <Sparkles className="w-4 h-4 text-amber-600 shrink-0" />
                {feature}
              </li>
            ))}
          </ul>
        </div>

        {/* Purchase Button */}
        <Button
          onClick={handlePurchase}
          disabled={isProcessing || checkoutPending}
          size="lg"
          className="w-full text-lg py-6 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
        >
          {isProcessing || checkoutPending ? (
            "Processing..."
          ) : (
            <>
              Purchase Access for {priceDisplay}
              <ArrowRight className="w-5 h-5 ml-2" />
            </>
          )}
        </Button>

        <p className="text-xs text-center text-gray-500">
          Secure payment powered by Stripe. You&apos;ll be redirected to
          complete your purchase.
        </p>
      </Card>

      {/* OTP Wizard Modal */}
      <Dialog open={showOTPWizard} onOpenChange={setShowOTPWizard}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Sign in to Purchase</DialogTitle>
            <DialogDescription>
              Create an account or sign in to complete your purchase
            </DialogDescription>
          </DialogHeader>
          <OTPWizard
            sessionToken=""
            onComplete={handleOTPComplete}
            requireFullname={true}
            requirePhone={false}
            skipSessionLink={true}
            personaUsername={personaUsername}
          />
        </DialogContent>
      </Dialog>

      {/* Success Modal - Shows ONLY after OTP completion while creating Stripe checkout */}
      <Dialog open={showSuccessModal} onOpenChange={() => {}}>
        <DialogContent className="sm:max-w-md">
          <div className="flex flex-col items-center justify-center py-8 space-y-4">
            <div className="relative">
              <div className="absolute inset-0 bg-green-400/20 blur-xl rounded-full" />
              <div className="relative bg-gradient-to-br from-green-400 to-green-600 p-4 rounded-full">
                <CheckCircle2 className="w-12 h-12 text-white" />
              </div>
            </div>
            <div className="text-center space-y-2">
              <h3 className="text-xl font-semibold text-gray-900">
                Account Created!
              </h3>
              <p className="text-sm text-gray-600">Redirecting to payment...</p>
            </div>
            <Loader2 className="w-6 h-6 animate-spin text-amber-600" />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
