import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  AddAccessControlUserRequest,
  AccessControlUser,
} from "./interface";
import { getAccessControlUsersQueryKey } from "./useAccessControlUsers";

/**
 * Add user to global access control list
 * POST /api/v1/users/me/visitors
 */
const addAccessControlUser = async (
  request: AddAccessControlUserRequest,
): Promise<AccessControlUser> => {
  const { data } = await api.post<AccessControlUser>(
    "/users/me/visitors",
    request,
  );
  return data;
};

/**
 * Mutation hook to add user to access control list
 */
export const useAddAccessControlUser = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: addAccessControlUser,
    onSuccess: () => {
      // Invalidate list to refetch
      queryClient.invalidateQueries({
        queryKey: getAccessControlUsersQueryKey(),
      });
    },
  });
};
