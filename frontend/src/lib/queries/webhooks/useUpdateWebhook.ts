import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { toast } from "sonner";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import type { UpdateWebhookRequest, WebhookConfigResponse } from "./interface";
import { getWebhookQueryKey } from "./useGetWebhook";

/**
 * Partially update webhook configuration (account-level)
 * Only provided fields are updated
 */
const updateWebhook = async (
  data: UpdateWebhookRequest,
): Promise<WebhookConfigResponse> => {
  const response = await api.patch<WebhookConfigResponse>(
    `/account/webhook`,
    data,
  );
  return response.data;
};

/**
 * Hook to partially update webhook configuration (account-level)
 * Requires JWT authentication
 * Note: Webhook must exist (created with POST first)
 */
export const useUpdateWebhook = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateWebhookRequest) => {
      trackDashboardOperation("webhook_update", "started", {
        fields: Object.keys(data),
      });
      return updateWebhook(data);
    },
    onSuccess: (response) => {
      // Invalidate webhook config cache
      queryClient.invalidateQueries({
        queryKey: getWebhookQueryKey(),
      });

      toast.success("Webhook updated successfully!");
      trackDashboardOperation("webhook_update", "success", {
        enabled: response.enabled,
        personasCount: response.personas_count,
      });
    },
    onError: (error: Error) => {
      console.error("Failed to update webhook:", error);
      toast.error(error.message || "Failed to update webhook");
      trackDashboardOperation("webhook_update", "error", {
        error: error.message,
      });
    },
  });
};
