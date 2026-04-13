"use client";

import { useState, useRef } from "react";
import { motion } from "motion/react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  Camera,
  Upload,
  Trash2,
  Loader2,
  User,
  AlertCircle,
} from "lucide-react";
import { cn, getInitials } from "@/lib/utils";
import { toast } from "sonner";
import {
  useUploadPersonaAvatar,
  useDeletePersonaAvatar,
} from "@/lib/queries/persona";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import {
  trackUserAction,
  trackDashboardOperation,
} from "@/lib/monitoring/sentry";

interface AvatarTabProps {
  personaId: string;
  personaName: string;
  currentAvatarUrl?: string;
  userAvatarUrl?: string;
  onAvatarChange?: (newAvatarUrl: string | null) => void;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_INPUT_DIMENSION = 8000; // Reject images larger than this (prevents memory issues)
const TARGET_DIMENSION = 4096; // Resize images to this max dimension (matches backend limit)
const IMAGE_QUALITY = 0.92; // High quality for JPEG/WebP (visually lossless)
const ALLOWED_TYPES: readonly string[] = [
  "image/jpeg",
  "image/png",
  "image/webp",
];

interface ImageProcessResult {
  file: File;
  width: number;
  height: number;
  wasResized: boolean;
  originalWidth?: number;
  originalHeight?: number;
}

/**
 * Load an image from a file and return the HTMLImageElement
 */
const loadImage = (file: File): Promise<HTMLImageElement> => {
  return new Promise((resolve, reject) => {
    const img = new window.Image();
    const url = URL.createObjectURL(file);

    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(
        new Error(
          "Failed to load image. The file may be corrupted or in an unsupported format.",
        ),
      );
    };

    img.src = url;
  });
};

interface ResizeResult {
  blob: Blob;
  width: number;
  height: number;
}

/**
 * Resize an image using Canvas API while maintaining aspect ratio
 * Returns both the blob and dimensions to avoid reloading the image
 */
const resizeImage = (
  img: HTMLImageElement,
  maxDimension: number,
  mimeType: string,
): Promise<ResizeResult> => {
  return new Promise((resolve, reject) => {
    const { width, height } = img;

    // Calculate new dimensions maintaining aspect ratio
    let newWidth = width;
    let newHeight = height;

    if (width > maxDimension || height > maxDimension) {
      if (width > height) {
        newWidth = maxDimension;
        newHeight = Math.round((height / width) * maxDimension);
      } else {
        newHeight = maxDimension;
        newWidth = Math.round((width / height) * maxDimension);
      }
    }

    // Create canvas and draw resized image
    const canvas = document.createElement("canvas");
    canvas.width = newWidth;
    canvas.height = newHeight;

    // Verify canvas was created properly (some browsers have size limits)
    if (canvas.width === 0 || canvas.height === 0) {
      reject(
        new Error(
          "Canvas dimensions are invalid. Your browser may not support this image size.",
        ),
      );
      return;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      reject(new Error("Failed to get canvas context"));
      return;
    }

    // Use high-quality image smoothing (with fallback for older browsers)
    ctx.imageSmoothingEnabled = true;
    if ("imageSmoothingQuality" in ctx) {
      ctx.imageSmoothingQuality = "high";
    }
    ctx.drawImage(img, 0, 0, newWidth, newHeight);

    // Convert to blob (PNG is lossless, JPEG/WebP use quality setting)
    const quality = mimeType === "image/png" ? undefined : IMAGE_QUALITY;
    canvas.toBlob(
      (blob) => {
        // Clean up canvas bitmap memory (canvas is not in DOM, this releases the buffer)
        canvas.width = 0;
        canvas.height = 0;

        if (blob) {
          resolve({ blob, width: newWidth, height: newHeight });
        } else {
          reject(new Error("Failed to create image blob"));
        }
      },
      mimeType,
      quality,
    );
  });
};

/**
 * Process an image file - validate and resize if needed
 */
const processImage = async (file: File): Promise<ImageProcessResult> => {
  const img = await loadImage(file);
  const { width, height } = img;

  // Reject extremely large images (memory safety)
  if (width > MAX_INPUT_DIMENSION || height > MAX_INPUT_DIMENSION) {
    throw new Error(
      `Image too large. Maximum input size: ${MAX_INPUT_DIMENSION}x${MAX_INPUT_DIMENSION}. Your image: ${width}x${height}.`,
    );
  }

  // If image is within target, return as-is
  if (width <= TARGET_DIMENSION && height <= TARGET_DIMENSION) {
    return {
      file,
      width,
      height,
      wasResized: false,
    };
  }

  // Resize the image - returns blob and dimensions together (avoids reloading image)
  const resizeResult = await resizeImage(img, TARGET_DIMENSION, file.type);

  // Create a new File from the blob
  const resizedFile = new File([resizeResult.blob], file.name, {
    type: file.type,
    lastModified: Date.now(),
  });

  return {
    file: resizedFile,
    width: resizeResult.width,
    height: resizeResult.height,
    wasResized: true,
    originalWidth: width,
    originalHeight: height,
  };
};

