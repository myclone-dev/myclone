"use client";

import { Timer } from "lucide-react";
import { cn } from "@/lib/utils";

interface SessionTimerProps {
  /** Remaining seconds in the session */
  remainingSeconds: number;
  /** Total session duration in minutes */
  totalMinutes: number;
  /** Whether the timer is active */
  isActive: boolean;
  /** Optional className for styling */
  className?: string;
  /** Show in compact mode (just time) */
  compact?: boolean;
}

/**
 * Formats seconds into MM:SS display
 */
function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

/**
 * Displays session time remaining for visitors with time limits enabled.
 * Shows a countdown timer that turns yellow/red as time runs low.
 */
export function SessionTimer({
  remainingSeconds,
  totalMinutes,
  isActive,
  className,
  compact = false,
}: SessionTimerProps) {
  if (!isActive) return null;

  // Determine color based on remaining time
  const totalSeconds = totalMinutes * 60;
  const percentRemaining = (remainingSeconds / totalSeconds) * 100;

  // Color thresholds:
  // > 25%: normal (gray)
  // 10-25%: warning (yellow/orange)
  // < 10%: critical (red)
  const isWarning = percentRemaining <= 25 && percentRemaining > 10;
  const isCritical = percentRemaining <= 10;

  const colorClass = isCritical
    ? "text-session-critical-text bg-session-critical-bg border-session-critical-border"
    : isWarning
      ? "text-session-warning-text bg-session-warning-bg border-session-warning-border"
      : "text-session-normal-text bg-session-normal-bg border-session-normal-border";

  const iconColorClass = isCritical
    ? "text-session-critical-icon"
    : isWarning
      ? "text-session-warning-icon"
      : "text-session-normal-icon";

  if (compact) {
    return (
      <div
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors",
          colorClass,
          isCritical && "animate-pulse",
          className,
        )}
      >
        <Timer className={cn("w-3 h-3", iconColorClass)} />
        <span className="tabular-nums">{formatTime(remainingSeconds)}</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium border transition-colors",
        colorClass,
        isCritical && "animate-pulse",
        className,
      )}
    >
      <Timer className={cn("w-4 h-4", iconColorClass)} />
      <span className="tabular-nums">{formatTime(remainingSeconds)}</span>
      <span className="text-xs opacity-70">remaining</span>
    </div>
  );
}
