"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { trackLiveKitEvent } from "@/lib/monitoring/sentry";

/**
 * Configuration options for the session time limit hook
 */
export interface UseSessionTimeLimitOptions {
  /** Total session duration limit in ms */
  limitMs: number;
  /** Time in ms before limit to show warning */
  warningMs: number;
  /** Callback when session limit reached */
  onLimitReached: () => void;
  /** Callback when warning should show */
  onWarningStart?: () => void;
  /** Whether the timer is active (should be true when connected) */
  enabled: boolean;
  /** Context for Sentry tracking */
  trackingContext?: {
    username?: string;
    personaName?: string;
    mode?: string;
  };
}

/**
 * Return type for the session time limit hook
 */
export interface UseSessionTimeLimitReturn {
  /** Whether to show the time limit warning UI */
  showWarning: boolean;
  /** Remaining seconds until session ends */
  remainingSeconds: number;
  /** Dismiss warning (does NOT extend session - just hides UI) */
  dismissWarning: () => void;
  /** Total elapsed time in seconds */
  elapsedSeconds: number;
  /** Whether session was terminated due to limit */
  isLimitReached: boolean;
  /** Reset the session timer (call before reconnecting) */
  resetSessionTimer: () => void;
}

/**
 * Custom hook to manage session time limits for chat sessions.
 *
 * Key difference from useInactivityTimeout:
 * - Inactivity: Timer resets on user activity
 * - Time Limit: Timer never resets, tracks total session time
 *
 * Flow:
 * 1. Session starts → timer begins counting
 * 2. Timer reaches (limitMs - warningMs) → warning shows
 * 3. Timer reaches limitMs → onLimitReached called, session ends
 * 4. Warning can be dismissed but doesn't extend time
 */
export function useSessionTimeLimit({
  limitMs,
  warningMs,
  onLimitReached,
  onWarningStart,
  enabled,
  trackingContext,
}: UseSessionTimeLimitOptions): UseSessionTimeLimitReturn {
  // State for UI
  const [showWarning, setShowWarning] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [isLimitReached, setIsLimitReached] = useState(false);
  const [warningDismissed, setWarningDismissed] = useState(false);

  // Calculate remaining seconds
  const totalLimitSeconds = Math.floor(limitMs / 1000);
  const remainingSeconds = Math.max(0, totalLimitSeconds - elapsedSeconds);

  // Refs for timer
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number | null>(null);

  // Refs for current values to avoid stale closures
  const configRef = useRef({
    onLimitReached,
    onWarningStart,
    trackingContext,
    warningMs,
    limitMs,
    enabled,
    isLimitReached: false,
    warningShown: false,
  });

  // Keep config ref up to date
  useEffect(() => {
    configRef.current = {
      ...configRef.current,
      onLimitReached,
      onWarningStart,
      trackingContext,
      warningMs,
      limitMs,
      enabled,
    };
  }, [
    onLimitReached,
    onWarningStart,
    trackingContext,
    warningMs,
    limitMs,
    enabled,
  ]);

  // Sync state to ref
  useEffect(() => {
    configRef.current.isLimitReached = isLimitReached;
  }, [isLimitReached]);

  /**
   * Clear timer
   */
  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  /**
   * Start the session timer
   */
  const startTimer = useCallback(() => {
    // Clear any existing timer
    clearTimer();

    // Don't start if disabled or already reached limit
    if (!configRef.current.enabled || configRef.current.isLimitReached) {
      return;
    }

    // Record start time
    startTimeRef.current = Date.now();

    // Update elapsed time every second
    timerRef.current = setInterval(() => {
      // Safety check for race conditions
      if (!startTimeRef.current || !timerRef.current) return;

      const cfg = configRef.current;
      const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
      setElapsedSeconds(elapsed);

      const elapsedMs = elapsed * 1000;
      const warningThreshold = cfg.limitMs - cfg.warningMs;

      // Check if we should show warning
      if (
        elapsedMs >= warningThreshold &&
        !cfg.warningShown &&
        !cfg.isLimitReached
      ) {
        cfg.warningShown = true;
        setShowWarning(true);

        // Track warning in Sentry
        trackLiveKitEvent("session_time_limit_warning_shown", {
          ...cfg.trackingContext,
          elapsedSeconds: elapsed,
          remainingSeconds: Math.floor((cfg.limitMs - elapsedMs) / 1000),
        });

        // Call optional callback
        cfg.onWarningStart?.();
      }

      // Check if limit reached
      if (elapsedMs >= cfg.limitMs && !cfg.isLimitReached) {
        cfg.isLimitReached = true;
        setIsLimitReached(true);
        setShowWarning(false);
        clearTimer();

        // Track limit reached in Sentry
        trackLiveKitEvent("session_time_limit_reached", {
          ...cfg.trackingContext,
          elapsedSeconds: elapsed,
          limitMinutes: Math.floor(cfg.limitMs / 60000),
        });

        // Call limit reached callback
        cfg.onLimitReached();
      }
    }, 1000);
  }, [clearTimer]);

  /**
   * Dismiss the warning (does not extend time)
   */
  const dismissWarning = useCallback(() => {
    setWarningDismissed(true);
    setShowWarning(false);

    trackLiveKitEvent("session_time_limit_warning_dismissed", {
      ...configRef.current.trackingContext,
      remainingSeconds,
    });
  }, [remainingSeconds]);

  /**
   * Reset the session timer (call before reconnecting)
   */
  const resetSessionTimer = useCallback(() => {
    clearTimer();
    startTimeRef.current = null;
    setElapsedSeconds(0);
    setShowWarning(false);
    setWarningDismissed(false);
    setIsLimitReached(false);
    configRef.current.isLimitReached = false;
    configRef.current.warningShown = false;
  }, [clearTimer]);

  // Start/stop timer based on enabled state
  // Note: startTimer and clearTimer are stable (useCallback with stable deps)
  // so we only need enabled and isLimitReached in the dependency array
  useEffect(() => {
    if (enabled && !isLimitReached) {
      startTimer();
    } else {
      clearTimer();
    }

    return () => {
      clearTimer();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, isLimitReached]);

  // Handle warning dismissed state - re-show if not dismissed and conditions met
  useEffect(() => {
    if (
      !warningDismissed &&
      configRef.current.warningShown &&
      !isLimitReached
    ) {
      setShowWarning(true);
    }
  }, [warningDismissed, isLimitReached]);

  return {
    showWarning: showWarning && !warningDismissed,
    remainingSeconds,
    dismissWarning,
    elapsedSeconds,
    isLimitReached,
    resetSessionTimer,
  };
}
