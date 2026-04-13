import { useQuery } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { env } from "@/env";
import type { ConversationSummaryResult } from "./interface";

/**
 * Fetch conversation summary from backend
 * Uses cookies for authentication (myclone_token)
 */
const fetchConversationSummary = async (
  conversationId: string,
): Promise<ConversationSummaryResult> => {
  const url = `${env.NEXT_PUBLIC_API_URL}/conversations/${conversationId}/summary`;

  const response = await fetch(url, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include", // Include cookies in the request
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const errorMessage =
      error.message || error.detail || "Failed to fetch conversation summary";
    Sentry.captureMessage(
      `Conversation summary fetch failed: ${errorMessage}`,
      {
        level: "error",
        tags: { operation: "conversation_summary" },
        contexts: {
          summary: {
            conversationId,
            status: response.status,
            error: errorMessage,
          },
        },
      },
    );
    throw new Error(errorMessage);
  }

  const data = await response.json();
  return data;
};

/**
 * Query key generator for conversation summary
 */
export const getConversationSummaryQueryKey = (conversationId: string) => {
  return ["conversation-summary", conversationId];
};

/**
 * Hook to fetch conversation summary
 * Uses cookie-based authentication (myclone_token)
 * @param conversationId - ID of the conversation
 * @param options - Query options (enabled, etc.)
 */
export const useConversationSummary = (
  conversationId: string | null,
  options?: { enabled?: boolean },
) => {
  const isEnabled = options?.enabled !== false && !!conversationId;

  return useQuery({
    queryKey: conversationId
      ? getConversationSummaryQueryKey(conversationId)
      : ["conversation-summary", "disabled"],
    queryFn: () => {
      if (!conversationId) {
        throw new Error("Conversation ID is required");
      }
      return fetchConversationSummary(conversationId);
    },
    enabled: isEnabled,
    staleTime: 30 * 60 * 1000, // 30 minutes - summaries don't change often
    retry: 1, // Only retry once for summaries
  });
};
