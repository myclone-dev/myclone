"use client";

import { useState, useRef, useEffect } from "react";
import { Mic, Square, Play, Trash2, Upload, Check, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { toast } from "sonner";

interface VoiceRecordingScriptProps {
  onRecordingsComplete: (recordings: File[]) => void;
  userName?: string;
  userExpertise?: string;
  isSubmitting?: boolean;
}

const MINIMUM_DURATION = 10; // 10 seconds minimum for Cartesia
const MAXIMUM_DURATION = 30; // 30 seconds maximum for optimal voice cloning

// Detect best supported audio format for recording
// Cartesia prefers WebM format for voice cloning
const getSupportedAudioFormat = (): {
  mimeType: string;
  extension: string;
} => {
  // Prefer WebM (better compatibility with Cartesia), then MP4
  const formats = [
    { mimeType: "audio/webm;codecs=opus", extension: "webm" },
    { mimeType: "audio/webm", extension: "webm" },
    { mimeType: "audio/mp4", extension: "m4a" },
    { mimeType: "audio/ogg;codecs=opus", extension: "ogg" },
  ];

  for (const format of formats) {
    if (
      typeof MediaRecorder !== "undefined" &&
      MediaRecorder.isTypeSupported(format.mimeType)
    ) {
      return format;
    }
  }

  // Fallback to webm if nothing is explicitly supported
  return { mimeType: "audio/webm", extension: "webm" };
};

export function VoiceRecordingScript({
  onRecordingsComplete,
  userName = "your name",
  userExpertise = "your expertise",
  isSubmitting = false,
}: VoiceRecordingScriptProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingBlob, setRecordingBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioFormat, setAudioFormat] = useState<{
    mimeType: string;
    extension: string;
  }>({ mimeType: "audio/webm", extension: "webm" });

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number>(0);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const scriptText = `Hi there! I'm ${userName}, and I work in ${userExpertise}. Over the years, I've learned that the best insights often come from asking the right questions and staying curious. Whether you're looking for quick advice, want to dive deep into a topic, or just need someone to bounce ideas off of, I'm here to help. I believe every challenge has a solution waiting to be discovered. What's on your mind today? Let's figure it out together.`;

  useEffect(() => {
    // Detect supported audio format
    const format = getSupportedAudioFormat();
    setAudioFormat(format);

    // Request microphone permission on mount
    if (typeof window !== "undefined") {
      navigator.mediaDevices
        .getUserMedia({ audio: true })
        .catch(() => console.error("Microphone permission denied"));
    }

    // Cleanup
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Use detected audio format
      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: audioFormat.mimeType,
      });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        console.log(
          `[VoiceRecording] Data available: ${e.data.size} bytes, chunks so far: ${chunksRef.current.length}`,
        );
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        // Combine all chunks into a single blob
        const totalChunks = chunksRef.current.length;
        const blob = new Blob(chunksRef.current, {
          type: audioFormat.mimeType,
        });
        const url = URL.createObjectURL(blob);

        console.log(
          `[VoiceRecording] Recording stopped. Total chunks: ${totalChunks}, blob: ${blob.size} bytes, type: ${blob.type}`,
        );

        // Warn if blob is suspiciously small (less than 50KB for 10+ seconds)
        if (blob.size < 50000) {
          console.warn(
            `[VoiceRecording] WARNING: Blob size (${blob.size} bytes) is suspiciously small. Recording may have failed.`,
          );
        }

        setRecordingBlob(blob);
        setAudioUrl(url);

        // Stop all tracks
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
        }
      };

      // Request data every 1 second to ensure we capture all audio
      // Without timeslice, ondataavailable only fires once at stop() which can
      // result in empty/small blobs if there are any timing issues
      mediaRecorder.start(1000);
      setIsRecording(true);
      startTimeRef.current = Date.now();
      setRecordingDuration(0);

      // Start timer
      timerRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000);
        setRecordingDuration(elapsed);

        // Auto-stop recording at exactly maximum duration
        if (elapsed === MAXIMUM_DURATION) {
          if (
            mediaRecorderRef.current &&
            mediaRecorderRef.current.state === "recording"
          ) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);

            if (timerRef.current) {
              clearInterval(timerRef.current);
              timerRef.current = null;
            }

            toast.success("Recording complete!", {
              description: `Maximum duration of ${MAXIMUM_DURATION} seconds reached. Your recording is ready.`,
            });
          }
        }
      }, 1000);
    } catch (error) {
      console.error("Failed to start recording:", error);
      toast.error("Microphone access denied", {
        description: "Please allow microphone access to record your voice.",
      });
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);

      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      // Check duration requirements
      if (recordingDuration < MINIMUM_DURATION) {
        toast.error("Recording too short", {
          description: `Please record at least ${MINIMUM_DURATION} seconds. You recorded ${recordingDuration} seconds.`,
        });
      } else {
        toast.success("Recording saved!", {
          description: `${recordingDuration} seconds recorded successfully.`,
        });
      }
    }
  };

  const playRecording = () => {
    if (audioUrl) {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }

      const audio = new Audio(audioUrl);
      audioRef.current = audio;

      audio.onplay = () => setIsPlaying(true);
      audio.onended = () => setIsPlaying(false);
      audio.onpause = () => setIsPlaying(false);

      audio.play();
    }
  };

  const stopPlayback = () => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
      setIsPlaying(false);
    }
  };

  const deleteRecording = () => {
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }

    stopPlayback();
    setRecordingBlob(null);
    setAudioUrl(null);
    setRecordingDuration(0);

    toast.info("Recording deleted");
  };

  const handleSubmit = () => {
    if (!recordingBlob) {
      toast.error("No recording found", {
        description: "Please record your voice before submitting.",
      });
      return;
    }

    if (recordingDuration < MINIMUM_DURATION) {
      toast.error("Recording too short", {
        description: `Recording must be at least ${MINIMUM_DURATION} seconds long.`,
      });
      return;
    }

    if (recordingDuration > MAXIMUM_DURATION) {
      toast.error("Recording too long", {
        description: `Recording must be ${MAXIMUM_DURATION} seconds or less.`,
      });
      return;
    }

    const file = new File(
      [recordingBlob],
      `voice-sample.${audioFormat.extension}`,
      {
        type: audioFormat.mimeType,
      },
    );

    onRecordingsComplete([file]);
  };

  const meetsMinimumDuration = recordingDuration >= MINIMUM_DURATION;
  const meetsMaximumDuration = recordingDuration <= MAXIMUM_DURATION;
  const meetsAllDurationRequirements =
    meetsMinimumDuration && meetsMaximumDuration;

  return (
    <div className="space-y-6">
      {/* Instructions */}
      <Alert>
        <Clock className="size-4" />
        <AlertDescription>
          Record yourself reading the script below. Duration: {MINIMUM_DURATION}
          -{MAXIMUM_DURATION} seconds. Speak naturally and clearly for the best
          results.
        </AlertDescription>
      </Alert>

      {/* Script Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Voice Sample Script</CardTitle>
            {isRecording && (
              <Badge variant="destructive" className="animate-pulse">
                Recording {formatTime(recordingDuration)}
              </Badge>
            )}
            {!isRecording && recordingBlob && (
              <Badge
                variant={meetsAllDurationRequirements ? "default" : "secondary"}
              >
                {formatTime(recordingDuration)}{" "}
                {!meetsMinimumDuration && "(too short)"}
                {meetsMinimumDuration && !meetsMaximumDuration && "(too long)"}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Script Text */}
          <div className="rounded-lg bg-muted p-6">
            <p className="text-base leading-relaxed text-foreground/90">
              {scriptText}
            </p>
          </div>

          {/* Recording Timer */}
          {isRecording && (
            <div className="flex items-center justify-center">
              <div className="text-center space-y-2">
                <div className="text-3xl font-bold tabular-nums text-primary">
                  {formatTime(recordingDuration)}
                </div>
                <div className="text-sm text-muted-foreground">
                  {recordingDuration < MINIMUM_DURATION
                    ? `${MINIMUM_DURATION - recordingDuration}s remaining to reach minimum`
                    : recordingDuration >= MAXIMUM_DURATION
                      ? "Stopping..."
                      : `Recording... (auto-stops in ${MAXIMUM_DURATION - recordingDuration}s)`}
                </div>
              </div>
            </div>
          )}

          {/* Recording Controls */}
          <div className="flex items-center justify-center gap-4">
            {!isRecording && !recordingBlob && (
              <Button size="lg" onClick={startRecording} className="gap-2 px-8">
                <Mic className="size-5" />
                Start Recording
              </Button>
            )}

            {isRecording && (
              <Button
                size="lg"
                variant="destructive"
                onClick={stopRecording}
                className="gap-2 px-8"
              >
                <Square className="size-5" />
                Stop Recording
              </Button>
            )}

            {!isRecording && recordingBlob && (
              <div className="flex gap-2">
                {!isPlaying ? (
                  <Button
                    size="lg"
                    variant="outline"
                    onClick={playRecording}
                    className="gap-2"
                  >
                    <Play className="size-5" />
                    Play
                  </Button>
                ) : (
                  <Button
                    size="lg"
                    variant="outline"
                    onClick={stopPlayback}
                    className="gap-2"
                  >
                    <Square className="size-5" />
                    Stop
                  </Button>
                )}
                <Button
                  size="lg"
                  variant="outline"
                  onClick={deleteRecording}
                  className="gap-2"
                >
                  <Trash2 className="size-5" />
                  Delete
                </Button>
                <Button size="lg" onClick={startRecording} className="gap-2">
                  <Mic className="size-5" />
                  Re-record
                </Button>
              </div>
            )}
          </div>

          {/* Status */}
          {!isRecording && recordingBlob && (
            <div
              className={`flex items-center justify-center gap-2 text-sm ${
                meetsAllDurationRequirements
                  ? "text-green-600"
                  : "text-orange-600"
              }`}
            >
              <Check className="size-4" />
              <span>
                {meetsAllDurationRequirements
                  ? "Recording meets duration requirements"
                  : !meetsMinimumDuration
                    ? `Recording too short - need ${MINIMUM_DURATION - recordingDuration}s more`
                    : `Recording too long - please re-record under ${MAXIMUM_DURATION}s`}
              </span>
            </div>
          )}

          {/* Submit Button */}
          {!isRecording && recordingBlob && (
            <div className="pt-4 border-t">
              <Button
                onClick={handleSubmit}
                disabled={!meetsAllDurationRequirements || isSubmitting}
                className="w-full gap-2"
                size="lg"
              >
                <Upload className="size-4" />
                {isSubmitting ? "Submitting..." : "Submit Recording"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
