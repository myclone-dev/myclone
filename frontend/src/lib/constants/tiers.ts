/**
 * Tier/Plan Constants
 * Defines tier IDs, names, and default limits for the platform
 */

// ==================== TIER IDS ====================

export const TIER_FREE = 0;
export const TIER_PRO = 1;
export const TIER_BUSINESS = 2;
export const TIER_ENTERPRISE = 3;

// ==================== TIER NAMES ====================

export const TIER_NAMES = {
  [TIER_FREE]: "free",
  [TIER_PRO]: "pro",
  [TIER_BUSINESS]: "business",
  [TIER_ENTERPRISE]: "enterprise",
} as const;

export const TIER_DISPLAY_NAMES = {
  [TIER_FREE]: "Free",
  [TIER_PRO]: "Pro",
  [TIER_BUSINESS]: "Business",
  [TIER_ENTERPRISE]: "Enterprise",
} as const;

// ==================== TYPE DEFINITIONS ====================

export type TierId =
  | typeof TIER_FREE
  | typeof TIER_PRO
  | typeof TIER_BUSINESS
  | typeof TIER_ENTERPRISE;

export type TierName = (typeof TIER_NAMES)[TierId];

// ==================== DEFAULT LIMITS (FREE TIER) ====================

/**
 * Default limits for free tier users.
 *
 * ⚠️ IMPORTANT: Do NOT use these values in UI components!
 * Always fetch actual limits from the backend via useUserUsage() hook.
 * The backend is the source of truth for all tier limits.
 *
 * These constants exist only for:
 * - Documentation of expected free tier limits
 * - Type definitions and test fixtures
 * - Emergency fallback if API is completely unavailable
 *
 * @deprecated Prefer using backend-provided limits from useUserUsage()
 */
export const FREE_TIER_LIMITS = {
  // Raw text limits
  max_raw_text_storage_mb: 10,
  max_raw_text_files: 5,

  // Document limits
  max_document_file_size_mb: 10,
  max_document_storage_mb: 50,
  max_document_files: 3,

  // Multimedia limits
  max_multimedia_file_size_mb: 50,
  max_multimedia_storage_mb: 100,
  max_multimedia_files: 2,
  max_multimedia_duration_hours: 1,

  // YouTube limits
  max_youtube_videos: 5,
  max_youtube_video_duration_minutes: 30,
  max_youtube_total_duration_hours: 2,

  // Voice clone limits
  max_voice_clones: 1,

  // Monthly usage limits
  max_voice_minutes_per_month: 10,
  max_text_messages_per_month: 500,

  // Persona limits (1 default + 1 custom)
  max_personas: 2,
} as const;

// ==================== HARD LIMITS (ALL TIERS) ====================

/**
 * Hard limits that cannot be exceeded even for enterprise tier
 * These are platform-wide safety limits
 */
export const HARD_LIMITS = {
  multimedia_duration_hours: 6,
  youtube_video_duration_minutes: 120,
  youtube_videos: 1000,
} as const;

// ==================== HELPER FUNCTIONS ====================

/**
 * Check if a tier is free tier
 */
export function isFreeTier(tierId: number | undefined | null): boolean {
  return tierId === TIER_FREE || tierId === undefined || tierId === null;
}

/**
 * Check if a tier is a paid tier (Pro or higher)
 */
export function isPaidTier(tierId: number | undefined | null): boolean {
  return tierId !== undefined && tierId !== null && tierId >= TIER_PRO;
}

/**
 * Check if a tier is business or higher (Business, Enterprise)
 */
export function isBusinessOrHigher(tierId: number | undefined | null): boolean {
  return tierId !== undefined && tierId !== null && tierId >= TIER_BUSINESS;
}

/**
 * Check if a tier is enterprise
 */
export function isEnterpriseTier(tierId: number | undefined | null): boolean {
  return tierId === TIER_ENTERPRISE;
}

/**
 * Check if a tier allows multiple voice clones (2+ voice clones)
 * Business (2) and Enterprise (3) allow 2+ voice clones
 */
export function canHaveMultipleVoiceClones(
  tierId: number | undefined | null,
): boolean {
  return tierId === TIER_BUSINESS || tierId === TIER_ENTERPRISE;
}

/**
 * Check if a tier has access to integrations (Business, Enterprise)
 */
export function hasIntegrationsAccess(
  tierId: number | undefined | null,
): boolean {
  return tierId === TIER_BUSINESS || tierId === TIER_ENTERPRISE;
}

/**
 * Check if a tier has access to custom email domains (Enterprise only)
 */
export function hasCustomEmailDomainAccess(
  tierId: number | undefined | null,
): boolean {
  return tierId === TIER_ENTERPRISE;
}

/**
 * Get display name for a tier
 */
export function getTierDisplayName(tierId: number | undefined | null): string {
  if (tierId === undefined || tierId === null) return "Free";
  return TIER_DISPLAY_NAMES[tierId as TierId] || "Unknown";
}

/**
 * Check if a value represents "unlimited" (-1)
 */
export function isUnlimited(limit: number): boolean {
  return limit === -1;
}

/**
 * Format a limit value for display
 */
export function formatLimit(limit: number, unit?: string): string {
  if (isUnlimited(limit)) return "Unlimited";
  if (unit) return `${limit} ${unit}`;
  return limit.toString();
}
