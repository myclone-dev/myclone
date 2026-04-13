"use client";

import { HelpCircle } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { PromptSection } from "../../types";

interface PromptFieldProps {
  section: PromptSection;
  value: string;
  onChange: (value: string) => void;
  exampleChips?: string[];
}

/**
 * Reusable Prompt Field Component
 * Used for both basic and advanced prompt sections
 * Features: tooltips, character count
 */
export function PromptField({ section, value, onChange }: PromptFieldProps) {
  const Icon = section.icon;
  const charCount = value.length;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon className="size-5 text-primary" />
          <span className="flex-1">{section.label}</span>
          {section.description && (
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground transition-colors"
                  aria-label="Help"
                >
                  <HelpCircle className="size-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent
                side="top"
                sideOffset={8}
                className="w-[280px] bg-white text-black border border-border shadow-md text-sm text-wrap [&>svg]:fill-white"
              >
                {section.description}
              </TooltipContent>
            </Tooltip>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {/* Textarea */}
          <Textarea
            id={section.id}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={section.placeholder}
            rows={8}
            className="resize-y min-h-32 overflow-y-auto border-slate-300 [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-track]:bg-slate-100 [&::-webkit-scrollbar-thumb]:bg-slate-300 [&::-webkit-scrollbar-thumb]:rounded-full hover:[&::-webkit-scrollbar-thumb]:bg-slate-400"
          />

          {/* Character Count */}
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              {charCount} {charCount === 1 ? "character" : "characters"}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
