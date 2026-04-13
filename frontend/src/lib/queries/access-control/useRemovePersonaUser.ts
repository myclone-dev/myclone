import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { getPersonaAccessControlUsersQueryKey } from "./usePersonaAccessControlUsers";
import { getAccessControlUsersQueryKey } from "./useAccessControlUsers";

/**
 * Remove user from a specific persona (but keep in global list)
 * DELETE /api/v1/personas/{persona_id}/visitors/{visitor_id}
 */
const removePersonaUser = async ({
  personaId,
  userId,
}: {
  personaId: string;
  userId: string;
}): Promise<void> => {
  await api.delete(`/personas/${personaId}/visitors/${userId}`);
};

/**
 * Mutation hook to remove user from a persona
 * User remains in global access list
 */
export const useRemovePersonaUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: removePersonaUser,
    onSuccess: (_data, variables) => {
      // Invalidate persona's assigned users list
      queryClient.invalidateQueries({
        queryKey: getPersonaAccessControlUsersQueryKey(variables.personaId),
      });
      // Invalidate global list to update assignedPersonaCount
      queryClient.invalidateQueries({
        queryKey: getAccessControlUsersQueryKey(),
      });
    },
  });
};
