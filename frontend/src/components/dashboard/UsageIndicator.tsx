"use client";

import { useEffect, useMemo, useRef } from "react";
import { Gauge, MessageSquare, Phone } from "lucide-react";
import Link from "next/link";
import { useUserUsage } from "@/lib/queries/tier";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import {
  trackTextUsageEvent,
  trackVoiceUsageEvent,
} from "@/lib/monitoring/sentry";

// Constants for magic numbers
const USAGE_REFRESH_INTERVAL = 60000; // 1 minute
const USAGE_WARNING_THRESHOLD = 75; // %
const USAGE_CRITICAL_THRESHOLD = 90; // %

/**
 * Get color classes based on percentage thresholds
 */
const getColors = (percentage: number, isUnlimited: boolean) => {
  if (isUnlimited) {
    return {
      stroke: "stroke-emerald-500",
      bg: "bg-emerald-500",
      bgLight: "bg-emerald-50",
      text: "text-emerald-600",
    };
  }
  if (percentage >= USAGE_CRITICAL_THRESHOLD) {
    return {
      stroke: "stroke-red-500",
      bg: "bg-red-500",
      bgLight: "bg-red-50",
      text: "text-red-600",
    };
  }
  if (percentage >= USAGE_WARNING_THRESHOLD) {
    return {
      stroke: "stroke-orange-500",
      bg: "bg-orange-500",
      bgLight: "bg-orange-50",
      text: "text-orange-600",
    };
  }
  return {
    stroke: "stroke-slate-400",
    bg: "bg-slate-400",
    bgLight: "bg-slate-50",
    text: "text-slate-600",
  };
};

/**
 * UsageIndicator Component
 * Combined indicator showing both text and voice usage limits in the navbar
 * with a single popover for details
 */
