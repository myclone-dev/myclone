"use client";

import React, { useEffect, useRef } from "react";
import { X, Maximize2, Minimize2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ui/conversation";
import { useStickToBottomContext } from "use-stick-to-bottom";
import { TranscriptMessage } from "./TranscriptMessage";
import { useTranslation } from "react-i18next";
import type { ContentOutputItem } from "@/types/contentOutput";
import {
  AgentStatusIndicator,
  type AgentStatus,
} from "../chat/AgentStatusIndicator";

// Auto-scroll hook that triggers scroll when message text changes
function useAutoScrollOnMessage(
  lastMessageText: string | undefined,
  messageCount: number,
) {
  const context = useStickToBottomContext();
  const prevTextRef = useRef<string | undefined>(lastMessageText);
  const prevCountRef = useRef<number>(messageCount);

  useEffect(() => {
    // Scroll when new message is added or last message text changes (streaming)
    if (
      messageCount !== prevCountRef.current ||
      lastMessageText !== prevTextRef.current
    ) {
      // Use requestAnimationFrame to ensure DOM has updated
      requestAnimationFrame(() => {
        context.scrollToBottom();
      });
    }
    prevTextRef.current = lastMessageText;
    prevCountRef.current = messageCount;
  }, [lastMessageText, messageCount, context]);
}

// Wrapper component to use the auto-scroll hook inside Conversation context
function AutoScrollMessages({
  children,
  lastMessageText,
  messageCount,
}: {
  children: React.ReactNode;
  lastMessageText: string | undefined;
  messageCount: number;
}) {
  useAutoScrollOnMessage(lastMessageText, messageCount);
  return <>{children}</>;
}

export interface TranscriptAttachment {
  id: string;
  filename: string;
  fileType: string;
  fileSize: number;
  extractionStatus?: string;
}

interface TranscriptMessageData {
  id: string;
  text: string;
  speaker: "user" | "assistant";
  timestamp: number;
  isComplete?: boolean;
  calendarUrl?: string;
  citations?: Array<{
    index: number;
    url: string;
    title: string;
    content?: string;
    raw_source?: string;
    source_type?: string;
  }>;
  attachments?: TranscriptAttachment[];
  contentOutput?: ContentOutputItem;
}

interface LiveTranscriptPanelProps {
  transcriptMessages: TranscriptMessageData[];
  expertName: string;
  avatarUrl?: string;
  isMaximized: boolean;
  showTranscript: boolean;
  onToggleMaximize: () => void;
  onClose: () => void;
  isSavingTranscripts?: boolean;
  isConnected?: boolean;
  /** Custom display name for calendar booking button (e.g., "Solicitar cita") */
  calendarDisplayName?: string;
  /** Called when user clicks "View Full Content" on a content output card */
  onViewContent?: (content: ContentOutputItem) => void;
  /** Current agent status (searching, fetching, generating, idle) */
  agentStatus?: AgentStatus | null;
}

// Helper to get status styling based on connection state
function getStatusStyle(isConnected: boolean): {
  textKey: string;
  dotColor: string;
  bgColor: string;
  textColor: string;
} {
  if (isConnected) {
    return {
      textKey: "voice.status.connected",
      dotColor: "bg-green-500",
      bgColor: "bg-green-50",
      textColor: "text-green-700",
    };
  }

  return {
    textKey: "voice.status.readyToTalk",
    dotColor: "bg-blue-400",
    bgColor: "bg-blue-50",
    textColor: "text-blue-600",
  };
}

export const LiveTranscriptPanel = React.memo(
  function LiveTranscriptPanel({
    transcriptMessages,
    expertName,
    avatarUrl,
    isMaximized,
    showTranscript,
    onToggleMaximize,
    onClose,
    isSavingTranscripts,
    isConnected = false,
    calendarDisplayName,
    onViewContent,
    agentStatus,
  }: LiveTranscriptPanelProps) {
    const { t } = useTranslation();
    const statusStyle = getStatusStyle(isConnected);
    const statusText = t(statusStyle.textKey);
    const handleDownloadTranscript = () => {
      const formatTime = (timestamp: number) => {
        return new Date(timestamp).toLocaleString();
      };

      const transcriptText = transcriptMessages
        .map((msg) => {
          const speaker = msg.speaker === "user" ? "You" : expertName;
          const time = formatTime(msg.timestamp);
          let text = `[${time}] ${speaker}:\n${msg.text}\n`;

          if (msg.citations && msg.citations.length > 0) {
            text += "\nSources:\n";
            msg.citations.forEach((citation, idx) => {
              text += `  ${idx + 1}. ${citation.title}${citation.url ? ` - ${citation.url}` : ""}\n`;
            });
          }

          if (msg.calendarUrl) {
            text += `\n📅 ${calendarDisplayName || t("calendar.bookCall")}: ${msg.calendarUrl}\n`;
          }

          return text;
        })
        .join("\n---\n\n");

      const blob = new Blob([transcriptText], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `transcript-${expertName}-${new Date().toISOString().split("T")[0]}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    };

    // Don't render anything if not shown
    if (!showTranscript) {
      return null;
    }

    return (
      <div
        className={`bg-white rounded-3xl border border-gray-200/50 flex flex-col shadow-xl overflow-hidden transition-all duration-300 ${
          isMaximized
            ? "w-full h-full sm:h-[500px] sm:w-[600px]"
            : "hidden sm:flex sm:h-[500px] sm:w-[380px]"
        }`}
      >
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-amber-50 rounded-lg flex items-center justify-center">
                <svg
                  className="w-5 h-5 text-amber-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-gray-900">
                  {t("voice.transcript.title")}
                </h3>
                {transcriptMessages.length > 0 && (
                  <span className="text-xs text-gray-400 mt-0.5">
                    {transcriptMessages.length} {t("common.messages")}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={onToggleMaximize}
                className="p-1.5 h-8 w-8 hover:bg-gray-100 rounded-lg transition-all"
                title={
                  isMaximized
                    ? t("voice.transcript.minimize")
                    : t("voice.transcript.maximize")
                }
              >
                {isMaximized ? (
                  <Minimize2 className="w-4 h-4 text-gray-600" />
                ) : (
                  <Maximize2 className="w-4 h-4 text-gray-600" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
                className="p-1.5 h-8 w-8 hover:bg-gray-100 rounded-lg transition-all"
              >
                <X className="w-4 h-4 text-gray-600" />
              </Button>
            </div>
          </div>
        </div>

        {/* Transcript Content - uses ElevenLabs Conversation for auto-scroll */}
        <Conversation className="flex-1 bg-gray-50/30">
          <ConversationContent className="space-y-3">
            <AutoScrollMessages
              lastMessageText={
                transcriptMessages.length > 0
                  ? transcriptMessages[transcriptMessages.length - 1].text
                  : undefined
              }
              messageCount={transcriptMessages.length}
            >
              {transcriptMessages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full py-8 text-center">
                  <p className="text-sm text-gray-500 mb-2">
                    {t("voice.transcript.emptyState")}
                  </p>
                  <div
                    className={`flex items-center gap-2 px-3 py-1.5 ${statusStyle.bgColor} rounded-full`}
                  >
                    <div
                      className={`w-2 h-2 ${statusStyle.dotColor} rounded-full ${isConnected ? "animate-pulse" : ""}`}
                    ></div>
                    <span
                      className={`text-xs ${statusStyle.textColor} font-medium`}
                    >
                      {statusText}
                    </span>
                  </div>
                </div>
              ) : (
                <>
                  {transcriptMessages.map((message) => {
                    // Validate message data to prevent render errors
                    if (!message || !message.id || !message.text) {
                      console.error("Invalid transcript message:", message);
                      return null;
                    }

                    return (
                      <TranscriptMessage
                        key={message.id}
                        text={message.text}
                        speaker={message.speaker}
                        timestamp={message.timestamp}
                        expertName={expertName}
                        avatarUrl={avatarUrl}
                        calendarUrl={message.calendarUrl}
                        calendarDisplayName={calendarDisplayName}
                        citations={message.citations}
                        attachments={message.attachments}
                        contentOutput={message.contentOutput}
                        onViewContent={onViewContent}
                      />
                    );
                  })}
                  <AgentStatusIndicator agentStatus={agentStatus ?? null} />
                </>
              )}
            </AutoScrollMessages>
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>

        {/* Footer */}
        {transcriptMessages.length > 0 && (
          <div className="bg-white border-t border-gray-200 px-4 py-2.5">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500">
                  {transcriptMessages.length}{" "}
                  {transcriptMessages.length !== 1
                    ? t("common.messages")
                    : t("common.message")}
                </span>
                {isSavingTranscripts && (
                  <span className="text-xs text-amber-600">
                    {t("voice.transcript.saving")}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleDownloadTranscript}
                  className="p-1.5 h-7 w-7 hover:bg-gray-100 rounded-lg transition-all"
                  title={t("voice.transcript.download")}
                >
                  <Download className="w-3.5 h-3.5 text-gray-600" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  },
  (prevProps, nextProps) => {
    // Custom comparison: only re-render if important props changed

    // Always re-render if visibility changed
    if (prevProps.showTranscript !== nextProps.showTranscript) {
      return false;
    }

    // If hidden, don't bother checking other props
    if (!nextProps.showTranscript) {
      return true; // Don't re-render if hidden
    }

    // Check message count
    if (
      prevProps.transcriptMessages.length !==
      nextProps.transcriptMessages.length
    ) {
      return false; // Re-render (message count changed)
    }

    // Check maximized state
    if (prevProps.isMaximized !== nextProps.isMaximized) {
      return false; // Re-render (maximized state changed)
    }

    // Check agent status
    if (
      prevProps.agentStatus?.status !== nextProps.agentStatus?.status ||
      prevProps.agentStatus?.message !== nextProps.agentStatus?.message
    ) {
      return false; // Re-render (agent status changed)
    }

    // Check if actual message content changed (last message text or calendar URL)
    if (
      prevProps.transcriptMessages.length > 0 &&
      nextProps.transcriptMessages.length > 0
    ) {
      const prevLast =
        prevProps.transcriptMessages[prevProps.transcriptMessages.length - 1];
      const nextLast =
        nextProps.transcriptMessages[nextProps.transcriptMessages.length - 1];

      if (
        prevLast.text !== nextLast.text ||
        prevLast.id !== nextLast.id ||
        prevLast.calendarUrl !== nextLast.calendarUrl
      ) {
        return false; // Re-render (last message changed)
      }
    }

    return true; // Don't re-render (nothing important changed)
  },
);
