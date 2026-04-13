import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { toast } from "sonner";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import type { CreateWebhookRequest, WebhookConfigResponse } from "./interface";
import { getWebhookQueryKey } from "./useGetWebhook";

/**
 * Create or replace webhook configuration (account-level)
 * If webhook exists, it will be replaced
 */
const createWebhook = async (
  data: CreateWebhookRequest,
): Promise<WebhookConfigResponse> => {
  const response = await api.post<WebhookConfigResponse>(
    `/account/webhook`,
    data,
  );
  return response.data;
};

/**
 * Hook to create or update webhook configuration (account-level)
 * Requires JWT authentication
 */
export const useCreateWebhook = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateWebhookRequest) => {
      trackDashboardOperation("webhook_create", "started", {
        url: data.url,
        eventsCount: data.events?.length ?? 1,
      });
      return createWebhook(data);
    },
    onSuccess: (response) => {
      // Invalidate webhook config cache
      queryClient.invalidateQueries({
        queryKey: getWebhookQueryKey(),
      });

      toast.success("Webhook configured successfully!");
      trackDashboardOperation("webhook_create", "success", {
        enabled: response.enabled,
        personasCount: response.personas_count,
      });
    },
    onError: (error: Error) => {
      console.error("Failed to create webhook:", error);
      toast.error(error.message || "Failed to configure webhook");
      trackDashboardOperation("webhook_create", "error", {
        error: error.message,
      });
    },
  });
};
