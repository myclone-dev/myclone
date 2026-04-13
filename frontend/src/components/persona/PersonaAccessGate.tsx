"use client";

import { useState } from "react";
import {
  Shield,
  Mail,
  Lock,
  ArrowRight,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  useRequestAccess,
  useVerifyAccess,
} from "@/lib/queries/access-control";
import { toast } from "sonner";
import { isValidEmail } from "@/lib/utils/validation";

interface PersonaAccessGateProps {
  username: string;
  personaName: string;
  onAccessGranted: () => void;
}

export function PersonaAccessGate({
  username,
  personaName,
  onAccessGranted,
}: PersonaAccessGateProps) {
  const [step, setStep] = useState<"email" | "otp" | "unauthorized">("email");
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const requestAccess = useRequestAccess();
  const verifyAccess = useVerifyAccess();

  const handleRequestAccess = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email.trim()) {
      toast.error("Email required");
      return;
    }

    // Email format validation using shared utility
    if (!isValidEmail(email)) {
      toast.error("Please enter a valid email address");
      return;
    }

    requestAccess.mutate(
      {
        username,
        personaName,
        email: email.trim(),
        firstName: firstName.trim() || undefined,
        lastName: lastName.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success("Verification code sent!", {
            description: `Check ${email} for your one-time code`,
          });
          setStep("otp");
        },
        onError: (
          error: Error & {
            response?: {
              status?: number;
              data?: { detail?: string; message?: string };
            };
          },
        ) => {
          // Check if it's a 403 Forbidden error (email not in whitelist)
          if (
            error.response?.status === 403 ||
            error.message.includes("not authorized")
          ) {
            // Extract clean error message from backend
            const cleanMessage =
              error.response?.data?.detail ||
              error.response?.data?.message ||
              "Your email is not authorized to access this persona.";
            setErrorMessage(cleanMessage);
            setStep("unauthorized");
          } else {
            toast.error("Access request failed", {
              description: error.message,
            });
          }
        },
      },
    );
  };

  const handleVerifyAccess = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!otpCode.trim()) {
      toast.error("Verification code required");
      return;
    }

    verifyAccess.mutate(
      {
        username,
        personaName,
        email: email.trim(),
        otpCode: otpCode.trim(),
        firstName: firstName.trim() || undefined,
        lastName: lastName.trim() || undefined,
      },
      {
        onSuccess: (data) => {
          toast.success("Access granted!", {
            description: data.visitorName
              ? `Welcome, ${data.visitorName}!`
              : "You can now chat with this persona",
          });
          onAccessGranted();
        },
        onError: (
          error: Error & {
            response?: {
              status?: number;
              data?: { detail?: string; message?: string };
            };
          },
        ) => {
          // Check if it's a 403 Forbidden error (email not in whitelist)
          if (
            error.response?.status === 403 ||
            error.message.includes("not authorized")
          ) {
            // Extract clean error message from backend
            const cleanMessage =
              error.response?.data?.detail ||
              error.response?.data?.message ||
              "Your email is not authorized to access this persona.";
            setErrorMessage(cleanMessage);
            setStep("unauthorized");
          } else {
            toast.error("Verification failed", {
              description: error.message,
            });
          }
        },
      },
    );
  };

  return (
    <div className="flex items-center justify-center min-h-[600px] p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <div className="flex size-16 items-center justify-center rounded-full bg-yellow-100">
              <Shield className="size-8 text-yellow-600" />
            </div>
          </div>
          <CardTitle className="text-2xl">Private Persona</CardTitle>
          <CardDescription>
            This persona requires email verification to access
          </CardDescription>
        </CardHeader>

        <CardContent>
          {step === "email" && (
            <form onSubmit={handleRequestAccess} className="space-y-4">
              <Alert className="bg-yellow-50/30 border-yellow-200/50">
                <Mail className="size-4 text-yellow-600/60" />
                <AlertDescription className="text-sm text-gray-600">
                  Enter your email to receive a one-time verification code
                </AlertDescription>
              </Alert>

              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">
                    Email Address <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label htmlFor="firstName">First Name</Label>
                    <Input
                      id="firstName"
                      type="text"
                      placeholder="John"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="lastName">Last Name</Label>
                    <Input
                      id="lastName"
                      type="text"
                      placeholder="Doe"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <Button
                type="submit"
                className="w-full gap-2 bg-yellow-bright text-black hover:bg-yellow-bright/90 cursor-pointer"
                disabled={requestAccess.isPending}
              >
                {requestAccess.isPending ? (
                  "Sending code..."
                ) : (
                  <>
                    Request Access
                    <ArrowRight className="size-4" />
                  </>
                )}
              </Button>
            </form>
          )}

          {step === "otp" && (
            <form onSubmit={handleVerifyAccess} className="space-y-4">
              <Alert className="bg-green-50 border-green-200">
                <CheckCircle2 className="size-4 text-green-600" />
                <AlertDescription className="text-sm text-green-900">
                  Verification code sent to <strong>{email}</strong>
                </AlertDescription>
              </Alert>

              <div className="space-y-2">
                <Label htmlFor="otpCode">
                  Verification Code <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="otpCode"
                  type="text"
                  placeholder="Enter 6-digit code"
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  maxLength={6}
                  required
                  autoFocus
                />
                <p className="text-xs text-muted-foreground">
                  Check your email inbox for the verification code
                </p>
              </div>

              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  className="flex-1 cursor-pointer"
                  onClick={() => {
                    setStep("email");
                    setOtpCode("");
                  }}
                  disabled={verifyAccess.isPending}
                >
                  Back
                </Button>
                <Button
                  type="submit"
                  className="flex-1 gap-2 bg-yellow-bright text-black hover:bg-yellow-bright/90 cursor-pointer"
                  disabled={verifyAccess.isPending}
                >
                  {verifyAccess.isPending ? (
                    "Verifying..."
                  ) : (
                    <>
                      <Lock className="size-4" />
                      Verify
                    </>
                  )}
                </Button>
              </div>

              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="w-full text-xs cursor-pointer"
                onClick={() =>
                  handleRequestAccess({
                    preventDefault: () => {},
                  } as React.FormEvent)
                }
                disabled={requestAccess.isPending}
              >
                Didn&apos;t receive code? Resend
              </Button>
            </form>
          )}

          {step === "unauthorized" && (
            <div className="space-y-4">
              <Alert className="bg-red-50 border-red-200">
                <XCircle className="size-4 text-red-600" />
                <AlertDescription className="text-sm text-red-900">
                  {errorMessage ||
                    "Your email is not authorized to access this persona."}
                </AlertDescription>
              </Alert>

              <Button
                type="button"
                variant="outline"
                className="w-full cursor-pointer"
                onClick={() => {
                  setStep("email");
                  setEmail("");
                  setFirstName("");
                  setLastName("");
                  setErrorMessage("");
                }}
              >
                Try Different Email
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
