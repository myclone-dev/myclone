import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  AccessControlToggleRequest,
  AccessControlToggleResponse,
} from "./interface";

/**
 * Toggle persona privacy (public/private)
 * PATCH /api/v1/personas/{persona_id}/access-control
 */
const toggleAccessControl = async ({
  personaId,
  isPrivate,
}: {
  personaId: string;
  isPrivate: boolean;
}): Promise<AccessControlToggleResponse> => {
  const request: AccessControlToggleRequest = { isPrivate };
  const { data } = await api.patch<AccessControlToggleResponse>(
    `/personas/${personaId}/access-control`,
    request,
  );
  return data;
};

/**
 * Mutation hook to toggle persona privacy
 */
export const useAccessControlToggle = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: toggleAccessControl,
    onSuccess: () => {
      // Invalidate persona list to refresh is_private status
      queryClient.invalidateQueries({ queryKey: ["user-personas"] });
      // Invalidate all individual persona queries to update is_private field
      queryClient.invalidateQueries({ queryKey: ["persona"] });
      queryClient.invalidateQueries({ queryKey: ["persona-by-id"] });
      // Invalidate knowledge library queries
      queryClient.invalidateQueries({ queryKey: ["knowledge-library"] });
    },
  });
};
