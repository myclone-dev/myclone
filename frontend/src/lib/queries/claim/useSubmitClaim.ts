/**
 * Submit Claim Hook
 * Completes the account claim with new credentials
 */

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { SubmitClaimRequest, SubmitClaimResponse } from "./interface";

const submitClaim = async (
  request: SubmitClaimRequest,
): Promise<SubmitClaimResponse> => {
  const response = await api.post<SubmitClaimResponse>(
    "/claim/submit",
    request,
  );
  return response.data;
};

export const useSubmitClaim = () => {
  return useMutation({
    mutationFn: submitClaim,
  });
};
