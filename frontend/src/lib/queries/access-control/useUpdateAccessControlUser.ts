import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  UpdateAccessControlUserRequest,
  AccessControlUser,
} from "./interface";
import { getAccessControlUsersQueryKey } from "./useAccessControlUsers";

/**
 * Update user in access control list
 * PATCH /api/v1/users/me/visitors/{visitor_id}
 */
const updateAccessControlUser = async ({
  userId,
  data: updateData,
}: {
  userId: string;
  data: UpdateAccessControlUserRequest;
}): Promise<AccessControlUser> => {
  const { data } = await api.patch<AccessControlUser>(
    `/users/me/visitors/${userId}`,
    updateData,
  );
  return data;
};

/**
 * Mutation hook to update user in access control list
 */
export const useUpdateAccessControlUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateAccessControlUser,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: getAccessControlUsersQueryKey(),
      });
    },
  });
};
