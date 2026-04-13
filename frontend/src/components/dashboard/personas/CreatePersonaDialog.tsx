"use client";

import React, { useState, useEffect } from "react";
import { useNextStep } from "nextstepjs";
import {
  isOnboardingInProgress,
  getCurrentOnboardingStep,
  hasSkippedPersonaCreationTour,
} from "@/lib/utils/onboardingProgress";
import Link from "next/link";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Plus,
  Linkedin,
  Twitter,
  Globe,
  FileText,
  Youtube,
  Database,
  Mic,
  Sparkles,
  AlertCircle,
  ChevronDown,
  Loader2,
  Check,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";
import { useKnowledgeLibrary } from "@/lib/queries/knowledge";
import { useUserMe } from "@/lib/queries/users/useUserMe";
import { cn } from "@/lib/utils";
import { useUserPersonas } from "@/lib/queries/persona";
import { useVoiceClones } from "@/lib/queries/voice-clone";
import { TIER_BUSINESS } from "@/lib/queries/voice-clone/interface";
import { useUserSubscription } from "@/lib/queries/tier";
import {
  type PersonaPromptFields,
  usePersonaPrefill,
} from "@/lib/queries/prompt";
import { PersonaPromptStep } from "./PersonaPromptStep";
import { env } from "@/env";
import { usePersonaNameValidation } from "@/hooks/usePersonaNameValidation";

type SourceType = "linkedin" | "twitter" | "website" | "document" | "youtube";

interface CreatePersonaDialogProps {
  onCreatePersona: (
    persona: {
      personaName: string; // Identifier (username)
      name: string; // Display name
      role: string;
      expertise: string;
      description: string;
      voice_id?: string;
      knowledgeSources: Array<{
        source_type: SourceType;
        source_record_id: string;
      }>;
    },
    promptFields?: PersonaPromptFields,
  ) => void;
  /** Whether the user can create a new persona based on tier limits */
  canCreate?: boolean;
  /** Reason why user cannot create persona (for tooltip/display) */
  limitReason?: string;
  /** Current persona count */
  currentCount?: number;
  /** Maximum personas allowed (-1 = unlimited) */
  maxPersonas?: number;
}

interface KnowledgeSourceItem {
  id: string;
  type: SourceType;
  name: string;
  items_count: number;
  icon?: LucideIcon;
}

interface CategoryGroup {
  title: string;
  icon: LucideIcon;
  colorClass: string;
  bgClass: string;
  sources: KnowledgeSourceItem[];
}

// Helper function to get category styles
const getCategoryStyles = (type: string) => {
  const styles = {
    linkedin: {
      colorClass: "text-[hsl(210.4_100%_41.4%)]",
      bgClass: "bg-[hsl(210.4_100%_41.4%)]/10",
    },
    twitter: {
      colorClass: "text-[hsl(203_89%_53%)]",
      bgClass: "bg-[hsl(203_89%_53%)]/10",
    },
    website: {
      colorClass: "text-[hsl(262.1_83.3%_57.8%)]",
      bgClass: "bg-[hsl(262.1_83.3%_57.8%)]/10",
    },
    document: {
      colorClass: "text-[hsl(24.6_95%_53.1%)]",
      bgClass: "bg-[hsl(24.6_95%_53.1%)]/10",
    },
    youtube: {
      colorClass: "text-[hsl(0_100%_50%)]",
      bgClass: "bg-[hsl(0_100%_50%)]/10",
    },
  };
  return styles[type as keyof typeof styles] || styles.document;
};

