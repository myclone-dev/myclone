import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import type {
  EnableTemplateRequest,
  EnableTemplateParams,
  Workflow,
} from "./interface";

/**
 * Enable a workflow template for a persona
 */
const enableWorkflowTemplate = async (
  params: EnableTemplateParams,
  request: EnableTemplateRequest,
): Promise<Workflow> => {
  const { data } = await api.post<Workflow>(
    "/workflow-templates/enable",
    request,
    {
      params,
    },
  );
  return data;
};

/**
 * Hook to enable a workflow template for a persona
 *
 * @example
 * ```tsx
 * const enableTemplate = useEnableTemplate();
 *
 * const handleEnable = async () => {
 *   try {
 *     const workflow = await enableTemplate.mutateAsync({
 *       persona_id: "persona-uuid",
 *       template_id: "template-uuid",
 *       auto_publish: true
 *     });
 *     console.log("Template enabled:", workflow);
 *   } catch (error) {
 *     console.error("Failed to enable template:", error);
 *   }
 * };
 * ```
 */
export function useEnableTemplate() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      persona_id,
      template_id,
      auto_publish = false,
    }: EnableTemplateParams & EnableTemplateRequest) => {
      trackDashboardOperation("workflow_template_enable", "started", {
        persona_id,
        template_id,
        auto_publish,
      });

      const workflow = await enableWorkflowTemplate(
        { persona_id },
        { template_id, auto_publish },
      );

      trackDashboardOperation("workflow_template_enable", "success", {
        persona_id,
        template_id,
        workflow_id: workflow.id,
        auto_publish,
      });

      return workflow;
    },
    onSuccess: (workflow) => {
      // Invalidate workflows list for this persona
      queryClient.invalidateQueries({
        queryKey: ["workflows", workflow.persona_id],
      });

      // Invalidate templates list (to update usage stats if they were included)
      queryClient.invalidateQueries({
        queryKey: ["workflow-templates"],
      });
    },
    onError: (error: Error, variables) => {
      trackDashboardOperation("workflow_template_enable", "error", {
        persona_id: variables.persona_id,
        template_id: variables.template_id,
        error: error.message,
      });
    },
  });
}
