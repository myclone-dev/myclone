"use client";

import { motion, AnimatePresence } from "framer-motion";
import { WifiOff, RefreshCw, Clock, Power } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TranscriptDownloadButton } from "./TranscriptDownloadButton";
import { useTranslation } from "@/i18n";
import type { Message } from "@/types/expert";

type DisconnectReason = "inactivity" | "manual" | "error";

interface SessionDisconnectedProps {
  /** Why the session was disconnected */
  reason: DisconnectReason;
  /** Callback to reconnect */
  onReconnect: () => void;
  /** Whether reconnection is in progress */
  isReconnecting: boolean;
  /** Whether to show the overlay */
  isVisible: boolean;
  /** Chat messages for transcript download */
  messages?: Message[];
  /** Expert name for transcript */
  expertName?: string;
  /** Username for transcript filename */
  username?: string;
  /** Persona name for transcript metadata */
  personaName?: string;
}

/**
 * Configuration for each disconnect reason (icons and styling)
 */
const reasonIconConfig: Record<
  DisconnectReason,
  {
    icon: typeof WifiOff;
    iconBg: string;
    iconColor: string;
  }
> = {
  inactivity: {
    icon: Clock,
    iconBg: "bg-yellow-light",
    iconColor: "text-yellow-600",
  },
  manual: {
    icon: Power,
    iconBg: "bg-gray-100",
    iconColor: "text-gray-600",
  },
  error: {
    icon: WifiOff,
    iconBg: "bg-red-50",
    iconColor: "text-red-500",
  },
};

/**
 * Session disconnected overlay component.
 * Shows when the LiveKit session is disconnected with a reason.
 * Allows user to reconnect and continue the conversation.
 * Provides option to download transcript.
 */
export function SessionDisconnected({
  reason,
  onReconnect,
  isReconnecting,
  isVisible,
  messages = [],
  expertName = "Expert",
  username = "user",
  personaName,
}: SessionDisconnectedProps) {
  const { t } = useTranslation();
  const iconConfig = reasonIconConfig[reason];
  const Icon = iconConfig.icon;

  // Get translated strings based on reason
  const title = t(`session.disconnected.reasons.${reason}.title`);
  const description = t(`session.disconnected.reasons.${reason}.description`);

  const hasMessages = messages.length > 0;

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="absolute inset-0 z-50 flex items-center justify-center bg-white/95 backdrop-blur-sm rounded-3xl"
          role="dialog"
          aria-modal="true"
          aria-labelledby="disconnected-title"
          aria-describedby="disconnected-description"
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            transition={{ duration: 0.2, delay: 0.05 }}
            className="text-center px-6 py-8 max-w-sm mx-4"
          >
            {/* Icon */}
            <div
              className={`mx-auto mb-6 w-16 h-16 sm:w-20 sm:h-20 rounded-full ${iconConfig.iconBg} flex items-center justify-center`}
            >
              <Icon
                className={`w-8 h-8 sm:w-10 sm:h-10 ${iconConfig.iconColor}`}
              />
            </div>

            {/* Title */}
            <h2
              id="disconnected-title"
              className="text-xl sm:text-2xl font-semibold text-gray-900 mb-3"
            >
              {title}
            </h2>

            {/* Description */}
            <p
              id="disconnected-description"
              className="text-sm sm:text-base text-gray-600 mb-6 leading-relaxed"
            >
              {description}
            </p>

            {/* Action Buttons */}
            <div className="space-y-3">
              {/* Reconnect Button */}
              <Button
                onClick={onReconnect}
                disabled={isReconnecting}
                className="w-full bg-yellow-bright hover:bg-yellow-400 text-gray-900 font-medium py-3 sm:py-4 text-sm sm:text-base disabled:opacity-70"
                size="lg"
              >
                {isReconnecting ? (
                  <>
                    <RefreshCw className="w-4 h-4 sm:w-5 sm:h-5 mr-2 animate-spin" />
                    {t("session.disconnected.reconnecting")}
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 sm:w-5 sm:h-5 mr-2" />
                    {t("session.disconnected.reconnect")}
                  </>
                )}
              </Button>

              {/* Download Transcript Button */}
              {hasMessages && (
                <TranscriptDownloadButton
                  messages={messages}
                  expertName={expertName}
                  username={username}
                  personaName={personaName}
                  variant="outline"
                  size="lg"
                  className="w-full py-3 sm:py-4 text-sm sm:text-base border-gray-300 hover:bg-gray-50"
                />
              )}
            </div>

            {/* Saved Indicator */}
            <p className="text-xs text-gray-400 mt-4 flex items-center justify-center gap-1">
              <span className="w-1.5 h-1.5 bg-green-400 rounded-full" />
              {t("session.disconnected.messagesSaved")}
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
