/**
 * Check Username Availability Hook
 * Real-time validation for username availability
 */

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { CheckUsernameRequest, CheckUsernameResponse } from "./interface";

const checkUsername = async (
  request: CheckUsernameRequest,
): Promise<CheckUsernameResponse> => {
  const response = await api.post<CheckUsernameResponse>(
    "/claim/check-username",
    request,
  );
  return response.data;
};

export const useCheckUsername = () => {
  return useMutation({
    mutationFn: checkUsername,
  });
};
