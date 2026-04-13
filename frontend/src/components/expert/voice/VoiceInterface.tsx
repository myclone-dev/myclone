"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { Room } from "livekit-client";
import { useVoiceAssistant } from "@livekit/components-react";
import {
  Mic,
  MicOff,
  PhoneOff,
  MessageSquare,
  ArrowLeft,
  Paperclip,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { VoiceAvatar } from "./VoiceAvatar";
import { GuideVoiceAvatar } from "./GuideVoiceAvatar";
import { AmbientWaves } from "./AmbientWaves";
import { LiveTranscriptPanel } from "./LiveTranscriptPanel";
import { TranscriptMessage } from "./TranscriptMessage";
import {
  useAttachmentUpload,
  validateAttachmentFile,
  notifyLiveKitDocumentUpload,
} from "@/lib/queries/expert/chat";
import { toast } from "sonner";
import { trackFileUpload } from "@/lib/monitoring/sentry";
import { cn } from "@/lib/utils";
import { GUIDE_WIDGET_TOKEN } from "@/components/dashboard/personas/AssistantWidget/types";
import { SessionTimer } from "../chat/SessionTimer";
import { useTranslation } from "react-i18next";
import type { ContentOutputItem } from "@/types/contentOutput";
import {
  AgentStatusIndicator,
  type AgentStatus,
} from "../chat/AgentStatusIndicator";

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
  contentOutput?: ContentOutputItem;
}

export interface UploadedDocument {
  id: string;
  filename: string;
  fileType: string;
  fileSize: number;
  timestamp: number;
  extractionStatus?: string;
}

interface VoiceInterfaceProps {
  room: Room;
  sessionStarted: boolean;
  isConnected: boolean;
  isMuted: boolean;
  showTranscript: boolean;
  isMaximized: boolean;
  transcriptMessages: TranscriptMessage[];
  voiceSessionToken: string | null;
  expertName: string;
  avatarUrl?: string;
  widgetToken?: string;
  initSessionPending: boolean;
  onStartSession: () => void;
  onToggleMute: () => void;
  onDisconnect: () => void; // Back to text chat
  onEndCall: () => void; // End active call
  onToggleMaximize: () => void;
  onCloseTranscript: () => void;
  onToggleTranscript: () => void;
  setIsMuted: React.Dispatch<React.SetStateAction<boolean>>;
  enableDocumentUpload?: boolean; // Enable document upload button
  onDocumentUploaded?: (doc: UploadedDocument) => void; // Callback when document is uploaded
  // Session time limit props
  sessionTimeLimitEnabled?: boolean;
  sessionTimeLimitMinutes?: number;
  sessionRemainingSeconds?: number;
  /**
   * Force guide-style UI rendering (centered avatar, inline transcript)
   * When true, renders the compact guide widget style regardless of widgetToken
   */
  useGuideStyle?: boolean;
  /** Custom display name for calendar booking button (e.g., "Solicitar cita") */
  calendarDisplayName?: string;
  /** Called when user clicks "View Full Content" on a content output card */
  onViewContent?: (content: ContentOutputItem) => void;
  /** Current agent status (searching, fetching, generating, idle) */
  agentStatus?: AgentStatus | null;
}

