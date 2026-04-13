"use client";

import { useState, useMemo } from "react";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import {
  useUserPersonas,
  useCreatePersonaWithKnowledge,
} from "@/lib/queries/persona";
import { useTierLimitCheck } from "@/lib/queries/tier/useTierLimitCheck";
import { CreatePersonaDialog } from "@/components/dashboard/personas/CreatePersonaDialog";
import { PersonaCard } from "@/components/dashboard/personas/PersonaCard";
import { KnowledgeToggleDialog } from "@/components/dashboard/personas/KnowledgeToggleDialog";
import { PersonaAccessControlDialog } from "@/components/dashboard/personas/PersonaAccessControlDialog";
import { DeletePersonaDialog } from "@/components/dashboard/personas/DeletePersonaDialog";
import { PersonaCountBadge } from "@/components/dashboard/personas/PersonaCountBadge";
import { Users, Sparkles, Crown } from "lucide-react";
import { toast } from "sonner";
import { parseApiError } from "@/lib/utils/apiError";
import {
  useCreateAdvancedPrompt,
  useGenerateSuggestedQuestions,
  type PersonaPromptFields,
} from "@/lib/queries/prompt";
import { useNextStep } from "nextstepjs";
import {
  isOnboardingInProgress,
  getCurrentOnboardingStep,
  markPersonaStepComplete,
  completeOnboarding,
} from "@/lib/utils/onboardingProgress";
import { useTour } from "@/hooks/useTour";
import { TOUR_KEYS } from "@/config/tour-keys";

/**
 * Persona Management Page
 * Create and manage multiple AI personas with different knowledge bases
 */
