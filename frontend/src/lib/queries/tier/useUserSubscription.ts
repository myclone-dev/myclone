import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { UserSubscription } from "./interface";

/**
 * Fetch user's active subscription (uses JWT token to identify user)
 */
const fetchUserSubscription = async (): Promise<UserSubscription> => {
  const response = await api.get<UserSubscription>(`/tier/subscription`);
  return response.data;
};

/**
 * Query key generator for user subscription
 */
export const getUserSubscriptionQueryKey = () => {
  return ["user-subscription"];
};

/**
 * Hook to fetch user's active subscription
 * Uses JWT authentication - no need to pass userId
 * Returns free tier (tier_id=0) as default if no active subscription exists
 */
export const useUserSubscription = () => {
  return useQuery({
    queryKey: getUserSubscriptionQueryKey(),
    queryFn: fetchUserSubscription,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
