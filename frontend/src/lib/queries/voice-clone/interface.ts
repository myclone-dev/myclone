/**
 * Voice Clone API Interfaces
 */

import {
  TIER_FREE,
  TIER_PRO,
  TIER_BUSINESS,
  TIER_ENTERPRISE,
} from "@/lib/constants/tiers";

// Re-export tier constants for backward compatibility
export { TIER_FREE, TIER_PRO, TIER_BUSINESS, TIER_ENTERPRISE };

/**
 * Voice clone provider - All tiers use Cartesia
 */
export type VoiceCloneProvider = "cartesia" | "elevenlabs";

/**
 * Voice clone limits per tier (all use Cartesia)
 * - Free: 1 voice clone
 * - Pro: 1 voice clone
 * - Business: 3 voice clones
 * - Enterprise: Unlimited (-1)
 */
export const TIER_VOICE_CLONE_LIMITS: Record<number, number> = {
  [TIER_FREE]: 1,
  [TIER_PRO]: 1,
  [TIER_BUSINESS]: 3,
  [TIER_ENTERPRISE]: -1, // unlimited
};

/**
 * Get the voice clone provider based on user's tier
 * All tiers now use Cartesia
 */
export const getVoiceCloneProvider = (_tierId: number): VoiceCloneProvider => {
  return "cartesia";
};

/**
 * Get the maximum number of voice clones allowed for a tier
 * Returns -1 for unlimited
 */
export const getVoiceCloneLimit = (tierId: number): number => {
  return TIER_VOICE_CLONE_LIMITS[tierId] ?? 1;
};

export interface CreateVoiceCloneRequest {
  user_id: string;
  name: string;
  description?: string;
  files: File[];
  provider?: VoiceCloneProvider;
  remove_background_noise?: boolean;
  language?: string;
}

export interface CreateVoiceCloneResponse {
  voice_id: string;
  name: string;
  description?: string;
  created_at?: string;
  status: "success" | "partial_success" | "processing" | "ready" | "failed";
  message?: string;
  elevenlabs_voice_id?: string;
  components?: {
    s3_upload?: { status: string; files_count?: number };
    cartesia_api?: { status: string; voice_id?: string };
    elevenlabs_api?: { status: string; voice_id?: string };
    database_save?: { status: string };
  };
}

export interface VoiceClone {
  id: string;
  voice_id: string;
  name: string;
  description?: string;
  platform: "elevenlabs" | "cartesia";
  total_files: number;
  total_size_bytes: number;
  created_at: string;
}
