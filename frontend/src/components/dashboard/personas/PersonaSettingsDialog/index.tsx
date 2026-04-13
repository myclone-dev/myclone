"use client";

import { useState, useEffect, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Settings,
  User,
  MessageSquare,
  Mail,
  Calendar,
  DollarSign,
  Mic,
  Globe,
  Timer,
  Camera,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  usePersonaPrefill,
  useGetSuggestedQuestions,
} from "@/lib/queries/prompt";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { PersonaCreatingOverlay } from "../PersonaCreatingOverlay";
import { SaveButton } from "./components/SaveButton";
import { usePersonaSettingsState } from "./hooks/usePersonaSettingsState";
import { usePersonaSettingsSave } from "./hooks/usePersonaSettingsSave";
import type { PersonaSettingsDialogProps, SettingsTab } from "./types";
import type { PersonaPromptFields } from "@/lib/queries/prompt";

// Lazy load tabs
import { BasicInfoTab } from "./tabs/BasicInfoTab";
import { AvatarTab } from "./tabs/AvatarTab";
import { VoiceTab } from "./tabs/VoiceTab";
import { LanguageTab } from "./tabs/LanguageTab";
import { EmailCaptureTab } from "./tabs/EmailCaptureTab";
import { CalendarTab } from "./tabs/CalendarTab";
import { MonetizationTab } from "./tabs/MonetizationTab";
import { PromptTab } from "./tabs/PromptTab";
import { SessionLimitTab } from "./tabs/SessionLimitTab";

/**
 * Refactored PersonaSettings Dialog
 * Modular architecture with extracted tabs and centralized state management
 * Reduced from 2,594 lines to ~150 lines
 */
