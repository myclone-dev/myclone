import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { TierPlansResponse } from "./interface";

/**
 * Fetch all available tier plans with their limits
 */
const fetchTierPlans = async (): Promise<TierPlansResponse> => {
  const response = await api.get<TierPlansResponse>("/tier/plans");
  return response.data;
};

/**
 * Query key generator for tier plans
 */
export const getTierPlansQueryKey = () => {
  return ["tier-plans"];
};

/**
 * Hook to fetch all tier plans
 */
export const useTierPlans = () => {
  return useQuery({
    queryKey: getTierPlansQueryKey(),
    queryFn: fetchTierPlans,
    staleTime: 60 * 60 * 1000, // 1 hour - tier plans don't change often
  });
};
