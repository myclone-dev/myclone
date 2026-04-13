import { useQuery, type Query } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { PersonaAccessResponse } from "./interface";

/**
 * Query key for persona access validation
 */
export const getPersonaAccessQueryKey = (personaId: string) => [
  "persona-access",
  personaId,
];

/**
 * Check if current user has access to a persona
 * Requires JWT authentication
 */
const checkPersonaAccess = async (
  personaId: string,
): Promise<PersonaAccessResponse> => {
  const response = await api.get<PersonaAccessResponse>(
    `/stripe/personas/${personaId}/access`,
  );
  return response.data;
};

/**
 * Hook to check if current authenticated user has access to a persona
 * Requires JWT authentication
 *
 * Access Logic:
 * 1. "owner" - User owns the persona → access granted
 * 2. "free" - Persona has no monetization → access granted
 * 3. "purchased" - User has active purchase → access granted (may expire)
 * 4. null - No access
 *
 * Usage:
 * ```tsx
 * const { data: access, isLoading } = useCheckPersonaAccess(personaId);
 *
 * if (isLoading) return <LoadingSpinner />;
 * if (!access?.has_access) return <AccessDenied />;
 * return <ChatInterface />;
 * ```
 */
export const useCheckPersonaAccess = (
  personaId: string | null,
  options?: {
    enabled?: boolean;
    refetchInterval?:
      | number
      | false
      | ((
          query: Query<
            PersonaAccessResponse,
            Error,
            PersonaAccessResponse,
            string[]
          >,
        ) => number | false);
  },
) => {
  return useQuery({
    queryKey: personaId
      ? getPersonaAccessQueryKey(personaId)
      : ["persona-access", "disabled"],
    queryFn: () => {
      if (!personaId) throw new Error("Persona ID is required");
      return checkPersonaAccess(personaId);
    },
    enabled: options?.enabled !== false && !!personaId,
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: options?.refetchInterval, // Optional polling
    retry: 1,
  });
};

/**
 * Helper hook for access polling (useful after payment success)
 * Polls every 2 seconds until access is granted or max attempts reached
 *
 * Usage:
 * ```tsx
 * const { data: access, isLoading } = usePersonaAccessPolling(personaId);
 *
 * useEffect(() => {
 *   if (access?.has_access) {
 *     router.push(`/persona/${personaId}/chat`);
 *   }
 * }, [access]);
 * ```
 */
export const usePersonaAccessPolling = (personaId: string | null) => {
  return useCheckPersonaAccess(personaId, {
    refetchInterval: (query) => {
      const data = query.state.data;
      // Stop polling if access is granted or no data
      if (data?.has_access || !data) return false;
      // Continue polling every 2 seconds
      return 2000;
    },
  });
};