export function UsageIndicator() {
  const {
    data: usage,
    isLoading,
    error,
  } = useUserUsage({
    refetchInterval: USAGE_REFRESH_INTERVAL,
  });

  // Track usage warnings when thresholds are crossed
  const hasTrackedText75Ref = useRef(false);
  const hasTrackedText90Ref = useRef(false);
  const hasTrackedVoice75Ref = useRef(false);
  const hasTrackedVoice90Ref = useRef(false);

  // Extract text values
  const text = usage?.text;
  const textIsUnlimited = text?.messages_limit === -1;
  const textPercentage = textIsUnlimited ? 0 : (text?.percentage ?? 0);
  const messagesUsed = text?.messages_used ?? 0;
  const messagesLimit = text?.messages_limit ?? 0;

  // Extract voice values
  const voice = usage?.voice;
  const voiceIsUnlimited = voice?.minutes_limit === -1;
  const voicePercentage = voiceIsUnlimited ? 0 : (voice?.percentage ?? 0);
  const minutesUsed = voice?.minutes_used ?? 0;
  const minutesLimit = voice?.minutes_limit ?? 0;

  // Calculate worst-case percentage for the indicator ring
  const worstPercentage = Math.max(
    textIsUnlimited ? 0 : textPercentage,
    voiceIsUnlimited ? 0 : voicePercentage,
  );
  const bothUnlimited = textIsUnlimited && voiceIsUnlimited;

  // Memoize color calculation for the main indicator
  const indicatorColors = useMemo(() => {
    return getColors(worstPercentage, bothUnlimited);
  }, [worstPercentage, bothUnlimited]);

  const textColors = useMemo(() => {
    return getColors(textPercentage, textIsUnlimited);
  }, [textPercentage, textIsUnlimited]);

  const voiceColors = useMemo(() => {
    return getColors(voicePercentage, voiceIsUnlimited);
  }, [voicePercentage, voiceIsUnlimited]);

  // Track text usage warnings
  useEffect(() => {
    if (!usage || textIsUnlimited) return;

    if (
      textPercentage >= USAGE_WARNING_THRESHOLD &&
      textPercentage < USAGE_CRITICAL_THRESHOLD &&
      !hasTrackedText75Ref.current
    ) {
      hasTrackedText75Ref.current = true;
      trackTextUsageEvent("usage_warning_75", {
        messagesUsed,
        messagesLimit,
        percentage: textPercentage,
      });
    }

    if (
      textPercentage >= USAGE_CRITICAL_THRESHOLD &&
      !hasTrackedText90Ref.current
    ) {
      hasTrackedText90Ref.current = true;
      trackTextUsageEvent("usage_warning_90", {
        messagesUsed,
        messagesLimit,
        percentage: textPercentage,
      });
    }
  }, [usage, textPercentage, messagesUsed, messagesLimit, textIsUnlimited]);

  // Track voice usage warnings
  useEffect(() => {
    if (!usage || voiceIsUnlimited) return;

    if (
      voicePercentage >= USAGE_WARNING_THRESHOLD &&
      voicePercentage < USAGE_CRITICAL_THRESHOLD &&
      !hasTrackedVoice75Ref.current
    ) {
      hasTrackedVoice75Ref.current = true;
      trackVoiceUsageEvent("usage_warning_75", {
        minutesUsed,
        minutesLimit,
        percentage: voicePercentage,
      });
    }

    if (
      voicePercentage >= USAGE_CRITICAL_THRESHOLD &&
      !hasTrackedVoice90Ref.current
    ) {
      hasTrackedVoice90Ref.current = true;
      trackVoiceUsageEvent("usage_warning_90", {
        minutesUsed,
        minutesLimit,
        percentage: voicePercentage,
      });
    }
  }, [usage, voicePercentage, minutesUsed, minutesLimit, voiceIsUnlimited]);

  // Error fallback
  if (error) {
    console.error("[UsageIndicator] Failed to load usage:", error);
    return (
      <div className="flex size-9 items-center justify-center rounded-full bg-slate-100">
        <Gauge className="size-4 text-slate-400" aria-hidden="true" />
      </div>
    );
  }

  if (isLoading || !usage) {
    return <div className="size-9 animate-pulse rounded-full bg-slate-100" />;
  }

  const messagesRemaining = textIsUnlimited
    ? -1
    : Math.max(0, messagesLimit - messagesUsed);
  const minutesRemaining = voiceIsUnlimited
    ? -1
    : Math.max(0, minutesLimit - minutesUsed);

  // Calculate stroke dash for circular progress
  const radius = 14;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset =
    circumference - (worstPercentage / 100) * circumference;

  const formatMessages = (count: number) => {
    if (count === -1) return "Unlimited";
    if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
    return count.toLocaleString();
  };

  const formatMinutes = (mins: number) => {
    if (mins === -1) return "Unlimited";
    if (mins < 1) return `${Math.round(mins * 60)}s`;
    if (mins >= 60) return `${(mins / 60).toFixed(1)}h`;
    return `${mins.toFixed(0)}m`;
  };

  const ariaLabel = bothUnlimited
    ? "Usage: Unlimited"
    : `Usage: ${worstPercentage.toFixed(0)}% of monthly limit used`;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          className={cn(
            "relative flex size-9 items-center justify-center rounded-full transition-all hover:scale-105",
            indicatorColors.bgLight,
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
            {!bothUnlimited && (
              <circle
                cx="18"
                cy="18"
                r={radius}
                fill="none"
                strokeWidth="3"
                strokeLinecap="round"
                className={indicatorColors.stroke}
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                style={{ transition: "stroke-dashoffset 0.5s ease" }}
              />
            )}
            {/* Unlimited indicator */}
            {bothUnlimited && (
              <circle
                cx="18"
                cy="18"
                r={radius}
                fill="none"
                strokeWidth="3"
                className={indicatorColors.stroke}
              />
            )}
          </svg>
          {/* Gauge icon in center */}
          <Gauge className="size-4 text-slate-900" aria-hidden="true" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="p-4">
          {/* Header */}
          <div className="mb-4 flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded-lg bg-slate-100">
              <Gauge className="size-4 text-slate-700" aria-hidden="true" />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-slate-900">
                Usage Limits
              </h4>
              <p className="text-xs text-slate-500">Monthly usage overview</p>
            </div>
          </div>

          {/* Usage Cards */}
          <div className="space-y-3">
            {/* Text Chat Usage */}
            <div className="rounded-lg border border-slate-200 p-3">
              <div className="mb-2 flex items-center gap-2">
                <div
                  className={cn(
                    "flex size-6 items-center justify-center rounded",
                    textColors.bgLight,
                  )}
                >
                  <MessageSquare
                    className={cn("size-3.5", textColors.text)}
                    aria-hidden="true"
                  />
                </div>
                <span className="text-sm font-medium text-slate-900">
                  Text Chat
                </span>
                {textIsUnlimited && (
                  <span className="ml-auto text-xs font-medium text-emerald-600">
                    Unlimited
                  </span>
                )}
              </div>
              {!textIsUnlimited && (
                <>
                  <div className="mb-1.5 flex items-center justify-between text-xs">
                    <span className="text-slate-500">
                      {formatMessages(messagesUsed)} /{" "}
                      {formatMessages(messagesLimit)}
                    </span>
                    <span className={cn("font-medium", textColors.text)}>
                      {formatMessages(messagesRemaining)} left
                    </span>
                  </div>
                  <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className={cn(
                        "h-full transition-all duration-500",
                        textColors.bg,
                      )}
                      style={{ width: `${Math.min(textPercentage, 100)}%` }}
                    />
                  </div>
                </>
              )}
            </div>

            {/* Voice Chat Usage */}
            <div className="rounded-lg border border-slate-200 p-3">
              <div className="mb-2 flex items-center gap-2">
                <div
                  className={cn(
                    "flex size-6 items-center justify-center rounded",
                    voiceColors.bgLight,
                  )}
                >
                  <Phone
                    className={cn("size-3.5", voiceColors.text)}
                    aria-hidden="true"
                  />
                </div>
                <span className="text-sm font-medium text-slate-900">
                  Voice Chat
                </span>
                {voiceIsUnlimited && (
                  <span className="ml-auto text-xs font-medium text-emerald-600">
                    Unlimited
                  </span>
                )}
              </div>
              {!voiceIsUnlimited && (
                <>
                  <div className="mb-1.5 flex items-center justify-between text-xs">
                    <span className="text-slate-500">
                      {formatMinutes(minutesUsed)} /{" "}
                      {formatMinutes(minutesLimit)}
                    </span>
                    <span className={cn("font-medium", voiceColors.text)}>
                      {formatMinutes(minutesRemaining)} left
                    </span>
                  </div>
                  <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className={cn(
                        "h-full transition-all duration-500",
                        voiceColors.bg,
                      )}
                      style={{ width: `${Math.min(voicePercentage, 100)}%` }}
                    />
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Reset date */}
          {(usage.text?.reset_date || usage.voice?.reset_date) && (
            <p className="mt-3 text-center text-xs text-slate-500">
              Resets{" "}
              {new Date(
                usage.text?.reset_date || usage.voice?.reset_date || "",
              ).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
              })}
            </p>
          )}

          {/* Link to usage page */}
          <Link
            href="/dashboard/usage"
            className="mt-3 flex w-full items-center justify-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-800"
          >
            View Details
          </Link>
        </div>
      </PopoverContent>
    </Popover>
  );
}
