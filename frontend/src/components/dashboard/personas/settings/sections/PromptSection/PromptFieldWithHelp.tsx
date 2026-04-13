"use client";

import { HelpCircle } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { PromptFieldConfig } from "./constants";
import { usePromptDocumentation } from "./hooks/usePromptDocumentation";

interface PromptFieldWithHelpProps {
  config: PromptFieldConfig;
  value: string;
  onChange: (value: string) => void;
}

export function PromptFieldWithHelp({
  config,
  value,
  onChange,
}: PromptFieldWithHelpProps) {
  const { openGuideLink } = usePromptDocumentation();
  const Icon = config.icon;

  return (
    <div className="space-y-2">
      <div className="flex items-start gap-2">
        <Icon
          className={`size-5 flex-shrink-0 mt-1 ${
            config.isOptional ? "text-amber-500" : "text-amber-600"
          }`}
        />
        <div className="flex-1">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <label className="font-medium text-slate-900">
                {config.label}
                {config.isOptional && (
                  <span className="text-amber-600 font-normal ml-1">
                    (Optional)
                  </span>
                )}
              </label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="text-slate-400 hover:text-slate-600 transition-colors"
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
                  {config.tooltip}
                </TooltipContent>
              </Tooltip>
            </div>
            <button
              className="text-xs text-amber-600 hover:text-amber-700 font-medium flex-shrink-0 ml-3"
              onClick={() => openGuideLink(config.docAnchor)}
            >
              View example →
            </button>
          </div>
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className={`w-full min-h-[${config.minHeight}] p-3 border border-slate-300 rounded-lg resize-y text-[15px] focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent`}
            placeholder={config.placeholder}
          />
        </div>
      </div>
    </div>
  );
}
