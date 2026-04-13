"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { MonetizationTab } from "../../PersonaSettingsDialog/tabs/MonetizationTab";
import { usePersonaSettingsState } from "../../PersonaSettingsDialog/hooks/usePersonaSettingsState";
import { usePersonaSettingsSave } from "../../PersonaSettingsDialog/hooks/usePersonaSettingsSave";
import { useUnsavedChanges } from "../hooks/useUnsavedChanges";
import { useSettingsSave } from "../contexts/SettingsSaveContext";
import { useToggleMonetizationStatus } from "@/lib/queries/stripe";
import { DEFAULT_PRICE_CENTS } from "../../PersonaSettingsDialog/utils/constants";
import type { Persona } from "../../PersonaSettingsDialog/types";

interface MonetizationSectionProps {
  personaId: string;
  persona: Persona;
}

export function MonetizationSection({
  personaId,
  persona,
}: MonetizationSectionProps) {
  const state = usePersonaSettingsState(persona);
  const { save } = usePersonaSettingsSave(personaId);

  // Mutation for instant toggle
  const toggleMonetization = useToggleMonetizationStatus(personaId);

  // Track if we've marked the initial state as saved
  const hasMarkedInitialAsSaved = useRef(false);

  // Track if setup form is expanded (first-time setup mode)
  const [isSetupExpanded, setIsSetupExpanded] = useState(false);

  // Only track fields that require Save button (NOT isActive - that's instant)
  // isActive is handled by instant toggle, only price/model changes need Save
  const priceOnlyFields = {
    pricingModel: state.monetization.pricingModel,
    priceInCents: state.monetization.priceInCents,
    accessDurationDays: state.monetization.accessDurationDays,
  };

  const { hasChanges, markAsSaved, markSaveStarted, reset } = useUnsavedChanges(
    priceOnlyFields,
    {
      enabled:
        state.isMonetizationDataLoaded && hasMarkedInitialAsSaved.current,
    },
  );

  const {
    setHasUnsavedChanges,
    setIsSaving,
    registerSaveHandler,
    registerDiscardHandler,
  } = useSettingsSave();

  // Mark initial state as saved AFTER:
  // 1. React Query data loaded (state.isMonetizationDataLoaded = true)
  // 2a. If monetization data EXISTS: Wait for effect to sync price fields
  // 2b. If NO monetization data: Mark as saved immediately (nothing to sync)
  // NOTE: Only checks price fields, NOT isActive (instant toggle field)
  useEffect(() => {
    if (!state.isMonetizationDataLoaded || hasMarkedInitialAsSaved.current) {
      return;
    }

    // Case 1: No existing monetization data (new persona or never enabled)
    if (!state.monetizationData) {
      markAsSaved();
      hasMarkedInitialAsSaved.current = true;
      return;
    }

    // Case 2: Existing monetization data - check if price fields are synced
    // (isActive is excluded - it's an instant toggle field)
    const hasStateSynced =
      state.monetization.priceInCents ===
        (state.monetizationData.price_cents ?? DEFAULT_PRICE_CENTS) &&
      state.monetization.pricingModel ===
        state.monetizationData.pricing_model &&
      state.monetization.accessDurationDays ===
        (state.monetizationData.access_duration_days ?? null);

    if (hasStateSynced) {
      markAsSaved();
      hasMarkedInitialAsSaved.current = true;
    }
  }, [
    state.isMonetizationDataLoaded,
    state.monetization.priceInCents,
    state.monetization.pricingModel,
    state.monetization.accessDurationDays,
    state.monetizationData,
    markAsSaved,
  ]);

  // Notify context about changes
  useEffect(() => {
    setHasUnsavedChanges(hasChanges);
  }, [hasChanges, setHasUnsavedChanges]);

  // Force unsaved changes when setup form is expanded (first-time setup)
  useEffect(() => {
    const isFirstTimeSetup = !state.monetizationData;
    if (isFirstTimeSetup && isSetupExpanded) {
      setHasUnsavedChanges(true);
    }
  }, [isSetupExpanded, state.monetizationData, setHasUnsavedChanges]);

  // Register save handler
  useEffect(() => {
    const handleSave = async () => {
      setIsSaving(true);
      markSaveStarted();
      try {
        await save({
          persona,
          activeTab: "monetization",
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
        markAsSaved(priceOnlyFields);
        // Reset setup form expansion after successful save
        setIsSetupExpanded(false);
        // Explicitly clear unsaved changes (don't rely on effect)
        setHasUnsavedChanges(false);
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
      // Only reset price fields, NOT isActive (instant toggle field)
      state.updateMonetization(original);
      setHasUnsavedChanges(false);
    };

    registerDiscardHandler(handleDiscard);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reset, state.updateMonetization, setHasUnsavedChanges]);

  // Handler: Instant toggle for monetization enable/disable
  // Bypasses Save button for better UX (matches Email, Calendar toggles)
  const handleInstantToggle = async (checked: boolean) => {
    try {
      await toggleMonetization.mutateAsync(checked);

      toast.success(checked ? "Monetization enabled" : "Monetization disabled");
    } catch (error) {
      console.error("Failed to toggle monetization:", error);

      const errorMessage = error instanceof Error ? error.message : "";
      if (errorMessage.includes("404") || errorMessage.includes("not found")) {
        toast.error("Please configure and save monetization settings first", {
          description: "Set your pricing and click Save before enabling.",
        });
      } else {
        toast.error("Failed to toggle monetization", {
          description: errorMessage || "Please try again.",
        });
      }
    }
  };

  // Handler: Setup form expanded/collapsed
  const handleSetupExpanded = (expanded: boolean) => {
    setIsSetupExpanded(expanded);
  };

  return (
    <MonetizationTab
      personaId={personaId}
      monetization={state.monetization}
      onChange={state.updateMonetization}
      priceDisplay={state.priceDisplay}
      setPriceDisplay={state.setPriceDisplay}
      onInstantToggle={handleInstantToggle}
      onSetupExpanded={handleSetupExpanded}
    />
  );
}
