"use client";

import { useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { useVerifyEmail } from "@/lib/queries/auth/useEmailAuth";
import { useAuthStore } from "@/store/auth.store";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function VerifyEmailPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const token = searchParams?.get("token");
  const { setAuth } = useAuthStore();

  const { data, isLoading, error } = useVerifyEmail(token);

  useEffect(() => {
    // Set auth state and redirect after successful verification
    if (data) {
      setAuth(
        {
          id: data.user_id,
          email: data.email,
          name: data.fullname,
          account_type: data.account_type,
        },
        data.token,
      );

      // Clear stale user query cache
      queryClient.removeQueries({ queryKey: ["user", "me"] });

      // Set hasOnboarded cookie for cross-domain CTA experience (creators only)
      if (data.account_type !== "visitor") {
        fetch("/api/cookies/set-onboarded", {
          method: "POST",
          credentials: "include",
        }).catch((cookieError) => {
          Sentry.captureException(cookieError, {
            tags: { operation: "set_onboarded_cookie" },
            contexts: {
              auth: { flow: "verify_email", accountType: data.account_type },
            },
          });
          // Don't block the flow if cookie setting fails
        });
      }

      setTimeout(() => {
        // Route based on account type
        if (data.account_type === "visitor") {
          router.push("/visitor");
        } else {
          router.push("/expert/onboarding");
        }
      }, 2000);
    }
  }, [data, router, setAuth, queryClient]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-linear-to-br from-yellow-light via-peach-cream to-peach-light flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center">
            <div className="mx-auto w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mb-4 animate-pulse">
              <svg
                className="w-8 h-8 text-primary animate-spin"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Verifying Your Email
            </h1>
            <p className="text-gray-600">
              Please wait while we verify your account...
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-linear-to-br from-yellow-light via-peach-cream to-peach-light flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center">
            <div className="mx-auto w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4">
              <svg
                className="w-8 h-8 text-red-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Verification Failed
            </h1>
            <p className="text-gray-600 mb-6">
              {error.message ||
                "The verification link is invalid or has expired."}
            </p>
            <div className="space-y-3">
              <Link href="/signup" className="block">
                <Button className="w-full">Try signing up again</Button>
              </Link>
              <Link href="/login" className="block">
                <Button variant="outline" className="w-full">
                  Back to login
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (data) {
    return (
      <div className="min-h-screen bg-linear-to-br from-yellow-light via-peach-cream to-peach-light flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center">
            <div className="mx-auto w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mb-4">
              <svg
                className="w-8 h-8 text-green-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Email Verified!
            </h1>
            <p className="text-gray-600 mb-2">
              Welcome, <strong>{data.fullname}</strong>!
            </p>
            <p className="text-sm text-gray-500 mb-6">
              Your account has been verified successfully.{" "}
              {data.account_type === "visitor"
                ? "Redirecting..."
                : "Redirecting to onboarding..."}
            </p>
            <Link
              href={
                data.account_type === "visitor"
                  ? "/visitor"
                  : "/expert/onboarding"
              }
            >
              <Button className="w-full">
                {data.account_type === "visitor"
                  ? "Continue"
                  : "Complete Setup"}
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
