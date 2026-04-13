"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { X, Mail, AlertCircle } from "lucide-react";
import { useResendVerification } from "@/lib/queries/auth/useEmailAuth";
import { toast } from "sonner";
import { parseApiError } from "@/lib/utils/apiError";

interface EmailVerificationBannerProps {
  email: string;
}

export function EmailVerificationBanner({
  email,
}: EmailVerificationBannerProps) {
  const [isDismissed, setIsDismissed] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const resendMutation = useResendVerification();

  // Check localStorage for dismissal
  useEffect(() => {
    const dismissed = localStorage.getItem(
      "email-verification-banner-dismissed",
    );
    if (dismissed === "true") {
      setIsDismissed(true);
    }
  }, []);

  // Countdown timer
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  const handleDismiss = () => {
    setIsDismissed(true);
    localStorage.setItem("email-verification-banner-dismissed", "true");
  };

  const handleResend = () => {
    resendMutation.mutate(
      { email },
      {
        onSuccess: (data) => {
          setCountdown(60); // 60 second cooldown
          toast.success("Verification email sent!", {
            description: data.message,
          });
        },
        onError: (error) => {
          const errorMessage = parseApiError(error);
          toast.error("Failed to send verification email", {
            description: errorMessage,
          });
        },
      },
    );
  };

  if (isDismissed) {
    return null;
  }

  return (
    <div className="relative bg-gradient-to-r from-yellow-50 to-orange-50 border-b border-yellow-200">
      <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3 flex-1">
            <div className="flex-shrink-0">
              <div className="h-10 w-10 rounded-full bg-yellow-100 flex items-center justify-center">
                <AlertCircle className="h-5 w-5 text-yellow-600" />
              </div>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-yellow-900">
                Verify your email address
              </p>
              <p className="text-xs text-yellow-700 mt-0.5">
                Please check your inbox at <strong>{email}</strong> and click
                the verification link to access all features.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleResend}
              disabled={resendMutation.isPending || countdown > 0}
              className="bg-white hover:bg-yellow-50 border-yellow-300 text-yellow-900 hover:text-yellow-900"
            >
              <Mail className="h-4 w-4 mr-2" />
              {countdown > 0
                ? `Resend (${countdown}s)`
                : resendMutation.isPending
                  ? "Sending..."
                  : "Resend email"}
            </Button>

            <button
              onClick={handleDismiss}
              className="flex-shrink-0 rounded-md p-1.5 text-yellow-600 hover:bg-yellow-100 focus:outline-none focus:ring-2 focus:ring-yellow-500"
              aria-label="Dismiss"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
