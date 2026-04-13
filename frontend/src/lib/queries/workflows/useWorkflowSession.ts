import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { WorkflowSession } from "./interface";

// ============================================================================
// QUERY KEYS
// ============================================================================

export const workflowSessionKeys = {
  all: ["workflow-sessions"] as const,
  details: () => [...workflowSessionKeys.all, "detail"] as const,
  detail: (sessionId: string) =>
    [...workflowSessionKeys.details(), sessionId] as const,
};

// ============================================================================
// GET WORKFLOW SESSION BY ID
// ============================================================================

/**
 * Fetch a workflow session by its ID
 * GET /api/workflows/sessions/{session_id}
 */
export const useWorkflowSession = (sessionId: string | undefined | null) => {
  return useQuery({
    queryKey: sessionId
      ? workflowSessionKeys.detail(sessionId)
      : ["workflow-sessions", "disabled"],
    queryFn: async () => {
      if (!sessionId) throw new Error("Session ID is required");
      const response = await api.get<WorkflowSession>(
        `/workflows/sessions/${sessionId}`,
      );
      return response.data;
    },
    enabled: !!sessionId,
    staleTime: 60 * 1000, // 1 minute
    // Don't retry on 404 - session may not exist
    retry: (failureCount, error) => {
      // Don't retry on 404
      if (error && "response" in error) {
        const axiosError = error as { response?: { status?: number } };
        if (axiosError.response?.status === 404) return false;
      }
      return failureCount < 2;
    },
  });
};
