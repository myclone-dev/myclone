"use client";

import { useState } from "react";
import { useUserMe } from "@/lib/queries/users";
import {
  useCreateVoiceClone,
  useVoiceClones,
  getVoiceCloneProvider,
  getVoiceCloneLimit,
} from "@/lib/queries/voice-clone";
import {
  useUserPersonas,
  useUpdateAllPersonasVoice,
} from "@/lib/queries/persona";
import { useUserSubscription } from "@/lib/queries/tier";
import { isFreeTier } from "@/lib/constants/tiers";
import { PageLoader } from "@/components/ui/page-loader";
import { toast } from "sonner";
import { markVoiceCloneComplete } from "@/lib/utils/setupProgress";
import { FreeTierBanner } from "@/components/tier";
import {
  VoiceCloneHeader,
  VoiceCloneInstructions,
  VoiceCloneGetStarted,
  VoiceCloneProcessing,
  VoiceCloneSuccess,
  VoiceCloneRecordingStep,
  VoiceCloneUploadStep,
  VoiceSlotGrid,
} from "@/components/dashboard/voice-clone";
import { isOnboardingInProgress } from "@/lib/utils/onboardingProgress";
import { useTour } from "@/hooks/useTour";
import { TOUR_KEYS } from "@/config/tour-keys";

type Step = "info" | "recording" | "upload" | "processing" | "success";

/**
 * Voice Clone Page
 * Create a personalized voice clone using interactive script recording or file upload
 */
