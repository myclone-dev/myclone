"use client";

import { useState, useRef, useCallback } from "react";
import {
  FileText,
  Upload,
  X,
  File,
  AlertCircle,
  CheckCircle2,
  Loader2,
  AlertTriangle,
  Copy,
  Trash2,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import { useBatchUpload, type BatchFileItem } from "@/lib/queries/knowledge";
import { useTierLimitCheck } from "@/lib/queries/tier";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface DocumentUploadFormProps {
  userId: string;
  onSuccess?: () => void;
}

const ACCEPTED_EXTENSIONS = [".pdf", ".txt", ".md", ".docx", ".pptx", ".xlsx"];
const MAX_FILES_PER_BATCH = 10;

export function DocumentUploadForm({
  userId,
  onSuccess,
}: DocumentUploadFormProps) {
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { canUploadDocument, usage, hasReachedLimit } = useTierLimitCheck();

  const {
    files,
    isUploading,
    uploadProgress,
    statusCounts,
    addFiles,
    removeFile,
    clearFiles,
    uploadAll,
    retryFailed,
  } = useBatchUpload({
    userId,
    onComplete: (result) => {
      if (result.successCount > 0) {
        onSuccess?.();
      }
    },
  });

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const isValidFileType = useCallback((file: File): boolean => {
    const extension = `.${file.name.split(".").pop()?.toLowerCase()}`;
    return ACCEPTED_EXTENSIONS.includes(extension);
  }, []);

  const validateFile = useCallback(
    (file: File): { valid: boolean; errorMessage?: string } => {
      // Check file type
      if (!isValidFileType(file)) {
        return {
          valid: false,
          errorMessage: `"${file.name}" - Invalid file type. Please upload PDF, DOCX, PPTX, XLSX, TXT, or MD files.`,
        };
      }

      // Check tier limits
      const fileSizeMB = file.size / 1024 / 1024;
      const limitCheck = canUploadDocument(fileSizeMB);
      if (!limitCheck.allowed) {
        return {
          valid: false,
          errorMessage: `"${file.name}" - ${limitCheck.reason}`,
        };
      }

      return { valid: true };
    },
    [isValidFileType, canUploadDocument],
  );

  const handleFilesSelected = useCallback(
    (selectedFiles: FileList | File[] | null) => {
      if (!selectedFiles || selectedFiles.length === 0) return;

      const fileArray = Array.isArray(selectedFiles)
        ? selectedFiles
        : Array.from(selectedFiles);

      // Check batch limit
      const currentPendingCount = files.filter(
        (f) => f.status === "pending",
      ).length;
      if (currentPendingCount + fileArray.length > MAX_FILES_PER_BATCH) {
        toast.error(
          `You can upload up to ${MAX_FILES_PER_BATCH} files at once. Current queue: ${currentPendingCount}`,
        );
        return;
      }

      const validFiles: File[] = [];
      const errors: string[] = [];

      fileArray.forEach((file) => {
        const validation = validateFile(file);
        if (validation.valid) {
          validFiles.push(file);
        } else if (validation.errorMessage) {
          errors.push(validation.errorMessage);
        }
      });

      if (errors.length > 0) {
        errors.forEach((error) => toast.error(error));
      }

      if (validFiles.length > 0) {
        addFiles(validFiles);
        toast.success(`Added ${validFiles.length} file(s) to upload queue`);
      }
    },
    [files, validateFile, addFiles],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      handleFilesSelected(e.dataTransfer.files);
    },
    [handleFilesSelected],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      // Convert FileList to array BEFORE resetting input
      // FileList is a live reference that becomes empty when input is cleared
      const fileArray = e.target.files ? Array.from(e.target.files) : [];
      // Reset the input immediately so the same file can be selected again
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      // Now process the captured files (converted to array)
      if (fileArray.length > 0) {
        handleFilesSelected(fileArray);
      }
    },
    [handleFilesSelected],
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      await uploadAll();
    },
    [uploadAll],
  );

  const getFileIcon = useCallback((fileName: string) => {
    const extension = fileName.split(".").pop()?.toLowerCase();
    const documentExtensions = ["pdf", "docx", "pptx", "xlsx", "txt", "md"];
    return documentExtensions.includes(extension || "") ? FileText : File;
  }, []);

  const getFileTypeLabel = useCallback((fileName: string): string => {
    const extension = fileName.split(".").pop()?.toLowerCase();
    switch (extension) {
      case "pdf":
        return "PDF";
      case "txt":
        return "TXT";
      case "md":
        return "MD";
      case "docx":
        return "DOCX";
      case "pptx":
        return "PPTX";
      case "xlsx":
        return "XLSX";
      default:
        return "DOC";
    }
  }, []);

  const getStatusIcon = useCallback((status: BatchFileItem["status"]) => {
    switch (status) {
      case "pending":
        return <File className="size-4 text-muted-foreground" />;
      case "uploading":
        return <Loader2 className="size-4 animate-spin text-primary" />;
      case "success":
        return <CheckCircle2 className="size-4 text-green-500" />;
      case "error":
        return <AlertCircle className="size-4 text-destructive" />;
      case "duplicate":
        return <Copy className="size-4 text-yellow-500" />;
      default:
        return <File className="size-4 text-muted-foreground" />;
    }
  }, []);

  const getStatusText = useCallback((item: BatchFileItem): string => {
    switch (item.status) {
      case "pending":
        return "Ready to upload";
      case "uploading":
        return "Uploading...";
      case "success":
        return "Uploaded successfully";
      case "error":
        return item.errorMessage || "Upload failed";
      case "duplicate":
        return "Duplicate file";
      default:
        return "";
    }
  }, []);

  // Show limit reached warning
  const limitReached = hasReachedLimit("documents");
  const maxFileSize = usage?.documents.max_file_size_mb || 50;
  const maxFileSizeDisplay =
    maxFileSize === -1 ? "Unlimited" : `${maxFileSize}MB`;

  const pendingCount = statusCounts.pending;
  const hasFiles = files.length > 0;
  const hasFailedFiles = statusCounts.error > 0;
  const allCompleted =
    files.length > 0 &&
    statusCounts.pending === 0 &&
    statusCounts.uploading === 0;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {limitReached && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertDescription>
            Document file limit reached ({usage?.documents.files.limit} files).
            Please upgrade your plan to upload more documents.
          </AlertDescription>
        </Alert>
      )}

      {usage && usage.documents.files.percentage >= 80 && !limitReached && (
        <Alert>
          <AlertCircle className="size-4" />
          <AlertDescription>
            You&apos;ve used {usage.documents.files.percentage}% of your
            document file limit ({usage.documents.files.used}/
            {usage.documents.files.limit} files). Consider upgrading your plan.
          </AlertDescription>
        </Alert>
      )}

      {/* Drop Zone */}
      <div
        className={cn(
          "relative rounded-lg border-2 border-dashed p-8 text-center transition-colors cursor-pointer",
          dragActive
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-muted/50",
          isUploading && "pointer-events-none opacity-50",
        )}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md,.docx,.pptx,.xlsx"
          onChange={handleFileChange}
          className="hidden"
          multiple
        />

        <div className="space-y-2">
          <Upload
            className={cn(
              "mx-auto size-10 text-muted-foreground",
              dragActive && "text-primary",
            )}
          />
          <div>
            <p className="text-sm font-medium">
              {dragActive
                ? "Drop files here"
                : "Drop documents here or click to browse"}
            </p>
            <p className="text-xs text-muted-foreground">
              Supports PDF, DOCX, PPTX, XLSX, TXT, MD • Max {maxFileSizeDisplay}{" "}
              per file • Up to {MAX_FILES_PER_BATCH} files at once
            </p>
          </div>
        </div>
      </div>

      {/* File Queue */}
      {hasFiles && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium">
              Upload Queue ({files.length} file{files.length !== 1 ? "s" : ""})
            </h4>
            {!isUploading && (
              <div className="flex items-center gap-2">
                {hasFailedFiles && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={retryFailed}
                    className="h-7 text-xs"
                  >
                    <RotateCcw className="mr-1 size-3" />
                    Retry Failed
                  </Button>
                )}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={clearFiles}
                  className="h-7 text-xs text-muted-foreground hover:text-destructive"
                >
                  <Trash2 className="mr-1 size-3" />
                  Clear All
                </Button>
              </div>
            )}
          </div>

          {/* Upload Progress */}
          {isUploading && (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>
                  Uploading {uploadProgress.completed + 1} of{" "}
                  {uploadProgress.total}
                </span>
                <span>
                  {Math.round(
                    (uploadProgress.completed / uploadProgress.total) * 100,
                  )}
                  %
                </span>
              </div>
              <Progress
                value={(uploadProgress.completed / uploadProgress.total) * 100}
                className="h-1.5"
              />
            </div>
          )}

          {/* File List */}
          <div className="max-h-64 space-y-2 overflow-hidden overflow-y-auto rounded-md border p-2">
            {files.map((item) => {
              const FileIcon = getFileIcon(item.file.name);
              return (
                <div
                  key={item.id}
                  className={cn(
                    "flex w-full items-center gap-3 overflow-hidden rounded-md p-2 transition-colors",
                    item.status === "success" &&
                      "bg-green-50 dark:bg-green-950/20",
                    item.status === "error" && "bg-destructive/10",
                    item.status === "duplicate" &&
                      "bg-yellow-50 dark:bg-yellow-950/20",
                    item.status === "uploading" && "bg-primary/5",
                  )}
                >
                  {getStatusIcon(item.status)}

                  <FileIcon className="size-5 shrink-0 text-muted-foreground" />

                  <div className="min-w-0 flex-1">
                    <p className="max-w-[250px] truncate text-sm font-medium">
                      {item.file.name}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="shrink-0 rounded bg-muted px-1">
                        {getFileTypeLabel(item.file.name)}
                      </span>
                      <span className="shrink-0">
                        {(item.file.size / 1024 / 1024).toFixed(2)} MB
                      </span>
                      <span className="truncate">{getStatusText(item)}</span>
                    </div>
                  </div>

                  {item.status === "pending" && !isUploading && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-7 shrink-0"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(item.id);
                      }}
                    >
                      <X className="size-4" />
                    </Button>
                  )}
                </div>
              );
            })}
          </div>

          {/* Status Summary */}
          {allCompleted && (
            <div className="flex items-center gap-4 text-xs">
              {statusCounts.success > 0 && (
                <span className="flex items-center gap-1 text-green-600">
                  <CheckCircle2 className="size-3" />
                  {statusCounts.success} uploaded
                </span>
              )}
              {statusCounts.duplicate > 0 && (
                <span className="flex items-center gap-1 text-yellow-600">
                  <AlertTriangle className="size-3" />
                  {statusCounts.duplicate} duplicates
                </span>
              )}
              {statusCounts.error > 0 && (
                <span className="flex items-center gap-1 text-destructive">
                  <AlertCircle className="size-3" />
                  {statusCounts.error} failed
                </span>
              )}
            </div>
          )}
        </div>
      )}

      <Button
        type="submit"
        disabled={pendingCount === 0 || isUploading || limitReached}
        className="w-full"
      >
        {isUploading ? (
          <>
            <Loader2 className="mr-2 size-4 animate-spin" />
            Uploading {uploadProgress.completed + 1} of {uploadProgress.total}
            ...
          </>
        ) : limitReached ? (
          "Limit Reached"
        ) : pendingCount > 0 ? (
          `Upload ${pendingCount} File${pendingCount !== 1 ? "s" : ""}`
        ) : allCompleted ? (
          "All Files Uploaded"
        ) : (
          "Select Files to Upload"
        )}
      </Button>
    </form>
  );
}
