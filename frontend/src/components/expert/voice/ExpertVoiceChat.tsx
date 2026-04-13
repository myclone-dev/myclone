"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Room } from "livekit-client";
import {
  RoomAudioRenderer,
  RoomContext,
  StartAudio,
} from "@livekit/components-react";
import {
  useInitVoiceSession,
  useVoiceHeartbeat,
  isVoiceLimitExceededError,
} from "@/lib/queries/expert/voice";
import {
  useInitSession,
  useProvideEmail,
  useCaptureLead,
} from "@/lib/queries/expert/chat";
import type { LeadCapturedRpcPayload } from "@/lib/queries/expert/chat";
import { VoiceInterface, type UploadedDocument } from "./VoiceInterface";
import { VoiceLimitExceeded } from "./VoiceLimitExceeded";
import { TranscriptionHandler } from "./TranscriptionHandler";
import { TranscriptModal } from "./TranscriptModal";
import { OTPWizard } from "../chat/OTPWizard";
import { SessionTimeLimitWarning } from "../chat/SessionTimeLimitWarning";
import { SessionTimeLimitExceeded } from "../chat/SessionTimeLimitExceeded";
import { useAuthStore } from "@/store/auth.store";
import { env } from "@/env";
import { trackLiveKitEvent } from "@/lib/monitoring/sentry";
import type { ContentOutputItem } from "@/types/contentOutput";
import { ContentOutputViewer } from "../chat/ContentOutputViewer";
import type { AgentStatus } from "../chat/AgentStatusIndicator";
import { useSessionTimeLimit } from "@/hooks/useSessionTimeLimit";
import { GUIDE_WIDGET_TOKEN } from "@/components/dashboard/personas/AssistantWidget/types";
import { useTranslation } from "react-i18next";

// Heartbeat interval in milliseconds (30 seconds)
const HEARTBEAT_INTERVAL = 30000;

interface ExpertVoiceChatProps {
  username: string;
  expertName: string;
  avatarUrl?: string;
  personaName?: string;
  widgetToken?: string;
  onDisconnect?: () => void;
  emailCaptureRequireFullname?: boolean;
  emailCaptureRequirePhone?: boolean;
  // Session time limit settings from persona
  sessionTimeLimitEnabled?: boolean;
  sessionTimeLimitMinutes?: number;
  sessionTimeLimitWarningMinutes?: number;
  /**
   * Force guide-style UI rendering (centered avatar, inline transcript)
   * When true, renders like the AssistantWidget regardless of widgetToken
   */
  useGuideStyle?: boolean;
  /** Custom display name for calendar booking button (e.g., "Solicitar cita") */
  calendarDisplayName?: string;
}

interface TranscriptAttachment {
  id: string;
  filename: string;
  fileType: string;
  fileSize: number;
  extractionStatus?: string;
}

