import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  KnowledgeLibraryResponse,
  KnowledgeSourceDetailResponse,
  DeleteKnowledgeSourceResponse,
  SourceType,
} from "./interface";

/**
 * Fetch user's knowledge library
 */
const fetchKnowledgeLibrary = async (
  userId: string,
): Promise<KnowledgeLibraryResponse> => {
  const response = await api.get(`/knowledge-library/users/${userId}`);
  return response.data;
};

export const getKnowledgeLibraryQueryKey = (userId: string) => {
  return ["knowledge-library", userId];
};

export const useKnowledgeLibrary = (userId: string) => {
  return useQuery({
    queryKey: getKnowledgeLibraryQueryKey(userId),
    queryFn: () => fetchKnowledgeLibrary(userId),
    enabled: !!userId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Fetch knowledge source detail
 */
const fetchKnowledgeSourceDetail = async (
  sourceType: SourceType,
  sourceId: string,
): Promise<KnowledgeSourceDetailResponse> => {
  const response = await api.get(
    `/knowledge-library/${sourceType}/${sourceId}`,
  );
  return response.data;
};

export const getKnowledgeSourceDetailQueryKey = (
  sourceType: SourceType,
  sourceId: string,
) => {
  return ["knowledge-source-detail", sourceType, sourceId];
};

export const useKnowledgeSourceDetail = (
  sourceType: SourceType,
  sourceId: string,
) => {
  return useQuery({
    queryKey: getKnowledgeSourceDetailQueryKey(sourceType, sourceId),
    queryFn: () => fetchKnowledgeSourceDetail(sourceType, sourceId),
    enabled: !!sourceType && !!sourceId,
  });
};

/**
 * Delete knowledge source
 */
const deleteKnowledgeSource = async (
  sourceType: SourceType,
  sourceId: string,
): Promise<DeleteKnowledgeSourceResponse> => {
  const response = await api.delete(
    `/knowledge-library/${sourceType}/${sourceId}`,
  );
  return response.data;
};

export const useDeleteKnowledgeSource = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      sourceType,
      sourceId,
    }: {
      sourceType: SourceType;
      sourceId: string;
    }) => deleteKnowledgeSource(sourceType, sourceId),
    onSuccess: () => {
      // Invalidate knowledge library queries
      queryClient.invalidateQueries({
        queryKey: ["knowledge-library"],
      });
      // Invalidate persona queries (since they might be affected)
      queryClient.invalidateQueries({
        queryKey: ["personas"],
      });
      queryClient.invalidateQueries({
        queryKey: ["persona-knowledge"],
      });
    },
  });
};
