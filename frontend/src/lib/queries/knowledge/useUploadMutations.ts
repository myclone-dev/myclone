import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { toast } from "sonner";
import type { AxiosError } from "axios";
import type {
  LinkedInUploadRequest,
  TwitterUploadRequest,
  WebsiteUploadRequest,
  YouTubeUploadRequest,
  UploadResponse,
  DocumentUploadResponse,
  DocumentUploadRequest,
} from "./interface";
import { getScrapingJobsQueryKey } from "./useScrapingJobs";
import { parseApiError, type ApiErrorResponse } from "@/lib/utils/apiError";
import { markKnowledgeLibraryComplete } from "@/lib/utils/setupProgress";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

/**
 * Upload LinkedIn URL
 */
const uploadLinkedIn = async (
  request: LinkedInUploadRequest,
): Promise<UploadResponse> => {
  const { data } = await api.post("/scraping/linkedin", request);
  return data;
};

export const useLinkedInUpload = () => {
  const queryClient = useQueryClient();

  return useMutation<
    UploadResponse,
    AxiosError<ApiErrorResponse>,
    LinkedInUploadRequest
  >({
    mutationFn: async (request) => {
      trackDashboardOperation("linkedin_import", "started", {
        url: request.linkedin_url,
        userId: request.user_id,
      });
      try {
        const result = await uploadLinkedIn(request);
        trackDashboardOperation("linkedin_import", "success", {
          url: request.linkedin_url,
          jobId: result.job_id,
        });
        return result;
      } catch (error) {
        trackDashboardOperation("linkedin_import", "error", {
          url: request.linkedin_url,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data, variables) => {
      toast.success("LinkedIn scraping job queued successfully");
      // Mark knowledge library as completed
      markKnowledgeLibraryComplete();
      // Invalidate scraping jobs to refetch
      queryClient.invalidateQueries({
        queryKey: getScrapingJobsQueryKey({ userId: variables.user_id }),
      });
    },
    onError: (error) => {
      const errorMessage = parseApiError(error, "Failed to queue LinkedIn job");
      toast.error(errorMessage);
    },
  });
};

/**
 * Upload Twitter username
 */
const uploadTwitter = async (
  request: TwitterUploadRequest,
): Promise<UploadResponse> => {
  const { data } = await api.post("/scraping/twitter", request);
  return data;
};

export const useTwitterUpload = () => {
  const queryClient = useQueryClient();

  return useMutation<
    UploadResponse,
    AxiosError<ApiErrorResponse>,
    TwitterUploadRequest
  >({
    mutationFn: async (request) => {
      trackDashboardOperation("twitter_import", "started", {
        username: request.twitter_username,
        userId: request.user_id,
      });
      try {
        const result = await uploadTwitter(request);
        trackDashboardOperation("twitter_import", "success", {
          username: request.twitter_username,
          jobId: result.job_id,
        });
        return result;
      } catch (error) {
        trackDashboardOperation("twitter_import", "error", {
          username: request.twitter_username,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data, variables) => {
      toast.success("Twitter scraping job queued successfully");
      // Mark knowledge library as completed
      markKnowledgeLibraryComplete();
      queryClient.invalidateQueries({
        queryKey: getScrapingJobsQueryKey({ userId: variables.user_id }),
      });
    },
    onError: (error) => {
      const errorMessage = parseApiError(error, "Failed to queue Twitter job");
      toast.error(errorMessage);
    },
  });
};

/**
 * Upload website URL
 */
const uploadWebsite = async (
  request: WebsiteUploadRequest,
): Promise<UploadResponse> => {
  const { data } = await api.post("/scraping/website", request);
  return data;
};

export const useWebsiteUpload = () => {
  const queryClient = useQueryClient();

  return useMutation<
    UploadResponse,
    AxiosError<ApiErrorResponse>,
    WebsiteUploadRequest
  >({
    mutationFn: async (request) => {
      trackDashboardOperation("website_scrape", "started", {
        url: request.website_url,
        maxPages: request.max_pages || 10,
        userId: request.user_id,
      });
      try {
        const result = await uploadWebsite(request);
        trackDashboardOperation("website_scrape", "success", {
          url: request.website_url,
          maxPages: request.max_pages || 10,
          jobId: result.job_id,
        });
        return result;
      } catch (error) {
        trackDashboardOperation("website_scrape", "error", {
          url: request.website_url,
          maxPages: request.max_pages || 10,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data, variables) => {
      toast.success("Website scraping job queued successfully");
      // Mark knowledge library as completed
      markKnowledgeLibraryComplete();
      queryClient.invalidateQueries({
        queryKey: getScrapingJobsQueryKey({ userId: variables.user_id }),
      });
    },
    onError: (error) => {
      const errorMessage = parseApiError(error, "Failed to queue website job");
      toast.error(errorMessage);
    },
  });
};

/**
 * Upload PDF file
 */
const uploadPDF = async (
  username: string,
  file: File,
  personaName = "default",
): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("username", username);
  formData.append("persona_name", personaName);

  const { data } = await api.post("/ingestion/process-pdf-data", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return data;
};

export const usePDFUpload = () => {
  return useMutation<
    UploadResponse,
    AxiosError<ApiErrorResponse>,
    { username: string; file: File; personaName?: string }
  >({
    mutationFn: ({ username, file, personaName }) =>
      uploadPDF(username, file, personaName),
    onSuccess: () => {
      toast.success("PDF uploaded and processed successfully");
    },
    onError: (error) => {
      const errorMessage = parseApiError(error, "Failed to upload PDF");
      toast.error(errorMessage);
    },
  });
};

/**
 * Upload Document file (PDF, TXT, MD, Audio, Video)
 * Uses /api/v1/documents/add endpoint with duplicate detection
 */
const uploadDocument = async (
  request: DocumentUploadRequest,
): Promise<DocumentUploadResponse> => {
  const formData = new FormData();
  formData.append("file", request.file);
  formData.append("user_id", request.userId);
  formData.append("persona_name", request.personaName || "default");
  formData.append("force", String(request.force || false));

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

export const useDocumentUpload = () => {
  const queryClient = useQueryClient();

  return useMutation<
    DocumentUploadResponse,
    AxiosError<ApiErrorResponse>,
    DocumentUploadRequest
  >({
    mutationFn: async (request: DocumentUploadRequest) => {
      trackDashboardOperation("pdf_upload", "started", {
        fileName: request.file.name,
        fileSize: request.file.size,
        fileType: request.file.type,
        userId: request.userId,
      });
      try {
        const result = await uploadDocument(request);
        trackDashboardOperation("pdf_upload", "success", {
          fileName: request.file.name,
          fileSize: request.file.size,
          documentId: result.document_id,
        });
        return result;
      } catch (error) {
        trackDashboardOperation("pdf_upload", "error", {
          fileName: request.file.name,
          fileSize: request.file.size,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data, variables) => {
      // Check if upload was successful or if it's a duplicate
      if (data.success) {
        const extension = variables.file.name.split(".").pop()?.toLowerCase();
        const fileType =
          extension === "pdf"
            ? "PDF"
            : extension === "docx"
              ? "Word document"
              : extension === "pptx"
                ? "PowerPoint presentation"
                : extension === "xlsx"
                  ? "Excel spreadsheet"
                  : extension === "txt"
                    ? "text file"
                    : extension === "md"
                      ? "markdown file"
                      : extension === "mp3" ||
                          extension === "wav" ||
                          extension === "m4a"
                        ? "audio file"
                        : extension === "mp4" ||
                            extension === "mov" ||
                            extension === "avi" ||
                            extension === "mkv"
                          ? "video file"
                          : "document";
        toast.success(`${fileType} uploaded and queued for processing`);

        // Mark knowledge library as completed
        markKnowledgeLibraryComplete();

        // Invalidate scraping jobs to show the new document
        queryClient.invalidateQueries({
          queryKey: ["scraping-jobs"],
        });
        queryClient.invalidateQueries({
          queryKey: ["documents"],
        });
        // Invalidate usage statistics to update limits
        queryClient.invalidateQueries({
          queryKey: ["user-usage"],
        });
      } else {
        // Handle duplicate detection response
        toast.warning(data.message);
      }
    },
    onError: (error) => {
      const errorMessage = parseApiError(error, "Failed to upload document");
      toast.error(errorMessage);
    },
  });
};

/**
 * Upload Audio/Video files
 * Uses /api/v1/documents/add endpoint (same as useDocumentUpload)
 * This is an alias for useDocumentUpload for backward compatibility
 */
export const useMediaUpload = () => {
  return useDocumentUpload();
};

/**
 * Upload YouTube video URL
 * Uses /api/v1/voice-processing/ingest-youtube endpoint
 */
const uploadYouTube = async (
  request: YouTubeUploadRequest,
): Promise<UploadResponse> => {
  const { data } = await api.post("/voice-processing/ingest-youtube", request);
  return data;
};

export const useYouTubeUpload = () => {
  const queryClient = useQueryClient();

  return useMutation<
    UploadResponse,
    AxiosError<ApiErrorResponse>,
    YouTubeUploadRequest
  >({
    mutationFn: uploadYouTube,
    onSuccess: (data, variables) => {
      toast.success("YouTube video queued for processing");
      // Mark knowledge library as completed
      markKnowledgeLibraryComplete();
      // Invalidate scraping jobs to show the new YouTube job
      queryClient.invalidateQueries({
        queryKey: getScrapingJobsQueryKey({ userId: variables.user_id }),
      });
      // Invalidate usage statistics to update limits
      queryClient.invalidateQueries({
        queryKey: ["user-usage"],
      });
    },
    onError: (error) => {
      const errorMessage = parseApiError(error, "Failed to queue YouTube job");
      toast.error(errorMessage);
    },
  });
};

/**
 * Raw Text Upload Request
 */
export interface RawTextUploadRequest {
  title: string;
  content: string;
  userId: string;
  personaName?: string;
  force?: boolean;
}

/**
 * Upload raw text content directly (meeting notes, transcripts, etc.)
 * Uses /api/v1/documents/add-text endpoint
 */
const uploadRawText = async (
  request: RawTextUploadRequest,
): Promise<DocumentUploadResponse> => {
  const { data } = await api.post<DocumentUploadResponse>(
    "/documents/add-text",
    {
      title: request.title,
      content: request.content,
      user_id: request.userId,
      persona_name: request.personaName || "default",
      force: request.force || false,
    },
  );
  return data;
};

export const useRawTextUpload = () => {
  const queryClient = useQueryClient();

  return useMutation<
    DocumentUploadResponse,
    AxiosError<ApiErrorResponse>,
    RawTextUploadRequest
  >({
    mutationFn: async (request: RawTextUploadRequest) => {
      trackDashboardOperation("raw_text_upload", "started", {
        title: request.title,
        contentLength: request.content.length,
        userId: request.userId,
      });
      try {
        const result = await uploadRawText(request);
        trackDashboardOperation("raw_text_upload", "success", {
          title: request.title,
          contentLength: request.content.length,
          documentId: result.document_id,
        });
        return result;
      } catch (error) {
        trackDashboardOperation("raw_text_upload", "error", {
          title: request.title,
          contentLength: request.content.length,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data) => {
      if (data.success) {
        toast.success("Text content added and queued for processing");

        // Mark knowledge library as completed
        markKnowledgeLibraryComplete();

        // Invalidate queries to refresh data
        queryClient.invalidateQueries({
          queryKey: ["scraping-jobs"],
        });
        queryClient.invalidateQueries({
          queryKey: ["documents"],
        });
        queryClient.invalidateQueries({
          queryKey: ["user-usage"],
        });
        queryClient.invalidateQueries({
          queryKey: ["knowledge-library"],
        });
      } else {
        // Handle duplicate detection response
        toast.warning(data.message);
      }
    },
    onError: (error) => {
      const errorMessage = parseApiError(error, "Failed to add text content");
      toast.error(errorMessage);
    },
  });
};
