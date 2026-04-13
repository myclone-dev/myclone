import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { toast } from "sonner";
import { AxiosError } from "axios";
import {
  isPersonaLimitError,
  type PersonaLimitExceededError,
} from "@/lib/queries/tier/interface";
import type {
  PersonaKnowledgeResponse,
  AvailableKnowledgeSourcesResponse,
  AttachKnowledgeRequest,
  PersonaCreateWithKnowledge,
  PersonaWithKnowledgeResponse,
  UserPersonasResponse,
} from "./interface";

/**
 * Get persona's knowledge sources
 */
const fetchPersonaKnowledge = async (
  personaId: string,
): Promise<PersonaKnowledgeResponse> => {
  const response = await api.get(`/personas/${personaId}/knowledge-sources`);
  return response.data;
};

export const getPersonaKnowledgeQueryKey = (personaId: string) => {
  return ["persona-knowledge", personaId];
};

export const usePersonaKnowledge = (personaId: string) => {
  return useQuery({
    queryKey: getPersonaKnowledgeQueryKey(personaId),
    queryFn: () => fetchPersonaKnowledge(personaId),
    enabled: !!personaId,
  });
};

/**
 * Get available knowledge sources for persona
 */
const fetchAvailableKnowledgeSources = async (
  personaId: string,
): Promise<AvailableKnowledgeSourcesResponse> => {
  const response = await api.get(
    `/personas/${personaId}/knowledge-sources/available`,
  );
  return response.data;
};

export const getAvailableKnowledgeSourcesQueryKey = (personaId: string) => {
  return ["available-knowledge-sources", personaId];
};

export const useAvailableKnowledgeSources = (personaId: string) => {
  return useQuery({
    queryKey: getAvailableKnowledgeSourcesQueryKey(personaId),
    queryFn: () => fetchAvailableKnowledgeSources(personaId),
    enabled: !!personaId,
  });
};

/**
 * Attach knowledge sources to persona
 */
const attachKnowledgeSources = async (
  personaId: string,
  request: AttachKnowledgeRequest,
): Promise<PersonaKnowledgeResponse> => {
  const response = await api.post(
    `/personas/${personaId}/knowledge-sources`,
    request,
  );
  return response.data;
};

export const useAttachKnowledgeSources = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      personaId,
      request,
    }: {
      personaId: string;
      request: AttachKnowledgeRequest;
    }) => attachKnowledgeSources(personaId, request),
    onSuccess: (_, variables) => {
      // Invalidate persona knowledge queries
      queryClient.invalidateQueries({
        queryKey: ["persona-knowledge", variables.personaId],
      });
      queryClient.invalidateQueries({
        queryKey: ["available-knowledge-sources", variables.personaId],
      });
      // Invalidate all user-personas queries (to update knowledge_sources_count)
      queryClient.invalidateQueries({
        predicate: (query) =>
          Array.isArray(query.queryKey) &&
          query.queryKey[0] === "user-personas",
      });
      // Invalidate knowledge library (used_by_personas_count might change)
      queryClient.invalidateQueries({
        queryKey: ["knowledge-library"],
      });
    },
  });
};

/**
 * Detach knowledge source from persona
 */
const detachKnowledgeSource = async (
  personaId: string,
  sourceRecordId: string,
): Promise<{ success: boolean; message: string }> => {
  const response = await api.delete(
    `/personas/${personaId}/knowledge-sources/${sourceRecordId}`,
  );
  return response.data;
};

export const useDetachKnowledgeSource = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      personaId,
      sourceRecordId,
    }: {
      personaId: string;
      sourceRecordId: string;
    }) => detachKnowledgeSource(personaId, sourceRecordId),
    onSuccess: (_, variables) => {
      // Invalidate persona knowledge queries
      queryClient.invalidateQueries({
        queryKey: ["persona-knowledge", variables.personaId],
      });
      queryClient.invalidateQueries({
        queryKey: ["available-knowledge-sources", variables.personaId],
      });
      // Invalidate all user-personas queries (to update knowledge_sources_count)
      queryClient.invalidateQueries({
        predicate: (query) =>
          Array.isArray(query.queryKey) &&
          query.queryKey[0] === "user-personas",
      });
      // Invalidate knowledge library
      queryClient.invalidateQueries({
        queryKey: ["knowledge-library"],
      });
    },
  });
};

/**
 * Toggle knowledge source enable/disable
 */
