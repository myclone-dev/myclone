import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Sentry from "@sentry/nextjs";
import { env } from "@/env";
import type {
  ExpertOnboardingSubmitRequest,
  ExpertOnboardingSubmitResponse,
} from "./interface";

// Fetch function for expert onboarding submission
const submitExpertOnboarding = async (
  data: ExpertOnboardingSubmitRequest,
): Promise<ExpertOnboardingSubmitResponse> => {
  const response = await fetch(
    `${env.NEXT_PUBLIC_API_URL}/users/expert/onboarding`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      credentials: "include",
      body: JSON.stringify(data),
    },
  );

  const result: ExpertOnboardingSubmitResponse = await response.json();

  if (!response.ok) {
    const errorMessage = result.message || "Failed to create expert profile";
    throw new Error(errorMessage);
  }

  return result;
};

// Hook for expert onboarding submission
export const useExpertOnboardingSubmit = () => {
  const queryClient = useQueryClient();

  return useMutation<
    ExpertOnboardingSubmitResponse,
    Error,
    ExpertOnboardingSubmitRequest
  >({
    mutationFn: submitExpertOnboarding,
    onSuccess: () => {
      // Invalidate user query to refresh onboarding_status
      // This ensures OnboardingGuard gets the updated status
      queryClient.invalidateQueries({ queryKey: ["user", "me"] });
    },
    onError: (error: Error) => {
      Sentry.captureException(error, {
        tags: { operation: "expert_onboarding" },
        contexts: { onboarding: { error: error.message } },
      });
    },
  });
};
