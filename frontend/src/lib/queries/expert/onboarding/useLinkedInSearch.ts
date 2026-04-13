import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { env } from "@/env";
import type {
  LinkedInSearchRequest,
  LinkedInSearchResponse,
} from "./interface";

// Generate stable query key based on search criteria
export const getLinkedInSearchQueryKey = (
  searchData: LinkedInSearchRequest,
) => {
  return [
    "linkedin-search",
    {
      name: searchData.name,
      current_company: searchData.current_company,
      role: searchData.role,
    },
  ];
};

// Fetch function for LinkedIn search
const fetchLinkedInSearch = async (
  searchData: LinkedInSearchRequest,
): Promise<LinkedInSearchResponse> => {
  const response = await fetch(
    `${env.NEXT_PUBLIC_API_URL}/users/linkedin/search`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(searchData),
    },
  );

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.message || `HTTP ${response.status}: ${response.statusText}`,
    );
  }

  const result: LinkedInSearchResponse = await response.json();

  if (!result.success) {
    throw new Error("LinkedIn search failed");
  }

  return result;
};

// Query hook for cached LinkedIn search
export const useLinkedInSearchQuery = (
  searchData: LinkedInSearchRequest | null,
  options?: {
    enabled?: boolean;
    staleTime?: number;
  },
) => {
  const queryResult = useQuery({
    queryKey: searchData
      ? getLinkedInSearchQueryKey(searchData)
      : ["linkedin-search", "disabled"],
    queryFn: async (): Promise<LinkedInSearchResponse> => {
      if (!searchData) {
        throw new Error("Search data is required");
      }
      return fetchLinkedInSearch(searchData);
    },
    enabled: options?.enabled !== false && !!searchData,
    staleTime: options?.staleTime ?? 10 * 60 * 1000, // 10 minutes
    retry: 2,
    retryDelay: 1000,
  });

  return {
    ...queryResult,
    refetchProfiles: queryResult.refetch,
  };
};

// Utility hook to refetch LinkedIn search when criteria changes
export const useRefetchLinkedInSearch = () => {
  const queryClient = useQueryClient();

  return (searchData: LinkedInSearchRequest) => {
    queryClient.refetchQueries({
      queryKey: getLinkedInSearchQueryKey(searchData),
    });
  };
};

// Legacy mutation hook (keeping for backward compatibility)
export const useLinkedInSearch = () => {
  return useMutation<LinkedInSearchResponse, Error, LinkedInSearchRequest>({
    mutationFn: fetchLinkedInSearch,
    onError: (error: Error) => {
      Sentry.captureException(error, {
        tags: { operation: "linkedin_search" },
        contexts: { linkedin: { error: error.message } },
      });
    },
  });
};
