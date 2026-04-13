import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { api } from "@/lib/api/client";
import type {
  WidgetConfigData,
  WidgetConfigResponse,
  UpdateWidgetConfigRequest,
} from "./interface";

/**
 * Query key for widget config
 */
export const widgetConfigQueryKey = ["user", "widget-config"] as const;

/**
 * Fetch widget config from the API
 */
const fetchWidgetConfig = async (): Promise<WidgetConfigResponse> => {
  const { data } = await api.get<WidgetConfigResponse>(
    "/users/me/widget-config",
  );
  return data;
};

/**
 * Update widget config via API
 */
const updateWidgetConfig = async (
  config: WidgetConfigData,
): Promise<WidgetConfigResponse> => {
  const { data } = await api.put<WidgetConfigResponse>(
    "/users/me/widget-config",
    { config } satisfies UpdateWidgetConfigRequest,
  );
  return data;
};

/**
 * Delete widget config via API
 */
const deleteWidgetConfig = async (): Promise<void> => {
  await api.delete("/users/me/widget-config");
};

/**
 * Query hook to fetch widget config from server
 *
 * Includes automatic retry with exponential backoff for network errors.
 *
 * @param options.enabled - Whether to enable the query (default: true)
 */
export const useWidgetConfigQuery = (options?: { enabled?: boolean }) => {
  return useQuery({
    queryKey: widgetConfigQueryKey,
    queryFn: fetchWidgetConfig,
    enabled: options?.enabled !== false,
    staleTime: 5 * 60 * 1000, // 5 minutes - config doesn't change often
    gcTime: 30 * 60 * 1000, // 30 minutes cache
    retry: 2, // Retry failed requests up to 2 times
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000), // Exponential backoff, max 30s
  });
};

/**
 * Mutation hook to update widget config on server
 *
 * Automatically invalidates the widget config query on success.
 */
export const useUpdateWidgetConfig = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (config: WidgetConfigData) => {
      trackDashboardOperation("widget_config_save", "started", {});
      try {
        const result = await updateWidgetConfig(config);
        trackDashboardOperation("widget_config_save", "success", {});
        return result;
      } catch (error) {
        trackDashboardOperation("widget_config_save", "error", {
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data) => {
      // Update the cache with the new config
      queryClient.setQueryData(widgetConfigQueryKey, data);
    },
  });
};

/**
 * Mutation hook to delete widget config from server
 *
 * Resets the config to null, allowing the user to start fresh.
 */
export const useDeleteWidgetConfig = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      trackDashboardOperation("widget_config_delete", "started", {});
      try {
        await deleteWidgetConfig();
        trackDashboardOperation("widget_config_delete", "success", {});
      } catch (error) {
        trackDashboardOperation("widget_config_delete", "error", {
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: () => {
      // Clear the cache
      queryClient.setQueryData(widgetConfigQueryKey, {
        config: null,
        updated_at: null,
      });
    },
  });
};
