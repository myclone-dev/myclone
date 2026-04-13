/**
 * Guide Style Modal
 * A chat modal that matches the AssistantWidget/Guide layout:
 * - Centered avatar with animated rings
 * - Voice/Text mode toggle in header
 * - Vertical layout with inline transcript
 * - Beautiful loading and connection animations
 */

import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Mic, MessageSquare, AlertCircle, Loader2 } from "lucide-react";
import { ExpertVoiceChat } from "../../components/expert/voice/ExpertVoiceChat";
import { ExpertTextChat } from "../../components/expert/text/ExpertTextChat";
import { cn } from "../../lib/utils";
import { useTranslation } from "../../i18n";

interface GuideStyleModalProps {
  /** Expert username */
  expertUsername: string;
  /** Persona name (optional) */
  personaName?: string;
  /** Widget token for authentication */
  widgetToken: string;
  /** Expert display name */
  expertName: string;
  /** Avatar URL */
  avatarUrl?: string;
  /** Primary color for theming */
  primaryColor?: string;
  /** Whether voice is enabled */
  enableVoice?: boolean;
  /** Suggested questions for text chat */
  suggestedQuestions?: string[];
  /** Email capture settings */
  emailCaptureEnabled?: boolean;
  emailCaptureThreshold?: number;
  emailCaptureRequireFullname?: boolean;
  emailCaptureRequirePhone?: boolean;
  /** Callback when close button is clicked */
  onClose: () => void;
  /** Whether the modal is loading persona data */
  isLoading?: boolean;
  /** Whether there was an error loading persona */
  isError?: boolean;
  /** Session time limit settings */
  sessionTimeLimitEnabled?: boolean;
  sessionTimeLimitMinutes?: number;
  sessionTimeLimitWarningMinutes?: number;
  /** Custom display name for calendar booking button (e.g., "Solicitar cita") */
  calendarDisplayName?: string;
  /** Hide the close button (when the parent loader handles close) */
  hideCloseButton?: boolean;
}

