import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { AccessControlUsersResponse } from "./interface";

/**
 * Fetch all users in the global access control list
 * GET /api/v1/users/me/visitors
 */
const fetchAccessControlUsers =
  async (): Promise<AccessControlUsersResponse> => {
    const { data } =
      await api.get<AccessControlUsersResponse>("/users/me/visitors");
    return data;
  };

export const getAccessControlUsersQueryKey = () => ["access-control-users"];

/**
 * Query hook to get all authorized users (global level)
 */
export const useAccessControlUsers = () => {
  return useQuery({
    queryKey: getAccessControlUsersQueryKey(),
    queryFn: fetchAccessControlUsers,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
