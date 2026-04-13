import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { PersonaNameAvailabilityResponse } from "./interface";

/**
 * Check if a persona name is available
 * Validates the name against backend rules (length, reserved words, duplicates, etc.)
 */
const checkPersonaNameAvailability = async (
  personaName: string,
): Promise<PersonaNameAvailabilityResponse> => {
  const { data } = await api.get<PersonaNameAvailabilityResponse>(
    `/personas/check-persona-name`,
    {
      params: {
        persona_name: personaName,
      },
    },
  );
  return data;
};

/**
 * Query key generator for cache management
 */
export const getPersonaNameCheckQueryKey = (personaName: string) => {
  return ["persona-name-check", personaName];
};

/**
 * Hook to check persona name availability
 * Only runs when personaName is provided and has at least 3 characters
 */
export function useCheckPersonaName(
  personaName: string | null,
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: personaName
      ? getPersonaNameCheckQueryKey(personaName)
      : ["persona-name-check", "disabled"],
    queryFn: () => {
      if (!personaName) {
        throw new Error("Persona name is required");
      }
      return checkPersonaNameAvailability(personaName);
    },
    enabled:
      options?.enabled !== false &&
      !!personaName &&
      personaName.trim().length >= 3,
    staleTime: 30 * 1000, // 30 seconds - short cache since availability can change
    retry: false, // Don't retry on validation errors
  });
}
