"use client";

import { useEffect } from "react";
import { SessionLimitTab } from "../../PersonaSettingsDialog/tabs/SessionLimitTab";
import { SectionHeader } from "../components/SectionHeader";
import { usePersonaSettingsState } from "../../PersonaSettingsDialog/hooks/usePersonaSettingsState";
import { usePersonaSettingsSave } from "../../PersonaSettingsDialog/hooks/usePersonaSettingsSave";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useSettingsSave } from "../contexts/SettingsSaveContext";
import type { Persona } from "../../PersonaSettingsDialog/types";

interface SessionSectionProps {
  personaId: string;
  persona: Persona;
}

export function SessionSection({ personaId, persona }: SessionSectionProps) {
  const state = usePersonaSettingsState(persona);
  const { save } = usePersonaSettingsSave(personaId);
  const { hasChanges, markAsSaved, markSaveStarted, reset } = useUnsavedChanges(
    state.sessionTimeLimit,
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
      markSaveStarted();
      try {
        await save({
          persona,
          activeTab: "session",
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
        markAsSaved(state.sessionTimeLimit);
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
    state.sessionTimeLimit,
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
      state.updateSessionTimeLimit(original);
      setHasUnsavedChanges(false);
    };

    registerDiscardHandler(handleDiscard);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reset, state.updateSessionTimeLimit, setHasUnsavedChanges]);

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Session Time Limits"
        description="Configure session duration limits for visitors interacting with your persona"
      />

      <SessionLimitTab
        sessionTimeLimit={state.sessionTimeLimit}
        onChange={state.updateSessionTimeLimit}
      />
    </div>
  );
}
