/**
 * Verify Claim Code Hook
 * Checks if claim code is valid and returns user info
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type {
  VerifyClaimCodeRequest,
  VerifyClaimCodeResponse,
} from "./interface";

const verifyClaimCode = async (
  request: VerifyClaimCodeRequest,
): Promise<VerifyClaimCodeResponse> => {
  const response = await api.post<VerifyClaimCodeResponse>(
    "/claim/verify-code",
    request,
  );
  return response.data;
};

export const getVerifyClaimCodeQueryKey = (code: string) => {
  return ["claim-verify", code] as const;
};

export const useVerifyClaimCode = (
  code: string | null,
  options?: { enabled?: boolean },
) => {
  return useQuery({
    queryKey: code
      ? getVerifyClaimCodeQueryKey(code)
      : ["claim-verify", "disabled"],
    queryFn: () => {
      if (!code) throw new Error("Claim code is required");
      return verifyClaimCode({ code });
    },
    enabled: options?.enabled !== false && !!code,
    retry: false, // Don't retry on failure (code might be invalid)
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
