"use client";

/**
 * Claim Account Page
 * Allows auto-onboarded users to claim their account with credentials
 */

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Loader2, CheckCircle2, XCircle, AlertCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  useVerifyClaimCode,
  useCheckUsername,
  useSubmitClaim,
} from "@/lib/queries/claim";
import { useAuthStore } from "@/store/auth.store";
import { toast } from "sonner";

// Form validation schema
const claimFormSchema = z.object({
  username: z
    .string()
    .min(3, "Username must be at least 3 characters")
    .max(30, "Username must be at most 30 characters")
    .regex(/^[a-zA-Z0-9]+$/, "Username can only contain letters and numbers"),
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
  fullname: z.string(),
});

type ClaimFormValues = z.infer<typeof claimFormSchema>;

export default function ClaimAccountPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);

  // Extract claim code synchronously to prevent flash of "No Claim Code Found"
  const claimCode = searchParams.get("code");

  const [usernameStatus, setUsernameStatus] = useState<
    "idle" | "checking" | "available" | "taken"
  >("idle");
  const [usernameDebounceTimer, setUsernameDebounceTimer] =
    useState<NodeJS.Timeout | null>(null);

  // Verify claim code
  const {
    data: verifyData,
    isLoading: isVerifying,
    error: verifyError,
  } = useVerifyClaimCode(claimCode);

  // Mutations
  const checkUsernameMutation = useCheckUsername();
  const submitClaimMutation = useSubmitClaim();

  // Initialize form
  const form = useForm<ClaimFormValues>({
    resolver: zodResolver(claimFormSchema),
    defaultValues: {
      username: "",
      email: "",
      password: "",
      fullname: "",
    },
  });

  // Pre-fill form when verification succeeds
  useEffect(() => {
    if (verifyData) {
      form.reset({
        username: verifyData.username,
        email: verifyData.is_generated_email ? "" : verifyData.email,
        password: "",
        fullname: verifyData.fullname,
      });
    }
  }, [verifyData, form]);

  // Real-time username validation (debounced)
  const handleUsernameChange = (value: string) => {
    form.setValue("username", value);
    setUsernameStatus("idle");

    // Clear existing timer
    if (usernameDebounceTimer) {
      clearTimeout(usernameDebounceTimer);
    }

    // Skip validation for invalid usernames
    if (
      value.length < 3 ||
      value.length > 30 ||
      !/^[a-zA-Z0-9]+$/.test(value)
    ) {
      return;
    }

    // Don't check if it's the same as the original username
    if (value === verifyData?.username) {
      setUsernameStatus("available");
      return;
    }

    // Debounce the check
    const timer = setTimeout(() => {
      setUsernameStatus("checking");
      checkUsernameMutation.mutate(
        { username: value },
        {
          onSuccess: (data) => {
            setUsernameStatus(data.available ? "available" : "taken");
            if (!data.available) {
              form.setError("username", {
                type: "manual",
                message: "This username is already taken",
              });
            } else {
              form.clearErrors("username");
            }
          },
          onError: () => {
            setUsernameStatus("idle");
          },
        },
      );
    }, 500); // 500ms debounce

    setUsernameDebounceTimer(timer);
  };

  // Handle form submission
  const onSubmit = async (values: ClaimFormValues) => {
    if (!claimCode) {
      toast.error("Claim code is missing");
      return;
    }

    if (usernameStatus === "taken") {
      toast.error("Please choose a different username");
      return;
    }

    submitClaimMutation.mutate(
      {
        code: claimCode,
        username: values.username,
        email: values.email,
        password: values.password,
      },
      {
        onSuccess: (data) => {
          // Auto-login: Store token in localStorage and Zustand
          if (typeof window !== "undefined") {
            localStorage.setItem("auth_token", data.token);
          }

          setAuth(
            {
              id: data.user_id,
              email: data.email,
              name: data.fullname,
              username: values.username,
            },
            data.token,
          );

          toast.success(data.message);

          // Redirect to dashboard
          router.push("/dashboard");
        },
        onError: (error: Error) => {
          const errorMessage =
            (error as { response?: { data?: { message?: string } } })?.response
              ?.data?.message ||
            error?.message ||
            "Failed to claim account. Please try again.";

          toast.error("Claim Failed", {
            description: errorMessage,
          });
        },
      },
    );
  };

  // Loading state
  if (!claimCode) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <AlertCircle className="mx-auto h-12 w-12 text-yellow-500" />
          <h2 className="mt-4 text-xl font-semibold">No Claim Code Found</h2>
          <p className="mt-2 text-muted-foreground">
            Please use the claim link provided to you.
          </p>
        </div>
      </div>
    );
  }

  if (isVerifying) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <Loader2 className="mx-auto h-12 w-12 animate-spin text-primary" />
          <h2 className="mt-4 text-xl font-semibold">
            Verifying Claim Code...
          </h2>
        </div>
      </div>
    );
  }

  if (verifyError) {
    const errorMessage =
      (
        verifyError as {
          response?: { data?: { message?: string } };
          message?: string;
        }
      )?.response?.data?.message ||
      (verifyError as { message?: string })?.message ||
      "Invalid or expired claim code";

    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <XCircle className="mx-auto h-12 w-12 text-destructive" />
          <h2 className="mt-4 text-xl font-semibold">Verification Failed</h2>
          <p className="mt-2 text-muted-foreground">{errorMessage}</p>
          <p className="mt-4 text-sm text-muted-foreground">
            Please contact support if you believe this is an error.
          </p>
        </div>
      </div>
    );
  }

  // Main form
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background to-muted/20 p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight">
            Claim Your Account
          </h1>
          <p className="mt-2 text-muted-foreground">
            Set your credentials to take ownership of your expert account
          </p>
        </div>

        <div className="rounded-lg border bg-card p-6 shadow-lg">
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              {/* Full Name (Read-only) */}
              <FormField
                control={form.control}
                name="fullname"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Full Name</FormLabel>
                    <FormControl>
                      <Input {...field} disabled className="bg-muted" />
                    </FormControl>
                    <FormDescription>
                      This is your display name on the platform
                    </FormDescription>
                  </FormItem>
                )}
              />

              {/* Username */}
              <FormField
                control={form.control}
                name="username"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Username</FormLabel>
                    <FormControl>
                      <div className="relative">
                        <Input
                          {...field}
                          placeholder="johndoe"
                          onChange={(e) =>
                            handleUsernameChange(e.target.value.toLowerCase())
                          }
                          className="pr-10"
                        />
                        <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                          {usernameStatus === "checking" && (
                            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                          )}
                          {usernameStatus === "available" && (
                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                          )}
                          {usernameStatus === "taken" && (
                            <XCircle className="h-4 w-4 text-destructive" />
                          )}
                        </div>
                      </div>
                    </FormControl>
                    <FormDescription>
                      3-30 characters, alphanumeric only
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Email */}
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        type="email"
                        placeholder="john@example.com"
                      />
                    </FormControl>
                    <FormDescription>
                      You&apos;ll use this to log in
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Password */}
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        type="password"
                        placeholder="Enter a secure password"
                      />
                    </FormControl>
                    <FormDescription>Minimum 8 characters</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Submit Button */}
              <Button
                type="submit"
                className="w-full"
                disabled={
                  submitClaimMutation.isPending ||
                  usernameStatus === "checking" ||
                  usernameStatus === "taken"
                }
              >
                {submitClaimMutation.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Claiming Account...
                  </>
                ) : (
                  "Claim Account"
                )}
              </Button>
            </form>
          </Form>
        </div>

        <p className="text-center text-xs text-muted-foreground">
          By claiming this account, you agree to our Terms of Service and
          Privacy Policy
        </p>
      </div>
    </div>
  );
}
