"use client";

import { Sparkles } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { SettingsSection, TierRequirement } from "./types";
import {
  isPaidTier,
  isBusinessOrHigher,
  isEnterpriseTier,
} from "@/lib/constants/tiers";

interface SettingsSidebarProps {
  sections: SettingsSection[];
  activeSection: string;
  onSectionChange: (sectionId: string) => void;
  className?: string;
  userTierId?: number;
}

/**
 * Check if user has access to a section based on tier requirement
 */
function hasAccessToSection(
  requiredTier: TierRequirement | undefined,
  userTierId: number | undefined,
): boolean {
  if (!requiredTier || requiredTier === "free") return true;

  switch (requiredTier) {
    case "paid":
      return isPaidTier(userTierId);
    case "business":
      return isBusinessOrHigher(userTierId);
    case "enterprise":
      return isEnterpriseTier(userTierId);
    default:
      return true;
  }
}

export function SettingsSidebar({
  sections,
  activeSection,
  onSectionChange,
  className,
  userTierId,
}: SettingsSidebarProps) {
  return (
    <aside
      className={cn(
        "w-64 border-r bg-muted/10 min-h-[calc(100vh-3.5rem)] sticky top-14",
        className,
      )}
    >
      <ScrollArea className="h-full py-6 px-4">
        <nav className="space-y-1">
          {sections.map((section) => {
            const Icon = section.icon;
            const isActive = activeSection === section.id;
            const hasAccess = hasAccessToSection(
              section.requiredTier,
              userTierId,
            );
            const isLocked = !hasAccess && section.showLocked;

            return (
              <button
                key={section.id}
                onClick={() => onSectionChange(section.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-yellow-bright text-black shadow-sm"
                    : "text-foreground/70 hover:bg-yellow-light hover:text-gray-700",
                )}
              >
                <Icon
                  className={cn(
                    "size-4 shrink-0",
                    isActive ? "text-black" : "text-foreground/50",
                  )}
                />
                <span className="flex-1 text-left">{section.label}</span>
                {isLocked && (
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium bg-gradient-to-r from-tier-pro-from to-tier-pro-to text-tier-pro-text">
                    <Sparkles className="size-3" />
                    Pro
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </ScrollArea>
    </aside>
  );
}
