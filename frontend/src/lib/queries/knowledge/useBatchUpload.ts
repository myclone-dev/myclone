import { useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { toast } from "sonner";
import type {
  BatchFileItem,
  BatchFileStatus,
  BatchUploadResult,
  DocumentUploadResponse,
} from "./interface";
import { parseApiError } from "@/lib/utils/apiError";
import { markKnowledgeLibraryComplete } from "@/lib/utils/setupProgress";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

interface UseBatchUploadOptions {
  userId: string;
  personaName?: string;
  force?: boolean;
  /** Auto-clear completed files after upload (default: true) */
  autoClearOnComplete?: boolean;
  /** Delay in ms before auto-clearing (default: 3000) */
  autoClearDelay?: number;
  onFileStatusChange?: (fileId: string, status: BatchFileStatus) => void;
  onComplete?: (result: BatchUploadResult) => void;
}

/**
 * Upload a single document file
 */
const uploadSingleDocument = async (
  userId: string,
  file: File,
  personaName: string,
  force: boolean,
): Promise<DocumentUploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("user_id", userId);
  formData.append("persona_name", personaName);
  formData.append("force", String(force));

  const { data } = await api.post<DocumentUploadResponse>(
    "/documents/add",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );
  return data;
};

/**
 * Generate a unique ID for batch file tracking
 */
const generateFileId = (): string => {
  return `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
};

/**
 * Hook for batch uploading multiple documents with progress tracking
 */
export function useBatchUpload(options: UseBatchUploadOptions) {
  const {
    userId,
    personaName = "default",
    force = false,
    autoClearOnComplete = true,
    autoClearDelay = 3000,
    onComplete,
  } = options;
  const queryClient = useQueryClient();

  const [files, setFiles] = useState<BatchFileItem[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({
    completed: 0,
    total: 0,
  });

  /**
   * Add files to the upload queue
   */
  const addFiles = useCallback((newFiles: File[]) => {
    const fileItems: BatchFileItem[] = newFiles.map((file) => ({
      id: generateFileId(),
      file,
      status: "pending" as BatchFileStatus,
      progress: 0,
    }));

    setFiles((prev) => [...prev, ...fileItems]);
    return fileItems;
  }, []);

  /**
   * Remove a file from the queue
   */
  const removeFile = useCallback((fileId: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== fileId));
  }, []);

  /**
   * Clear all files from the queue
   */
  const clearFiles = useCallback(() => {
    setFiles([]);
    setUploadProgress({ completed: 0, total: 0 });
  }, []);

  /**
   * Update a specific file's status
   */
  const updateFileStatus = useCallback(
    (
      fileId: string,
      updates: Partial<
        Pick<
          BatchFileItem,
          "status" | "progress" | "errorMessage" | "documentId"
        >
      >,
    ) => {
      setFiles((prev) =>
        prev.map((f) => (f.id === fileId ? { ...f, ...updates } : f)),
      );
    },
    [],
  );

  /**
   * Upload all pending files
   */
  const uploadAll = useCallback(async () => {
    const pendingFiles = files.filter((f) => f.status === "pending");
    if (pendingFiles.length === 0) {
      toast.info("No files to upload");
      return;
    }

    setIsUploading(true);
    setUploadProgress({ completed: 0, total: pendingFiles.length });

    trackDashboardOperation("batch_upload", "started", {
      fileCount: pendingFiles.length,
      userId,
    });

    const results: BatchUploadResult = {
      totalFiles: pendingFiles.length,
      successCount: 0,
      errorCount: 0,
      duplicateCount: 0,
      results: [],
    };

    // Upload files sequentially to avoid overwhelming the server
    for (const fileItem of pendingFiles) {
      updateFileStatus(fileItem.id, { status: "uploading", progress: 50 });

      try {
        const response = await uploadSingleDocument(
          userId,
          fileItem.file,
          personaName,
          force,
        );

        if (response.success) {
          updateFileStatus(fileItem.id, {
            status: "success",
            progress: 100,
            documentId: response.document_id,
          });
          results.successCount++;
          results.results.push({
            fileName: fileItem.file.name,
            status: "success",
            documentId: response.document_id,
          });
        } else {
          // Duplicate detected
          updateFileStatus(fileItem.id, {
            status: "duplicate",
            progress: 100,
            errorMessage: response.message,
            documentId: response.document_id,
          });
          results.duplicateCount++;
          results.results.push({
            fileName: fileItem.file.name,
            status: "duplicate",
            documentId: response.document_id,
            errorMessage: response.message,
          });
        }
      } catch (error) {
        const errorMessage = parseApiError(error, "Upload failed");
        updateFileStatus(fileItem.id, {
          status: "error",
          progress: 0,
          errorMessage,
        });
        results.errorCount++;
        results.results.push({
          fileName: fileItem.file.name,
          status: "error",
          errorMessage,
        });
      }

      setUploadProgress((prev) => ({
        ...prev,
        completed: prev.completed + 1,
      }));
    }

    setIsUploading(false);

    // Track completion
    trackDashboardOperation("batch_upload", "success", {
      fileCount: pendingFiles.length,
      successCount: results.successCount,
      errorCount: results.errorCount,
      duplicateCount: results.duplicateCount,
    });

    // Show summary toast
    if (results.successCount > 0) {
      toast.success(
        `Successfully uploaded ${results.successCount} of ${results.totalFiles} files`,
      );
      markKnowledgeLibraryComplete();
    }

    if (results.errorCount > 0) {
      toast.error(`${results.errorCount} file(s) failed to upload`);
    }

    if (results.duplicateCount > 0) {
      toast.warning(`${results.duplicateCount} duplicate file(s) skipped`);
    }

    // Invalidate queries
    queryClient.invalidateQueries({ queryKey: ["scraping-jobs"] });
    queryClient.invalidateQueries({ queryKey: ["documents"] });
    queryClient.invalidateQueries({ queryKey: ["user-usage"] });

    onComplete?.(results);

    // Auto-clear completed files after delay to prevent memory leak
    if (autoClearOnComplete && results.errorCount === 0) {
      setTimeout(() => {
        setFiles((prev) =>
          prev.filter(
            (f) => f.status !== "success" && f.status !== "duplicate",
          ),
        );
        setUploadProgress({ completed: 0, total: 0 });
      }, autoClearDelay);
    }

    return results;
  }, [
    files,
    userId,
    personaName,
    force,
    autoClearOnComplete,
    autoClearDelay,
    updateFileStatus,
    queryClient,
    onComplete,
  ]);

  /**
   * Retry failed uploads
   */
  const retryFailed = useCallback(() => {
    setFiles((prev) =>
      prev.map((f) =>
        f.status === "error" ? { ...f, status: "pending", progress: 0 } : f,
      ),
    );
  }, []);

  /**
   * Get counts by status
   */
  const statusCounts = {
    pending: files.filter((f) => f.status === "pending").length,
    uploading: files.filter((f) => f.status === "uploading").length,
    success: files.filter((f) => f.status === "success").length,
    error: files.filter((f) => f.status === "error").length,
    duplicate: files.filter((f) => f.status === "duplicate").length,
  };

  return {
    files,
    isUploading,
    uploadProgress,
    statusCounts,
    addFiles,
    removeFile,
    clearFiles,
    updateFileStatus,
    uploadAll,
    retryFailed,
  };
}
