"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChatModeToggle } from "./ChatModeToggle";
import { ExpertVoiceChat } from "./voice/ExpertVoiceChat";
import { ExpertTextChat } from "./text/ExpertTextChat";

interface ExpertChatInterfaceProps {
  username: string;
  expertName: string;
  avatarUrl?: string;
  personaName?: string;
  widgetToken?: string;
  suggestedQuestions?: string[];
  // Email capture settings from persona
  emailCaptureEnabled?: boolean;
  emailCaptureThreshold?: number;
  emailCaptureRequireFullname?: boolean;
  emailCaptureRequirePhone?: boolean;
  // Session time limit settings from persona
  sessionTimeLimitEnabled?: boolean;
  sessionTimeLimitMinutes?: number;
  sessionTimeLimitWarningMinutes?: number;
  /** Whether voice chat is enabled - when false, only text chat is available */
  enableVoice?: boolean;
  /** Custom display name for calendar booking button (e.g., "Solicitar cita") */
  calendarDisplayName?: string;
}

export function ExpertChatInterface({
  username,
  expertName,
  avatarUrl,
  personaName,
  widgetToken,
  suggestedQuestions,
  emailCaptureEnabled = false,
  emailCaptureThreshold = 5,
  emailCaptureRequireFullname = true,
  emailCaptureRequirePhone = false,
  sessionTimeLimitEnabled = false,
  sessionTimeLimitMinutes = 30,
  sessionTimeLimitWarningMinutes = 2,
  enableVoice = true,
  calendarDisplayName,
}: ExpertChatInterfaceProps) {
  // Check if this is a task-based persona (should default to text chat)
  const isTaskPersona = personaName?.toLowerCase().includes("task") ?? false;

  // Default to text chat for task personas or when voice is disabled, voice chat for others
  const [isVoiceMode, setIsVoiceMode] = useState(enableVoice && !isTaskPersona);

  // In widget mode, remove max-width constraint to fill container
  const containerClass = widgetToken
    ? "w-full mx-auto"
    : "w-full max-w-4xl mx-auto";

  return (
    <div className={containerClass}>
      {/* Mode Toggle - only show when voice is enabled */}
      {enableVoice && (
        <ChatModeToggle
          isVoiceMode={isVoiceMode}
          onToggle={(isVoice) => setIsVoiceMode(isVoice)}
        />
      )}

      <AnimatePresence mode="wait">
        {!isVoiceMode || !enableVoice ? (
          <motion.div
            key="text-chat"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            <ExpertTextChat
              username={username}
              expertName={expertName}
              avatarUrl={avatarUrl}
              personaName={personaName}
              widgetToken={widgetToken}
              suggestedQuestions={suggestedQuestions}
              emailCaptureEnabled={emailCaptureEnabled}
              emailCaptureThreshold={emailCaptureThreshold}
              emailCaptureRequireFullname={emailCaptureRequireFullname}
              emailCaptureRequirePhone={emailCaptureRequirePhone}
              sessionTimeLimitEnabled={sessionTimeLimitEnabled}
              sessionTimeLimitMinutes={sessionTimeLimitMinutes}
              sessionTimeLimitWarningMinutes={sessionTimeLimitWarningMinutes}
              calendarDisplayName={calendarDisplayName}
              onSwitchToVoice={
                enableVoice ? () => setIsVoiceMode(true) : undefined
              }
            />
          </motion.div>
        ) : (
          <motion.div
            key="voice-chat"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
          >
            <ExpertVoiceChat
              username={username}
              expertName={expertName}
              avatarUrl={avatarUrl}
              personaName={personaName}
              widgetToken={widgetToken}
              onDisconnect={() => setIsVoiceMode(false)}
              emailCaptureRequireFullname={emailCaptureRequireFullname}
              emailCaptureRequirePhone={emailCaptureRequirePhone}
              sessionTimeLimitEnabled={sessionTimeLimitEnabled}
              sessionTimeLimitMinutes={sessionTimeLimitMinutes}
              sessionTimeLimitWarningMinutes={sessionTimeLimitWarningMinutes}
              calendarDisplayName={calendarDisplayName}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
