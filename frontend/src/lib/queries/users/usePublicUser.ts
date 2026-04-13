import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { PublicUserDetails } from "./interface";

/**
 * Fetch public user details by username
 */
const fetchPublicUserDetails = async (
  username: string,
): Promise<PublicUserDetails> => {
  const { data } = await api.get<PublicUserDetails>(
    `/public/users/${username}`,
  );
  return data;
};

/**
 * Hook to fetch public user details
 */
export function usePublicUserDetails(username: string, enabled = true) {
  return useQuery({
    queryKey: ["public-user-details", username],
    queryFn: () => fetchPublicUserDetails(username),
    enabled: Boolean(username) && enabled,
    retry: 2,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    gcTime: 10 * 60 * 1000, // Keep in cache for 10 minutes
  });
}
