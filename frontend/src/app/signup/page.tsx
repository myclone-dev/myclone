"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { Eye, EyeOff } from "lucide-react";
import { GoogleButton } from "@/components/auth/GoogleButton";
import { LinkedInButton } from "@/components/auth/LinkedInButton";
import { PasswordStrengthMeter } from "@/components/auth/PasswordStrengthMeter";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useRegister } from "@/lib/queries/auth/useEmailAuth";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { validatePassword } from "@/lib/utils/passwordValidation";
import { toast } from "sonner";
import { parseApiError } from "@/lib/utils/apiError";

export default function SignupPage() {
  const [fullname, setFullname] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const registerMutation = useRegister();
  const { data: currentUser, isLoading } = useUserMe();

  // Get account_type from URL query parameters
  const accountType = searchParams.get("account_type");

  // Redirect authenticated users to dashboard
  useEffect(() => {
    if (!isLoading && currentUser) {
      router.push("/dashboard");
    }
  }, [currentUser, isLoading, router]);

  const handlePasswordChange = (value: string) => {
    setPassword(value);
    if (value.trim()) {
      const validation = validatePassword(value);
      setPasswordError(validation.error);
    } else {
      setPasswordError(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate fields
    if (!fullname.trim() || !email.trim() || !password || !confirmPassword) {
      toast.error("Please fill in all required fields");
      return;
    }

    // Check if passwords match
    if (password !== confirmPassword) {
      toast.error("Passwords don't match", {
        description: "Please make sure both passwords are the same.",
      });
      return;
    }

    // Validate password
    const validation = validatePassword(password);
    if (!validation.isValid) {
      setPasswordError(validation.error);
      toast.error("Invalid password", {
        description: validation.error || undefined,
      });
      return;
    }

    // Submit registration
    registerMutation.mutate(
      {
        email: email.trim(),
        password,
        fullname: fullname.trim(),
        ...(accountType && { account_type: accountType }),
      },
      {
        onSuccess: () => {
          setShowSuccess(true);
          toast.success("Registration successful!", {
            description:
              "Please check your email to verify your account.",
          });
        },
        onError: (error) => {
          const errorMessage = parseApiError(error);
          toast.error("Registration failed", {
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
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-gray-900 mb-2">
              Check Your Email
            </h1>
            <p className="text-gray-600 mb-6">
              We&apos;ve sent a verification link to <strong>{email}</strong>
            </p>
            <p className="text-sm text-gray-500 mb-8">
              Click the link in the email to verify your account and get
              started.
            </p>
            <div className="space-y-3">
              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  setShowSuccess(false);
                  setFullname("");
                  setEmail("");
                  setPassword("");
                  setConfirmPassword("");
                }}
              >
                Back to signup
              </Button>
              <Link
                href="/login"
                className="block"
              >
                <Button variant="ghost" className="w-full">
                  Go to login
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

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
            Create Your Clone
          </h1>
          <p className="text-gray-600">Get started in just a few seconds</p>
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
              Or sign up with email
            </span>
          </div>
        </div>

        {/* Registration Form */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="fullname">Full Name *</Label>
            <Input
              id="fullname"
              type="text"
              placeholder="John Doe"
              value={fullname}
              onChange={(e) => setFullname(e.target.value)}
              disabled={registerMutation.isPending}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email *</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={registerMutation.isPending}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password *</Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••"
                value={password}
                onChange={(e) => handlePasswordChange(e.target.value)}
                disabled={registerMutation.isPending}
                className={passwordError ? "border-red-500 pr-10" : "pr-10"}
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
            {passwordError && (
              <p className="text-sm text-red-600">{passwordError}</p>
            )}
            {!passwordError && password && (
              <>
                <PasswordStrengthMeter password={password} />
                <p className="text-xs text-gray-500">
                  Min 8 characters with uppercase, lowercase, and number
                </p>
              </>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm Password *</Label>
            <div className="relative">
              <Input
                id="confirmPassword"
                type={showConfirmPassword ? "text" : "password"}
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                disabled={registerMutation.isPending}
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
            {confirmPassword && password !== confirmPassword && (
              <p className="text-sm text-red-600">Passwords don&apos;t match</p>
            )}
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={
              registerMutation.isPending ||
              !!passwordError ||
              !password ||
              !confirmPassword ||
              password !== confirmPassword
            }
          >
            {registerMutation.isPending
              ? "Creating your clone..."
              : "Create My Clone"}
          </Button>
        </form>

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

        <div className="mt-6 text-center">
          <p className="text-sm text-gray-600">
            Already have an account?{" "}
            <Link
              href="/login"
              className="text-ai-brown hover:text-ai-brown/80 font-medium"
            >
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
