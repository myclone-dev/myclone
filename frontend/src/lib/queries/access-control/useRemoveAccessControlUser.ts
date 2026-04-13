import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { getAccessControlUsersQueryKey } from "./useAccessControlUsers";

/**
 * Remove user from global access control list
 * DELETE /api/v1/users/me/visitors/{visitor_id}
 */
const removeAccessControlUser = async (userId: string): Promise<void> => {
  await api.delete(`/users/me/visitors/${userId}`);
};

/**
 * Mutation hook to remove user from access control list
 * This removes them from ALL personas they're assigned to
 */
export const useRemoveAccessControlUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: removeAccessControlUser,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: getAccessControlUsersQueryKey(),
      });
      // Also invalidate persona-specific lists
      queryClient.invalidateQueries({
        queryKey: ["persona-access-control-users"],
      });
    },
  });
};
