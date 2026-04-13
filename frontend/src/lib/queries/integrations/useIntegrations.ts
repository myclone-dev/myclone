import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  IntegrationListResponse,
  ConnectIntegrationRequest,
  DisconnectIntegrationRequest,
  Integration,
} from "./interface";

/**
 * Fetch all integrations for the current user
 */
const fetchIntegrations = async (): Promise<IntegrationListResponse> => {
  const response = await api.get<IntegrationListResponse>(
    "/api/v1/integrations",
  );
  return response.data;
};

/**
 * Connect a new integration
 */
const connectIntegration = async (
  request: ConnectIntegrationRequest,
): Promise<Integration> => {
  const response = await api.post<Integration>(
    "/api/v1/integrations/connect",
    request,
  );
  return response.data;
};

/**
 * Disconnect an existing integration
 */
const disconnectIntegration = async (
  request: DisconnectIntegrationRequest,
): Promise<void> => {
  await api.delete(`/api/v1/integrations/${request.id}`);
};

/**
 * Query key generator
 */
export const getIntegrationsQueryKey = () => ["integrations"];

/**
 * Hook to fetch all integrations
 */
export const useIntegrations = () => {
  return useQuery({
    queryKey: getIntegrationsQueryKey(),
    queryFn: fetchIntegrations,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to connect an integration
 */
export const useConnectIntegration = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: connectIntegration,
    onSuccess: () => {
      // Invalidate integrations query to refetch
      queryClient.invalidateQueries({
        queryKey: getIntegrationsQueryKey(),
      });
    },
  });
};

/**
 * Hook to disconnect an integration
 */
export const useDisconnectIntegration = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: disconnectIntegration,
    onSuccess: () => {
      // Invalidate integrations query to refetch
      queryClient.invalidateQueries({
        queryKey: getIntegrationsQueryKey(),
      });
    },
  });
};
