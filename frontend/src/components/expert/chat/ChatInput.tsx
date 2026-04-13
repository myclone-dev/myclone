"use client";

import { useRef, KeyboardEvent, useEffect, useState, ChangeEvent } from "react";
import {
  Send,
  Paperclip,
  X,
  FileText,
  ImageIcon,
  Loader2,
  FileSpreadsheet,
  Presentation,
} from "lucide-react";
import {
  useAttachmentUpload,
  validateAttachmentFile,
  formatFileSize,
  getAttachmentCategory,
  notifyLiveKitDocumentUpload,
  type AttachmentUploadResponse,
} from "@/lib/queries/expert/chat";
import { toast } from "sonner";
import { trackFileUpload } from "@/lib/monitoring/sentry";
import type { Room } from "livekit-client";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
  isLoading?: boolean;
  placeholder?: string;
  // Props for attachment upload
  sessionToken?: string | null;
  widgetToken?: string;
  onAttachmentUploaded?: (attachment: AttachmentUploadResponse) => void;
  onAttachmentRemoved?: (attachmentId: string) => void;
  attachments?: AttachmentUploadResponse[]; // Current attachments from parent
  maxAttachments?: number;
  enableAttachments?: boolean; // Whether attachment upload is enabled (default: true)
  // LiveKit room for document upload notification
  room?: Room | null;
}

interface UploadingFile {
  id: string; // Temporary ID for tracking
  file: File;
  uploading: boolean;
  error?: string;
}