interface TranscriptMessage {
  id: string;
  text: string;
  speaker: "user" | "assistant";
  timestamp: number;
  isComplete: boolean;
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

export function ExpertVoiceChat({
  username,
  expertName,
  avatarUrl,
  personaName,
  widgetToken,
  onDisconnect,
  emailCaptureRequireFullname = true,
  emailCaptureRequirePhone = false,
  sessionTimeLimitEnabled = false,
  sessionTimeLimitMinutes = 30,
  sessionTimeLimitWarningMinutes = 2,
  useGuideStyle = false,
  calendarDisplayName,
}: ExpertVoiceChatProps) {
  const { t } = useTranslation();
  // Check authentication status
  const { isAuthenticated, isVisitor, user } = useAuthStore();

  const [isConnected, setIsConnected] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [showTranscript, setShowTranscript] = useState(true);
  const [isMaximized, setIsMaximized] = useState(false);
  const [showTranscriptModal, setShowTranscriptModal] = useState(false);
  const [transcriptMessages, setTranscriptMessages] = useState<
    TranscriptMessage[]
  >([]);
  // Content output viewer state
  const [contentOutputViewer, setContentOutputViewer] =
    useState<ContentOutputItem | null>(null);
  // Agent status state (searching, fetching, generating, idle)
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [sessionStarted, setSessionStarted] = useState(false);
  const [voiceSessionToken, setVoiceSessionToken] = useState<string | null>(
    null,
  );
  const [emailCaptureState, setEmailCaptureState] = useState<{
    showPrompt: boolean;
    resolveCallback: ((value: string) => void) | null;
  }>({
    showPrompt: false,
    resolveCallback: null,
  });
  // Track if auto-link is in progress or completed (synchronous state)
  const [isSessionAutoLinked, setIsSessionAutoLinked] = useState(false);

  // Voice limit exceeded state
  const [voiceLimitExceeded, setVoiceLimitExceeded] = useState(false);
  const [wasLimitExceededMidCall, setWasLimitExceededMidCall] = useState(false);

  // Session time limit exceeded state (different from voice quota limit)
  const [sessionTimeLimitExceeded, setSessionTimeLimitExceeded] =
    useState(false);

  // Voice session tracking (for heartbeat)
  const [voiceSessionId, setVoiceSessionId] = useState<string | null>(null);
  const sessionStartTimeRef = useRef<number | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const room = useMemo(() => new Room(), []);
  const initSessionMutation = useInitSession();
  const initVoiceSessionMutation = useInitVoiceSession();
  const provideEmailMutation = useProvideEmail();
  const heartbeatMutation = useVoiceHeartbeat();
  const captureLeadMutation = useCaptureLead();

  // Session time limit hook - tracks total session duration
  const handleSessionTimeLimitReached = useCallback(() => {
    // Disconnect from LiveKit room
    room.disconnect();
    setIsConnected(false);
    setSessionStarted(false);
    setSessionTimeLimitExceeded(true);

    trackLiveKitEvent("session_time_limit_reached", {
      username,
      personaName,
      mode: "voice",
      limitMinutes: sessionTimeLimitMinutes,
    });
  }, [room, username, personaName, sessionTimeLimitMinutes]);

  const {
    showWarning: showSessionTimeLimitWarning,
    remainingSeconds: sessionTimeLimitRemainingSeconds,
    dismissWarning: dismissSessionTimeLimitWarning,
    resetSessionTimer,
  } = useSessionTimeLimit({
    limitMs: sessionTimeLimitMinutes * 60 * 1000,
    warningMs: sessionTimeLimitWarningMinutes * 60 * 1000,
    onLimitReached: handleSessionTimeLimitReached,
    enabled: sessionTimeLimitEnabled && isConnected,
    trackingContext: {
      username,
      personaName,
      mode: "voice",
    },
  });

  // Handler for starting a new session after time limit exceeded
  const handleStartNewSessionAfterTimeLimit = useCallback(() => {
    // Reset session time limit state
    setSessionTimeLimitExceeded(false);
    resetSessionTimer();

    // Clear stored session to force new session creation
    const sessionKey = personaName
      ? `voice_session_${username}_${personaName}`
      : `voice_session_${username}`;
    localStorage.removeItem(sessionKey);
    setVoiceSessionToken(null);

    trackLiveKitEvent("session_new_after_time_limit", {
      username,
      personaName,
      mode: "voice",
    });

    // Re-initialize session by refreshing component state
    // The useEffect will pick up the null token and create a new session
  }, [resetSessionTimer, username, personaName]);

  // Step 1: Initialize voice session to get session token on mount
  useEffect(() => {
    const sessionKey = personaName
      ? `voice_session_${username}_${personaName}`
      : `voice_session_${username}`;
    const storedToken = localStorage.getItem(sessionKey);

    if (storedToken) {
      // Reuse existing session token from localStorage
      setVoiceSessionToken(storedToken);
    } else {
      // Create new session if no token exists
      const initializeVoiceSession = async () => {
        try {
          const data = await initSessionMutation.mutateAsync({
            username,
            personaName,
            widgetToken,
          });
          setVoiceSessionToken(data.session_token);
          localStorage.setItem(sessionKey, data.session_token);
        } catch (error) {
          trackLiveKitEvent("session_init_error", {
            error: error instanceof Error ? error.message : "Unknown error",
            username,
            personaName,
          });
          console.error("Failed to initialize voice session:", error);
        }
      };

      initializeVoiceSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [username, personaName]);

  // Step 1.5: Auto-link session for authenticated users IMMEDIATELY
  useEffect(() => {
    // Only auto-link if:
    // 1. User is authenticated with full account (not visitor)
    // 2. Voice session token exists
    // 3. Session hasn't been linked yet
    if (!isAuthenticated || isVisitor || !voiceSessionToken || !user?.email) {
      return;
    }

    const sessionLinkedKey = personaName
      ? `voice_session_linked_${username}_${personaName}`
      : `voice_session_linked_${username}`;

    const isSessionLinked = localStorage.getItem(sessionLinkedKey);

    if (!isSessionLinked && !isSessionAutoLinked) {
      console.log("🔗 Auto-linking voice session for authenticated user...");

      // ✅ SET STATE IMMEDIATELY (synchronous)
      setIsSessionAutoLinked(true);

      provideEmailMutation.mutate(
        {
          sessionToken: voiceSessionToken,
          email: user.email,
          fullname: user.name || undefined,
          widgetToken,
        },
        {
          onSuccess: () => {
            console.log(
              "✅ Voice session auto-linked BEFORE LiveKit connection",
            );
            localStorage.setItem(sessionLinkedKey, "true");
            // Also mark email as captured to prevent RPC from showing OTP
            localStorage.setItem(`email_captured_${username}`, "true");
          },
          onError: (error) => {
            console.error("❌ Failed to auto-link voice session:", error);
            // Keep state as true - user is still authenticated, just API failed
            // RPC handler will retry if needed
          },
        },
      );
    } else if (isSessionLinked) {
      // Session was already linked in a previous session
      setIsSessionAutoLinked(true);
    }
  }, [
    isAuthenticated,
    isVisitor,
    voiceSessionToken,
    user,
    username,
    personaName,
    widgetToken,
    provideEmailMutation,
    isSessionAutoLinked,
  ]);

  // Step 2: Connect to LiveKit room with voice session token
  useEffect(() => {
    // Only run if session is started and not already connected/connecting
    // Also prevent multiple API calls while mutation is pending
    if (
      !sessionStarted ||
      !voiceSessionToken ||
      room.state !== "disconnected" ||
      !env.NEXT_PUBLIC_LIVEKIT_URL ||
      initVoiceSessionMutation.isPending ||
      voiceLimitExceeded
    ) {
      return;
    }

    let aborted = false;

    const connectToRoom = async () => {
      try {
        const voiceSession = await initVoiceSessionMutation.mutateAsync({
          expert_username: username,
          persona_name: personaName,
          session_token: voiceSessionToken,
          widget_token: widgetToken,
          room_config: {
            agents: [{ agent_name: username }],
          },
        });

        // Check if effect was cleaned up
        if (aborted) return;

        // Store voice session ID for heartbeat tracking
        if (voiceSession.session_id) {
          setVoiceSessionId(voiceSession.session_id);
          sessionStartTimeRef.current = Date.now();
        }

        // Use Promise.all to parallel connect microphone and room (like rappo implementation)
        await Promise.all([
          room.localParticipant.setMicrophoneEnabled(true, undefined, {
            preConnectBuffer: true,
          }),
          room.connect(voiceSession.serverUrl, voiceSession.participantToken),
        ]);

        if (!aborted) {
          setIsConnected(true);
          trackLiveKitEvent("session_connected", {
            username,
            personaName,
          });
        }
      } catch (error) {
        if (!aborted) {
          // Check for voice limit exceeded error
          if (isVoiceLimitExceededError(error)) {
            setVoiceLimitExceeded(true);
            setWasLimitExceededMidCall(false);
            trackLiveKitEvent("voice_limit_exceeded", {
              username,
              personaName,
              usedMinutes: error.usedMinutes,
              limitMinutes: error.limitMinutes,
            });
            // Reset session state
            setSessionStarted(false);
            return;
          }

          trackLiveKitEvent("connection_error", {
            error: error instanceof Error ? error.message : "Unknown error",
            username,
            personaName,
          });
          console.error("Failed to connect to LiveKit room:", error);
        }
      }
    };

    connectToRoom();

    // Cleanup function
    return () => {
      aborted = true;
      if (room.state !== "disconnected") {
        room.disconnect();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionStarted, voiceSessionToken, voiceLimitExceeded]);

  // Register RPC method for email capture
  useEffect(() => {
    if (!isConnected || !voiceSessionToken) return;

    console.log("🔧 Registering RPC method: requestEmailCapture");

    room.localParticipant.registerRpcMethod(
      "requestEmailCapture",
      async (data: {
        requestId: string;
        callerIdentity: string;
        payload: string;
      }) => {
        try {
          const captureData = JSON.parse(data.payload);
          console.log("🔔 Email capture requested by agent:", captureData);

          // ✅ PRIORITY 1: Check synchronous state flag (no race condition)
          if (isSessionAutoLinked) {
            console.log(
              "✅ Session auto-linked (state flag), returning submitted",
            );
            return JSON.stringify({
              action: "submitted",
            });
          }

          // PRIORITY 2: Check localStorage flag (for persistence across reloads)
          const sessionLinkedKey = personaName
            ? `voice_session_linked_${username}_${personaName}`
            : `voice_session_linked_${username}`;

          const isSessionLinked = localStorage.getItem(sessionLinkedKey);

          if (isSessionLinked) {
            console.log(
              "✅ Session already auto-linked (localStorage), returning submitted",
            );
            return JSON.stringify({
              action: "submitted",
            });
          }

          // PRIORITY 3: For authenticated users not yet linked (shouldn't happen but safety check)
          if (isAuthenticated && !isVisitor && user?.email) {
            console.log(
              "⚠️ Authenticated user but session not linked yet, linking now...",
            );

            try {
              // Link the session to the authenticated user's account
              await provideEmailMutation.mutateAsync({
                sessionToken: voiceSessionToken,
                email: user.email,
                fullname: user.name || undefined,
                widgetToken,
              });

              console.log("✅ Session auto-linked to authenticated user (RPC)");
              localStorage.setItem(sessionLinkedKey, "true");
              localStorage.setItem(`email_captured_${username}`, "true");

              return JSON.stringify({
                action: "submitted",
              });
            } catch (error) {
              console.error("❌ Failed to auto-link session:", error);
              return JSON.stringify({
                action: "cancelled",
              });
            }
          }

          // PRIORITY 4: Show email prompt banner for anonymous/visitor users
          return new Promise<string>((resolve) => {
            setEmailCaptureState({
              showPrompt: true,
              resolveCallback: resolve,
            });
          });
        } catch (error) {
          console.error("❌ RPC handler error:", error);
          return JSON.stringify({
            action: "cancelled",
          });
        }
      },
    );

    // Cleanup when disconnecting
    return () => {
      console.log("🔧 Cleaning up RPC method: requestEmailCapture");
    };
  }, [
    isConnected,
    voiceSessionToken,
    room,
    isAuthenticated,
    isVisitor,
    user,
    provideEmailMutation,
    widgetToken,
    username,
    personaName,
    isSessionAutoLinked,
  ]);

  // Register RPC method for agent-driven lead capture
  // The agent collects name/email/phone during conversation, then sends via RPC.
  // We POST to /sessions/{token}/capture-lead to persist + receive JWT cookie.
  useEffect(() => {
    if (!isConnected || !voiceSessionToken) return;

    console.log("🔧 Registering RPC method: leadCaptured");

    room.localParticipant.registerRpcMethod(
      "leadCaptured",
      async (data: {
        requestId: string;
        callerIdentity: string;
        payload: string;
      }) => {
        try {
          const payload: LeadCapturedRpcPayload = JSON.parse(data.payload);
          console.log("🔔 Lead captured by agent:", payload);

          const result = await captureLeadMutation.mutateAsync({
            sessionToken: payload.session_token,
            email: payload.email,
            fullname: payload.fullname,
            phone: payload.phone,
          });

          console.log("✅ Lead capture saved:", {
            email: result.email,
            isNewUser: result.is_new_user,
          });

          return JSON.stringify({ action: "saved" });
        } catch (error) {
          console.error("❌ Lead capture failed:", error);
          return JSON.stringify({
            action: "error",
            message:
              error instanceof Error ? error.message : "Lead capture failed",
          });
        }
      },
    );

    return () => {
      console.log("🔧 Cleaning up RPC method: leadCaptured");
    };
  }, [isConnected, voiceSessionToken, room, captureLeadMutation]);

  const handleToggleMute = useCallback(async () => {
    const micPublication = Array.from(
      room.localParticipant.trackPublications.values(),
    ).find((pub) => pub.kind === "audio");

    if (micPublication?.track) {
      if (isMuted) {
        await micPublication.track.unmute();
      } else {
        await micPublication.track.mute();
      }
      setIsMuted(!isMuted);
    }
  }, [room, isMuted]);

  // Heartbeat effect for tracking session duration and checking limits
  useEffect(() => {
    if (!isConnected || !voiceSessionId) return;

    // Start heartbeat interval
    heartbeatIntervalRef.current = setInterval(async () => {
      const durationSeconds = sessionStartTimeRef.current
        ? Math.floor((Date.now() - sessionStartTimeRef.current) / 1000)
        : 0;

      try {
        const response = await heartbeatMutation.mutateAsync({
          sessionId: voiceSessionId,
          durationSeconds,
        });

        // If server says to stop (limit exceeded), disconnect gracefully
        if (!response.continue_session) {
          console.log("Voice limit reached, disconnecting gracefully...");

          // Clear heartbeat interval
          if (heartbeatIntervalRef.current) {
            clearInterval(heartbeatIntervalRef.current);
            heartbeatIntervalRef.current = null;
          }

          // Disconnect room
          room.disconnect();
          setIsConnected(false);
          setSessionStarted(false);

          // Show limit exceeded UI
          setVoiceLimitExceeded(true);
          setWasLimitExceededMidCall(true);

          trackLiveKitEvent("voice_limit_exceeded_mid_call", {
            username,
            personaName,
            durationSeconds,
            reason: response.reason,
          });
        }
      } catch (error) {
        console.error("Heartbeat failed:", error);
        // Don't disconnect on heartbeat failure - it might be transient
      }
    }, HEARTBEAT_INTERVAL);

    // Cleanup on disconnect
    return () => {
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = null;
      }
    };
  }, [
    isConnected,
    voiceSessionId,
    heartbeatMutation,
    room,
    username,
    personaName,
  ]);

  const handleDisconnect = useCallback(async () => {
    // Clear heartbeat interval
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }

    room.disconnect();
    setIsConnected(false);
    setSessionStarted(false);
    setVoiceSessionId(null);
    sessionStartTimeRef.current = null;
    // Don't immediately call onDisconnect - let user see transcript button
    // onDisconnect?.();
  }, [room]);

  const handleStartVoiceSession = () => {
    setSessionStarted(true);
    setShowTranscript(true);
  };

  const handleToggleMaximize = useCallback(() => {
    setIsMaximized((prev) => !prev);
  }, []);

  const handleCloseTranscript = useCallback(() => {
    setShowTranscript(false);
  }, []);

  const handleToggleTranscript = useCallback(() => {
    // During active session, toggle side panel
    if (isConnected) {
      setShowTranscript((prev) => !prev);
    } else {
      // After session ends, toggle modal
      setShowTranscriptModal((prev) => !prev);
    }
  }, [isConnected]);

  const handleDownloadTranscript = useCallback(() => {
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

        return text;
      })
      .join("\n---\n\n");

    const blob = new Blob([transcriptText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `transcript-${username}-${new Date().toISOString().split("T")[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [transcriptMessages, expertName, username]);

  const handleBackToTextChat = useCallback(() => {
    // This is called when user explicitly clicks "Back to Text Chat"
    onDisconnect?.();
  }, [onDisconnect]);

  // Handle agent status updates (searching, fetching, generating, idle)
  const handleAgentStatus = useCallback((status: AgentStatus) => {
    setAgentStatus(status);
  }, []);

  // Handle content output — attach to the last assistant message in the transcript
  const handleContentOutput = useCallback((content: ContentOutputItem) => {
    setTranscriptMessages((prev) => {
      const lastAssistantIdx = prev.findLastIndex(
        (msg) => msg.speaker === "assistant",
      );
      if (lastAssistantIdx === -1) return prev;

      const updated = [...prev];
      updated[lastAssistantIdx] = {
        ...updated[lastAssistantIdx],
        contentOutput: content,
      };
      return updated;
    });
  }, []);

  // Handle document upload from voice interface
  const handleDocumentUploaded = useCallback((doc: UploadedDocument) => {
    // Add a user message to the transcript showing the uploaded document
    const uploadMessage: TranscriptMessage = {
      id: `upload_${doc.id}`,
      text: `Uploaded document: ${doc.filename}`,
      speaker: "user",
      timestamp: doc.timestamp,
      isComplete: true,
      attachments: [
        {
          id: doc.id,
          filename: doc.filename,
          fileType: doc.fileType,
          fileSize: doc.fileSize,
          extractionStatus: doc.extractionStatus,
        },
      ],
    };

    setTranscriptMessages((prev) => [...prev, uploadMessage]);
  }, []);

  const handleOTPComplete = useCallback(() => {
    // OTP flow completed successfully (session linked via OTP wizard)
    const currentResolveCallback = emailCaptureState.resolveCallback;
    if (currentResolveCallback) {
      // ✅ OTP flow succeeded - send "submitted" to backend via RPC
      currentResolveCallback(
        JSON.stringify({
          action: "submitted",
        }),
      );
    }

    // Mark email as captured and hide prompt
    localStorage.setItem(`email_captured_${username}`, "true");
    setEmailCaptureState({
      showPrompt: false,
      resolveCallback: null,
    });
  }, [username, emailCaptureState.resolveCallback]);

  // Show voice limit exceeded component if quota exhausted
  if (voiceLimitExceeded) {
    return (
      <VoiceLimitExceeded
        expertName={expertName}
        onSwitchToText={handleBackToTextChat}
        wasMidCall={wasLimitExceededMidCall}
        widgetToken={widgetToken}
      />
    );
  }

  // Show session time limit exceeded component if session duration limit reached
  if (sessionTimeLimitExceeded) {
    return (
      <SessionTimeLimitExceeded
        expertName={expertName}
        sessionDurationMinutes={sessionTimeLimitMinutes}
        onStartNewSession={handleStartNewSessionAfterTimeLimit}
        onGoBack={handleBackToTextChat}
        widgetToken={widgetToken}
        transcriptMessages={transcriptMessages}
        avatarUrl={avatarUrl}
      />
    );
  }

  // Check if this is the ConvoxAI Guide widget (needs special compact styling)
  // Either explicitly requested via useGuideStyle prop, or using the guide widget token
  const isGuideWidget = useGuideStyle || widgetToken === GUIDE_WIDGET_TOKEN;

  // Container styles for guide widget mode only
  const containerStyle = isGuideWidget
    ? {
        height: "100%",
        width: "100%",
        display: "flex",
        flexDirection: "column" as const,
      }
    : undefined;

  return (
    <RoomContext.Provider value={room}>
      <div style={containerStyle}>
        {/* Handle transcription with proper speaker detection */}
        {isConnected && (
          <TranscriptionHandler
            setTranscriptMessages={setTranscriptMessages}
            onContentOutput={handleContentOutput}
            onAgentStatus={handleAgentStatus}
          />
        )}

        {/* OTP Wizard Modal */}
        {emailCaptureState.showPrompt &&
          voiceSessionToken &&
          !(isAuthenticated && !isVisitor) && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
              <div className="mx-4 max-w-lg w-full">
                <OTPWizard
                  sessionToken={voiceSessionToken}
                  widgetToken={widgetToken}
                  onComplete={handleOTPComplete}
                  requireFullname={emailCaptureRequireFullname}
                  requirePhone={emailCaptureRequirePhone}
                  personaUsername={username}
                />
              </div>
            </div>
          )}

        {/* Session Time Limit Warning */}
        {sessionTimeLimitEnabled && (
          <SessionTimeLimitWarning
            isVisible={showSessionTimeLimitWarning}
            remainingSeconds={sessionTimeLimitRemainingSeconds}
            onDismiss={dismissSessionTimeLimitWarning}
          />
        )}

        <VoiceInterface
          room={room}
          sessionStarted={sessionStarted}
          isConnected={isConnected}
          isMuted={isMuted}
          showTranscript={showTranscript}
          isMaximized={isMaximized}
          transcriptMessages={transcriptMessages}
          voiceSessionToken={voiceSessionToken}
          expertName={expertName}
          avatarUrl={avatarUrl}
          widgetToken={widgetToken}
          initSessionPending={initSessionMutation.isPending}
          onStartSession={handleStartVoiceSession}
          onToggleMute={handleToggleMute}
          onDisconnect={handleBackToTextChat}
          onEndCall={handleDisconnect}
          onToggleMaximize={handleToggleMaximize}
          onCloseTranscript={handleCloseTranscript}
          onToggleTranscript={handleToggleTranscript}
          setIsMuted={setIsMuted}
          onDocumentUploaded={handleDocumentUploaded}
          sessionTimeLimitEnabled={sessionTimeLimitEnabled}
          sessionTimeLimitMinutes={sessionTimeLimitMinutes}
          sessionRemainingSeconds={sessionTimeLimitRemainingSeconds}
          useGuideStyle={isGuideWidget}
          calendarDisplayName={calendarDisplayName}
          onViewContent={setContentOutputViewer}
          agentStatus={agentStatus}
        />
        <RoomAudioRenderer />
        <StartAudio label={t("voice.buttons.enableAudio")} />

        {/* Transcript Modal */}
        <TranscriptModal
          isOpen={showTranscriptModal}
          onClose={() => setShowTranscriptModal(false)}
          transcriptMessages={transcriptMessages}
          expertName={expertName}
          avatarUrl={avatarUrl}
          onDownload={handleDownloadTranscript}
        />

        {/* Content Output Viewer */}
        <ContentOutputViewer
          content={contentOutputViewer}
          onClose={() => setContentOutputViewer(null)}
        />
      </div>
    </RoomContext.Provider>
  );
}
