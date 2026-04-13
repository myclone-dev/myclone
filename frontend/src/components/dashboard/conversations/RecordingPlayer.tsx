"use client";

import { useRef, useState, useEffect, useCallback } from "react";
import {
  Play,
  Pause,
  Download,
  Volume2,
  VolumeX,
  AlertCircle,
  Loader2,
  Radio,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import type { RecordingStatus } from "@/lib/queries/conversations";

interface RecordingPlayerProps {
  recordingUrl: string | null;
  recordingStatus: RecordingStatus | null;
  durationSeconds: number | null;
  conversationId: string;
}

function formatTime(seconds: number): string {
  if (!isFinite(seconds) || seconds < 0) return "0:00";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export function RecordingPlayer({
  recordingUrl,
  recordingStatus,
  durationSeconds,
  conversationId,
}: RecordingPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(durationSeconds || 0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [volume, setVolume] = useState(1);

  // Check if player should be shown
  const isCompleted = recordingStatus === "completed";
  const hasUrl = !!recordingUrl;

  // Handle audio events - only attach when completed with URL
  useEffect(() => {
    if (!isCompleted || !hasUrl) return;

    const audio = audioRef.current;
    if (!audio) return;

    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
    };

    const handleLoadedMetadata = () => {
      setDuration(audio.duration);
      setIsLoading(false);
    };

    const handleEnded = () => {
      setIsPlaying(false);
      setCurrentTime(0);
    };

    const handleError = () => {
      setError("Failed to load recording");
      setIsLoading(false);
      setIsPlaying(false);
      trackDashboardOperation("conversation_view", "error", {
        error: "recording_playback_error",
        conversationId,
        recordingStatus,
      });
    };

    const handleWaiting = () => {
      setIsLoading(true);
    };

    const handleCanPlay = () => {
      setIsLoading(false);
    };

    audio.addEventListener("timeupdate", handleTimeUpdate);
    audio.addEventListener("loadedmetadata", handleLoadedMetadata);
    audio.addEventListener("ended", handleEnded);
    audio.addEventListener("error", handleError);
    audio.addEventListener("waiting", handleWaiting);
    audio.addEventListener("canplay", handleCanPlay);

    return () => {
      audio.removeEventListener("timeupdate", handleTimeUpdate);
      audio.removeEventListener("loadedmetadata", handleLoadedMetadata);
      audio.removeEventListener("ended", handleEnded);
      audio.removeEventListener("error", handleError);
      audio.removeEventListener("waiting", handleWaiting);
      audio.removeEventListener("canplay", handleCanPlay);
    };
  }, [isCompleted, hasUrl, conversationId, recordingStatus]);

  const togglePlayPause = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !recordingUrl) return;

    if (isPlaying) {
      audio.pause();
      setIsPlaying(false);
    } else {
      setIsLoading(true);
      audio
        .play()
        .then(() => {
          setIsPlaying(true);
          setIsLoading(false);
          trackDashboardOperation("conversation_view", "success", {
            action: "recording_playback_start",
            conversationId,
            durationSeconds,
          });
        })
        .catch((err) => {
          setError("Failed to play recording");
          setIsLoading(false);
          trackDashboardOperation("conversation_view", "error", {
            error: "recording_playback_error",
            errorMessage: err.message,
            conversationId,
          });
        });
    }
  }, [isPlaying, recordingUrl, conversationId, durationSeconds]);

  const handleSeek = useCallback((value: number[]) => {
    const audio = audioRef.current;
    if (!audio) return;

    const newTime = value[0];
    audio.currentTime = newTime;
    setCurrentTime(newTime);
  }, []);

  const toggleMute = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;

    audio.muted = !isMuted;
    setIsMuted(!isMuted);
  }, [isMuted]);

  const handleVolumeChange = useCallback((value: number[]) => {
    const audio = audioRef.current;
    if (!audio) return;

    const newVolume = value[0];
    audio.volume = newVolume;
    setVolume(newVolume);
    setIsMuted(newVolume === 0);
  }, []);

  const handleDownload = useCallback(() => {
    if (!recordingUrl) return;

    trackDashboardOperation("conversation_view", "success", {
      action: "recording_download",
      conversationId,
      durationSeconds,
    });

    // Open in new tab for download
    window.open(recordingUrl, "_blank");
  }, [recordingUrl, conversationId, durationSeconds]);

  // Don't render if recording is disabled or no status
  if (!recordingStatus || recordingStatus === "disabled") {
    return null;
  }

  // Render status badge for non-completed recordings
  if (!isCompleted) {
    return (
      <div className="flex items-center gap-2 px-3 py-2.5 sm:px-4 sm:py-3">
        <Radio className="size-4 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">Voice Recording</span>
        {recordingStatus === "active" && (
          <Badge variant="default" className="ml-auto bg-red-500">
            <span className="mr-1 inline-block size-2 animate-pulse rounded-full bg-white" />
            Recording in progress
          </Badge>
        )}
        {recordingStatus === "starting" && (
          <Badge variant="secondary" className="ml-auto">
            <Loader2 className="mr-1 size-3 animate-spin" />
            Starting...
          </Badge>
        )}
        {recordingStatus === "stopping" && (
          <Badge variant="secondary" className="ml-auto">
            <Loader2 className="mr-1 size-3 animate-spin" />
            Stopping...
          </Badge>
        )}
        {(recordingStatus === "failed" || recordingStatus === "stopped") && (
          <Badge variant="destructive" className="ml-auto">
            <AlertCircle className="mr-1 size-3" />
            {recordingStatus === "failed"
              ? "Recording failed"
              : "Recording stopped"}
          </Badge>
        )}
      </div>
    );
  }

  // No URL for completed recording
  if (!hasUrl) {
    return (
      <div className="flex items-center gap-2 px-3 py-2.5 sm:px-4 sm:py-3">
        <AlertCircle className="size-4 text-muted-foreground" />
        <span className="text-sm text-muted-foreground">
          Recording unavailable
        </span>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex items-center gap-2 border-red-200 bg-red-50 px-3 py-2.5 sm:px-4 sm:py-3">
        <AlertCircle className="size-4 text-red-500" />
        <span className="text-sm text-red-600">{error}</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setError(null)}
          className="ml-auto text-red-600 hover:text-red-700"
        >
          Retry
        </Button>
      </div>
    );
  }

  // Full player for completed recordings with URL
  return (
    <div className="px-3 py-2.5 sm:px-4 sm:py-3">
      {/* Hidden audio element */}
      <audio ref={audioRef} src={recordingUrl} preload="metadata" />

      {/* Player UI */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Play/Pause button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={togglePlayPause}
          disabled={isLoading}
          className="size-9 shrink-0 rounded-full bg-primary text-primary-foreground hover:bg-primary/90 sm:size-10"
          aria-label={isPlaying ? "Pause" : "Play"}
        >
          {isLoading ? (
            <Loader2 className="size-4 animate-spin sm:size-5" />
          ) : isPlaying ? (
            <Pause className="size-4 sm:size-5" />
          ) : (
            <Play className="size-4 pl-0.5 sm:size-5" />
          )}
        </Button>

        {/* Progress section */}
        <div className="flex flex-1 items-center gap-2 sm:gap-3">
          {/* Current time */}
          <span className="w-10 text-right text-xs tabular-nums text-muted-foreground sm:w-12 sm:text-sm">
            {formatTime(currentTime)}
          </span>

          {/* Progress bar */}
          <Slider
            value={[currentTime]}
            max={duration || 1}
            step={0.1}
            onValueChange={handleSeek}
            className="flex-1"
            aria-label="Seek"
          />

          {/* Duration */}
          <span className="w-10 text-xs tabular-nums text-muted-foreground sm:w-12 sm:text-sm">
            {formatTime(duration)}
          </span>
        </div>

        {/* Volume control - Desktop only */}
        <div className="hidden items-center gap-1 sm:flex">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleMute}
            className="size-8 shrink-0"
            aria-label={isMuted ? "Unmute" : "Mute"}
          >
            {isMuted || volume === 0 ? (
              <VolumeX className="size-4" />
            ) : (
              <Volume2 className="size-4" />
            )}
          </Button>
          <Slider
            value={[isMuted ? 0 : volume]}
            max={1}
            step={0.1}
            onValueChange={handleVolumeChange}
            className="w-20"
            aria-label="Volume"
          />
        </div>

        {/* Download button */}
        <Button
          variant="outline"
          size="sm"
          onClick={handleDownload}
          className={cn("shrink-0 gap-1.5", "h-8 px-2 sm:h-9 sm:px-3")}
          aria-label="Download recording"
        >
          <Download className="size-3.5 sm:size-4" />
          <span className="hidden sm:inline">Download</span>
        </Button>
      </div>
    </div>
  );
}
