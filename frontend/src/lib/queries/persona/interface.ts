/**
 * Persona/Expert Clone type definitions
 */

export interface PersonaDetails {
  id: string;
  persona_name: string;
  name: string;
  role?: string;
  company?: string;
  description?: string;
  voice_id?: string;
  voice_enabled?: boolean;
  is_private: boolean;
  created_at: string;
  updated_at: string;
  // Email Capture Settings
  email_capture_enabled: boolean;
  email_capture_message_threshold: number;
  email_capture_require_fullname: boolean;
  email_capture_require_phone: boolean;
  // Conversational Lead Capture (agent collects info naturally during conversation)
  default_lead_capture_enabled?: boolean;
  // Calendar Integration Settings
  calendar_enabled?: boolean;
  calendar_url?: string | null;
  calendar_display_name?: string | null;
  // Language Settings
  language?: PersonaLanguage;
  // Session Time Limit Settings
  session_time_limit_enabled?: boolean;
  session_time_limit_minutes?: number;
  session_time_limit_warning_minutes?: number;
  // Persona-specific avatar (overrides user avatar when set)
  persona_avatar_url?: string;
  // Conversation Summary Email Settings
  send_summary_email_enabled?: boolean;

  // User fields (from /public endpoint)
  username?: string;
  fullname?: string; // User's full name
  avatar?: string; // User's profile avatar (fallback if no persona_avatar_url)
  location?: string;
  linkedin_url?: string;
  // Suggested questions for chat UI
  suggested_questions?: string[];
  // Widget customization settings (bubble icon, colors, sizes, etc.)
  widget_config?: {
    bubbleIcon?: string;
    simpleBubble?: boolean;
    avatarUrl?: string;
    headerTitle?: string;
    headerSubtitle?: string;
    showBranding?: boolean;
    showAvatar?: boolean;
    primaryColor?: string;
    backgroundColor?: string;
    bubbleBackgroundColor?: string;
    bubbleTextColor?: string;
    [key: string]: unknown;
  };
}

export interface PersonaStatus {
  username: string;
  persona_id: string;
  enrichment_status: {
    linkedin_completed: boolean;
    website_completed: boolean;
    twitter_completed: boolean;
    pdf_completed: boolean;
  };
  chat_enabled: boolean;
  total_chunks_processed: number;
  last_updated: string;
}

export interface UpdatePersonaRequest {
  fullname?: string;
  company_role?: string;
  description?: string;
  location?: string;
}

export interface UpdateVoiceSettingsRequest {
  voice_id: string; // Voice ID from voice clone, or empty string to use default
}

export interface UpdateVoiceSettingsResponse {
  // Returns full PersonaDetails object
  id: string;
  persona_name: string;
  name: string;
  role?: string;
  company?: string;
  description?: string;
  voice_id?: string;
  created_at: string;
  updated_at: string;
}

// Persona Knowledge Management Types
export interface PersonaKnowledgeSource {
  id: string;
  source_type: "linkedin" | "twitter" | "website" | "document" | "youtube";
  source_record_id: string;
  display_name: string;
  enabled: boolean;
  enabled_at?: string;
  disabled_at?: string;
  embeddings_count: number;
  created_at: string;
}

export interface PersonaKnowledgeResponse {
  persona_id: string;
  persona_name: string;
  name: string;
  sources: PersonaKnowledgeSource[];
  total_sources: number;
  enabled_sources: number;
  total_embeddings: number;
}

export interface AvailableKnowledgeSource {
  source_type: "linkedin" | "twitter" | "website" | "document" | "youtube";
  source_record_id: string;
  display_name: string;
  embeddings_count: number;
  is_attached: boolean;
  is_enabled: boolean;
  metadata: Record<string, unknown>;
}

export interface AvailableKnowledgeSourcesResponse {
  persona_id: string;
  user_id: string;
  available_sources: AvailableKnowledgeSource[];
  total_available: number;
  already_attached: number;
}

export interface KnowledgeSourceAttachment {
  source_type: "linkedin" | "twitter" | "website" | "document" | "youtube";
  source_record_id: string;
}

export interface AttachKnowledgeRequest {
  sources: KnowledgeSourceAttachment[];
}

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

export interface PersonaCreateWithKnowledge {
  persona_name: string;
  name: string;
  role?: string;
  expertise?: string;
  company?: string;
  description?: string;
  voice_id?: string;
  voice_enabled?: boolean;
  greeting_message?: string;
  knowledge_sources?: KnowledgeSourceAttachment[];
  // Email Capture Settings
  email_capture_enabled?: boolean;
  email_capture_message_threshold?: number;
  email_capture_require_fullname?: boolean;
  email_capture_require_phone?: boolean;
  // Conversational Lead Capture
  default_lead_capture_enabled?: boolean;
  // Calendar Integration Settings
  calendar_enabled?: boolean;
  calendar_url?: string | null;
  calendar_display_name?: string | null;
  // Language Settings
  language?: PersonaLanguage;
  // Session Time Limit Settings
  session_time_limit_enabled?: boolean;
  session_time_limit_minutes?: number;
  session_time_limit_warning_minutes?: number;
}

export interface PersonaWithKnowledgeResponse {
  id: string;
  user_id: string;
  persona_name: string;
  name: string;
  role?: string;
  expertise?: string;
  company?: string;
  description?: string;
  voice_id?: string;
  voice_enabled?: boolean;
  greeting_message?: string;
  // Persona-specific avatar
  persona_avatar_url?: string;
  knowledge_sources_count: number;
  enabled_sources_count: number;
  total_embeddings: number;
  created_at: string;
  updated_at: string;
  is_private: boolean;
  access_control_enabled_at: string | null;
  // Email Capture Settings
  email_capture_enabled?: boolean;
  email_capture_message_threshold?: number;
  email_capture_require_fullname?: boolean;
  email_capture_require_phone?: boolean;
  // Conversational Lead Capture
  default_lead_capture_enabled?: boolean;
  // Calendar Integration Settings
  calendar_enabled?: boolean;
  calendar_url?: string | null;
  calendar_display_name?: string | null;
  // Language Settings
  language?: PersonaLanguage;
  // Session Time Limit Settings
  session_time_limit_enabled?: boolean;
  session_time_limit_minutes?: number;
  session_time_limit_warning_minutes?: number;
  // Conversation Summary Email Settings
  send_summary_email_enabled?: boolean;
}

export interface UserPersonasResponse {
  user_id: string;
  personas: PersonaWithKnowledgeResponse[];
  total_personas: number;
}

/**
 * Persona name availability check
 * Used to validate persona name before creation
 */
export interface PersonaNameAvailabilityResponse {
  original_name: string; // The original name user provided
  persona_name: string; // The slugified version that will be stored
  available: boolean; // true if name can be used, false otherwise
  reason: string | null; // Error message if unavailable, null if available
}
