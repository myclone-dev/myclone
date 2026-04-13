import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { VerifyAccessRequest, VerifyAccessResponse } from "./interface";

/**
 * Verify OTP and get access cookie (public endpoint)
 * POST /api/v1/personas/username/{username}/verify-access?persona_name={persona_name}
 */
const verifyAccess = async ({
  username,
  personaName = "default",
  email,
  otpCode,
  firstName,
  lastName,
}: {
  username: string;
  personaName?: string;
  email: string;
  otpCode: string;
  firstName?: string;
  lastName?: string;
}): Promise<VerifyAccessResponse> => {
  const request: VerifyAccessRequest = { email, otpCode, firstName, lastName };
  const { data } = await api.post<VerifyAccessResponse>(
    `/personas/username/${username}/verify-access`,
    request,
    {
      params: { persona_name: personaName },
    },
  );
  return data;
};

/**
 * Mutation hook to verify OTP and get access
 * On success, backend sets httpOnly cookie (myclone_visitor)
 */
export const useVerifyAccess = () => {
  return useMutation({
    mutationFn: verifyAccess,
  });
};
