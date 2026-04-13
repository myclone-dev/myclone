import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  WidgetTokenResponse,
  CreateWidgetTokenRequest,
  WidgetTokenListResponse,
} from "./interface";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

/**
 * Query key for widget tokens list
 */
export const getWidgetTokensQueryKey = () => ["widget-tokens"];

/**
 * Fetch all widget tokens for the current user
 */
const fetchWidgetTokens = async (): Promise<WidgetTokenListResponse> => {
  const response = await api.get<WidgetTokenListResponse>(
    "/users/me/widget-tokens",
  );
  return response.data;
};

/**
 * Hook to get all widget tokens (active and revoked)
 */
export const useWidgetTokens = () => {
  return useQuery({
    queryKey: getWidgetTokensQueryKey(),
    queryFn: fetchWidgetTokens,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: 1,
  });
};

/**
 * Create a new widget token
 */
const createWidgetToken = async (
  request: CreateWidgetTokenRequest,
): Promise<WidgetTokenResponse> => {
  const response = await api.post<WidgetTokenResponse>(
    "/users/me/widget-tokens",
    request,
  );
  return response.data;
};

/**
 * Hook to create a new widget token
 */
export const useCreateWidgetToken = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: CreateWidgetTokenRequest) => {
      trackDashboardOperation("widget_token_create", "started", {
        tokenName: request.name,
      });
      try {
        const result = await createWidgetToken(request);
        trackDashboardOperation("widget_token_create", "success", {
          tokenName: request.name,
          tokenId: result.id,
        });
        return result;
      } catch (error) {
        trackDashboardOperation("widget_token_create", "error", {
          tokenName: request.name,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (newToken) => {
      // Update the cache with the new token
      queryClient.setQueryData<WidgetTokenListResponse>(
        getWidgetTokensQueryKey(),
        (oldData) => {
          if (!oldData) {
            return {
              tokens: [newToken],
              total: 1,
            };
          }
          return {
            tokens: [newToken, ...oldData.tokens],
            total: oldData.total + 1,
          };
        },
      );
    },
    onError: () => {
      // Error already tracked via trackDashboardOperation in mutationFn
    },
  });
};

/**
 * Revoke (soft-delete) a widget token
 */
const revokeWidgetToken = async (tokenId: string): Promise<void> => {
  await api.delete(`/users/me/widget-tokens/${tokenId}`);
};

/**
 * Hook to revoke a widget token
 */
export const useRevokeWidgetToken = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (tokenId: string) => {
      trackDashboardOperation("widget_token_revoke", "started", {
        tokenId,
      });
      try {
        await revokeWidgetToken(tokenId);
        trackDashboardOperation("widget_token_revoke", "success", {
          tokenId,
        });
      } catch (error) {
        trackDashboardOperation("widget_token_revoke", "error", {
          tokenId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (_, tokenId) => {
      // Update the cache - mark token as inactive
      queryClient.setQueryData<WidgetTokenListResponse>(
        getWidgetTokensQueryKey(),
        (oldData) => {
          if (!oldData) return oldData;
          return {
            ...oldData,
            tokens: oldData.tokens.map((token) =>
              token.id === tokenId ? { ...token, is_active: false } : token,
            ),
          };
        },
      );
    },
    onError: () => {
      // Error already tracked via trackDashboardOperation in mutationFn
    },
  });
};
