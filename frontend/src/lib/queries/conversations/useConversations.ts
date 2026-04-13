import { useQuery } from "@tanstack/react-query";
import { env } from "@/env";
import type {
  ConversationListResponse,
  ConversationQueryParams,
} from "./interface";

/**
 * Fetch conversations by user ID
 */
const fetchUserConversations = async (
  userId: string,
  params?: ConversationQueryParams,
): Promise<ConversationListResponse> => {
  const queryParams = new URLSearchParams({
    limit: String(params?.limit || 20),
    offset: String(params?.offset || 0),
    ...(params?.conversation_type && {
      conversation_type: params.conversation_type,
    }),
  });

  const response = await fetch(
    `${env.NEXT_PUBLIC_API_URL}/users/${userId}/conversations?${queryParams}`,
    {
      credentials: "include",
    },
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || "Failed to fetch conversations");
  }

  return response.json();
};

/**
 * Query key generator
 */
export const getUserConversationsQueryKey = (
  userId: string,
  params?: ConversationQueryParams,
) => {
  return ["conversations", "user", userId, params];
};

/**
 * Hook to fetch user conversations with pagination and filtering
 * TODO: Remove retry: false once backend API is stable
 */
export const useUserConversations = (
  userId: string | undefined,
  params?: ConversationQueryParams,
) => {
  return useQuery({
    queryKey: userId
      ? getUserConversationsQueryKey(userId, params)
      : ["conversations", "disabled"],
    queryFn: () => {
      if (!userId) throw new Error("User ID required");
      return fetchUserConversations(userId, params);
    },
    enabled: !!userId,
    staleTime: 30 * 1000, // 30 seconds
    retry: false, // Don't retry on 404 - let component handle with mock data
  });
};
