import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { PersonaAccessControlUsersResponse } from "./interface";

/**
 * Fetch users assigned to a specific persona
 * GET /api/v1/personas/{persona_id}/visitors
 */
const fetchPersonaAccessControlUsers = async (
  personaId: string,
): Promise<PersonaAccessControlUsersResponse> => {
  const { data } = await api.get<PersonaAccessControlUsersResponse>(
    `/personas/${personaId}/visitors`,
  );
  return data;
};

export const getPersonaAccessControlUsersQueryKey = (personaId: string) => [
  "persona-access-control-users",
  personaId,
];

/**
 * Query hook to get users assigned to a persona
 */
export const usePersonaAccessControlUsers = (personaId: string | undefined) => {
  return useQuery({
    queryKey: personaId
      ? getPersonaAccessControlUsersQueryKey(personaId)
      : ["persona-access-control-users", "disabled"],
    queryFn: () => {
      if (!personaId) throw new Error("Persona ID required");
      return fetchPersonaAccessControlUsers(personaId);
    },
    enabled: !!personaId,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
