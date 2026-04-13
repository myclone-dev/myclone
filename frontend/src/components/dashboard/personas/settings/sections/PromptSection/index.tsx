"use client";

import { useState, useEffect, useRef } from "react";
import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePersonaPrefill } from "@/lib/queries/prompt";
import { usePersonaSettingsSave } from "../../../PersonaSettingsDialog/hooks/usePersonaSettingsSave";
import { useUnsavedChanges } from "../../hooks/useUnsavedChanges";
import { useSettingsSave } from "../../contexts/SettingsSaveContext";
import type { Persona } from "../../../PersonaSettingsDialog/types";
import type { PersonaPromptFields } from "@/lib/queries/prompt";
import { usePromptDocumentation } from "./hooks/usePromptDocumentation";
import { PromptFieldWithHelp } from "./PromptFieldWithHelp";
import { AdvancedSettingsSection } from "./AdvancedSettingsSection";
import { ESSENTIAL_FIELDS } from "./constants";

interface PromptSectionProps {
  personaId: string;
  persona: Persona;
}

export function PromptSection({ personaId, persona }: PromptSectionProps) {
  const { data: promptData } = usePersonaPrefill(personaId, { enabled: true });
  const { save } = usePersonaSettingsSave(personaId);
  const { openGuideLink } = usePromptDocumentation();

  const [promptFields, setPromptFields] = useState<
    Partial<PersonaPromptFields>
  >({});
  const isInitialLoad = useRef(true);
  const hasMarkedAsSaved = useRef(false);

  const { hasChanges, markAsSaved, markSaveStarted, reset } =
    useUnsavedChanges(promptFields);

  const {
    setHasUnsavedChanges,
    setIsSaving,
    registerSaveHandler,
    registerDiscardHandler,
  } = useSettingsSave();

  // Initialize prompt fields from API data
  useEffect(() => {
    if (promptData && isInitialLoad.current) {
      const initialFields = {
        introduction: promptData.introduction || "",
        area_of_expertise: promptData.area_of_expertise || "",
        chat_objective: promptData.chat_objective || "",
        target_audience: promptData.target_audience || "",
        thinking_style: promptData.thinking_style || "",
        objective_response: promptData.objective_response || "",
        conversation_flow: promptData.conversation_flow || "",
        example_responses: promptData.example_responses || "",
        strict_guideline: promptData.strict_guideline || "",
      };
      setPromptFields(initialFields);
      isInitialLoad.current = false;
    }
  }, [promptData]);

  // Mark as saved AFTER promptFields has been populated (only once)
  useEffect(() => {
    if (
      !isInitialLoad.current &&
      !hasMarkedAsSaved.current &&
      Object.keys(promptFields).length > 0
    ) {
      markAsSaved();
      hasMarkedAsSaved.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [promptFields]);

  // Notify context about changes
  useEffect(() => {
    setHasUnsavedChanges(hasChanges);
  }, [hasChanges, setHasUnsavedChanges]);

  // Register save handler
  useEffect(() => {
    const handleSave = async () => {
      setIsSaving(true);
      markSaveStarted();
      try {
        await save({
          persona,
          activeTab: "prompt",
          basicInfo: {
            name: persona.name,
            role: persona.role || "",
            expertise: persona.expertise || "",
            description: persona.description || "",
            greetingMessage: persona.greeting_message || "",
          },
          voiceId: persona.voice_id,
          voiceEnabled: persona.voice_enabled ?? true,
          language: persona.language || "auto",
          emailCapture: {
            threshold: persona.email_capture_message_threshold || 3,
            enabled: persona.email_capture_enabled || false,
            requireFullname: persona.email_capture_require_fullname || false,
            requirePhone: persona.email_capture_require_phone || false,
            defaultLeadCaptureEnabled:
              persona.default_lead_capture_enabled || false,
          },
          calendar: {
            enabled: persona.calendar_enabled || false,
            url: persona.calendar_url || "",
            displayName: persona.calendar_display_name || "",
          },
          calendarUrlError: null,
          sessionTimeLimit: {
            enabled: persona.session_time_limit_enabled || false,
            limitMinutes: persona.session_time_limit_minutes || 30,
            warningMinutes: persona.session_time_limit_warning_minutes || 2,
          },
          monetization: {
            isActive: false,
            pricingModel: "free" as const,
            priceInCents: 0,
            accessDurationDays: null,
          },
          monetizationData: {
            enableWallet: false,
          },
          promptFields: promptFields,
          promptData: promptData || undefined,
        });
        markAsSaved(promptFields);
      } finally {
        setIsSaving(false);
      }
    };

    registerSaveHandler(handleSave);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    save,
    persona,
    promptFields,
    promptData,
    markAsSaved,
    markSaveStarted,
    setIsSaving,
  ]);

  // Register discard handler
  useEffect(() => {
    const handleDiscard = () => {
      const original = reset();
      setPromptFields(original);
      setHasUnsavedChanges(false);
    };

    registerDiscardHandler(handleDiscard);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reset, setHasUnsavedChanges]);

  const handleFieldChange = (
    field: keyof PersonaPromptFields,
    value: string,
  ) => {
    setPromptFields((prev) => ({ ...prev, [field]: value }));
  };

  return (
    <div className="space-y-6">
      {/* Header with View Guide link */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">
            Prompt Configuration
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Define how your persona thinks and responds
          </p>
        </div>
        <Button
          variant="outline"
          className="text-amber-600 hover:text-amber-700 hover:bg-amber-50 border-amber-300"
          onClick={() => openGuideLink()}
        >
          <ExternalLink className="size-4 mr-2" />
          View Guide
        </Button>
      </div>

      {/* Essential Fields */}
      <div className="space-y-8">
        {ESSENTIAL_FIELDS.map((field) => (
          <PromptFieldWithHelp
            key={field.id}
            config={field}
            value={
              (promptFields[field.id as keyof PersonaPromptFields] as
                | string
                | undefined) || ""
            }
            onChange={(value) =>
              handleFieldChange(field.id as keyof PersonaPromptFields, value)
            }
          />
        ))}

        {/* Advanced Settings */}
        <AdvancedSettingsSection
          promptFields={promptFields}
          onFieldChange={handleFieldChange}
        />
      </div>
    </div>
  );
}
