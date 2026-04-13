import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  Workflow,
  WorkflowsListResponse,
  CreateWorkflowRequest,
  UpdateWorkflowRequest,
  WorkflowAnalytics,
} from "./interface";

// ============================================================================
// QUERY KEYS
// ============================================================================

export const workflowKeys = {
  all: ["workflows"] as const,
  lists: () => [...workflowKeys.all, "list"] as const,
  list: (filters: { persona_id?: string; active_only?: boolean }) =>
    [...workflowKeys.lists(), filters] as const,
  details: () => [...workflowKeys.all, "detail"] as const,
  detail: (id: string) => [...workflowKeys.details(), id] as const,
  analytics: (id: string) => [...workflowKeys.all, "analytics", id] as const,
};

// ============================================================================
// LIST WORKFLOWS
// ============================================================================

interface UseWorkflowsOptions {
  persona_id?: string;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}

export const useWorkflows = (options?: UseWorkflowsOptions) => {
  return useQuery({
    queryKey: workflowKeys.list({
      persona_id: options?.persona_id,
      active_only: options?.active_only,
    }),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (options?.persona_id) params.append("persona_id", options.persona_id);
      if (options?.active_only !== undefined)
        params.append("active_only", String(options.active_only));
      if (options?.limit) params.append("limit", String(options.limit));
      if (options?.offset) params.append("offset", String(options.offset));

      const queryString = params.toString();
      const url = queryString ? `/workflows?${queryString}` : "/workflows";

      const response = await api.get<WorkflowsListResponse>(url);
      return response.data;
    },
    staleTime: 30 * 1000, // 30 seconds
  });
};

// ============================================================================
// GET SINGLE WORKFLOW
// ============================================================================

export const useWorkflow = (workflowId: string | undefined) => {
  return useQuery({
    queryKey: workflowId
      ? workflowKeys.detail(workflowId)
      : ["workflows", "disabled"],
    queryFn: async () => {
      if (!workflowId) throw new Error("Workflow ID is required");
      const response = await api.get<Workflow>(`/workflows/${workflowId}`);
      return response.data;
    },
    enabled: !!workflowId,
    staleTime: 60 * 1000, // 1 minute
  });
};

// ============================================================================
// CREATE WORKFLOW
// ============================================================================

export const useCreateWorkflow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (
      data: CreateWorkflowRequest & { persona_id: string },
    ) => {
      const { persona_id, ...workflowData } = data;
      const response = await api.post<Workflow>(
        `/workflows?persona_id=${persona_id}`,
        workflowData,
      );
      return response.data;
    },
    onSuccess: () => {
      // Invalidate all workflow lists
      queryClient.invalidateQueries({ queryKey: workflowKeys.lists() });
    },
  });
};

// ============================================================================
// UPDATE WORKFLOW
// ============================================================================

export const useUpdateWorkflow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      workflowId,
      data,
    }: {
      workflowId: string;
      data: UpdateWorkflowRequest;
    }) => {
      const response = await api.patch<Workflow>(
        `/workflows/${workflowId}`,
        data,
      );
      return response.data;
    },
    onSuccess: (data) => {
      // Invalidate lists and specific workflow
      queryClient.invalidateQueries({ queryKey: workflowKeys.lists() });
      queryClient.invalidateQueries({ queryKey: workflowKeys.detail(data.id) });
    },
  });
};

// ============================================================================
// PUBLISH WORKFLOW
// ============================================================================

export const usePublishWorkflow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (workflowId: string) => {
      const response = await api.post<Workflow>(
        `/workflows/${workflowId}/publish`,
      );
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.lists() });
      queryClient.invalidateQueries({ queryKey: workflowKeys.detail(data.id) });
    },
  });
};

// ============================================================================
// DELETE WORKFLOW
// ============================================================================

export const useDeleteWorkflow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (workflowId: string) => {
      await api.delete(`/workflows/${workflowId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.lists() });
    },
  });
};

// ============================================================================
// GET ANALYTICS
// ============================================================================

export const useWorkflowAnalytics = (workflowId: string | undefined) => {
  return useQuery({
    queryKey: workflowId
      ? workflowKeys.analytics(workflowId)
      : ["workflows", "analytics", "disabled"],
    queryFn: async () => {
      if (!workflowId) throw new Error("Workflow ID is required");
      const response = await api.get<WorkflowAnalytics>(
        `/workflows/${workflowId}/analytics`,
      );
      return response.data;
    },
    enabled: !!workflowId,
    staleTime: 60 * 1000, // 1 minute
  });
};

// ============================================================================
// REGENERATE WORKFLOW OBJECTIVE
// ============================================================================

export const useRegenerateWorkflowObjective = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (workflowId: string) => {
      const response = await api.post<Workflow>(
        `/workflows/${workflowId}/regenerate-objective`,
      );
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.detail(data.id) });
    },
  });
};

// ============================================================================
// DUPLICATE WORKFLOW
// ============================================================================

export const useDuplicateWorkflow = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      workflowId,
      targetPersonaId,
    }: {
      workflowId: string;
      targetPersonaId: string;
    }) => {
      // 1. Get original workflow
      const originalResponse = await api.get<Workflow>(
        `/workflows/${workflowId}`,
      );
      const original = originalResponse.data;

      // 2. Create copy for target persona
      const copyData: CreateWorkflowRequest = {
        workflow_type: original.workflow_type,
        title: `${original.title} (Copy)`,
        description: original.description,
        opening_message: original.opening_message,
        workflow_objective: original.workflow_objective,
        workflow_config: original.workflow_config,
        result_config: original.result_config,
        trigger_config: original.trigger_config,
      };

      const response = await api.post<Workflow>(
        `/workflows?persona_id=${targetPersonaId}`,
        copyData,
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.lists() });
    },
  });
};
