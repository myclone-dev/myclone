import { useQuery } from "@tanstack/react-query";
import { env } from "@/env";
import type { VoiceClone } from "./interface";

/**
 * Fetch voice clones from all providers using the unified endpoint
 * Backend now handles merging from all platforms (elevenlabs, cartesia)
 * and includes platform field in each response
 */
const fetchAllVoiceClones = async (userId: string): Promise<VoiceClone[]> => {
  const endpoint = `${env.NEXT_PUBLIC_API_URL}/voice-clones/users/${userId}`;
  const response = await fetch(endpoint, {
    method: "GET",
    credentials: "include",
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      error.detail || error.message || "Failed to fetch voice clones",
    );
  }

  return response.json();
};

/**
 * Query key generator
 */
export const getVoiceClonesQueryKey = (userId: string) => {
  return ["voice-clones", userId];
};

/**
 * Hook to fetch user's voice clones from all providers
 * Uses unified endpoint that returns all voice clones with platform field
 * Backend handles merging from elevenlabs, cartesia, and future platforms
 */
export const useVoiceClones = (userId: string | undefined) => {
  return useQuery({
    queryKey: userId ? getVoiceClonesQueryKey(userId) : ["voice-clones"],
    queryFn: () => {
      if (!userId) throw new Error("User ID required");
      return fetchAllVoiceClones(userId);
    },
    enabled: !!userId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
