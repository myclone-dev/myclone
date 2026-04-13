/**
 * Tier management type definitions
 */

// Re-export tier constants for convenience
export {
  TIER_FREE,
  TIER_PRO,
  TIER_BUSINESS,
  TIER_ENTERPRISE,
  TIER_NAMES,
  TIER_DISPLAY_NAMES,
  HARD_LIMITS,
  isFreeTier,
  isPaidTier,
  isBusinessOrHigher,
  isEnterpriseTier,
  hasIntegrationsAccess,
  getTierDisplayName,
  isUnlimited,
  formatLimit,
} from "@/lib/constants/tiers";

export type { TierId, TierName } from "@/lib/constants/tiers";

// ==================== TIER PLAN TYPES ====================

export interface TierPlan {
  id: number;
  tier_name: string;
  // Raw text limits
  max_raw_text_storage_mb: number;
  max_raw_text_files: number;
  // Document limits
  max_document_file_size_mb: number;
  max_document_storage_mb: number;
  max_document_files: number;
  // Multimedia limits
  max_multimedia_file_size_mb: number;
  max_multimedia_storage_mb: number;
  max_multimedia_files: number;
  max_multimedia_duration_hours: number;
  // YouTube limits
  max_youtube_videos: number;
  max_youtube_video_duration_minutes: number;
  max_youtube_total_duration_hours: number;
  // Voice clone limits
  max_voice_clones: number;
  // Monthly usage limits
  max_voice_minutes_per_month?: number; // -1 = unlimited
  max_text_messages_per_month?: number; // -1 = unlimited
  // Persona limits
  max_personas: number;
  // Custom domain limits
  max_custom_domains: number;
  created_at: string;
  updated_at: string;
}

export interface TierPlansResponse {
  tier_plans: TierPlan[];
}

// ==================== SUBSCRIPTION TYPES ====================

export type SubscriptionStatus = "active" | "expired" | "cancelled" | "pending";

export interface UserSubscription {
  id: string;
  user_id: string;
  tier_id: number;
  tier_name: string;
  subscription_start_date: string;
  subscription_end_date: string | null;
  status: SubscriptionStatus;
  created_at: string;
  updated_at: string;
}

// ==================== USAGE TYPES ====================

export interface UsageMetric {
  used: number;
  limit: number;
  percentage: number;
}

export interface StorageUsageMetric {
  used_mb: number;
  limit_mb: number;
  percentage: number;
}

export interface DurationUsageMetric {
  used_hours: number;
  limit_hours: number;
  hard_limit_hours?: number;
  percentage: number;
}

export interface VideoUsageMetric {
  used: number;
  limit: number;
  hard_limit?: number;
  percentage: number;
}

export interface RawTextUsage {
  files: UsageMetric;
  storage: StorageUsageMetric;
}

export interface DocumentUsage {
  files: UsageMetric;
  storage: StorageUsageMetric;
  max_file_size_mb: number;
}

export interface MultimediaUsage {
  files: UsageMetric;
  storage: StorageUsageMetric;
  duration: DurationUsageMetric;
  max_file_size_mb: number;
}

export interface YouTubeUsage {
  videos: VideoUsageMetric;
  duration: DurationUsageMetric;
  max_video_duration_minutes: number;
  hard_limit_video_duration_minutes?: number;
}

// Voice usage types (charged to persona owner)
export interface PersonaVoiceUsage {
  persona_id: string;
  persona_name: string;
  display_name: string;
  minutes_used: number;
}

export interface VoiceUsage {
  minutes_used: number;
  minutes_limit: number; // -1 = unlimited
  percentage: number;
  reset_date: string | null;
  per_persona: PersonaVoiceUsage[];
}

// Text chat usage types (charged to persona owner)
export interface TextUsage {
  messages_used: number;
  messages_limit: number; // -1 = unlimited
  percentage: number;
  reset_date: string | null;
}

// Persona usage types
export interface PersonaUsage {
  used: number;
  limit: number; // -1 = unlimited
  percentage: number;
}

// Custom domain usage types
export interface CustomDomainUsage {
  limit: number; // -1 = unlimited
}

// ==================== ERROR TYPES ====================

/**
 * Error response when persona limit is exceeded
 * Returned by backend with 403 status and error_code: 'PERSONA_LIMIT_EXCEEDED'
 */
export interface PersonaLimitExceededError {
  message: string;
  error_code: "PERSONA_LIMIT_EXCEEDED";
  current_count: number;
  max_personas: number;
  tier: string;
}

/**
 * Type guard to check if an error detail is a PersonaLimitExceededError
 */
export function isPersonaLimitError(
  detail: unknown,
): detail is PersonaLimitExceededError {
  return (
    typeof detail === "object" &&
    detail !== null &&
    "error_code" in detail &&
    (detail as PersonaLimitExceededError).error_code ===
      "PERSONA_LIMIT_EXCEEDED"
  );
}

export interface TierUsageResponse {
  tier: string;
  raw_text: RawTextUsage;
  documents: DocumentUsage;
  multimedia: MultimediaUsage;
  youtube: YouTubeUsage;
  voice: VoiceUsage;
  text: TextUsage;
  personas: PersonaUsage;
  custom_domains: CustomDomainUsage;
}

// ==================== HELPER TYPES ====================

export interface TierLimits {
  // Document limits
  maxDocumentFiles: number;
  maxDocumentStorage: number;
  maxDocumentFileSize: number;
  // Multimedia limits
  maxMultimediaFiles: number;
  maxMultimediaStorage: number;
  maxMultimediaFileSize: number;
  maxMultimediaDuration: number;
  // YouTube limits
  maxYouTubeVideos: number;
  maxYouTubeVideoLength: number;
  maxYouTubeTotalDuration: number;
  // Raw text limits
  maxRawTextFiles: number;
  maxRawTextStorage: number;
  // Voice clone limits
  maxVoiceClones: number;
  // Persona limits
  maxPersonas: number;
}