/**
 * Avatar Tab
 * Allows upload/management of persona-specific avatar
 */
export function AvatarTab({
  personaId,
  personaName,
  currentAvatarUrl,
  userAvatarUrl,
  onAvatarChange,
}: AvatarTabProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploadedAvatarUrl, setUploadedAvatarUrl] = useState<string | null>(
    null,
  );
  const [isDragging, setIsDragging] = useState(false);

  const { data: user } = useUserMe();
  const uploadMutation = useUploadPersonaAvatar();
  const deleteMutation = useDeletePersonaAvatar();

  const isUploading = uploadMutation.isPending;
  const isDeleting = deleteMutation.isPending;
  const isLoading = isUploading || isDeleting;

  // Display priority: preview > uploaded URL > persona avatar from prop > user avatar
  // uploadedAvatarUrl ensures we show the new avatar immediately after upload
  // before the query refetch updates the persona prop
  const displayAvatarUrl =
    previewUrl || uploadedAvatarUrl || currentAvatarUrl || userAvatarUrl;
  const hasPersonaAvatar = !!(uploadedAvatarUrl || currentAvatarUrl);
  const fallbackAvatar = user?.avatar || userAvatarUrl;

  const handleFileSelect = async (file: File) => {
    // Validate file type (client-side only - backend validates actual file content)
    if (!ALLOWED_TYPES.includes(file.type)) {
      toast.error("Invalid file type. Please upload JPEG, PNG, or WebP.");
      trackUserAction("persona_avatar_validation_error", {
        personaId,
        error: "invalid_file_type",
        fileType: file.type,
        fileName: file.name,
      });
      return;
    }

    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
      toast.error("File too large. Maximum size is 10MB.");
      trackUserAction("persona_avatar_validation_error", {
        personaId,
        error: "file_too_large",
        fileSize: file.size,
        fileName: file.name,
      });
      return;
    }

    // Process and resize image if needed
    let processedFile: File;
    try {
      const result = await processImage(file);
      processedFile = result.file;

      // Notify user if image was resized
      if (result.wasResized) {
        toast.info(
          `Image resized from ${result.originalWidth}x${result.originalHeight} to ${result.width}x${result.height}`,
        );
        trackDashboardOperation("persona_avatar_resize", "success", {
          personaId,
          originalWidth: result.originalWidth,
          originalHeight: result.originalHeight,
          newWidth: result.width,
          newHeight: result.height,
          fileName: file.name,
        });
      }

      // Validate resized file size (PNG can still be large after resize)
      if (processedFile.size > MAX_FILE_SIZE) {
        toast.error(
          "Image is too large even after resizing. Try a lower resolution image or convert to JPEG.",
        );
        trackUserAction("persona_avatar_validation_error", {
          personaId,
          error: "resized_file_too_large",
          originalSize: file.size,
          resizedSize: processedFile.size,
          fileName: file.name,
        });
        return;
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Failed to process image";
      toast.error(errorMessage);
      trackUserAction("persona_avatar_validation_error", {
        personaId,
        error: "processing_failed",
        errorMessage,
        errorStack: error instanceof Error ? error.stack : undefined,
        fileName: file.name,
      });
      return;
    }

    // Track upload initiated
    trackUserAction("persona_avatar_upload_initiated", {
      personaId,
      fileName: processedFile.name,
      fileSize: processedFile.size,
      fileType: processedFile.type,
    });

    // Show preview before upload (await with timeout to prevent hanging)
    const reader = new FileReader();
    const PREVIEW_TIMEOUT_MS = 5000;

    const previewPromise = Promise.race([
      new Promise<void>((resolve, reject) => {
        reader.onload = (e) => {
          setPreviewUrl(e.target?.result as string);
          resolve();
        };
        reader.onerror = () => {
          reject(new Error("preview_failed"));
        };
      }),
      new Promise<void>((_, reject) =>
        setTimeout(
          () => reject(new Error("preview_timeout")),
          PREVIEW_TIMEOUT_MS,
        ),
      ),
    ]);
    reader.readAsDataURL(processedFile);

    try {
      await previewPromise;
    } catch (error) {
      const errorType =
        error instanceof Error && error.message === "preview_timeout"
          ? "preview_timeout"
          : "preview_failed";
      toast.error(
        errorType === "preview_timeout"
          ? "Preview took too long. Uploading anyway..."
          : "Failed to preview image",
      );
      trackDashboardOperation("persona_avatar_upload", "error", {
        personaId,
        error: errorType,
        fileName: processedFile.name,
      });
      // For timeout, continue with upload; for other errors, abort
      if (errorType !== "preview_timeout") {
        return;
      }
    }

    // Upload
    try {
      const result = await uploadMutation.mutateAsync({
        personaId,
        file: processedFile,
      });
      if (result.success && result.persona_avatar_url) {
        toast.success("Avatar uploaded successfully");
        // Store the new URL locally to display immediately
        // This ensures the new avatar shows before the query refetch updates the prop
        setUploadedAvatarUrl(result.persona_avatar_url);
        onAvatarChange?.(result.persona_avatar_url);
        setPreviewUrl(null); // Clear preview, use uploaded URL
      }
    } catch {
      toast.error("Failed to upload avatar. Please try again.");
      setPreviewUrl(null);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
    // Reset input so same file can be selected again
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDelete = async () => {
    if (!hasPersonaAvatar) return;

    // Track delete initiated
    trackUserAction("persona_avatar_delete_initiated", {
      personaId,
    });

    try {
      await deleteMutation.mutateAsync(personaId);
      toast.success("Avatar removed. Using profile avatar instead.");
      // Clear local uploaded URL state
      setUploadedAvatarUrl(null);
      onAvatarChange?.(null);
    } catch {
      toast.error("Failed to remove avatar. Please try again.");
    }
  };

  const initials = personaName ? getInitials(personaName) : "P";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Camera className="size-4" />
            Persona Avatar
          </CardTitle>
          <CardDescription>
            Upload a custom avatar for this persona. This will override your
            profile avatar when visitors chat with this persona.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Current Avatar Preview */}
          <div className="flex flex-col items-center gap-4">
            <div className="relative">
              <Avatar className="size-32 border-4 border-background shadow-lg">
                <AvatarImage
                  src={displayAvatarUrl}
                  alt={personaName}
                  className="object-cover"
                />
                <AvatarFallback className="text-2xl bg-muted">
                  {initials}
                </AvatarFallback>
              </Avatar>

              {isLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-full">
                  <Loader2 className="size-8 text-white animate-spin" />
                </div>
              )}
            </div>

            {/* Avatar type indicator */}
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              {hasPersonaAvatar ? (
                <>
                  <Camera className="size-4" />
                  <span>Custom persona avatar</span>
                </>
              ) : fallbackAvatar ? (
                <>
                  <User className="size-4" />
                  <span>Using profile avatar</span>
                </>
              ) : (
                <>
                  <AlertCircle className="size-4" />
                  <span>No avatar set</span>
                </>
              )}
            </div>
          </div>

          {/* Upload Area */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={cn(
              "border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer",
              isDragging
                ? "border-primary bg-primary/5"
                : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50",
              isLoading && "pointer-events-none opacity-50",
            )}
            onClick={() => !isLoading && fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={ALLOWED_TYPES.join(",")}
              onChange={handleFileInputChange}
              className="hidden"
              disabled={isLoading}
            />

            <Upload className="size-8 mx-auto mb-3 text-muted-foreground" />
            <p className="text-sm font-medium">
              {isDragging
                ? "Drop image here"
                : "Click to upload or drag and drop"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              JPEG, PNG, or WebP (max 10MB, auto-resized if needed)
            </p>
          </div>

          {/* Remove Button - Only show when persona has custom avatar */}
          {hasPersonaAvatar && (
            <div className="flex justify-center">
              <Button
                variant="outline"
                size="sm"
                onClick={handleDelete}
                disabled={isLoading}
                className="text-destructive hover:text-destructive hover:bg-destructive/10"
              >
                {isDeleting ? (
                  <Loader2 className="size-4 mr-2 animate-spin" />
                ) : (
                  <Trash2 className="size-4 mr-2" />
                )}
                Remove Avatar
              </Button>
            </div>
          )}

          {/* Info note */}
          <p className="text-xs text-muted-foreground text-center">
            The persona avatar will be shown in the chat widget header and
            bubble button when visitors interact with this persona.
          </p>
        </CardContent>
      </Card>
    </motion.div>
  );
}
