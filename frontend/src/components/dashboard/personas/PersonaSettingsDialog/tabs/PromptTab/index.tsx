"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Sparkles, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PersonaPromptFields } from "@/lib/queries/prompt";
import { basicPromptSections, advancedPromptSections } from "./promptSections";
import { PromptField } from "./PromptField";

interface PromptTabProps {
  promptFields: Partial<PersonaPromptFields>;
  onChange: (updates: Partial<PersonaPromptFields>) => void;
}

/**
 * Prompt Tab
 * Configure persona prompts with sidebar navigation
 * Includes 4 basic sections + 5 advanced sections
 * Data is fetched by parent component and passed as props
 */
export function PromptTab({ promptFields, onChange }: PromptTabProps) {
  const [activeSection, setActiveSection] = useState("introduction");
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

  const handleFieldChange = (
    fieldId: keyof PersonaPromptFields,
    value: string,
  ) => {
    onChange({ [fieldId]: value });
  };

  // Get current section
  const currentSection =
    [...basicPromptSections, ...advancedPromptSections].find(
      (s) => s.id === activeSection,
    ) || basicPromptSections[0];

  return (
    <div className="flex flex-col md:flex-row h-full overflow-hidden">
      {/* Sidebar Navigation */}
      <div className="md:w-56 lg:w-64 border-b md:border-b-0 md:border-r bg-muted/30 shrink-0">
        {/* Mobile: Horizontal scroll */}
        <div className="md:hidden overflow-x-auto">
          <div className="flex gap-2 p-3 min-w-max">
            {/* Basic Sections */}
            {basicPromptSections.map((section) => {
              const Icon = section.icon;
              return (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap",
                    activeSection === section.id
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "bg-background hover:bg-muted text-foreground border",
                  )}
                >
                  <Icon className="size-3.5 shrink-0" />
                  <span>{section.label}</span>
                </button>
              );
            })}
            {/* Advanced Sections */}
            {advancedPromptSections.map((section) => {
              const Icon = section.icon;
              return (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap",
                    activeSection === section.id
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "bg-background hover:bg-muted text-foreground border",
                  )}
                >
                  <Icon className="size-3.5 shrink-0" />
                  <span>{section.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Desktop: Vertical sidebar */}
        <ScrollArea className="hidden md:block h-full">
          <div className="p-3 lg:p-4 space-y-1.5 lg:space-y-2">
            {/* Basic Sections */}
            {basicPromptSections.map((section) => {
              const Icon = section.icon;
              return (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={cn(
                    "w-full flex items-center gap-2.5 lg:gap-3 px-3 lg:px-4 py-2.5 lg:py-3 rounded-lg text-sm font-medium transition-all",
                    activeSection === section.id
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "hover:bg-muted text-foreground",
                  )}
                >
                  <Icon className="size-4 shrink-0" />
                  <span className="text-left truncate">{section.label}</span>
                </button>
              );
            })}

            {/* Advanced Options Collapsible */}
            <Collapsible open={isAdvancedOpen} onOpenChange={setIsAdvancedOpen}>
              <CollapsibleTrigger asChild>
                <button
                  className={cn(
                    "w-full flex items-center gap-2.5 lg:gap-3 px-3 lg:px-4 py-2.5 lg:py-3 rounded-lg text-sm font-medium transition-all hover:bg-muted text-foreground",
                  )}
                >
                  <Sparkles className="size-4 shrink-0 text-primary" />
                  <span className="text-left flex-1 truncate">
                    Advanced Options
                  </span>
                  <ChevronDown
                    className={cn(
                      "size-4 transition-transform duration-200 shrink-0",
                      isAdvancedOpen && "rotate-180",
                    )}
                  />
                </button>
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-1 mt-1">
                {advancedPromptSections.map((section) => {
                  const Icon = section.icon;
                  return (
                    <button
                      key={section.id}
                      onClick={() => setActiveSection(section.id)}
                      className={cn(
                        "w-full flex items-center gap-2.5 lg:gap-3 pl-6 lg:pl-8 pr-3 lg:pr-4 py-2 lg:py-2.5 rounded-lg text-sm font-medium transition-all",
                        activeSection === section.id
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "hover:bg-muted text-foreground",
                      )}
                    >
                      <Icon className="size-4 shrink-0" />
                      <span className="text-left truncate">
                        {section.label}
                      </span>
                    </button>
                  );
                })}
              </CollapsibleContent>
            </Collapsible>
          </div>
        </ScrollArea>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden min-h-0">
        <ScrollArea className="h-full">
          <div className="p-4 md:p-6 max-w-4xl">
            <motion.div
              key={activeSection}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
            >
              <PromptField
                section={currentSection}
                value={
                  (promptFields[
                    activeSection as keyof PersonaPromptFields
                  ] as string) || ""
                }
                onChange={(value) =>
                  handleFieldChange(
                    activeSection as keyof PersonaPromptFields,
                    value,
                  )
                }
              />
            </motion.div>
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
