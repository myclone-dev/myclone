"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Timer, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/i18n";

interface SessionTimeLimitWarningProps {
  /** Whether to show the warning */
  isVisible: boolean;
  /** Remaining seconds before session ends */
  remainingSeconds: number;
  /** Callback when user dismisses the warning (does NOT extend time) */
  onDismiss: () => void;
}

/**
 * Session time limit warning overlay component.
 * Shows a countdown timer warning that session will end soon.
 *
 * Key difference from InactivityWarning:
 * - This warning cannot extend the session time
 * - Dismissing only hides the UI, the timer continues
 */
export function SessionTimeLimitWarning({
  isVisible,
  remainingSeconds,
  onDismiss,
}: SessionTimeLimitWarningProps) {
  const { t } = useTranslation();
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;
  const formattedTime =
    minutes > 0
      ? `${minutes}:${seconds.toString().padStart(2, "0")}`
      : `${seconds}`;

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm rounded-3xl"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="time-limit-title"
          aria-describedby="time-limit-description"
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            transition={{ duration: 0.2, delay: 0.05 }}
            className="bg-white rounded-2xl shadow-2xl p-6 sm:p-8 mx-4 max-w-sm w-full text-center"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Timer Icon with Pulse Animation */}
            <div className="relative mx-auto mb-4 w-16 h-16 sm:w-20 sm:h-20">
              <div className="absolute inset-0 bg-session-timer-ping/50 rounded-full animate-ping" />
              <div className="relative flex items-center justify-center w-full h-full bg-session-timer-bg rounded-full">
                <Timer className="w-8 h-8 sm:w-10 sm:h-10 text-session-timer-icon" />
              </div>
            </div>

            {/* Title */}
            <h2
              id="time-limit-title"
              className="text-lg sm:text-xl font-semibold text-gray-900 mb-2"
            >
              {t("session.timeLimit.title")}
            </h2>

            {/* Description */}
            <p
              id="time-limit-description"
              className="text-sm sm:text-base text-gray-600 mb-4"
            >
              {t("session.timeLimit.description")}
            </p>

            {/* Countdown Timer */}
            <div className="mb-6" aria-live="polite" aria-atomic="true">
              <motion.div
                key={remainingSeconds}
                initial={{ scale: 1.1, opacity: 0.7 }}
                animate={{ scale: 1, opacity: 1 }}
                className="inline-flex items-center justify-center w-20 h-20 sm:w-24 sm:h-24 rounded-full bg-session-timer-countdown-bg border-2 border-session-timer-border"
              >
                <span className="text-2xl sm:text-3xl font-bold text-session-timer-text">
                  {formattedTime}
                </span>
              </motion.div>
              <p className="text-xs sm:text-sm text-gray-500 mt-2">
                {minutes > 0 ? t("common.minutes") : t("common.seconds")}
              </p>
            </div>

            {/* Dismiss Button */}
            <Button
              onClick={onDismiss}
              className="w-full bg-session-timer-btn hover:bg-session-timer-btn-hover text-white font-medium py-3 sm:py-4 text-sm sm:text-base"
              size="lg"
            >
              {t("session.timeLimit.dismiss")}
            </Button>

            {/* Info Text */}
            <div className="flex items-start gap-2 mt-4 p-3 bg-gray-50 rounded-lg text-left">
              <Info className="w-4 h-4 text-gray-500 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-gray-500">
                {t("session.timeLimit.info")}
              </p>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
