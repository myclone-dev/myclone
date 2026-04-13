"use client";

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Users, MessageSquare, Sparkles, Loader2 } from "lucide-react";
import { toast } from "sonner";
import * as Sentry from "@sentry/nextjs";
import type { PersonaPromptFields } from "@/lib/queries/prompt";
import { useGenerateChatConfig } from "@/lib/queries/prompt";

interface PersonaPromptStepProps {
  values: PersonaPromptFields;
  onChange: (values: PersonaPromptFields) => void;
  isLoadingPrefill?: boolean;
  /** Persona details from step 1 for generating chat config */
  personaDetails?: {
    name: string;
    role: string;
    expertise: string;
  };
}

export function PersonaPromptStep({
  values,
  onChange,
  personaDetails,
}: PersonaPromptStepProps) {
  const { mutateAsync: generateChatConfig, isPending: isGenerating } =
    useGenerateChatConfig();

  const updateField = <K extends keyof PersonaPromptFields>(
    field: K,
    value: PersonaPromptFields[K],
  ) => {
    onChange({ ...values, [field]: value });
  };

  const handleGenerateChatConfig = async () => {
    if (
      !personaDetails?.name?.trim() ||
      !personaDetails?.role?.trim() ||
      !personaDetails?.expertise?.trim()
    ) {
      toast.error("Missing persona details", {
        description: "Please fill in persona name, role, and expertise first.",
      });
      return;
    }

    try {
      const result = await generateChatConfig({
        persona_name: personaDetails.name.trim(),
        role: personaDetails.role.trim(),
        expertise: personaDetails.expertise.trim(),
      });

      if (result.chat_objective) {
        onChange({
          ...values,
          chat_objective: result.chat_objective,
          target_audience:
            result.target_audience || values.target_audience || "",
        });
        toast.success("Generated chat configuration");
      } else {
        toast.warning("Partial generation", {
          description:
            result.message || "Could not fully generate chat config.",
        });
      }
    } catch (error) {
      Sentry.captureException(error, {
        tags: { operation: "chat_config_generate" },
        contexts: {
          persona: {
            name: personaDetails?.name,
            role: personaDetails?.role,
            expertise: personaDetails?.expertise,
          },
        },
      });
      toast.error("Failed to generate chat configuration", {
        description:
          error instanceof Error
            ? error.message
            : "Please try again or fill in manually.",
      });
    }
  };

  const canGenerate =
    personaDetails?.name?.trim() &&
    personaDetails?.role?.trim() &&
    personaDetails?.expertise?.trim();

  return (
    <div className="space-y-4 sm:space-y-5">
      {/* Generate Button */}
      <div className="flex items-start sm:items-center justify-between gap-2">
        <p className="text-xs sm:text-sm text-muted-foreground flex-1">
          Configure how your persona responds to users
        </p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleGenerateChatConfig}
          disabled={isGenerating || !canGenerate}
          className="gap-2 text-xs shrink-0"
        >
          {isGenerating ? (
            <>
              <Loader2 className="size-3 animate-spin" />
              <span className="hidden sm:inline">Generating...</span>
              <span className="sm:hidden">...</span>
            </>
          ) : (
            <>
              <Sparkles className="size-3" />
              Generate
            </>
          )}
        </Button>
      </div>

      {/* Chat Objective */}
      <div id="chat-objective-field" className="space-y-2">
        <Label
          htmlFor="chat_objective"
          className="flex items-center gap-2 text-sm"
        >
          <MessageSquare className="size-3 sm:size-4 text-ai-brown" />
          Chat Objective
          <span className="text-destructive">*</span>
        </Label>
        <Textarea
          id="chat_objective"
          placeholder="What should this persona help users achieve?"
          value={values.chat_objective || ""}
          onChange={(e) => updateField("chat_objective", e.target.value)}
          maxLength={500}
          rows={3}
          className="resize-none text-sm sm:text-base"
          required
        />
        <p className="text-xs text-muted-foreground">
          Example: &quot;Help users understand machine learning concepts and
          guide them through practical implementations&quot;
        </p>
      </div>

      {/* Target Audience */}
      <div id="target-audience-field" className="space-y-2">
        <Label
          htmlFor="target_audience"
          className="flex items-center gap-2 text-sm"
        >
          <Users className="size-3 sm:size-4 text-ai-brown" />
          Target Audience
        </Label>
        <Input
          id="target_audience"
          placeholder="e.g., ML beginners to intermediate practitioners"
          value={values.target_audience || ""}
          onChange={(e) => updateField("target_audience", e.target.value)}
          maxLength={200}
          className="text-sm sm:text-base"
        />
      </div>

      {/* Response Settings */}
      <div
        id="response-settings"
        className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"
      >
        <div className="space-y-2">
          <Label htmlFor="response_length" className="text-sm">
            Response Length
          </Label>
          <Select
            value={values.response_structure?.response_length || "explanatory"}
            onValueChange={(value) =>
              updateField("response_structure", {
                response_length: value as
                  | "intelligent"
                  | "concise"
                  | "explanatory"
                  | "custom",
                creativity: values.response_structure?.creativity || "adaptive",
              })
            }
          >
            <SelectTrigger
              id="response_length"
              className="text-sm sm:text-base"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="intelligent" className="text-sm">
                Intelligent (Auto)
              </SelectItem>
              <SelectItem value="concise" className="text-sm">
                Concise
              </SelectItem>
              <SelectItem value="explanatory" className="text-sm">
                Explanatory
              </SelectItem>
              <SelectItem value="custom" className="text-sm">
                Custom
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="creativity" className="text-sm">
            Creativity Level
          </Label>
          <Select
            value={values.response_structure?.creativity || "adaptive"}
            onValueChange={(value) =>
              updateField("response_structure", {
                response_length:
                  values.response_structure?.response_length || "explanatory",
                creativity: value as "strict" | "adaptive" | "creative",
              })
            }
          >
            <SelectTrigger id="creativity" className="text-sm sm:text-base">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="strict" className="text-sm">
                Strict (Factual)
              </SelectItem>
              <SelectItem value="adaptive" className="text-sm">
                Adaptive (Balanced)
              </SelectItem>
              <SelectItem value="creative" className="text-sm">
                Creative
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Info Box */}
      <div className="rounded-lg bg-muted/50 p-3 sm:p-4 text-xs sm:text-sm text-muted-foreground">
        <p className="font-medium mb-1 sm:mb-2">Why configure this?</p>
        <p>
          These settings help generate personalized suggested questions and
          optimize the chat experience for your specific use case. You can
          access advanced settings anytime from the persona&apos;s Settings
          menu.
        </p>
      </div>
    </div>
  );
}
