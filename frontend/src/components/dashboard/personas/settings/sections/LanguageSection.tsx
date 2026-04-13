"use client";

import { useEffect } from "react";
import { LanguageTab } from "../../PersonaSettingsDialog/tabs/LanguageTab";
import { SectionHeader } from "../components/SectionHeader";
import { usePersonaSettingsState } from "../../PersonaSettingsDialog/hooks/usePersonaSettingsState";
import { usePersonaSettingsSave } from "../../PersonaSettingsDialog/hooks/usePersonaSettingsSave";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useSettingsSave } from "../contexts/SettingsSaveContext";
import type { Persona } from "../../PersonaSettingsDialog/types";

interface LanguageSectionProps {
  personaId: string;
  persona: Persona;
}

export function LanguageSection({ personaId, persona }: LanguageSectionProps) {
  const state = usePersonaSettingsState(persona);
  const { save } = usePersonaSettingsSave(personaId);
  const { hasChanges, markAsSaved, markSaveStarted, reset } = useUnsavedChanges(
    state.language,
  );

  const {
    setHasUnsavedChanges,
    setIsSaving,
    registerSaveHandler,
    registerDiscardHandler,
  } = useSettingsSave();

  // Notify context about changes
  useEffect(() => {
    setHasUnsavedChanges(hasChanges);
  }, [hasChanges, setHasUnsavedChanges]);

  // Register save handler
  useEffect(() => {
    const handleSave = async () => {
      setIsSaving(true);
      // Mark save started BEFORE the API call so the hook knows to sync
      // originalValue when the refetch updates currentValue
      markSaveStarted();
      try {
        await save({
          persona,
          activeTab: "language",
          basicInfo: state.basicInfo,
          voiceId: state.voiceId,
          voiceEnabled: state.voiceEnabled,
          language: state.language,
          emailCapture: state.emailCapture,
          calendar: state.calendar,
          calendarUrlError: state.calendarUrlError,
          sessionTimeLimit: state.sessionTimeLimit,
          monetization: state.monetization,
          monetizationData: state.monetizationData,
          promptFields: {},
        });
        // Pass the saved value explicitly so originalValue is set correctly
        // even if the refetch hasn't updated currentValue yet
        markAsSaved(state.language);
      } finally {
        setIsSaving(false);
      }
    };

    registerSaveHandler(handleSave);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    save,
    persona,
    state.basicInfo,
    state.voiceId,
    state.language,
    state.emailCapture,
    state.calendar,
    state.calendarUrlError,
    state.monetization,
    state.monetizationData,
    markAsSaved,
    markSaveStarted,
    setIsSaving,
  ]);

  // Register discard handler
  useEffect(() => {
    const handleDiscard = () => {
      const original = reset();
      state.setLanguage(original);
      setHasUnsavedChanges(false);
    };

    registerDiscardHandler(handleDiscard);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reset, state.setLanguage, setHasUnsavedChanges]);

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Language Settings"
        description="Configure the preferred response language for your persona"
      />

      <LanguageTab
        language={state.language}
        savedLanguage={
          hasChanges ? (reset() as typeof state.language) : state.language
        }
        onChange={(language) => state.setLanguage(language)}
      />
    </div>
  );
}
