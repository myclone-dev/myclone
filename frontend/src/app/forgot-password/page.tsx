"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Link from "next/link";
import { useForgotPassword } from "@/lib/queries/auth/useEmailAuth";
import { toast } from "sonner";
import { parseApiError } from "@/lib/utils/apiError";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [showSuccess, setShowSuccess] = useState(false);
  const forgotPasswordMutation = useForgotPassword();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email.trim()) {
      toast.error("Please enter your email address");
      return;
    }

    forgotPasswordMutation.mutate(
      { email: email.trim() },
      {
        onSuccess: (data) => {
          setShowSuccess(true);
          toast.success("Check your email", {
            description: data.message,
          });
        },
        onError: (error) => {
          const errorMessage = parseApiError(error);
          toast.error("Failed to send reset link", {
            description: errorMessage,
          });
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
              Check Your Email
            </h1>
            <p className="text-gray-600 mb-2">
              If an account exists with <strong>{email}</strong>, you&apos;ll
              receive a password reset link shortly.
            </p>
            <p className="text-sm text-gray-500 mb-8">
              The link will expire in 1 hour.
            </p>
            <div className="space-y-3">
              <Link href="/login" className="block">
                <Button className="w-full">Back to login</Button>
              </Link>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  setShowSuccess(false);
                  setEmail("");
                }}
              >
                Try different email
              </Button>
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
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Forgot Password?
          </h1>
          <p className="text-gray-600">
            No worries! Enter your email and we&apos;ll send you a reset link.
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
              disabled={forgotPasswordMutation.isPending}
              required
              autoFocus
            />
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={forgotPasswordMutation.isPending}
          >
            {forgotPasswordMutation.isPending
              ? "Sending reset link..."
              : "Send reset link"}
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

        <div className="mt-8 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <p className="text-sm text-blue-800">
            <strong>Tip:</strong> Check your spam folder if you don&apos;t see
            the email within a few minutes.
          </p>
        </div>
      </div>
    </div>
  );
}