export default function VoiceClonePage() {
  const { data: user, isLoading } = useUserMe();
  const { data: subscription, isLoading: subscriptionLoading } =
    useUserSubscription();
  const { mutate: createVoiceClone, isPending: isCreatingVoiceClone } =
    useCreateVoiceClone();
  const { data: voiceClones } = useVoiceClones(user?.id);
  const { data: personasData } = useUserPersonas(user?.id ?? "");
  const { mutate: updateAllPersonasVoice } = useUpdateAllPersonasVoice();

  const [step, setStep] = useState<Step>("info");
  const [createdVoiceName, setCreatedVoiceName] = useState<string>("");

  // Auto-start voice clone tour with cleanup on unmount
  useTour({
    tourName: "onboarding-voice-clone",
    storageKey: TOUR_KEYS.VOICE_CLONE_TOUR,
    shouldStart: () => isOnboardingInProgress(),
    dependencies: [user, isLoading],
  });

  // Determine voice clone provider based on user's tier
  // Free (0) and Business (2) use Cartesia, Pro (1) and Enterprise (3) use ElevenLabs
  const voiceCloneProvider = getVoiceCloneProvider(subscription?.tier_id ?? 0);

  // Get voice clone limit for user's tier
  const voiceCloneLimit = getVoiceCloneLimit(subscription?.tier_id ?? 0);
  const currentVoiceCloneCount = voiceClones?.length ?? 0;
  const isUnlimited = voiceCloneLimit === -1;
  const hasExistingVoiceClone = currentVoiceCloneCount > 0;

  // Check if user is on free tier
  const isFree = isFreeTier(subscription?.tier_id);
  const hasReachedVoiceLimit =
    !isUnlimited && currentVoiceCloneCount >= voiceCloneLimit;

  if (isLoading || subscriptionLoading || !user) {
    return <PageLoader />;
  }

  const handleRecordingComplete = (files: File[]) => {
    submitVoiceClone(files[0]);
  };

  const handleFileUploadComplete = (
    file: File,
    customName?: string,
    language?: string,
  ) => {
    submitVoiceClone(file, customName, language);
  };

  const submitVoiceClone = (
    file: File,
    customName?: string,
    language: string = "en",
  ) => {
    // Prevent duplicate submissions
    if (isCreatingVoiceClone) {
      return;
    }

    // Use custom name if provided (Business/Enterprise), otherwise generate default
    // Default format: "{User's Full Name} Voice - {Date}"
    let voiceName: string;
    if (customName && customName.trim()) {
      voiceName = customName.trim();
    } else {
      const now = new Date();
      const dateStr = now.toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
      voiceName = `${user.fullname} Voice - ${dateStr}`;
    }

    // Show processing state immediately
    setStep("processing");

    // Use tier-based provider selection:
    // Free tier (0) -> Cartesia
    // Paid tiers (1+) -> Eleven Labs
    createVoiceClone(
      {
        user_id: user.id,
        name: voiceName,
        description: undefined,
        provider: voiceCloneProvider,
        // Eleven Labs specific options
        remove_background_noise: true,
        // Cartesia specific options
        language,
        files: [file],
      },
      {
        onSuccess: (data) => {
          setCreatedVoiceName(data.name);
          setStep("success");
          // Mark voice clone as completed in localStorage
          markVoiceCloneComplete();
          toast.success("Voice clone created!", {
            description: `Your voice clone "${data.name}" is being processed.`,
          });

          // Auto-assign the new voice clone to all existing personas ONLY if this is the first voice clone
          // For Business/Enterprise users with multiple voices, they should manually select voices per persona
          const isFirstVoiceClone = currentVoiceCloneCount === 0;
          if (
            isFirstVoiceClone &&
            personasData?.personas &&
            personasData.personas.length > 0
          ) {
            const personaIds = personasData.personas.map((p) => p.id);
            updateAllPersonasVoice(
              {
                personaIds,
                voiceId: data.voice_id,
              },
              {
                onSuccess: (result) => {
                  if (result.successCount > 0) {
                    toast.success("Voice applied to all personas!", {
                      description: `Your voice clone has been automatically applied to ${result.successCount} persona${result.successCount > 1 ? "s" : ""}.`,
                    });
                  }
                },
                onError: () => {
                  toast.error("Failed to apply voice to some personas", {
                    description:
                      "You can manually assign the voice in Persona Management.",
                  });
                },
              },
            );
          }
        },
        onError: (error) => {
          setStep("info");
          toast.error("Failed to create voice clone", {
            description: error.message,
          });
        },
      },
    );
  };

  // If user already has voice clones, show the slots grid
  if (hasExistingVoiceClone && step === "info") {
    return (
      <div className="max-w-4xl mx-auto py-8 space-y-8 px-4 sm:px-6 lg:px-8">
        <VoiceCloneHeader />

        {/* Free tier banner when at limit */}
        {isFree && hasReachedVoiceLimit && (
          <FreeTierBanner
            title="Voice Clone Limit Reached"
            description={`Free plan allows ${voiceCloneLimit} voice clone${voiceCloneLimit !== 1 ? "s" : ""}. Upgrade to create more.`}
            variant="warning"
            limitInfo={{
              current: currentVoiceCloneCount,
              max: voiceCloneLimit,
              unit: "voice clones",
            }}
          />
        )}

        <VoiceSlotGrid
          voiceClones={voiceClones ?? []}
          voiceCloneLimit={voiceCloneLimit}
          isUnlimited={isUnlimited}
          onRecordClick={() => setStep("recording")}
          onUploadClick={() => setStep("upload")}
        />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto py-8 space-y-8 px-4 sm:px-6 lg:px-8">
      <VoiceCloneHeader />

      {/* Free tier info banner */}
      {isFree && step === "info" && (
        <FreeTierBanner
          title="Free Plan"
          description={`You can create ${voiceCloneLimit} voice clone${voiceCloneLimit !== 1 ? "s" : ""} on the free plan.`}
          variant="compact"
        />
      )}

      {step === "processing" && <VoiceCloneProcessing />}

      {step === "success" && <VoiceCloneSuccess voiceName={createdVoiceName} />}

      {step === "recording" && (
        <VoiceCloneRecordingStep
          userName={user.fullname}
          userExpertise={user.role || undefined}
          onBack={() => setStep("info")}
          onComplete={handleRecordingComplete}
          isSubmitting={isCreatingVoiceClone}
        />
      )}

      {step === "upload" && (
        <VoiceCloneUploadStep
          onBack={() => setStep("info")}
          onComplete={handleFileUploadComplete}
          isSubmitting={isCreatingVoiceClone}
        />
      )}

      {step === "info" && (
        <div id="voice-clone-section" className="space-y-6">
          <VoiceCloneInstructions />
          <VoiceCloneGetStarted
            onRecordClick={() => setStep("recording")}
            onUploadClick={() => setStep("upload")}
          />
        </div>
      )}
    </div>
  );
}
