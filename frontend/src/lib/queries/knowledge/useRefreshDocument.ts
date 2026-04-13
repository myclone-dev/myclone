import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { api } from "@/lib/api/client";

export interface RefreshDocumentRequest {
  user_id: string;
  document_id: string;
}

export interface RefreshDocumentResponse {
  success: boolean;
  message: string;
  document_id: string;
  job_id: string;
}

/**
 * Refresh document embeddings via POST /api/v1/documents/refresh
 */
const refreshDocument = async (
  request: RefreshDocumentRequest,
): Promise<RefreshDocumentResponse> => {
  // Create FormData for multipart/form-data request
  const formData = new FormData();
  formData.append("user_id", request.user_id);
  formData.append("document_id", request.document_id);

  const { data } = await api.post<RefreshDocumentResponse>(
    "/documents/refresh",
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
 * Mutation hook to refresh document embeddings
 * Invalidates scraping jobs query on success to show new job status
 */
export const useRefreshDocument = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: refreshDocument,
    onSuccess: () => {
      // Invalidate scraping jobs to refetch and show the new refresh job
      queryClient.invalidateQueries({ queryKey: ["scraping-jobs"] });
    },
    onError: (error: Error) => {
      Sentry.captureException(error, {
        tags: { operation: "document_refresh" },
        contexts: { document: { error: error.message } },
      });
    },
  });
};
