"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { useSearchParams, useRouter } from "next/navigation";
import { PasswordStrengthMeter } from "@/components/auth/PasswordStrengthMeter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Link from "next/link";
import { useResetPassword } from "@/lib/queries/auth/useEmailAuth";
import { validatePassword } from "@/lib/utils/passwordValidation";
import { toast } from "sonner";
import { parseApiError } from "@/lib/utils/apiError";

export default function ResetPasswordPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = searchParams?.get("token");

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const resetPasswordMutation = useResetPassword();

  const handlePasswordChange = (value: string) => {
    setNewPassword(value);
    if (value.trim()) {
      const validation = validatePassword(value);
      setPasswordError(validation.error);
    } else {
      setPasswordError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!token) {
      toast.error("Invalid reset link", {
        description: "Please request a new password reset link.",
      });
      return;
    }

    if (!newPassword || !confirmPassword) {
      toast.error("Please fill in all fields");
      return;
    }

    // Validate password
    const validation = validatePassword(newPassword);
    if (!validation.isValid) {
      setPasswordError(validation.error);
      toast.error("Invalid password", {
        description: validation.error || undefined,
      });
      return;
    }

    // Check if passwords match
    if (newPassword !== confirmPassword) {
      toast.error("Passwords don't match", {
        description: "Please make sure both passwords are the same.",
      });
      return;
    }

    resetPasswordMutation.mutate(
      { token, new_password: newPassword },
      {
        onSuccess: (data) => {
          setShowSuccess(true);
          toast.success("Password reset successful!", {
            description: data.message,
          });
        },
        onError: (error) => {
          const errorMessage = parseApiError(error);

          if (
            errorMessage.includes("expired") ||
            errorMessage.includes("invalid")
          ) {
            toast.error("Reset link expired or invalid", {
              description: "Please request a new password reset link.",
              action: {
                label: "Request new link",
                onClick: () => router.push("/forgot-password"),
              },
            });
          } else {
            toast.error("Failed to reset password", {
              description: errorMessage,
            });
          }
        },
      },
    );
  };

  if (!token) {
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
              Invalid Reset Link
            </h1>
            <p className="text-gray-600 mb-6">
              This password reset link is invalid or missing.
            </p>
            <Link href="/forgot-password">
              <Button className="w-full">Request new reset link</Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

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
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Password Reset Successful!
            </h1>
            <p className="text-gray-600 mb-6">
              Your password has been reset successfully. You can now login with
              your new password.
            </p>
            <Link href="/login">
              <Button className="w-full">Go to login</Button>
            </Link>
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
            Reset Your Password
          </h1>
          <p className="text-gray-600">Enter your new password below.</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="newPassword">New Password</Label>
            <div className="relative">
              <Input
                id="newPassword"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={newPassword}
                onChange={(e) => handlePasswordChange(e.target.value)}
                disabled={resetPasswordMutation.isPending}
                className={passwordError ? "border-red-500 pr-10" : "pr-10"}
                required
                autoFocus
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 focus:outline-none"
                tabIndex={-1}
              >
                {showPassword ? (
                  <Eye className="h-4 w-4" />
                ) : (
                  <EyeOff className="h-4 w-4" />
                )}
              </button>
            </div>
            {passwordError && (
              <p className="text-sm text-red-600">{passwordError}</p>
            )}
            {!passwordError && newPassword && (
              <>
                <PasswordStrengthMeter password={newPassword} />
                <p className="text-xs text-gray-500">
                  Min 8 characters with uppercase, lowercase, and number
                </p>
              </>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm Password</Label>
            <div className="relative">
              <Input
                id="confirmPassword"
                type={showConfirmPassword ? "text" : "password"}
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={resetPasswordMutation.isPending}
                className="pr-10"
                required
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700 focus:outline-none"
                tabIndex={-1}
              >
                {showConfirmPassword ? (
                  <Eye className="h-4 w-4" />
                ) : (
                  <EyeOff className="h-4 w-4" />
                )}
              </button>
            </div>
            {confirmPassword && newPassword !== confirmPassword && (
              <p className="text-sm text-red-600">Passwords don&apos;t match</p>
            )}
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={
              resetPasswordMutation.isPending ||
              !!passwordError ||
              !newPassword ||
              !confirmPassword ||
              newPassword !== confirmPassword
            }
          >
            {resetPasswordMutation.isPending
              ? "Resetting password..."
              : "Reset password"}
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
      </div>
    </div>
  );
}
