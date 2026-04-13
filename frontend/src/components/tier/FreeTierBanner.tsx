"use client";

import { Crown, Sparkles, ArrowRight, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { EXTERNAL_URLS } from "@/lib/constants/urls";

interface FreeTierBannerProps {
  /** Title for the banner */
  title?: string;
  /** Description/message for the banner */
  description?: string;
  /** Whether the banner can be dismissed */
  dismissible?: boolean;
  /** Callback when dismissed */
  onDismiss?: () => void;
  /** Link to upgrade page */
  upgradeLink?: string;
  /** Custom CTA button text */
  ctaText?: string;
  /** Variant style */
  variant?: "default" | "warning" | "compact";
  /** Additional class name */
  className?: string;
  /** Show specific limit info */
  limitInfo?: {
    current: number;
    max: number;
    unit: string;
  };
}

/**
 * Banner component to show free tier limitations and upgrade CTA
 */
export function FreeTierBanner({
  title = "You're on the Free Plan",
  description = "Upgrade to unlock more features and higher limits.",
  dismissible = true,
  onDismiss,
  upgradeLink = EXTERNAL_URLS.PRICING,
  ctaText = "Upgrade Now",
  variant = "default",
  className,
  limitInfo,
}: FreeTierBannerProps) {
  const [isDismissed, setIsDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("tier-banner-dismissed") === "true";
  });

  // Sync with localStorage on mount (for SSR hydration)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const dismissed = localStorage.getItem("tier-banner-dismissed") === "true";
    if (dismissed !== isDismissed) {
      setIsDismissed(dismissed);
    }
  }, [isDismissed]);

  if (isDismissed) return null;

  const handleDismiss = () => {
    if (typeof window !== "undefined") {
      localStorage.setItem("tier-banner-dismissed", "true");
    }
    setIsDismissed(true);
    onDismiss?.();
  };

  if (variant === "compact") {
    return (
      <div
        className={cn(
          "flex items-center justify-between gap-3 rounded-lg border border-banner-yellow-border bg-banner-yellow-bg px-4 py-2",
          className,
        )}
      >
        <div className="flex items-center gap-2">
          <Crown className="size-4 text-banner-yellow-icon" />
          <span className="text-sm font-medium text-banner-yellow-text">
            {limitInfo
              ? `${limitInfo.current}/${limitInfo.max} ${limitInfo.unit} used`
              : "Free Plan"}
          </span>
        </div>
        <Button
          size="sm"
          variant="ghost"
          className="h-7 gap-1 text-xs text-banner-yellow-text hover:bg-banner-yellow-hover hover:text-banner-yellow-text"
          asChild
        >
          <a href={upgradeLink} target="_blank" rel="noopener noreferrer">
            Upgrade
            <ArrowRight className="size-3" />
          </a>
        </Button>
      </div>
    );
  }

  if (variant === "warning") {
    return (
      <Alert
        className={cn(
          "border-alert-warning-border bg-alert-warning-bg [&>svg]:text-status-warning",
          className,
        )}
      >
        <Sparkles className="size-4" />
        <AlertTitle className="text-alert-warning-text">{title}</AlertTitle>
        <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-alert-warning-text">
            {description}
            {limitInfo && (
              <span className="ml-1 font-semibold">
                ({limitInfo.current}/{limitInfo.max} {limitInfo.unit})
              </span>
            )}
          </span>
          <Button
            size="sm"
            className="w-fit gap-1.5 bg-status-warning hover:bg-status-warning/90"
            asChild
          >
            <a href={upgradeLink} target="_blank" rel="noopener noreferrer">
              {ctaText}
              <ArrowRight className="size-3.5" />
            </a>
          </Button>
        </AlertDescription>
        {dismissible && (
          <button
            onClick={handleDismiss}
            className="absolute right-2 top-2 rounded-md p-1 text-status-warning hover:bg-alert-warning-bg hover:text-alert-warning-text"
            aria-label="Dismiss banner"
          >
            <X className="size-4" />
          </button>
        )}
      </Alert>
    );
  }

  // Default variant
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border-2 border-yellow-200 bg-gradient-to-br from-yellow-50 via-amber-50 to-orange-50 p-6",
        className,
      )}
    >
      {/* Background decoration */}
      <div className="absolute -right-8 -top-8 size-32 rounded-full bg-yellow-200/30 blur-2xl" />
      <div className="absolute -bottom-8 -left-8 size-32 rounded-full bg-orange-200/30 blur-2xl" />

      <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-yellow-400 to-orange-500 shadow-lg">
            <Crown className="size-6 text-white" />
          </div>
          <div className="space-y-1">
            <h3 className="font-semibold text-gray-900">{title}</h3>
            <p className="text-sm text-gray-600">
              {description}
              {limitInfo && (
                <span className="ml-1 font-medium text-orange-700">
                  ({limitInfo.current}/{limitInfo.max} {limitInfo.unit})
                </span>
              )}
            </p>
          </div>
        </div>

        <Button
          className="w-full gap-2 bg-gradient-to-r from-yellow-500 to-orange-500 text-white shadow-md hover:from-yellow-600 hover:to-orange-600 sm:w-auto"
          asChild
        >
          <a href={upgradeLink} target="_blank" rel="noopener noreferrer">
            <Sparkles className="size-4" />
            {ctaText}
            <ArrowRight className="size-4" />
          </a>
        </Button>
      </div>

      {dismissible && (
        <button
          onClick={handleDismiss}
          className="absolute right-3 top-3 rounded-md p-1 text-gray-400 hover:bg-white/50 hover:text-gray-600"
          aria-label="Dismiss"
        >
          <X className="size-4" />
        </button>
      )}
    </div>
  );
}