export function ChatInput({
  value,
  onChange,
  onSend,
  disabled = false,
  isLoading = false,
  placeholder = "Type your message...",
  sessionToken,
  widgetToken,
  onAttachmentUploaded,
  onAttachmentRemoved,
  attachments = [],
  maxAttachments = 5,
  enableAttachments = true,
  room,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadingFiles, setUploadingFiles] = useState<UploadingFile[]>([]);

  const attachmentUploadMutation = useAttachmentUpload();

  // Attachment upload is enabled by default
  const canUploadAttachments = enableAttachments;

  const hasAttachments = attachments.length > 0 || uploadingFiles.length > 0;
  const totalAttachments = attachments.length + uploadingFiles.length;
  const canAddMoreAttachments = totalAttachments < maxAttachments;

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      // Allow sending if there's text OR if there are attachments
      if ((value.trim() || hasAttachments) && !disabled && !isLoading) {
        onSend();
      }
    }
  };

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }
  }, [value]);

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    // Check max attachments limit
    const remainingSlots = maxAttachments - totalAttachments;
    if (files.length > remainingSlots) {
      toast.error(
        `Maximum ${maxAttachments} attachments allowed. You can add ${remainingSlots} more.`,
      );
      return;
    }

    if (!sessionToken) {
      toast.error("Session not initialized");
      return;
    }

    // Process each file
    for (const file of files) {
      // Validate file
      const validationError = validateAttachmentFile(file);
      if (validationError) {
        toast.error(validationError);
        continue;
      }

      // Create temporary ID for tracking
      const tempId = `temp_${Date.now()}_${Math.random().toString(36).substring(7)}`;

      // Add to uploading state
      setUploadingFiles((prev) => [
        ...prev,
        { id: tempId, file, uploading: true },
      ]);

      trackFileUpload("attachment", "started", {
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
      });

      try {
        const result = await attachmentUploadMutation.mutateAsync({
          sessionToken,
          file,
          widgetToken,
        });

        // Remove from uploading state
        setUploadingFiles((prev) => prev.filter((f) => f.id !== tempId));

        // Notify parent of successful upload
        onAttachmentUploaded?.(result);

        // Notify LiveKit agent about the document upload (if room is connected)
        if (room && result.s3_url) {
          try {
            await notifyLiveKitDocumentUpload(
              room,
              result.filename,
              result.s3_url,
              result.extracted_text, // Pass extracted text to avoid backend S3 re-fetch
            );
            if (process.env.NODE_ENV === "development") {
              console.log(
                "📤 [ChatInput] Notified LiveKit agent about document:",
                result.filename,
              );
            }
          } catch (liveKitError) {
            // Log but don't fail the upload - the document is still uploaded
            console.warn(
              "Failed to notify LiveKit agent about document upload:",
              liveKitError,
            );
          }
        }

        trackFileUpload("attachment", "success", {
          fileName: file.name,
          fileType: result.file_type,
          extractionStatus: result.extraction_status,
        });

        const fileTypeLabels: Record<string, string> = {
          pdf: "PDF",
          doc: "Word document",
          docx: "Word document",
          xls: "Excel spreadsheet",
          xlsx: "Excel spreadsheet",
          ppt: "PowerPoint",
          pptx: "PowerPoint",
          png: "Image",
          jpg: "Image",
          jpeg: "Image",
        };
        const fileTypeLabel = fileTypeLabels[result.file_type] || "File";
        const statusNote =
          result.extraction_status === "completed"
            ? " (text extracted)"
            : result.extraction_status === "failed"
              ? " (extraction failed)"
              : "";
        toast.success(`${fileTypeLabel} "${file.name}" uploaded${statusNote}`);
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : "Failed to upload file";

        trackFileUpload("attachment", "error", {
          fileName: file.name,
          fileSize: file.size,
          error: errorMessage,
        });

        // Mark as error in uploading state
        setUploadingFiles((prev) =>
          prev.map((f) =>
            f.id === tempId
              ? { ...f, uploading: false, error: errorMessage }
              : f,
          ),
        );

        toast.error(errorMessage);
      }
    }

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRemoveAttachment = (attachmentId: string) => {
    onAttachmentRemoved?.(attachmentId);
  };

  const handleRemoveUploadingFile = (tempId: string) => {
    setUploadingFiles((prev) => prev.filter((f) => f.id !== tempId));
  };

  const handleAttachClick = () => {
    if (!canAddMoreAttachments) {
      toast.error(`Maximum ${maxAttachments} attachments allowed`);
      return;
    }
    fileInputRef.current?.click();
  };

  const getFileIcon = (fileType: string) => {
    const category = getAttachmentCategory(fileType);
    switch (category) {
      case "pdf":
        return <FileText className="h-4 w-4 text-red-500" />;
      case "document":
        return <FileText className="h-4 w-4 text-blue-600" />;
      case "spreadsheet":
        return <FileSpreadsheet className="h-4 w-4 text-green-600" />;
      case "presentation":
        return <Presentation className="h-4 w-4 text-orange-500" />;
      case "image":
      default:
        return <ImageIcon className="h-4 w-4 text-blue-500" />;
    }
  };

  const getUploadingFileIcon = (mimeType: string) => {
    // Map MIME types to categories for uploading files
    if (mimeType === "application/pdf") {
      return <FileText className="h-4 w-4 text-red-500" />;
    }
    if (
      mimeType === "application/msword" ||
      mimeType ===
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ) {
      return <FileText className="h-4 w-4 text-blue-600" />;
    }
    if (
      mimeType === "application/vnd.ms-excel" ||
      mimeType ===
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    ) {
      return <FileSpreadsheet className="h-4 w-4 text-green-600" />;
    }
    if (
      mimeType === "application/vnd.ms-powerpoint" ||
      mimeType ===
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ) {
      return <Presentation className="h-4 w-4 text-orange-500" />;
    }
    if (mimeType.startsWith("image/")) {
      return <ImageIcon className="h-4 w-4 text-blue-500" />;
    }
    return <FileText className="h-4 w-4 text-gray-500" />;
  };

  return (
    <div className="border-t border-gray-200/50 bg-white/80 p-4 backdrop-blur-sm sm:p-6">
      {/* Attachments preview area */}
      {(attachments.length > 0 || uploadingFiles.length > 0) && (
        <div className="mb-3 flex flex-wrap gap-2">
          {/* Uploaded attachments */}
          {attachments.map((attachment) => (
            <div
              key={attachment.attachment_id}
              className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2"
            >
              {getFileIcon(attachment.file_type)}
              <span className="max-w-32 truncate text-sm text-gray-700">
                {attachment.filename}
              </span>
              <span className="text-xs text-gray-400">
                {formatFileSize(attachment.file_size)}
              </span>
              {attachment.extraction_status === "completed" && (
                <span className="text-xs text-green-600">✓</span>
              )}
              {attachment.extraction_status === "processing" && (
                <Loader2 className="h-3 w-3 animate-spin text-amber-500" />
              )}
              {attachment.extraction_status === "failed" && (
                <span className="text-xs text-red-500">!</span>
              )}
              <button
                onClick={() => handleRemoveAttachment(attachment.attachment_id)}
                className="rounded p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-600"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}

          {/* Currently uploading files */}
          {uploadingFiles.map((uploadingFile) => (
            <div
              key={uploadingFile.id}
              className="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2"
            >
              {getUploadingFileIcon(uploadingFile.file.type)}
              <span className="max-w-32 truncate text-sm text-gray-700">
                {uploadingFile.file.name}
              </span>
              {uploadingFile.uploading ? (
                <Loader2 className="h-3 w-3 animate-spin text-gray-400" />
              ) : uploadingFile.error ? (
                <span className="text-xs text-red-500">Failed</span>
              ) : null}
              <button
                onClick={() => handleRemoveUploadingFile(uploadingFile.id)}
                className="rounded p-1 text-gray-400 hover:bg-gray-200 hover:text-gray-600"
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="flex max-w-full items-end gap-3">
        {/* Attachment upload button - only visible for allowed personas */}
        {canUploadAttachments && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.png,.jpg,.jpeg,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation,image/png,image/jpeg"
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />
            <button
              onClick={handleAttachClick}
              disabled={
                disabled ||
                isLoading ||
                !canAddMoreAttachments ||
                uploadingFiles.some((f) => f.uploading)
              }
              className="shrink-0 rounded-full border border-gray-300 bg-white p-3 text-gray-500 transition-all duration-200 hover:border-amber-400 hover:bg-amber-50 hover:text-amber-600 disabled:cursor-not-allowed disabled:opacity-50"
              title={
                uploadingFiles.some((f) => f.uploading)
                  ? "Please wait for current uploads to complete..."
                  : canAddMoreAttachments
                    ? "Attach file (PDF, Word, Excel, PowerPoint, Images)"
                    : `Maximum ${maxAttachments} attachments`
              }
            >
              <Paperclip className="h-5 w-5" />
            </button>
          </>
        )}

        <textarea
          ref={textareaRef}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled || isLoading}
          rows={1}
          className="max-h-32 min-h-11 flex-1 resize-none overflow-hidden rounded-[52px] border border-gray-300/50 bg-gray-50/80 px-5 py-3 text-base leading-normal text-gray-900 placeholder:text-gray-500 transition-all duration-200 focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-400/50 disabled:cursor-not-allowed disabled:opacity-50"
        />
        <button
          onClick={onSend}
          disabled={
            (!value.trim() && !hasAttachments) ||
            disabled ||
            isLoading ||
            uploadingFiles.some((f) => f.uploading)
          }
          className="shrink-0 rounded-full bg-linear-to-r from-amber-400 to-orange-500 p-4 text-white transition-all duration-200 hover:scale-105 hover:from-amber-500 hover:to-orange-600 hover:shadow-lg active:scale-95 disabled:cursor-not-allowed disabled:opacity-50"
          title={
            uploadingFiles.some((f) => f.uploading)
              ? "Please wait for files to finish uploading..."
              : "Send message"
          }
        >
          <Send className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
