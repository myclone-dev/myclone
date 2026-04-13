"use client";

import { useState } from "react";
import {
  Timer,
  RefreshCw,
  ArrowLeft,
  MessageSquare,
  Download,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { TranscriptModal } from "../voice/TranscriptModal";

interface TranscriptMessage {
  id: string;
  text: string;
  speaker: "user" | "assistant";
  timestamp: number;
  isComplete: boolean;
  citations?: Array<{
    index: number;
    url: string;
    title: string;
    content?: string;
    raw_source?: string;
    source_type?: string;
  }>;
}

interface SessionTimeLimitExceededProps {
  expertName: string;
  /** Duration of the session in minutes (supports fractions like 2.5) */
  sessionDurationMinutes?: number;
  /** Callback to start a new session */
  onStartNewSession?: () => void;
  /** Callback to go back */
  onGoBack?: () => void;
  /** Widget mode removes max-width constraints */
  widgetToken?: string;
  /** Transcript messages from the session */
  transcriptMessages?: TranscriptMessage[];
  /** Avatar URL for transcript modal */
  avatarUrl?: string;
}

/**
 * Format duration in minutes to a human-readable string.
 * Supports fractional minutes (e.g., 2.5 = "2m 30s")
 */
function formatDuration(minutes: number): string {
  const totalSeconds = Math.round(minutes * 60);
  const hrs = Math.floor(totalSeconds / 3600);
  const mins = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  if (hrs > 0) {
    return mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`;
  }
  if (mins > 0) {
    return secs > 0 ? `${mins}m ${secs}s` : `${mins}m`;
  }
  return `${secs}s`;
}

/**
 * Component shown when session time limit has been reached.
 * Allows user to view transcript and start a new session.
 */
export function SessionTimeLimitExceeded({
  expertName,
  sessionDurationMinutes,
  onStartNewSession,
  onGoBack,
  widgetToken,
  transcriptMessages = [],
  avatarUrl,
}: SessionTimeLimitExceededProps) {
  const { t } = useTranslation();
  const [showTranscript, setShowTranscript] = useState(false);

  const containerClass = widgetToken
    ? "relative w-full h-full"
    : "relative w-full h-full";

  // Download transcript as text file
  const handleDownloadTranscript = () => {
    if (transcriptMessages.length === 0) return;

    const durationStr = sessionDurationMinutes
      ? `Duration: ${formatDuration(sessionDurationMinutes)}\n`
      : "";
    const header = `Conversation with ${expertName}\nSession ended due to time limit\n${durationStr}Date: ${new Date().toLocaleDateString()}\n\n${"=".repeat(50)}\n\n`;

    const content = transcriptMessages
      .map((msg) => {
        // Null safety for message text and timestamp
        const text = msg.text ?? "";
        const timestamp = msg.timestamp ?? Date.now();
        const time = new Date(timestamp).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });
        const speaker = msg.speaker === "user" ? "You" : expertName;
        return `[${time}] ${speaker}:\n${text}\n`;
      })
      .join("\n");

    const blob = new Blob([header + content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `conversation-${expertName.toLowerCase().replace(/\s+/g, "-")}-${new Date().toISOString().split("T")[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const messageCount = transcriptMessages.length;

  return (
    <div className={containerClass}>
      <div className="flex min-h-[450px] flex-col items-center justify-center gap-6 p-8 sm:p-12">
        <div className="flex max-w-md flex-col items-center justify-center space-y-6 text-center">
          {/* Animated Icon */}
          <div className="relative">
            <div className="absolute inset-0 animate-ping rounded-full bg-session-timer-ping opacity-30" />
            <div className="relative flex size-24 items-center justify-center rounded-full bg-gradient-to-br from-session-timer-gradient-from to-session-timer-gradient-to shadow-lg shadow-session-timer-bg">
              <Timer
                className="size-12 text-session-timer-accent"
                strokeWidth={1.5}
              />
            </div>
          </div>

          {/* Title */}
          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-gray-900 sm:text-3xl">
              {t("session.timeLimitExceeded.title")}
            </h2>
            <p className="text-base text-gray-600">
              {t("session.timeLimitExceeded.sessionEnded", {
                name: expertName,
              })}
            </p>
          </div>

          {/* Stats Card */}
          <div className="flex w-full items-center justify-center gap-4 rounded-2xl bg-gradient-to-r from-session-timer-stats-from to-session-timer-stats-to px-6 py-4 shadow-sm">
            {sessionDurationMinutes && sessionDurationMinutes > 0 && (
              <div className="flex flex-col items-center">
                <span className="text-2xl font-bold text-session-timer-text">
                  {formatDuration(sessionDurationMinutes)}
                </span>
                <span className="text-xs text-gray-500">
                  {t("session.timeLimitExceeded.duration")}
                </span>
              </div>
            )}
            {sessionDurationMinutes && messageCount > 0 && (
              <div className="h-8 w-px bg-session-timer-divider" />
            )}
            {messageCount > 0 && (
              <div className="flex flex-col items-center">
                <span className="text-2xl font-bold text-session-timer-text">
                  {messageCount}
                </span>
                <span className="text-xs text-gray-500">
                  {t("session.timeLimitExceeded.messagesCount")}
                </span>
              </div>
            )}
          </div>

          {/* Subtitle */}
          <p className="text-sm text-gray-500">
            {t("session.timeLimitExceeded.conversationSaved")}
          </p>

          {/* CTA Buttons */}
          <div className="mt-2 flex w-full flex-col gap-3">
            {/* View Transcript Button */}
            {messageCount > 0 && (
              <Button
                onClick={() => setShowTranscript(true)}
                variant="outline"
                size="lg"
                className="flex w-full items-center justify-center gap-2 rounded-full border-session-timer-btn-outline-border bg-white px-8 py-3 text-session-timer-btn-outline-text transition-all hover:border-session-timer-btn-outline-hover-border hover:bg-session-timer-btn-outline-hover-bg"
              >
                <MessageSquare className="size-5" />
                {t("session.timeLimitExceeded.viewTranscript")}
                <span className="ml-1 rounded-full bg-session-timer-badge-bg px-2 py-0.5 text-xs font-medium text-session-timer-badge-text">
                  {messageCount}
                </span>
              </Button>
            )}

            {/* Start New Session Button */}
            {onStartNewSession && (
              <Button
                onClick={onStartNewSession}
                size="lg"
                className="flex w-full items-center justify-center gap-2 rounded-full bg-ai-gold px-8 py-3 text-gray-900 shadow-md transition-all hover:bg-ai-gold/90 hover:shadow-lg"
              >
                <RefreshCw className="size-5" />
                {t("session.timeLimitExceeded.startNewSession")}
              </Button>
            )}

            {/* Download Transcript */}
            {messageCount > 0 && (
              <Button
                onClick={handleDownloadTranscript}
                variant="ghost"
                size="sm"
                className="flex items-center justify-center gap-2 rounded-full px-6 py-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
              >
                <Download className="size-4" />
                {t("session.timeLimitExceeded.downloadTranscript")}
              </Button>
            )}

            {/* Go Back */}
            {onGoBack && (
              <Button
                onClick={onGoBack}
                variant="ghost"
                size="sm"
                className="flex items-center justify-center gap-2 rounded-full px-6 py-2 text-gray-400 hover:bg-gray-50 hover:text-gray-600"
              >
                <ArrowLeft className="size-4" />
                {t("common.goBack")}
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Transcript Modal */}
      <TranscriptModal
        isOpen={showTranscript}
        onClose={() => setShowTranscript(false)}
        transcriptMessages={transcriptMessages}
        expertName={expertName}
        avatarUrl={avatarUrl}
        onDownload={handleDownloadTranscript}
      />
    </div>
  );
}
