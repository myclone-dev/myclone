import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { WebhookConfigResponse } from "./interface";

/**
 * Query key for webhook configuration (account-level)
 */
export const getWebhookQueryKey = () => ["webhook-config"];

/**
 * Fetch webhook configuration for the account
 */
const fetchWebhookConfig = async (): Promise<WebhookConfigResponse> => {
  const response = await api.get<WebhookConfigResponse>(`/account/webhook`);
  return response.data;
};

/**
 * Hook to get webhook configuration for the account
 * Requires JWT authentication
 */
export const useGetWebhook = () => {
  return useQuery({
    queryKey: getWebhookQueryKey(),
    queryFn: fetchWebhookConfig,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
