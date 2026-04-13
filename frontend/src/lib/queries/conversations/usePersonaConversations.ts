import { useQuery } from "@tanstack/react-query";
import { env } from "@/env";
import { api } from "@/lib/api/client";
import type {
  ConversationListResponse,
  ConversationQueryParams,
} from "./interface";

/**
 * Fetch conversations by persona ID
 */
const fetchPersonaConversations = async (
  personaId: string,
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
    `${env.NEXT_PUBLIC_API_URL}/personas/${personaId}/conversations?${queryParams}`,
    {
      credentials: "include",
    },
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.message || "Failed to fetch persona conversations");
  }

  return response.json();
};

/**
 * Query key generator
 */
export const getPersonaConversationsQueryKey = (
  personaId: string,
  params?: ConversationQueryParams,
) => {
  return ["conversations", "persona", personaId, params];
};

/**
 * Hook to fetch persona conversations with pagination and filtering
 * TODO: Remove retry: false once backend API is stable
 */
export const usePersonaConversations = (
  personaId: string | undefined,
  params?: ConversationQueryParams,
) => {
  return useQuery({
    queryKey: personaId
      ? getPersonaConversationsQueryKey(personaId, params)
      : ["conversations", "disabled"],
    queryFn: () => {
      if (!personaId) throw new Error("Persona ID required");
      return fetchPersonaConversations(personaId, params);
    },
    enabled: !!personaId,
    staleTime: 30 * 1000, // 30 seconds
    retry: false, // Don't retry on 404 - let component handle with mock data
  });
};

/**
 * Fetch only the conversation count for a persona (limit=1 minimum required by backend)
 * Uses api client to include JWT token automatically
 */
const fetchPersonaConversationCount = async (
  personaId: string,
): Promise<number> => {
  try {
    const { data } = await api.get<ConversationListResponse>(
      `/personas/${personaId}/conversations?limit=1&offset=0`,
    );
    return data.total;
  } catch (error) {
    console.error(
      `[ERROR] Failed to fetch conversation count for persona ${personaId}:`,
      error,
    );
    // If API returns error, return 0 (persona has no conversations yet)
    return 0;
  }
};

/**
 * Query key for persona conversation count
 */
export const getPersonaConversationCountQueryKey = (personaId: string) => {
  return ["conversations", "persona", personaId, "count"];
};

/**
 * Hook to fetch only the conversation count for a persona
 * Useful for displaying counts in persona cards without fetching full conversation list
 */
export const usePersonaConversationCount = (personaId: string | undefined) => {
  return useQuery({
    queryKey: personaId
      ? getPersonaConversationCountQueryKey(personaId)
      : ["conversations", "count", "disabled"],
    queryFn: () => {
      if (!personaId) throw new Error("Persona ID required");
      return fetchPersonaConversationCount(personaId);
    },
    enabled: !!personaId,
    staleTime: 60 * 1000, // 1 minute - counts don't change as frequently
    retry: false, // Don't retry on 404
  });
};