export function PersonaSettingsDialog({
  persona,
  open: controlledOpen,
  onOpenChange,
  trigger,
  onSuccess,
  isCreating = false,
  onCreationComplete,
}: PersonaSettingsDialogProps) {
  // Dialog state
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen ?? internalOpen;
  const setOpen = onOpenChange ?? setInternalOpen;

  // Active tab
  const [activeTab, setActiveTab] = useState<SettingsTab>("basic");

  // Centralized state management
  const state = usePersonaSettingsState(persona);
  const { save, isSaving } = usePersonaSettingsSave(persona.id);

  // Prompt fields state (for PromptTab)
  const [promptFields, setPromptFields] = useState<
    Partial<PersonaPromptFields>
  >({});

  // Fetch prompt data when dialog opens
  const {
    data: promptData,
    isLoading: promptLoading,
    refetch: refetchPromptData,
  } = usePersonaPrefill(persona.id, { enabled: open });

  // Fetch suggested questions
  const { refetch: refetchQuestions } = useGetSuggestedQuestions(persona.id, {
    enabled: open,
  });

  const { data: user } = useUserMe();

  // Track if we're refetching after creation
  const [isRefetchingAfterCreate, setIsRefetchingAfterCreate] = useState(false);
  const [hasBeenOpenedBefore, setHasBeenOpenedBefore] = useState(false);
  const prevIsCreatingRef = useRef(isCreating);

  // When isCreating transitions from true to false, refetch data
  useEffect(() => {
    if (prevIsCreatingRef.current && !isCreating && open) {
      setIsRefetchingAfterCreate(true);
      Promise.all([refetchPromptData(), refetchQuestions()]).finally(() => {
        setIsRefetchingAfterCreate(false);
        onCreationComplete?.();
      });
    }
    prevIsCreatingRef.current = isCreating;
  }, [
    isCreating,
    open,
    refetchPromptData,
    refetchQuestions,
    onCreationComplete,
  ]);

  // Mark dialog as "has been opened" when it closes
  useEffect(() => {
    if (!open && promptData && !hasBeenOpenedBefore) {
      setHasBeenOpenedBefore(true);
    }
  }, [open, promptData, hasBeenOpenedBefore]);

  // Initialize prompt fields from API data
  useEffect(() => {
    if (promptData) {
      setPromptFields({
        introduction: promptData.introduction || "",
        area_of_expertise: promptData.area_of_expertise || "",
        chat_objective: promptData.chat_objective || "",
        target_audience: promptData.target_audience || "",
        thinking_style: promptData.thinking_style || "",
        objective_response: promptData.objective_response || "",
        conversation_flow: promptData.conversation_flow || "",
        example_responses: promptData.example_responses || "",
        strict_guideline: promptData.strict_guideline || "",
      });
    }
  }, [promptData]);

  // Combined loading state
  const showLoadingOverlay =
    isCreating || promptLoading || isRefetchingAfterCreate;

  const showSimplifiedLoader =
    hasBeenOpenedBefore &&
    promptLoading &&
    !isCreating &&
    !isRefetchingAfterCreate;

  // Save handler
  const handleSave = async () => {
    await save({
      persona,
      activeTab,
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
      promptFields: promptFields as Partial<PersonaPromptFields>,
      promptData: promptData || undefined,
      onSuccess,
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger && <DialogTrigger asChild>{trigger}</DialogTrigger>}

      <DialogContent className="w-[95vw] sm:w-[90vw] md:w-[85vw] lg:w-[70vw] max-w-[95vw] sm:max-w-[90vw] md:max-w-[85vw] lg:max-w-[70vw] h-[90vh] sm:h-[85vh] overflow-hidden flex flex-col p-0">
        <DialogHeader className="px-4 sm:px-6 pt-4 sm:pt-6 pb-3 sm:pb-4 border-b shrink-0 bg-gradient-to-r from-background to-muted/20">
          <DialogTitle className="flex items-center gap-2 text-lg sm:text-xl">
            <Settings className="size-4 sm:size-5 text-primary" />
            Persona Settings
          </DialogTitle>
          <DialogDescription className="text-xs sm:text-sm">
            Configure your persona&apos;s identity and behavior
          </DialogDescription>
        </DialogHeader>

        {showLoadingOverlay ? (
          <PersonaCreatingOverlay
            personaName={persona.name}
            variant={
              isCreating || isRefetchingAfterCreate ? "creating" : "loading"
            }
            showOnlyFinalStep={showSimplifiedLoader}
          />
        ) : (
          <Tabs
            value={activeTab}
            onValueChange={(value) => setActiveTab(value as SettingsTab)}
            className="w-full flex-1 flex flex-col min-h-0"
          >
            {/* Tab Navigation */}
            <div className="px-3 sm:px-6 pt-3 sm:pt-4 pb-2 sm:pb-3 border-b bg-muted/20 shrink-0 overflow-x-auto">
              <TabsList
                className={cn(
                  "inline-flex w-auto min-w-full sm:grid sm:w-full sm:max-w-5xl h-9 sm:h-10 bg-background/50 p-1 gap-1 sm:gap-0",
                  "sm:grid-cols-9",
                )}
              >
                <TabsTrigger
                  value="basic"
                  className="gap-1.5 sm:gap-2 px-2.5 sm:px-3 text-xs sm:text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm data-[state=inactive]:hover:bg-yellow-light transition-colors whitespace-nowrap"
                >
                  <User className="size-3.5 sm:size-4" />
                  <span className="hidden sm:inline">Basic Info</span>
                </TabsTrigger>

                <TabsTrigger
                  value="avatar"
                  className="gap-1.5 sm:gap-2 px-2.5 sm:px-3 text-xs sm:text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm data-[state=inactive]:hover:bg-yellow-light transition-colors whitespace-nowrap"
                >
                  <Camera className="size-3.5 sm:size-4" />
                  <span className="hidden sm:inline">Avatar</span>
                </TabsTrigger>

                <TabsTrigger
                  value="prompt"
                  className="gap-1.5 sm:gap-2 px-2.5 sm:px-3 text-xs sm:text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm data-[state=inactive]:hover:bg-yellow-light transition-colors whitespace-nowrap"
                >
                  <MessageSquare className="size-3.5 sm:size-4" />
                  <span className="hidden sm:inline">Prompt</span>
                </TabsTrigger>

                <TabsTrigger
                  value="voice"
                  className="gap-1.5 sm:gap-2 px-2.5 sm:px-3 text-xs sm:text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm data-[state=inactive]:hover:bg-yellow-light transition-colors whitespace-nowrap"
                >
                  <Mic className="size-3.5 sm:size-4" />
                  <span className="hidden sm:inline">Voice</span>
                </TabsTrigger>

                <TabsTrigger
                  value="language"
                  className="gap-1.5 sm:gap-2 px-2.5 sm:px-3 text-xs sm:text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm data-[state=inactive]:hover:bg-yellow-light transition-colors whitespace-nowrap"
                >
                  <Globe className="size-3.5 sm:size-4" />
                  <span className="hidden sm:inline">Language</span>
                </TabsTrigger>

                <TabsTrigger
                  value="email"
                  className="gap-1.5 sm:gap-2 px-2.5 sm:px-3 text-xs sm:text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm data-[state=inactive]:hover:bg-yellow-light transition-colors whitespace-nowrap"
                >
                  <Mail className="size-3.5 sm:size-4" />
                  <span className="hidden sm:inline">Email</span>
                </TabsTrigger>

                <TabsTrigger
                  value="calendar"
                  className="gap-1.5 sm:gap-2 px-2.5 sm:px-3 text-xs sm:text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm data-[state=inactive]:hover:bg-yellow-light transition-colors whitespace-nowrap"
                >
                  <Calendar className="size-3.5 sm:size-4" />
                  <span className="hidden sm:inline">Calendar</span>
                </TabsTrigger>

                <TabsTrigger
                  value="session"
                  className="gap-1.5 sm:gap-2 px-2.5 sm:px-3 text-xs sm:text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm data-[state=inactive]:hover:bg-yellow-light transition-colors whitespace-nowrap"
                >
                  <Timer className="size-3.5 sm:size-4" />
                  <span className="hidden sm:inline">Session</span>
                </TabsTrigger>

                <TabsTrigger
                  value="monetization"
                  className="gap-1.5 sm:gap-2 px-2.5 sm:px-3 text-xs sm:text-sm data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-sm data-[state=inactive]:hover:bg-yellow-light transition-colors whitespace-nowrap"
                >
                  <DollarSign className="size-3.5 sm:size-4" />
                  <span className="hidden sm:inline">Money</span>
                </TabsTrigger>
              </TabsList>
            </div>

            {/* Tab Content */}
            <TabsContent
              value="basic"
              className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-0 min-h-0"
            >
              <BasicInfoTab
                persona={persona}
                basicInfo={state.basicInfo}
                onChange={state.updateBasicInfo}
              />
            </TabsContent>

            <TabsContent
              value="avatar"
              className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-0 min-h-0"
            >
              <AvatarTab
                personaId={persona.id}
                personaName={persona.name}
                currentAvatarUrl={persona.persona_avatar_url}
                userAvatarUrl={user?.avatar ?? undefined}
              />
            </TabsContent>

            <TabsContent
              value="prompt"
              className="flex-1 overflow-hidden mt-0 min-h-0"
            >
              <PromptTab
                promptFields={promptFields}
                onChange={(updates) =>
                  setPromptFields((prev) => ({ ...prev, ...updates }))
                }
              />
            </TabsContent>

            <TabsContent
              value="voice"
              className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-0 min-h-0"
            >
              <VoiceTab
                voiceId={state.voiceId}
                onChange={(voiceId) => state.setVoiceId(voiceId)}
                voiceEnabled={state.voiceEnabled}
                onVoiceEnabledChange={state.setVoiceEnabled}
              />
            </TabsContent>

            <TabsContent
              value="language"
              className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-0 min-h-0"
            >
              <LanguageTab
                language={state.language}
                savedLanguage={state.language}
                onChange={(language) => state.setLanguage(language)}
              />
            </TabsContent>

            <TabsContent
              value="email"
              className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-0 min-h-0"
            >
              <EmailCaptureTab
                personaId={persona.id}
                emailCapture={state.emailCapture}
                onChange={state.updateEmailCapture}
                emailThresholdDisplay={state.emailThresholdDisplay}
                setEmailThresholdDisplay={state.setEmailThresholdDisplay}
                sendSummaryEmailEnabled={state.sendSummaryEmailEnabled}
                onSummaryEmailChange={state.setSendSummaryEmailEnabled}
              />
            </TabsContent>

            <TabsContent
              value="calendar"
              className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-0 min-h-0"
            >
              <CalendarTab
                calendar={state.calendar}
                onChange={state.updateCalendar}
                calendarUrlError={state.calendarUrlError}
                setCalendarUrlError={state.setCalendarUrlError}
              />
            </TabsContent>

            <TabsContent
              value="session"
              className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-0 min-h-0"
            >
              <SessionLimitTab
                sessionTimeLimit={state.sessionTimeLimit}
                onChange={state.updateSessionTimeLimit}
              />
            </TabsContent>

            <TabsContent
              value="monetization"
              className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-0 min-h-0"
            >
              <MonetizationTab
                personaId={persona.id}
                monetization={state.monetization}
                onChange={state.updateMonetization}
                priceDisplay={state.priceDisplay}
                setPriceDisplay={state.setPriceDisplay}
              />
            </TabsContent>
          </Tabs>
        )}

        {/* Save Button Footer */}
        {!showLoadingOverlay && (
          <DialogFooter className="px-4 sm:px-6 py-3 sm:py-4 border-t shrink-0 bg-muted/10">
            <SaveButton onClick={handleSave} isSaving={isSaving} />
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
