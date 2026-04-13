import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { RequestAccessRequest, RequestAccessResponse } from "./interface";

/**
 * Request OTP for persona access (public endpoint)
 * POST /api/v1/personas/username/{username}/request-access?persona_name={persona_name}
 */
const requestAccess = async ({
  username,
  personaName = "default",
  email,
  firstName,
  lastName,
}: {
  username: string;
  personaName?: string;
  email: string;
  firstName?: string;
  lastName?: string;
}): Promise<RequestAccessResponse> => {
  const request: RequestAccessRequest = { email, firstName, lastName };
  const { data } = await api.post<RequestAccessResponse>(
    `/personas/username/${username}/request-access`,
    request,
    {
      params: { persona_name: personaName },
    },
  );
  return data;
};

/**
 * Mutation hook to request OTP for persona access
 */
export const useRequestAccess = () => {
  return useMutation({
    mutationFn: requestAccess,
  });
};
