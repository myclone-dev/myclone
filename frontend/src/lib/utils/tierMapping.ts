/**
 * Utility functions for workflow template tier access control
 * Works with tier IDs (integers) from the backend
 */

import {
  TIER_FREE,
  TIER_PRO,
  TIER_BUSINESS,
  TIER_ENTERPRISE,
} from "@/lib/constants/tiers";

/**
 * Tier information mapping
 */
const TIER_INFO = {
  [TIER_FREE]: { name: "free", label: "Free", order: 0 },
  [TIER_PRO]: { name: "pro", label: "Pro", order: 1 },
  [TIER_BUSINESS]: { name: "business", label: "Business", order: 2 },
  [TIER_ENTERPRISE]: { name: "enterprise", label: "Enterprise", order: 3 },
} as const;

/**
 * Check if user has access to a template based on their tier ID
 *
 * @param userTierId - User's current tier ID
 * @param templateTierId - Template's minimum required tier ID
 * @returns true if user has access, false otherwise
 */
export function hasTemplateAccess(
  userTierId: number | undefined | null,
  templateTierId: number,
): boolean {
  const currentTierId = userTierId ?? TIER_FREE;

  // Free tier templates (0): accessible to everyone
  if (templateTierId === TIER_FREE) {
    return true;
  }

  // Professional tier templates (1): accessible to Pro, Business, and Enterprise
  if (templateTierId === TIER_PRO) {
    return (
      currentTierId === TIER_PRO ||
      currentTierId === TIER_BUSINESS ||
      currentTierId === TIER_ENTERPRISE
    );
  }

  // Business tier templates (2): accessible to Business and Enterprise
  if (templateTierId === TIER_BUSINESS) {
    return currentTierId === TIER_BUSINESS || currentTierId === TIER_ENTERPRISE;
  }

  // Enterprise tier templates (3): accessible to Enterprise only
  if (templateTierId === TIER_ENTERPRISE) {
    return currentTierId === TIER_ENTERPRISE;
  }

  return false;
}

/**
 * Get display name for a tier ID
 * @param tierId - Tier ID (0-3)
 * @returns Display name (e.g., "Enterprise")
 */
export function getTierDisplayName(tierId: number): string {
  return TIER_INFO[tierId as keyof typeof TIER_INFO]?.label || "Unknown";
}

/**
 * Get badge CSS classes for a tier ID
 * @param tierId - Tier ID (0-3)
 * @returns Tailwind classes for badge styling
 */
export function getTierBadgeClass(tierId: number): string {
  switch (tierId) {
    case TIER_FREE:
      return "bg-gray-100 text-gray-700";
    case TIER_PRO:
      return "bg-yellow-light text-yellow-900 border border-yellow-bright";
    case TIER_BUSINESS:
      return "bg-blue-100 text-blue-700 border border-blue-300";
    case TIER_ENTERPRISE:
      return "bg-purple-100 text-purple-700 border border-purple-300";
    default:
      return "bg-gray-100 text-gray-700";
  }
}
