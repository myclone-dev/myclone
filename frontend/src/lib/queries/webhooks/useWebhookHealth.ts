import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { WebhookHealthResponse } from "./interface";

/**
 * Query key for webhook health check
 */
export const getWebhookHealthQueryKey = () => ["webhook-health"];

/**
 * Fetch webhook system health
 * Public endpoint - no auth required
 */
const fetchWebhookHealth = async (): Promise<WebhookHealthResponse> => {
  const response = await api.get<WebhookHealthResponse>(
    "/personas/webhook/health",
  );
  return response.data;
};

/**
 * Hook to check webhook system health and supported features
 * Public endpoint - no authentication required
 */
export const useWebhookHealth = () => {
  return useQuery({
    queryKey: getWebhookHealthQueryKey(),
    queryFn: fetchWebhookHealth,
    staleTime: 10 * 60 * 1000, // 10 minutes
    retry: 3,
  });
};
