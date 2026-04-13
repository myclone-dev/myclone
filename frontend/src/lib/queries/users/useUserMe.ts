import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { UserProfile } from "./interface";

export type OnboardingStatus = "NOT_STARTED" | "PARTIAL" | "FULLY_ONBOARDED";

export interface UserMeResponse {
  id: string;
  email: string;
  firstname: string;
  lastname: string;
  fullname: string;
  phone: string | null; // NEW: Phone number field
  avatar: string | null;
  linkedin_url: string | null;
  username: string | null;
  company: string | null;
  role: string | null;
  llm_generated_expertise: string | null;
  email_confirmed: boolean;
  onboarding_status: OnboardingStatus | null;
  account_type: string;
  language: string | null; // UI language preference (en, es, fr, ar)
  created_at: string;
  updated_at: string;
}

/**
 * Fetch current authenticated user data (using axios with Bearer token from localStorage)
 */
const fetchUserMe = async (): Promise<UserMeResponse> => {
  const { data } = await api.get("/users/me");
  return data.data || data;
};

export const useUserMe = (options?: { enabled?: boolean }) => {
  return useQuery<UserMeResponse, Error>({
    queryKey: ["user", "me"],
    queryFn: fetchUserMe,
    enabled: options?.enabled !== false,
    staleTime: 5 * 60 * 1000,
    retry: (failureCount, error) => {
      // Don't retry auth errors
      const httpError = error as { response?: { status?: number } };
      if (
        httpError?.response?.status === 401 ||
        httpError?.response?.status === 403
      )
        return false;
      return failureCount < 3;
    },
  });
};

/**
 * Fetch current authenticated user profile (using axios)
 */
const fetchUserProfile = async (): Promise<UserProfile> => {
  const { data } = await api.get("/users/me");
  return data.data || data;
};

export const getUserProfileQueryKey = () => ["user", "profile"];

/**
 * Query hook to get current user profile (using axios interceptors)
 */
export const useUserProfile = (enabled = true) => {
  return useQuery({
    queryKey: getUserProfileQueryKey(),
    queryFn: fetchUserProfile,
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: false, // Don't retry on auth failures
  });
};
