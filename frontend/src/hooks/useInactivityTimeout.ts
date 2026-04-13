"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { trackLiveKitEvent } from "@/lib/monitoring/sentry";

/**
 * Configuration options for the inactivity timeout hook
 */
export interface UseInactivityTimeoutOptions {
  /** Time in ms before showing warning (default: 60000 = 1 minute) */
  inactivityMs?: number;
  /** Time in ms for warning countdown before disconnect (default: 30000 = 30 seconds) */
  warningMs?: number;
  /** Callback when auto-disconnect happens */
  onDisconnect: () => void;
  /** Callback when warning starts showing */
  onWarningStart?: () => void;
  /** Whether the timeout tracking is active (should be true when connected) */
  enabled: boolean;
  /** Context for Sentry tracking */
  trackingContext?: {
    username?: string;
    personaName?: string;
    mode?: string;
  };
}

/**
 * Return type for the inactivity timeout hook
 */
export interface UseInactivityTimeoutReturn {
  /** Whether to show the inactivity warning UI */
  showWarning: boolean;
  /** Remaining seconds in the warning countdown */
  remainingSeconds: number;
  /** Call this when user dismisses the warning */
  dismissWarning: () => void;
  /** Call this on any user activity to reset the timer */
  recordActivity: () => void;
  /** Whether the session was disconnected due to inactivity */
  isDisconnectedDueToInactivity: boolean;
  /** Reset the inactivity state (call before reconnecting) */
  resetInactivityState: () => void;
}

// Default timeout values
const DEFAULT_INACTIVITY_MS = 60000; // 1 minute
const DEFAULT_WARNING_MS = 30000; // 30 seconds

/**
 * Custom hook to manage inactivity detection and auto-disconnect for chat sessions.
 *
 * Flow:
 * 1. User is active → timer resets
 * 2. User inactive for inactivityMs → warning shows with countdown
 * 3. User interacts during warning → warning dismissed, timer resets
 * 4. Warning countdown expires → onDisconnect called
 */
