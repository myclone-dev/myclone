"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { toast } from "sonner";
import * as Sentry from "@sentry/nextjs";
import { MessageSquare, Mic, Sparkles, Globe } from "lucide-react";
import { trackDashboardOperation } from "@/lib/monitoring/sentry";
import { ProfileAndDataSourcesStep } from "./steps/ProfileAndDataSourcesStep";
import { useExpertOnboardingSubmit } from "@/lib/queries/expert";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { useCreateAdvancedPrompt } from "@/lib/queries/prompt";

const FEATURES = [
  {
    icon: MessageSquare,
    title: "Text Chat",
    description: "Engage visitors with AI-powered conversations",
  },
  {
    icon: Mic,
    title: "Voice Chat",
    description: "Natural voice interactions with your clone",
  },
  {
    icon: Sparkles,
    title: "AI Trained on You",
    description: "Personalized responses based on your knowledge",
  },
  {
    icon: Globe,
    title: "Embed Anywhere",
    description: "Add your clone to any website in minutes",
  },
];

export default function ExpertOnboarding() {
  const router = useRouter();

  // Get current authenticated user
  const {
    data: currentUser,
    isLoading: isLoadingUser,
    refetch: refetchUser,
  } = useUserMe();

  // Expert onboarding submission mutation
  const submitMutation = useExpertOnboardingSubmit();

  // Advanced prompt creation mutation
  const createAdvancedPromptMutation = useCreateAdvancedPrompt();

  // Redirect to signup if not authenticated
  useEffect(() => {
    if (!isLoadingUser && !currentUser) {
      toast.error("Please sign in with LinkedIn to continue");
      router.push("/signup");
    }
  }, [currentUser, isLoadingUser, router]);

  const handleSubmit = async (formData: { username: string }) => {
    trackDashboardOperation("expert_onboarding", "started", {
      username: formData.username,
    });

    try {
      const submitData: {
        username: string;
        userId?: string;
      } = {
        username: formData.username,
        userId: currentUser?.id,
      };

      const result = await submitMutation.mutateAsync(submitData);

      if (result.success) {
        trackDashboardOperation("expert_onboarding", "success", {
          username: formData.username,
          personaId: result.persona_id,
        });

        toast.success("Expert profile created successfully!");

        // Generate AI prompt (async, non-blocking)
        // This will run in the background after onboarding completes
        if (result.persona_id && result.user_id) {
          createAdvancedPromptMutation.mutate(
            {
              persona_id: result.persona_id,
              user_id: result.user_id,
              db_update: true,
              sample_questions: [
                "How did you get started in your field?",
                "What's your approach to problem-solving?",
                "What advice would you give someone starting out?",
              ],
              template: "basic",
              template_expertise: "general",
              platform: "openai",
              chat_objective: "",
              response_structure: "",
              role: "",
              expertise: "",
              description: "",
            },
            {
              onSuccess: () => {
                // Advanced prompt generated successfully
                // No user notification needed - this is a background task
              },
              onError: (promptError) => {
                Sentry.captureException(promptError, {
                  tags: { operation: "advanced_prompt_generation" },
                  contexts: {
                    onboarding: {
                      personaId: result.persona_id,
                      userId: result.user_id,
                    },
                  },
                });
                console.error(
                  "Failed to generate advanced prompt:",
                  promptError,
                );
                // Don't show error to user - this is a background task
              },
            },
          );
        }

        // Refetch user data to update onboarding status
        await refetchUser();

        // Redirect to dashboard (user query cache is now updated)
        router.push("/dashboard");
      } else {
        trackDashboardOperation("expert_onboarding", "error", {
          username: formData.username,
          error: "Profile creation returned unsuccessful",
        });
        toast.error("Failed to create expert profile");
      }
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Failed to create profile";

      trackDashboardOperation("expert_onboarding", "error", {
        username: formData.username,
        error: errorMessage,
      });

      toast.error(errorMessage);
    }
  };

  // Show loading while checking authentication
  if (isLoadingUser) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
        <div className="text-center">
          <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-4 border-gray-200 border-t-primary sm:h-16 sm:w-16"></div>
          <p className="text-sm text-gray-600 sm:text-base">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="container mx-auto px-4 py-8 sm:py-12 md:py-16">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <Image
            src="/myclone-logo.svg"
            alt="MyClone"
            width={140}
            height={36}
            priority
          />
        </div>

        <div className="mx-auto max-w-4xl">
          <div className="grid gap-8 lg:grid-cols-2 lg:gap-12 items-center">
            {/* Left side - Features */}
            <div className="hidden lg:block">
              <h1 className="text-3xl font-bold text-gray-900 mb-3">
                Welcome to MyClone
              </h1>
              <p className="text-lg text-gray-600 mb-8">
                Create your AI-powered digital twin in just a few steps. Your
                clone will represent you 24/7.
              </p>

              <div className="space-y-4">
                {FEATURES.map((feature) => (
                  <div
                    key={feature.title}
                    className="flex items-start gap-4 p-4 rounded-xl bg-white/60 border border-gray-100"
                  >
                    <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-yellow-bright/20 flex items-center justify-center">
                      <feature.icon className="w-5 h-5 text-yellow-700" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">
                        {feature.title}
                      </h3>
                      <p className="text-sm text-gray-600">
                        {feature.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right side - Form */}
            <div>
              <div className="rounded-2xl bg-white p-6 shadow-lg border border-gray-200 sm:p-8">
                {/* Mobile welcome text */}
                <div className="lg:hidden text-center mb-6">
                  <h1 className="text-2xl font-bold text-gray-900 mb-2">
                    Welcome to MyClone
                  </h1>
                  <p className="text-gray-600">
                    Create your AI-powered digital twin
                  </p>
                </div>

                <ProfileAndDataSourcesStep
                  onSubmit={handleSubmit}
                  isSubmitting={submitMutation.isPending}
                />

                {/* Mobile features - compact */}
                <div className="lg:hidden mt-8 pt-6 border-t border-gray-100">
                  <p className="text-xs text-gray-500 text-center mb-4">
                    What you&apos;ll get
                  </p>
                  <div className="grid grid-cols-2 gap-3">
                    {FEATURES.map((feature) => (
                      <div
                        key={feature.title}
                        className="flex items-center gap-2 text-sm text-gray-600"
                      >
                        <feature.icon className="w-4 h-4 text-yellow-600" />
                        <span>{feature.title}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Trust indicators */}
              <p className="text-center text-xs text-gray-500 mt-4">
                You can add data sources and customize your clone after setup
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
