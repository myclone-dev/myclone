import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  ScrapingJobsResponse,
  DataSourceType,
  ScrapingStatus,
} from "./interface";

export interface FetchScrapingJobsParams {
  userId: string;
  source_type?: DataSourceType;
  status?: ScrapingStatus;
  limit?: number;
}

/**
 * Fetch scraping jobs for a user using new unified job status API
 */
const fetchScrapingJobs = async (
  params: FetchScrapingJobsParams,
): Promise<ScrapingJobsResponse> => {
  const { userId, ...queryParams } = params;
  const { data } = await api.get<ScrapingJobsResponse>(`/jobs/${userId}`, {
    params: queryParams,
  });
  return data;
};

export const getScrapingJobsQueryKey = (params: FetchScrapingJobsParams) => [
  "scraping-jobs",
  params,
];

/**
 * Query hook to get scraping jobs for a user with optional filtering
 */
export const useScrapingJobs = (
  userId: string | undefined,
  options?: {
    source_type?: DataSourceType;
    status?: ScrapingStatus;
    limit?: number;
    refetchInterval?:
      | number
      | false
      | ((query: { state: { data?: ScrapingJobsResponse } }) => number | false);
  },
) => {
  const params: FetchScrapingJobsParams = {
    userId: userId || "",
    source_type: options?.source_type,
    status: options?.status,
    limit: options?.limit || 50,
  };

  return useQuery({
    queryKey: userId
      ? getScrapingJobsQueryKey(params)
      : ["scraping-jobs", "disabled"],
    queryFn: async () => {
      if (!userId) throw new Error("User ID required");
      const result = await fetchScrapingJobs(params);
      return result;
    },
    enabled: !!userId,
    staleTime: Infinity, // Never auto-invalidate - only refetch via polling or manual trigger
    gcTime: 10 * 60 * 1000, // Keep in cache for 10 minutes after component unmount
    refetchOnWindowFocus: false, // Don't refetch when switching tabs
    refetchOnReconnect: false, // Don't refetch on network reconnect
    refetchInterval: options?.refetchInterval ?? false, // Only poll when function returns a number
  });
};
