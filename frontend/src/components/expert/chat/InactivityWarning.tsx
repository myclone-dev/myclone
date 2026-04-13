"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Clock, MousePointerClick } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/i18n";

interface InactivityWarningProps {
  /** Whether to show the warning */
  isVisible: boolean;
  /** Remaining seconds before disconnect */
  remainingSeconds: number;
  /** Callback when user dismisses the warning */
  onDismiss: () => void;
}

/**
 * Inactivity warning overlay component.
 * Shows a countdown timer and allows user to dismiss by clicking.
 * Designed to be highly visible but not completely blocking.
 */
export function InactivityWarning({
  isVisible,
  remainingSeconds,
  onDismiss,
}: InactivityWarningProps) {
  const { t } = useTranslation();

  // Handle keyboard events - any key press dismisses
  useEffect(() => {
    if (!isVisible) return;

    const handleKeyPress = () => {
      onDismiss();
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [isVisible, onDismiss]);

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm rounded-3xl"
          onClick={onDismiss}
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="inactivity-title"
          aria-describedby="inactivity-description"
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            transition={{ duration: 0.2, delay: 0.05 }}
            className="bg-white rounded-2xl shadow-2xl p-6 sm:p-8 mx-4 max-w-sm w-full text-center"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Clock Icon with Pulse Animation */}
            <div className="relative mx-auto mb-4 w-16 h-16 sm:w-20 sm:h-20">
              <div className="absolute inset-0 bg-yellow-bright/20 rounded-full animate-ping" />
              <div className="relative flex items-center justify-center w-full h-full bg-yellow-light rounded-full">
                <Clock className="w-8 h-8 sm:w-10 sm:h-10 text-yellow-600" />
              </div>
            </div>

            {/* Title */}
            <h2
              id="inactivity-title"
              className="text-lg sm:text-xl font-semibold text-gray-900 mb-2"
            >
              {t("session.inactivity.title")}
            </h2>

            {/* Description */}
            <p
              id="inactivity-description"
              className="text-sm sm:text-base text-gray-600 mb-4"
            >
              {t("session.inactivity.description")}
            </p>

            {/* Countdown Timer */}
            <div className="mb-6" aria-live="polite" aria-atomic="true">
              <motion.div
                key={remainingSeconds}
                initial={{ scale: 1.2, opacity: 0.5 }}
                animate={{ scale: 1, opacity: 1 }}
                className="inline-flex items-center justify-center w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-red-50 border-2 border-red-200"
              >
                <span className="text-2xl sm:text-3xl font-bold text-red-600">
                  {remainingSeconds}
                </span>
              </motion.div>
              <p className="text-xs sm:text-sm text-gray-500 mt-2">
                {t("common.seconds")}
              </p>
            </div>

            {/* Dismiss Button */}
            <Button
              onClick={onDismiss}
              className="w-full bg-yellow-bright hover:bg-yellow-400 text-gray-900 font-medium py-3 sm:py-4 text-sm sm:text-base"
              size="lg"
            >
              <MousePointerClick className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
              {t("session.inactivity.dismiss")}
            </Button>

            {/* Hint Text */}
            <p className="text-xs text-gray-400 mt-3">
              {t("session.inactivity.hint")}
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
