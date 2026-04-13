import { useMutation, useQueryClient } from "@tanstack/react-query";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { api } from "@/lib/api/client";
import type { UpdateProfileRequest, UserProfile } from "./interface";

/**
 * Update user profile (company and role)
 */
const updateProfile = async (
  request: UpdateProfileRequest,
): Promise<UserProfile> => {
  const { data } = await api.patch("/users/me", request);
  return data;
};

/**
 * Mutation hook to update user profile
 */
export const useUpdateProfile = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: UpdateProfileRequest) => {
      trackDashboardOperation("profile_update", "started", {});
      try {
        const result = await updateProfile(request);
        trackDashboardOperation("profile_update", "success", {});
        return result;
      } catch (error) {
        trackDashboardOperation("profile_update", "error", {
          error: error instanceof Error ? error.message : "Unknown error",
        });
        throw error;
      }
    },
    onSuccess: (data) => {
      // Invalidate user queries to refetch with new data
      queryClient.invalidateQueries({ queryKey: ["user", "me"] });
      queryClient.invalidateQueries({ queryKey: ["user", "profile"] });

      // Optimistically update the cache
      queryClient.setQueryData(["user", "me"], data);
      queryClient.setQueryData(["user", "profile"], data);
    },
    onError: () => {
      // Error already tracked via trackDashboardOperation in mutationFn
    },
  });
};
