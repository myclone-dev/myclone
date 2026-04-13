"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Room, RoomEvent } from "livekit-client";
import { RoomContext } from "@livekit/components-react";
import { AnimatePresence, motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useInitVoiceSession } from "@/lib/queries/expert/voice";
import {
  useInitSession,
  useProvideEmail,
  useCaptureLead,
  type AttachmentUploadResponse,
  type DocumentStatusMessage,
  type TextLimitExceededMessage,
  type LeadCapturedRpcPayload,
} from "@/lib/queries/expert/chat";
import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ui/conversation";
import { TooltipProvider } from "@/components/ui/tooltip";
import { MessageItem } from "../chat/MessageItem";
import { ChatInput } from "../chat/ChatInput";
import { OTPWizard } from "../chat/OTPWizard";
import { ChatEmptyState } from "../chat/ChatEmptyState";
import { SuggestedQuestions } from "../chat/SuggestedQuestions";
import { TypingIndicator } from "../chat/TypingIndicator";
import { TextChatHandler } from "./TextChatHandler";
import { TextLimitExceeded } from "../chat/TextLimitExceeded";
import { InactivityWarning } from "../chat/InactivityWarning";
import { SessionDisconnected } from "../chat/SessionDisconnected";
import { SessionTimeLimitWarning } from "../chat/SessionTimeLimitWarning";
import { SessionTimeLimitExceeded } from "../chat/SessionTimeLimitExceeded";
import { SessionTimer } from "../chat/SessionTimer";
import { EndSessionButton } from "../chat/EndSessionButton";
import { useInactivityTimeout } from "@/hooks/useInactivityTimeout";
import { useSessionTimeLimit } from "@/hooks/useSessionTimeLimit";
import { useAuthStore } from "@/store/auth.store";
import { env } from "@/env";
import { trackLiveKitEvent } from "@/lib/monitoring/sentry";
import { cn } from "@/lib/utils";
import { GUIDE_WIDGET_TOKEN } from "@/components/dashboard/personas/AssistantWidget/types";
import type { Message, MessageSource } from "@/types/expert";
import type { ContentOutputItem } from "@/types/contentOutput";
import { ContentOutputViewer } from "../chat/ContentOutputViewer";
import {
  AgentStatusIndicator,
  type AgentStatus,
} from "../chat/AgentStatusIndicator";

// Inactivity timeout configuration
const INACTIVITY_TIMEOUT_MS = 60000; // 1 minute
const WARNING_COUNTDOWN_MS = 30000; // 30 seconds

interface ExpertTextChatProps {
  username: string;
  expertName: string;
  avatarUrl?: string;
  personaName?: string;
  widgetToken?: string;
  suggestedQuestions?: string[];
  emailCaptureEnabled?: boolean;
  emailCaptureThreshold?: number;
  emailCaptureRequireFullname?: boolean;
  emailCaptureRequirePhone?: boolean;
  /** Session time limit settings */
  sessionTimeLimitEnabled?: boolean;
  sessionTimeLimitMinutes?: number;
  sessionTimeLimitWarningMinutes?: number;
  onSwitchToVoice?: () => void;
  /** Force guide-style compact UI (used in embed widget guide mode) */
  useGuideStyle?: boolean;
  /** Container element for dialogs - used in embed widget to keep dialogs within the widget */
  dialogContainer?: HTMLElement | null;
  /** Custom display name for calendar booking button (e.g., "Solicitar cita") */
  calendarDisplayName?: string;
}

