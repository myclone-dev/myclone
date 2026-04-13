"use client";

import { useEffect, useMemo, useRef } from "react";
import { Phone, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useUserUsage } from "@/lib/queries/tier";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { trackVoiceUsageEvent } from "@/lib/monitoring/sentry";

// Constants for magic numbers
const VOICE_USAGE_REFRESH_INTERVAL = 60000; // 1 minute
const VOICE_USAGE_WARNING_THRESHOLD = 75; // %
const VOICE_USAGE_CRITICAL_THRESHOLD = 90; // %

/**
 * VoiceUsageIndicator Component
 * Circular indicator showing voice usage limit in the navbar
 * with popover for details and link to usage page
 */
export function VoiceUsageIndicator() {
  const {
    data: usage,
    isLoading,
    error,
  } = useUserUsage({
    refetchInterval: VOICE_USAGE_REFRESH_INTERVAL,
  });

  // Track usage warnings when thresholds are crossed
  // These refs must be called before any conditional returns (React hooks rules)
  const hasTracked75Ref = useRef(false);
  const hasTracked90Ref = useRef(false);

  // Extract values for the effect (use defaults when loading)
  const voice = usage?.voice;
  const isUnlimited = voice?.minutes_limit === -1;
  const percentage = isUnlimited ? 0 : (voice?.percentage ?? 0);
  const minutesUsed = voice?.minutes_used ?? 0;
  const minutesLimit = voice?.minutes_limit ?? 0;

  // Memoize color calculation to prevent unnecessary re-renders
  const colors = useMemo(() => {
    if (isUnlimited) {
      return {
        stroke: "stroke-emerald-500",
        bg: "bg-emerald-50",
        text: "text-emerald-600",
      };
    }
    if (percentage >= VOICE_USAGE_CRITICAL_THRESHOLD) {
      return {
        stroke: "stroke-red-500",
        bg: "bg-red-50",
        text: "text-red-600",
      };
    }
    if (percentage >= VOICE_USAGE_WARNING_THRESHOLD) {
      return {
        stroke: "stroke-orange-500",
        bg: "bg-orange-50",
        text: "text-orange-600",
      };
    }
    // Default: muted amber/yellow colors
    return {
      stroke: "stroke-amber-400",
      bg: "bg-amber-50",
      text: "text-amber-600",
    };
  }, [isUnlimited, percentage]);

  useEffect(() => {
    if (!usage || isUnlimited) return;

    // Track 75% warning (only once per session)
    if (
      percentage >= VOICE_USAGE_WARNING_THRESHOLD &&
      percentage < VOICE_USAGE_CRITICAL_THRESHOLD &&
      !hasTracked75Ref.current
    ) {
      hasTracked75Ref.current = true;
      trackVoiceUsageEvent("usage_warning_75", {
        minutesUsed,
        minutesLimit,
        percentage,
      });
    }

    // Track 90% warning (only once per session)
    if (
      percentage >= VOICE_USAGE_CRITICAL_THRESHOLD &&
      !hasTracked90Ref.current
    ) {
      hasTracked90Ref.current = true;
      trackVoiceUsageEvent("usage_warning_90", {
        minutesUsed,
        minutesLimit,
        percentage,
      });
    }
  }, [usage, percentage, minutesUsed, minutesLimit, isUnlimited]);

  // Error fallback - show inactive indicator
  if (error) {
    console.error("[VoiceUsageIndicator] Failed to load usage:", error);
    return (
      <div className="flex size-9 items-center justify-center rounded-full bg-slate-100">
        <Phone className="size-4 text-slate-400" aria-hidden="true" />
      </div>
    );
  }

  if (isLoading || !usage) {
    return <div className="size-9 animate-pulse rounded-full bg-slate-100" />;
  }

  const minutesRemaining = isUnlimited
    ? -1
    : Math.max(0, minutesLimit - minutesUsed);

  // Calculate stroke dash for circular progress
  const radius = 14;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  const formatMinutes = (mins: number) => {
    if (mins === -1) return "Unlimited";
    if (mins < 1) return `${Math.round(mins * 60)}s`;
    if (mins >= 60) return `${(mins / 60).toFixed(1)}h`;
    return `${mins.toFixed(1)}m`;
  };

  // Accessibility label for the progress indicator
  const ariaLabel = isUnlimited
    ? "Voice usage: Unlimited"
    : `Voice usage: ${percentage.toFixed(0)}% of monthly limit used`;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className={cn(
            "relative flex size-9 items-center justify-center rounded-full transition-all hover:scale-105",
            colors.bg,
          )}
          aria-label={ariaLabel}
        >
          {/* Circular Progress */}
          <svg
            className="absolute size-9 -rotate-90"
            viewBox="0 0 36 36"
            role="img"
            aria-label={ariaLabel}
          >
            {/* Background circle */}
            <circle
              cx="18"
              cy="18"
              r={radius}
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              className="text-slate-200"
            />
            {/* Progress circle */}
            {!isUnlimited && (
              <circle
                cx="18"
                cy="18"
                r={radius}
                fill="none"
                strokeWidth="3"
                strokeLinecap="round"
                className={colors.stroke}
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                style={{ transition: "stroke-dashoffset 0.5s ease" }}
                role="progressbar"
                aria-valuenow={percentage}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            )}
            {/* Unlimited indicator */}
            {isUnlimited && (
              <circle
                cx="18"
                cy="18"
                r={radius}
                fill="none"
                strokeWidth="3"
                className={colors.stroke}
              />
            )}
          </svg>
          {/* Phone icon in center - always black */}
          <Phone className="size-4 text-slate-900" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-72 p-0">
        <div className="p-4">
          {/* Header */}
          <div className="mb-4 flex items-center gap-2">
            <div
              className={cn(
                "flex size-8 items-center justify-center rounded-lg",
                colors.bg,
              )}
            >
              <Phone className={cn("size-4", colors.text)} aria-hidden="true" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-slate-900">
                Voice Chat Usage
              </h4>
              <p className="text-xs text-slate-500">Monthly voice minutes</p>
            </div>
          </div>

          {/* Usage Stats */}
          <div className="mb-4 space-y-3">
            {/* Main usage bar */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-600">Used</span>
                <span className={cn("font-semibold", colors.text)}>
                  {formatMinutes(minutesUsed)} / {formatMinutes(minutesLimit)}
                </span>
              </div>
              <div
                className="relative h-2 w-full overflow-hidden rounded-full bg-slate-100"
                role="progressbar"
                aria-valuenow={percentage}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Voice usage progress"
              >
                <div
                  className={cn(
                    "h-full transition-all duration-500",
                    isUnlimited
                      ? "bg-emerald-500"
                      : percentage >= VOICE_USAGE_CRITICAL_THRESHOLD
                        ? "bg-red-500"
                        : percentage >= VOICE_USAGE_WARNING_THRESHOLD
                          ? "bg-orange-500"
                          : "bg-amber-500",
                  )}
                  style={{
                    width: isUnlimited
                      ? "100%"
                      : `${Math.min(percentage, 100)}%`,
                  }}
                />
              </div>
            </div>

            {/* Remaining time */}
            {!isUnlimited && (
              <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                <div className="flex items-center gap-2">
                  <TrendingUp
                    className="size-4 text-slate-400"
                    aria-hidden="true"
                  />
                  <span className="text-sm text-slate-600">Remaining</span>
                </div>
                <span
                  className={cn(
                    "text-sm font-semibold",
                    minutesRemaining < 2 ? "text-red-600" : "text-slate-900",
                  )}
                >
                  {formatMinutes(minutesRemaining)}
                </span>
              </div>
            )}

            {isUnlimited && (
              <div className="flex items-center justify-center rounded-lg bg-emerald-50 px-3 py-2">
                <span className="text-sm font-medium text-emerald-600">
                  Unlimited voice minutes
                </span>
              </div>
            )}
          </div>

          {/* Reset date */}
          {usage.voice?.reset_date && (
            <p className="mb-3 text-center text-xs text-slate-500">
              Resets{" "}
              {new Date(usage.voice.reset_date).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              })}
            </p>
          )}

          {/* Link to usage page */}
          <Link
            href="/dashboard/usage"
            className="flex w-full items-center justify-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800"
          >
            View All Limits & Usage
          </Link>
        </div>
      </PopoverContent>
    </Popover>
  );
}