export function useInactivityTimeout({
  inactivityMs = DEFAULT_INACTIVITY_MS,
  warningMs = DEFAULT_WARNING_MS,
  onDisconnect,
  onWarningStart,
  enabled,
  trackingContext,
}: UseInactivityTimeoutOptions): UseInactivityTimeoutReturn {
  // State for UI
  const [showWarning, setShowWarning] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(
    Math.floor(warningMs / 1000),
  );
  const [isDisconnectedDueToInactivity, setIsDisconnectedDueToInactivity] =
    useState(false);

  // Refs for timers
  const inactivityTimerRef = useRef<NodeJS.Timeout | null>(null);
  const countdownIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Refs for current values to avoid stale closures in timer callbacks
  const configRef = useRef({
    onDisconnect,
    onWarningStart,
    trackingContext,
    warningMs,
    inactivityMs,
    enabled,
    isDisconnected: false,
    showWarning: false,
    remainingSeconds: Math.floor(warningMs / 1000),
  });

  // Keep config ref up to date
  useEffect(() => {
    configRef.current = {
      ...configRef.current,
      onDisconnect,
      onWarningStart,
      trackingContext,
      warningMs,
      inactivityMs,
      enabled,
    };
  }, [
    onDisconnect,
    onWarningStart,
    trackingContext,
    warningMs,
    inactivityMs,
    enabled,
  ]);

  // Sync state to ref
  useEffect(() => {
    configRef.current.isDisconnected = isDisconnectedDueToInactivity;
  }, [isDisconnectedDueToInactivity]);

  useEffect(() => {
    configRef.current.showWarning = showWarning;
  }, [showWarning]);

  useEffect(() => {
    configRef.current.remainingSeconds = remainingSeconds;
  }, [remainingSeconds]);

  /**
   * Clear all timers
   */
  const clearAllTimers = useCallback(() => {
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
      inactivityTimerRef.current = null;
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }
  }, []);

  /**
   * Start the countdown when warning is shown
   */
  const startCountdown = useCallback(() => {
    // Clear any existing countdown
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
    }

    countdownIntervalRef.current = setInterval(() => {
      setRemainingSeconds((prev) => {
        const next = prev - 1;
        configRef.current.remainingSeconds = next;

        if (next <= 0) {
          // Countdown finished - disconnect
          if (inactivityTimerRef.current) {
            clearTimeout(inactivityTimerRef.current);
            inactivityTimerRef.current = null;
          }
          if (countdownIntervalRef.current) {
            clearInterval(countdownIntervalRef.current);
            countdownIntervalRef.current = null;
          }

          setShowWarning(false);
          configRef.current.showWarning = false;
          setIsDisconnectedDueToInactivity(true);
          configRef.current.isDisconnected = true;

          // Track disconnect in Sentry
          trackLiveKitEvent("session_disconnected_inactivity", {
            ...configRef.current.trackingContext,
          });

          // Call disconnect callback
          configRef.current.onDisconnect();
          return 0;
        }
        return next;
      });
    }, 1000);
  }, []);

  /**
   * Start the inactivity timer - uses refs to avoid recreating on every render
   */
  const startInactivityTimer = useCallback(() => {
    // Clear any existing timers
    if (inactivityTimerRef.current) {
      clearTimeout(inactivityTimerRef.current);
      inactivityTimerRef.current = null;
    }
    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
      countdownIntervalRef.current = null;
    }

    // Don't start if disabled or disconnected
    if (!configRef.current.enabled || configRef.current.isDisconnected) {
      return;
    }

    // Start new inactivity timer
    inactivityTimerRef.current = setTimeout(() => {
      const cfg = configRef.current;

      // Show warning
      const initialSeconds = Math.floor(cfg.warningMs / 1000);
      setShowWarning(true);
      cfg.showWarning = true;
      setRemainingSeconds(initialSeconds);
      cfg.remainingSeconds = initialSeconds;

      // Track warning start in Sentry
      trackLiveKitEvent("inactivity_warning_shown", {
        ...cfg.trackingContext,
      });

      // Call optional callback
      cfg.onWarningStart?.();

      // Start countdown
      startCountdown();
    }, configRef.current.inactivityMs);
  }, [startCountdown]);

  /**
   * Record user activity - resets the inactivity timer
   */
  const recordActivity = useCallback(() => {
    const cfg = configRef.current;

    // Don't do anything if disabled or disconnected
    if (!cfg.enabled || cfg.isDisconnected) {
      return;
    }

    // If warning is showing, dismiss it
    if (cfg.showWarning) {
      // Track that user dismissed warning
      trackLiveKitEvent("inactivity_warning_dismissed", {
        ...cfg.trackingContext,
        remainingSeconds: cfg.remainingSeconds,
      });

      setShowWarning(false);
      cfg.showWarning = false;
      const initialSeconds = Math.floor(cfg.warningMs / 1000);
      setRemainingSeconds(initialSeconds);
      cfg.remainingSeconds = initialSeconds;
    }

    // Restart the inactivity timer
    startInactivityTimer();
  }, [startInactivityTimer]);

  /**
   * Dismiss the warning (user clicked "I'm still here")
   */
  const dismissWarning = useCallback(() => {
    recordActivity();
  }, [recordActivity]);

  /**
   * Reset inactivity state (call before reconnecting)
   */
  const resetInactivityState = useCallback(() => {
    clearAllTimers();
    setShowWarning(false);
    configRef.current.showWarning = false;
    const initialSeconds = Math.floor(configRef.current.warningMs / 1000);
    setRemainingSeconds(initialSeconds);
    configRef.current.remainingSeconds = initialSeconds;
    setIsDisconnectedDueToInactivity(false);
    configRef.current.isDisconnected = false;
  }, [clearAllTimers]);

  // Start/stop timer based on enabled state
  useEffect(() => {
    if (enabled && !isDisconnectedDueToInactivity) {
      // Start tracking inactivity
      startInactivityTimer();
    } else {
      // Stop tracking
      clearAllTimers();
      if (!isDisconnectedDueToInactivity) {
        setShowWarning(false);
        configRef.current.showWarning = false;
      }
    }

    return () => {
      clearAllTimers();
    };
  }, [
    enabled,
    isDisconnectedDueToInactivity,
    startInactivityTimer,
    clearAllTimers,
  ]);

  return {
    showWarning,
    remainingSeconds,
    dismissWarning,
    recordActivity,
    isDisconnectedDueToInactivity,
    resetInactivityState,
  };
}
