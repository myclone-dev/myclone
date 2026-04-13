"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Mic, MessageSquare, AlertCircle, Loader2 } from "lucide-react";
import { ExpertVoiceChat } from "@/components/expert/voice/ExpertVoiceChat";
import { ExpertTextChat } from "@/components/expert/text/ExpertTextChat";
import { usePersona } from "@/lib/queries/persona";
import { cn } from "@/lib/utils";
import { GUIDE_PERSONA, GUIDE_WIDGET_TOKEN } from "./types";

interface AssistantPanelProps {
  /** Handler to close the panel */
  onClose: () => void;
}

/**
 * Assistant panel with both text and voice chat modes
 * Follows the embed widget pattern for proper flex layout
 */
export function AssistantPanel({ onClose }: AssistantPanelProps) {
  const [isVoiceMode, setIsVoiceMode] = useState(true);

  // Fetch persona details to get the avatar
  const {
    data: persona,
    isLoading: isPersonaLoading,
    isError: isPersonaError,
  } = usePersona(GUIDE_PERSONA.username, GUIDE_PERSONA.personaName);
  const avatarUrl = persona?.avatar;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.95 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={cn(
        "rounded-2xl bg-background shadow-2xl",
        "border border-border",
        "overflow-hidden",
      )}
      style={{
        width: "420px",
        maxWidth: "calc(100vw - 3rem)",
        height: "700px",
        maxHeight: "calc(100vh - 6rem)",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header: Centered mode toggle with close button */}
      <div
        className="relative flex items-center justify-center px-3 py-2.5 border-b border-border/30 bg-muted/30"
        style={{ flexShrink: 0 }}
      >
        {/* Centered Mode Toggle */}
        <div className="relative inline-flex rounded-full bg-muted p-0.5 shadow-sm">
          {/* Animated background pill */}
          <motion.div
            className="absolute inset-y-0.5 w-[calc(50%-2px)] rounded-full bg-foreground shadow-md"
            animate={{ x: isVoiceMode ? 2 : "calc(100% + 2px)" }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
          />
          <button
            onClick={() => setIsVoiceMode(true)}
            className={cn(
              "relative z-10 flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium transition-colors",
              isVoiceMode
                ? "text-background"
                : "text-muted-foreground hover:text-foreground/70",
            )}
          >
            <Mic className="h-3.5 w-3.5" />
            Voice
          </button>
          <button
            onClick={() => setIsVoiceMode(false)}
            className={cn(
              "relative z-10 flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-medium transition-colors",
              !isVoiceMode
                ? "text-background"
                : "text-muted-foreground hover:text-foreground/70",
            )}
          >
            <MessageSquare className="h-3.5 w-3.5" />
            Text
          </button>
        </div>

        {/* Close button - positioned absolutely on the right */}
        <button
          onClick={onClose}
          className="absolute right-2 rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Chat Interface - flex: 1 to fill remaining space, minHeight: 0 for proper overflow */}
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
        {isPersonaLoading && (
          <div className="flex flex-1 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Error state */}
        {isPersonaError && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 p-4 text-center">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <p className="text-sm text-muted-foreground">
              Unable to load assistant. Please try again later.
            </p>
          </div>
        )}

        {/* Chat interface - only show when persona is loaded */}
        {!isPersonaLoading && !isPersonaError && (
          <AnimatePresence mode="wait">
            {isVoiceMode ? (
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
                  username={GUIDE_PERSONA.username}
                  expertName={GUIDE_PERSONA.displayName}
                  personaName={GUIDE_PERSONA.personaName}
                  avatarUrl={avatarUrl}
                  widgetToken={GUIDE_WIDGET_TOKEN}
                  onDisconnect={() => setIsVoiceMode(false)}
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
                  username={GUIDE_PERSONA.username}
                  expertName={GUIDE_PERSONA.displayName}
                  personaName={GUIDE_PERSONA.personaName}
                  avatarUrl={avatarUrl}
                  widgetToken={GUIDE_WIDGET_TOKEN}
                  onSwitchToVoice={() => setIsVoiceMode(true)}
                />
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>
    </motion.div>
  );
}
