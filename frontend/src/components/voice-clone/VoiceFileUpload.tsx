"use client";

import { useState, useRef } from "react";
import { FileAudio, Upload, Play, Square, Trash2, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

// Cartesia supported languages for voice cloning
const CARTESIA_LANGUAGES = [
  { code: "en", name: "English" },
  { code: "fr", name: "French" },
  { code: "de", name: "German" },
  { code: "es", name: "Spanish" },
  { code: "pt", name: "Portuguese" },
  { code: "zh", name: "Chinese" },
  { code: "ja", name: "Japanese" },
  { code: "hi", name: "Hindi" },
  { code: "it", name: "Italian" },
  { code: "ko", name: "Korean" },
  { code: "nl", name: "Dutch" },
  { code: "pl", name: "Polish" },
  { code: "ru", name: "Russian" },
  { code: "sv", name: "Swedish" },
  { code: "tr", name: "Turkish" },
] as const;

interface VoiceFileUploadProps {
  onFileComplete: (file: File, customName?: string, language?: string) => void;
  isSubmitting?: boolean;
  /** Default name to show in the name field */
  defaultName?: string;
}

const MINIMUM_DURATION = 10; // 10 seconds minimum for Cartesia
const MAXIMUM_DURATION = 30; // 30 seconds maximum for optimal voice cloning
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_FORMATS = [".wav", ".mp3", ".m4a", ".flac"];

export function VoiceFileUpload({
  onFileComplete,
  isSubmitting = false,
  defaultName = "",
}: VoiceFileUploadProps) {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioDuration, setAudioDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [voiceName, setVoiceName] = useState(defaultName);
  const [language, setLanguage] = useState("en");

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    const fileExtension = file.name
      .toLowerCase()
      .slice(file.name.lastIndexOf("."));
    if (!ALLOWED_FORMATS.includes(fileExtension)) {
      toast.error("Invalid file format", {
        description: `Please upload a valid audio file: ${ALLOWED_FORMATS.join(", ")}`,
      });
      return;
    }

    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
      toast.error("File too large", {
        description: `Maximum file size is ${MAX_FILE_SIZE / (1024 * 1024)}MB`,
      });
      return;
    }

    // Validate audio duration using HTML5 Audio API
    const audioElement = new Audio();
    const objectUrl = URL.createObjectURL(file);

    audioElement.addEventListener("loadedmetadata", () => {
      const duration = Math.floor(audioElement.duration);
      URL.revokeObjectURL(objectUrl);

      if (duration < MINIMUM_DURATION) {
        toast.error("Audio too short", {
          description: `Audio must be at least ${MINIMUM_DURATION} seconds long. Your file is ${duration} seconds.`,
        });
        return;
      }

      if (duration > MAXIMUM_DURATION) {
        toast.error("Audio too long", {
          description: `Audio must be ${MAXIMUM_DURATION} seconds or less for optimal voice cloning. Your file is ${duration} seconds. Please trim your audio.`,
        });
        return;
      }

      // File is valid
      setUploadedFile(file);
      setAudioUrl(URL.createObjectURL(file));
      setAudioDuration(duration);

      toast.success("File uploaded", {
        description: `${file.name} (${duration} seconds)`,
      });
    });

    audioElement.addEventListener("error", () => {
      URL.revokeObjectURL(objectUrl);
      toast.error("Invalid audio file", {
        description: "Could not read audio file. Please try another file.",
      });
    });

    audioElement.src = objectUrl;
  };

  const handleFileUploadClick = () => {
    fileInputRef.current?.click();
  };

  const playAudio = () => {
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

  const deleteFile = () => {
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl);
    }

    stopPlayback();
    setUploadedFile(null);
    setAudioUrl(null);
    setAudioDuration(0);

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    toast.info("File deleted");
  };

  const handleSubmit = () => {
    if (!uploadedFile) {
      toast.error("No file uploaded", {
        description: "Please upload an audio file before submitting.",
      });
      return;
    }

    if (audioDuration < MINIMUM_DURATION) {
      toast.error("Audio too short", {
        description: `Audio must be at least ${MINIMUM_DURATION} seconds long.`,
      });
      return;
    }

    if (audioDuration > MAXIMUM_DURATION) {
      toast.error("Audio too long", {
        description: `Audio must be ${MAXIMUM_DURATION} seconds or less.`,
      });
      return;
    }

    // Pass the custom name if provided, otherwise undefined (use default)
    const customName = voiceName.trim() || undefined;
    onFileComplete(uploadedFile, customName, language);
  };

  const meetsMinimumDuration = audioDuration >= MINIMUM_DURATION;
  const meetsMaximumDuration = audioDuration <= MAXIMUM_DURATION;
  const meetsAllDurationRequirements =
    meetsMinimumDuration && meetsMaximumDuration;

  return (
    <div className="space-y-6">
      {/* Instructions */}
      <Alert>
        <FileAudio className="size-4" />
        <AlertDescription>
          Upload a pre-recorded audio file of your voice. Accepted formats:{" "}
          {ALLOWED_FORMATS.join(", ")}. Maximum size:{" "}
          {MAX_FILE_SIZE / (1024 * 1024)}MB. Duration: {MINIMUM_DURATION}-
          {MAXIMUM_DURATION} seconds.
        </AlertDescription>
      </Alert>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept={ALLOWED_FORMATS.join(",")}
        onChange={handleFileUpload}
        className="hidden"
      />

      {/* Upload Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Upload Audio File</CardTitle>
            {uploadedFile && (
              <Badge
                variant={meetsAllDurationRequirements ? "default" : "secondary"}
              >
                {formatTime(audioDuration)}{" "}
                {!meetsMinimumDuration && "(too short)"}
                {meetsMinimumDuration && !meetsMaximumDuration && "(too long)"}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Upload Area */}
          {!uploadedFile && (
            <div className="rounded-lg border-2 border-dashed border-muted-foreground/25 p-12 text-center">
              <FileAudio className="size-16 mx-auto mb-4 text-muted-foreground" />
              <p className="text-base font-medium text-foreground mb-2">
                Upload a pre-recorded audio file of your voice
              </p>
              <p className="text-sm text-muted-foreground mb-6">
                Supported formats: WAV, MP3, M4A, FLAC
                <br />
                Maximum size: 10MB | Duration: {MINIMUM_DURATION}-
                {MAXIMUM_DURATION} seconds
              </p>
              <Button
                size="lg"
                onClick={handleFileUploadClick}
                className="gap-2"
              >
                <Upload className="size-5" />
                Choose Audio File
              </Button>
            </div>
          )}

          {/* File Info */}
          {uploadedFile && (
            <div className="rounded-lg bg-muted p-4 sm:p-6">
              <div className="flex items-start gap-3 sm:gap-4 min-w-0">
                <div className="flex size-10 sm:size-12 items-center justify-center rounded-lg bg-primary/10 shrink-0">
                  <FileAudio className="size-5 sm:size-6 text-primary" />
                </div>
                <div className="flex-1 min-w-0 overflow-hidden">
                  <p className="font-medium text-foreground text-sm sm:text-base truncate max-w-full">
                    {uploadedFile.name}
                  </p>
                  <p className="text-xs sm:text-sm text-muted-foreground">
                    {(uploadedFile.size / (1024 * 1024)).toFixed(2)} MB •{" "}
                    {formatTime(audioDuration)}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Playback Controls */}
          {uploadedFile && (
            <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3">
              {!isPlaying ? (
                <Button
                  size="default"
                  variant="outline"
                  onClick={playAudio}
                  className="gap-1.5 sm:gap-2 text-sm"
                >
                  <Play className="size-4 sm:size-5" />
                  Play
                </Button>
              ) : (
                <Button
                  size="default"
                  variant="outline"
                  onClick={stopPlayback}
                  className="gap-1.5 sm:gap-2 text-sm"
                >
                  <Square className="size-4 sm:size-5" />
                  Stop
                </Button>
              )}
              <Button
                size="default"
                variant="outline"
                onClick={deleteFile}
                className="gap-1.5 sm:gap-2 text-sm"
              >
                <Trash2 className="size-4 sm:size-5" />
                Delete
              </Button>
              <Button
                size="default"
                onClick={handleFileUploadClick}
                className="gap-1.5 sm:gap-2 text-sm"
              >
                <Upload className="size-4 sm:size-5" />
                Upload New
              </Button>
            </div>
          )}

          {/* Status */}
          {uploadedFile && (
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
                  ? "File meets duration requirements"
                  : !meetsMinimumDuration
                    ? `Audio too short - need ${MINIMUM_DURATION - audioDuration}s more`
                    : `Audio too long - please trim to ${MAXIMUM_DURATION}s or less`}
              </span>
            </div>
          )}

          {/* Voice Settings - Name and Language */}
          {uploadedFile && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              {/* Voice Name Field */}
              <div className="space-y-2">
                <Label htmlFor="voice-name">Voice Name (Optional)</Label>
                <Input
                  id="voice-name"
                  value={voiceName}
                  onChange={(e) => setVoiceName(e.target.value)}
                  placeholder="Enter a custom name"
                />
                <p className="text-xs text-muted-foreground">
                  Give your voice clone a memorable name
                </p>
              </div>

              {/* Language Selection */}
              <div className="space-y-2">
                <Label htmlFor="voice-language">Voice Language</Label>
                <Select value={language} onValueChange={setLanguage}>
                  <SelectTrigger id="voice-language">
                    <SelectValue placeholder="Select language" />
                  </SelectTrigger>
                  <SelectContent>
                    {CARTESIA_LANGUAGES.map((lang) => (
                      <SelectItem key={lang.code} value={lang.code}>
                        {lang.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Language spoken in your recording
                </p>
              </div>
            </div>
          )}

          {/* Submit Button */}
          {uploadedFile && (
            <div className="pt-4 border-t">
              <Button
                onClick={handleSubmit}
                disabled={!meetsAllDurationRequirements || isSubmitting}
                className="w-full gap-2"
                size="lg"
              >
                <Upload className="size-4" />
                {isSubmitting ? "Submitting..." : "Submit Audio File"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
