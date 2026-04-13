import type { LucideIcon } from "lucide-react";

export type TierRequirement = "free" | "paid" | "business" | "enterprise";

export interface SettingsSection {
  id: string;
  label: string;
  title: string;
  description: string;
  icon: LucideIcon;
  conditional?: (context: SectionContext) => boolean;
  /** Minimum tier required to access this section */
  requiredTier?: TierRequirement;
  /** Whether to show section in sidebar but locked (vs hiding completely) */
  showLocked?: boolean;
}

export interface SectionContext {
  userTier?: string;
  userTierId?: number;
  voicesCount?: number;
  isPrivate?: boolean;
}

export interface PersonaSettingsProps {
  personaId: string;
}
