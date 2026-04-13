import { useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { getErrorMessage } from "@/lib/api/error";
import type {
  Persona,
  BasicInfoFormData,
  EmailCaptureSettings,
  CalendarSettings,
  SessionTimeLimitSettings,
  MonetizationSettings,
  SettingsTab,
  PersonaLanguage,
} from "../types";
import {
  DEFAULT_SESSION_LIMIT_MINUTES,
  DEFAULT_SESSION_WARNING_MINUTES,
} from "../utils";
import { useUpdatePersonaWithKnowledge } from "@/lib/queries/persona";
import {
  useUpdatePromptField,
  type PersonaPromptFields,
} from "@/lib/queries/prompt";
import {
  useEnableMonetization,
  useUpdateMonetization,
} from "@/lib/queries/stripe";
import { validateCalendarUrl } from "../utils/validation";

interface SaveOptions {
  persona: Persona;
  activeTab: SettingsTab;
  basicInfo: BasicInfoFormData;
  voiceId: string | undefined;
  voiceEnabled: boolean;
  language: PersonaLanguage;
  emailCapture: EmailCaptureSettings;
  calendar: CalendarSettings;
  calendarUrlError: string | null;
  sessionTimeLimit: SessionTimeLimitSettings;
  monetization: MonetizationSettings;
  monetizationData: unknown;
  promptFields?: Partial<PersonaPromptFields>;
  promptData?: Partial<PersonaPromptFields>;
  onSuccess?: () => void;
}

/**
 * Hook to handle saving persona settings based on active tab
 * Only saves and validates data for the currently active tab
 * Provides better UX by avoiding validation errors for tabs user hasn't visited
 */
export function usePersonaSettingsSave(personaId: string) {
  const [isSaving, setIsSaving] = useState(false);
  const queryClient = useQueryClient();

  // Mutations
  const updatePersonaMutation = useUpdatePersonaWithKnowledge();
  const updatePromptMutation = useUpdatePromptField();
  const enableMonetization = useEnableMonetization(personaId);
  const updateMonetization = useUpdateMonetization(personaId);

  const save = async (options: SaveOptions) => {
    const {
      persona,
      activeTab,
      basicInfo,
      voiceId,
      voiceEnabled,
      language,
      emailCapture,
      calendar,
      calendarUrlError,
      sessionTimeLimit,
      monetization,
      monetizationData,
      promptFields,
      promptData,
      onSuccess,
    } = options;

    setIsSaving(true);

    try {
      // ===== TAB-SPECIFIC SAVE =====
      switch (activeTab) {
        case "basic": {
          // Validate and save basic info
          const hasBasicChanges =
            basicInfo.name !== persona.name ||
            basicInfo.role !== persona.role ||
            basicInfo.expertise !== (persona.expertise || "") ||
            basicInfo.description !== (persona.description || "") ||
            basicInfo.greetingMessage !== (persona.greeting_message || "");

          if (hasBasicChanges) {
            await updatePersonaMutation.mutateAsync({
              personaId: persona.id,
              data: {
                name: basicInfo.name,
                role: basicInfo.role,
                expertise: basicInfo.expertise,
                description: basicInfo.description,
                greeting_message: basicInfo.greetingMessage,
              },
            });
          } else {
            toast.info("No changes to save");
            setIsSaving(false);
            return;
          }
          break;
        }

        case "voice": {
          // Validate and save voice selection + voice enabled toggle
          // Treat empty string and undefined as equivalent (both mean default voice)
          const normalizedVoiceId = voiceId || "";
          const normalizedPersonaVoiceId = persona.voice_id || "";
          const hasVoiceIdChanges =
            normalizedVoiceId !== normalizedPersonaVoiceId;
          const hasVoiceEnabledChanges =
            voiceEnabled !== (persona.voice_enabled ?? true);
          const hasVoiceChanges = hasVoiceIdChanges || hasVoiceEnabledChanges;

          if (hasVoiceChanges) {
            await updatePersonaMutation.mutateAsync({
              personaId: persona.id,
              data: {
                voice_id: normalizedVoiceId,
                voice_enabled: voiceEnabled,
              },
            });
          } else {
            toast.info("No changes to save");
            setIsSaving(false);
            return;
          }
          break;
        }

        case "language": {
          // Validate and save language preference
          const hasLanguageChanges = language !== (persona.language || "auto");

          if (hasLanguageChanges) {
            await updatePersonaMutation.mutateAsync({
              personaId: persona.id,
              data: { language },
            });
          } else {
            toast.info("No changes to save");
            setIsSaving(false);
            return;
          }
          break;
        }

        case "email": {
          // Validate and save email capture settings
          const hasEmailChanges =
            emailCapture.enabled !== (persona.email_capture_enabled ?? false) ||
            emailCapture.threshold !==
              (persona.email_capture_message_threshold ?? 5) ||
            emailCapture.requireFullname !==
              (persona.email_capture_require_fullname ?? true) ||
            emailCapture.requirePhone !==
              (persona.email_capture_require_phone ?? false) ||
            emailCapture.defaultLeadCaptureEnabled !==
              (persona.default_lead_capture_enabled ?? false);

          if (hasEmailChanges) {
            await updatePersonaMutation.mutateAsync({
              personaId: persona.id,
              data: {
                email_capture_enabled: emailCapture.enabled,
                email_capture_message_threshold: emailCapture.threshold,
                email_capture_require_fullname: emailCapture.requireFullname,
                email_capture_require_phone: emailCapture.requirePhone,
                default_lead_capture_enabled:
                  emailCapture.defaultLeadCaptureEnabled,
              },
            });
          } else {
            toast.info("No changes to save");
            setIsSaving(false);
            return;
          }
          break;
        }

        case "calendar": {
          // Validate calendar URL
          if (calendar.enabled && calendar.url) {
            const validation = validateCalendarUrl(calendar.url);
            if (!validation.valid) {
              toast.error(validation.error || "Invalid calendar URL");
              setIsSaving(false);
              return;
            }
          }

          if (calendarUrlError) {
            toast.error("Please fix calendar URL error before saving");
            setIsSaving(false);
            return;
          }

          // Check for changes
          const hasCalendarChanges =
            calendar.enabled !== (persona.calendar_enabled ?? false) ||
            calendar.url !== (persona.calendar_url ?? "") ||
            calendar.displayName !== (persona.calendar_display_name ?? "");

          if (hasCalendarChanges) {
            await updatePersonaMutation.mutateAsync({
              personaId: persona.id,
              data: {
                calendar_enabled: calendar.enabled,
                calendar_url: calendar.enabled ? calendar.url || null : null,
                calendar_display_name: calendar.enabled
                  ? calendar.displayName || null
                  : null,
              },
            });
          } else {
            toast.info("No changes to save");
            setIsSaving(false);
            return;
          }
          break;
        }

        case "session": {
          // Validate session duration is not zero when enabled
          if (sessionTimeLimit.enabled && sessionTimeLimit.limitMinutes <= 0) {
            toast.error("Session duration must be greater than 0");
            setIsSaving(false);
            return;
          }

          // Validate warning time is less than limit
          if (
            sessionTimeLimit.warningMinutes >= sessionTimeLimit.limitMinutes
          ) {
            toast.error("Warning time must be less than session duration");
            setIsSaving(false);
            return;
          }

          // Check for changes
          const hasSessionChanges =
            sessionTimeLimit.enabled !==
              (persona.session_time_limit_enabled ?? false) ||
            sessionTimeLimit.limitMinutes !==
              (persona.session_time_limit_minutes ??
                DEFAULT_SESSION_LIMIT_MINUTES) ||
            sessionTimeLimit.warningMinutes !==
              (persona.session_time_limit_warning_minutes ??
                DEFAULT_SESSION_WARNING_MINUTES);

          if (hasSessionChanges) {
            await updatePersonaMutation.mutateAsync({
              personaId: persona.id,
              data: {
                session_time_limit_enabled: sessionTimeLimit.enabled,
                session_time_limit_minutes: sessionTimeLimit.limitMinutes,
                session_time_limit_warning_minutes:
                  sessionTimeLimit.warningMinutes,
              },
            });
          } else {
            toast.info("No changes to save");
            setIsSaving(false);
            return;
          }
          break;
        }

        case "monetization": {
          // Validate price
          if (monetization.priceInCents < 100) {
            toast.error("Price must be at least $1.00");
            setIsSaving(false);
            return;
          }

          // Check if pricing settings changed (NOT isActive - that's handled by instant toggle)
          const currentPrice = (monetizationData as { price_cents?: number })
            ?.price_cents;
          const currentModel = (
            monetizationData as {
              pricing_model?: string;
            }
          )?.pricing_model;
          const currentDuration = (
            monetizationData as {
              access_duration_days?: number | null;
            }
          )?.access_duration_days;

          const hasPriceChange =
            monetization.priceInCents !== currentPrice ||
            monetization.pricingModel !== currentModel ||
            monetization.accessDurationDays !== currentDuration;

          if (!hasPriceChange) {
            toast.info("No changes to save");
            setIsSaving(false);
            return;
          }

          // Save pricing settings only (isActive is handled by instant toggle)
          if (!monetizationData) {
            // First-time creation: Use POST /monetization
            const monetizationPayload = {
              pricing_model: monetization.pricingModel,
              price_cents: monetization.priceInCents,
              currency: "usd" as const,
              access_duration_days:
                monetization.pricingModel === "one_time_duration"
                  ? monetization.accessDurationDays
                  : null,
            };
            await enableMonetization.mutateAsync(monetizationPayload);
          } else {
            // Update existing: Use PUT /monetization (updates price/model only)
            const updatePayload = {
              pricing_model: monetization.pricingModel,
              price_cents: monetization.priceInCents,
              access_duration_days:
                monetization.pricingModel === "one_time_duration"
                  ? monetization.accessDurationDays
                  : null,
            };
            await updateMonetization.mutateAsync(updatePayload);
          }
          break;
        }

        case "prompt": {
          // Save prompt fields
          if (promptFields && promptData) {
            const fieldsToUpdate: Array<keyof PersonaPromptFields> = [
              "introduction",
              "area_of_expertise",
              "chat_objective",
              "target_audience",
              "response_structure",
              "thinking_style",
              "objective_response",
              "conversation_flow",
              "example_responses",
              "strict_guideline",
            ];

            let hasChanges = false;

            for (const field of fieldsToUpdate) {
              const newValue = promptFields[field];
              const oldValue = promptData[field];

              if (
                newValue !== undefined &&
                JSON.stringify(newValue) !== JSON.stringify(oldValue)
              ) {
                hasChanges = true;
                await updatePromptMutation.mutateAsync({
                  persona_id: persona.id,
                  field: field,
                  value: newValue as string | object,
                });
              }
            }

            if (!hasChanges) {
              toast.info("No changes to save");
              setIsSaving(false);
              return;
            }
          } else {
            toast.info("No changes to save");
            setIsSaving(false);
            return;
          }
          break;
        }

        default:
          toast.error("Unknown tab");
          setIsSaving(false);
          return;
      }

      // ===== REFETCH QUERIES =====
      // Refetch persona list (for personas page)
      await queryClient.refetchQueries({
        predicate: (query) =>
          Array.isArray(query.queryKey) &&
          query.queryKey[0] === "user-personas",
      });

      // Refetch current persona (for settings page to get fresh data)
      await queryClient.refetchQueries({
        predicate: (query) =>
          Array.isArray(query.queryKey) &&
          query.queryKey[0] === "persona-by-id" &&
          query.queryKey[1] === personaId,
      });

      // Success!
      toast.success("Settings updated successfully!", {
        description: `Your ${activeTab === "basic" ? "basic info" : activeTab} settings have been saved.`,
      });

      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      console.error("Failed to update settings:", error);
      const errorMessage = getErrorMessage(error, `save ${activeTab} settings`);
      toast.error("Failed to update settings", {
        description: errorMessage,
      });
    } finally {
      setIsSaving(false);
    }
  };

  return {
    save,
    isSaving,
  };
}
