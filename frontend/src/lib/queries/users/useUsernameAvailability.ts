import { useQuery } from "@tanstack/react-query";
import { env } from "@/env";
import type { UsernameAvailabilityResponse } from "./interface";

/**
 * Fetch username availability from the API
 *
 * @param username - The username to check
 * @returns Promise with availability response
 */
const checkUsernameAvailability = async (
  username: string,
): Promise<UsernameAvailabilityResponse> => {
  const response = await fetch(
    `${env.NEXT_PUBLIC_API_URL}/users/check-username/${encodeURIComponent(username)}`,
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    },
  );

  if (!response.ok) {
    throw new Error("Failed to check username availability");
  }

  return response.json();
};

/**
 * Query key generator for username availability
 */
export const getUsernameAvailabilityQueryKey = (username: string) => {
  return ["username-availability", username.toLowerCase()];
};

/**
 * Hook to check if a username is available
 *
 * @param username - The username to check (null to disable query)
 * @param options - Query options
 * @returns Query result with availability data
 */
export const useUsernameAvailability = (
  username: string | null,
  options?: { enabled?: boolean },
) => {
  return useQuery({
    queryKey: username
      ? getUsernameAvailabilityQueryKey(username)
      : ["username-availability", "disabled"],
    queryFn: () => {
      if (!username) throw new Error("Username is required");
      return checkUsernameAvailability(username);
    },
    enabled: options?.enabled !== false && !!username && username.length >= 3,
    staleTime: 5 * 60 * 1000, // 5 minutes - usernames don't change often
    retry: false, // Don't retry on 404/422 errors
  });
};
