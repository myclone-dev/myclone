"use client";

import { useState } from "react";
import { ChevronDown, Sparkles } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { PromptFieldWithHelp } from "./PromptFieldWithHelp";
import { ADVANCED_FIELDS } from "./constants";
import type { PersonaPromptFields } from "@/lib/queries/prompt";

interface AdvancedSettingsSectionProps {
  promptFields: Partial<PersonaPromptFields>;
  onFieldChange: (field: keyof PersonaPromptFields, value: string) => void;
}

export function AdvancedSettingsSection({
  promptFields,
  onFieldChange,
}: AdvancedSettingsSectionProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

  return (
    <div className="pt-6 border-t border-slate-200">
      <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
        <CollapsibleTrigger asChild>
          <button className="w-full flex items-center justify-between p-4 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg transition-colors">
            <div className="flex items-center gap-3">
              <div className="size-10 rounded-lg bg-white border border-amber-200 flex items-center justify-center">
                <Sparkles className="size-5 text-amber-600" />
              </div>
              <div className="text-left">
                <div className="font-medium text-slate-900">
                  Advanced Settings{" "}
                  <span className="text-amber-600 font-normal">
                    (6 optional fields)
                  </span>
                </div>
                <div className="text-sm text-slate-600">
                  Fine-tune your persona's behavior and style
                </div>
              </div>
            </div>
            <ChevronDown
              className={`size-5 text-amber-500 transition-transform ${showAdvanced ? "rotate-180" : ""}`}
            />
          </button>
        </CollapsibleTrigger>

        <CollapsibleContent className="mt-6 space-y-8">
          {ADVANCED_FIELDS.map((field) => (
            <PromptFieldWithHelp
              key={field.id}
              config={field}
              value={
                (promptFields[field.id as keyof PersonaPromptFields] as
                  | string
                  | undefined) || ""
              }
              onChange={(value) =>
                onFieldChange(field.id as keyof PersonaPromptFields, value)
              }
            />
          ))}
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