export const VoiceInterface = React.memo(function VoiceInterface({
  room,
  sessionStarted,
  isConnected,
  isMuted,
  showTranscript,
  isMaximized,
  transcriptMessages,
  voiceSessionToken,
  expertName,
  avatarUrl,
  widgetToken,
  initSessionPending,
  onStartSession,
  onToggleMute,
  onDisconnect,
  onEndCall,
  onToggleMaximize,
  onCloseTranscript,
  onToggleTranscript,
  setIsMuted,
  enableDocumentUpload = true,
  onDocumentUploaded,
  sessionTimeLimitEnabled = false,
  sessionTimeLimitMinutes = 30,
  sessionRemainingSeconds = 0,
  useGuideStyle = false,
  calendarDisplayName,
  onViewContent,
  agentStatus,
}: VoiceInterfaceProps) {
  const { t } = useTranslation();
  const { state: agentState } = useVoiceAssistant();
  const agentSpeaking = agentState === "speaking";

  // Check if this is the ConvoxAI Guide widget (needs special compact styling)
  // Either explicitly requested via useGuideStyle prop, or using the guide widget token
  const isGuideWidget = useGuideStyle || widgetToken === GUIDE_WIDGET_TOKEN;

  // Document upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const attachmentUploadMutation = useAttachmentUpload();

  // Guide widget mode: live transcript visibility (shown by default during call)
  const [showWidgetLiveTranscript, setShowWidgetLiveTranscript] =
    useState(true);
  const widgetTranscriptRef = useRef<HTMLDivElement>(null);

  // Resizable transcript panel state
  const [transcriptHeight, setTranscriptHeight] = useState(200);
  const isDraggingRef = useRef(false);
  const startYRef = useRef(0);
  const startHeightRef = useRef(200);
  const MIN_TRANSCRIPT_HEIGHT = 100;
  const MAX_TRANSCRIPT_HEIGHT = 400;

  // Auto-scroll guide widget transcript when new messages arrive
  useEffect(() => {
    if (
      isGuideWidget &&
      showWidgetLiveTranscript &&
      widgetTranscriptRef.current
    ) {
      widgetTranscriptRef.current.scrollTop =
        widgetTranscriptRef.current.scrollHeight;
    }
  }, [transcriptMessages, isGuideWidget, showWidgetLiveTranscript]);

  // Handle transcript panel resize
  const handleResizeStart = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      e.preventDefault();
      isDraggingRef.current = true;
      startYRef.current = "touches" in e ? e.touches[0].clientY : e.clientY;
      startHeightRef.current = transcriptHeight;

      const handleMove = (moveEvent: MouseEvent | TouchEvent) => {
        if (!isDraggingRef.current) return;
        const currentY =
          "touches" in moveEvent
            ? moveEvent.touches[0].clientY
            : moveEvent.clientY;
        // Dragging up increases height, dragging down decreases
        const delta = startYRef.current - currentY;
        const newHeight = Math.max(
          MIN_TRANSCRIPT_HEIGHT,
          Math.min(MAX_TRANSCRIPT_HEIGHT, startHeightRef.current + delta),
        );
        setTranscriptHeight(newHeight);
      };

      const handleEnd = () => {
        isDraggingRef.current = false;
        document.removeEventListener("mousemove", handleMove);
        document.removeEventListener("mouseup", handleEnd);
        document.removeEventListener("touchmove", handleMove);
        document.removeEventListener("touchend", handleEnd);
      };

      document.addEventListener("mousemove", handleMove);
      document.addEventListener("mouseup", handleEnd);
      document.addEventListener("touchmove", handleMove);
      document.addEventListener("touchend", handleEnd);
    },
    [transcriptHeight],
  );

  // Handle file selection for document upload
  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file || !voiceSessionToken || !isConnected) return;

      // Validate file
      const validationError = validateAttachmentFile(file);
      if (validationError) {
        toast.error(validationError);
        if (fileInputRef.current) fileInputRef.current.value = "";
        return;
      }

      setIsUploading(true);
      trackFileUpload("attachment", "started", {
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
      });

      try {
        const result = await attachmentUploadMutation.mutateAsync({
          sessionToken: voiceSessionToken,
          file,
          widgetToken,
        });

        // Notify LiveKit agent about the document upload
        if (result.s3_url) {
          await notifyLiveKitDocumentUpload(
            room,
            result.filename,
            result.s3_url,
            result.extracted_text, // Pass extracted text to avoid backend S3 re-fetch
          );
          if (process.env.NODE_ENV === "development") {
            console.log(
              "📤 [VoiceInterface] Notified LiveKit agent about document:",
              result.filename,
            );
          }
        }

        trackFileUpload("attachment", "success", {
          fileName: file.name,
          fileType: result.file_type,
          extractionStatus: result.extraction_status,
        });

        // Notify parent about the uploaded document
        onDocumentUploaded?.({
          id: result.attachment_id,
          filename: result.filename,
          fileType: result.file_type,
          fileSize: result.file_size,
          timestamp: Date.now(),
          extractionStatus: result.extraction_status,
        });

        toast.success(`Document "${file.name}" uploaded and sent to assistant`);
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : "Failed to upload file";
        trackFileUpload("attachment", "error", {
          fileName: file.name,
          fileSize: file.size,
          error: errorMessage,
        });
        toast.error(errorMessage);
      } finally {
        setIsUploading(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    },
    [
      voiceSessionToken,
      isConnected,
      widgetToken,
      room,
      attachmentUploadMutation,
      onDocumentUploaded,
    ],
  );

  const handleDocumentClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  // NOTE: Transcription handling is now done in TranscriptionHandler.tsx
  // to avoid duplicate handlers and flickering issues

  // Sync isMuted state with actual microphone state only when connected
  useEffect(() => {
    if (!isConnected) return;

    const syncMicState = () => {
      const micEnabled = room.localParticipant.isMicrophoneEnabled ?? true;
      setIsMuted(!micEnabled);
    };
    syncMicState();
  }, [isConnected, room.localParticipant, setIsMuted]);

  // In guide widget mode, remove max-width constraint and padding to fill container
  const containerClass = isGuideWidget
    ? "relative w-full"
    : "relative w-full max-w-4xl mx-auto px-4 sm:px-0";

  // Container style for guide widget mode to ensure full height
  const containerStyle = isGuideWidget
    ? {
        flex: 1,
        display: "flex",
        flexDirection: "column" as const,
        minHeight: 0,
      }
    : undefined;

  // In guide widget mode, use full height and single column layout
  const contentLayoutClass = isGuideWidget
    ? "flex flex-col"
    : "flex flex-col sm:flex-row gap-4 min-h-[500px] sm:h-[500px]";

  // Content layout style for guide widget mode
  const contentLayoutStyle = isGuideWidget
    ? { flex: 1, minHeight: 0 }
    : undefined;

  // Guide widget: Render a completely different, compact UI
  if (isGuideWidget) {
    return (
      <div className={containerClass} style={containerStyle}>
        <div className="flex flex-col h-full" style={{ flex: 1, minHeight: 0 }}>
          {/* Main content area - responsive padding */}
          <div
            className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6 relative overflow-hidden"
            style={{
              background: "linear-gradient(180deg, #fafafa 0%, #f5f5f5 100%)",
            }}
          >
            {/* Subtle background pattern */}
            <div
              className="absolute inset-0 opacity-30"
              style={{
                backgroundImage:
                  "radial-gradient(circle at 2px 2px, #e5e5e5 1px, transparent 0)",
                backgroundSize: "24px 24px",
              }}
            />

            {/* Avatar with animations - responsive size */}
            <div className="relative z-10 mb-3 sm:mb-4">
              <GuideVoiceAvatar
                avatarUrl={avatarUrl}
                expertName={expertName}
                speaking={agentSpeaking}
                isConnected={isConnected}
                isConnecting={sessionStarted && !isConnected}
                size="lg"
              />
            </div>

            {/* Name and status - responsive text */}
            <div className="relative z-10 text-center mb-4 sm:mb-6 max-w-full px-4">
              <h3 className="text-base sm:text-lg font-semibold text-gray-900 mb-0.5 sm:mb-1 truncate">
                {expertName}
              </h3>
              <p className="text-xs sm:text-sm text-gray-500">
                {!sessionStarted
                  ? t("voice.status.readyToHelp")
                  : isConnected
                    ? agentSpeaking
                      ? t("voice.status.speaking")
                      : t("voice.status.listening")
                    : t("voice.status.connecting")}
              </p>
              {/* Session Timer for guide widget */}
              {sessionTimeLimitEnabled && isConnected && (
                <div className="mt-2">
                  <SessionTimer
                    remainingSeconds={sessionRemainingSeconds}
                    totalMinutes={sessionTimeLimitMinutes}
                    isActive={true}
                    compact
                  />
                </div>
              )}
            </div>

            {/* Action area - responsive width */}
            <div className="relative z-10 w-full max-w-[280px] sm:max-w-xs px-2 sm:px-0">
              {!sessionStarted ? (
                <div className="flex flex-col gap-2 sm:gap-3">
                  {/* Start button - responsive height */}
                  <Button
                    onClick={onStartSession}
                    disabled={!voiceSessionToken || initSessionPending}
                    className="w-full h-10 sm:h-12 rounded-full bg-black hover:bg-gray-800 text-white font-medium text-sm sm:text-base transition-all hover:scale-[1.02] active:scale-[0.98]"
                  >
                    {!voiceSessionToken ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Mic className="w-4 h-4 mr-2" />
                    )}
                    {!voiceSessionToken
                      ? t("voice.status.initializing")
                      : t("voice.buttons.startConversation")}
                  </Button>

                  {/* Previous transcript - responsive */}
                  {transcriptMessages.length > 0 && (
                    <Button
                      onClick={onToggleTranscript}
                      variant="ghost"
                      className="w-full h-9 sm:h-10 rounded-full text-gray-600 hover:text-gray-900 hover:bg-gray-100 text-sm"
                    >
                      <MessageSquare className="w-4 h-4 mr-2" />
                      {t("voice.transcript.viewPrevious")}
                    </Button>
                  )}
                </div>
              ) : (
                /* Active call controls - responsive sizing */
                <div className="flex items-center justify-center gap-3 sm:gap-4">
                  {/* Mute button - responsive size */}
                  <Button
                    onClick={onToggleMute}
                    disabled={!isConnected}
                    className={cn(
                      "w-11 h-11 sm:w-14 sm:h-14 rounded-full transition-all",
                      isMuted
                        ? "bg-red-500 hover:bg-red-600 text-white"
                        : "bg-white hover:bg-gray-50 text-gray-700 border-2 border-gray-200",
                    )}
                  >
                    {isMuted ? (
                      <MicOff className="w-5 h-5 sm:w-6 sm:h-6" />
                    ) : (
                      <Mic className="w-5 h-5 sm:w-6 sm:h-6" />
                    )}
                  </Button>

                  {/* Transcript toggle - responsive size */}
                  <Button
                    onClick={() => setShowWidgetLiveTranscript((prev) => !prev)}
                    disabled={!isConnected}
                    className={cn(
                      "w-10 h-10 sm:w-12 sm:h-12 rounded-full transition-all",
                      showWidgetLiveTranscript
                        ? "bg-primary/10 text-primary border-2 border-primary/30"
                        : "bg-white hover:bg-gray-50 text-gray-700 border-2 border-gray-200",
                    )}
                  >
                    <MessageSquare className="w-4 h-4 sm:w-5 sm:h-5" />
                  </Button>

                  {/* Document upload - responsive size */}
                  {enableDocumentUpload && (
                    <>
                      <input
                        ref={fileInputRef}
                        type="file"
                        accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation,image/png,image/jpeg"
                        onChange={handleFileSelect}
                        className="hidden"
                      />
                      <Button
                        onClick={handleDocumentClick}
                        disabled={!isConnected || isUploading}
                        className="w-10 h-10 sm:w-12 sm:h-12 rounded-full bg-white hover:bg-gray-50 text-gray-700 border-2 border-gray-200"
                      >
                        {isUploading ? (
                          <Loader2 className="w-4 h-4 sm:w-5 sm:h-5 animate-spin" />
                        ) : (
                          <Paperclip className="w-4 h-4 sm:w-5 sm:h-5" />
                        )}
                      </Button>
                    </>
                  )}

                  {/* End call - responsive size */}
                  <Button
                    onClick={onEndCall}
                    disabled={!isConnected}
                    className="w-11 h-11 sm:w-14 sm:h-14 rounded-full bg-red-500 hover:bg-red-600 text-white transition-all"
                  >
                    <PhoneOff className="w-5 h-5 sm:w-6 sm:h-6" />
                  </Button>
                </div>
              )}
            </div>
          </div>

          {/* Live transcript panel - slides up when active, resizable */}
          {sessionStarted && showWidgetLiveTranscript && (
            <div
              className="border-t border-gray-200 bg-white flex flex-col"
              style={{ height: `${transcriptHeight}px`, flexShrink: 0 }}
            >
              {/* Drag handle for resizing */}
              <div
                className="h-2 cursor-ns-resize flex items-center justify-center hover:bg-gray-100 transition-colors select-none touch-none"
                onMouseDown={handleResizeStart}
                onTouchStart={handleResizeStart}
              >
                <div className="w-10 h-1 bg-gray-300 rounded-full" />
              </div>
              <div className="px-4 py-1.5 border-b border-gray-100 flex items-center justify-between bg-gray-50">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  <span className="text-xs font-medium text-gray-600">
                    {t("voice.transcript.title")}
                  </span>
                </div>
                <span className="text-xs text-gray-400">
                  {transcriptMessages.length} {t("common.messages")}
                </span>
              </div>
              <div
                ref={widgetTranscriptRef}
                className="flex-1 overflow-y-auto p-3 space-y-3"
              >
                {transcriptMessages.length === 0 ? (
                  <p className="text-xs text-gray-400 text-center py-4">
                    {t("voice.transcript.emptyState")}
                  </p>
                ) : (
                  transcriptMessages.map((msg) => (
                    <TranscriptMessage
                      key={msg.id}
                      text={msg.text}
                      speaker={msg.speaker}
                      timestamp={msg.timestamp}
                      expertName={expertName}
                      avatarUrl={avatarUrl}
                      citations={msg.citations}
                      contentOutput={msg.contentOutput}
                      onViewContent={onViewContent}
                    />
                  ))
                )}
                <AgentStatusIndicator agentStatus={agentStatus ?? null} />
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Default (non-guide-widget) UI
  return (
    <div className={containerClass} style={containerStyle}>
      <div className={contentLayoutClass} style={contentLayoutStyle}>
        {/* Main Voice Interface */}
        <div
          className="flex items-center justify-center relative overflow-hidden flex-1 rounded-3xl border border-gray-200/50 shadow-2xl p-8 sm:p-12"
          style={{
            background:
              "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 50%, #e2e8f0 100%)",
          }}
        >
          {/* Gradient orbs for depth - smaller in guide widget mode */}
          <div
            className={cn(
              "absolute top-0 right-0 bg-gradient-to-br from-slate-100/50 to-slate-200/40 rounded-full blur-3xl",
              isGuideWidget ? "w-32 h-32" : "w-64 h-64",
            )}
          />
          <div
            className={cn(
              "absolute bottom-0 left-0 bg-gradient-to-tr from-slate-50/50 to-yellow-50/30 rounded-full blur-3xl",
              isGuideWidget ? "w-28 h-28" : "w-56 h-56",
            )}
          />
          <div
            className={cn(
              "flex flex-col items-center justify-center relative z-10",
              isGuideWidget ? "space-y-3" : "space-y-5",
            )}
          >
            {/* Avatar Stage */}
            <div className="relative">
              <AmbientWaves active={isConnected} />
              <VoiceAvatar speaking={agentSpeaking} isConnected={isConnected} />

              {/* Loading Spinner */}
              {!isConnected && sessionStarted && (
                <div className="pointer-events-none absolute -inset-1 sm:-inset-1.5 rounded-full">
                  <div className="absolute inset-0 rounded-full border-2 sm:border-3 border-gray-200/70" />
                  <div
                    className="absolute inset-0 rounded-full border-2 sm:border-3 border-transparent animate-spin"
                    style={{
                      animationDuration: "1.5s",
                      borderTopColor: "#64748b",
                    }}
                  />
                </div>
              )}
            </div>

            {/* Status Text */}
            <div className="text-center">
              <p className="text-gray-600 text-sm sm:text-base">
                {!sessionStarted
                  ? t("voice.status.readyToStart")
                  : isConnected
                    ? agentSpeaking
                      ? t("voice.status.speaking")
                      : t("voice.status.listening")
                    : t("voice.status.connecting")}
              </p>
              {/* Session Timer */}
              {sessionTimeLimitEnabled && isConnected && (
                <div className="mt-2">
                  <SessionTimer
                    remainingSeconds={sessionRemainingSeconds}
                    totalMinutes={sessionTimeLimitMinutes}
                    isActive={true}
                    compact
                  />
                </div>
              )}
            </div>

            {/* Controls */}
            {!sessionStarted ? (
              <div className="flex flex-col gap-3">
                <Button
                  onClick={onStartSession}
                  disabled={!voiceSessionToken || initSessionPending}
                  size="lg"
                  className="rounded-full hover:opacity-90 transition-opacity px-8 py-3"
                  style={{
                    backgroundColor: "#000000",
                    color: "#FFFFFF",
                    fontWeight: "600",
                  }}
                >
                  {!voiceSessionToken
                    ? t("voice.status.initializing")
                    : t("voice.buttons.startVoiceChat")}
                </Button>

                {/* Show transcript button after call ends */}
                {transcriptMessages.length > 0 && (
                  <>
                    <Button
                      onClick={onToggleTranscript}
                      variant="outline"
                      size="lg"
                      className="border-gray-300 hover:bg-gray-100 hover:border-gray-400 text-gray-700 hover:text-gray-900 rounded-full flex items-center gap-2 transition-all px-8 py-3"
                    >
                      <MessageSquare className="w-4 h-4" />
                      {t("voice.transcript.show")}
                    </Button>

                    <Button
                      onClick={onDisconnect}
                      variant="ghost"
                      size="sm"
                      className="text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded-full px-6 py-2 flex items-center gap-2"
                    >
                      <ArrowLeft className="w-4 h-4" />
                      {t("voice.buttons.backToTextChat")}
                    </Button>
                  </>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <Button
                  onClick={onToggleMute}
                  disabled={!isConnected}
                  size="lg"
                  className={`rounded-full w-12 h-12 sm:w-14 sm:h-14 ${
                    isMuted
                      ? "bg-red-500 hover:bg-red-600 text-white"
                      : "bg-white hover:bg-gray-100 text-gray-700 hover:text-gray-900 border-2 border-gray-200 hover:border-gray-300"
                  }`}
                >
                  {isMuted ? (
                    <MicOff className="w-5 h-5 sm:w-6 sm:h-6" />
                  ) : (
                    <Mic className="w-5 h-5 sm:w-6 sm:h-6" />
                  )}
                </Button>

                {/* Transcript toggle button */}
                <Button
                  onClick={onToggleTranscript}
                  disabled={!isConnected}
                  size="lg"
                  className="rounded-full w-12 h-12 sm:w-14 sm:h-14 bg-white hover:bg-gray-100 text-gray-700 hover:text-gray-900 border-2 border-gray-200 hover:border-gray-300"
                >
                  <MessageSquare className="w-5 h-5 sm:w-6 sm:h-6" />
                </Button>

                {/* Document Upload Button */}
                {enableDocumentUpload && (
                  <>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation,image/png,image/jpeg"
                      onChange={handleFileSelect}
                      className="hidden"
                    />
                    <Button
                      onClick={handleDocumentClick}
                      disabled={!isConnected || isUploading}
                      size="lg"
                      className="rounded-full w-12 h-12 sm:w-14 sm:h-14 bg-white hover:bg-gray-100 text-gray-700 hover:text-gray-900 border-2 border-gray-200 hover:border-gray-300"
                      title={t("voice.upload.title")}
                    >
                      {isUploading ? (
                        <Loader2 className="w-5 h-5 sm:w-6 sm:h-6 animate-spin" />
                      ) : (
                        <Paperclip className="w-5 h-5 sm:w-6 sm:h-6" />
                      )}
                    </Button>
                  </>
                )}

                <Button
                  onClick={onEndCall}
                  disabled={!isConnected}
                  size="lg"
                  variant="destructive"
                  className="rounded-full w-12 h-12 sm:w-14 sm:h-14"
                >
                  <PhoneOff className="w-5 h-5 sm:w-6 sm:h-6" />
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Side Transcript Panel */}
        <LiveTranscriptPanel
          transcriptMessages={transcriptMessages}
          expertName={expertName}
          avatarUrl={avatarUrl}
          isMaximized={isMaximized}
          showTranscript={showTranscript}
          onToggleMaximize={onToggleMaximize}
          onClose={onCloseTranscript}
          isConnected={isConnected}
          calendarDisplayName={calendarDisplayName}
          onViewContent={onViewContent}
          agentStatus={agentStatus ?? null}
        />
      </div>
    </div>
  );
});