export function ExpertTextChat({
  username,
  expertName,
  avatarUrl,
  personaName,
  widgetToken,
  suggestedQuestions,
  emailCaptureEnabled: _emailCaptureEnabled = false,
  emailCaptureThreshold: _emailCaptureThreshold = 5,
  emailCaptureRequireFullname = true,
  emailCaptureRequirePhone = false,
  sessionTimeLimitEnabled = false,
  sessionTimeLimitMinutes = 30,
  sessionTimeLimitWarningMinutes = 2,
  onSwitchToVoice: _onSwitchToVoice,
  useGuideStyle = false,
  dialogContainer,
  calendarDisplayName,
}: ExpertTextChatProps) {
  const { t } = useTranslation();
  const { isAuthenticated, isVisitor, user } = useAuthStore();

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [emailCaptureState, setEmailCaptureState] = useState<{
    showPrompt: boolean;
    resolveCallback: ((value: string) => void) | null;
  }>({
    showPrompt: false,
    resolveCallback: null,
  });
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingAttachments, setPendingAttachments] = useState<
    AttachmentUploadResponse[]
  >([]);
  const [isSessionAutoLinked, setIsSessionAutoLinked] = useState(false);
  // Track text limit exceeded state
  const [textLimitExceeded, setTextLimitExceeded] = useState<{
    messagesUsed: number;
    messagesLimit: number;
  } | null>(null);
  // Track session time limit exceeded state
  const [sessionLimitReached, setSessionLimitReached] = useState(false);
  // Suggested questions from LiveKit (overrides prop when received)
  const [liveKitSuggestedQuestions, setLiveKitSuggestedQuestions] = useState<
    string[] | null
  >(null);
  // Track if user has sent their first message (to hide suggested questions)
  const [hasUserSentMessage, setHasUserSentMessage] = useState(false);
  // Content output viewer state
  const [contentOutputViewer, setContentOutputViewer] =
    useState<ContentOutputItem | null>(null);
  // Agent status state (searching, fetching, generating, idle)
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);

  // Track session disconnect reason (for showing appropriate UI)
  const [disconnectReason, setDisconnectReason] = useState<
    "inactivity" | "manual" | null
  >(null);

  // Timeout ref to reset streaming state if no response received
  const streamingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  // Track connection retry attempts to prevent infinite loops
  const connectionAttemptsRef = useRef<number>(0);
  const MAX_CONNECTION_ATTEMPTS = 3;

  const room = useMemo(
    () =>
      new Room({
        adaptiveStream: false,
        dynacast: false,
      }),
    [],
  );

  // Handle inactivity disconnect
  // Note: Sentry tracking is handled in useInactivityTimeout hook
  const handleInactivityDisconnect = useCallback(() => {
    if (room.state !== "disconnected") {
      room.disconnect();
    }
    setIsConnected(false);
    setDisconnectReason("inactivity");
  }, [room]);

  // Inactivity timeout hook
  const {
    showWarning: showInactivityWarning,
    remainingSeconds: inactivityRemainingSeconds,
    dismissWarning: dismissInactivityWarning,
    recordActivity,
    resetInactivityState,
  } = useInactivityTimeout({
    inactivityMs: INACTIVITY_TIMEOUT_MS,
    warningMs: WARNING_COUNTDOWN_MS,
    onDisconnect: handleInactivityDisconnect,
    enabled: isConnected && !textLimitExceeded && !emailCaptureState.showPrompt,
    trackingContext: {
      username,
      personaName,
      mode: "text",
    },
  });

  // Handle session time limit reached
  const handleSessionLimitReached = useCallback(() => {
    trackLiveKitEvent("session_time_limit_reached", {
      username,
      personaName,
      mode: "text",
      limitMinutes: sessionTimeLimitMinutes,
    });
    if (room.state !== "disconnected") {
      room.disconnect();
    }
    setIsConnected(false);
    setSessionLimitReached(true);
  }, [room, username, personaName, sessionTimeLimitMinutes]);

  // Session time limit hook (tracks total session time, not inactivity)
  const {
    showWarning: showSessionLimitWarning,
    remainingSeconds: sessionLimitRemainingSeconds,
    dismissWarning: dismissSessionLimitWarning,
    resetSessionTimer,
  } = useSessionTimeLimit({
    limitMs: sessionTimeLimitMinutes * 60 * 1000,
    warningMs: sessionTimeLimitWarningMinutes * 60 * 1000,
    onLimitReached: handleSessionLimitReached,
    enabled:
      sessionTimeLimitEnabled &&
      isConnected &&
      !textLimitExceeded &&
      !sessionLimitReached,
    trackingContext: {
      username,
      personaName,
      mode: "text",
    },
  });

  // Handle manual session end
  const handleManualEndSession = useCallback(() => {
    trackLiveKitEvent("session_ended_manual", {
      username,
      personaName,
      mode: "text",
    });
    if (room.state !== "disconnected") {
      room.disconnect();
    }
    setIsConnected(false);
    setDisconnectReason("manual");
  }, [room, username, personaName]);

  const initSessionMutation = useInitSession();
  const initTextSessionMutation = useInitVoiceSession();
  const provideEmailMutation = useProvideEmail();
  const captureLeadMutation = useCaptureLead();

  // Refs for avoiding re-registering RPC on every render
  const provideEmailMutationRef = useRef(provideEmailMutation);
  const captureLeadMutationRef = useRef(captureLeadMutation);
  const userRef = useRef(user);

  useEffect(() => {
    provideEmailMutationRef.current = provideEmailMutation;
    captureLeadMutationRef.current = captureLeadMutation;
    userRef.current = user;
  }, [provideEmailMutation, captureLeadMutation, user]);

  // Step 1: Initialize session to get session token on mount
  useEffect(() => {
    const sessionKey = personaName
      ? `text_session_${username}_${personaName}`
      : `text_session_${username}`;
    const messagesKey = personaName
      ? `text_messages_${username}_${personaName}`
      : `text_messages_${username}`;

    const storedToken = localStorage.getItem(sessionKey);
    const storedMessages = localStorage.getItem(messagesKey);

    if (storedToken) {
      setSessionToken(storedToken);
      if (storedMessages) {
        try {
          setMessages(JSON.parse(storedMessages));
        } catch {
          // Invalid stored messages, ignore
        }
      }
    } else {
      const initializeSession = async () => {
        try {
          const data = await initSessionMutation.mutateAsync({
            username,
            personaName,
            widgetToken,
          });
          setSessionToken(data.session_token);
          localStorage.setItem(sessionKey, data.session_token);
        } catch (error) {
          trackLiveKitEvent("session_init_error", {
            error: error instanceof Error ? error.message : "Unknown error",
            username,
            personaName,
            mode: "text",
          });
          console.error("Failed to initialize text session:", error);
          setError("Unable to connect. Please try again later.");
        }
      };

      initializeSession();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [username, personaName]);

  // Save messages to localStorage
  useEffect(() => {
    if (messages.length > 0) {
      const messagesKey = personaName
        ? `text_messages_${username}_${personaName}`
        : `text_messages_${username}`;
      localStorage.setItem(messagesKey, JSON.stringify(messages));
    }
  }, [messages, username, personaName]);

  // Step 1.5: Auto-link session for authenticated users
  useEffect(() => {
    if (!isAuthenticated || isVisitor || !sessionToken || !user?.email) {
      return;
    }

    const sessionLinkedKey = personaName
      ? `text_session_linked_${username}_${personaName}`
      : `text_session_linked_${username}`;

    const isSessionLinked = localStorage.getItem(sessionLinkedKey);

    if (!isSessionLinked && !isSessionAutoLinked) {
      console.log("🔗 Auto-linking text session for authenticated user...");

      setIsSessionAutoLinked(true);

      provideEmailMutation.mutate(
        {
          sessionToken,
          email: user.email,
          fullname: user.name || undefined,
          widgetToken,
        },
        {
          onSuccess: () => {
            console.log("✅ Text session auto-linked");
            localStorage.setItem(sessionLinkedKey, "true");
            localStorage.setItem(`email_captured_${username}`, "true");
          },
          onError: (error) => {
            console.error("❌ Failed to auto-link text session:", error);
          },
        },
      );
    } else if (isSessionLinked) {
      setIsSessionAutoLinked(true);
    }
  }, [
    isAuthenticated,
    isVisitor,
    sessionToken,
    user,
    username,
    personaName,
    widgetToken,
    provideEmailMutation,
    isSessionAutoLinked,
  ]);

  // Step 2: Connect to LiveKit room with text-only mode
  const connectToRoom = useCallback(async () => {
    if (
      !sessionToken ||
      isConnected ||
      isConnecting ||
      room.state !== "disconnected" ||
      !env.NEXT_PUBLIC_LIVEKIT_URL
    ) {
      return;
    }

    // Check if we've exceeded max connection attempts
    if (connectionAttemptsRef.current >= MAX_CONNECTION_ATTEMPTS) {
      console.error(
        "❌ Max connection attempts reached. Please refresh the page.",
      );
      setError(
        "Connection failed after multiple attempts. Please refresh the page.",
      );
      return;
    }

    connectionAttemptsRef.current += 1;
    console.log(
      `🔄 Connection attempt ${connectionAttemptsRef.current}/${MAX_CONNECTION_ATTEMPTS}`,
    );

    setIsConnecting(true);

    try {
      const textSession = await initTextSessionMutation.mutateAsync({
        expert_username: username,
        persona_name: personaName,
        session_token: sessionToken,
        widget_token: widgetToken,
        room_config: {
          text_only_mode: true,
        },
      });

      // Connect to room (text-only mode - no need to enable microphone)
      await room.connect(textSession.serverUrl, textSession.participantToken);

      setIsConnected(true);
      setError(null);
      // Reset connection attempts on successful connection
      connectionAttemptsRef.current = 0;
      trackLiveKitEvent("session_connected", {
        username,
        personaName,
        mode: "text",
      });

      console.log("✅ Connected to LiveKit room (text-only mode)");
    } catch (error) {
      trackLiveKitEvent("connection_error", {
        error: error instanceof Error ? error.message : "Unknown error",
        username,
        personaName,
        mode: "text",
        attempt: connectionAttemptsRef.current,
      });
      console.error(
        `Failed to connect to LiveKit room (attempt ${connectionAttemptsRef.current}/${MAX_CONNECTION_ATTEMPTS}):`,
        error,
      );
      setError("Unable to connect. Please try again.");
    } finally {
      setIsConnecting(false);
    }
  }, [
    sessionToken,
    isConnected,
    isConnecting,
    room,
    username,
    personaName,
    widgetToken,
    initTextSessionMutation,
  ]);

  // Auto-connect when session token is available
  useEffect(() => {
    if (sessionToken && !isConnected && !isConnecting && !error) {
      connectToRoom();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionToken, isConnected, isConnecting, error]);

  // Handle room disconnection
  useEffect(() => {
    if (!room) return;

    const handleDisconnected = () => {
      console.log("📴 Disconnected from LiveKit room");
      setIsConnected(false);
    };

    room.on(RoomEvent.Disconnected, handleDisconnected);

    return () => {
      room.off(RoomEvent.Disconnected, handleDisconnected);
    };
  }, [room]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (room.state !== "disconnected") {
        room.disconnect();
      }
      // Clear streaming timeout on unmount
      if (streamingTimeoutRef.current) {
        clearTimeout(streamingTimeoutRef.current);
      }
    };
  }, [room]);

  // Register RPC method for email capture (agent-driven)
  useEffect(() => {
    if (!isConnected || !sessionToken) return;

    console.log("🔧 [Text Chat] Registering RPC method: requestEmailCapture");

    room.localParticipant.registerRpcMethod(
      "requestEmailCapture",
      async (data: {
        requestId: string;
        callerIdentity: string;
        payload: string;
      }) => {
        try {
          const captureData = JSON.parse(data.payload);
          console.log(
            "🔔 [Text Chat] Email capture requested by agent:",
            captureData,
          );

          // ✅ PRIORITY 1: Check synchronous state flag (no race condition)
          if (isSessionAutoLinked) {
            console.log(
              "✅ [Text Chat] Session auto-linked (state flag), returning submitted",
            );
            return JSON.stringify({
              action: "submitted",
            });
          }

          // PRIORITY 2: Check localStorage flag (for persistence across reloads)
          const sessionLinkedKey = personaName
            ? `text_session_linked_${username}_${personaName}`
            : `text_session_linked_${username}`;

          const isSessionLinked = localStorage.getItem(sessionLinkedKey);

          if (isSessionLinked) {
            console.log(
              "✅ [Text Chat] Session already auto-linked (localStorage), returning submitted",
            );
            return JSON.stringify({
              action: "submitted",
            });
          }

          // PRIORITY 3: For authenticated users not yet linked (shouldn't happen but safety check)
          if (isAuthenticated && !isVisitor && userRef.current?.email) {
            console.log(
              "⚠️ [Text Chat] Authenticated user but session not linked yet, linking now...",
            );

            try {
              // Link the session to the authenticated user's account
              await provideEmailMutationRef.current.mutateAsync({
                sessionToken,
                email: userRef.current.email,
                fullname: userRef.current.name || undefined,
                widgetToken,
              });

              console.log(
                "✅ [Text Chat] Session auto-linked to authenticated user (RPC)",
              );
              localStorage.setItem(sessionLinkedKey, "true");
              localStorage.setItem(`email_captured_${username}`, "true");

              return JSON.stringify({
                action: "submitted",
              });
            } catch (error) {
              console.error(
                "❌ [Text Chat] Failed to auto-link session:",
                error,
              );
              return JSON.stringify({
                action: "cancelled",
              });
            }
          }

          // PRIORITY 4: Show email prompt for anonymous/visitor users
          return new Promise<string>((resolve) => {
            setEmailCaptureState({
              showPrompt: true,
              resolveCallback: resolve,
            });
          });
        } catch (error) {
          console.error("❌ [Text Chat] RPC handler error:", error);
          return JSON.stringify({
            action: "cancelled",
          });
        }
      },
    );

    // Cleanup when disconnecting
    return () => {
      console.log("🔧 [Text Chat] Cleaning up RPC method: requestEmailCapture");
    };
  }, [
    isConnected,
    sessionToken,
    room, // Stable - created with useMemo with empty deps
    isAuthenticated,
    isVisitor,
    // Note: Not including 'user', 'provideEmailMutation' to avoid re-registration on every render
    // 'user' object may change reference frequently
    // 'provideEmailMutation' accessed via ref to keep stable
    widgetToken,
    username,
    personaName,
    isSessionAutoLinked,
  ]);

  // Register RPC method for agent-driven lead capture
  // The agent collects name/email/phone during conversation, then sends via RPC.
  // We POST to /sessions/{token}/capture-lead to persist + receive JWT cookie.
  useEffect(() => {
    if (!isConnected || !sessionToken) return;

    console.log("🔧 [Text Chat] Registering RPC method: leadCaptured");

    room.localParticipant.registerRpcMethod(
      "leadCaptured",
      async (data: {
        requestId: string;
        callerIdentity: string;
        payload: string;
      }) => {
        try {
          const payload: LeadCapturedRpcPayload = JSON.parse(data.payload);
          console.log("🔔 [Text Chat] Lead captured by agent:", payload);

          const result = await captureLeadMutationRef.current.mutateAsync({
            sessionToken: payload.session_token,
            email: payload.email,
            fullname: payload.fullname,
            phone: payload.phone,
          });

          console.log("✅ [Text Chat] Lead capture saved:", {
            email: result.email,
            isNewUser: result.is_new_user,
          });

          return JSON.stringify({ action: "saved" });
        } catch (error) {
          console.error("❌ [Text Chat] Lead capture failed:", error);
          return JSON.stringify({
            action: "error",
            message:
              error instanceof Error ? error.message : "Lead capture failed",
          });
        }
      },
    );

    return () => {
      console.log("🔧 [Text Chat] Cleaning up RPC method: leadCaptured");
    };
  }, [
    isConnected,
    sessionToken,
    room, // Stable - created with useMemo with empty deps
    // captureLeadMutation accessed via ref to keep stable
  ]);

  // Handle incoming message from agent
  // IMPORTANT: We look for streaming messages in the prev array itself,
  // not via an external ref, to avoid race conditions with React batching.
  const handleAgentMessage = useCallback(
    (
      content: string,
      isFinal: boolean,
      sources?: MessageSource[],
      calendarUrl?: string,
      contentOutput?: ContentOutputItem,
    ) => {
      // Clear the streaming timeout since we received a response
      if (streamingTimeoutRef.current) {
        clearTimeout(streamingTimeoutRef.current);
        streamingTimeoutRef.current = null;
      }

      if (process.env.NODE_ENV === "development") {
        console.log("📥 handleAgentMessage called:", {
          content: content.substring(0, 50),
          isFinal,
          calendarUrl,
        });
      }

      setMessages((prev) => {
        if (process.env.NODE_ENV === "development") {
          console.log(
            "🔧 setMessages updater called, prev length:",
            prev.length,
          );
        }

        // Find existing streaming expert message (the last expert message that is streaming)
        const streamingMessageIndex = prev.findIndex(
          (msg) => msg.sender === "expert" && msg.isStreaming,
        );

        if (streamingMessageIndex !== -1) {
          // Update existing streaming message
          if (process.env.NODE_ENV === "development") {
            console.log(
              "📝 Updating existing message at index:",
              streamingMessageIndex,
            );
          }
          const updated = [...prev];
          updated[streamingMessageIndex] = {
            ...updated[streamingMessageIndex],
            content,
            isStreaming: !isFinal,
            sources: sources || updated[streamingMessageIndex].sources,
            calendarUrl:
              calendarUrl || updated[streamingMessageIndex].calendarUrl,
            contentOutput:
              contentOutput || updated[streamingMessageIndex].contentOutput,
          };
          if (process.env.NODE_ENV === "development") {
            console.log("📝 After update, length:", updated.length);
          }
          return updated;
        } else {
          // Create new message
          const newId = Date.now().toString();
          if (process.env.NODE_ENV === "development") {
            console.log("✨ Creating new message:", newId);
          }
          const newMessages = [
            ...prev,
            {
              id: newId,
              content,
              sender: "expert" as const,
              timestamp: new Date(),
              isStreaming: !isFinal,
              sources,
              calendarUrl,
              contentOutput,
            },
          ];
          if (process.env.NODE_ENV === "development") {
            console.log("✨ After create, length:", newMessages.length);
          }
          return newMessages;
        }
      });

      if (isFinal) {
        setIsStreaming(false);
      }
    },
    [],
  );

  // Handle stream complete - mark all streaming messages as final
  const handleStreamComplete = useCallback(() => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.isStreaming ? { ...msg, isStreaming: false } : msg,
      ),
    );
    setIsStreaming(false);
  }, []);

  // Handle document status updates from LiveKit agent
  const handleDocumentStatus = useCallback((status: DocumentStatusMessage) => {
    if (process.env.NODE_ENV === "development") {
      console.log("📄 [ExpertTextChat] Document status received:", status);
    }

    if (status.status === "success") {
      // Document processed successfully by the agent
      // The agent will also send a chat message, so no additional toast needed here
      if (process.env.NODE_ENV === "development") {
        console.log(
          `✅ Document "${status.filename}" processed: ${status.chars_extracted} chars extracted`,
        );
      }
    } else if (status.status === "error") {
      // Document processing failed
      console.error(
        `❌ Document "${status.filename}" processing failed:`,
        status.message,
      );
    }
  }, []);

  // Handle text limit exceeded from LiveKit agent
  const handleTextLimitExceeded = useCallback(
    (data: TextLimitExceededMessage) => {
      if (process.env.NODE_ENV === "development") {
        console.log("⚠️ [ExpertTextChat] Text limit exceeded:", data);
      }
      setTextLimitExceeded({
        messagesUsed: data.messages_used,
        messagesLimit: data.messages_limit,
      });
      // Stop streaming state since we won't get a response
      setIsStreaming(false);
      // Clear the streaming timeout
      if (streamingTimeoutRef.current) {
        clearTimeout(streamingTimeoutRef.current);
        streamingTimeoutRef.current = null;
      }
    },
    [],
  );

  // Handle suggested questions from LiveKit agent
  const handleSuggestedQuestions = useCallback((questions: string[]) => {
    if (process.env.NODE_ENV === "development") {
      console.log(
        "💡 [ExpertTextChat] Received suggested questions:",
        questions.length,
      );
    }
    setLiveKitSuggestedQuestions(questions);
  }, []);

  // Handle agent status updates (searching, fetching, generating, idle)
  const handleAgentStatus = useCallback((status: AgentStatus) => {
    setAgentStatus(status);
  }, []);

  // Handle content output — attach to the last expert message in the array
  const handleContentOutput = useCallback((content: ContentOutputItem) => {
    setMessages((prev) => {
      // Find the last expert message and attach contentOutput to it
      const lastExpertIdx = prev.findLastIndex(
        (msg) => msg.sender === "expert",
      );
      if (lastExpertIdx === -1) return prev;

      const updated = [...prev];
      updated[lastExpertIdx] = {
        ...updated[lastExpertIdx],
        contentOutput: content,
      };
      return updated;
    });
  }, []);

  // Send message via LiveKit data channel
  const handleSendMessage = useCallback(async () => {
    const hasMessage = inputMessage.trim().length > 0;
    const hasAttachments = pendingAttachments.length > 0;

    if ((!hasMessage && !hasAttachments) || !isConnected || isStreaming) return;

    // Track that user has sent their first message (to hide suggested questions)
    if (!hasUserSentMessage) {
      setHasUserSentMessage(true);
    }

    // Record activity when user sends a message
    recordActivity();

    const attachmentNames = pendingAttachments
      .map((a) => a.filename)
      .join(", ");
    const messageToSend = hasMessage
      ? inputMessage
      : `Review ${pendingAttachments.length === 1 ? "this file" : "these files"}: ${attachmentNames}`;

    // Build full message with attachment context
    const attachmentContext = pendingAttachments
      .map((a) => {
        if (a.extracted_text) {
          return `[Attachment: ${a.filename}]\n${a.extracted_text}`;
        }
        return `[Attachment: ${a.filename}]\nFile URL: ${a.s3_url}\nExtraction Status: ${a.extraction_status}`;
      })
      .join("\n\n");

    const fullMessage =
      hasAttachments && attachmentContext
        ? `${messageToSend}\n\n---\nAttachment Content:\n${attachmentContext}`
        : messageToSend;

    // Add user message to UI
    const userMessage: Message = {
      id: Date.now().toString(),
      content: messageToSend,
      sender: "user",
      timestamp: new Date(),
      attachments: hasAttachments
        ? pendingAttachments.map((a) => ({
            id: a.attachment_id,
            filename: a.filename,
            file_type: a.file_type,
            file_size: a.file_size,
            s3_url: a.s3_url,
            extraction_status: a.extraction_status,
          }))
        : undefined,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputMessage("");
    setPendingAttachments([]);
    setIsStreaming(true);

    // Set a safety timeout to reset streaming state if no response in 30 seconds
    if (streamingTimeoutRef.current) {
      clearTimeout(streamingTimeoutRef.current);
    }
    streamingTimeoutRef.current = setTimeout(() => {
      if (process.env.NODE_ENV === "development") {
        console.log("⏱️ Streaming timeout - resetting state");
      }
      setIsStreaming(false);
      streamingTimeoutRef.current = null;
    }, 30000); // 30 second timeout

    try {
      // Send message via LiveKit text stream
      // Architecture: Client sends on "lk.chat" → Agent receives → Agent sends on "lk.transcription"
      const messageData = JSON.stringify({ message: fullMessage });
      const sendTopic = "lk.chat";

      // Use sendText() with proper options object for text-only agents
      await room.localParticipant.sendText(messageData, {
        topic: sendTopic,
      });

      if (process.env.NODE_ENV === "development") {
        console.log(
          `📤 [SEND Topic: ${sendTopic}] Message sent via sendText:`,
          messageToSend.substring(0, 50),
        );
      }
    } catch (error) {
      console.error("Failed to send message:", error);
      setIsStreaming(false);
      if (streamingTimeoutRef.current) {
        clearTimeout(streamingTimeoutRef.current);
        streamingTimeoutRef.current = null;
      }
      setError("Failed to send message. Please try again.");
    }
  }, [
    inputMessage,
    pendingAttachments,
    isConnected,
    isStreaming,
    room,
    recordActivity,
    hasUserSentMessage,
  ]);

  const handleAttachmentUploaded = (attachment: AttachmentUploadResponse) => {
    setPendingAttachments((prev) => [...prev, attachment]);
    recordActivity(); // User uploaded an attachment
  };

  const handleAttachmentRemoved = (attachmentId: string) => {
    setPendingAttachments((prev) =>
      prev.filter((a) => a.attachment_id !== attachmentId),
    );
    recordActivity(); // User removed an attachment
  };

  // Handle input change with activity tracking
  const handleInputChange = useCallback(
    (value: string) => {
      setInputMessage(value);
      recordActivity(); // User is typing
    },
    [recordActivity],
  );

  // Handle suggested question click with activity tracking
  const handleSuggestedQuestionClick = useCallback(
    (question: string) => {
      setInputMessage(question);
      recordActivity(); // User clicked a suggested question
    },
    [recordActivity],
  );

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

  // Retry connection if failed
  const handleRetryConnection = () => {
    // Reset connection attempts on manual retry
    connectionAttemptsRef.current = 0;
    setError(null);
    connectToRoom();
  };

  // Reconnect after inactivity/manual disconnect
  const handleReconnect = useCallback(() => {
    trackLiveKitEvent("session_reconnect_attempt", {
      username,
      personaName,
      mode: "text",
      previousReason: disconnectReason,
    });
    // Reset connection attempts on manual reconnect
    connectionAttemptsRef.current = 0;
    setDisconnectReason(null);
    resetInactivityState();
    setError(null);
    connectToRoom();
  }, [
    disconnectReason,
    resetInactivityState,
    connectToRoom,
    username,
    personaName,
  ]);

  // Start new session after time limit exceeded
  const handleStartNewSession = useCallback(() => {
    trackLiveKitEvent("session_new_after_time_limit", {
      username,
      personaName,
      mode: "text",
    });
    // Reset connection attempts for new session
    connectionAttemptsRef.current = 0;
    setSessionLimitReached(false);
    resetSessionTimer();
    resetInactivityState();
    setError(null);
    connectToRoom();
  }, [
    resetSessionTimer,
    resetInactivityState,
    connectToRoom,
    username,
    personaName,
  ]);

  // Track successful reconnection
  useEffect(() => {
    if (isConnected && disconnectReason === null) {
      // Connection established - could be initial or reconnect
      // We only track if there was a previous disconnect reason that was just cleared
    }
  }, [isConnected, disconnectReason]);

  // Check if this is the ConvoxAI Guide widget (needs special compact styling)
  // Either by the special token OR by explicit useGuideStyle prop (for embed widget guide mode)
  const isGuideWidget = widgetToken === GUIDE_WIDGET_TOKEN || useGuideStyle;

  const containerClass = isGuideWidget
    ? "w-full mx-auto h-full"
    : "w-full max-w-4xl mx-auto";

  return (
    <RoomContext.Provider value={room}>
      <TooltipProvider>
        {/* Handle incoming data messages - always render to catch early messages */}
        <TextChatHandler
          onMessage={handleAgentMessage}
          onStreamComplete={handleStreamComplete}
          onDocumentStatus={handleDocumentStatus}
          onTextLimitExceeded={handleTextLimitExceeded}
          onSuggestedQuestions={handleSuggestedQuestions}
          onContentOutput={handleContentOutput}
          onAgentStatus={handleAgentStatus}
        />

        {/* Content Output Viewer Sheet */}
        <ContentOutputViewer
          content={contentOutputViewer}
          onClose={() => setContentOutputViewer(null)}
        />

        <div
          className={`relative ${containerClass}`}
          style={
            isGuideWidget
              ? { height: "100%", display: "flex", flexDirection: "column" }
              : undefined
          }
        >
          {/* Chat Container */}
          <div
            className={cn(
              "overflow-hidden flex flex-col relative",
              isGuideWidget
                ? "bg-white" // In guide widget mode, use solid background
                : "bg-white/90 backdrop-blur-sm border border-gray-200/50 shadow-xl",
            )}
            style={{
              flex: isGuideWidget ? 1 : undefined,
              minHeight: isGuideWidget ? 0 : undefined,
              height: isGuideWidget
                ? undefined
                : "min(600px, calc(100vh - 6rem))",
              borderRadius: isGuideWidget ? "0" : "24px",
            }}
            onClick={recordActivity}
            onKeyDown={recordActivity}
          >
            {/* End Session Button and Session Timer - shown when connected */}
            {isConnected && !disconnectReason && (
              <div className="absolute top-3 right-3 z-30 flex items-center gap-2">
                {/* Session Time Limit Timer */}
                {sessionTimeLimitEnabled && (
                  <SessionTimer
                    remainingSeconds={sessionLimitRemainingSeconds}
                    totalMinutes={sessionTimeLimitMinutes}
                    isActive={true}
                    compact
                  />
                )}
                <EndSessionButton
                  onEndSession={handleManualEndSession}
                  disabled={isStreaming}
                  dialogContainer={dialogContainer}
                />
              </div>
            )}

            {/* Inactivity Warning Overlay */}
            <InactivityWarning
              isVisible={showInactivityWarning}
              remainingSeconds={inactivityRemainingSeconds}
              onDismiss={dismissInactivityWarning}
            />

            {/* Session Time Limit Warning Overlay */}
            <SessionTimeLimitWarning
              isVisible={showSessionLimitWarning && !sessionLimitReached}
              remainingSeconds={sessionLimitRemainingSeconds}
              onDismiss={dismissSessionLimitWarning}
            />

            {/* Session Disconnected Overlay */}
            <SessionDisconnected
              isVisible={!!disconnectReason}
              reason={disconnectReason || "inactivity"}
              onReconnect={handleReconnect}
              isReconnecting={isConnecting}
              messages={messages}
              expertName={expertName}
              username={username}
              personaName={personaName}
            />

            {/* Connection Status Overlay - shown when not connected and no disconnect reason */}
            {!isConnected && !error && !disconnectReason && (
              <div className="absolute inset-0 z-20 flex items-center justify-center bg-white/80 backdrop-blur-sm rounded-3xl">
                <div className="flex flex-col items-center gap-4 p-8">
                  <div className="relative">
                    <div className="h-12 w-12 rounded-full border-4 border-yellow-light border-t-yellow-bright animate-spin" />
                  </div>
                  <div className="text-center">
                    <p className="text-lg font-medium text-gray-800">
                      {isConnecting
                        ? t("chat.connection.connecting")
                        : t("chat.connection.settingUp")}
                    </p>
                    <p className="text-sm text-gray-500 mt-1">
                      {t("chat.connection.takeMoment")}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Session Time Limit Exceeded State */}
            {sessionLimitReached ? (
              <SessionTimeLimitExceeded
                expertName={expertName}
                sessionDurationMinutes={sessionTimeLimitMinutes}
                onStartNewSession={handleStartNewSession}
                widgetToken={widgetToken}
                avatarUrl={avatarUrl}
                transcriptMessages={messages.map((msg) => ({
                  id: msg.id,
                  text: msg.content,
                  speaker: msg.sender === "user" ? "user" : "assistant",
                  timestamp: msg.timestamp.getTime(),
                  isComplete: !msg.isStreaming,
                  citations: msg.sources?.map((s, i) => ({
                    index: i,
                    url: s.source_url,
                    title: s.title,
                    content: s.content,
                    raw_source: s.source,
                    source_type: s.type,
                  })),
                }))}
              />
            ) : /* Text Limit Exceeded State */
            textLimitExceeded ? (
              <TextLimitExceeded
                expertName={expertName}
                messagesUsed={textLimitExceeded.messagesUsed}
                messagesLimit={textLimitExceeded.messagesLimit}
                voiceAvailable={true}
                onSwitchToVoice={() => {
                  setTextLimitExceeded(null);
                  _onSwitchToVoice?.();
                }}
                onGoBack={() => setTextLimitExceeded(null)}
              />
            ) : (
              <>
                {/* Error Banner */}
                {error && (
                  <div className="shrink-0 border-b border-gray-200/50 bg-red-50 px-4 py-2 flex items-center justify-between">
                    <span className="text-sm text-red-700">{error}</span>
                    <button
                      onClick={handleRetryConnection}
                      className="text-sm text-red-600 hover:text-red-800 underline"
                    >
                      Retry
                    </button>
                  </div>
                )}

                {/* Email Prompt Banner */}
                <AnimatePresence>
                  {emailCaptureState.showPrompt && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="shrink-0 border-b border-gray-200/50 bg-peach-cream"
                    >
                      <div className="p-4">
                        <OTPWizard
                          sessionToken={sessionToken || ""}
                          widgetToken={widgetToken}
                          onComplete={handleOTPComplete}
                          requireFullname={emailCaptureRequireFullname}
                          requirePhone={emailCaptureRequirePhone}
                          personaUsername={username}
                        />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Messages */}
                <Conversation
                  className={cn(
                    "flex-1 relative",
                    isGuideWidget ? "bg-white" : "bg-white/50",
                  )}
                >
                  <ConversationContent className="p-6 space-y-3">
                    {/* Empty state shown only when no messages */}
                    {messages.length === 0 && (
                      <ChatEmptyState
                        expertName={expertName}
                        avatarUrl={avatarUrl}
                        error={error}
                      />
                    )}

                    {/* Messages list */}
                    {messages.length > 0 && (
                      <div className="space-y-3 max-w-full">
                        {messages
                          .filter((message) => !message.hidden)
                          .map((message) => (
                            <MessageItem
                              key={message.id}
                              message={message}
                              calendarDisplayName={calendarDisplayName}
                              onViewContent={setContentOutputViewer}
                            />
                          ))}
                        {/* Agent status indicator (searching, fetching, generating) */}
                        <AgentStatusIndicator agentStatus={agentStatus} />

                        {/* Typing indicator - show when streaming and no expert message is currently streaming */}
                        {isStreaming &&
                          !messages.some(
                            (m) => m.sender === "expert" && m.isStreaming,
                          ) && (
                            <div className="flex justify-start">
                              <div className="bg-white border border-gray-200 rounded-2xl px-4 py-3 shadow-sm">
                                <TypingIndicator variant="dots" />
                              </div>
                            </div>
                          )}
                      </div>
                    )}

                    {/* Suggested questions - only on fresh chats with no user messages in history */}
                    {!hasUserSentMessage &&
                      !messages.some((m) => m.sender === "user") &&
                      (() => {
                        // Prefer LiveKit questions if received, fall back to prop
                        const questionsToShow =
                          liveKitSuggestedQuestions ?? suggestedQuestions;
                        return (
                          questionsToShow &&
                          questionsToShow.length > 0 && (
                            <SuggestedQuestions
                              questions={questionsToShow}
                              onQuestionClick={handleSuggestedQuestionClick}
                              disabled={
                                !isConnected ||
                                isStreaming ||
                                emailCaptureState.showPrompt
                              }
                            />
                          )
                        );
                      })()}
                  </ConversationContent>
                  <ConversationScrollButton />

                  {/* Overlay when email prompt is shown */}
                  {emailCaptureState.showPrompt && (
                    <div className="absolute inset-0 bg-white/60 backdrop-blur-[2px] pointer-events-none z-10" />
                  )}
                </Conversation>

                {/* Input Area */}
                <ChatInput
                  value={inputMessage}
                  onChange={handleInputChange}
                  onSend={handleSendMessage}
                  disabled={!isConnected || emailCaptureState.showPrompt}
                  isLoading={isStreaming}
                  placeholder={
                    emailCaptureState.showPrompt
                      ? t("chat.input.provideInfo")
                      : !isConnected
                        ? t("chat.connection.connecting")
                        : `Message ${expertName?.split(" ")[0] || "expert"}...`
                  }
                  sessionToken={sessionToken}
                  widgetToken={widgetToken}
                  onAttachmentUploaded={handleAttachmentUploaded}
                  onAttachmentRemoved={handleAttachmentRemoved}
                  attachments={pendingAttachments}
                  maxAttachments={5}
                  room={isConnected ? room : null}
                />
              </>
            )}
          </div>
        </div>
      </TooltipProvider>
    </RoomContext.Provider>
  );
}
