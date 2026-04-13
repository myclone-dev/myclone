import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { UpdateVoiceSettingsRequest } from "./interface";

/**
 * Update persona voice settings by persona ID
 */
const updateVoiceSettings = async (
  personaId: string,
  data: UpdateVoiceSettingsRequest,
) => {
  const { data: response } = await api.patch(
    `/persona/${personaId}/voice`,
    data,
  );
  return response;
};

/**
 * Hook to update persona voice settings
 * @param personaId - The persona ID to update
 */
export const useUpdateVoiceSettings = (personaId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateVoiceSettingsRequest) =>
      updateVoiceSettings(personaId, data),
    onSuccess: () => {
      // Invalidate persona queries to refetch updated data
      queryClient.invalidateQueries({
        queryKey: ["user-personas"],
      });
      queryClient.invalidateQueries({
        queryKey: ["persona", personaId],
      });
    },
  });
};
