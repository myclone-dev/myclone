import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { toast } from "sonner";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { getWebhookQueryKey } from "./useGetWebhook";

/**
 * Delete webhook configuration (account-level)
 * Completely removes webhook (URL, events, secret)
 */
const deleteWebhook = async (): Promise<void> => {
  await api.delete(`/account/webhook`);
};

/**
 * Hook to delete webhook configuration (account-level)
 * Requires JWT authentication
 */
export const useDeleteWebhook = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => {
      trackDashboardOperation("webhook_delete", "started", {});
      return deleteWebhook();
    },
    onSuccess: () => {
      // Invalidate webhook config cache
      queryClient.invalidateQueries({
        queryKey: getWebhookQueryKey(),
      });

      toast.success("Webhook deleted successfully!");
      trackDashboardOperation("webhook_delete", "success", {});
    },
    onError: (error: Error) => {
      console.error("Failed to delete webhook:", error);
      toast.error(error.message || "Failed to delete webhook");
      trackDashboardOperation("webhook_delete", "error", {
        error: error.message,
      });
    },
  });
};