export const GuideStyleModal: React.FC<GuideStyleModalProps> = ({
  expertUsername,
  personaName,
  widgetToken,
  expertName,
  avatarUrl,
  primaryColor: _primaryColor = "#000000", // Reserved for future theming
  enableVoice = true,
  suggestedQuestions,
  emailCaptureEnabled = false,
  emailCaptureThreshold = 5,
  emailCaptureRequireFullname = true,
  emailCaptureRequirePhone = false,
  onClose,
  isLoading = false,
  isError = false,
  sessionTimeLimitEnabled = false,
  sessionTimeLimitMinutes = 30,
  sessionTimeLimitWarningMinutes = 2,
  calendarDisplayName,
  hideCloseButton = false,
}) => {
  // Note: _primaryColor is reserved for future theming customization
  void _primaryColor;
  // Default to voice mode if enabled, otherwise text
  const [isVoiceMode, setIsVoiceMode] = useState(enableVoice);
  const { t } = useTranslation();
  // Container element for dialogs - uses callback ref to trigger re-render when set
  const [modalContainer, setModalContainer] = useState<HTMLDivElement | null>(
    null,
  );
  const modalRefCallback = useCallback((node: HTMLDivElement | null) => {
    if (node !== null) {
      setModalContainer(node);
    }
  }, []);

  return (
    <motion.div
      ref={modalRefCallback}
      initial={{ opacity: 0, y: 24, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 16, scale: 0.98 }}
      transition={{
        type: "spring",
        stiffness: 400,
        damping: 30,
        mass: 0.8,
      }}
      className="guide-style-modal"
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        borderRadius: "1rem",
        background: "#ffffff",
        boxShadow:
          "0 0 0 1px rgba(0, 0, 0, 0.05), 0 25px 50px -12px rgba(0, 0, 0, 0.25)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Header: Centered mode toggle with close button - responsive */}
      <div
        className="relative flex items-center justify-center border-b"
        style={{
          padding: "0.5rem 0.625rem",
          borderColor: "rgba(0, 0, 0, 0.05)",
          background: "rgba(250, 250, 250, 0.5)",
          flexShrink: 0,
          minHeight: "40px",
        }}
      >
        {/* Centered Mode Toggle - responsive sizing */}
        {enableVoice && (
          <div
            className="relative inline-flex rounded-full p-0.5 shadow-sm"
            style={{ background: "rgba(0, 0, 0, 0.05)" }}
          >
            {/* Animated background pill */}
            <motion.div
              className="absolute inset-y-0.5 rounded-full shadow-md"
              style={{
                width: "calc(50% - 2px)",
                background: "#1a1a1a",
              }}
              animate={{ x: isVoiceMode ? 2 : "calc(100% + 2px)" }}
              transition={{ type: "spring", stiffness: 400, damping: 30 }}
            />
            <button
              onClick={() => setIsVoiceMode(true)}
              className={cn(
                "relative z-10 flex items-center gap-1 sm:gap-1.5 rounded-full px-3 sm:px-4 py-1 sm:py-1.5 text-[11px] sm:text-xs font-medium transition-colors",
                isVoiceMode
                  ? "text-white"
                  : "text-gray-500 hover:text-gray-700",
              )}
            >
              <Mic className="h-3 w-3 sm:h-3.5 sm:w-3.5" />
              {t("chat.modeToggle.voice")}
            </button>
            <button
              onClick={() => setIsVoiceMode(false)}
              className={cn(
                "relative z-10 flex items-center gap-1 sm:gap-1.5 rounded-full px-3 sm:px-4 py-1 sm:py-1.5 text-[11px] sm:text-xs font-medium transition-colors",
                !isVoiceMode
                  ? "text-white"
                  : "text-gray-500 hover:text-gray-700",
              )}
            >
              <MessageSquare className="h-3 w-3 sm:h-3.5 sm:w-3.5" />
              {t("chat.modeToggle.text")}
            </button>
          </div>
        )}

        {/* Close button - positioned absolutely on the right, responsive */}
        {/* Hidden when the SDK loader handles close via its own bubble button */}
        {!hideCloseButton && (
          <button
            onClick={onClose}
            className="absolute right-1.5 sm:right-2 rounded-full p-1 sm:p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
            aria-label="Close"
          >
            <X className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
          </button>
        )}
      </div>

      {/* Chat Interface - flex: 1 to fill remaining space */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Loading state */}
        {isLoading && (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          </div>
        )}

        {/* Error state */}
        {isError && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 p-4 text-center">
            <AlertCircle className="h-8 w-8 text-red-500" />
            <p className="text-sm text-gray-500">
              {t("assistant.error.unableToLoad")}
            </p>
          </div>
        )}

        {/* Chat interface - only show when loaded */}
        {!isLoading && !isError && (
          <AnimatePresence mode="wait">
            {isVoiceMode && enableVoice ? (
              <motion.div
                key="voice"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.2 }}
                style={{
                  height: "100%",
                  width: "100%",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <ExpertVoiceChat
                  username={expertUsername}
                  expertName={expertName}
                  personaName={personaName}
                  avatarUrl={avatarUrl}
                  widgetToken={widgetToken}
                  onDisconnect={() => setIsVoiceMode(false)}
                  emailCaptureRequireFullname={emailCaptureRequireFullname}
                  emailCaptureRequirePhone={emailCaptureRequirePhone}
                  sessionTimeLimitEnabled={sessionTimeLimitEnabled}
                  sessionTimeLimitMinutes={sessionTimeLimitMinutes}
                  sessionTimeLimitWarningMinutes={
                    sessionTimeLimitWarningMinutes
                  }
                  // Force guide-style UI rendering (centered avatar, inline transcript)
                  useGuideStyle={true}
                  calendarDisplayName={calendarDisplayName}
                />
              </motion.div>
            ) : (
              <motion.div
                key="text"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                style={{
                  height: "100%",
                  width: "100%",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <ExpertTextChat
                  username={expertUsername}
                  expertName={expertName}
                  personaName={personaName}
                  avatarUrl={avatarUrl}
                  widgetToken={widgetToken}
                  suggestedQuestions={suggestedQuestions}
                  emailCaptureEnabled={emailCaptureEnabled}
                  emailCaptureThreshold={emailCaptureThreshold}
                  emailCaptureRequireFullname={emailCaptureRequireFullname}
                  emailCaptureRequirePhone={emailCaptureRequirePhone}
                  sessionTimeLimitEnabled={sessionTimeLimitEnabled}
                  sessionTimeLimitMinutes={sessionTimeLimitMinutes}
                  sessionTimeLimitWarningMinutes={
                    sessionTimeLimitWarningMinutes
                  }
                  onSwitchToVoice={
                    enableVoice ? () => setIsVoiceMode(true) : undefined
                  }
                  // Force guide-style UI rendering (compact, no borders)
                  useGuideStyle={true}
                  // Keep dialogs within the modal
                  dialogContainer={modalContainer}
                  calendarDisplayName={calendarDisplayName}
                />
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>
    </motion.div>
  );
};
