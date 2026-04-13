/**
 * Setup Progress Tracker
 * Manages localStorage flags for dashboard setup completion
 * to prevent flickering of the setup guide
 */

const STORAGE_KEYS = {
  HAS_KNOWLEDGE_LIBRARY: "hasCompletedKnowledgeLibrary",
  HAS_VOICE_CLONE: "hasCompletedVoiceClone",
  CURRENT_USERNAME: "currentUsername",
} as const;

/**
 * Check if user has completed knowledge library setup
 * Returns cached value from localStorage if available
 */
export function hasCompletedKnowledgeLibrary(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(STORAGE_KEYS.HAS_KNOWLEDGE_LIBRARY) === "true";
}

/**
 * Mark knowledge library as completed
 * Called when user successfully adds first knowledge source
 */
export function markKnowledgeLibraryComplete(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.HAS_KNOWLEDGE_LIBRARY, "true");
}

/**
 * Check if user has completed voice clone setup
 * Returns cached value from localStorage if available
 */
export function hasCompletedVoiceClone(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(STORAGE_KEYS.HAS_VOICE_CLONE) === "true";
}

/**
 * Mark voice clone as completed
 * Called when user successfully creates first voice clone
 */
export function markVoiceCloneComplete(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.HAS_VOICE_CLONE, "true");
}

/**
 * Reset all setup progress flags
 * Useful for testing or clearing cache
 */
export function resetSetupProgress(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(STORAGE_KEYS.HAS_KNOWLEDGE_LIBRARY);
  localStorage.removeItem(STORAGE_KEYS.HAS_VOICE_CLONE);
  localStorage.removeItem(STORAGE_KEYS.CURRENT_USERNAME);
}

/**
 * Store the current user's username for navigation purposes
 */
export function setCurrentUsername(username: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEYS.CURRENT_USERNAME, username);
}

/**
 * Get the current user's username
 */
export function getCurrentUsername(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEYS.CURRENT_USERNAME);
}
