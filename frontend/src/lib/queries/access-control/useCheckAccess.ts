import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { CheckAccessResponse } from "./interface";

/**
 * Check if visitor has access to a private persona (via cookie)
 * GET /api/v1/personas/username/{username}/check-access?persona_name={persona_name}
 */
const checkAccess = async ({
  username,
  personaName = "default",
}: {
  username: string;
  personaName?: string;
}): Promise<CheckAccessResponse> => {
  const { data } = await api.get<CheckAccessResponse>(
    `/personas/username/${username}/check-access`,
    {
      params: { persona_name: personaName },
      withCredentials: true, // Include cookies
    },
  );
  return data;
};

/**
 * Query hook to check persona access
 * Uses myclone_visitor httpOnly cookie automatically
 */
export const useCheckAccess = (
  username: string | undefined,
  personaName?: string,
) => {
  return useQuery({
    queryKey: ["check-access", username, personaName || "default"],
    queryFn: () => {
      if (!username) throw new Error("Username required");
      return checkAccess({ username, personaName });
    },
    enabled: !!username,
    staleTime: 30 * 1000, // 30 seconds
    retry: false, // Don't retry on 404 or other errors
  });
};
