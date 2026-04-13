"use client";

import { useRef, useState } from "react";
import { Upload, Trash2, ImagePlus, X, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { trackFileUpload } from "@/lib/monitoring/sentry";
import { parseApiError } from "@/lib/utils/apiError";
import {
  useUploadAvatar,
  useDeleteAvatar,
} from "@/lib/queries/users/useAvatarMutations";

interface AvatarUploadButtonProps {
  currentAvatar: string | null | undefined;
  onUploadSuccess?: (avatarUrl: string) => void;
  onDeleteSuccess?: () => void;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_IMAGE_DIMENSION = 4096; // 4096x4096 max (must match backend)
const ACCEPTED_IMAGE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/gif",
];

export function AvatarUploadButton({
  currentAvatar,
  onUploadSuccess,
  onDeleteSuccess,
}: AvatarUploadButtonProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const uploadMutation = useUploadAvatar();
  const deleteMutation = useDeleteAvatar();

  const isUploading = uploadMutation.isPending;
  const isDeleting = deleteMutation.isPending;

  /**
   * Validate file before upload (type and size only)
   */
  const validateFile = (file: File): string | null => {
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      return "Invalid file type. Please upload JPEG, PNG, WebP, or GIF images.";
    }

    if (file.size > MAX_FILE_SIZE) {
      return "File too large. Maximum size is 10MB.";
    }

    return null;
  };

  /**
   * Validate image dimensions (async - requires loading the image)
   */
  const validateImageDimensions = (
    file: File,
  ): Promise<{
    valid: boolean;
    error?: string;
    width?: number;
    height?: number;
  }> => {
    return new Promise((resolve) => {
      const img = new window.Image();
      const url = URL.createObjectURL(file);

      img.onload = () => {
        URL.revokeObjectURL(url);
        const { width, height } = img;

        if (width > MAX_IMAGE_DIMENSION || height > MAX_IMAGE_DIMENSION) {
          resolve({
            valid: false,
            error: `Image dimensions too large. Maximum: ${MAX_IMAGE_DIMENSION}x${MAX_IMAGE_DIMENSION}. Your image: ${width}x${height}.`,
            width,
            height,
          });
        } else {
          resolve({ valid: true, width, height });
        }
      };

      img.onerror = () => {
        URL.revokeObjectURL(url);
        resolve({
          valid: false,
          error: "Failed to load image. The file may be corrupted.",
        });
      };

      img.src = url;
    });
  };

  /**
   * Handle file selection
   */
  const handleFileSelect = async (file: File) => {
    // Validate type and size first (sync)
    const error = validateFile(file);
    if (error) {
      toast.error(error);
      return;
    }

    // Validate image dimensions (async)
    const dimensionResult = await validateImageDimensions(file);
    if (!dimensionResult.valid) {
      toast.error(dimensionResult.error || "Invalid image dimensions");
      return;
    }

    setSelectedFile(file);

    // Create preview
    const reader = new FileReader();
    reader.onloadend = () => {
      setPreview(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  /**
   * Handle file input change
   */
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  /**
   * Handle drag and drop
   */
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  /**
   * Upload the selected file
   */
  const handleUpload = async () => {
    if (!selectedFile) return;

    trackFileUpload("avatar", "started", {
      fileName: selectedFile.name,
      fileSize: selectedFile.size,
      fileType: selectedFile.type,
    });

    try {
      const response = await uploadMutation.mutateAsync(selectedFile);

      trackFileUpload("avatar", "success", {
        fileName: selectedFile.name,
      });

      toast.success("Avatar uploaded successfully!");

      // Reset state
      setSelectedFile(null);
      setPreview(null);

      // Clear file input
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      if (response.avatar_url && onUploadSuccess) {
        onUploadSuccess(response.avatar_url);
      }
    } catch (error) {
      // Use parseApiError to extract the backend's detailed error message
      const errorMessage = parseApiError(error, "Failed to upload avatar");

      trackFileUpload("avatar", "error", {
        fileName: selectedFile.name,
        error: errorMessage,
      });

      toast.error(errorMessage);
    }
  };

  /**
   * Delete current avatar
   */
  const handleDelete = async () => {
    trackFileUpload("avatar", "started", { action: "delete" });

    try {
      await deleteMutation.mutateAsync();

      trackFileUpload("avatar", "success", { action: "delete" });

      toast.success("Avatar deleted successfully!");
      setShowDeleteDialog(false);

      if (onDeleteSuccess) {
        onDeleteSuccess();
      }
    } catch (error) {
      // Use parseApiError to extract the backend's detailed error message
      const errorMessage = parseApiError(error, "Failed to delete avatar");

      trackFileUpload("avatar", "error", {
        action: "delete",
        error: errorMessage,
      });

      toast.error(errorMessage);
    }
  };

  /**
   * Cancel upload and reset state
   */
  const handleCancel = () => {
    setSelectedFile(null);
    setPreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  /**
   * Trigger file input click
   */
  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="w-full">
      {/* File Input (Hidden) */}
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_IMAGE_TYPES.join(",")}
        onChange={handleInputChange}
        className="hidden"
        disabled={isUploading || isDeleting}
      />

      {/* Preview or Upload Area */}
      {preview ? (
        <div className="space-y-6">
          {/* Preview Image with Close Button */}
          <div className="relative mx-auto w-full max-w-sm">
            <div className="relative aspect-square w-full overflow-hidden rounded-2xl border-2 border-yellow-bright bg-slate-50 shadow-lg">
              <img
                src={preview}
                alt="Avatar preview"
                className="size-full object-cover"
              />
              {/* Close Preview Button */}
              <Button
                size="icon"
                variant="secondary"
                className="absolute right-2 top-2 size-8 rounded-full shadow-md"
                onClick={handleCancel}
                disabled={isUploading}
              >
                <X className="size-4" />
              </Button>
            </div>
          </div>

          {/* Upload Info */}
          <div className="rounded-lg bg-yellow-light p-4 text-center">
            <p className="text-sm font-medium text-gray-900">Ready to upload</p>
            <p className="mt-1 text-xs text-gray-700">
              {selectedFile?.name} (
              {((selectedFile?.size ?? 0) / 1024 / 1024).toFixed(2)} MB)
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button
              onClick={handleUpload}
              disabled={isUploading}
              className="flex-1 gap-2 shadow-sm"
              size="lg"
            >
              {isUploading ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="size-4" />
                  Upload Photo
                </>
              )}
            </Button>
            <Button
              onClick={handleCancel}
              variant="outline"
              disabled={isUploading}
              size="lg"
              className="flex-1"
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Drag & Drop Area */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`group relative mx-auto w-full cursor-pointer overflow-hidden rounded-2xl border-2 transition-all duration-300 ${
              dragActive
                ? "border-solid border-yellow-bright bg-yellow-light shadow-lg"
                : "border-dashed border-slate-300 bg-slate-50/50 hover:border-solid hover:border-yellow-bright hover:bg-yellow-light/30 hover:shadow-md"
            }`}
            onClick={handleButtonClick}
          >
            <div className="flex flex-col items-center justify-center px-6 py-12 sm:py-16">
              {/* Icon */}
              <div
                className={`mb-4 rounded-full p-4 transition-all duration-300 ${
                  dragActive
                    ? "bg-yellow-bright text-gray-700"
                    : "bg-slate-200 text-slate-400 group-hover:bg-yellow-light group-hover:text-gray-700"
                }`}
              >
                <ImagePlus className="size-8 sm:size-10" />
              </div>

              {/* Text */}
              <h3 className="mb-2 text-base font-semibold text-slate-700 sm:text-lg">
                {dragActive ? "Drop your photo here" : "Upload a profile photo"}
              </h3>
              <p className="mb-1 text-center text-sm text-slate-600">
                Drag and drop or click to browse
              </p>
              <p className="text-xs text-slate-500">
                Supports: JPEG, PNG, WebP, GIF
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Max size: 10MB, Max dimensions: 4096x4096
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button
              onClick={handleButtonClick}
              disabled={isUploading || isDeleting}
              className="flex-1 gap-2 shadow-sm"
              size="lg"
              variant="default"
            >
              <ImagePlus className="size-4" />
              Choose Photo
            </Button>

            {currentAvatar && (
              <Button
                onClick={() => setShowDeleteDialog(true)}
                variant="outline"
                disabled={isUploading || isDeleting}
                size="lg"
                className="flex-1 gap-2 border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="size-4" />
                    Remove Photo
                  </>
                )}
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent className="sm:max-w-md">
          <AlertDialogHeader>
            <AlertDialogTitle>Remove Profile Photo?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete your profile picture. You can always
              upload a new one later.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-red-600 hover:bg-red-700"
            >
              Remove Photo
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
