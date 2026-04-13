"use client";

import { Zap, Palette, Maximize2, Layout, Tag } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { CustomizeTab } from "../types";

interface CustomizeTabSelectorProps {
  activeTab: CustomizeTab;
  setActiveTab: (tab: CustomizeTab) => void;
}

const TABS = [
  { value: "essentials" as const, label: "Essentials", icon: Zap },
  { value: "theme" as const, label: "Theme", icon: Palette },
  { value: "size" as const, label: "Size", icon: Maximize2 },
  { value: "layout" as const, label: "Layout", icon: Layout },
  { value: "branding" as const, label: "Brand", icon: Tag },
];

export function CustomizeTabSelector({
  activeTab,
  setActiveTab,
}: CustomizeTabSelectorProps) {
  return (
    <div
      role="tablist"
      aria-label="Widget customization options"
      className="grid w-full grid-cols-5 gap-0.5 rounded-full bg-slate-100 p-1 sm:gap-1"
    >
      {TABS.map(({ value, label, icon: Icon }) => (
        <Tooltip key={value} delayDuration={0}>
          <TooltipTrigger asChild>
            <button
              role="tab"
              aria-selected={activeTab === value}
              aria-controls={`${value}-panel`}
              aria-label={label}
              onClick={() => setActiveTab(value)}
              className={`flex min-w-0 items-center justify-center gap-1 rounded-full px-1 py-1.5 text-xs font-medium transition-all sm:gap-1.5 sm:px-3 sm:py-2 sm:text-sm ${
                activeTab === value
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              <Icon
                className="size-3.5 shrink-0 sm:size-4"
                aria-hidden="true"
              />
              <span className="hidden truncate sm:inline">{label}</span>
            </button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-sm:hidden">
            <p>{label}</p>
          </TooltipContent>
        </Tooltip>
      ))}
    </div>
  );
}
