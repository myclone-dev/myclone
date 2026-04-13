import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { AssignUsersRequest, AssignUsersResponse } from "./interface";
import { getPersonaAccessControlUsersQueryKey } from "./usePersonaAccessControlUsers";
import { getAccessControlUsersQueryKey } from "./useAccessControlUsers";

/**
 * Bulk assign users to a persona
 * POST /api/v1/personas/{persona_id}/visitors
 */
const assignUsers = async ({
  personaId,
  visitorIds,
}: {
  personaId: string;
  visitorIds: string[];
}): Promise<AssignUsersResponse> => {
  const request: AssignUsersRequest = { visitorIds };
  const { data } = await api.post<AssignUsersResponse>(
    `/personas/${personaId}/visitors`,
    request,
  );
  return data;
};

/**
 * Mutation hook to bulk assign users to a persona
 */
export const useAssignUsers = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: assignUsers,
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
