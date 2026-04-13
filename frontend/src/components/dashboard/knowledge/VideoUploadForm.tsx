"use client";

import { useState, useRef } from "react";
import { Video, X, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useMediaUpload } from "@/lib/queries/knowledge";
import { useTierLimitCheck } from "@/lib/queries/tier";
import { cn } from "@/lib/utils";

interface VideoUploadFormProps {
  userId: string;
  onSuccess?: () => void;
}

const ACCEPTED_EXTENSIONS = [".mp4", ".mov", ".avi", ".mkv"];

export function VideoUploadForm({ userId, onSuccess }: VideoUploadFormProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { mutate: uploadMedia, isPending } = useMediaUpload();
  const {
    canUploadMultimedia,
    usage,
    hasReachedLimit,
    isLoading: isLoadingUsage,
  } = useTierLimitCheck();

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const isValidFileType = (file: File): boolean => {
    const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
    return ACCEPTED_EXTENSIONS.includes(extension);
  };

  const validateFile = (
    file: File,
  ): { valid: boolean; errorMessage?: string } => {
    // Check file type
    if (!isValidFileType(file)) {
      return {
        valid: false,
        errorMessage:
          "Invalid file type. Please upload MP4, MOV, AVI, or MKV files.",
      };
    }

    // Skip tier limit check if still loading - will be validated on submit
    if (isLoadingUsage) {
      return { valid: true };
    }

    // Check tier limits (note: duration will be checked on backend)
    const fileSizeMB = file.size / 1024 / 1024;
    const limitCheck = canUploadMultimedia(fileSizeMB);
    if (!limitCheck.allowed) {
      return {
        valid: false,
        errorMessage: limitCheck.reason,
      };
    }

    return { valid: true };
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    setError(null);

    const files = e.dataTransfer.files;
    if (files && files[0]) {
      const file = files[0];
      const validation = validateFile(file);
      if (!validation.valid) {
        setError(validation.errorMessage || "Invalid file");
        return;
      }
      setSelectedFile(file);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const files = e.target.files;
    if (files && files[0]) {
      const file = files[0];
      const validation = validateFile(file);
      if (!validation.valid) {
        setError(validation.errorMessage || "Invalid file");
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
        return;
      }
      setSelectedFile(file);
    }
  };

  const getFileTypeLabel = (fileName: string): string => {
    const extension = fileName.split(".").pop()?.toLowerCase();
    switch (extension) {
      case "mp4":
        return "MP4 Video";
      case "mov":
        return "MOV Video";
      case "avi":
        return "AVI Video";
      case "mkv":
        return "MKV Video";
      default:
        return "Video File";
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    // Validate tier limits before upload (in case it wasn't checked during file selection)
    const fileSizeMB = selectedFile.size / 1024 / 1024;
    const limitCheck = canUploadMultimedia(fileSizeMB);
    if (!limitCheck.allowed) {
      setError(limitCheck.reason || "Upload not allowed");
      return;
    }

    uploadMedia(
      { userId, file: selectedFile },
      {
        onSuccess: () => {
          setSelectedFile(null);
          setError(null);
          if (fileInputRef.current) {
            fileInputRef.current.value = "";
          }
          onSuccess?.();
        },
      },
    );
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Show limit reached warning
  const limitReached = hasReachedLimit("multimedia");
  const maxFileSize = usage?.multimedia.max_file_size_mb || 200;
  const maxFileSizeDisplay =
    maxFileSize === -1 ? "Unlimited" : `${maxFileSize}MB`;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {limitReached && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>
            Multimedia file limit reached ({usage?.multimedia.files.limit}{" "}
            files). Please upgrade your plan to upload more audio/video files.
          </AlertDescription>
        </Alert>
      )}

      {usage && usage.multimedia.files.percentage >= 80 && !limitReached && (
        <Alert>
          <AlertCircle className="size-4" />
          <AlertDescription>
            You&apos;ve used {usage.multimedia.files.percentage}% of your
            multimedia file limit ({usage.multimedia.files.used}/
            {usage.multimedia.files.limit} files). Consider upgrading your plan.
          </AlertDescription>
        </Alert>
      )}

      <div
        className={cn(
          "relative rounded-lg border-2 border-dashed p-8 text-center transition-colors cursor-pointer",
          dragActive
            ? "border-primary bg-muted"
            : "border-border hover:border-primary/50 hover:bg-muted/50",
          selectedFile && "border-solid border-primary bg-muted",
          error && "border-destructive",
        )}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !selectedFile && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".mp4,.mov,.avi,.mkv"
          onChange={handleFileChange}
          className="hidden"
        />

        {selectedFile ? (
          <div className="flex items-center gap-3">
            <Video className="size-8 text-muted-foreground" />
            <div className="flex-1 text-left">
              <p className="font-medium">{selectedFile.name}</p>
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>{getFileTypeLabel(selectedFile.name)}</span>
                <span>•</span>
                <span>{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</span>
              </div>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={(e) => {
                e.stopPropagation();
                handleRemoveFile();
              }}
              disabled={isPending}
            >
              <X className="size-4" />
            </Button>
          </div>
        ) : (
          <div className="space-y-2">
            <Video className="mx-auto size-10 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">
                Drop video file here or click to browse
              </p>
              <p className="text-xs text-muted-foreground">
                Supports MP4, MOV, AVI, MKV files • Max size:{" "}
                {maxFileSizeDisplay}
              </p>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="text-sm text-destructive text-center">{error}</div>
      )}

      <Button
        type="submit"
        disabled={!selectedFile || isPending || limitReached}
        className="w-full"
      >
        {isPending ? "Uploading..." : limitReached ? "Limit Reached" : "Upload"}
      </Button>
    </form>
  );
}
