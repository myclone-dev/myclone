import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { TemplateListParams, TemplateListResponse } from "./interface";

/**
 * Fetch workflow templates from backend
 */
const fetchWorkflowTemplates = async (
  params: TemplateListParams = {},
): Promise<TemplateListResponse> => {
  const { data } = await api.get<TemplateListResponse>("/workflow-templates", {
    params,
  });
  return data;
};

/**
 * Query key generator for workflow templates
 */
export const getWorkflowTemplatesQueryKey = (
  params: TemplateListParams = {},
) => {
  return ["workflow-templates", params];
};

/**
 * Hook to fetch workflow templates
 *
 * @example
 * ```tsx
 * // List all templates
 * const { data, isLoading } = useWorkflowTemplates();
 *
 * // Filter by category with stats
 * const { data } = useWorkflowTemplates({
 *   category: "cpa",
 *   include_stats: true,
 *   limit: 10
 * });
 * ```
 */
export function useWorkflowTemplates(
  params: TemplateListParams = {},
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: getWorkflowTemplatesQueryKey(params),
    queryFn: () => fetchWorkflowTemplates(params),
    enabled: options?.enabled !== false,
    staleTime: 5 * 60 * 1000, // 5 minutes - templates don't change often
  });
}
