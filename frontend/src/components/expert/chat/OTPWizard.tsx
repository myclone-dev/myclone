"use client";

import { useState, KeyboardEvent, useEffect, useRef } from "react";
import { Mail, User, Phone, ShieldCheck, ArrowLeft } from "lucide-react";
import { useTranslation } from "react-i18next";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  useRequestOtp,
  useVerifyOtp,
} from "@/lib/queries/expert/chat/useVisitorAuth";
import { useProvideEmail } from "@/lib/queries/expert/chat";
import { useUpdateProfile } from "@/lib/queries/users/useUpdateProfile";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { useAuthStore } from "@/store/auth.store";

interface OTPWizardProps {
  sessionToken: string;
  widgetToken?: string;
  onComplete: () => void;
  requireFullname?: boolean;
  requirePhone?: boolean;
  skipSessionLink?: boolean; // If true, skip provide-email call (for payment flow)
  personaUsername?: string; // For whitelabel email - OTP sent from persona owner's custom domain
}

type Step = "email" | "verify" | "info";

export function OTPWizard({
  sessionToken,
  widgetToken,
  onComplete,
  requireFullname = false,
  requirePhone = false,
  skipSessionLink = false,
  personaUsername,
}: OTPWizardProps) {
  const { t } = useTranslation();
  const { isAuthenticated, isVisitor, user } = useAuthStore();
  const [currentStep, setCurrentStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [fullname, setFullname] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0);

  const requestOtpMutation = useRequestOtp();
  const verifyOtpMutation = useVerifyOtp();
  const provideEmailMutation = useProvideEmail();
  const updateProfileMutation = useUpdateProfile();
  const userMeQuery = useUserMe({ enabled: false }); // Disabled until after OTP verification

  // Use ref for onComplete to avoid infinite loops if parent doesn't memoize the callback
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  });

  // If user is already authenticated (not a visitor), skip OTP wizard entirely
  // This handles the case where a logged-in user opens a widget or persona page
  useEffect(() => {
    if (isAuthenticated && !isVisitor && user?.email) {
      // User is already logged in - complete immediately
      onCompleteRef.current();
    }
  }, [isAuthenticated, isVisitor, user]);

  // Resend cooldown timer
  useEffect(() => {
    if (resendCooldown > 0) {
      const timer = setTimeout(
        () => setResendCooldown(resendCooldown - 1),
        1000,
      );
      return () => clearTimeout(timer);
    }
  }, [resendCooldown]);

  // Don't render if user is already authenticated
  if (isAuthenticated && !isVisitor && user?.email) {
    return null;
  }

  // Handle Step 1: Request OTP
  const handleRequestOtp = async () => {
    if (!email.trim()) return;
    setError(null);

    try {
      await requestOtpMutation.mutateAsync({
        email,
        personaUsername, // For whitelabel email from persona owner's custom domain
        source: "email_capture",
      });

      // Backend now sends OTP to ALL users (creator and visitor)
      // Always proceed to OTP verification
      setCurrentStep("verify");
      setResendCooldown(60); // 60 second cooldown
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : t("email.otp.errors.sendFailed");
      setError(errorMessage);
    }
  };

  // Handle Step 2: Verify OTP
  const handleVerifyOtp = async () => {
    if (otpCode.length !== 6) return;
    setError(null);

    try {
      const response = await verifyOtpMutation.mutateAsync({ email, otpCode }); // Backend uses camelCase

      // Store visitor JWT token in sessionStorage (works in widget/iframe contexts)
      // This token identifies the specific visitor for user-specific endpoints like /users/me
      if (response.token) {
        sessionStorage.setItem("auth_token", response.token);
      }

      // Fetch user profile to check existing data
      const result = await userMeQuery.refetch();

      // Handle refetch errors or missing data - fall back to Step 3 form
      if (result.isError || !result.isSuccess) {
        // If user data fetch fails, show Step 3 form as fallback
        // This is safer than blocking the flow entirely
        setCurrentStep("info");
        return;
      }

      const userData = result.data;

      // Check if user already has all required fields
      const hasFullname =
        !requireFullname ||
        (userData.fullname && userData.fullname.trim() !== "");
      const hasPhone =
        !requirePhone || (userData.phone && userData.phone.trim() !== "");

      if (hasFullname && hasPhone) {
        // User has all required data - skip Step 3
        if (skipSessionLink) {
          // Payment flow: Just complete (visitor account already created)
          onComplete();
          return;
        }

        // Chat flow: Link session to visitor account
        await provideEmailMutation.mutateAsync({
          sessionToken,
          email,
          fullname: userData.fullname || undefined,
          phone: userData.phone || undefined,
          widgetToken,
        });
        onComplete();
        return;
      }

      // User is missing some required data - pre-fill the form with existing data
      if (userData.fullname) setFullname(userData.fullname);
      if (userData.phone) setPhone(userData.phone);

      setCurrentStep("info");
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : t("email.otp.errors.invalidCode");
      setError(errorMessage);
      setOtpCode(""); // Clear code on error
    }
  };

  // Handle Step 3: Link Session (using provide-email with JWT cookie from step 2)
  const handleLinkSession = async () => {
    if (requireFullname && !fullname.trim()) return;
    if (requirePhone && !phone.trim()) return;
    setError(null);

    try {
      // Step 1: Update user profile with fullname/phone (saves to user account)
      if (fullname.trim() || phone.trim()) {
        await updateProfileMutation.mutateAsync({
          fullname: fullname.trim() || undefined,
          phone: phone.trim() || undefined,
        });
      }

      if (skipSessionLink) {
        // Payment flow: Just complete (visitor account already created, profile updated)
        onComplete();
        return;
      }

      // Step 2: Link session to authenticated user (chat flow only)
      // The provide-email endpoint uses JWT cookie (set in step 2) to identify the user
      // and associates the anonymous session with their account
      await provideEmailMutation.mutateAsync({
        sessionToken,
        email,
        fullname: fullname.trim() || undefined,
        phone: phone.trim() || undefined,
        widgetToken,
      });
      onComplete();
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : t("email.otp.errors.linkFailed");
      setError(errorMessage);
    }
  };

  // Handle resend OTP
  const handleResendOtp = async () => {
    if (resendCooldown > 0) return;
    setError(null);

    try {
      await requestOtpMutation.mutateAsync({
        email,
        personaUsername, // For whitelabel email from persona owner's custom domain
        source: "email_capture",
      });
      setResendCooldown(60);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : t("email.otp.errors.resendFailed");
      setError(errorMessage);
    }
  };

  // Handle Enter key
  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      if (currentStep === "email" && email.trim()) {
        handleRequestOtp();
      } else if (currentStep === "verify" && otpCode.length === 6) {
        handleVerifyOtp();
      } else if (currentStep === "info") {
        handleLinkSession();
      }
    }
  };

  const isLoading =
    requestOtpMutation.isPending ||
    verifyOtpMutation.isPending ||
    provideEmailMutation.isPending ||
    updateProfileMutation.isPending ||
    userMeQuery.isFetching;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div className="shrink-0 mt-0.5">
          <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center">
            {currentStep === "verify" ? (
              <ShieldCheck className="w-5 h-5 text-ai-brown" />
            ) : (
              <Mail className="w-5 h-5 text-ai-brown" />
            )}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Step indicator */}
          <div className="flex items-center gap-2 mb-3">
            {["email", "verify", "info"].map((step) => (
              <div
                key={step}
                className={`h-1.5 flex-1 rounded-full transition-colors ${
                  currentStep === step ||
                  (step === "email" && currentStep !== "email") ||
                  (step === "verify" && currentStep === "info")
                    ? "bg-yellow-bright"
                    : "bg-gray-200"
                }`}
              />
            ))}
          </div>

          <h3 className="text-base font-semibold text-gray-900 mb-1">
            {currentStep === "email" && t("email.otp.continue")}
            {currentStep === "verify" && t("email.otp.verify")}
            {currentStep === "info" && t("email.otp.completeProfile")}
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            {currentStep === "email" && t("email.otp.verifyDescription")}
            {currentStep === "verify" && t("email.otp.codeSentTo", { email })}
            {currentStep === "info" && t("email.otp.detailsDescription")}
          </p>

          {/* Error message */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          <div className="space-y-3">
            {/* STEP 1: Email */}
            {currentStep === "email" && (
              <div>
                <Label
                  htmlFor="email"
                  className="text-xs font-medium text-gray-700 mb-1.5 block"
                >
                  {t("email.banner.emailLabel")}{" "}
                  <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="email"
                  type="email"
                  placeholder={t("email.banner.emailPlaceholder")}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={isLoading}
                  className="w-full h-10 border-gray-300 focus:border-primary focus:ring-primary/20"
                  autoFocus
                />
                <Button
                  onClick={handleRequestOtp}
                  disabled={!email.trim() || isLoading}
                  className="w-full h-10 mt-3 bg-primary hover:bg-primary/90 text-foreground font-medium shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? (
                    <LoadingSpinner size="sm" />
                  ) : (
                    t("email.otp.sendCode")
                  )}
                </Button>
              </div>
            )}

            {/* STEP 2: Verify OTP */}
            {currentStep === "verify" && (
              <div>
                <Label
                  htmlFor="otp"
                  className="text-xs font-medium text-gray-700 mb-1.5 block"
                >
                  {t("email.otp.verificationCode")}{" "}
                  <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="otp"
                  type="text"
                  inputMode="numeric"
                  placeholder="123456"
                  value={otpCode}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, "").slice(0, 6);
                    setOtpCode(value);
                  }}
                  onKeyDown={handleKeyDown}
                  disabled={isLoading}
                  className="w-full h-10 border-gray-300 focus:border-primary focus:ring-primary/20 text-center text-2xl tracking-widest font-mono placeholder:text-gray-300"
                  maxLength={6}
                  autoFocus
                />
                <div className="flex items-center justify-between mt-2">
                  <button
                    onClick={() => setCurrentStep("email")}
                    disabled={isLoading}
                    className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1 disabled:opacity-50"
                  >
                    <ArrowLeft className="w-3 h-3" />
                    {t("email.otp.changeEmail")}
                  </button>
                  <button
                    onClick={handleResendOtp}
                    disabled={isLoading || resendCooldown > 0}
                    className="text-sm text-yellow-bright hover:text-yellow-bright/80 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {resendCooldown > 0
                      ? t("email.otp.resendIn", { seconds: resendCooldown })
                      : t("email.otp.resendCode")}
                  </button>
                </div>
                <Button
                  onClick={handleVerifyOtp}
                  disabled={otpCode.length !== 6 || isLoading}
                  className="w-full h-10 mt-3 bg-primary hover:bg-primary/90 text-foreground font-medium shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? (
                    <LoadingSpinner size="sm" />
                  ) : (
                    t("email.otp.verifyCode")
                  )}
                </Button>
                {/* Loading state after OTP verification while checking profile */}
                {verifyOtpMutation.isSuccess && userMeQuery.isFetching && (
                  <div className="mt-3 flex items-center justify-center gap-2 text-sm text-gray-600">
                    <LoadingSpinner size="sm" />
                    <span>{t("email.otp.checkingProfile")}</span>
                  </div>
                )}
              </div>
            )}

            {/* STEP 3: Additional Info */}
            {currentStep === "info" && (
              <>
                <div>
                  <Label
                    htmlFor="fullname"
                    className="text-xs font-medium text-gray-700 mb-1.5 block"
                  >
                    {t("email.banner.fullnameLabel")}{" "}
                    {requireFullname ? (
                      <span className="text-red-500">*</span>
                    ) : (
                      <span className="text-gray-400 font-normal">
                        ({t("common.optional")})
                      </span>
                    )}
                  </Label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      id="fullname"
                      type="text"
                      placeholder={t("email.otp.fullNamePlaceholder")}
                      value={fullname}
                      onChange={(e) => setFullname(e.target.value)}
                      onKeyDown={handleKeyDown}
                      disabled={isLoading}
                      className="w-full h-10 pl-9 border-gray-300 focus:border-primary focus:ring-primary/20"
                      autoFocus
                    />
                  </div>
                </div>

                <div>
                  <Label
                    htmlFor="phone"
                    className="text-xs font-medium text-gray-700 mb-1.5 block"
                  >
                    {t("email.banner.phoneLabel")}{" "}
                    {requirePhone ? (
                      <span className="text-red-500">*</span>
                    ) : (
                      <span className="text-gray-400 font-normal">
                        ({t("common.optional")})
                      </span>
                    )}
                  </Label>
                  <div className="relative">
                    <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      id="phone"
                      type="tel"
                      placeholder={t("email.banner.phonePlaceholder")}
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      onKeyDown={handleKeyDown}
                      disabled={isLoading}
                      className="w-full h-10 pl-9 border-gray-300 focus:border-primary focus:ring-primary/20"
                    />
                  </div>
                </div>

                <Button
                  onClick={handleLinkSession}
                  disabled={
                    (requireFullname && !fullname.trim()) ||
                    (requirePhone && !phone.trim()) ||
                    isLoading
                  }
                  className="w-full h-10 bg-primary hover:bg-primary/90 text-foreground font-medium shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? (
                    <LoadingSpinner size="sm" />
                  ) : (
                    t("email.otp.complete")
                  )}
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
