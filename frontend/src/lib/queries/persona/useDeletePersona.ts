import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";

interface DeletePersonaResponse {
  success: boolean;
  message: string;
  persona_id: string;
}

/**
 * Delete persona (soft delete)
 * DELETE /api/v1/personas/{persona_id}
 */
const deletePersona = async (
  personaId: string,
): Promise<DeletePersonaResponse> => {
  const { data } = await api.delete<DeletePersonaResponse>(
    `/personas/${personaId}`,
  );
  return data;
};

/**
 * Mutation hook to delete a persona
 * Soft deletes by setting is_active=false
 */
export const useDeletePersona = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (personaId: string) => {
      trackDashboardOperation("persona_delete", "started", {
        personaId,
      });
      try {
        const result = await deletePersona(personaId);
        trackDashboardOperation("persona_delete", "success", {
          personaId,
        });
        return result;
      } catch (error) {
        trackDashboardOperation("persona_delete", "error", {
          personaId,
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: () => {
      // Invalidate personas list to remove deleted persona
      queryClient.invalidateQueries({
        queryKey: ["user-personas"],
      });
      // Invalidate knowledge library (used_by_personas_count might change)
      queryClient.invalidateQueries({
        queryKey: ["knowledge-library"],
      });
    },
  });
};