const toggleKnowledgeSource = async (
  personaId: string,
  sourceRecordId: string,
): Promise<{ success: boolean; message: string }> => {
  const response = await api.patch(
    `/personas/${personaId}/knowledge-sources/${sourceRecordId}/toggle`,
  );
  return response.data;
};

export const useToggleKnowledgeSource = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      personaId,
      sourceRecordId,
    }: {
      personaId: string;
      sourceRecordId: string;
    }) => toggleKnowledgeSource(personaId, sourceRecordId),
    onSuccess: (_, variables) => {
      // Invalidate persona knowledge queries
      queryClient.invalidateQueries({
        queryKey: ["persona-knowledge", variables.personaId],
      });
      queryClient.invalidateQueries({
        queryKey: ["available-knowledge-sources", variables.personaId],
      });
    },
  });
};

/**
 * Create persona with knowledge
 */
const createPersonaWithKnowledge = async (
  userId: string,
  data: PersonaCreateWithKnowledge,
): Promise<PersonaWithKnowledgeResponse> => {
  const response = await api.post(
    `/personas/with-knowledge?user_id=${userId}`,
    data,
  );
  return response.data;
};

export const useCreatePersonaWithKnowledge = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      userId,
      data,
    }: {
      userId: string;
      data: PersonaCreateWithKnowledge;
    }) => createPersonaWithKnowledge(userId, data),
    onSuccess: () => {
      // Invalidate all user-personas queries (including with userId)
      queryClient.invalidateQueries({
        predicate: (query) =>
          Array.isArray(query.queryKey) &&
          query.queryKey[0] === "user-personas",
      });
      // Invalidate knowledge library (used_by_personas_count might change)
      queryClient.invalidateQueries({
        queryKey: ["knowledge-library"],
      });
      // Invalidate tier usage to refresh persona count
      queryClient.invalidateQueries({
        queryKey: ["user-usage"],
      });
    },
    onError: (error: Error) => {
      // Handle persona limit exceeded error at hook level
      const axiosError = error as AxiosError<{
        detail: string | PersonaLimitExceededError;
      }>;
      const errorDetail = axiosError?.response?.data?.detail;

      if (isPersonaLimitError(errorDetail)) {
        toast.error("Persona limit reached", {
          description: `You've reached your limit of ${errorDetail.max_personas} personas on the ${errorDetail.tier} plan. Upgrade to create more personas.`,
          action: {
            label: "View Plans",
            onClick: () => window.open("/pricing", "_blank"),
          },
        });
        // Re-throw to allow component to handle state reset
        throw error;
      }
      // Other errors are not handled here - let component handle them
    },
  });
};

/**
 * Update persona with knowledge
 */
const updatePersonaWithKnowledge = async (
  personaId: string,
  data: Partial<PersonaCreateWithKnowledge>,
): Promise<PersonaWithKnowledgeResponse> => {
  const response = await api.patch(
    `/personas/${personaId}/with-knowledge`,
    data,
  );
  return response.data;
};

export const useUpdatePersonaWithKnowledge = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      personaId,
      data,
    }: {
      personaId: string;
      data: Partial<PersonaCreateWithKnowledge>;
    }) => updatePersonaWithKnowledge(personaId, data),
    onSuccess: (response, variables) => {
      // Invalidate persona queries
      queryClient.invalidateQueries({
        queryKey: ["persona", variables.personaId],
      });
      queryClient.invalidateQueries({
        queryKey: ["persona-knowledge", variables.personaId],
      });
      // Invalidate all user-personas queries (including with userId)
      queryClient.invalidateQueries({
        predicate: (query) =>
          Array.isArray(query.queryKey) &&
          query.queryKey[0] === "user-personas",
      });
      // Invalidate knowledge library
      queryClient.invalidateQueries({
        queryKey: ["knowledge-library"],
      });
    },
  });
};

/**
 * List user's personas
 */
const fetchUserPersonas = async (
  userId: string,
): Promise<UserPersonasResponse> => {
  const response = await api.get(`/personas/users/${userId}/personas`);
  return response.data;
};

export const getUserPersonasQueryKey = (userId: string) => {
  return ["user-personas", userId];
};

export const useUserPersonas = (userId: string) => {
  return useQuery({
    queryKey: getUserPersonasQueryKey(userId),
    queryFn: () => fetchUserPersonas(userId),
    enabled: !!userId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
