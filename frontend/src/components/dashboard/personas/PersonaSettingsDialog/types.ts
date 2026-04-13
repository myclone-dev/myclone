import type { LucideIcon } from "lucide-react";
import type { PricingModel } from "@/lib/queries/stripe";
import type { PersonaPromptFields } from "@/lib/queries/prompt";

/**
 * Persona entity from API
 */
/**
 * Supported language codes for persona TTS and responses
 * auto: No language restriction (default)
 * en: English, hi: Hindi, es: Spanish, fr: French
 * zh: Chinese, de: German, ar: Arabic, it: Italian
 * el: Greek, cs: Czech, ja: Japanese, pt: Portuguese
 * nl: Dutch, ko: Korean, pl: Polish
 */
export type PersonaLanguage =
  | "auto"
  | "en"
  | "hi"
  | "es"
  | "fr"
  | "zh"
  | "de"
  | "ar"
  | "it"
  | "el"
  | "cs"
  | "ja"
  | "pt"
  | "nl"
  | "ko"
  | "pl"
  | "sv";

export interface Persona {
  id: string;
  persona_name: string;
  name: string;
  role: string;
  expertise?: string;
  description?: string;
  greeting_message?: string;
  voice_id?: string;
  voice_enabled?: boolean;
  is_private?: boolean;
  email_capture_enabled?: boolean;
  email_capture_message_threshold?: number;
  email_capture_require_fullname?: boolean;
  email_capture_require_phone?: boolean;
  // Conversational Lead Capture (agent collects info naturally)
  default_lead_capture_enabled?: boolean;
  calendar_enabled?: boolean;
  calendar_url?: string;
  calendar_display_name?: string;
  language?: PersonaLanguage;
  // Session Time Limit Settings
  session_time_limit_enabled?: boolean;
  session_time_limit_minutes?: number;
  session_time_limit_warning_minutes?: number;
  // Persona-specific avatar
  persona_avatar_url?: string;
  // Conversation Summary Email Settings
  send_summary_email_enabled?: boolean;
}

/**
 * Main dialog props
 */
export interface PersonaSettingsDialogProps {
  persona: Persona;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  trigger?: React.ReactNode;
  onSuccess?: () => void;
  /** Show creation loading overlay - use when persona was just created */
  isCreating?: boolean;
  /** Called when prompt data finishes loading (for newly created personas) */
  onCreationComplete?: () => void;
}

/**
 * Tab identifiers
 */
export type SettingsTab =
  | "basic"
  | "avatar"
  | "prompt"
  | "voice"
  | "language"
  | "email"
  | "calendar"
  | "monetization"
  | "session";

/**
 * Tab configuration
 */
export interface TabConfig {
  id: SettingsTab;
  label: string;
  shortLabel?: string; // For mobile view
  icon: LucideIcon;
  visibilityCondition?: boolean;
}

/**
 * Tab visibility context (for determining which tabs to show)
 */
export interface TabVisibilityContext {
  canSelectMultipleVoices: boolean;
  hasMultipleVoices: boolean;
}

/**
 * Basic info form data
 */
export interface BasicInfoFormData {
  name: string;
  role: string;
  expertise: string;
  description: string;
  greetingMessage: string;
}

/**
 * Email capture settings
 */
export interface EmailCaptureSettings {
  enabled: boolean;
  threshold: number;
  requireFullname: boolean;
  requirePhone: boolean;
  /** When true, the AI agent collects name/email/phone naturally during conversation instead of using a popup form */
  defaultLeadCaptureEnabled: boolean;
}

/**
 * Calendar integration settings
 */
export interface CalendarSettings {
  enabled: boolean;
  url: string;
  displayName: string;
}

/**
 * Session time limit settings
 */
export interface SessionTimeLimitSettings {
  enabled: boolean;
  limitMinutes: number;
  warningMinutes: number;
}

/**
 * Monetization settings
 */
export interface MonetizationSettings {
  isActive: boolean; // Whether monetization is enabled (replaces "free" pricing model)
  pricingModel: PricingModel;
  priceInCents: number;
  accessDurationDays: number | null;
}

/**
 * Complete persona settings state
 */
export interface PersonaSettingsState {
  basicInfo: BasicInfoFormData;
  emailCapture: EmailCaptureSettings;
  calendar: CalendarSettings;
  sessionTimeLimit: SessionTimeLimitSettings;
  monetization: MonetizationSettings;
  voiceId: string | undefined;
  promptFields: Partial<PersonaPromptFields>;
  suggestedQuestions: string[];
}

/**
 * Validation result
 */
export interface ValidationResult {
  valid: boolean;
  error?: string;
}

/**
 * Prompt section configuration
 */
export interface PromptSection {
  id: keyof PersonaPromptFields;
  label: string;
  icon: LucideIcon;
  placeholder: string;
  description?: string;
  infoTitle?: string;
  infoDescription?: string;
  infoDetails?: string[];
}

/**
 * Advanced prompt info data
 */
export interface AdvancedPromptInfo {
  title: string;
  description: string;
  details: string[];
}

/**
 * Tab component props (shared interface for all tab components)
 */
export interface TabComponentProps<T = unknown> {
  state: T;
  onChange: (value: Partial<T>) => void;
  isLoading?: boolean;
}
