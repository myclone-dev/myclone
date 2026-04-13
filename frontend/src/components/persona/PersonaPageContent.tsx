"use client";

import { Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";
import { ExpertChatInterface } from "@/components/expert/ExpertChatInterface";
import { PersonaAccessGate } from "@/components/persona/PersonaAccessGate";
import { PersonaMonetizationGate } from "@/components/persona/PersonaMonetizationGate";
import { usePersona } from "@/lib/queries/persona";
import { useGetSuggestedQuestions } from "@/lib/queries/prompt";
import { useCheckAccess } from "@/lib/queries/access-control";
import { PageLoader } from "@/components/ui/page-loader";
import { AvatarWithAIBadge } from "@/components/expert/AvatarWithAIBadge";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { toast } from "sonner";
import * as Sentry from "@sentry/nextjs";
import { I18nProvider } from "@/i18n/I18nProvider";

interface PersonaPageContentProps {
  username: string;
  personaName?: string;
}

/**
 * Inner component that uses translations (must be inside I18nProvider)
 */
function PersonaPageInner({
  username,
  personaName,
  persona,
  questionsToDisplay,
  accessCheck,
  accessLoading,
  handleAccessGranted,
}: {
  username: string;
  personaName: string;
  persona: NonNullable<ReturnType<typeof usePersona>["data"]>;
  questionsToDisplay: string[];
  accessCheck: ReturnType<typeof useCheckAccess>["data"];
  accessLoading: boolean;
  handleAccessGranted: () => Promise<void>;
}) {
  const { t } = useTranslation();

  if (accessLoading) {
    return <PageLoader />;
  }

  // Show access gate if persona is private and visitor doesn't have access
  // accessCheck.hasAccess is determined by the myclone_visitor cookie
  if (accessCheck?.isPrivate && !accessCheck?.hasAccess) {
    return (
      <div className="min-h-screen relative overflow-hidden bg-white">
        {/* Split Background */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-0 right-0 h-1/2 bg-peach-cream" />
          <div className="absolute bottom-0 left-0 right-0 h-1/2 bg-white" />
        </div>

        <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          {/* Profile Header */}
          <div className="flex flex-col items-center mb-8 space-y-6">
            <Avatar className="w-28 h-28 ring-4 ring-white shadow-xl">
              <AvatarImage
                src={persona.persona_avatar_url || persona.avatar || undefined}
                alt={persona.name}
              />
              <AvatarFallback className="bg-gradient-to-br from-amber-400 to-orange-500 text-white text-3xl font-semibold">
                {persona.name?.charAt(0).toUpperCase() || "E"}
              </AvatarFallback>
            </Avatar>

            <div className="text-center space-y-3">
              <h1 className="text-4xl md:text-5xl font-bold text-gray-900">
                {persona.name}
              </h1>
              {persona.role && (
                <p className="text-gray-700 text-lg md:text-xl font-medium">
                  {persona.role}
                  {persona.company && ` ${t("common.at")} ${persona.company}`}
                </p>
              )}
            </div>
          </div>

          {/* Access Gate */}
          <PersonaAccessGate
            username={username}
            personaName={personaName}
            onAccessGranted={handleAccessGranted}
          />
        </div>
      </div>
    );
  }

  return (
    <PersonaMonetizationGate
      personaId={persona.id}
      personaName={personaName}
      personaUsername={username}
      personaDisplayName={persona.name}
    >
      <div className="min-h-screen relative overflow-hidden bg-white">
        {/* Split Background - Top 60% peach-light (#FFF4EB), bottom 40% white */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-0 left-0 right-0 h-[60%] bg-peach-light" />
          <div className="absolute bottom-0 left-0 right-0 h-[40%] bg-white" />
        </div>

        <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          {/* Profile Header */}
          <div className="flex flex-col items-center mb-8 space-y-6">
            {/* Avatar */}
            <AvatarWithAIBadge
              src={persona.persona_avatar_url || persona.avatar || undefined}
              alt={persona.name}
              fallbackText={persona.name?.charAt(0).toUpperCase() || "E"}
            />

            {/* Name and Title */}
            <div className="text-center space-y-3">
              <h1 className="text-4xl md:text-5xl font-bold text-gray-900">
                {persona.name}
              </h1>
              {persona.role && (
                <p className="text-gray-700 text-lg md:text-xl font-medium">
                  {persona.role}
                  {persona.company && ` ${t("common.at")} ${persona.company}`}
                </p>
              )}

              {/* AI Badge */}
              <div className="flex items-center justify-center gap-2 pt-2">
                <div
                  className="inline-flex items-center gap-2 text-sm font-semibold"
                  style={{ color: "#B06B30" }}
                >
                  <Sparkles className="w-4 h-4" />
                  <span>{t("widget.aiPowered")}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Chat Interface */}
          <ExpertChatInterface
            username={username}
            personaName={personaName}
            expertName={persona.name}
            avatarUrl={persona.persona_avatar_url || persona.avatar}
            suggestedQuestions={questionsToDisplay}
            enableVoice={persona.voice_enabled !== false}
            emailCaptureEnabled={persona.email_capture_enabled}
            emailCaptureThreshold={persona.email_capture_message_threshold}
            emailCaptureRequireFullname={persona.email_capture_require_fullname}
            emailCaptureRequirePhone={persona.email_capture_require_phone}
            sessionTimeLimitEnabled={persona.session_time_limit_enabled}
            sessionTimeLimitMinutes={persona.session_time_limit_minutes}
            sessionTimeLimitWarningMinutes={
              persona.session_time_limit_warning_minutes
            }
            calendarDisplayName={persona.calendar_display_name ?? undefined}
          />
        </div>
      </div>
    </PersonaMonetizationGate>
  );
}

/**
 * Shared component for rendering persona chat interface
 * Handles access control, monetization gates, and chat functionality
 * Used by both /[username] and /[username]/[persona_name] routes
 *
 * Wraps content with I18nProvider using persona's language setting
 */
export function PersonaPageContent({
  username,
  personaName = "default",
}: PersonaPageContentProps) {
  const {
    data: persona,
    isLoading: personaLoading,
    error: personaError,
  } = usePersona(username, personaName);

  // Debug: Log calendar display name from persona
  if (process.env.NODE_ENV === "development" && persona) {
    console.log("[PersonaPageContent] Calendar settings:", {
      calendar_enabled: persona.calendar_enabled,
      calendar_url: persona.calendar_url,
      calendar_display_name: persona.calendar_display_name,
    });
  }

  // Fetch suggested questions using the new GET endpoint
  const { data: suggestedQuestionsData } = useGetSuggestedQuestions(
    persona?.id ?? null,
    { enabled: !!persona?.id },
  );

  // Determine which questions to use
  // Priority: Use whichever has MORE questions (to work around backend cache bug)
  const personaQuestions = persona?.suggested_questions || [];
  const cachedQuestions = suggestedQuestionsData?.suggested_questions || [];
  const questionsToDisplay =
    personaQuestions.length > cachedQuestions.length
      ? personaQuestions
      : cachedQuestions.length > 0
        ? cachedQuestions
        : personaQuestions;

  // Check access using myclone_visitor cookie
  const {
    data: accessCheck,
    isLoading: accessLoading,
    refetch: refetchAccess,
  } = useCheckAccess(username, personaName);

  const handleAccessGranted = async () => {
    // Refetch to update access status (cookie is now set)
    try {
      await refetchAccess();
    } catch (error) {
      Sentry.captureException(error, {
        tags: { operation: "persona_access_verify" },
        contexts: {
          persona: { username, persona_name: personaName },
        },
      });
      toast.error("Failed to verify access. Please refresh the page.");
    }
  };

  // Check loading states separately to avoid race conditions
  if (personaLoading) {
    return <PageLoader />;
  }

  if (personaError || !persona) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            Persona not found
          </h1>
          <p className="text-gray-600">
            The persona @{username}/{personaName} does not exist.
          </p>
        </div>
      </div>
    );
  }

  // Wrap with I18nProvider using persona's language setting
  // Language defaults to "en" if not set or set to "auto"
  return (
    <I18nProvider locale={persona.language}>
      <PersonaPageInner
        username={username}
        personaName={personaName}
        persona={persona}
        questionsToDisplay={questionsToDisplay}
        accessCheck={accessCheck}
        accessLoading={accessLoading}
        handleAccessGranted={handleAccessGranted}
      />
    </I18nProvider>
  );
}
