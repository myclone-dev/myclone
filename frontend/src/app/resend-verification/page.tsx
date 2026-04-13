"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Link from "next/link";
import { useResendVerification } from "@/lib/queries/auth/useEmailAuth";
import { toast } from "sonner";
import { parseApiError } from "@/lib/utils/apiError";

export default function ResendVerificationPage() {
  const searchParams = useSearchParams();
  const emailParam = searchParams?.get("email");

  const [email, setEmail] = useState(emailParam || "");
  const [showSuccess, setShowSuccess] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const resendMutation = useResendVerification();

  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email.trim()) {
      toast.error("Please enter your email address");
      return;
    }

    resendMutation.mutate(
      { email: email.trim() },
      {
        onSuccess: (data) => {
          setShowSuccess(true);
          setCountdown(60); // 60 second cooldown
          toast.success("Verification email sent!", {
            description: data.message,
          });
        },
        onError: (error) => {
          const errorMessage = parseApiError(error);

          if (errorMessage.includes("already verified")) {
            toast.error("Email already verified", {
              description: "You can now login to your account.",
              action: {
                label: "Go to login",
                onClick: () => (window.location.href = "/login"),
              },
            });
          } else {
            toast.error("Failed to send verification email", {
              description: errorMessage,
            });
          }
        },
      },
    );
  };

  if (showSuccess) {
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
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Verification Email Sent!
            </h1>
            <p className="text-gray-600 mb-2">
              We&apos;ve sent a new verification link to{" "}
              <strong>{email}</strong>
            </p>
            <p className="text-sm text-gray-500 mb-6">
              Click the link in the email to verify your account.
            </p>

            {countdown > 0 && (
              <div className="mb-6 p-3 bg-blue-50 rounded-lg border border-blue-200">
                <p className="text-sm text-blue-800">
                  You can request another email in <strong>{countdown}s</strong>
                </p>
              </div>
            )}

            <div className="space-y-3">
              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  setShowSuccess(false);
                }}
                disabled={countdown > 0}
              >
                {countdown > 0 ? `Resend in ${countdown}s` : "Resend email"}
              </Button>
              <Link href="/login" className="block">
                <Button variant="ghost" className="w-full">
                  Back to login
                </Button>
              </Link>
            </div>

            <div className="mt-6 p-4 bg-yellow-50 rounded-lg border border-yellow-200">
              <p className="text-sm text-yellow-800">
                <strong>Tip:</strong> Check your spam folder if you don&apos;t
                see the email within a few minutes.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-linear-to-br from-yellow-light via-peach-cream to-peach-light flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
        <div className="text-center mb-8">
          <div className="mx-auto w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mb-4">
            <svg
              className="w-8 h-8 text-primary"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
              />
            </svg>
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Resend Verification Email
          </h1>
          <p className="text-gray-600">
            Enter your email to receive a new verification link.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email Address</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={resendMutation.isPending}
              required
              autoFocus
            />
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={resendMutation.isPending}
          >
            {resendMutation.isPending
              ? "Sending verification email..."
              : "Send verification email"}
          </Button>
        </form>

        <div className="mt-6 text-center">
          <Link
            href="/login"
            className="text-sm text-ai-brown hover:text-ai-brown/80 font-medium"
          >
            ← Back to login
          </Link>
        </div>

        <div className="mt-8 space-y-3">
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h3 className="text-sm font-semibold text-blue-900 mb-1">
              Didn&apos;t receive the email?
            </h3>
            <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
              <li>Check your spam or junk folder</li>
              <li>Make sure you entered the correct email</li>
              <li>Wait a few minutes for the email to arrive</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