export default function PersonasPage() {
  const { data: user, isLoading: userLoading } = useUserMe();
  const { data: personasData, isLoading: personasLoading } = useUserPersonas(
    user?.id || "",
  );
  const createPersonaMutation = useCreatePersonaWithKnowledge();
  const createAdvancedPromptMutation = useCreateAdvancedPrompt();
  const generateQuestionsMutation = useGenerateSuggestedQuestions();
  const { startNextStep } = useNextStep();
  const {
    canCreatePersona,
    isLoading: tierLoading,
    usage: tierUsage,
  } = useTierLimitCheck();

  // Auto-start personas tour with cleanup on unmount
  useTour({
    tourName: "onboarding-persona",
    storageKey: TOUR_KEYS.PERSONAS_TOUR,
    shouldStart: () => isOnboardingInProgress(),
    dependencies: [user, userLoading],
  });

  // Get persona limit info - memoized to avoid recalculation on every render
  const personaLimitCheck = useMemo(
    () => canCreatePersona(),
    [canCreatePersona],
  );

  const [selectedPersonaId, setSelectedPersonaId] = useState<string | null>(
    null,
  );
  const [knowledgeDialogOpen, setKnowledgeDialogOpen] = useState(false);
  const [accessControlDialogOpen, setAccessControlDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // Track which persona is currently being created (by ID) for loading animation
  // When user opens PersonaSettingsDialog for this persona, show animation until creation completes
  const [creatingPersonaId, setCreatingPersonaId] = useState<string | null>(
    null,
  );

  const handleCreatePersona = async (
    newPersona: {
      personaName: string; // Identifier (username)
      name: string; // Display name
      role: string;
      expertise: string;
      description: string;
      voice_id?: string;
      knowledgeSources: Array<{
        source_type:
          | "linkedin"
          | "twitter"
          | "website"
          | "document"
          | "youtube";
        source_record_id: string;
      }>;
    },
    promptFields?: PersonaPromptFields,
  ) => {
    if (!user?.id) {
      toast.error("User not found");
      return;
    }

    const payload = {
      userId: user.id,
      data: {
        persona_name: newPersona.personaName, // Use the identifier directly
        name: newPersona.name, // Use the display name
        role: newPersona.role,
        expertise: newPersona.expertise,
        description: newPersona.description,
        voice_id: newPersona.voice_id,
        knowledge_sources: newPersona.knowledgeSources,
      },
    };

    try {
      // Step 1: Create persona
      const data = await createPersonaMutation.mutateAsync(payload);

      // Track this persona ID as "being created" - if user opens settings dialog
      // before all steps complete, show loading animation
      if (data.id) {
        setCreatingPersonaId(data.id);
      }

      // Step 2: Create advanced prompt using the new endpoint
      if (data.id) {
        try {
          // Create advanced prompt with all required fields
          await createAdvancedPromptMutation.mutateAsync({
            persona_id: data.id,
            user_id: user.id,
            db_update: true,
            sample_questions: ["string"], // Keep as is per requirement
            template: "basic",
            template_expertise: "general",
            platform: "openai",
            chat_objective: promptFields?.chat_objective || "",
            response_structure: promptFields?.response_structure
              ? JSON.stringify(promptFields.response_structure)
              : "",
            role: newPersona.role,
            expertise: newPersona.expertise,
            description: newPersona.description,
            target_audience: promptFields?.target_audience || "",
          });

          // Step 3: Generate suggested questions
          try {
            const questionsResult = await generateQuestionsMutation.mutateAsync(
              {
                personaId: data.id,
                numQuestions: 5,
                forceRegenerate: false,
              },
            );

            toast.success(
              `Persona "${newPersona.name}" created successfully!`,
              {
                description: `${newPersona.knowledgeSources.length} knowledge sources enabled. ${questionsResult.suggested_questions.length} suggested questions generated.`,
              },
            );
          } catch (questionsError) {
            console.error("Failed to generate questions:", questionsError);

            toast.success(
              `Persona "${newPersona.name}" created successfully!`,
              {
                description: `${newPersona.knowledgeSources.length} knowledge sources enabled. Questions generation will be retried later.`,
              },
            );
          }
        } catch (promptError) {
          console.error("Failed to update prompt fields:", promptError);

          toast.success(`Persona "${newPersona.name}" created!`, {
            description:
              "Persona created but some configuration failed. You can update it later.",
          });
        }
      } else {
        toast.success(`Persona "${newPersona.name}" created successfully!`, {
          description: `${newPersona.knowledgeSources.length} knowledge sources enabled.`,
        });
      }

      // If in onboarding, mark complete and show completion tour
      if (
        isOnboardingInProgress() &&
        getCurrentOnboardingStep() === "persona"
      ) {
        markPersonaStepComplete();
        completeOnboarding();

        // Show onboarding completion tour after a brief delay
        setTimeout(() => {
          startNextStep("onboarding-complete");
        }, 1500);
      }

      // Creation successful - clear creating state so PersonaSettingsDialog shows form
      setCreatingPersonaId(null);
    } catch (error: unknown) {
      console.error("Failed to create persona:", error);

      // Reset creation state on error
      setCreatingPersonaId(null);

      // Note: Persona limit exceeded error (403 with PERSONA_LIMIT_EXCEEDED) is
      // handled at the hook level in useCreatePersonaWithKnowledge

      const errorMessage = parseApiError(error);

      // Handle duplicate persona name error
      if (
        errorMessage.includes("duplicate key") ||
        errorMessage.includes("already exists")
      ) {
        toast.error("Failed to create persona", {
          description: `A persona with the name "${newPersona.name}" already exists. Please choose a different name.`,
        });
        throw error; // Re-throw so dialog knows creation failed
      }

      // Only show generic error if it's not a persona limit error
      // (which is already handled by the hook)
      if (!errorMessage.includes("Persona limit")) {
        toast.error("Failed to create persona", {
          description: errorMessage,
        });
      }
      throw error; // Re-throw so dialog knows creation failed
    }
  };

  const handleManageKnowledge = (personaId: string) => {
    setSelectedPersonaId(personaId);
    setKnowledgeDialogOpen(true);
  };

  const handleManageAccessControl = (personaId: string) => {
    setSelectedPersonaId(personaId);
    setAccessControlDialogOpen(true);
  };

  const handleDeletePersona = (personaId: string) => {
    setSelectedPersonaId(personaId);
    setDeleteDialogOpen(true);
  };

  // Show loading skeleton only on initial load to prevent jarring UX on refetches
  const isInitialLoading =
    (userLoading && !user) ||
    (personasLoading && !personasData) ||
    (tierLoading && !tierUsage);

  if (isInitialLoading) {
    return (
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div className="space-y-6 animate-pulse">
          <div className="h-8 w-48 bg-muted rounded" />
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-96 bg-muted rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  // Sort personas by created_at to maintain consistent order
  const personas = (personasData?.personas || []).sort((a, b) => {
    return new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
  });
  const selectedPersona = personas.find((p) => p.id === selectedPersonaId);

  return (
    <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2 flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight flex items-center gap-2 sm:gap-3">
              <Users className="size-6 sm:size-8 text-ai-brown shrink-0" />
              <span className="wrap-break-word">Persona Management</span>
            </h1>
            {/* Persona usage badge */}
            <PersonaCountBadge
              current={personaLimitCheck.current}
              max={personaLimitCheck.limit}
              isAtLimit={!personaLimitCheck.allowed}
            />
          </div>
          <p className="text-sm sm:text-base text-muted-foreground leading-relaxed">
            Create different personas focusing on various aspects of your
            expertise. Each persona uses selected parts of your knowledge.
          </p>
        </div>
        <div id="create-persona-button" className="shrink-0">
          <CreatePersonaDialog
            onCreatePersona={handleCreatePersona}
            canCreate={personaLimitCheck.allowed}
            limitReason={personaLimitCheck.reason}
            currentCount={personaLimitCheck.current}
            maxPersonas={personaLimitCheck.limit}
          />
        </div>
      </div>

      {/* Persona Limit Warning */}
      {!personaLimitCheck.allowed && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-yellow-50 border border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800">
          <Crown className="size-5 text-yellow-600 dark:text-yellow-400 shrink-0" />
          <div className="flex-1">
            <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
              Persona limit reached
            </p>
            <p className="text-xs text-yellow-700 dark:text-yellow-300">
              You&apos;ve used all {personaLimitCheck.limit} personas on your
              current plan. Upgrade to create more.
            </p>
          </div>
          <a
            href="/pricing"
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 text-sm font-medium text-yellow-800 dark:text-yellow-200 hover:underline"
          >
            View Plans
          </a>
        </div>
      )}

      {/* Personas Grid */}
      {personas.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-center">
          <div className="mb-4 flex size-20 items-center justify-center rounded-full bg-orange-100">
            <Sparkles className="size-10 text-ai-brown" />
          </div>
          <h3 className="mb-2 text-lg font-semibold">No personas yet</h3>
          <p className="mb-6 text-sm text-muted-foreground max-w-md">
            Create your first persona to focus on a specific aspect of your
            expertise. For example: &quot;Tech Advisor&quot; for technical
            questions or &quot;Career Mentor&quot; for career guidance.
          </p>
          <CreatePersonaDialog
            onCreatePersona={handleCreatePersona}
            canCreate={personaLimitCheck.allowed}
            limitReason={personaLimitCheck.reason}
            currentCount={personaLimitCheck.current}
            maxPersonas={personaLimitCheck.limit}
          />
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {personas.map((persona) => (
            <PersonaCard
              key={persona.id}
              persona={{
                id: persona.id,
                persona_name: persona.persona_name,
                name: persona.name,
                role: persona.role || "AI Assistant",
                expertise: persona.expertise,
                description: persona.description,
                slug: persona.persona_name,
                voice_id: persona.voice_id,
                greeting_message: persona.greeting_message,
                knowledge_sources_count: persona.knowledge_sources_count,
                conversations_count: 0, // Fetched separately in PersonaCard component via usePersonaConversationCount
                created_at: persona.created_at,
                is_private: persona.is_private,
                suggested_questions: [], // Will be fetched from PersonaWithKnowledgeResponse once backend updated
                email_capture_enabled: persona.email_capture_enabled,
                email_capture_message_threshold:
                  persona.email_capture_message_threshold,
                email_capture_require_fullname:
                  persona.email_capture_require_fullname,
                email_capture_require_phone:
                  persona.email_capture_require_phone,
                calendar_enabled: persona.calendar_enabled,
                calendar_url: persona.calendar_url ?? undefined,
                calendar_display_name:
                  persona.calendar_display_name ?? undefined,
              }}
              username={user.username || ""}
              onManageKnowledge={handleManageKnowledge}
              onManageAccessControl={handleManageAccessControl}
              onDelete={handleDeletePersona}
              isCreating={creatingPersonaId === persona.id}
            />
          ))}
        </div>
      )}

      {/* Info Card */}
      <div className="rounded-lg bg-muted/50 p-6 space-y-3">
        <h3 className="font-semibold flex items-center gap-2">
          <Sparkles className="size-5 text-ai-brown" />
          How Persona Management Works
        </h3>
        <ul className="text-sm text-muted-foreground space-y-2">
          <li>
            • <strong>Different Focus Areas:</strong> Each persona highlights a
            different aspect of YOUR expertise (tech, career, product, etc.)
          </li>
          <li>
            • <strong>Selective Knowledge:</strong> Choose which knowledge
            sources each persona uses - LinkedIn posts for tech, career docs for
            mentoring, etc.
          </li>
          <li>
            • <strong>Unique URLs:</strong> Share specific personas with
            different audiences: /{user.username || "username"}/tech-advisor vs
            /{user.username || "username"}/career-mentor
          </li>
          <li>
            • <strong>Separate Conversations:</strong> Each persona tracks its
            own conversations, making it easy to see which aspect people engage
            with most
          </li>
        </ul>
      </div>

      {/* Knowledge Toggle Dialog */}
      {selectedPersona && (
        <KnowledgeToggleDialog
          open={knowledgeDialogOpen}
          onOpenChange={setKnowledgeDialogOpen}
          personaId={selectedPersona.id}
          personaName={selectedPersona.name}
        />
      )}

      {/* Access Control Dialog */}
      {selectedPersona && (
        <PersonaAccessControlDialog
          open={accessControlDialogOpen}
          onOpenChange={setAccessControlDialogOpen}
          personaId={selectedPersona.id}
          personaName={selectedPersona.name}
          isPrivate={selectedPersona.is_private || false}
        />
      )}

      {/* Delete Persona Dialog */}
      {selectedPersona && (
        <DeletePersonaDialog
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
          personaId={selectedPersona.id}
          personaName={selectedPersona.name}
        />
      )}
    </div>
  );
}
