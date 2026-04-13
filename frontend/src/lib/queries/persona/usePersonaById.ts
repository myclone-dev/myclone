import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { PersonaWithKnowledgeResponse } from "./interface";

/**
 * Fetch persona details by ID (for authenticated users editing their own personas)
 * Use with-knowledge endpoint so language and counts are included.
 */
const fetchPersonaById = async (
  personaId: string,
): Promise<PersonaWithKnowledgeResponse> => {
  const { data } = await api.get(`/personas/${personaId}/with-knowledge`);
  return data;
};

export const getPersonaByIdQueryKey = (personaId: string) => [
  "persona-by-id",
  personaId,
];

/**
 * Query hook to get persona details by ID
 * Use this for persona settings/editing pages (authenticated context)
 * For public persona pages, use usePersona() instead
 */
export const usePersonaById = (personaId: string | undefined) => {
  return useQuery({
    queryKey: personaId
      ? getPersonaByIdQueryKey(personaId)
      : ["persona-by-id", "disabled"],
    queryFn: () => {
      if (!personaId) throw new Error("Persona ID required");
      return fetchPersonaById(personaId);
    },
    enabled: !!personaId,
    staleTime: 0, // Always fetch fresh data for settings
  });
};
