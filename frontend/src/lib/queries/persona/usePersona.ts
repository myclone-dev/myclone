import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { PersonaDetails, PersonaStatus } from "./interface";

/**
 * Fetch public persona details by username (includes user avatar, location, etc.)
 */
const fetchPersona = async (
  username: string,
  personaName?: string,
): Promise<PersonaDetails> => {
  const params = personaName
    ? `?persona_name=${encodeURIComponent(personaName)}`
    : "";
  const { data } = await api.get(`/expert/${username}/public${params}`);
  return data;
};

export const getPersonaQueryKey = (username: string, personaName?: string) => [
  "persona",
  username,
  personaName || "default",
];

/**
 * Query hook to get persona details
 */
export const usePersona = (
  username: string | undefined,
  personaName?: string,
) => {
  return useQuery({
    queryKey: username
      ? getPersonaQueryKey(username, personaName)
      : ["persona", "disabled"],
    queryFn: () => {
      if (!username) throw new Error("Username required");
      return fetchPersona(username, personaName);
    },
    enabled: !!username,
    staleTime: 0, // Always fetch fresh data
  });
};

/**
 * Fetch persona status (enrichment status, chat enabled, etc.)
 */
const fetchPersonaStatus = async (username: string): Promise<PersonaStatus> => {
  const { data } = await api.get(`/ingestion/expert-status/${username}`);
  return data;
};

export const getPersonaStatusQueryKey = (username: string) => [
  "persona-status",
  username,
];

/**
 * Query hook to get persona status
 */
export const usePersonaStatus = (username: string | undefined) => {
  return useQuery({
    queryKey: username
      ? getPersonaStatusQueryKey(username)
      : ["persona-status", "disabled"],
    queryFn: () => {
      if (!username) throw new Error("Username required");
      return fetchPersonaStatus(username);
    },
    enabled: !!username,
    staleTime: 30 * 1000, // 30 seconds
    refetchInterval: 15 * 1000, // Poll every 15 seconds
  });
};
