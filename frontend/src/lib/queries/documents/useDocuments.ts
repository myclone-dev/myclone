import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { DocumentListResponse } from "./interface";

/**
 * Fetch documents for a user
 */
const fetchDocuments = async (
  userId: string,
): Promise<DocumentListResponse> => {
  const response = await api.get<DocumentListResponse>(
    `/api/v1/documents/${userId}`,
  );
  return response.data;
};

/**
 * Hook to fetch user documents
 */
export const useDocuments = (userId?: string) => {
  return useQuery({
    queryKey: ["documents", userId],
    queryFn: () => {
      if (!userId) throw new Error("User ID is required");
      return fetchDocuments(userId);
    },
    enabled: !!userId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
