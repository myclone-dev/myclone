"use client";

import { useState, KeyboardEvent } from "react";
import { Mail, X, User, Phone } from "lucide-react";
import { LoadingSpinner } from "@/components/ui/loading-spinner";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useTranslation } from "@/i18n";

interface EmailPromptBannerProps {
  onSubmit: (email: string, fullname?: string, phone?: string) => Promise<void>;
  onDismiss: () => void;
  isLoading?: boolean;
  requireFullname?: boolean;
  requirePhone?: boolean;
}

export function EmailPromptBanner({
  onSubmit,
  onDismiss,
  isLoading = false,
  requireFullname = false,
  requirePhone = false,
}: EmailPromptBannerProps) {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [fullname, setFullname] = useState("");
  const [phone, setPhone] = useState("");

  const isFormValid = () => {
    if (!email.trim()) return false;
    if (requireFullname && !fullname.trim()) return false;
    if (requirePhone && !phone.trim()) return false;
    return true;
  };

  const handleSubmit = async () => {
    if (isFormValid() && !isLoading) {
      await onSubmit(email, fullname || undefined, phone || undefined);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSubmit();
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <div className="flex items-start gap-4">
        {/* Icon */}
        <div className="shrink-0 mt-0.5">
          <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center">
            <Mail className="w-5 h-5 text-ai-brown" />
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-semibold text-gray-900 mb-1">
            {t("email.banner.title")}
          </h3>
          <p className="text-sm text-gray-600 mb-4">
            {t("email.banner.description")}
          </p>

          <div className="space-y-3">
            {/* Email field - always required */}
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
              />
            </div>

            {/* Fullname field - always shown */}
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
                />
              </div>
            </div>

            {/* Phone field - always shown */}
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

            {/* Submit button */}
            <Button
              onClick={handleSubmit}
              disabled={!isFormValid() || isLoading}
              className="w-full h-10 bg-primary hover:bg-primary/90 text-foreground font-medium shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <LoadingSpinner size="sm" />
              ) : (
                t("email.banner.continueConversation")
              )}
            </Button>
          </div>
        </div>

        {/* Close button */}
        <button
          onClick={onDismiss}
          disabled={isLoading}
          className="shrink-0 text-gray-400 hover:text-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed p-1 rounded-lg hover:bg-gray-100"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
