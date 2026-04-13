"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { Eye, EyeOff } from "lucide-react";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { LinkedInButton } from "@/components/auth/LinkedInButton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useEmailLogin } from "@/lib/queries/auth/useEmailAuth";
import { useAuthStore } from "@/store/auth.store";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { toast } from "sonner";
import * as Sentry from "@sentry/nextjs";
import { parseApiError } from "@/lib/utils/apiError";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectUrl = searchParams.get("redirect");
  const queryClient = useQueryClient();
  const { setAuth } = useAuthStore();
  const loginMutation = useEmailLogin();
  const { data: currentUser, isLoading } = useUserMe();

  // Redirect authenticated users based on account type or redirect URL
  useEffect(() => {
    if (!isLoading && currentUser) {
      if (redirectUrl) {
        router.push(redirectUrl);
      } else if (currentUser.account_type === "visitor") {
        router.push("/visitor");
      } else {
        router.push("/dashboard");
      }
    }
  }, [currentUser, isLoading, router, redirectUrl]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email.trim() || !password) {
      toast.error("Please fill in all fields");
      return;
    }

    loginMutation.mutate(
      { email: email.trim(), password },
      {
        onSuccess: async (data) => {
          // Set auth state with account_type
          setAuth(
            {
              id: data.user_id,
              email: data.email,
              name: data.fullname,
              account_type: data.account_type,
            },
            data.token,
          );

          // CRITICAL: Clear stale user query cache to force fresh fetch
          queryClient.removeQueries({ queryKey: ["user", "me"] });

          // Set hasOnboarded cookie for cross-domain CTA experience (creators only)
          if (data.account_type !== "visitor") {
            try {
              await fetch("/api/cookies/set-onboarded", {
                method: "POST",
                credentials: "include",
              });
            } catch (error) {
              Sentry.captureException(error, {
                tags: { operation: "set_onboarded_cookie" },
                contexts: {
                  auth: { flow: "login", accountType: data.account_type },
                },
              });
              // Don't block login flow if cookie setting fails
            }
          }

          toast.success("Login successful!");

          // Route based on context
          if (data.account_type === "visitor") {
            router.push("/visitor");
          } else {
            router.push("/dashboard");
          }
        },
        onError: (error) => {
          const errorMessage = parseApiError(error);

          // Handle specific error cases
          if (errorMessage.includes("not verified")) {
            toast.error("Email not verified", {
              description: "Please check your email and verify your account.",
              action: {
                label: "Resend",
                onClick: () =>
                  router.push(`/resend-verification?email=${email}`),
              },
            });
          } else if (errorMessage.includes("locked")) {
            toast.error("Account locked", {
              description:
                "Too many failed login attempts. Please try again in 15 minutes.",
            });
          } else {
            toast.error("Login failed", {
              description: errorMessage,
            });
          }
        },
      },
    );
  };

  return (
    <div className="min-h-screen bg-linear-to-br from-yellow-light via-peach-cream to-peach-light flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
        {/* Logo */}
        <div className="flex justify-center mb-6">
          <Image
            src="/myclone-logo.svg"
            alt="MyClone"
            width={120}
            height={32}
            priority
          />
        </div>

        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Welcome Back
          </h1>
          <p className="text-gray-600">Sign in to access your expert clone</p>
        </div>

        {/* OAuth Buttons - Primary */}
        <div className="space-y-3">
          <GoogleButton className="w-full" />
          <LinkedInButton className="w-full" />
        </div>

        {/* Divider */}
        <div className="relative my-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300" />
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-white text-gray-500">
              Or sign in with email
            </span>
          </div>
        </div>

        {/* Email/Password Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email or Username</Label>
            <Input
              id="email"
              type="text"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={loginMutation.isPending}
              required
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="password">Password</Label>
              <Link
                href="/forgot-password"
                className="text-sm text-ai-brown hover:text-ai-brown/80"
              >
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loginMutation.isPending}
                className="pr-10"
                required
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
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={loginMutation.isPending}
          >
            {loginMutation.isPending ? "Signing in..." : "Sign in"}
          </Button>
        </form>

        <div className="mt-6 text-center">
          <p className="text-sm text-gray-600">
            Don&apos;t have an account?{" "}
            <Link
              href="/signup"
              className="text-ai-brown hover:text-ai-brown/80 font-medium"
            >
              Sign up
            </Link>
          </p>
        </div>

        <p className="text-xs text-center text-gray-500 mt-6">
          By continuing, you agree to our{" "}
          <Link href="/terms" className="text-ai-brown hover:underline">
            Terms of Service
          </Link>{" "}
          and{" "}
          <Link href="/privacy" className="text-ai-brown hover:underline">
            Privacy Policy
          </Link>
        </p>
      </div>
    </div>
  );
}
