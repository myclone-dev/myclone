import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { TierUsageResponse } from "./interface";

/**
 * Fetch user's tier usage statistics (uses JWT token to identify user)
 */
const fetchUserUsage = async (): Promise<TierUsageResponse> => {
  const response = await api.get<TierUsageResponse>(`/tier/usage`);
  return response.data;
};

/**
 * Query key generator for user usage
 */
export const getUserUsageQueryKey = () => {
  return ["user-usage"];
};

/**
 * Hook to fetch user's tier usage statistics
 * Uses JWT authentication - no need to pass userId
 * Returns current usage vs limits for:
 * - Raw text files (txt, md)
 * - Document files (pdf, docx, xlsx, pptx)
 * - Multimedia files (audio, video) with duration tracking
 * - YouTube videos with duration tracking
 */
export const useUserUsage = (options?: { refetchInterval?: number }) => {
  return useQuery({
    queryKey: getUserUsageQueryKey(),
    queryFn: fetchUserUsage,
    staleTime: 30 * 1000, // 30 seconds - usage updates frequently
    refetchInterval: options?.refetchInterval,
  });
};
