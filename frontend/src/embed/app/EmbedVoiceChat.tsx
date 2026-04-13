/**
 * Embed Voice Chat Component
 * Simplified voice chat for embed widget using LiveKit
 */

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { Room, RoomEvent } from "livekit-client";
import {
  RoomAudioRenderer,
  RoomContext,
  StartAudio,
} from "@livekit/components-react";
import * as Sentry from "@sentry/nextjs";
import { useTranslation } from "../../i18n";

interface EmbedVoiceChatProps {
  expertId: string;
  personaName?: string;
  sessionToken: string | null;
  livekitUrl: string;
  onError?: (error: Error) => void;
  onDisconnect?: () => void;
}

interface TranscriptMessage {
  text: string;
  speaker: "user" | "assistant";
  timestamp: number;
}

export const EmbedVoiceChat: React.FC<EmbedVoiceChatProps> = ({
  expertId,
  personaName,
  sessionToken,
  livekitUrl,
  onError,
  onDisconnect,
}) => {
  const { t } = useTranslation();
  const [isConnected, setIsConnected] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [transcripts, setTranscripts] = useState<TranscriptMessage[]>([]);
  const [connectionToken, setConnectionToken] = useState<string | null>(null);

  const room = useMemo(() => new Room(), []);

  /**
   * Get LiveKit connection token from API
   */
  const getConnectionToken = useCallback(async () => {
    if (!sessionToken) {
      throw new Error("Session token required");
    }

    try {
      // Get LiveKit connection details from your API
      const response = await fetch(
        `${window.location.origin}/api/v1/livekit/connection-details`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({
            expert_username: expertId,
            persona_name: personaName,
            session_token: sessionToken,
            room_config: {
              agents: [{ agent_name: expertId }],
            },
          }),
        },
      );

      if (!response.ok) {
        throw new Error("Failed to get connection details");
      }

      const data = await response.json();
      return data.token;
    } catch (error) {
      Sentry.captureException(error, {
        tags: { operation: "embed_voice_token" },
        contexts: {
          voice: {
            expertId,
            personaName,
            error: error instanceof Error ? error.message : "Unknown error",
          },
        },
      });
      console.error("Connection token error:", error);
      throw error;
    }
  }, [expertId, personaName, sessionToken]);

  /**
   * Connect to LiveKit room
   */
  const connectToRoom = useCallback(async () => {
    if (!connectionToken || isConnected || isConnecting) return;

    setIsConnecting(true);

    try {
      await room.connect(livekitUrl, connectionToken);
      setIsConnected(true);

      // Setup event listeners
      room.on(RoomEvent.DataReceived, (payload: Uint8Array) => {
        try {
          const message = JSON.parse(new TextDecoder().decode(payload));
          if (message.type === "transcript") {
            setTranscripts((prev) => [
              ...prev,
              {
                text: message.text,
                speaker: message.speaker,
                timestamp: Date.now(),
              },
            ]);
          }
        } catch (error) {
          console.error("Failed to parse data:", error);
        }
      });

      room.on(RoomEvent.Disconnected, () => {
        setIsConnected(false);
        onDisconnect?.();
      });
    } catch (error) {
      Sentry.captureException(error, {
        tags: { operation: "embed_voice_connect" },
        contexts: {
          voice: {
            expertId,
            livekitUrl,
            error: error instanceof Error ? error.message : "Unknown error",
          },
        },
      });
      console.error("Failed to connect to room:", error);
      onError?.(error as Error);
      setIsConnected(false);
    } finally {
      setIsConnecting(false);
    }
  }, [
    connectionToken,
    isConnected,
    isConnecting,
    room,
    livekitUrl,
    onError,
    onDisconnect,
  ]);

  /**
   * Toggle microphone mute
   */
  const toggleMute = useCallback(() => {
    room.localParticipant.setMicrophoneEnabled(isMuted);
    setIsMuted(!isMuted);
  }, [room, isMuted]);

  /**
   * Disconnect from room
   */
  const disconnect = useCallback(() => {
    room.disconnect();
    setIsConnected(false);
    onDisconnect?.();
  }, [room, onDisconnect]);

  /**
   * Get connection token on mount
   */
  useEffect(() => {
    if (!sessionToken) return;

    getConnectionToken()
      .then((token) => setConnectionToken(token))
      .catch((error) => {
        console.error("Failed to get token:", error);
        onError?.(error);
      });
  }, [sessionToken, getConnectionToken, onError]);

  /**
   * Cleanup on unmount
   */
  useEffect(() => {
    return () => {
      room.disconnect();
    };
  }, [room]);

  return (
    <RoomContext.Provider value={room}>
      <div className="embed-voice-chat">
        <RoomAudioRenderer />
        <StartAudio label="Click to enable audio" />

        <div className="embed-voice-container">
          {/* Header */}
          <div className="embed-voice-header">
            <h3>Voice Chat</h3>
            <button
              className="embed-voice-close"
              onClick={disconnect}
              aria-label="End call"
            >
              ✕
            </button>
          </div>

          {/* Avatar/Status */}
          <div className="embed-voice-status">
            <div
              className={`embed-voice-avatar ${isConnected ? "active" : ""}`}
            >
              🎙️
            </div>
            <p className="embed-voice-status-text">
              {isConnecting
                ? t("voice.status.connecting")
                : isConnected
                  ? t("voice.status.connected")
                  : t("voice.status.readyToStart")}
            </p>
          </div>

          {/* Controls */}
          <div className="embed-voice-controls">
            {!isConnected && !isConnecting && connectionToken && (
              <button
                className="embed-voice-btn embed-voice-btn-primary"
                onClick={connectToRoom}
              >
                {t("voice.buttons.startVoiceChat")}
              </button>
            )}

            {isConnected && (
              <>
                <button
                  className={`embed-voice-btn ${isMuted ? "embed-voice-btn-danger" : "embed-voice-btn-secondary"}`}
                  onClick={toggleMute}
                >
                  {isMuted
                    ? `🔇 ${t("voice.buttons.unmute")}`
                    : `🎤 ${t("voice.buttons.mute")}`}
                </button>
                <button
                  className="embed-voice-btn embed-voice-btn-danger"
                  onClick={disconnect}
                >
                  {t("voice.buttons.endCall")}
                </button>
              </>
            )}
          </div>

          {/* Transcripts */}
          {transcripts.length > 0 && (
            <div className="embed-voice-transcripts">
              <h4>{t("voice.transcript.title")}</h4>
              <div className="embed-voice-transcript-list">
                {transcripts.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`embed-voice-transcript-msg ${msg.speaker}`}
                  >
                    <span className="speaker">
                      {msg.speaker === "user" ? t("common.you") : "Expert"}:
                    </span>
                    <span className="text">{msg.text}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </RoomContext.Provider>
  );
};
