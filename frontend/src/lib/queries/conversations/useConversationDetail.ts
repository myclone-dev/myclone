import { useQuery } from "@tanstack/react-query";
import { env } from "@/env";
import type { ConversationDetail } from "./interface";

/**
 * Fetch conversation by ID
 */
const fetchConversation = async (
  conversationId: string,
): Promise<ConversationDetail> => {
  const response = await fetch(
    `${env.NEXT_PUBLIC_API_URL}/conversations/${conversationId}`,
    {
      credentials: "include",
    },
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || "Failed to fetch conversation");
  }

  return response.json();
};

/**
 * Query key generator
 */
export const getConversationQueryKey = (conversationId: string) => {
  return ["conversations", conversationId];
};

/**
 * Hook to fetch a single conversation by ID
 * TODO: Remove retry: false once backend API is stable
 */
export const useConversation = (conversationId: string | undefined) => {
  return useQuery({
    queryKey: conversationId
      ? getConversationQueryKey(conversationId)
      : ["conversations", "disabled"],
    queryFn: () => {
      if (!conversationId) throw new Error("Conversation ID required");
      return fetchConversation(conversationId);
    },
    enabled: !!conversationId,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: false, // Don't retry on 404 - let component handle with mock data
  });
};
