"use client";

import { use, useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Loader2, AlertCircle } from "lucide-react";
import { usePersonaAccessPolling } from "@/lib/queries/stripe";
import { usePersona } from "@/lib/queries/persona";
import { toast } from "sonner";

interface PageProps {
  params: Promise<{ username: string; persona_name: string }>;
  searchParams: Promise<{ session_id?: string }>;
}

/**
 * Payment Success Page
 * Polls access status after successful Stripe checkout
 * Redirects to chat interface once access is granted
 */
export default function PaymentSuccessPage({
  params,
  searchParams,
}: PageProps) {
  const { username, persona_name } = use(params);
  const { session_id } = use(searchParams);
  const router = useRouter();
  const pollingAttemptsRef = useRef(0);
  const [maxAttemptsReached, setMaxAttemptsReached] = useState(false);

  // Fetch persona details to get persona ID
  const { data: persona, isLoading: personaLoading } = usePersona(
    username,
    persona_name,
  );

  // Poll access status every 2 seconds once we have persona ID
  const { data: accessData, isLoading } = usePersonaAccessPolling(
    persona?.id || null,
  );

  // Monitor polling and redirect when access is granted
  useEffect(() => {
    if (accessData?.has_access) {
      toast.success("Payment successful! Redirecting to chat...");
      // Small delay for better UX
      setTimeout(() => {
        router.push(`/${username}/${persona_name}`);
      }, 1500);
    }
  }, [accessData, username, persona_name, router]);

  // Track polling attempts
  useEffect(() => {
    if (isLoading && persona?.id) {
      pollingAttemptsRef.current += 1;

      // Max 30 attempts (60 seconds at 2 second intervals)
      if (pollingAttemptsRef.current > 30) {
        setMaxAttemptsReached(true);
        toast.error(
          "Payment verification is taking longer than expected. Please refresh the page.",
        );
      }
    }
  }, [isLoading, persona?.id]);

  // Show error if persona not found
  useEffect(() => {
    if (!personaLoading && !persona) {
      toast.error("Persona not found");
      router.push("/");
    }
  }, [persona, personaLoading, router]);

  // Loading state while fetching persona
  if (personaLoading || !persona) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-amber-50 to-orange-50">
        <Card className="p-8 max-w-md w-full text-center space-y-6">
          <Loader2 className="w-16 h-16 mx-auto text-amber-600 animate-spin" />
          <p className="text-gray-600">Loading payment status...</p>
        </Card>
      </div>
    );
  }

  if (maxAttemptsReached) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-amber-50 to-orange-50">
        <Card className="p-8 max-w-md w-full space-y-6 border-amber-200">
          <div className="text-center space-y-4">
            <AlertCircle className="w-16 h-16 mx-auto text-amber-600" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                Verification Taking Longer
              </h1>
              <p className="text-gray-600 mt-2">
                Your payment is being processed. This can take a few moments.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <Button
              onClick={() => router.push(`/${username}/${persona_name}`)}
              className="w-full bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700"
            >
              Go to Persona Page
            </Button>
            <Button
              onClick={() => window.location.reload()}
              variant="outline"
              className="w-full"
            >
              Refresh Status
            </Button>
          </div>

          <p className="text-xs text-center text-gray-500">
            Session ID: {session_id || "N/A"}
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-amber-50 to-orange-50">
      <Card className="p-8 max-w-md w-full space-y-6 border-amber-200">
        <div className="text-center space-y-4">
          {accessData?.has_access ? (
            <>
              <CheckCircle2 className="w-16 h-16 mx-auto text-green-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  Payment Successful!
                </h1>
                <p className="text-gray-600 mt-2">
                  Your access has been granted. Redirecting to chat...
                </p>
              </div>
            </>
          ) : (
            <>
              <Loader2 className="w-16 h-16 mx-auto text-amber-600 animate-spin" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  Processing Payment
                </h1>
                <p className="text-gray-600 mt-2">
                  Please wait while we verify your payment...
                </p>
              </div>
            </>
          )}
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-gray-600">
          <p className="font-medium text-gray-900 mb-1">
            What&apos;s happening?
          </p>
          <ul className="space-y-1 text-xs">
            <li>✓ Payment received by Stripe</li>
            <li>
              {accessData?.has_access ? "✓" : "⏳"} Confirming your access...
            </li>
            <li>
              {accessData?.has_access ? "✓" : "⏳"} Preparing chat interface...
            </li>
          </ul>
        </div>

        <p className="text-xs text-center text-gray-500">
          This usually takes just a few seconds
        </p>
      </Card>
    </div>
  );
}
