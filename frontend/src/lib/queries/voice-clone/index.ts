/**
 * Voice Clone Query Hooks
 * Centralized exports for voice clone API operations
 *
 * Tier-based provider selection:
 * - Free tier (tier_id = 0): Cartesia (1 voice clone)
 * - Pro tier (tier_id = 1): ElevenLabs (1 voice clone)
 * - Business tier (tier_id = 2): Cartesia (3 voice clones)
 * - Enterprise tier (tier_id = 3): ElevenLabs (unlimited voice clones)
 */

export * from "./interface";
export * from "./useCreateVoiceClone";
export * from "./useDeleteVoiceClone";
export * from "./useVoiceClones";