export function CreatePersonaDialog({
  onCreatePersona,
  canCreate = true,
  limitReason,
  currentCount = 0,
  maxPersonas = -1,
}: CreatePersonaDialogProps) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [name, setName] = useState(""); // Display name
  const [role, setRole] = useState("");
  const [expertise, setExpertise] = useState("");
  const [knowledgeSources, setKnowledgeSources] = useState<
    Record<string, { type: SourceType; enabled: boolean }>
  >({});
  // Track which knowledge source categories are expanded (all collapsed by default on mobile)
  const [expandedCategories, setExpandedCategories] = useState<
    Record<string, boolean>
  >({});
  const [promptFields, setPromptFields] = useState<PersonaPromptFields>({
    introduction: "",
    area_of_expertise: "",
    chat_objective: "",
    target_audience: "",
    response_structure: {
      response_length: "explanatory",
      creativity: "adaptive",
    },
    is_dynamic: false,
    thinking_style: "",
    objective_response: "",
    example_responses: "",
    example_prompt: "",
    conversation_flow: "",
  });

  // Fetch user, knowledge library, voice clones, personas, and subscription
  const { data: user } = useUserMe();
  const { data: libraryData, isLoading: libraryLoading } = useKnowledgeLibrary(
    user?.id || "",
  );
  const { data: voiceClones, isLoading: voiceClonesLoading } = useVoiceClones(
    user?.id,
  );
  const { data: personasData } = useUserPersonas(user?.id || "");
  const { data: subscription } = useUserSubscription();
  const { startNextStep } = useNextStep();

  // Validate persona name with debouncing and API check
  const nameValidation = usePersonaNameValidation(name);

  // Check if user has Business or Enterprise tier (can select multiple voices)
  const canSelectMultipleVoices = (subscription?.tier_id ?? 0) >= TIER_BUSINESS;

  // State for selected voice
  const [selectedVoiceId, setSelectedVoiceId] = useState<string | undefined>(
    undefined,
  );

  // Get base URL for helper text
  const baseUrl = env.NEXT_PUBLIC_APP_URL.endsWith("/")
    ? env.NEXT_PUBLIC_APP_URL.slice(0, -1)
    : env.NEXT_PUBLIC_APP_URL;

  // Fetch prefill data from default persona (first persona)
  const defaultPersonaId =
    personasData?.personas && personasData.personas.length > 0
      ? personasData.personas[0].id
      : null;

  const { data: prefillData } = usePersonaPrefill(defaultPersonaId || "", {
    enabled: open && step === 2 && !!defaultPersonaId, // Only fetch when dialog opens to step 2 and we have a persona
  });

  // Reset form function to avoid repetition
  const resetForm = () => {
    setStep(1);
    setName("");
    setRole("");
    setExpertise("");
    setKnowledgeSources({});
    setSelectedVoiceId(undefined);
    setExpandedCategories({});
    setPromptFields({
      introduction: "",
      area_of_expertise: "",
      chat_objective: "",
      target_audience: "",
      response_structure: {
        response_length: "explanatory",
        creativity: "adaptive",
      },
      is_dynamic: false,
      thinking_style: "",
      objective_response: "",
      example_responses: "",
      example_prompt: "",
      conversation_flow: "",
    });
  };

  // Toggle category expansion
  const toggleCategory = (categoryTitle: string) => {
    setExpandedCategories((prev) => ({
      ...prev,
      [categoryTitle]: !prev[categoryTitle],
    }));
  };

  // Get selected count for a category
  const getSelectedCountForCategory = (sources: KnowledgeSourceItem[]) => {
    return sources.filter((s) => knowledgeSources[s.id]?.enabled).length;
  };

  // Set default voice when voice clones are loaded
  React.useEffect(() => {
    if (voiceClones && voiceClones.length > 0 && !selectedVoiceId) {
      setSelectedVoiceId(voiceClones[0].voice_id);
    }
  }, [voiceClones, selectedVoiceId]);

  // Populate prompt fields with prefill data when available
  React.useEffect(() => {
    if (prefillData && open && step === 2) {
      setPromptFields((prev) => ({
        ...prev,
        introduction: prev.introduction || prefillData.introduction || "",
        area_of_expertise:
          prev.area_of_expertise || prefillData.area_of_expertise || "",
      }));
    }
  }, [prefillData, open, step]);

  // Prefill role and expertise from user profile or LinkedIn data when dialog opens
  React.useEffect(() => {
    if (open && step === 1) {
      // Try to prefill role:
      // 1. First priority: User's saved role in profile
      // 2. Second priority: Latest LinkedIn experience title (most recent job)
      // 3. Fallback: LinkedIn headline
      if (!role) {
        const userRole = user?.role;
        const latestExperienceTitle =
          libraryData?.linkedin?.[0]?.latest_experience_title;
        const linkedInHeadline = libraryData?.linkedin?.[0]?.headline;

        if (userRole) {
          setRole(userRole);
        } else if (latestExperienceTitle) {
          setRole(latestExperienceTitle);
        } else if (linkedInHeadline) {
          setRole(linkedInHeadline);
        }
      }

      // Try to prefill expertise (only if user hasn't entered anything yet):
      // 1. First priority: LLM-generated expertise from user profile (short, concise)
      // 2. Fallback: LinkedIn summary (first 200 chars)
      if (!expertise) {
        const llmExpertise = user?.llm_generated_expertise;
        const linkedInSummary = libraryData?.linkedin?.[0]?.summary;

        if (llmExpertise) {
          setExpertise(llmExpertise);
        } else if (linkedInSummary) {
          setExpertise(
            linkedInSummary.length > 200
              ? linkedInSummary.substring(0, 200)
              : linkedInSummary,
          );
        }
      }
    }
    // Only run when dialog opens or library data loads, not when role/expertise change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    open,
    step,
    user?.role,
    user?.llm_generated_expertise,
    libraryData?.linkedin,
  ]);

  // Trigger tour when dialog opens for first-time users (Step 1)
  useEffect(() => {
    if (!open) return;

    // Don't show tour if user has skipped it before
    if (hasSkippedPersonaCreationTour()) return;

    if (
      isOnboardingInProgress() &&
      getCurrentOnboardingStep() === "persona" &&
      step === 1
    ) {
      console.log("👤 [Onboarding] Starting persona creation step 1 tour...");
      // Small delay to ensure DOM is ready
      const timer = setTimeout(() => {
        startNextStep("persona-creation-step-1");
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [open, step, startNextStep]);

  // Trigger tours when step changes (Steps 2 and 3)
  useEffect(() => {
    if (!open) return;
    if (!isOnboardingInProgress() || getCurrentOnboardingStep() !== "persona")
      return;
    // Don't show tour if user has skipped it before
    if (hasSkippedPersonaCreationTour()) return;

    const timer = setTimeout(() => {
      if (step === 2) {
        console.log("👤 [Onboarding] Starting persona creation step 2 tour...");
        startNextStep("persona-creation-step-2");
      } else if (step === 3) {
        console.log("👤 [Onboarding] Starting persona creation step 3 tour...");
        startNextStep("persona-creation-step-3");
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [step, open, startNextStep]);

  // Build categorized knowledge sources
  const categorizedSources: CategoryGroup[] = libraryData
    ? [
        {
          title: "LinkedIn",
          icon: Linkedin,
          ...getCategoryStyles("linkedin"),
          sources: libraryData.linkedin.map((s) => ({
            id: s.id,
            type: s.type,
            name: s.display_name,
            items_count: s.embeddings_count,
            icon: Linkedin,
          })),
        },
        {
          title: "Twitter",
          icon: Twitter,
          ...getCategoryStyles("twitter"),
          sources: libraryData.twitter.map((s) => ({
            id: s.id,
            type: s.type,
            name: s.display_name,
            items_count: s.embeddings_count,
            icon: Twitter,
          })),
        },
        {
          title: "Websites",
          icon: Globe,
          ...getCategoryStyles("website"),
          sources: libraryData.websites.map((s) => ({
            id: s.id,
            type: s.type,
            name: s.display_name,
            items_count: s.embeddings_count,
            icon: Globe,
          })),
        },
        {
          title: "Documents",
          icon: FileText,
          ...getCategoryStyles("document"),
          sources: libraryData.documents.map((s) => ({
            id: s.id,
            type: s.type,
            name: s.display_name,
            items_count: s.embeddings_count,
            icon: FileText,
          })),
        },
        {
          title: "YouTube",
          icon: Youtube,
          ...getCategoryStyles("youtube"),
          sources: libraryData.youtube.map((s) => ({
            id: s.id,
            type: s.type,
            name: s.display_name,
            items_count: s.embeddings_count,
            icon: Youtube,
          })),
        },
      ].filter((category) => category.sources.length > 0)
    : [];

  const totalSources = categorizedSources.reduce(
    (sum, cat) => sum + cat.sources.length,
    0,
  );

  const hasNoDataSources = !libraryLoading && totalSources === 0;

  const handleNameChange = (value: string) => {
    setName(value);
  };

  const handleNext = () => {
    if (!name.trim()) {
      toast.error("Please enter a persona name");
      return;
    }

    // Check if name is still being validated
    if (nameValidation.isChecking) {
      toast.error("Please wait while we check the name availability");
      return;
    }

    // Check if name is valid
    if (!nameValidation.isValid) {
      toast.error("Persona name not available", {
        description: nameValidation.error || undefined,
      });
      return;
    }

    if (!nameValidation.slugifiedName) {
      toast.error("Invalid persona name");
      return;
    }

    if (!role.trim()) {
      toast.error("Please enter a role");
      return;
    }

    if (!expertise.trim()) {
      toast.error("Please enter expertise");
      return;
    }
    setStep(2);
  };

  const handleNextPrompt = () => {
    setStep(3);
  };

  const handleBack = () => {
    if (step === 2) {
      setStep(1);
    } else if (step === 3) {
      setStep(2);
    }
  };

  const handleCreate = () => {
    // Ensure we have a valid slugified name
    if (!nameValidation.slugifiedName) {
      toast.error("Invalid persona name");
      return;
    }

    // Convert knowledge sources map to API format (allow empty array)
    const knowledgeSourcesArray = Object.entries(knowledgeSources)
      .filter(([_, value]) => value.enabled)
      .map(([sourceId, value]) => ({
        source_type: value.type,
        source_record_id: sourceId,
      }));

    // Call parent handler - dialog closes immediately
    onCreatePersona(
      {
        personaName: nameValidation.slugifiedName, // Slugified identifier from backend
        name: name.trim(), // Display name
        role: role.trim(),
        expertise: expertise.trim(),
        description: "", // Description is now auto-generated by backend
        voice_id: selectedVoiceId,
        knowledgeSources: knowledgeSourcesArray,
      },
      promptFields,
    );

    // Reset form and close dialog immediately
    resetForm();
    setOpen(false);
  };

  const toggleKnowledgeSource = (sourceId: string, sourceType: SourceType) => {
    setKnowledgeSources((prev) => ({
      ...prev,
      [sourceId]: {
        type: sourceType,
        enabled: !prev[sourceId]?.enabled,
      },
    }));
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen) {
      resetForm();
    }
    setOpen(newOpen);
  };

  const selectedCount = Object.values(knowledgeSources).filter(
    (v) => v.enabled,
  ).length;

  const getStepTitle = () => {
    switch (step) {
      case 1:
        return "Create New Persona";
      case 2:
        return "Configure Chat Behavior";
      case 3:
        return "Select Knowledge & Voice";
      default:
        return "";
    }
  };

  const getStepDescription = () => {
    switch (step) {
      case 1:
        return "Step 1 of 3: Define your persona's basic information";
      case 2:
        return "Step 2 of 3: Configure how your persona responds to users";
      case 3:
        return "Step 3 of 3: Choose knowledge sources and voice (optional)";
      default:
        return "";
    }
  };

  // Badge component for persona count - ensures consistent styling
  const PersonaLimitBadge = () => {
    if (maxPersonas === -1) return null;
    return (
      <Badge variant="outline" className="ml-1 text-xs bg-background">
        {currentCount}/{maxPersonas}
      </Badge>
    );
  };

  // If limit is reached, show disabled button with tooltip
  if (!canCreate) {
    return (
      <Button
        className="gap-2"
        variant="secondary"
        disabled
        title={limitReason || "Persona limit reached"}
      >
        <Plus className="size-4" />
        New Persona
        <PersonaLimitBadge />
      </Button>
    );
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button className="gap-2">
          <Plus className="size-4" />
          New Persona
          <PersonaLimitBadge />
        </Button>
      </DialogTrigger>
      <DialogContent
        className={cn(
          // Base styles
          "p-0 shadow-2xl gap-0 flex flex-col",
          // Mobile: Full screen with slide-up animation
          "max-sm:w-full max-sm:h-full max-sm:max-w-full max-sm:max-h-full",
          "max-sm:rounded-none max-sm:border-0",
          "max-sm:top-0 max-sm:left-0 max-sm:translate-x-0 max-sm:translate-y-0",
          "max-sm:data-[state=open]:slide-in-from-bottom-full max-sm:data-[state=closed]:slide-out-to-bottom-full",
          "max-sm:data-[state=open]:zoom-in-100 max-sm:data-[state=closed]:zoom-out-100",
          // Desktop: Centered modal
          "sm:w-[95vw] sm:max-w-[90vw] md:max-w-[700px] sm:max-h-[92vh] sm:h-auto",
        )}
        onInteractOutside={(e) => {
          // Prevent closing when:
          // 1. Clicking on tour cards
          // 2. Clicking on any radix portaled elements (dropdowns, etc.)
          // 3. During onboarding
          const target = e.target as HTMLElement;
          if (
            target.closest("[data-nextstepjs-tour-card]") ||
            target.closest("[data-radix-popper-content-wrapper]") ||
            target.closest('[role="listbox"]') ||
            target.closest('[role="option"]') ||
            (isOnboardingInProgress() &&
              getCurrentOnboardingStep() === "persona")
          ) {
            e.preventDefault();
          }
        }}
      >
        <div className="flex flex-col h-full sm:max-h-[92vh] min-w-0 overflow-hidden">
          {/* Header with step indicator */}
          <DialogHeader className="px-4 sm:px-6 pt-4 sm:pt-6 pb-3 sm:pb-4 border-b shrink-0 bg-background">
            {/* Step Progress Indicator - Mobile */}
            <div className="flex items-center justify-center gap-1.5 mb-3 sm:hidden">
              {[1, 2, 3].map((s) => (
                <div
                  key={s}
                  className={cn(
                    "h-1.5 rounded-full transition-all duration-300",
                    s === step
                      ? "w-8 bg-primary"
                      : s < step
                        ? "w-4 bg-primary/60"
                        : "w-4 bg-muted",
                  )}
                />
              ))}
            </div>
            <DialogTitle className="text-lg sm:text-xl">
              {getStepTitle()}
            </DialogTitle>
            <DialogDescription className="text-xs sm:text-sm">
              {getStepDescription()}
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto overflow-x-hidden px-4 sm:px-6">
            {step === 1 ? (
              <div className="space-y-4 py-4">
                <div id="persona-name-field" className="space-y-2">
                  <Label htmlFor="name" className="text-sm">
                    Persona Name *
                  </Label>
                  <div className="relative">
                    <Input
                      id="name"
                      placeholder="e.g., Tech Advisor"
                      value={name}
                      onChange={(e) => handleNameChange(e.target.value)}
                      maxLength={100}
                      className={cn(
                        "text-sm sm:text-base pr-10",
                        nameValidation.error && name.length > 0
                          ? "border-red-500"
                          : nameValidation.isValid
                            ? "border-green-500"
                            : "",
                      )}
                    />
                    {/* Validation indicator */}
                    <div
                      className="absolute right-3 top-1/2 -translate-y-1/2 h-5 w-5"
                      translate="no"
                    >
                      {name && name.length > 0 ? (
                        nameValidation.isChecking ? (
                          <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                        ) : nameValidation.isValid ? (
                          <Check className="h-5 w-5 text-green-500" />
                        ) : null
                      ) : null}
                    </div>
                  </div>

                  {/* Validation feedback */}
                  <div className="min-h-[20px]" translate="no">
                    {name && name.length > 0 ? (
                      nameValidation.isChecking ? (
                        <p className="flex items-center gap-1 text-xs text-blue-600 sm:text-sm">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Checking availability...
                        </p>
                      ) : nameValidation.error ? (
                        <p className="text-xs text-red-600 sm:text-sm">
                          {nameValidation.error}
                        </p>
                      ) : nameValidation.isValid ? (
                        <p className="flex items-center gap-1 text-xs text-green-600 sm:text-sm">
                          <Check className="h-4 w-4" />
                          Persona name is available!
                        </p>
                      ) : null
                    ) : null}
                  </div>

                  <p className="text-xs text-muted-foreground">
                    The friendly name shown to users (can be changed later)
                  </p>

                  {nameValidation.slugifiedName &&
                    nameValidation.isValid &&
                    !nameValidation.isChecking &&
                    user?.username && (
                      <p className="text-xs text-muted-foreground">
                        URL: {baseUrl}/{user.username}/
                        <strong>{nameValidation.slugifiedName}</strong>
                      </p>
                    )}
                </div>
                <div id="persona-role-field" className="space-y-2">
                  <Label htmlFor="role" className="text-sm">
                    Role *
                  </Label>
                  <Input
                    id="role"
                    placeholder="e.g., AI Consultant"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    maxLength={100}
                    className="text-sm sm:text-base"
                  />
                </div>
                <div id="persona-expertise-field" className="space-y-2">
                  <Label htmlFor="expertise" className="text-sm">
                    Expertise *
                  </Label>
                  <Input
                    id="expertise"
                    placeholder="e.g., Deep learning, model training, Speech synthesis"
                    value={expertise}
                    onChange={(e) => setExpertise(e.target.value)}
                    maxLength={200}
                    className="text-sm sm:text-base"
                  />
                </div>
              </div>
            ) : step === 2 ? (
              <div className="py-4">
                <PersonaPromptStep
                  values={promptFields}
                  onChange={setPromptFields}
                  personaDetails={{
                    name: name.trim(),
                    role: role.trim(),
                    expertise: expertise.trim(),
                  }}
                />
              </div>
            ) : (
              <div className="space-y-4 py-4 min-w-0">
                {/* Voice Selection Section */}
                <div id="voice-select-field" className="space-y-3 min-w-0">
                  <h3 className="text-sm sm:text-base font-semibold flex items-center gap-2">
                    <Mic className="size-4 sm:size-5 text-ai-brown" />
                    Voice
                  </h3>
                  {voiceClonesLoading ? (
                    <Skeleton className="h-16 rounded-lg" />
                  ) : voiceClones && voiceClones.length > 0 ? (
                    // User has voice clones
                    canSelectMultipleVoices && voiceClones.length > 1 ? (
                      // Business/Enterprise tier with multiple voices - show dropdown
                      <div className="rounded-lg border bg-muted/30 p-3 sm:p-4 space-y-3">
                        <div className="flex items-center gap-2 sm:gap-3">
                          <div className="flex size-10 sm:size-12 shrink-0 items-center justify-center rounded-full bg-ai-brown/10">
                            <Mic className="size-5 sm:size-6 text-ai-brown" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm sm:text-base font-medium">
                              Select Voice
                            </p>
                            <p className="text-xs text-muted-foreground">
                              Choose from your {voiceClones.length} cloned
                              voices
                            </p>
                          </div>
                        </div>
                        <Select
                          value={selectedVoiceId}
                          onValueChange={setSelectedVoiceId}
                        >
                          <SelectTrigger className="w-full">
                            <SelectValue placeholder="Select a voice" />
                          </SelectTrigger>
                          <SelectContent>
                            {voiceClones.map((voice) => (
                              <SelectItem
                                key={voice.voice_id}
                                value={voice.voice_id}
                              >
                                <div className="flex items-center gap-2">
                                  <Mic className="size-3.5 text-ai-brown" />
                                  <span>{voice.name}</span>
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    ) : (
                      // Free/Pro tier or single voice - show static display
                      <div className="rounded-lg border bg-muted/30 p-3 sm:p-4 overflow-hidden">
                        <div className="flex items-center gap-2 sm:gap-3 w-full">
                          <div className="flex size-10 sm:size-12 shrink-0 items-center justify-center rounded-full bg-ai-brown/10">
                            <Mic className="size-5 sm:size-6 text-ai-brown" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm sm:text-base font-medium truncate">
                              {voiceClones[0].name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              Your cloned voice
                            </p>
                          </div>
                          <Badge className="bg-green-100 text-green-800 border-green-300 text-xs shrink-0 whitespace-nowrap">
                            Active
                          </Badge>
                        </div>
                      </div>
                    )
                  ) : (
                    // No voice clone - show default with create button
                    <div className="rounded-lg border border-dashed p-3 sm:p-4">
                      <div className="flex items-center gap-3">
                        <div className="flex size-10 sm:size-12 shrink-0 items-center justify-center rounded-full bg-muted">
                          <Mic className="size-5 sm:size-6 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm sm:text-base font-medium">
                            Default Voice
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Using system default voice
                          </p>
                        </div>
                      </div>
                      <div className="mt-3 pt-3 border-t">
                        <Link
                          href="/dashboard/voice-clone"
                          className="inline-flex items-center gap-2 text-xs sm:text-sm font-medium text-ai-brown hover:text-ai-brown/80 transition-colors"
                          onClick={() => setOpen(false)}
                        >
                          <Sparkles className="size-3.5 sm:size-4" />
                          Create your own voice clone
                        </Link>
                      </div>
                    </div>
                  )}
                </div>

                {/* Knowledge Sources Section */}
                <div
                  id="knowledge-sources-list"
                  className="space-y-3 border-t pt-4 min-w-0"
                >
                  <h3 className="text-sm sm:text-base font-semibold flex items-center gap-2">
                    <Database className="size-4 sm:size-5 text-ai-brown" />
                    Select Knowledge Sources
                  </h3>

                  {/* Info banner when no data sources available */}
                  {hasNoDataSources && (
                    <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 sm:p-4">
                      <div className="flex gap-2 sm:gap-3">
                        <AlertCircle className="size-4 sm:size-5 text-blue-600 shrink-0 mt-0.5" />
                        <div className="space-y-1 sm:space-y-2 flex-1">
                          <p className="text-xs sm:text-sm font-medium text-blue-900">
                            No knowledge sources yet
                          </p>
                          <p className="text-[11px] sm:text-xs text-blue-700">
                            You can create the persona now and add knowledge
                            sources later from the{" "}
                            <Link
                              href="/dashboard/knowledge"
                              className="underline font-medium hover:text-blue-900"
                              onClick={() => setOpen(false)}
                            >
                              Knowledge Library
                            </Link>
                            . The persona will work better with knowledge
                            sources added.
                          </p>
                        </div>
                      </div>
                    </div>
                  )}

                  {libraryLoading ? (
                    <div className="space-y-3">
                      {[1, 2, 3].map((i) => (
                        <Skeleton key={i} className="h-16 rounded-lg" />
                      ))}
                    </div>
                  ) : totalSources === 0 ? (
                    <div className="rounded-lg border border-dashed p-4 sm:p-8 text-center">
                      <Database className="mx-auto mb-3 size-8 sm:size-12 text-muted-foreground" />
                      <p className="text-xs sm:text-sm font-medium text-muted-foreground mb-1">
                        No knowledge sources available yet
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Add knowledge sources from the Knowledge Library first.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {/* Selection Summary */}
                      <div className="flex items-center justify-between rounded-lg bg-muted/50 p-2 sm:p-3">
                        <div className="flex items-center gap-2 text-xs sm:text-sm">
                          <Database className="size-3 sm:size-4 text-muted-foreground" />
                          <span className="font-medium">
                            {selectedCount} of {totalSources} selected
                          </span>
                        </div>
                        {selectedCount > 0 && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setKnowledgeSources({})}
                            className="h-7 text-xs"
                          >
                            Clear all
                          </Button>
                        )}
                      </div>

                      {/* Category Sections - Collapsible on mobile */}
                      <ScrollArea className="h-[280px] sm:h-[350px] overflow-x-hidden">
                        <div className="space-y-2 sm:space-y-3 overflow-x-hidden pr-2">
                          {categorizedSources.map((category) => {
                            const isExpanded =
                              expandedCategories[category.title] ?? false;
                            const selectedInCategory =
                              getSelectedCountForCategory(category.sources);

                            return (
                              <Collapsible
                                key={category.title}
                                open={isExpanded}
                                onOpenChange={() =>
                                  toggleCategory(category.title)
                                }
                                className="rounded-lg border bg-card overflow-hidden min-w-0"
                              >
                                {/* Category Header - Clickable to expand/collapse */}
                                <CollapsibleTrigger asChild>
                                  <button
                                    className={`w-full p-2.5 sm:p-3 ${category.bgClass} flex items-center justify-between hover:opacity-90 transition-opacity`}
                                  >
                                    <div className="flex items-center gap-1.5 sm:gap-2">
                                      <category.icon
                                        className={`size-4 sm:size-5 ${category.colorClass}`}
                                      />
                                      <h3 className="font-semibold text-xs sm:text-sm">
                                        {category.title}
                                      </h3>
                                      <Badge
                                        variant="secondary"
                                        className="text-[10px] sm:text-xs px-1.5 sm:px-2"
                                      >
                                        {category.sources.length}
                                      </Badge>
                                      {selectedInCategory > 0 && (
                                        <Badge className="text-[10px] sm:text-xs px-1.5 sm:px-2 bg-green-100 text-green-800 border-green-300">
                                          {selectedInCategory} selected
                                        </Badge>
                                      )}
                                    </div>
                                    <ChevronDown
                                      className={`size-4 text-muted-foreground transition-transform duration-200 ${
                                        isExpanded ? "rotate-180" : ""
                                      }`}
                                    />
                                  </button>
                                </CollapsibleTrigger>

                                {/* Category Sources - Collapsible */}
                                <CollapsibleContent>
                                  <div className="p-1.5 sm:p-2 space-y-1.5 sm:space-y-2 overflow-x-hidden border-t">
                                    {category.sources.map((source) => {
                                      const Icon = source.icon || Database;
                                      return (
                                        <div
                                          key={source.id}
                                          className="flex items-center gap-2 sm:gap-3 rounded-lg border p-2 sm:p-2.5 hover:bg-muted/50 transition-colors min-w-0 overflow-hidden"
                                        >
                                          <div className="flex items-center gap-2 sm:gap-3 flex-1 min-w-0 overflow-hidden">
                                            <div
                                              className={`flex size-8 sm:size-9 shrink-0 items-center justify-center rounded-lg ${category.bgClass}`}
                                            >
                                              <Icon
                                                className={`size-3.5 sm:size-4 ${category.colorClass}`}
                                              />
                                            </div>
                                            <div className="flex-1 min-w-0 overflow-hidden">
                                              <p className="text-xs sm:text-sm font-medium leading-tight break-all line-clamp-2">
                                                {source.name}
                                              </p>
                                            </div>
                                          </div>
                                          <Switch
                                            checked={
                                              knowledgeSources[source.id]
                                                ?.enabled || false
                                            }
                                            onCheckedChange={() =>
                                              toggleKnowledgeSource(
                                                source.id,
                                                source.type,
                                              )
                                            }
                                            className="shrink-0"
                                          />
                                        </div>
                                      );
                                    })}
                                  </div>
                                </CollapsibleContent>
                              </Collapsible>
                            );
                          })}
                        </div>
                      </ScrollArea>

                      <p className="text-[11px] sm:text-xs text-muted-foreground leading-relaxed">
                        You can change these settings later from the persona
                        management page.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="px-4 sm:px-6 pb-4 sm:pb-6 pt-3 sm:pt-4 border-t gap-2 flex-row shrink-0 bg-background">
            {step > 1 && (
              <Button
                variant="outline"
                onClick={handleBack}
                className="text-xs sm:text-sm flex-1 sm:flex-initial"
              >
                Back
              </Button>
            )}
            {step === 1 && (
              <>
                <Button
                  variant="outline"
                  onClick={() => setOpen(false)}
                  className="text-xs sm:text-sm flex-1"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleNext}
                  className="text-xs sm:text-sm flex-1"
                  disabled={
                    !name.trim() ||
                    !role.trim() ||
                    !expertise.trim() ||
                    nameValidation.isChecking ||
                    !nameValidation.isValid ||
                    !nameValidation.slugifiedName
                  }
                >
                  {nameValidation.isChecking ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Checking...
                    </>
                  ) : (
                    "Next: Configure Chat"
                  )}
                </Button>
              </>
            )}
            {step === 2 && (
              <Button
                onClick={handleNextPrompt}
                className="text-xs sm:text-sm flex-1 sm:flex-initial"
              >
                Next: Select Knowledge
              </Button>
            )}
            {step === 3 && (
              <Button
                id="create-persona-submit-button"
                onClick={handleCreate}
                className="gap-2 text-xs sm:text-sm flex-1 sm:flex-initial"
              >
                <Sparkles className="size-3.5 sm:size-4" />
                Create Persona
              </Button>
            )}
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
