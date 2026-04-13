"use client";

import { useEffect } from "react";
import { VoiceTab } from "../../PersonaSettingsDialog/tabs/VoiceTab";
import { SectionHeader } from "../components/SectionHeader";
import { usePersonaSettingsState } from "../../PersonaSettingsDialog/hooks/usePersonaSettingsState";
import { usePersonaSettingsSave } from "../../PersonaSettingsDialog/hooks/usePersonaSettingsSave";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useSettingsSave } from "../contexts/SettingsSaveContext";
import type { Persona } from "../../PersonaSettingsDialog/types";

interface VoiceSectionProps {
  personaId: string;
  persona: Persona;
}

export function VoiceSection({ personaId, persona }: VoiceSectionProps) {
  const state = usePersonaSettingsState(persona);
  const { save } = usePersonaSettingsSave(personaId);
  const voiceState = {
    voiceId: state.voiceId,
    voiceEnabled: state.voiceEnabled,
  };
  const { hasChanges, markAsSaved, markSaveStarted, reset } =
    useUnsavedChanges(voiceState);

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
          activeTab: "voice",
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
        markAsSaved({
          voiceId: state.voiceId,
          voiceEnabled: state.voiceEnabled,
        });
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
    state.voiceEnabled,
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
      state.setVoiceId(original.voiceId);
      state.setVoiceEnabled(original.voiceEnabled);
      setHasUnsavedChanges(false);
    };

    registerDiscardHandler(handleDiscard);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reset, state.setVoiceId, state.setVoiceEnabled, setHasUnsavedChanges]);

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Voice Agent"
        description="Control whether visitors can use voice chat with this persona"
      />

      <VoiceTab
        voiceId={state.voiceId}
        onChange={(voiceId) => state.setVoiceId(voiceId)}
        voiceEnabled={state.voiceEnabled}
        onVoiceEnabledChange={state.setVoiceEnabled}
      />
    </div>
  );
}
