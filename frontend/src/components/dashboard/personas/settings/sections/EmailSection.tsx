"use client";

import { useEffect } from "react";
import { EmailCaptureTab } from "../../PersonaSettingsDialog/tabs/EmailCaptureTab";
import { usePersonaSettingsState } from "../../PersonaSettingsDialog/hooks/usePersonaSettingsState";
import { usePersonaSettingsSave } from "../../PersonaSettingsDialog/hooks/usePersonaSettingsSave";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useSettingsSave } from "../contexts/SettingsSaveContext";
import type { Persona } from "../../PersonaSettingsDialog/types";

interface EmailSectionProps {
  personaId: string;
  persona: Persona;
}

export function EmailSection({ personaId, persona }: EmailSectionProps) {
  const state = usePersonaSettingsState(persona);
  const { save } = usePersonaSettingsSave(personaId);
  const { hasChanges, markAsSaved, markSaveStarted, reset } = useUnsavedChanges(
    state.emailCapture,
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
          activeTab: "email",
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
        markAsSaved(state.emailCapture);
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
      state.updateEmailCapture(original);
      setHasUnsavedChanges(false);
    };

    registerDiscardHandler(handleDiscard);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reset, state.updateEmailCapture, setHasUnsavedChanges]);

  return (
    <EmailCaptureTab
      personaId={personaId}
      emailCapture={state.emailCapture}
      onChange={state.updateEmailCapture}
      emailThresholdDisplay={state.emailThresholdDisplay}
      setEmailThresholdDisplay={state.setEmailThresholdDisplay}
      sendSummaryEmailEnabled={state.sendSummaryEmailEnabled}
      onSummaryEmailChange={state.setSendSummaryEmailEnabled}
    />
  );
}
