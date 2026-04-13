import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { UpdateVoiceSettingsRequest } from "./interface";

/**
 * Update voice settings for a single persona
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
 * Update voice settings for all user personas
 * This is called after creating a voice clone to auto-assign it to all personas
 */
const updateAllPersonasVoice = async ({
  personaIds,
  voiceId,
}: {
  personaIds: string[];
  voiceId: string;
}) => {
  // Update all personas in parallel
  const results = await Promise.allSettled(
    personaIds.map((personaId) =>
      updateVoiceSettings(personaId, { voice_id: voiceId }),
    ),
  );

  const successCount = results.filter((r) => r.status === "fulfilled").length;
  const failedCount = results.filter((r) => r.status === "rejected").length;

  return {
    successCount,
    failedCount,
    totalPersonas: personaIds.length,
  };
};

/**
 * Hook to update voice settings for all user personas
 * Used to auto-assign a newly created voice clone to all existing personas
 */
export const useUpdateAllPersonasVoice = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateAllPersonasVoice,
    onSuccess: () => {
      // Invalidate all persona-related queries
      queryClient.invalidateQueries({
        queryKey: ["user-personas"],
      });
      queryClient.invalidateQueries({
        predicate: (query) =>
          Array.isArray(query.queryKey) && query.queryKey[0] === "persona",
      });
    },
  });
};
