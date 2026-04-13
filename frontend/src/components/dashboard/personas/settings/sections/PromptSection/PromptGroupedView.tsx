"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  FileText,
  Target,
  MessageSquare,
  Users,
  Zap,
  Code,
  MessagesSquare,
  Sparkles,
  ShieldCheck,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { PersonaPromptFields } from "@/lib/queries/prompt";
import { PromptField } from "../../../PersonaSettingsDialog/tabs/PromptTab/PromptField";
import type { PromptSection } from "../../../PersonaSettingsDialog/types";

interface PromptGroupedViewProps {
  promptFields: Partial<PersonaPromptFields>;
  onChange: (updates: Partial<PersonaPromptFields>) => void;
}

// Group definitions
const promptGroups = [
  {
    id: "identity",
    title: "About Your Persona",
    icon: FileText,
    description: "Basic identity and expertise",
    defaultOpen: true,
    isOptional: false,
    sections: [
      {
        id: "introduction",
        label: "How should your persona introduce itself?",
        icon: FileText,
        placeholder: "Write a brief introduction...",
        description: "The opening message when someone starts a conversation",
      },
      {
        id: "area_of_expertise",
        label: "What topics can your persona help with?",
        icon: Target,
        placeholder: "List your areas of expertise...",
        description: "Topics and skills this persona specializes in",
      },
    ] as PromptSection[],
  },
  {
    id: "objectives",
    title: "Goals & Audience",
    icon: Target,
    description: "Purpose and target users",
    defaultOpen: true,
    isOptional: false,
    sections: [
      {
        id: "chat_objective",
        label: "What should conversations achieve?",
        icon: MessageSquare,
        placeholder: "Describe the goal of conversations...",
        description:
          "What users should accomplish from talking to this persona",
      },
      {
        id: "target_audience",
        label: "Who will chat with your persona?",
        icon: Users,
        placeholder: "Describe your target audience...",
        description: "The type of people this persona is designed for",
      },
      {
        id: "objective_response",
        label: "How should your persona structure answers?",
        icon: Code,
        placeholder: "Describe your preferred response format...",
        description: "How the persona should format and organize responses",
      },
    ] as PromptSection[],
  },
  {
    id: "communication",
    title: "Communication Style",
    icon: MessagesSquare,
    description: "Personality and conversation approach",
    defaultOpen: false,
    isOptional: true,
    sections: [
      {
        id: "thinking_style",
        label: "How should your persona approach problems?",
        icon: Zap,
        placeholder: "Describe the reasoning style...",
        description: "The persona's problem-solving and communication approach",
      },
      {
        id: "conversation_flow",
        label: "How should conversations progress?",
        icon: MessagesSquare,
        placeholder: "Describe the conversation flow...",
        description: "How the persona should guide the conversation",
      },
    ] as PromptSection[],
  },
  {
    id: "examples",
    title: "Examples & Guardrails",
    icon: ShieldCheck,
    description: "Sample responses and boundaries",
    defaultOpen: false,
    isOptional: true,
    sections: [
      {
        id: "example_responses",
        label: "Show your persona how to respond",
        icon: Sparkles,
        placeholder: "Provide example conversations or responses...",
        description: "Sample exchanges that demonstrate the desired style",
      },
      {
        id: "strict_guideline",
        label: "What should your persona avoid or always do?",
        icon: ShieldCheck,
        placeholder: "Define boundaries and rules...",
        description: "Hard rules and limits for what the persona can/cannot do",
      },
    ] as PromptSection[],
  },
];

export function PromptGroupedView({
  promptFields,
  onChange,
}: PromptGroupedViewProps) {
  const [openGroups, setOpenGroups] = useState<string[]>(
    promptGroups.filter((g) => g.defaultOpen).map((g) => g.id),
  );

  const handleFieldChange = (
    fieldId: keyof PersonaPromptFields,
    value: string,
  ) => {
    onChange({ [fieldId]: value });
  };

  const toggleGroup = (groupId: string) => {
    setOpenGroups((prev) =>
      prev.includes(groupId)
        ? prev.filter((id) => id !== groupId)
        : [...prev, groupId],
    );
  };

  return (
    <div className="space-y-4">
      {promptGroups.map((group) => {
        const GroupIcon = group.icon;
        const isOpen = openGroups.includes(group.id);

        return (
          <Card key={group.id} className="overflow-hidden">
            <Collapsible
              open={isOpen}
              onOpenChange={() => toggleGroup(group.id)}
            >
              <CollapsibleTrigger className="w-full">
                <div className="flex items-center justify-between p-4 hover:bg-muted/50 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary/10">
                      <GroupIcon className="size-5 text-primary" />
                    </div>
                    <div className="text-left">
                      <h3 className="text-sm font-semibold">
                        {group.title}
                        {group.isOptional && (
                          <span className="ml-2 text-xs font-normal text-muted-foreground">
                            (Optional)
                          </span>
                        )}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        {group.description}
                      </p>
                    </div>
                  </div>
                  <ChevronDown
                    className={cn(
                      "size-5 text-muted-foreground transition-transform duration-200",
                      isOpen && "rotate-180",
                    )}
                  />
                </div>
              </CollapsibleTrigger>

              <CollapsibleContent>
                <div className="px-4 pb-4 space-y-6">
                  {group.sections.map((section) => (
                    <div key={section.id}>
                      <PromptField
                        section={section}
                        value={
                          (promptFields[
                            section.id as keyof PersonaPromptFields
                          ] as string) || ""
                        }
                        onChange={(value) =>
                          handleFieldChange(
                            section.id as keyof PersonaPromptFields,
                            value,
                          )
                        }
                      />
                    </div>
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
          </Card>
        );
      })}
    </div>
  );
}
